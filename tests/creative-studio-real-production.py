#!/usr/bin/env python3
"""Drive an explicitly authorized local production run and collect actual artifacts."""

import argparse
import base64
import json
import time
import urllib.request
import zipfile
from io import BytesIO
from urllib.error import URLError
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
        try:
            plan_info = http(base)
        except (URLError, TimeoutError):
            time.sleep(3)
            continue
        job = plan_info["job"]
        status = {key: job.get(key) for key in ("status", "kind", "step", "number", "total", "waiting", "pause_reason", "error", "detail")}
        if status != previous:
            print(json.dumps(status, ensure_ascii=False), flush=True)
            save_json(folder / "status.json", status)
            previous = status
        if job["kind"] == "plan" and job["status"] == "completed" and args.start_approved_test:
            plan = plan_info["plan"]
            assert plan["language"] in ("de", "en") and plan["chapter_count"] == args.chapters
            assert [chapter["number"] for chapter in plan["chapters"]] == list(range(1, args.chapters + 1))
            assert all((chapter["minimum"], chapter["maximum"]) == (args.minimum, args.maximum) for chapter in plan["chapters"])
            assert len({chapter["beats"] for chapter in plan["chapters"]}) == args.chapters
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
                    assert [chapter["number"] for chapter in manuscript["chapters"]] == list(range(1, args.chapters + 1))
                    assert all(args.minimum <= chapter["words"] <= args.maximum and chapter["image"] for chapter in manuscript["chapters"])
                    if args.visual_profile:
                        assets = [manuscript["cover"], *(chapter["image"] for chapter in manuscript["chapters"])]
                        assert all(asset["dimensions"] == [1024, 576]
                                   and asset["visual_profile"]["template"] == args.visual_profile for asset in assets)
                    archive = http(base + "/export", {"format": "zip"})
                    raw = base64.b64decode(archive["base64"])
                    with zipfile.ZipFile(BytesIO(raw)) as bundle:
                        assert bundle.testzip() is None
                        images = [name for name in bundle.namelist() if name.endswith(".png")]
                        texts = [name for name in bundle.namelist() if name.endswith((".md", ".mdx"))]
                        assert len(images) == args.chapters + 1 and len(texts) == 2
                        for name in texts:
                            contents = bundle.read(name).decode()
                            assert all(path in contents for path in images) and "/api/images/" not in contents
                        if args.visual_profile:
                            metadata = json.loads(bundle.read("images/metadata.json"))
                            assert {item["path"] for item in metadata} == set(images)
                            assert all(item["alt"] and item["visual_profile"]["template"] == args.visual_profile for item in metadata)
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
    parser.add_argument("--chapters", type=int, default=8)
    parser.add_argument("--minimum", type=int, default=1000)
    parser.add_argument("--maximum", type=int, default=1500)
    parser.add_argument("--visual-profile")
    parser.add_argument("--start-approved-test", action="store_true",
                        help="Approve the distinct test proposal and start the authorized live test.")
    raise SystemExit(watch(parser.parse_args()))
