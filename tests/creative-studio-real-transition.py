#!/usr/bin/env python3
"""Verify the real write, repair, illustration and next-chapter path in a separate database."""

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_production as production


def test_plan():
    first = {
        "title": "The Brass Bell", "perspective": "Third person close to Nell.",
        "opening": "Nell arrives at the old ferry landing before the dawn crossing.",
        "conflict": "A loose chain has jammed the bell's clapper.",
        "beats": "Nell untangles the chain and rings the bell for the ferryman.",
        "development": "Nell chooses to tackle the problem herself.",
        "revelations": "The chain slipped through a cracked ring.",
        "tension": "Nell is trying to get across the river before the market opens.",
        "closing": "The ferryman hears the bell and turns his boat toward her.",
        "continuity": "Nell is alone at the landing. The ferryman is still on the water.",
        "illustration": "Nell pulls the chain free under a brass bell on a foggy wooden dock.",
        "minimum": 180, "maximum": 430,
    }
    second = {**first, "title": "Across the River",
              "opening": "The ferryman reaches Nell's landing.",
              "conflict": "Nell must protect her basket from rain.",
              "beats": "Nell shelters her basket on the ferry and crosses the river.",
              "closing": "Nell reaches the market on time."}
    return {
        **dict.fromkeys(production.PLAN, "Nell needs to cross a river to sell apples at the morning market."),
        "title": "The Bell at Heron Landing", "language": "en",
        "perspective": "Close third person past, following Nell.",
        "setting": "A quiet country river landing in autumn.",
        "bible": dict.fromkeys(production.BIBLE, "Nell brings apples to market. The ferry bell is on the near dock."),
        "visual": {**dict.fromkeys(production.VISUAL, "Muted ink wash, soft gray and brass."),
                   "model": "z-image-turbo", "preset": "none", "size": "768x768", "cover_size": "768x1024"},
        "chapters": [first, second],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for the isolated data and evidence.")
    parser.add_argument("--retry", action="store_true", help="Only retry a failed isolated test in the same output directory.")
    args = parser.parse_args()
    output = args.output.resolve()
    if not args.retry:
        output.mkdir(mode=0o700, parents=True)
    os.environ.update(XDG_DATA_HOME=str(output / "data"), XDG_CONFIG_HOME=str(output / "config"),
                      XDG_STATE_HOME=str(output / "state"))
    runtime = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
    runtime["migrate"]()
    db = runtime["db"]
    worker = runtime["production_worker"]
    call_model = worker.call
    def record_prompt_response(lang, role, prompt, tokens, schema=None):
        text, evidence, finish = call_model(lang, role, prompt, tokens, schema)
        if schema and "passage" in schema["properties"]:
            with (output / "image-prompt-responses.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"response": text, "finish": finish}, ensure_ascii=False) + "\n")
        return text, evidence, finish
    worker.call = record_prompt_response
    injected_version = None
    restarted = False
    previous, events = None, []
    pid, sid = uuid.uuid4().hex, uuid.uuid4().hex

    def action(name, **values):
        return production.mutate(db(), pid, name, {"session_id": sid, **values},
                                 runtime["save_document"], runtime["store_message"])[0]

    with db() as conn:
        if args.retry:
            prior = json.loads((output / "report.json").read_text(encoding="utf-8"))
            pid, identifier = prior["project_id"], prior["id"]
            row = production.job_state(conn, pid)
            assert row["id"] == identifier and row["state"] == "failed"
            sid = json.loads(row["payload"])["session_id"]
            injected_version, restarted, events = prior["injected_version"], prior["reopened_database"], prior["events"]
            action("retry", job_id=identifier)
        else:
            conn.execute("INSERT INTO projects(id,name,kind,lang) VALUES(?,?,'story','en')", (pid, "The Bell at Heron Landing"))
            conn.execute("INSERT INTO sessions(id,project_id,title) VALUES(?,?,?)", (sid, pid, "The Bell at Heron Landing"))
            action("save-plan", plan=test_plan())
            action("approve-plan", version=1)
            identifier = action("start", version=1, mode="automatic")["id"]

    deadline = time.monotonic() + 2400
    while time.monotonic() < deadline:
        row = production.job_state(db(), pid)
        result = json.loads(row["result"])
        job = production.public_job(row)
        current = result.get("current", {})
        image_job = current.get("image_job")
        image = db().execute("SELECT * FROM jobs WHERE id=?", (image_job,)).fetchone() if image_job else None
        phase = (job["status"], job["number"], job["phase"], job.get("waiting"), image["state"] if image else None)
        if phase != previous:
            previous = phase
            events.append(phase)
            print(*phase, flush=True)
        report = {"id": identifier, "project_id": pid, "status": job["status"], "events": events,
                  "result": result, "injected_version": injected_version, "reopened_database": restarted}
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if row["state"] in ("paused", "failed", "cancelled"):
            raise RuntimeError(f"Isolated job stopped in {job['phase']} with {job.get('error') or job.get('pause_reason')}")
        if job["number"] == 2 and job["step"] == "writing":
            receipt = result["chapter_results"][0]
            assert restarted and receipt["version"] > injected_version and receipt["corrections"] >= 1
            assert any(candidate["accepted"] for candidate in receipt["candidate_audits"])
            assert 1 <= len(receipt["patches"]) <= 2
            assert receipt["review"]["proof"][0]["skill_version"]
            assert db().execute("SELECT count(*) FROM jobs WHERE service='image' AND state='completed'").fetchone()[0] == 1
            body = production.managed_docs(db(), pid)[0]["body"]
            assert receipt["image"]["quote"] in body and "., but" not in body
            (output / "chapter-1.md").write_text(body + "\n", encoding="utf-8")
            with urllib.request.urlopen(runtime["IMAGES"] + "/studio/api/files/" + receipt["image"]["id"], timeout=30) as response:
                (output / "chapter-1.png").write_bytes(response.read())
            with db():
                action("pause", job_id=identifier)
            return
        if job["step"] == "auditing" and injected_version is None:
            document = production.managed_docs(db(), pid)[0]
            assert document["version"] >= 2 and document["body"]
            original = document["body"]
            damaged, count = re.subn(r",(?=\s+(?:but|and|or|yet)\b)", ".,", original, count=1)
            if not count:
                damaged = original + "\n\nThe bell was still., but the boat was moving."
            (output / "generated-before-fault.md").write_text(original + "\n", encoding="utf-8")
            with db() as conn:
                injected_version = production.organizer.update_document(conn, document, document["title"], damaged,
                                                                          "Isolated punctuation test", "user", "en")
            continue
        if image and not restarted:
            db().close()
            del runtime["_dbs"].conn
            restarted = True
            continue
        if image and image["state"] not in runtime["TERMINAL"]:
            runtime["advance_image"](image_job)
        if not worker.tick():
            time.sleep(2)
    raise RuntimeError("Isolated test reached its time limit")


if __name__ == "__main__":
    main()
