#!/usr/bin/env python3
"""Measure manual compaction and a resumed turn on a generated Pi transcript."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
import uuid
from urllib.request import ProxyHandler, Request, build_opener

from pi_benchmark_metrics import model_pid, server_timings

MODEL = "coding-cyber-tiel-35b"
ROUTER = "http://127.0.0.1:8080"
OPENER = build_opener(ProxyHandler({}))
CODING_FIXTURE = Path(__file__).with_name("fixtures") / "context-replay"
CODING_FILES = {"src/replay.py", "src/checkpoint.py"}
PINS = ("REPLAY_ORDER_644", "CHECKPOINT_FIELD_839", "FAILED_TEST_275", "OPEN_TASK_416")


def require_idle_slot():
    with OPENER.open(ROUTER + "/models", timeout=5) as response:
        catalog = json.load(response)
    if not any(m["id"] == MODEL and m["status"]["value"] == "loaded" for m in catalog["data"]):
        raise SystemExit("Load Coding Long 256K before the context benchmark.")
    with OPENER.open(ROUTER + f"/slots?model={MODEL}", timeout=5) as response:
        slots = json.load(response)
    if len(slots) != 1 or slots[0].get("is_processing") or slots[0].get("n_ctx") != 262144:
        raise SystemExit("The coding slot must be idle.")


def seed_transcript(project, target, thinking="off", coding=False, batches=None):
    raw = []
    stamp = datetime.now(timezone.utc)
    timestamp = stamp.isoformat()
    parent = None

    def entry(kind, **fields):
        nonlocal parent
        ident = f"{len(raw):08x}"
        raw.append({"type": kind, "id": ident, "parentId": parent, "timestamp": timestamp, **fields})
        parent = ident

    def message(role, content, **fields):
        entry("message", message={"role": role, "content": [{"type": "text", "text": content}],
                                  "timestamp": int(stamp.timestamp() * 1000), **fields})

    raw.append({"type": "session", "version": 3, "id": str(uuid.uuid4()),
                "cwd": str(project), "timestamp": timestamp})
    entry("model_change", provider="llama.cpp", modelId=MODEL)
    entry("thinking_level_change", thinkingLevel=thinking)
    message("user", f"""Continue this repository migration across multiple review rounds.
The protocol marker {PINS[0]} identifies the required replay order in src/replay.py.
Keep the checkpoint field {PINS[1]} when updating src/checkpoint.py.
The last blocking test is {PINS[2]} in tests/test_recovery.py.
The pending task is {PINS[3]}, checking rollback after an interrupted migration.
Preserve these exact identifiers in summaries and when resuming.""")
    if coding:
        message("user", """
