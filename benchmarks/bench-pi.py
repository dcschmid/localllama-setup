#!/usr/bin/env python3
"""Run the MetalVault task against one installed Pi profile and emit metrics only."""

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
from urllib.request import ProxyHandler, build_opener

from pi_benchmark_metrics import model_pid, server_timings

PROMPT = (
    "In MetalVault, make merge_duplicates reject a repeated ID in drop_ids "
    "with DuplicateError before changing the database. This prevents silently "
    "accepting duplicate drop IDs and preserves the valid transaction behavior "
    "and existing self-merge guard. Limit source changes to "
    "metavault/duplicates.py, do not modify tests, and run python3 -m unittest discover -s tests -q. "
    "Report the result briefly."
)
FILES = ("metavault", "tests")
SOURCE = "metavault/duplicates.py"
SAMPLING = Path(__file__).with_name("pi-benchmark-sampling.ts")
URL = "http://127.0.0.1:8080"
MODEL = "coding-cyber-tiel-35b"
OPENER = build_opener(ProxyHandler({}))


def router(path):
    with OPENER.open(URL + path, timeout=5) as response:
        return json.load(response)


def backend_resources():
    values = subprocess.run(
        ["systemctl", "--user", "show", "-p", "MemoryCurrent", "-p", "CPUUsageNSec", "llama-cpp.service"],
        text=True, capture_output=True,
    )
    resources = {}
    for row in values.stdout.splitlines():
        key, _, value = row.partition("=")
        if value.isdecimal():
            resources[key] = int(value)
    return resources

def inventory(project):
    if any(path.is_symlink() for path in project.rglob("*")):
        raise ValueError("unexpected symlink in fixture")
    return {
        str(path.relative_to(project)): sha256(path.read_bytes()).hexdigest()
        for path in project.rglob("*") if path.is_file() and not any(part in ("__pycache__", ".pytest_cache", ".ruff_cache", ".git")
                                      for part in path.relative_to(project).parts)
    }


def make_project(source, project):
    project.mkdir()
    for name in FILES:
        shutil.copytree(
            source / name, project / name,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache", ".git"), symlinks=True,
        )


def grade(project, original):
    try:
        current = inventory(project)
    except ValueError:
        return {"accepted": False, "reason": "unexpected symlink in fixture"}
    changed = sorted(k for k in original.keys() | current.keys() if original.get(k) != current.get(k))
    isolated = [
        "bwrap", "--unshare-all", "--die-with-parent", "--clearenv",
        "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev",
        "--tmpfs", "/tmp", "--ro-bind", str(project), "/fixture",
        "--chdir", "/fixture", "--setenv", "PATH", "/usr/bin",
    ]
    suite = subprocess.run(
        [*isolated, "/usr/bin/python3", "-m", "unittest", "discover", "-s", "tests", "-q"],
        capture_output=True, text=True, timeout=60,
    )
    total = re.search(r"Ran (\d+) tests?", suite.stderr)
    failures = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", suite.stderr))
    counts = {"passed": int(total[1]) - failures, "failed": failures} if total else {}
    # The independent regression is outside the model's workspace until the
    # agent exits. It checks the error and absence of partial changes.
    regression = subprocess.run([*isolated, "/usr/bin/python3", "-c", """
from metavault.duplicates import DuplicateError, merge_duplicates
from tests.helpers import MetalVaultTestCase, _pid

case = MetalVaultTestCase()
case.setUp()
try:
    band = case.repo.create_artist(name="Band")
    keep = case.repo.create_album(artist_id=_pid(band.id), title="Keep")
    drop = case.repo.create_album(artist_id=_pid(band.id), title="Drop")
    case.repo.create_track(album_id=_pid(drop.id), title="Keep original")
    try:
        merge_duplicates(case.db, _pid(keep.id), [_pid(drop.id), _pid(drop.id)])
    except DuplicateError:
        pass
    else:
        raise AssertionError("repeated drop IDs must fail")
    assert len(case.repo.list_tracks(_pid(drop.id))) == 1
    assert case.repo.list_tracks(_pid(keep.id)) == []
finally:
    case.tearDown()
"""], capture_output=True, timeout=30)
    return {
        "existing_suite_exit": suite.returncode,
        "existing_tests_counted": counts,
        "regression_pass": regression.returncode == 0,
        "changed_files": changed,
        "accepted": suite.returncode == regression.returncode == 0 and changed == [SOURCE],
    }


