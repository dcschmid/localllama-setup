#!/usr/bin/env python3
"""Drive an explicitly authorized local production run and collect actual artifacts."""

import argparse
import base64
import json
import time
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path


def http(url, body=None, raw=False):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=150) as response:
        return response.read() if raw else json.load(response)


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def watch(args):
    folder = args.output
    run_path = folder / "run.json"
    receipt = json.loads(run_path.read_text(encoding="utf-8"))
    root = args.url.rstrip("/")
    base = root + "/api/production/" + receipt["project_id"]
    previous = None
    paused = {"blocker", "art", "chapter", "user"}
    while True:
        plan_info = http(base)
        job = plan_info["job"]
        status = {key: job.get(key) for key in ("status", "kind", "step", "number", "total", "waiting", "pause_reason", "error", "detail")}
        if status != previous:
            print(json.dumps(status, ensure_ascii=False), flush=True)
            save_json(folder / "status.json", status)
            previous = status
        if job["kind"] == "plan" and job["status"] == "completed" and args.start_approved_test:
            plan = plan_info["plan"]
            assert plan["language"] in ("de", "en") and plan["chapter_count"] == 8
            assert [chapter["number"] for chapter in plan["chapters"]] == list(range(1, 9))
            assert all((chapter["minimum"], chapter["maximum"]) == (1000, 1500) for chapter in plan["chapters"])
            assert len({chapter["beats"] for chapter in plan["chapters"]}) == 8
            if (plan_info.get("impact") or {}).get("outline_findings"):
                save_json(folder / "plan-for-review.json", plan_info)
                return 2
            http(base + "/approve-plan", {"version": plan_info["version"]})
            save_json(folder / "approved-plan.json", plan)
            story = http(base + "/start", {"version": plan_info["version"], "mode": "automatic", "session_id": receipt["session_id"]})
            receipt["production_job"] = story["id"]
            save_json(run_path, receipt)
            continue
        if job["status"] in ("failed", "cancelled") or job.get("pause_reason") in paused or job["status"] == "completed":
            save_json(folder / "job-report.json", http(base + "/report"))
            if job["kind"] == "story":
                manuscript = http(base + "/manuscript")
                target = folder / "material"
                target.mkdir(exist_ok=True)
                for chapter in manuscript["chapters"]:
                    if chapter["body"].strip():
                        (target / f"chapter-{chapter['number']:02}.md").write_text(
                            f"# {chapter['title']}\n\n{chapter['body']}\n", encoding="utf-8")
                    if image := chapter.get("image"):
                        (target / f"chapter-{chapter['number']:02}.png").write_bytes(http(root + "/api/images/files/" + image["id"], raw=True))
                if cover := manuscript.get("cover"):
                    (target / "cover.png").write_bytes(http(root + "/api/images/files/" + cover["id"], raw=True))
                save_json(folder / "manuscript-state.json", {**manuscript, "chapters": [
                    {k: v for k, v in chapter.items() if k != "body"} for chapter in manuscript["chapters"]]})
                if manuscript["complete"]:
                    assert [chapter["number"] for chapter in manuscript["chapters"]] == list(range(1, 9))
                    assert all(1000 <= chapter["words"] <= 1500 and chapter["image"] for chapter in manuscript["chapters"])
                    archive = http(base + "/export", {"format": "zip"})
                    raw = base64.b64decode(archive["base64"])
                    with zipfile.ZipFile(BytesIO(raw)) as bundle:
                        assert bundle.testzip() is None
                        assert len([name for name in bundle.namelist() if name.endswith(".png")]) == 9
                        assert len([name for name in bundle.namelist() if name.endswith((".md", ".mdx"))]) == 2
                    (folder / archive["name"]).write_bytes(raw)
                    for fmt in ("md", "mdx"):
                        export = http(base + "/export", {"format": fmt})
                        (folder / export["name"]).write_text(export["text"], encoding="utf-8")
            return 0 if job["status"] == "completed" else 2
        time.sleep(8)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-approved-test", action="store_true",
                        help="Approve the distinct eight-chapter test proposal and start the authorized live test.")
    raise SystemExit(watch(parser.parse_args()))
