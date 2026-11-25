#!/usr/bin/env python3
"""Drive the real persistence layer and production state machine with deterministic upstreams."""

import contextlib
import json
import os
import re
import runpy
import struct
import threading
import zlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_production as production

PROSE = "When Mara opened the drawer, she found the key beneath a sheet of paper. She held the key to the light and gave it to Nera. The lock turned as the last bell rang. The record was still there."
BLOCK = "The lock turned as the last bell rang."


def example_plan():
    return production.validate_plan({
        **{key: key.replace("_", " ") + " about a lost key" for key in production.PLAN},
        "title": "The Key in the Drawer", "language": "en", "motifs": [], "audience": "General readers",
        "bible": {key: "Mara and Nera look for the key." for key in production.BIBLE},
        "visual": {**{key: "Ink wash in red and gray" for key in production.VISUAL}, "size": "768x768", "cover_size": "768x768"},
        "chapters": [{**{key: "Mara opens the drawer." for key in production.CHAPTER}, "title": "The drawer", "minimum": 38, "maximum": 60}],
    })


def fake_model(lang, role, prompt, tokens, schema=None):
    def data(value):
        return json.dumps(value), {"model_id": "fixture", "skill_version": "fixture", "role": role}, "stop"
    if role == "write":
        return PROSE, {"model_id": "fixture", "role": role}, "stop"
    keys = schema["properties"]
    if "bible" in keys:
        plan = example_plan()
        return data({k: plan[k] for k in keys})
    if "chapters" in keys:
        return data({"chapters": example_plan()["chapters"]})
    if "answer" in keys:
        if "changes" not in keys:
            return data({"answer": "Das Ende löst Maras Suche ein."})
        revised = "Verbessere Kapitel 4" in prompt
        change = ("Mara gibt Nera den Schlüssel." if revised else "Der Archivar leiht den Schlüssel erst am Abend."
                  if "Prüfe die acht Kapitel" in prompt else "Der Schlüssel gehörte dem Archivar.")
        return data({"answer": "Die Kapitelpläne wurden miteinander verglichen.", "findings": [
            {"chapter": "1", "quote": "Mara opens the drawer.", "issue": "Der Grund für Maras Suche fehlt.",
             "correction": "Nenne die Herkunft des Schlüssels."},
            {"chapter": "2", "quote": "This is absent from the outline.", "issue": "Ein erfundener Beleg wäre unzulässig.",
             "correction": "Verwirf den Befund."},
        ], "changes": [{"section": "chapter", "chapter": "4" if revised else "1", "field": "continuity",
                        "value": change}]})
    if "scenes" in keys:
        size = int(re.search(r"Plan exactly (\d+) scenes", prompt)[1])
        return data({"scenes": [{key: "Mara finds the key." for key in production.SCENE} for _ in range(size)]})
    if "summary" in keys:
        return data({"summary": "Mara and Nera find the key.", "findings": [
                        {"quote": "The record was still there.", "related_quote": "", "issue": "Fixture claim",
                         "correction": "", "category": "naturalness", "severity": "editorial"}], "editorial": [],
                     "memory": [{"kind": "object", "status": "established", "fact": "Mara found the key in the drawer.",
                                 "quote": "she found the key beneath a sheet of paper."}]})
    if "assessment" in keys:
        return data({"assessment": "The promised discovery closes the story.", "findings": []})
    if "verdicts" in keys:
        return data({"verdicts": []})
    if "findings" in keys:
        return data({"findings": []})
    if "alt" in keys:
        return data({"prompt": "Ink wash of Mara and Nera by an open drawer.",
                     "passage": "1", "alt": "Mara and Nera at the open drawer"})
    if "edits" in keys:
        return data({"edits": []})
    raise AssertionError(keys)