def events(path):
    counters = Counter()
    usage = Counter()
    per_request = []
    compaction = []
    tool_counts = Counter()
    compact_start = turn_start = None
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
            event = row["event"]
            at = row["elapsed_s"]
        except (ValueError, KeyError, TypeError):
            continue
        kind = event.get("type")
        if kind == "turn_start":
            turn_start = at
        elif kind == "message_update" and turn_start is not None:
            update = event.get("assistantMessageEvent", {}).get("type")
            if update in ("text_delta", "thinking_delta", "toolcall_delta"):
                per_request.append(round(at - turn_start, 3))
                turn_start = None
        elif kind == "message_end":
            message = event.get("message", {})
            if message.get("role") != "assistant":
                continue
            counters["assistant_messages"] += 1
            if message.get("stopReason") in ("error", "aborted"):
                counters["failed_model_messages"] += 1
                continue
            counters["model_responses"] += 1
            tokens = message.get("usage", {})
            for key in ("input", "output", "cacheRead", "cacheWrite"):
                usage[key] += tokens.get(key, 0)
            usage["max_total"] = max(usage["max_total"], tokens.get("totalTokens", 0))
            if counters["model_responses"] == 1:
                usage["first_input"] = tokens.get("input", 0)
                usage["first_cache_read"] = tokens.get("cacheRead", 0)
        elif kind == "tool_execution_end":
            tool = event.get("toolName", "unknown")
            tool_counts[tool] += 1
            counters["tool_calls"] += 1
            if event.get("isError"):
                counters["failed_tools"] += 1
                if tool in ("edit", "replace", "write", "insert"):
                    counters["failed_edit_tools"] += 1
        elif kind == "compaction_start" and event.get("reason") != "manual":
            compact_start = at
        elif kind == "compaction_end":
            if compact_start is not None:
                compaction.append(round(at - compact_start, 3))
                compact_start = None
    return {
        "counts": dict(counters),
        "tool_counts": dict(tool_counts),
        "pi_tokens": dict(usage),
        "turn_start_to_first_client_delta_s": per_request,
        "automatic_compaction_wall_s": compaction,
        "permission_questions": None,
    }



