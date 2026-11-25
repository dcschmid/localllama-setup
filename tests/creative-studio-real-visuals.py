#!/usr/bin/env python3
"""Run a profile comparison through a dedicated Studio and its real image queue."""

import argparse
import base64
import json
import struct
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def call(root, path, data=None, raw=False):
    request = Request(root + "/api/" + path, json.dumps(data).encode() if data is not None else None,
                      {"Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response:
        return response.read() if raw else json.load(response)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def seed(root, riff):
    cases = [
        ("A", "anima-aesthetic"), ("B", "painterly-storybook"), ("C", "graphic-novel"),
        ("D", "soft-cinematic-anime"), ("E", "riff-racers-low-poly"), ("F", "riff-racers-high-poly"),
    ]
    base_story = ("At dusk, a young watchkeeper in a rust-red coat lifts a brass lantern at the weather station door. "
                  "Beyond the steps, snow holds the final lavender light and the lit window reflects on the ice.")
    riff_story = ("In Metal World, Mika Blaze leans into the foundry bend in the red Hard Rock Kart. "
                  "Its oversized black tires cut across graphite pavement. Amber industrial lights reflect on steel and gold trim.")
    tasks = {}
    for case, template in cases:
        race = case in ("E", "F")
        title = ("Riff Racers " if race else "Story ") + "Visual QA " + case
        pid = call(root, "projects", {"name": title, "kind": "story", "lang": "en"})["id"]
        sid = call(root, "sessions", {"title": title, "project_id": pid})["id"]
        profile = call(root, f"projects/{pid}/visual-profile")["profile"]
        body = {"version": profile["version"], "template": template}
        if race:
            base = {"characters": [], "locations": [{"name": "Metal World", "materials": "Steel and graphite",
                                                      "lighting": "Warm industrial amber"}]}
            for name, file, features in (
                ("Mika Blaze", "character-hero.png", "Black helmet with a red stripe; red-black racing suit with gold panels and black boots"),
                ("Hard Rock Kart", "vehicle-hero.png", "Red faceted nose and wing, gold edging, black open tubular chassis, four chunky tires"),
            ):
                ref = {"name": name, "features": features}
                if riff:
                    ref["attachment"] = call(root, "attachments", {"project_id": pid, "name": file,
                        "data": base64.b64encode((riff / file).read_bytes()).decode()})["id"]
                base["characters"].append(ref)
            body["bible"] = base
        profile = call(root, f"projects/{pid}/visual-profile", body)["profile"]
        did = call(root, "documents", {"project_id": pid, "title": "Visual QA", "kind": "chapter",
                                       "lang": "en", "body": riff_story if race else base_story})["id"]
        ident = uuid.uuid4().hex
        brief = "Create an image showing the action in this chapter. " + (riff_story if race else base_story)
        job = call(root, "chat/dispatch", {"workflow": "chat", "request_id": ident, "session_id": sid, "mode": "image",
                                          "document_id": did, "default_lang": "en", "text": brief,
                                          "image_options": {"seed": 42071}})
        assert job["id"] == ident, job
        tasks[case] = {"task": ident, "chat": sid, "document": did, "project": pid, "profile": profile}
    return tasks


def retry_failed(root, tasks):
    for case, task in tasks.items():
        current = call(root, "chat/tasks/" + task["task"])
        if current["status"] not in ("failed", "partial", "cancelled"):
            continue
        doc = call(root, "documents/" + task["document"])
        ident = uuid.uuid4().hex
        task.setdefault("previous_tasks", []).append(task["task"])
        call(root, "chat/dispatch", {"workflow": "chat", "request_id": ident, "session_id": task["chat"],
            "mode": "image", "document_id": task["document"], "default_lang": "en",
            "text": "Create an image showing the action in this chapter. " + doc["body"], "image_options": {"seed": 42071}})
        task["task"] = ident


def monitor(root, out, tasks, minutes):
    end = time.monotonic() + minutes * 60
    statuses = {}
    pending = set(tasks)
    while pending and time.monotonic() < end:
        for case in sorted(pending.copy()):
            task = tasks[case]
            try:
                current = call(root, "chat/tasks/" + task["task"])
            except (URLError, TimeoutError):
                continue
            child = current.get("image") or {}
            status = (current["status"], child.get("status"), child.get("waiting_reason"), current.get("steps", {}).get("image", {}).get("error"))
            if statuses.get(case) != status:
                statuses[case] = status
                print(case, status, flush=True)
                save(out / "progress.json", statuses)
            if status[0] not in ("completed", "failed", "partial", "cancelled"):
                continue
            pending.remove(case)
            save(out / f"{case}-result.json", current)
            if status[0] != "completed":
                continue
            png = call(root, "images/files/" + child["image_id"], raw=True)
            assert png[:8] == b"\x89PNG\r\n\x1a\n" and b"IEND" in png[-12:]
            assert struct.unpack(">II", png[16:24]) == (1024, 576), (case, child["request"])
            assert child["request"]["model"] == task["profile"]["model"]
            assert child["visual_profile"]["version"] == task["profile"]["version"]
            assert child["visual_profile"]["template"] == task["profile"]["template"]
            messages = call(root, f"sessions/{task['chat']}/messages")
            assert any(message["meta"].get("job_id") == task["task"] for message in messages)
            memories = call(root, f"projects/{task['project']}/memories")
            assert any(row["kind"] == "document-image" and row["key"] == f"{task['document']}/{child['image_id']}"
                       for row in memories)
            (out / f"{case}.png").write_bytes(png)
        if pending:
            time.sleep(8)
    return 0 if not pending and all(status[0] == "completed" for status in statuses.values()) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--riff-references", type=Path)
    parser.add_argument("--minutes", type=int, default=120)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = args.out / "cases.json"
    cases = json.loads(manifest.read_text()) if manifest.is_file() else seed(args.url, args.riff_references)
    if args.retry_failed:
        retry_failed(args.url, cases)
    save(manifest, cases)
    raise SystemExit(monitor(args.url, args.out, cases, args.minutes))