The pending migration is in the real fixture files src/replay.py and src/checkpoint.py.
Implement replay(events): keep the first record seen for each id, then sort the kept
records by integer when ascending. Preserve input encounter order for ties and leave
the caller's list and records intact.
Implement checkpoint(events): return exactly {"CHECKPOINT_FIELD_839": [...]},
with ids in the order of the input events. Return an empty list under the same key
for an empty input. Preserve the existing public function signatures.
Change only those two source files and run python3 -m unittest discover -s tests -q.
""".strip())
    for batch in range(batches if batches is not None else max(4, target // 650)):
        # Perturb each identifier so this is a source-like workload rather than
        # one repeated token string. Actual prompt lengths come from inference.
        sample = "\n".join(
            f"def migrate_record_{batch}_{row}(record): return record.get('field_{batch}_{row}', {batch + row})"
            for row in range(32)
        )
        message("user", f"Review this synthetic editor preview from src/segment_{batch}.py:\n{sample}")
        message("assistant", f"Segment {batch} inspected. Pending acceptance and rollback checks continue.",
                api="openai-completions", provider="llama.cpp", model=MODEL, stopReason="stop",
                usage={"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0,
                       "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0}})
    path = project / "history.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in raw))
    return path


def router_json(path, payload):
    request = Request(ROUTER + path, json.dumps({"model": MODEL, **payload}).encode(),
                      headers={"Content-Type": "application/json"})
    with OPENER.open(request, timeout=20) as response:
        return json.load(response)


def calibrated_transcript(project, target, thinking, coding):
    batches = max(4, target // 930)
    for _ in range(5):
        history = seed_transcript(project, target, thinking, coding, batches)
        rows = (json.loads(line) for line in history.read_text().splitlines())
        messages = [
            {"role": row["message"]["role"], "content": row["message"]["content"][0]["text"]}
            for row in rows if row["type"] == "message"
        ]
        rendered = router_json("/apply-template", {
            "messages": messages,
            "chat_template_kwargs": {"enable_thinking": thinking != "off"},
        })["prompt"]
        tokens = len(router_json("/tokenize", {"content": rendered})["tokens"])
        if target - 1100 <= tokens <= target:
            return history, tokens
        batches = max(4, int(batches * (target - 150) / tokens))
    raise RuntimeError(f"Could not calibrate the transcript to {target} tokens (measured {tokens})")


def run(command, project, rpc=None, timeout=1800):
    start = time.monotonic()
    command = ["timeout", "--foreground", "--kill-after=10", str(timeout), *command]
    rows = []
    # Keep RPC stdin open until its asynchronous reply. Timestamp output
    # events so a priming turn can also report automatic compaction.
    with subprocess.Popen(
        command, cwd=project, stdin=subprocess.PIPE if rpc else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    ) as process:
        if rpc:
            process.stdin.write(json.dumps(rpc) + "\n")
            process.stdin.flush()
        for line in process.stdout:
            if not line.startswith("{"):
                continue
            row = json.loads(line)
            row["_benchmark_elapsed_s"] = time.monotonic() - start
            rows.append(row)
            if rpc and row.get("id") == rpc["id"] and row.get("type") == "response":
                break
        if rpc:
            process.stdin.close()
        code = process.wait()
    return code, round(time.monotonic() - start, 3), rows


def coding_snapshot(project):
    entries = {}
    for path in project.rglob("*"):
        relative = path.relative_to(project)
        if relative.parts[0] in {"candidate", "history.jsonl"} or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            entries[str(relative)] = "symlink"
        elif path.is_file():
            entries[str(relative)] = sha256(path.read_bytes()).hexdigest()
    return entries


def prepare_coding_fixture(project):
    for entry in project.iterdir():
        if entry.name == "candidate":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for directory in ("src", "tests"):
        shutil.copytree(CODING_FIXTURE / directory, project / directory,
                        ignore=shutil.ignore_patterns("__pycache__"))
    return coding_snapshot(project)


def grade_coding_fixture(project, before):
    after = coding_snapshot(project)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    acceptance = subprocess.run(
        ["bwrap", "--unshare-all", "--die-with-parent", "--clearenv",
         "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib64", "/lib64",
         "--ro-bind", str(project), "/fixture",
         "--ro-bind", str(CODING_FIXTURE / "acceptance.py"), "/acceptance.py",
         "--chdir", "/fixture", "/usr/bin/python3", "/acceptance.py"],
        capture_output=True, text=True, timeout=30,
    )
    count = re.search(r"^Ran (\d+) tests? in ", acceptance.stderr, re.MULTILINE)
    tests_run = int(count[1]) if count else 0
    failures = re.findall(r"^(?:FAIL|ERROR): (test_[a-z_]+) \(__main__\.ReplayAcceptance", acceptance.stderr,
                          re.MULTILINE)
    return {"changed_files": sorted(changed), "tests_exit": acceptance.returncode,
            "tests_run": tests_run, "failed_tests": failures,
            "accepted": acceptance.returncode == 0 and tests_run == 3 and changed == CODING_FILES}


def measure_turn(common, history, project, tool_args, prompt):
    start = time.time()
    code, wall, rows = run(
        common + ["--session", str(history), "--mode", "json", "-p", *tool_args, "--", prompt],
        project,
    )
    stop = time.time()
    messages = [row["message"] for row in rows if row.get("type") == "message_end"
                and row.get("message", {}).get("role") == "assistant"]
    answer = " ".join(block.get("text", "") for msg in messages[-1:]
                      for block in msg.get("content", []) if block.get("type") == "text")
    automatic_compactions = []
    compact_started = None
    for row in rows:
        if row.get("type") == "compaction_start" and row.get("reason") != "manual":
            compact_started = row["_benchmark_elapsed_s"]
        elif row.get("type") == "compaction_end" and compact_started is not None:
            automatic_compactions.append(round(row["_benchmark_elapsed_s"] - compact_started, 3))
            compact_started = None
    return {
        "exit": code, "wall_s": wall, "assistant_responded": bool(answer.strip()),
        "markers": sum(pin in answer for pin in PINS),
        "usage": [{k: v for k, v in m.get("usage", {}).items() if k != "cost"} for m in messages],
        "tool_calls": sum(row.get("type") == "tool_execution_end" for row in rows),
        "server_timings": server_timings(start, stop),
        "automatic_compactions_s": automatic_compactions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi", default="~/.local/bin/pi-sandbox")
    parser.add_argument("--target", type=int, choices=(16384, 32768, 65536, 131072, 196608, 245760),
                        default=32768, help="approximate fixture size")
    parser.add_argument("--extension-root", type=Path, help="local directory with a reviewed extension and its dependencies")
    parser.add_argument("--extension", type=Path, help="entry file relative to --extension-root")
    parser.add_argument("--thinking", choices=("off", "medium"), default="off")
    parser.add_argument("--calibrate", action="store_true",
                        help="size the synthetic transcript with the local model's chat template and tokenizer")
    parser.add_argument("--coding", action="store_true",
                        help="implement the early migration requirements and run independent tests")
    parser.add_argument("--prime-cache", action="store_true",
                        help="run an acknowledgement turn on the same transcript before compaction")
    parser.add_argument("--recall-tool", help="allow only this tool on the post-compaction turn")
    parser.add_argument("--repeat", type=int, choices=range(1, 11), default=1)
    args = parser.parse_args()
    if bool(args.extension_root) != bool(args.extension):
        parser.error("supply --extension-root and --extension together")
    if args.extension:
        if args.extension.is_absolute() or ".." in args.extension.parts:
            parser.error("--extension must be inside --extension-root")
    if args.coding and args.recall_tool:
        parser.error("--recall-tool restricts marker-only runs. Coding needs access to the edit and test tools.")
    if args.recall_tool and not re.fullmatch(r"[a-z][a-z0-9_]*", args.recall_tool):
        parser.error("invalid recall tool name")
    common = [str(Path(args.pi).expanduser().resolve()), "--perm", "build", "--no-approve", "--no-context-files",
              "--no-skills", "--no-prompt-templates", "--no-lens-context", "--no-read-expansion",
              "--thinking", args.thinking]
    with TemporaryDirectory(prefix="pi-context-", dir="/tmp") as tmp:
        project = Path(tmp)
        if args.extension_root:
            candidate = project / "candidate"
            shutil.copytree(args.extension_root, candidate, symlinks=True,
                            ignore=shutil.ignore_patterns(".git", "probe.stderr"))
            common.extend(("-e", str(candidate / args.extension)))
        for repeat in range(1, args.repeat + 1):
            require_idle_slot()
            before = prepare_coding_fixture(project) if args.coding else None
            if args.calibrate or args.target >= 131072:
                history, calibrated_tokens = calibrated_transcript(project, args.target, args.thinking, args.coding)
            else:
                history = seed_transcript(project, args.target, args.thinking, args.coding)
                calibrated_tokens = None
            pid = model_pid()
            prime = None
            if args.prime_cache:
                prime = measure_turn(common, history, project, ["--no-tools"],
                                     "Reply with exactly READY. The earlier migration plan remains in effect.")
                if prime["exit"] or not prime["assistant_responded"]:
                    print(json.dumps({"prime": prime, "compaction_completed": False,
                                      "reason": "cache priming turn failed"}), flush=True)
                    continue
            transcript = [json.loads(line) for line in history.read_text().splitlines()]
            automatic = prime is not None and any(row["type"] == "compaction" for row in transcript)
            if automatic:
                code, wall, reply, timings = prime["exit"], None, {}, None
            else:
                compact_start = time.time()
                code, wall, rows = run(
                    common + (["--no-tools"] if args.prime_cache else [])
                    + ["--mode", "rpc", "--session", str(history)], project,
                    {"type": "compact", "id": "compact",
                     "customInstructions": "Preserve the user requirements and exact identifiers."},
                )
                timings = server_timings(compact_start, time.time())
                reply = next((row for row in rows if row.get("id") == "compact"), {})
                transcript = [json.loads(line) for line in history.read_text().splitlines()]
            compaction = next((row for row in reversed(transcript) if row["type"] == "compaction"), {})
            better_report = next((
                row.get("data") for row in reversed(transcript)
                if row.get("customType") == "better-compaction-report"
            ), None)
            data = {
                "profile": MODEL, "target_fixture_tokens": args.target,
                "calibrated_transcript_tokens": calibrated_tokens,
                "variant": args.extension.name if args.extension else "native", "repeat": repeat,
                "thinking": args.thinking, "coding": args.coding, "prime": prime,
                "compaction_exit": code, "compaction_wall_s_including_startup": wall,
                "compaction_server_timings": timings,
                "automatic_compaction_during_prime": automatic,
                "compaction_extension_hook": compaction.get("fromHook"),
                "compaction_usage": {k: v for k, v in compaction["usage"].items() if k != "cost"}
                if compaction.get("usage") else None,
                "better_compaction_cache_read_tokens": better_report.get("cacheRead") if better_report else None,
                "better_compaction_thinking_ms": better_report.get("thinkingMs") if better_report else None,
                "compaction_completed": bool(reply.get("success") or compaction),
                "compaction_rpc_error": str(reply.get("error", "")).split("\n", 1)[0] or None,
                "compaction_rpc_response_received": bool(reply),
                "tokens_before_reported_by_pi": compaction.get("tokensBefore"),
                "markers_in_summary": sum(pin in compaction.get("summary", "") for pin in PINS) if compaction else None,
                "expected_markers": len(PINS),
            }
            if data["compaction_completed"]:
                if args.coding:
                    tool_args = []
                    prompt = ("Implement the pending migration from the earlier requirements. "
                              "Run the named tests and report the result and four identifiers.")
                else:
                    tool_args = ["--tools", args.recall_tool] if args.recall_tool else ["--no-tools"]
                    prompt = ("List the four exact identifiers from the initial migration plan: replay order, "
                              "checkpoint field, failing test and open task. Return only those identifiers.")
                resumed = measure_turn(common, history, project, tool_args, prompt)
                if before is not None:
                    data["coding_quality"] = grade_coding_fixture(project, before)
                data.update(
                    resumed_exit=resumed["exit"], resumed_wall_s=resumed["wall_s"],
                    markers_after_restart=resumed["markers"], resumed_usage=resumed["usage"],
                    resumed_tool_calls=resumed["tool_calls"], resumed_server_timings=resumed["server_timings"],
                    resumed_server_counts_match_client=(
                        len(resumed["server_timings"]) == len(resumed["usage"])
                        if resumed["server_timings"] and not resumed["automatic_compactions_s"] else None
                    ),
                )
            data["router_pid_stable"] = pid != "0" and model_pid() == pid
            print(json.dumps(data), flush=True)


if __name__ == "__main__":
    main()
