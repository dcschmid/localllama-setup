#!/usr/bin/env python3
"""Measure a local llama.cpp worker on a repeatable repository branching workload."""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")


def grade(answer, branch):
    try:
        obj = json.loads(answer)
    except json.JSONDecodeError:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    rule = str(obj.get("rule", ""))
    duplicate_rule = r"(?i)first|original|earliest|skipp|returns?\s+`?none|does not re-apply"
    return {"key": obj.get("key") == branch + "-682", "days": obj.get("days") == 43,
            "rule": bool(re.search(duplicate_rule, rule))}


def process(pid):
    root = Path(f"/proc/{pid}")
    stat = (root / "stat").read_text().rsplit(")", 1)[1].split()
    fields = {}
    for file, keys in (("status", {"VmRSS", "VmHWM", "VmSwap"}), ("smaps_rollup", {"AnonHugePages"})):
        for line in (root / file).read_text().splitlines():
            key, _, value = line.partition(":")
            if key in keys:
                fields[key] = int(value.split()[0])
    return {"minor": int(stat[7]), "major": int(stat[9]),
            "cpu_ticks": int(stat[11]) + int(stat[12]), **fields}


def repository(branch, modules, edit):
    out = [f"Review the {branch} branch of this synthetic ledger repository."]
    for i in range(modules):
        if i == modules // 3:
            out.append(f"# config.py\nREVIEW_KEY = {branch + '-682'!r}\nRETAIN_DAYS = 43")
        if i == modules // 2 and edit:
            out.append("# CHANGE: the public report uses uppercase currency identifiers.")
        out.append(
            f"# {branch}/ledger_{i:04}.py\nfrom decimal import Decimal\n"
            f"def apply_event_{i}(row, processed):\n"
            "    # A retry keeps the original event, across all currencies.\n"
            "    if row['id'] in processed:\n        return None\n"
            "    processed.add(row['id'])\n"
            f"    return row['currency'].strip().upper(), Decimal(row['amount']) + Decimal('{i % 11}.125')\n"
        )
    return "\n".join(out)


def request(port, route, payload=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=900)
    conn.request("POST" if payload is not None else "GET", route, json.dumps(payload) if payload is not None else None,
                 {"Content-Type": "application/json"})
    response = conn.getresponse()
    if response.status != 200:
        error = response.read(512).decode(errors="replace")
        conn.close()
        raise RuntimeError(f"{route}: HTTP {response.status}: {error}")
    return conn, response


def measure(args, branch, edit, phase):
    content = repository(branch, args.modules, edit)
    content += "\nReturn JSON. Give the value of REVIEW_KEY as key and RETAIN_DAYS as days. State in rule what happens to duplicate IDs."
    response_format = {"type": "json_object", "schema": {"type": "object", "properties": {
        "key": {"type": "string"}, "days": {"type": "integer"}, "rule": {"type": "string"}},
        "required": ["key", "days", "rule"], "additionalProperties": False}}
    old = process(args.pid)
    start = time.monotonic()
    conn, response = request(args.port, "/v1/chat/completions", {
        "model": args.alias, "messages": [{"role": "user", "content": content}],
        "stream": True, "stream_options": {"include_usage": True}, "response_format": response_format,
        "temperature": 0, "seed": 843, "max_tokens": 96, "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False}, "reasoning_budget_tokens": 0,
    })
    first = None
    parts = []
    timing, usage = {}, {}
    try:
        for line in response:
            if not line.startswith(b"data: ") or line.startswith(b"data: [DONE]"):
                continue
            chunk = json.loads(line[6:])
            if chunk.get("error"):
                raise RuntimeError(chunk["error"])
            timing, usage = chunk.get("timings") or timing, chunk.get("usage") or usage
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                if first is None and (delta.get("content") or delta.get("reasoning_content")):
                    first = time.monotonic() - start
                parts.append(delta.get("content") or "")
    finally:
        conn.close()
    if first is None or not timing:
        raise RuntimeError(f"{args.alias}/{phase}: incomplete event stream, no valid measurement")
    wall = time.monotonic() - start
    new = process(args.pid)
    answer = "".join(parts)
    return {"case": args.case, "model": args.alias, "phase": phase, "ttft_s": first, "wall_s": wall,
            "minor_faults": new["minor"] - old["minor"], "major_faults": new["major"] - old["major"],
            "cpu_s": (new["cpu_ticks"] - old["cpu_ticks"]) / CLOCK_TICKS,
            **{k: v for k, v in new.items() if k not in ("minor", "major", "cpu_ticks")}, "timings": timing,
            "usage": usage, "quality": grade(answer, branch), "answer": answer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--pid", type=int, required=True, help="PID of the loaded model worker")
    parser.add_argument("--case", required=True)
    parser.add_argument("--modules", type=int, default=32)
    parser.add_argument("--flow", choices=["cold", "prefix", "branch"], default="branch")
    parser.add_argument("alias")
    args = parser.parse_args()
    conn, response = request(args.port, "/props?" + urlencode({"model": args.alias}))
    with response:
        if json.load(response)["model_alias"] != args.alias:
            raise SystemExit("unexpected model worker")
    conn.close()
    rows = [("atlas", False, "cold")]
    if args.flow == "prefix":
        rows += [("atlas", True, "edit"), ("atlas", True, "repeat")]
    if args.flow == "branch":
        rows += [("boreal", False, "switch"), ("atlas", False, "return"),
                 ("atlas", True, "edit"), ("atlas", True, "repeat")]
    for branch, edit, phase in rows:
        print(json.dumps(measure(args, branch, edit, phase), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