class Fixture:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {
            "XDG_DATA_HOME": self.tmp.name, "XDG_CONFIG_HOME": self.tmp.name, "XDG_STATE_HOME": self.tmp.name,
        })
        self.env.start()
        self.backend = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
        self.backend["migrate"]()
        self.conn = self.backend["db"]()
        self.worker = self.backend["production_worker"]
        self.worker.call = fake_model
        self.worker.visual_compose = None
        self.worker.image_verify = lambda image, size: [int(side) for side in size.split("x")]
        return self

    def __exit__(self, *_):
        self.conn.close()
        self.env.stop()
        self.tmp.cleanup()

    def create(self):
        self.pid, self.sid = "a" * 32, "b" * 32
        with self.conn:
            self.conn.execute("INSERT INTO projects(id,name,kind,lang) VALUES(?, 'The Key in the Drawer','story','en')", (self.pid,))
            self.conn.execute("INSERT INTO sessions(id,project_id,title) VALUES(?,?,'The Key in the Drawer')", (self.sid, self.pid))

    def change(self, action, **values):
        with self.conn:
            body = {"session_id": self.sid, **values}
            if action == "start":
                body.setdefault("review_art", True)
            return production.mutate(self.conn, self.pid, action, body,
                                     self.backend["save_document"], self.backend["store_message"])[0]

    def uploads(self):
        images = self.conn.execute("SELECT * FROM jobs WHERE service='image' AND state='waiting_gpu'").fetchall()
        with self.conn:
            for row in images:
                img = row["id"]
                result = {"id": img, "status": "completed", "image_id": img, "request": json.loads(row["payload"])["request"]}
                self.conn.execute("UPDATE jobs SET state='completed',result=?,external_id=? WHERE id=?",
                                  (production.dump(result), img, img))

    def drive(self, stop=("paused", "failed", "completed"), checkpoints=75):
        for _ in range(checkpoints):
            job = production.job_state(self.conn, self.pid)
            if job["state"] in stop:
                return job
            self.uploads()
            self.worker.tick()
        raise AssertionError(dict(job))

    def start(self, mode="automatic"):
        self.create()
        plan = self.change("save-plan", plan=example_plan())
        self.change("approve-plan", version=plan["version"])
        return self.change("start", version=plan["version"], mode=mode)["id"]


