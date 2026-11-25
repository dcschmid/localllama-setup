#!/usr/bin/env python3
"""Collect and validate article exports from isolated, real Studio chat jobs."""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def request(base, path, data=None):
    payload = json.dumps(data).encode() if data is not None else None
    with urlopen(Request(base + "/api/" + path, payload, {"Content-Type": "application/json"}), timeout=30) as result:
        return json.load(result)


def save(folder, name, value):
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collection(args):
    end = time.monotonic() + args.minutes * 60
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    records = {}
    pending = dict(cases)
    accepted = {}
    while pending and time.monotonic() < end:
        for case, spec in list(pending.items()):
            try:
                task = request(args.url, "chat/tasks/" + spec["task_id"])
            except (URLError, TimeoutError):
                # The same job remains valid during an isolated Studio restart.
                continue
            writing = task["steps"]["writing"]
            state = {"task": task["status"], "writing": writing["status"],
                     "document_id": task.get("document_id"), "publication": writing.get("publishing"),
                     "corrections": writing.get("corrections"), "error": task.get("error"),
                     "skills": writing.get("skills", {}), "source": spec.get("source")}
            if records.get(case) != state:
                records[case] = state
                save(args.output, "article-status.json", records)
                print(case, json.dumps(state, ensure_ascii=False), flush=True)
            if task["status"] not in ("completed", "failed", "partial", "cancelled"):
                continue
            pending.pop(case)
            save(args.output, case + "-report.json", task)
            if not state["document_id"]:
                continue
            doc = request(args.url, "documents/" + state["document_id"])
            checks = {"version": doc["version"], "language": doc["lang"],
                      "stored": bool(doc["body"]), "publication": state["publication"]}
            if expected := spec.get("lang"):
                assert doc["lang"] == expected, case
            versions = request(args.url, "documents/" + doc["id"] + "/versions")
            if doc["version"] > 1:
                original = next(version for version in versions if version["version"] == 1)
                save(args.output, case + "-original.json",
                     request(args.url, f"documents/{doc['id']}/versions/{original['id']}"))
            for fmt in ("md", "mdx"):
                data = request(args.url, "export", {"doc_id": doc["id"], "format": fmt})
                text = data["files"][0]["content"]
                assert re.match(r"\A(?:\ufeff)?---\r?\n.+?\r?\n---\r?\n", text, re.S), case
                assert doc["body"] in text, case  # These text fixtures have no Studio image IDs.
                (args.output / f"{case}.{fmt}").write_text(text, encoding="utf-8")
                checks[fmt] = True
            if spec.get("source"):
                checks["source_confirmed"] = any(f.get("verdict") == "supported"
                    and f.get("source_url") == spec["source"] for f in writing.get("findings", []))
            if spec.get("expect_code"):
                checks["code_block"] = bool(re.search(r"(?ms)^`{3}python\b.*?^`{3}\s*$", doc["body"]))
            save(args.output, case + "-checks.json", checks)
            accepted[case] = (not spec.get("source") or checks["source_confirmed"]) and (
                not spec.get("expect_code") or checks["code_block"])
        if pending:
            time.sleep(8)
    return 2 if pending or any(state["task"] != "completed" or state["publication"] != "ready"
                             or not accepted.get(case) for case, state in records.items()) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, type=lambda value: value.rstrip("/"))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minutes", type=float, default=120)
    raise SystemExit(collection(parser.parse_args()))