def run(args, source, location, index):
    project = location / "project"
    if project.exists():
        shutil.rmtree(project)
    make_project(source, project)
    original = inventory(project)
    sampling = project / ".pi-benchmark-sampling.ts"
    shutil.copyfile(SAMPLING, sampling)
    path = location / f"run-{index}"
    gpu_path = path.with_suffix(".gpu")
    timings_path = path.with_suffix(".time")
    events_path = path.with_suffix(".events")
    launcher = str(Path(args.pi).expanduser().resolve())
    cmd = ["timeout", "--foreground", "--kill-after=10", str(args.timeout), launcher, "--perm", "build",
           "--no-approve", "--no-context-files", "--no-session", "-e", sampling.name, "--mode", "json", "-p"]
    if args.thinking:
        cmd += ["--thinking", args.thinking]
    if args.variant == "lens-lean":
        cmd += ["--no-lens-context", "--no-read-expansion"]
    if not any(m["id"] == MODEL and m["status"]["value"] == "loaded" for m in router("/models")["data"]):
        raise SystemExit("Load Coding Long 256K before the benchmark.")
    slot = router(f"/slots?model={MODEL}")
    if len(slot) != 1 or slot[0].get("is_processing") or slot[0].get("n_ctx") != 262144:
        raise SystemExit("Coding Long 256K needs one idle slot. Wait for the active request.")
    pid = model_pid()
    backend_start = backend_resources()
    power = Path("/sys/firmware/acpi/platform_profile")
    start = time.time()
    clock = time.monotonic()
    with gpu_path.open("w") as gpu_file, path.with_suffix(".stderr").open("w") as stderr, events_path.open("w") as log:
        gpu = subprocess.Popen(
            ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits", "-l", "2"], stdout=gpu_file, stderr=subprocess.DEVNULL,
        ) if shutil.which("nvidia-smi") else None
        try:
            with subprocess.Popen(
                ["/usr/bin/time", "-f", "%U %S %M", "-o", str(timings_path), *cmd, "--", PROMPT],
                cwd=project, stdout=subprocess.PIPE, stderr=stderr, text=True,
            ) as process:
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    log.write(json.dumps({"elapsed_s": time.monotonic() - clock, "event": event}) + "\n")
                code = process.wait()
        finally:
            if gpu is not None:
                gpu.terminate()
                gpu.wait(timeout=10)
    stop = time.time()
    stats = events(events_path)
    measured = server_timings(start, stop)
    gpu_rows = [tuple(float(x) for x in row.split(",")) for row in gpu_path.read_text().splitlines()
                if re.fullmatch(r"\d+(?:\.\d+)?,\s*\d+,\s*\d+", row)]
    resource = timings_path.read_text().splitlines()[-1:] if timings_path.exists() else []
    sampling_preserved = sampling.is_file() and not sampling.is_symlink() and sampling.read_bytes() == SAMPLING.read_bytes()
    if sampling_preserved:
        sampling.unlink()
    quality = grade(project, original)
    if not sampling_preserved:
        quality.update(accepted=False, reason="benchmark sampling extension changed")
    stable = pid != "0" and model_pid() == pid
    backend_stop = backend_resources()
    cpu_before = backend_start.get("CPUUsageNSec")
    cpu_after = backend_stop.get("CPUUsageNSec")
    return {
        "fixture": "metalvault-duplicate-drop-id",
        "source_sha256": sha256(json.dumps(original, sort_keys=True).encode()).hexdigest(),
        "profile": MODEL,
        "variant": args.variant,
        "requested_seed": 42,
        "thinking": args.thinking or "default",
        "sampling_fixture_preserved": sampling_preserved,
        "repeat": index,
        "cache_condition": "shared slot; classify using first request counters",
        "initial_slot_cached_tokens": slot[0].get("n_prompt_tokens_cache"),
        "power_profile": power.read_text().strip() if power.exists() else None,
        "wall_s": round(stop - start, 3),
        "pi_exit": code,
        "manual_interventions": 0,
        "router_pid_stable": stable,
        "server_observed_calls": len(measured),
        "server_counts_match_client": bool(measured) and len(measured) == stats["counts"].get("model_responses"),
        "backend_cgroup_memory_bytes_start_end": [
            backend_start.get("MemoryCurrent"), backend_stop.get("MemoryCurrent"),
        ],
        "backend_cgroup_cpu_s": round((cpu_after - cpu_before) / 1e9, 3)
        if stable and cpu_before is not None and cpu_after is not None else None,
        "server_timings": measured,
        "launcher_time_user_sys_max_rss_kib": resource,
        "gpu_samples": len(gpu_rows),
        "gpu_peak_temp_c_vram_mib_util_pct": [max(v) for v in zip(*gpu_rows)] if gpu_rows else None,
        **stats,
        "quality": quality,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() /
                        "dev/github/local-coding-tests/01-python-music-library")
    parser.add_argument("--pi", default="~/.local/bin/pi-sandbox")
    parser.add_argument("--variant", choices=("default", "lens-lean"), default="default")
    parser.add_argument("--thinking", choices=("off", "medium"))
    parser.add_argument("--repeat", type=int, choices=range(1, 11), default=1)
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()
    missing = [name for name in FILES if not (args.source / name).is_dir()]
    if missing:
        parser.error(f"fixture is missing: {', '.join(missing)}")
    if not 10 <= args.timeout <= 3600:
        parser.error("--timeout must be between 10 and 3600 seconds")
    os.umask(0o077)
    with TemporaryDirectory(prefix="pi-benchmark-", dir="/tmp") as tmp:
        for index in range(1, args.repeat + 1):
            print(json.dumps(run(args, args.source, Path(tmp), index)), flush=True)


if __name__ == "__main__":
    main()