class ProductionTests(unittest.TestCase):
    def test_image_preflight_releases_only_its_sleeping_writer_and_rechecks_gpu(self):
        with Fixture() as f:
            f.backend["gpu_holders"] = lambda: [(6, "/usr/bin/kwin_wayland", 7),
                                                (7, "/usr/local/bin/llama-server", 162)]
            f.backend["llama_worker_alias"] = lambda _: "author"
            state = "loaded"
            calls = []

            def upstream(url, method="GET", body=None, **_):
                if url.endswith("/health"):
                    return 200, {"backend_pid": 9, "busy": False}
                if url.endswith("/v1/models"):
                    return 200, {"data": [{"id": "author", "status": {"value": state}}]}
                self.assertTrue(url.endswith("/models/unload"))
                calls.append((method, body))
                return 200, {"success": True}

            f.backend["http_json"] = upstream
            check = f.backend["gpu_free"]
            self.assertFalse(check(production=True, writer="someone-else")[0])
            self.assertFalse(check(production=True, writer="author")[0])
            self.assertEqual(calls, [])
            state = "sleeping"
            self.assertFalse(check(production=True, writer="author")[0])
            self.assertEqual(calls, [("POST", {"model": "author"})])
            f.backend["gpu_holders"] = lambda: [(6, "/usr/bin/kwin_wayland", 7), (9, "/usr/bin/sd-server", 286)]
            self.assertEqual(check(production=True, writer="author"), (True, ""))

    def test_image_selection_retries_without_rewriting_or_submitting_an_image(self):
        with Fixture() as f:
            identifier = f.start()
            for _ in range(12):
                f.worker.tick()
                job = production.job_state(f.conn, f.pid)
                if production.public_job(job)["phase"] == "image_prompt":
                    break
            self.assertEqual(production.public_job(job)["phase"], "image_prompt")
            checkpoint = json.loads(job["result"])["current"]
            self.assertEqual(checkpoint["version"], checkpoint["text_finalized_version"])
            self.assertEqual(checkpoint["review"]["words"], production.story.count_words(PROSE))

            def invalid_selection(lang, role, prompt, tokens, schema):
                self.assertIn("1", schema["properties"]["passage"]["enum"])
                return json.dumps({"passage": "100", "alt": "An invented event", "prompt": "A sea battle."}), {}, "stop"

            f.worker.call = invalid_selection
            for attempt in range(3):
                f.worker.tick()
                job = production.job_state(f.conn, f.pid)
                if attempt < 2:
                    self.assertEqual(production.public_job(job)["retry"]["attempt"], attempt + 1)
                    with f.conn:
                        f.conn.execute("UPDATE jobs SET result=json_remove(result,'$.next_at') WHERE id=?", (identifier,))
            failed = production.public_job(job)
            self.assertEqual((failed["status"], failed["phase"], failed["error"]),
                             ("failed", "image_prompt", "production_image_evidence"))
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 0)
            self.assertEqual(json.loads(job["result"])["current"], checkpoint)
            f.change("retry", job_id=identifier)
            f.worker.call = lambda *_: (json.dumps({"passage": "1", "alt": "", "prompt": ""}), {}, "stop")
            f.worker.tick()
            queued = json.loads(production.job_state(f.conn, f.pid)["result"])
            self.assertEqual(production.work_phase(queued), "image_queue")
            prompt = queued["current"]["image_prompt"]
            self.assertIn(prompt["quote"], PROSE)
            self.assertIn(prompt["quote"], prompt["prompt"])
            self.assertEqual(prompt["prompt_source"], "selected_passage")
            self.assertEqual(prompt["alt"], "Illustration for The drawer")

    def test_archive_retry_reuses_completed_image_and_finalized_text(self):
        with Fixture() as f:
            identifier = f.start()
            verified = f.worker.image_verify

            def unavailable(*_):
                raise production.PlanError("image_archive_missing")

            f.worker.image_verify = unavailable
            failed = f.drive()
            status = production.public_job(failed)
            self.assertEqual((status["status"], status["phase"], status["error"]),
                             ("failed", "image_archive", "image_archive_missing"))
            slot = json.loads(failed["result"])["current"]
            f.change("retry", job_id=identifier)
            f.worker.image_verify = verified
            f.worker.tick()
            restored = json.loads(production.job_state(f.conn, f.pid)["result"])
            self.assertEqual(restored["step"], "finalizing")
            self.assertEqual(restored["current"]["asset"]["job_id"], slot["image_job"])
            self.assertEqual(restored["current"]["text_finalized_version"], slot["version"])
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 1)

    def test_failed_image_queue_transaction_keeps_prompt_checkpoint(self):
        with Fixture() as f:
            f.start()
            for _ in range(12):
                f.worker.tick()
                job = production.job_state(f.conn, f.pid)
                if production.public_job(job)["phase"] == "image_queue":
                    break
            self.assertEqual(production.public_job(job)["phase"], "image_queue")
            original = json.loads(job["result"])["current"]
            queue = f.worker.image_queue

            def rollback(*args, **kwargs):
                queue(*args, **kwargs)
                raise TimeoutError

            f.worker.image_queue = rollback
            f.worker.tick()
            retried = production.job_state(f.conn, f.pid)
            self.assertEqual(production.public_job(retried)["retry"]["attempt"], 1)
            self.assertEqual(json.loads(retried["result"])["current"], original)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 0)
            f.worker.image_queue = queue
            with f.conn:
                f.conn.execute("UPDATE jobs SET result=json_remove(result,'$.next_at') WHERE id=?", (job["id"],))
            f.worker.tick()
            self.assertEqual(production.public_job(production.job_state(f.conn, f.pid))["image_state"], "waiting_gpu")
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 1)

    def test_invalid_rewrite_output_has_two_attempts_and_keeps_reviewed_prose(self):
        with Fixture() as f:
            f.start()
            for _ in range(10):
                f.worker.tick()
                job = production.job_state(f.conn, f.pid)
                if production.public_job(job)["phase"] == "reviewed":
                    break
            result = json.loads(job["result"])
            result["current"]["review"]["findings"] = [{
                "status": "confirmed", "severity": "automatic", "category": "grammar",
                "start": 0, "end": 24, "quote": PROSE[:24], "issue": "Fixture correction."
            }]
            with f.conn:
                f.conn.execute("UPDATE jobs SET result=? WHERE id=?", (production.dump(result), job["id"]))

            def invalid_patch(lang, role, prompt, tokens, schema):
                self.assertEqual(role, "rewrite")
                return "{}", {}, "stop"

            f.worker.call = invalid_patch
            for _ in range(3):
                f.worker.tick()
            result = json.loads(production.job_state(f.conn, f.pid)["result"])
            self.assertEqual(result["step"], "text_finalize")
            self.assertEqual(result["current"]["passes"], 2)
            self.assertEqual([p["error"] for p in result["current"]["patches"]], ["story_model_format"] * 2)
            self.assertEqual(production.managed_docs(f.conn, f.pid)[0]["body"], PROSE)

    def test_only_approved_future_only_plan_changes_can_rebind_a_paused_job(self):
        with Fixture() as f:
            f.create()
            original = example_plan()
            original["chapters"].append({**original["chapters"][0], "title": "The window",
                                         "beats": "Nera opens the window."})
            f.change("save-plan", plan=original)
            f.change("approve-plan", version=1)
            identifier = f.change("start", version=1, mode="automatic")["id"]
            f.change("pause", job_id=identifier)
            docs = production.managed_docs(f.conn, f.pid)
            proposal = json.loads(production.latest_plan(f.conn, f.pid)["plan"])
            proposal["chapters"][1]["closing"] = "Nera hides the letter."
            f.change("save-plan", plan=proposal, version=1)
            with self.assertRaises(production.organizer.OrganizerError):
                f.change("resume", job_id=identifier, plan_version=2)
            self.assertEqual(production.job_state(f.conn, f.pid)["state"], "paused")
            f.change("approve-plan", version=2)
            f.change("resume", job_id=identifier, plan_version=2)
            rebound = production.job_state(f.conn, f.pid)
            self.assertEqual(rebound["id"], identifier)
            self.assertEqual(json.loads(rebound["result"])["plan_history"], [1])
            self.assertEqual(json.loads(rebound["result"])["plan_version"], 2)
            self.assertEqual(json.loads(rebound["payload"])["plan"]["chapters"][1]["closing"], "Nera hides the letter.")
            self.assertEqual([d["id"] for d in production.managed_docs(f.conn, f.pid)], [d["id"] for d in docs])

    def test_scene_checkpoints_archived_images_and_manifest(self):
        with Fixture() as f:
            identifier = f.start()
            for _ in range(10):
                f.worker.tick()
                if production.public_job(production.job_state(f.conn, f.pid))["phase"] == "reviewed":
                    break
            f.change("pause", job_id=identifier)
            paused = f.drive()
            self.assertEqual(paused["state"], "paused")
            data = json.loads(paused["result"])
            self.assertEqual(data["step"], "reviewed")
            # Resume through a fresh worker and a freshly opened database connection.
            f.conn.close()
            del f.backend["_dbs"].conn
            f.conn = f.backend["db"]()
            f.worker = production.ProductionWorker(f.backend["db"], f.backend["_lock"], fake_model,
                f.backend["production_skill"], f.backend["queue_image"], lambda *_: [768, 768],
                f.backend["store_message"], f.backend["running_work"])
            f.change("resume", job_id=identifier)
            art = f.drive()
            self.assertEqual(json.loads(art["result"])["step"], "art_review")
            self.assertFalse(production.manuscript(f.conn, f.pid)["complete"])
            f.change("approve-art", job_id=identifier)
            done = f.drive()
            self.assertEqual(done["state"], "completed", done["result"])
            result = json.loads(done["result"])
            self.assertEqual(result["whole_review"]["verified_assets"], 2)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 2)
            self.assertEqual(f.change("start", version=1, mode="automatic")["id"], identifier)
            doc = production.manuscript(f.conn, f.pid)
            self.assertTrue(doc["complete"])
            self.assertEqual(doc["chapters"][0]["body"], PROSE)
            self.assertIn("images/" + doc["cover"]["id"] + ".png", production.manuscript_text(doc, "mdx", True))
            self.assertEqual(len(result["chapter_results"][0]["memory"]), 1)

    def test_eight_chapter_production_and_total_word_count(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            template = plan["chapters"][0]
            plan["chapters"] = [{**template, "title": f"Drawer {n}", "beats": f"Mara finds record {n}.",
                                 "minimum": 1000, "maximum": 1500} for n in range(1, 9)]
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            identifier = f.change("start", version=1, mode="automatic")["id"]

            def eight_chapter_model(lang, role, prompt, tokens, schema=None):
                if role != "write":
                    return fake_model(lang, role, prompt, tokens, schema)
                section, chapter = re.search(r"scene (\d+) of 2 of chapter (\d+)", prompt).groups()
                labels = [f"folio{chapter}x{section}x{i}" for i in range(65)]
                sentences = [f"The record {label} lay beside the key and the ledger." for label in labels]
                return ("When Mara opened the drawer, she paused. " + " ".join(sentences),
                        {"model_id": "fixture", "role": role}, "stop")
            f.worker.call = eight_chapter_model
            review = f.drive(checkpoints=600)
            state = json.loads(review["result"])
            self.assertEqual(state["step"], "art_review", state.get("detail"))
            f.change("approve-art", job_id=identifier)
            self.assertEqual(f.drive()["state"], "completed")
            chapters = production.manuscript(f.conn, f.pid)["chapters"]
            self.assertEqual([c["number"] for c in chapters], list(range(1, 9)))
            self.assertTrue(all(1000 <= c["words"] <= 1500 for c in chapters))
            self.assertEqual(len({c["image"]["id"] for c in chapters}), 8)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 9)
            self.assertEqual(len(state["whole_review"]["reviews"]), 2)

    def test_together_pauses_with_text_and_image(self):
        with Fixture() as f:
            identifier = f.start("together")
            paused = f.drive()
            self.assertEqual(paused["state"], "paused")
            result = json.loads(paused["result"])
            self.assertEqual(result["pause_reason"], "chapter")
            self.assertEqual(result["chapter_results"][0]["status"], "review")
            self.assertFalse(production.manuscript(f.conn, f.pid)["complete"])
            f.change("resume", job_id=identifier)
            self.assertEqual(json.loads(f.drive()["result"])["pause_reason"], "art")
            f.change("approve-art", job_id=identifier)
            self.assertEqual(f.drive()["state"], "completed")

    def test_unresolved_blocker_does_not_generate_images(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            rule = "The lock was sealed before the last bell and cannot turn at the bell."
            plan["chapters"][0]["continuity"] = rule
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            identifier = f.change("start", version=1, mode="automatic")["id"]
            def conflict(*args):
                answer, proof, finish = fake_model(*args)
                if args[1] == "audit" and "verdicts" in args[-1]["properties"]:
                    return json.dumps({"verdicts": [{"index": "0", "status": "confirmed",
                                      "reason": "The canon says the seal prevents turning it when the bell rings."}]}), proof, finish
                if args[1] == "audit" and "summary" in args[-1]["properties"]:
                    result = json.loads(answer)
                    result["findings"] = [{"category": "continuity", "severity": "blocking", "quote": BLOCK,
                                           "related_quote": rule, "issue": "The lock turns at the bell despite already being sealed.",
                                           "correction": "Move the turning before the lock is sealed."}]
                    return json.dumps(result), proof, finish
                return answer, proof, finish
            f.worker.call = conflict
            paused = f.drive()
            self.assertEqual(paused["state"], "paused")
            report = json.loads(paused["result"])
            self.assertEqual(report["current"]["passes"], 2)
            self.assertEqual(report["detail"][0]["quote"], BLOCK)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 0)
            with self.assertRaisesRegex(production.organizer.OrganizerError, "production_fix_required"):
                f.change("resume", job_id=identifier)
            f.change("cancel", job_id=identifier)
            self.assertEqual(f.drive(stop=("cancelled",))["state"], "cancelled")

    def test_recheck_repairs_saved_version_and_resumes_at_next_chapter(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            chapter = plan["chapters"][0]
            chapter.update(minimum=38, maximum=150)
            plan["chapters"].append({**chapter, "title": "The river", "beats": "Mara crosses the river."})
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            identifier = f.change("start", version=1, mode="automatic")["id"]
            phrase = "felt sharp against the dust motes that rose whenever Mara shifted something"
            lead = f"The sun had just cleared the ridge when she started, and already it {phrase}. "
            bad = lead + f"It wasn't even ten yet., but already the winter sunlight {phrase}."
            clock = "She had until two o'clock. She could afford a few hours of sorting."
            stamp = 'The stamp read "DUPLICATE" in block letters.'
            original = bad + "\n\n" + PROSE + " " + clock + " " + stamp
            doc = production.managed_docs(f.conn, f.pid)[0]
            with f.conn:
                version = production.organizer.update_document(f.conn, doc, doc["title"], original, "Old rewrite", "generated")
                legacy = {"quote": "It wasn't even ten yet.", "issue": "blocking", "severity": "blocking"}
                f.conn.execute("UPDATE jobs SET state='paused',result=? WHERE id=?", (production.dump({
                    "step": "reviewed", "number": 1, "plan_version": 1, "pause_reason": "blocker", "detail": [legacy],
                    "current": {"document_id": doc["id"], "version": version, "passes": 2,
                                "review": {"findings": [legacy]}, "patches": [{"edits": []}]},
                }), identifier))

            def audit_model(*args):
                answer, proof, finish = fake_model(*args)
                if args[1] != "audit" or "summary" not in args[-1]["properties"]:
                    return answer, proof, finish
                result = json.loads(answer)
                result["findings"] = [
                    {"quote": "It wasn't even ten yet", "related_quote": clock, "category": "continuity",
                     "severity": "blocking", "issue": "The interval to the deadline contradicts the duration stated.",
                     "correction": "Change the deadline to a later time."},
                    {"quote": stamp, "related_quote": "", "category": "naturalness",
                     "severity": "editorial", "issue": "editorial", "correction": ""},
                    {"quote": "An invented quotation", "related_quote": "", "category": "continuity",
                     "severity": "blocking", "issue": "This passage cannot be located in the current draft.",
                     "correction": "Check the actual version of the draft."},
                ]
                return json.dumps(result), proof, finish

            f.worker.call = audit_model
            self.assertTrue(production.public_job(production.job_state(f.conn, f.pid))["recheck_available"])
            f.change("resume", job_id=identifier)
            for _ in range(30):
                f.uploads()
                f.worker.tick()
                state = production.job_state(f.conn, f.pid)
                result = json.loads(state["result"])
                if result["step"] == "advance":
                    break
            else:
                self.fail(dict(state))
            receipt = result["chapter_results"][0]
            self.assertEqual(receipt["corrections"], 2)
            self.assertEqual([x["status"] for x in receipt["review"]["findings"]], ["refuted", "unconfirmed", "unconfirmed"])
            self.assertEqual(receipt["quality_history"][0]["passes"], 2)
            saved = production.managed_docs(f.conn, f.pid)[0]
            self.assertEqual(saved["id"], doc["id"])
            self.assertEqual(saved["body"].count(phrase), 1)
            self.assertNotIn("yet.,", saved["body"])
            self.assertTrue(saved["body"].endswith(PROSE + " " + clock + " " + stamp))
            self.assertEqual(f.conn.execute("SELECT body FROM doc_versions WHERE document_id=? AND version=?",
                                           (doc["id"], version)).fetchone()[0], original)
            first_image = receipt["image"]["id"]

            f.change("pause", job_id=identifier)
            f.change("resume", job_id=identifier)
            end = json.loads(f.drive()["result"])
            self.assertEqual(end["step"], "art_review")
            self.assertEqual(end["chapter_results"][0]["image"]["id"], first_image)
            self.assertEqual(len(production.managed_docs(f.conn, f.pid)), 2)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 3)

    def test_story_uses_visual_profile_for_two_chapters_and_cover(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            plan["chapters"].append({**plan["chapters"][0], "title": "The last drawer",
                                     "beats": "Nera carries the key into the corridor."})
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            f.change("start", version=1, mode="automatic", review_art=False)
            received = []

            def compose(pid, profile, subject, passage, number, *, cover, seed):
                self.assertEqual(pid, f.pid)
                self.assertIn(passage, PROSE)
                self.assertEqual(profile["ratio"], "16:9")
                received.append((number, cover))
                return ({"model": profile["model"], "prompt": subject, "size": "1024x576", "seed": seed},
                        {"id": profile["id"], "template": profile["template"], "version": profile["version"]})

            f.worker.visual_compose = compose
            self.assertEqual(f.drive(checkpoints=120)["state"], "completed")
            self.assertEqual(received, [(1, False), (2, False), (1, True)])
            result = production.manuscript(f.conn, f.pid)
            assets = [result["cover"], *(chapter["image"] for chapter in result["chapters"])]
            self.assertTrue(all(asset["dimensions"] == [1024, 576] for asset in assets))
            self.assertTrue(all(asset["visual_profile"]["template"] == "anima-aesthetic" for asset in assets))
            self.assertTrue(all("images/" + asset["id"] in production.manuscript_text(result, "mdx", local_images=True)
                                for asset in assets))
            scene = "Mara found the key beneath a sheet of paper near the drawer."
            observed = production.visual_observations(f.conn, f.pid, 2, scene)
            self.assertEqual(observed, [{"chapter": 1, "fact": "Mara found the key in the drawer."}])
            self.assertEqual(production.visual_observations(f.conn, f.pid, 1, scene), [])
            self.assertEqual(production.visual_observations(f.conn, f.pid, 2, "A snowstorm closes the road."), [])
            selected = assets[1]["id"]
            with f.conn:
                f.conn.execute("UPDATE projects SET meta=json_set(meta,'$.manual_cover',?) WHERE id=?", (selected, f.pid))
            self.assertEqual(production.manuscript(f.conn, f.pid)["cover"]["id"], selected)

    def test_eight_chapter_checkpoints_complete_in_order_and_export_nine_images(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            first = plan["chapters"][0]
            plan["chapters"] = [{**first, "title": f"Drawer {num}", "beats": f"Mara examines drawer {num}."}
                                for num in range(1, 9)]
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            ident = f.change("start", version=1, mode="automatic", review_art=False)["id"]
            def compose(pid, profile, subject, passage, number, *, cover, seed):
                request = {"model": profile["model"], "prompt": subject, "size": "1024x576", "seed": seed}
                return request, {key: profile[key] for key in ("id", "version", "template", "ratio", "recipe")}

            f.worker.visual_compose = compose
            end = f.drive(checkpoints=210)
            self.assertEqual(end["state"], "completed")
            self.assertTrue(production.public_job(end)["art_review_pending"])
            self.assertEqual(f.change("approve-art", job_id=ident)["status"], "completed")
            self.assertFalse(production.public_job(production.job_state(f.conn, f.pid)).get("art_review_pending"))
            manuscript = production.manuscript(f.conn, f.pid)
            self.assertTrue(manuscript["complete"])
            self.assertEqual([c["number"] for c in manuscript["chapters"]], list(range(1, 9)))
            self.assertTrue(manuscript["whole_review"]["repetitions"])
            assets = [manuscript["cover"], *[c["image"] for c in manuscript["chapters"]]]
            self.assertEqual(len({asset["id"] for asset in assets}), 9)
            self.assertTrue(all(asset["visual_profile"]["recipe"] == "anima-film"
                                and asset["dimensions"] == [1024, 576] for asset in assets))
            for fmt in ("md", "mdx"):
                text = production.manuscript_text(manuscript, fmt, local_images=True)
                self.assertTrue(all(f"images/{asset['id']}.png" in text for asset in assets))

    def test_canon_backed_quantity_fix_is_verified_and_saved_as_new_version(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            canon = "There are exactly three keys in the drawer."
            plan["chapters"][0]["continuity"] = canon
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            f.change("start", version=1, mode="automatic")
            original = PROSE.replace("she found the key", "she found four keys")

            def model(lang, role, prompt, tokens, schema=None):
                if role == "write":
                    return original, {"role": role}, "stop"
                properties = schema["properties"]
                if "safe" in properties:
                    return production.dump({"safe": "yes", "reason": "Only the count changes to the approved three."}), {}, "stop"
                answer, proof, finish = fake_model(lang, role, prompt, tokens, schema)
                result = json.loads(answer)
                if "summary" in properties:
                    result["findings"] = [{
                        "category": "continuity", "severity": "blocking", "quote": "four keys", "related_quote": canon,
                        "issue": "A fourth key appears against the explicit drawer count.",
                        "correction": "Use three keys as established in the approved chapter plan."},
                    ] if "four keys" in prompt.split("CHAPTER PASSAGE")[-1] else []
                if "verdicts" in properties:
                    result["verdicts"] = [{"index": "0", "status": "confirmed",
                                          "reason": "The plan allows exactly three keys in the drawer."}]
                if "edits" in properties:
                    result["edits"] = [{"before": "four keys", "after": "three keys"}]
                return production.dump(result), proof, finish

            f.worker.call = model
            job = f.drive()
            chapter = json.loads(job["result"])["chapter_results"][0]
            doc = production.managed_docs(f.conn, f.pid)[0]
            self.assertEqual(chapter["corrections"], 1)
            self.assertEqual(doc["body"], original.replace("four keys", "three keys"))
            self.assertEqual(chapter["final_hash"], production.digest(doc["body"]))
            self.assertEqual(chapter["patches"][0]["base_hash"], production.digest(original))
            self.assertTrue(chapter["candidate_audits"][0]["accepted"])

    def test_manual_chapter_version_is_not_automatically_overwritten(self):
        with Fixture() as f:
            f.start()
            for _ in range(16):
                f.worker.tick()
                doc = production.managed_docs(f.conn, f.pid)[0]
                if doc["body"]:
                    break
            else:
                self.fail("Draft was not saved")
            manual = PROSE.replace("paper. She", "paper., but she")
            with f.conn:
                version = production.organizer.update_document(f.conn, doc, doc["title"], manual, "Manual", "user")
            job = f.drive()
            self.assertEqual(job["state"], "paused")
            saved = production.managed_docs(f.conn, f.pid)[0]
            self.assertEqual((saved["body"], saved["version"], saved["version_origin"]), (manual, version, "user"))
            self.assertEqual(json.loads(job["result"])["chapter_results"][0]["corrections"], 0)

    def test_model_patches_reject_bad_joins_overlap_and_new_duplicates(self):
        with Fixture() as f:
            skill = f.worker.fiction()[0]
            original = "The rope had held, but the flood broke the old retaining wall. The neighbours heard the bell."
            cases = [
                ([{"before": "The rope had held", "after": "The rope held."}], "production_patch_boundary"),
                ([{"before": "The rope had held", "after": "The rope remained intact"},
                  {"before": "rope had held, but", "after": "rope had held despite the noise, but"}], "production_patch_invalid"),
                ([{"before": "The neighbours heard the bell.", "after":
                   "The rope had held, but the flood broke the old retaining wall. The neighbours heard the bell."}],
                 "production_patch_regression"),
            ]
            for edits, problem in cases:
                with self.subTest(problem=problem), self.assertRaisesRegex(production.PlanError, problem):
                    production.patch_text(original, edits, [], skill)
            with self.assertRaisesRegex(production.PlanError, "production_patch_invalid"):
                production.patch_text("She arrived at nine in the morning.", [{
                    "before": "nine in the morning", "after": "ten in the morning"}], [], skill)
            good = {"before": "The neighbours heard the bell.", "after": "The neighbours stopped when the bell rang."}
            fixed = production.patch_text(original, [good], [], skill)
            self.assertEqual(fixed, original.replace(good["before"], good["after"]))
            with self.assertRaisesRegex(production.PlanError, "production_patch_invalid"):
                production.patch_text(fixed, [good], [], skill)

    def test_variant_replaces_only_the_selected_illustration(self):
        with Fixture() as f:
            identifier = f.start()
            before = json.loads(f.drive()["result"])
            self.assertEqual(before["step"], "art_review")
            f.change("regenerate-art", job_id=identifier, number=1, instruction="Use a lower point of view.")
            after = json.loads(f.drive()["result"])
            self.assertEqual(after["step"], "art_review")
            self.assertEqual(before["cover"]["id"], after["cover"]["id"])
            old, new = before["chapter_results"][0], after["chapter_results"][0]
            self.assertEqual(old["version"], new["version"])
            self.assertNotEqual(old["image"]["id"], new["image"]["id"])
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 3)
            f.change("approve-art", job_id=identifier)
            self.assertEqual(f.drive()["state"], "completed")

    def test_plan_version_and_fidelity(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            self.assertEqual(f.change("save-plan", plan=plan)["version"], 1)
            with self.assertRaisesRegex(production.organizer.OrganizerError, "production_approval_required"):
                f.change("start", mode="automatic", version=1)
            plan["title"] = "The revised proposal"
            self.assertEqual(f.change("save-plan", plan=plan, version=1)["version"], 2)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM story_production_plans").fetchone()[0], 2)
            module = f.worker.fiction()[0]
            self.assertEqual(production.patch_text(PROSE, [{"before": "held the key", "after": "lifted it"}], [], module),
                             PROSE.replace("held the key", "lifted it"))
            with self.assertRaisesRegex(production.PlanError, "production_patch_invalid"):
                production.patch_text('It was 1970.', [{"before": "1970", "after": "1969"}], [], module)


def png(size):
    width, height = (int(value) for value in size.split("x"))
    def chunk(name, value):
        return struct.pack(">I", len(value)) + name + value + struct.pack(">I", zlib.crc32(name + value))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xad\x61\x50" * width) * height)) + chunk(b"IEND", b""))


def serve_fixture(port):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Images(BaseHTTPRequestHandler):
        jobs = {}

        def send(self, value, status=200):
            raw = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parts = self.path.strip("/").split("/")
            if parts == ["health"]:
                return self.send({"busy": False})
            if parts == ["studio", "api", "catalog"]:
                return self.send({"models": [], "presets": []})
            if parts == ["studio", "api", "jobs"]:
                return self.send(list(self.jobs.values()))
            identifier = parts[-1]
            if identifier not in self.jobs:
                return self.send({"error": "not_found"}, 404)
            job = self.jobs[identifier]
            if parts[-2] == "files":
                return self.send(png(job["request"]["size"]))
            return self.send(job)

        def do_POST(self):
            assert self.path == "/studio/api/jobs"
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            identifier = self.headers["Idempotency-Key"]
            self.jobs.setdefault(identifier, {"id": identifier, "image_id": identifier, "status": "completed", "request": request})
            return self.send(self.jobs[identifier], 202)

        def log_message(self, *_):
            pass

    image_server = ThreadingHTTPServer(("127.0.0.1", 0), Images)
    threading.Thread(target=image_server.serve_forever, daemon=True).start()
    upstream = f"http://127.0.0.1:{image_server.server_port}"
    os.environ.update(CREATIVE_STUDIO_PORT=str(port), CREATIVE_STUDIO_IMAGES=upstream, CREATIVE_STUDIO_ROUTER=upstream,
                      CREATIVE_STUDIO_RESEARCH=upstream, CREATIVE_STUDIO_WEB=str(ROOT / "packages/creative-studio/web/dist"))
    with Fixture() as fixture:
        fixture.backend["gpu_free"] = lambda **_: (True, "")
        fixture.worker.image_verify = fixture.backend["verify_image_file"]
        fixture.backend["cmd_serve"]()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve-fixture":
        serve_fixture(int(sys.argv[2]))
    else:
        unittest.main()
