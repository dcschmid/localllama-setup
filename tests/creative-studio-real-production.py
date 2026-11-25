#!/usr/bin/env python3
"""Drive an explicitly authorized local production run and collect actual artifacts."""

import argparse
import hashlib
import re
import struct
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
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
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
            report = http(base + "/report")
            save_json(folder / "job-report.json", report)
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
                if job["status"] == "completed":
                    assert manuscript["complete"], manuscript
                    assert [chapter["number"] for chapter in manuscript["chapters"]] == list(range(1, args.chapters + 1))
                    assert all(args.minimum <= chapter["words"] <= args.maximum and chapter["image"] for chapter in manuscript["chapters"])
                    manifest = job["manifest"]
                    assert manifest["completed_chapters"] == args.chapters and manifest["verified_images"] == args.chapters + 1
                    evidence = next(item["result"] for item in report if item["id"] == job["id"])
                    for entry, chapter in zip(evidence["chapter_results"], manuscript["chapters"], strict=True):
                        review = entry["review"]
                        assert entry["audit_id"] and hashlib.sha256(chapter["body"].encode()).hexdigest() == review["hash"]
                        assert "local" in review and review["language_proof"] and review["proof"]
                        for lane, skill in (("language_proof", "human-writing"), ("proof", "story-writing")):
                            assert any(s["name"] == skill and s["version"] for p in review[lane] for s in p["skills"])
                    assets = [manuscript["cover"], *(chapter["image"] for chapter in manuscript["chapters"])]
                    for asset, png_file in zip(assets, [target / "cover.png", *sorted(target.glob("chapter-*.png"))], strict=True):
                        data = png_file.read_bytes()
                        assert data.startswith(b"\x89PNG\r\n\x1a\n")
                        width, height = struct.unpack_from(">II", data, 16)
                        assert width * 9 == height * 16 and [width, height] == asset["dimensions"]
                        if args.visual_profile:
                            assert asset["visual_profile"]["template"] == args.visual_profile
                    paths = job["downloads"]
                    files = {fmt: http(root + paths[fmt], raw=True) for fmt in ("md", "mdx", "zip")}
                    for fmt, data in files.items():
                        name = f"manuscript.{fmt}"
                        assert hashlib.sha256(data).hexdigest() == manifest["exports"][name]["sha256"]
                        (folder / name).write_bytes(data)
                    with zipfile.ZipFile(BytesIO(files["zip"])) as bundle:
                        assert bundle.testzip() is None
                        bundled = json.loads(bundle.read("manifest.json"))
                        assert bundled["status"] == "completed" and "mdx_compile" in bundled["checks"]
                        assert len(bundled["images"]) == args.chapters + 1
                        for fmt in ("md", "mdx"):
                            assert bundle.read(f"manuscript.{fmt}") == files[fmt]
                            contents = files[fmt].decode()
                            assert len(re.findall(r"(?m)^## (?:Kapitel|Chapter) [0-9]+$", contents)) == args.chapters
                            assert all(f"]({entry['path']})" in contents for entry in bundled["images"])
                        for entry in bundled["images"]:
                            image = bundle.read(entry["path"])
                            assert image == http(root + paths["md"].rsplit("/", 1)[0] + "/" + entry["path"], raw=True)
                            assert hashlib.sha256(image).hexdigest() == entry["sha256"]
            return 0 if job["status"] == "completed" else 2
        time.sleep(8)
    return 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chapters", type=int, default=8)
    parser.add_argument("--minimum", type=int, default=1000)
    parser.add_argument("--maximum", type=int, default=1500)
    parser.add_argument("--visual-profile")
    parser.add_argument("--timeout", type=int, default=5400, help="Maximum number of seconds to follow the job.")
    parser.add_argument("--start-approved-test", action="store_true",
                        help="Approve the distinct test proposal and start the authorized live test.")
    raise SystemExit(watch(parser.parse_args()))
