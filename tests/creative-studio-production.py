#!/usr/bin/env python3
"""Drive the real persistence layer and production state machine with deterministic upstreams."""

import contextlib
import json
import os
import re
import runpy
import sqlite3
import struct
import threading
import zlib
import zipfile
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
        skills = [{"name": name, "version": "fixture"} for name in
                  {"human-audit": ("human-writing",), "audit": ("story-writing",)}.get(role, ())]
        return json.dumps(value), {"model_id": "fixture", "skill_version": "fixture", "role": role, "skills": skills}, "stop"
    if role == "write":
        return PROSE, {"model_id": "fixture", "role": role}, "stop"
    if role == "plan" and "[[model-format]]" in prompt:
        return "not json", {"model_id": "fixture", "alias": "creative-writing", "variant": "Fixture-Q4_K_M.gguf",
                            "quantization": "Q4_K_M", "role": role, "skills": [
                                {"name": "human-writing", "version": "1.3.0"}, {"name": "story-writing", "version": "1.0.0"}]}, "stop"
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
        self.worker.image_verify = lambda image, size: self.backend["png_dimensions"](png(size), size)
        self.worker.image_bytes = lambda image, size: png(size)
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


PLAN_PROOF = {"model_id": "creative-writing", "alias": "creative-writing", "variant": "Fixture-Q4_K_M.gguf", "quantization": "Q4_K_M",
              "skill_version": "1.3.0", "skills": [{"name": "human-writing", "version": "1.3.0"},
                                                   {"name": "story-writing", "version": "1.0.0"}]}


def three_chapters(plan):
    return [{**plan["chapters"][0], "title": f"Kapitel {n}", "beats": f"Handlung {n}", "closing": f"Schluss {n}",
             "minimum": 900, "maximum": 1200} for n in (1, 2, 3)]


def planning_model(*, empty_bible=False, outline=None, repair=None, seen=None):
    """Planning answers for a three-chapter story. `outline` is a (text, finish) pair replacing the outline answer,
    `repair` maps the requested bible fields to the answer for them."""
    plan = example_plan()

    def model(lang, role, prompt, tokens, schema=None):
        keys = schema["properties"] if schema else {}
        if seen is not None:
            seen.append((role, tuple(sorted(keys))))
        if role == "plan" and "bible" in keys:
            if outline:
                return outline[0], {**PLAN_PROOF, "role": role}, outline[1]
            value = {key: plan[key] for key in keys}
            if empty_bible:
                value["bible"] = {**value["bible"], **{key: "" for key in ("characters", "world", "locations", "chronology")}}
            return json.dumps(value), {**PLAN_PROOF, "role": role}, "stop"
        if role == "plan" and "chapters" in keys:
            return json.dumps({"chapters": three_chapters(plan)}), {**PLAN_PROOF, "role": role}, "stop"
        if role == "plan" and set(keys) <= set(production.REQUIRED_BIBLE):
            answer = repair(keys) if repair else {key: f"Zusammenfassung {key}" for key in keys}
            return json.dumps(answer), {**PLAN_PROOF, "role": role}, "stop"
        answer, proof, finish = fake_model(lang, role, prompt, tokens, schema)
        return answer, {**proof, **PLAN_PROOF, "role": role}, finish
    return model


class AutonomousProductionTests(unittest.TestCase):
    def test_automatic_plan_handoff_keeps_job_and_survives_worker_restart(self):
        with Fixture() as f:
            f.create()
            seen = []
            f.worker.call = planning_model(seen=seen)
            identifier = f.change("propose", brief="Write a full three chapter story.", language="en", count=3,
                minimum=38, maximum=60, production_mode="auto_production", title="Thunder over Thunderforge")["id"]
            for _ in range(10):
                f.worker.tick()
                job = production.job_state(f.conn, f.pid)
                if json.loads(job["payload"])["kind"] == "story":
                    break
            self.assertEqual(job["id"], identifier)
            payload = json.loads(job["payload"])
            self.assertEqual(payload["kind"], "story", job["result"])
            self.assertEqual(payload["plan"]["title"], "Thunder over Thunderforge")
            self.assertEqual(payload["mode"], "automatic")
            self.assertFalse(payload["review_art"])
            self.assertEqual(production.latest_plan(f.conn, f.pid)["state"], "approved")
            # Reload the backend against the persisted checkpoint as after a server restart.
            f.backend = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
            f.worker = f.backend["production_worker"]
            f.worker.call = fake_model
            f.worker.image_verify = lambda image, size: f.backend["png_dimensions"](png(size), size)
            f.worker.image_bytes = lambda image, size: png(size)
            job = f.drive(checkpoints=250)
            self.assertEqual(job["state"], "completed", job["result"])
            result = json.loads(job["result"])
            self.assertEqual(len(result["chapter_results"]), 3)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='production'").fetchone()[0], 1)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 4)
            self.assertTrue({"manuscript.md", "manuscript.mdx", "manuscript.zip", "manifest.json"} <= result["exports"]["files"].keys())

    def test_folder_canon_is_used_in_planning_and_repair_budget_is_bounded(self):
        with Fixture() as f:
            f.create()
            with f.conn:
                f.conn.execute("INSERT INTO folders(id,name,updated) VALUES(?,?,1)", ("d" * 32, "Riff Racers"))
                f.conn.execute("UPDATE sessions SET folder_id=? WHERE id=?", ("d" * 32, f.sid))
                production.knowledge.mutate(f.conn, "d" * 32, {"action": "add", "category": "world", "title": "Strecke",
                    "content": "Thunderforge führt über eine orbital schwebende Schmiede.", "status": "confirmed"})
            underlying = planning_model()
            seen = []
            def model(lang, role, prompt, tokens, schema=None):
                seen.append(prompt)
                props = schema["properties"]
                if "unresolved" in props:
                    if "changes" not in props:
                        return json.dumps({"unresolved": ["Bestätigte Weltfakten widersprechen dem Kapitel."]}), PLAN_PROOF, "stop"
                    return json.dumps({"changes": [{"section": "chapter", "chapter": "1", "field": "beats", "value": "Handlung 1 korrigiert " + str(len(seen))}], "unresolved": []}), PLAN_PROOF, "stop"
                if "Critique this completed" in prompt:
                    return json.dumps({"findings": [{"chapter": "1", "quote": "Handlung 1", "issue": "Kanonkonflikt bleibt offen."}]}), PLAN_PROOF, "stop"
                return underlying(lang, role, prompt, tokens, schema)
            f.worker.call = model
            identifier = f.change("propose", brief="Write the story on Thunderforge.", language="en", count=3,
                                  production_mode="auto_production")["id"]
            job = f.drive(checkpoints=20)
            self.assertEqual(job["state"], "paused", job["result"])
            self.assertEqual(json.loads(job["result"])["plan_passes"], 2)
            self.assertEqual(sum("Verify each cited planning defect" in p for p in seen), 2)
            self.assertTrue(all("orbital schwebende Schmiede" in p for p in seen))
            self.assertEqual(len(production.managed_docs(f.conn, f.pid)), 0)

    def test_plan_errors_are_repaired_and_explicit_approval_starts_production(self):
        with Fixture() as f:
            f.create()
            underlying = planning_model()
            reviewed = 0
            def model(lang, role, prompt, tokens, schema=None):
                nonlocal reviewed
                props = schema["properties"]
                if "unresolved" in props:
                    return json.dumps({"changes": [{"section": "chapter", "chapter": "1", "field": "beats",
                        "value": "Die Qualifikation beginnt, das Finale folgt erst im letzten Kapitel."}], "unresolved": []}), PLAN_PROOF, "stop"
                if "Critique this completed" in prompt:
                    reviewed += 1
                    findings = [{"chapter": "1", "quote": "Handlung 1", "issue": "Das Finale beginnt zu früh."}] if reviewed == 1 else []
                    return json.dumps({"findings": findings}), PLAN_PROOF, "stop"
                return underlying(lang, role, prompt, tokens, schema)
            f.worker.call = model
            identifier = f.change("propose", brief="Erstelle eine Geschichte. Zeige mir zuerst die Planung.", count=3,
                                  language="de", production_mode="approval_first")["id"]
            job = f.drive()
            self.assertEqual(job["state"], "completed", job["result"])
            self.assertEqual(json.loads(job["result"])["plan_passes"], 1)
            self.assertEqual(reviewed, 2)
            info = production.plan_info(f.conn, f.pid)
            self.assertFalse(info["approved"])
            self.assertIn("Qualifikation", info["plan"]["chapters"][0]["beats"])
            started = f.change("approve-plan", version=info["version"])
            self.assertIn("id", started)
            self.assertEqual(json.loads(production.job_state(f.conn, f.pid)["payload"])["kind"], "story")


class PlanDiscussionRegressionTests(unittest.TestCase):
    def test_discussed_revision_is_persisted_and_approved_for_production(self):
        import creative_studio_chat as chats
        with Fixture() as f:
            f.create()
            base = example_plan()
            base["language"] = "de"
            first = f.change("save-plan", plan=base)["version"]
            f.change("approve-plan", version=first)
            source = production.planning_source(f.conn, f.pid, f.sid)
            request = "das bitte umplanenn und korregieren und wir schreiben auf Deutsch bitte die ganze Geschichte"
            action = chats.requested_action(request, "story", has_plan=True, has_prose=False, story_context=True)
            self.assertEqual(action, "planning-revise")
            with f.conn:
                queued, _ = production.enqueue_planning(f.conn, f.pid, f.sid, action.removeprefix("planning-"),
                    request, "en", source, f.backend["store_message"], "c" * 32, "fingerprint")
            f.worker.tick()
            job = f.conn.execute("SELECT * FROM jobs WHERE id=?", (queued["id"],)).fetchone()
            self.assertEqual(job["state"], "completed", job["result"])
            info = production.plan_info(f.conn, f.pid)
            self.assertEqual(info["version"], first + 1)
            self.assertFalse(info["approved"])
            self.assertEqual(info["plan"]["language"], "de")
            self.assertEqual(info["impact"]["proposal"], {"story_id": f.pid, "original_version": first,
                "proposed_version": first + 1, "status": "pending_approval"})
            self.assertEqual(info["impact"]["changed_chapters"], [1])
            self.assertTrue(info["impact"]["chapter_changes"])
            self.assertEqual(json.loads(f.conn.execute("SELECT plan FROM story_production_plans WHERE version=1").fetchone()[0]), base)
            self.assertEqual(chats.production_command("Ja so ist das gut dann leg los", "proposal"), "automatic")
            f.change("approve-plan", version=info["version"])
            job_id = f.change("start", version=info["version"], mode="automatic")["id"]
            payload = json.loads(f.conn.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()[0])
            self.assertEqual(payload["plan"]["language"], "de")
            self.assertEqual(production.plan_info(f.conn, f.pid)["stage"], "PRODUCTION_RUNNING")

    def test_discussion_changes_need_no_audit_finding_and_invalid_values_fail(self):
        with Fixture() as f:
            f.create()
            f.change("save-plan", plan=example_plan())
            def model(lang, role, prompt, tokens, schema=None):
                if "answer" not in schema["properties"]:
                    return json.dumps({"findings": []}), {}, "stop"
                return json.dumps({"answer": "Der Schlüssel wird später entdeckt.", "findings": [], "changes": [
                    {"section": "bible", "chapter": "0", "field": "main_plot", "value": "Die Entdeckung folgt im Finale."}
                ]}), {}, "stop"
            f.worker.call = model
            with f.conn:
                production.enqueue_planning(f.conn, f.pid, f.sid, "discuss", "Was ändern wir am Finale?", "en",
                    production.planning_source(f.conn, f.pid, f.sid), f.backend["store_message"], "c" * 32, "input")
            f.worker.tick()
            self.assertEqual(f.conn.execute("SELECT state FROM jobs WHERE id=?", ("c" * 32,)).fetchone()[0], "completed")
            info = production.plan_info(f.conn, f.pid)
            self.assertEqual(info["version"], 2)
            self.assertIn("main_plot", info["impact"]["bible_changes"])
            with self.assertRaises(production.organizer.OrganizerError):
                production.changed_plan(info["plan"], [{"section": "chapter", "chapter": "1", "field": "beats", "value": "x" * 10000}])

    def test_english_discussion_output_fails_before_saving_a_revision(self):
        with Fixture() as f:
            f.create()
            base = example_plan()
            base["language"] = "de"
            f.change("save-plan", plan=base)
            def model(lang, role, prompt, tokens, schema=None):
                return json.dumps({"answer": "The roar of the crowd and the neon glare overwhelm Mika as she prepares for her first qualifying lap. She looks at the track and knows that she has to win the race.",
                    "findings": [], "changes": [{"section": "chapter", "chapter": "1", "field": "beats", "value": "Mika fährt das Finale."}]}), {}, "stop"
            f.worker.call = model
            with f.conn:
                production.enqueue_planning(f.conn, f.pid, f.sid, "discuss", "Wie ändern wir das Finale?", "en",
                    production.planning_source(f.conn, f.pid, f.sid), f.backend["store_message"], "c" * 32, "input")
            f.worker.tick()
            row = f.conn.execute("SELECT * FROM jobs WHERE id=?", ("c" * 32,)).fetchone()
            self.assertEqual(row["state"], "failed")
            self.assertEqual(json.loads(row["result"])["error"], "story_language_mismatch")
            self.assertEqual(production.plan_info(f.conn, f.pid)["version"], 1)


class PlanningTests(unittest.TestCase):
    brief = "Eine Geschichte über zwei Rennfahrer und ein verlorenes Rennen."

    def propose(self, f, model, language="de"):
        f.create()
        f.worker.call = model
        return f.change("propose", brief=self.brief, count=3, language=language, minimum=900, maximum=1200)["id"]

    def settle(self, f, identifier, limit=60):
        for _ in range(limit):
            row = f.conn.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            if row["state"] in ("completed", "failed"):
                return row
            with f.conn:
                f.conn.execute("UPDATE jobs SET result=json_remove(result,'$.next_at') WHERE id=?", (identifier,))
            f.worker.tick()
        raise AssertionError(dict(row))

    def result(self, f, identifier):
        return json.loads(f.conn.execute("SELECT result FROM jobs WHERE id=?", (identifier,)).fetchone()[0])

    def test_german_and_english_three_chapter_plans_use_both_writing_skills(self):
        for language in ("de", "en"):
            with self.subTest(language=language), Fixture() as f:
                identifier = self.propose(f, planning_model(), language)
                self.assertEqual(production.plan_info(f.conn, f.pid)["stage"], "PLANNING")
                self.assertEqual(self.settle(f, identifier)["state"], "completed")
                info = production.plan_info(f.conn, f.pid)
                self.assertEqual((info["stage"], info["version"], info["plan"]["language"], len(info["plan"]["chapters"])),
                                 ("PLAN_READY", 1, language, 3))
                job = info["job"]
                self.assertEqual(job["skills"], {"human-writing": "1.3.0", "story-writing": "1.0.0"})
                self.assertEqual(job["model"], {"alias": "creative-writing", "variant": "Fixture-Q4_K_M.gguf", "quantization": "Q4_K_M"})
                # The step after "Story-Planung liegt vor" is the release of exactly this plan version.
                f.change("approve-plan", version=info["version"])
                self.assertEqual(production.plan_info(f.conn, f.pid)["stage"], "PLAN_APPROVED")
                self.assertEqual(production.plan_info(f.conn, f.pid)["approved"], True)

    def test_installed_skills_resolve_for_the_planning_phase(self):
        root = Path(os.environ.get("LLAMA_SETUP_SKILLS", Path.home() / "dev/github/skillset/skills"))
        if not (root / "story-writing/SKILL.md").is_file():
            self.skipTest("skillset checkout not available")
        skills = runpy.run_path(str(ROOT / "libexec/creative_studio_skills.py"))
        for language in ("de", "en"):
            context = skills["resolve"](root, language, "story", "plan")
            self.assertEqual(context.versions, {"human-writing": "1.3.0", "story-writing": "1.0.0"})
            self.assertEqual(sorted(context.rules), sorted([
                "human-writing/SKILL.md", f"human-writing/references/style-{language}.md", "story-writing/SKILL.md",
                "story-writing/references/story-bible.md", "story-writing/references/story-planning.md"]))
            self.assertTrue(all(len(rule["sha256"]) == 64 for item in context.evidence() for rule in item["rules"]))

    def test_validation_errors_name_the_field_and_never_its_content(self):
        plan = example_plan()
        cases = (({"bible": {**plan["bible"], "characters": ""}}, "bible.characters", "empty"),
                 ({"bible": {**plan["bible"], "world": "x" * 1401}}, "bible.world", "too_long"),
                 ({"visual": {**plan["visual"], "palette": " "}}, "visual.palette", "empty"),
                 ({"chapters": [{**plan["chapters"][0], "beats": ""}]}, "chapters[1].beats", "empty"),
                 ({"bible_records": {**plan["bible_records"], "characters": [{"name": "", "role": "x"}]}},
                  "bible_records.characters[1].name", "empty"))
        for change, field, reason in cases:
            with self.subTest(field=field), self.assertRaises(production.PlanFieldError) as caught:
                production.validate_plan({**plan, **change})
            self.assertEqual((str(caught.exception), caught.exception.field, caught.exception.reason),
                             ("story_input_invalid", field, reason))

    def test_empty_bible_fields_are_completed_once_and_nothing_else_is_regenerated(self):
        seen = []
        with Fixture() as f:
            identifier = self.propose(f, planning_model(empty_bible=True, seen=seen))
            self.assertEqual(self.settle(f, identifier)["state"], "completed")
            plan = production.plan_info(f.conn, f.pid)["plan"]
            self.assertEqual(plan["bible"]["characters"], "Zusammenfassung characters")
            self.assertEqual(plan["bible"]["main_plot"], example_plan()["bible"]["main_plot"])   # valid parts are kept
            self.assertEqual(sum("bible" in keys for _, keys in seen), 1)
            self.assertEqual(sum("chapters" in keys for _, keys in seen), 1)
            repairs = [keys for _, keys in seen if set(keys) <= set(production.REQUIRED_BIBLE)]
            self.assertEqual(repairs, [("characters", "chronology", "locations", "world")])
            self.assertEqual(self.result(f, identifier)["repairs"], [{"step": "bible_fields",
                             "fields": ["characters", "world", "locations", "chronology"]}])

    def test_failed_job_with_empty_bible_resumes_at_the_failed_step(self):
        """The stored shape of the failed Thunderforge planning: complete outline, empty bible fields, story_input_invalid."""
        seen = []
        with Fixture() as f:
            f.create()
            f.worker.call = planning_model(seen=seen)
            base = example_plan()
            outline = {**{key: base[key] for key in (*production.PLAN, "audience", "subtitle", "visual", "bible_records", "motifs")},
                       "bible": {**base["bible"], **{key: "" for key in ("characters", "world", "locations", "chronology")}},
                       "language": "de", "chapters": three_chapters(base)}
            payload = {"kind": "plan", "brief": self.brief, "count": 3, "language": "de", "minimum": 900, "maximum": 1200,
                       "visual": {"model": "", "preset": "none", "size": "1024x576", "cover_size": "1024x576"},
                       "project_id": f.pid, "session_id": f.sid}
            result = {"step": "planning", "outline": outline, "model_evidence": [{**PLAN_PROOF, "role": "plan"}],
                      "error": "story_input_invalid", "failure_phase": "planning", "detail": {"exception": "OrganizerError"}}
            identifier = "c" * 32
            with f.conn:
                f.conn.execute("INSERT INTO jobs(id,service,state,payload,result,created,updated) VALUES(?,'production','failed',?,?,1,1)",
                               (identifier, production.dump(payload), production.dump(result)))
            self.assertEqual(production.public_job(production.job_state(f.conn, f.pid))["status"], "failed")
            f.change("retry", job_id=identifier)
            self.assertEqual(self.settle(f, identifier)["state"], "completed")
            # Same job, one plan version, and only the missing fields plus the final review were asked of the model.
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='production'").fetchone()[0], 1)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM story_production_plans").fetchone()[0], 1)
            self.assertFalse(any("bible" in keys or "chapters" in keys for _, keys in seen), seen)
            self.assertEqual(production.plan_info(f.conn, f.pid)["stage"], "PLAN_READY")

    def test_unusable_model_answers_fail_with_the_step_and_keep_the_original_answer_private(self):
        cases = (("not json", "stop", "story_model_format"), ("{", "length", "story_output_truncated"))
        for answer, finish, code in cases:
            with self.subTest(code=code), Fixture() as f:
                seen = []
                identifier = self.propose(f, planning_model(outline=(answer, finish), seen=seen))
                row = self.settle(f, identifier)
                result = json.loads(row["result"])
                self.assertEqual((row["state"], result["error"], result["detail"]["stage"]), ("failed", code, "outline"))
                self.assertEqual(len(seen), 3)   # one try and two bounded retries, no endless loop
                public = production.public_job(row)
                self.assertEqual(public["retries"]["automatic"], 2)
                self.assertNotIn("diagnostics", public)
                self.assertNotIn(answer, [v for v in public.values() if isinstance(v, str)])
                self.assertFalse(any(isinstance(v, str) and len(answer) > 1 and answer in v for v in public.values()))
                self.assertNotIn("raw", json.dumps(public))
                # The failed call names its model and the loaded skills even though no earlier call succeeded.
                self.assertEqual(public["model"], {"alias": "creative-writing", "variant": "Fixture-Q4_K_M.gguf", "quantization": "Q4_K_M"})
                self.assertEqual(public["skills"], {"human-writing": "1.3.0", "story-writing": "1.0.0"})
                self.assertEqual({d["code"] for d in result["diagnostics"]}, {code})
                self.assertEqual((result["diagnostics"][-1]["raw"], result["diagnostics"][-1]["finish"]), (answer, finish))
                self.assertEqual(len(result["diagnostics"]), 3)

    def test_model_timeout_is_retried_twice_and_reported_as_unavailable(self):
        with Fixture() as f:
            calls = []

            def slow(lang, role, prompt, tokens, schema=None):
                calls.append(role)
                raise TimeoutError

            identifier = self.propose(f, slow)
            row = self.settle(f, identifier)
            result = json.loads(row["result"])
            self.assertEqual((row["state"], result["error"], result["detail"]["stage"]), ("failed", "production_upstream_unavailable", "outline"))
            self.assertEqual(len(calls), 3)

    def test_failed_save_keeps_the_generated_plan_and_the_retry_only_saves(self):
        seen = []
        with Fixture() as f:
            identifier = self.propose(f, planning_model(seen=seen))
            with mock.patch.object(production, "plan_version", side_effect=sqlite3.OperationalError("disk I/O error")):
                row = self.settle(f, identifier)
            result = json.loads(row["result"])
            self.assertEqual((row["state"], result["error"], result["detail"]["stage"]), ("failed", "production_checkpoint_write", "save"))
            self.assertEqual(len(result["outline"]["chapters"]), 3)
            self.assertIn("outline_review", result)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM story_production_plans").fetchone()[0], 0)
            before = len(seen)
            f.change("retry", job_id=identifier)
            self.assertEqual(self.settle(f, identifier)["state"], "completed")
            self.assertEqual(len(seen), before)   # no model call was repeated
            self.assertEqual(f.conn.execute("SELECT count(*) FROM story_production_plans").fetchone()[0], 1)

    def test_retry_after_a_failed_repair_completes_without_rewriting_the_outline(self):
        seen = []
        with Fixture() as f:
            blank = lambda keys: {key: " " for key in keys}
            identifier = self.propose(f, planning_model(empty_bible=True, repair=blank, seen=seen))
            row = self.settle(f, identifier)
            result = json.loads(row["result"])
            self.assertEqual((row["state"], result["error"], result["detail"]["stage"]), ("failed", "story_model_format", "repair"))
            self.assertEqual(sum("bible" in keys for _, keys in seen), 1)
            f.worker.call = planning_model(empty_bible=True, seen=seen)
            f.change("retry", job_id=identifier)
            self.assertEqual(self.settle(f, identifier)["state"], "completed")
            self.assertEqual(sum("bible" in keys for _, keys in seen), 1)   # the outline was not generated again
            self.assertEqual(sum("chapters" in keys for _, keys in seen), 1)
            self.assertEqual(production.plan_info(f.conn, f.pid)["plan"]["bible"]["world"], "Zusammenfassung world")


class ProductionTests(unittest.TestCase):
    def test_placeholder_in_image_response_never_creates_an_image_job(self):
        with Fixture() as f:
            f.start()
            def simulated(lang, role, prompt, tokens, schema=None):
                if role == "image":
                    return json.dumps({"passage": "1", "alt": "Mara", "prompt": "Simuliertes Bild: Low-Poly"}), {}, "stop"
                return fake_model(lang, role, prompt, tokens, schema)
            f.worker.call = simulated
            for _ in range(40):
                row = production.job_state(f.conn, f.pid)
                if row["state"] == "failed":
                    break
                f.worker.tick()
                with f.conn:
                    f.conn.execute("UPDATE jobs SET result=json_remove(result,'$.next_at') WHERE id=?", (row["id"],))
            report = production.public_job(row)
            self.assertEqual(report["error"], "production_image_evidence")
            self.assertFalse(report.get("downloads"))
            self.assertEqual(report["manifest"]["verified_images"], 0)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0], 0)

    def test_incomplete_chapters_resume_automatically_and_stop_on_failed_image(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            chapter = plan["chapters"][0]
            plan["chapters"] = [{**chapter, "number": n, "title": f"Drawer {n}", "beats": f"Mara finds record {n}."}
                                for n in range(1, 4)]
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            f.change("start", version=1, mode="automatic", review_art=False)
            docs = production.managed_docs(f.conn, f.pid)
            for doc in docs[:2]:
                with f.conn:
                    production.organizer.update_document(f.conn, doc, doc["title"], PROSE, "Existing draft", "user", "en")
            self.assertFalse(production.manuscript(f.conn, f.pid)["complete"])
            for _ in range(110):
                row = production.job_state(f.conn, f.pid)
                result = json.loads(row["result"])
                if result.get("number") == 3:
                    break
                f.uploads()
                f.worker.tick()
            self.assertEqual((row["state"], result["number"], result["step"]), ("running", 3, "writing"))
            f.conn.close()
            del f.backend["_dbs"].conn
            f.conn = f.backend["db"]()
            for _ in range(40):
                f.worker.tick()
                row = production.job_state(f.conn, f.pid)
                if child := json.loads(row["result"])["current"].get("image_job"):
                    with f.conn:
                        f.conn.execute("UPDATE jobs SET state='failed',result=? WHERE id=?",
                                       ('{"error":"image_service_unreachable"}', child))
                    break
            f.worker.tick()
            row = production.job_state(f.conn, f.pid)
            self.assertEqual((row["state"], production.public_job(row)["error"]), ("failed", "production_image_failed"))
            current = production.manuscript(f.conn, f.pid)
            self.assertEqual([c["body"] for c in current["chapters"]], [PROSE] * 3)
            self.assertEqual([c["version"] for c in current["chapters"]], [2, 2, 2])
            self.assertEqual([c["image"] is not None for c in current["chapters"]], [True, True, False])
            self.assertFalse(current["complete"])
            f.change("retry", job_id=row["id"])
            done = f.drive()
            self.assertEqual(done["state"], "completed")
            receipt = json.loads(done["result"])["exports"]
            archive = f.worker.exports.file(row["id"], receipt, "manuscript.zip")
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual({name for name in bundle.namelist() if name.endswith(".png")},
                                 {"images/cover.png", "images/chapter-01.png", "images/chapter-02.png", "images/chapter-03.png"})
                self.assertEqual(bundle.read("manuscript.md").decode().count(PROSE), 3)
                self.assertEqual(bundle.read("manuscript.mdx").decode().count(PROSE), 3)
                manifest = json.loads(bundle.read("manifest.json"))
                self.assertEqual(manifest["verified_images"], 4)
                self.assertTrue(all(c["audit_id"] for c in manifest["chapters"]))
            path = f.worker.exports.file(row["id"], receipt, "manuscript.md")
            path.write_bytes(b"x" * path.stat().st_size)
            self.assertFalse(f.backend["artifacts_available"](done))
            self.assertEqual(production.public_job(done, artifacts=False)["status"], "incomplete")
            self.assertFalse(production.public_job(done, artifacts=False).get("downloads"))

    def test_short_generated_chapter_gets_an_audited_scene_expansion(self):
        with Fixture() as f:
            f.start()
            short = PROSE.rsplit(" The lock", 1)[0]
            addition = "Nera turned the key in her hand and compared its teeth with the marks Mara had drawn."

            def expanding(lang, role, prompt, tokens, schema=None):
                if role == "write":
                    return short, {}, "stop"
                if role == "rewrite" and "anchor" in schema["properties"]:
                    return json.dumps({"anchor": short[-120:], "addition": addition}), {}, "stop"
                return fake_model(lang, role, prompt, tokens, schema)

            f.worker.call = expanding
            row = f.drive()
            result = json.loads(row["result"])
            c = result["chapter_results"][0]
            self.assertEqual(c["original_version"], 2)
            self.assertEqual(c["version"], 3)
            self.assertEqual(c["corrections"], 1)
            self.assertTrue(c["candidate_audits"][0]["accepted"])
            self.assertEqual(production.managed_docs(f.conn, f.pid)[0]["body"], short + "\n\n" + addition)
            f.change("approve-art", job_id=row["id"])
            self.assertEqual(f.drive()["state"], "completed")

    def test_short_chapter_can_fix_confirmed_punctuation_in_same_revision(self):
        with Fixture() as f:
            f.start()
            short = PROSE.rsplit(" The lock", 1)[0].replace("paper. She", "paper., but she")
            addition = "Nera turned the key in her hand and compared its teeth with the marks Mara had drawn."

            def expanding(lang, role, prompt, tokens, schema=None):
                if role == "write":
                    return short + "\n\nShe watched the empty corridor.", {}, "stop"
                if role == "rewrite" and "anchor" in schema["properties"]:
                    self.assertIn("edits", schema["properties"])
                    anchor = schema["properties"]["anchor"]["enum"][0]
                    return json.dumps({"anchor": anchor, "addition": addition,
                                       "edits": [{"before": "paper.,", "after": "paper,"}]}), {}, "stop"
                return fake_model(lang, role, prompt, tokens, schema)

            f.worker.call = expanding
            row = f.drive()
            result = json.loads(row["result"])
            receipt = result["chapter_results"][0]
            self.assertEqual(receipt["corrections"], 2)
            self.assertTrue(receipt["candidate_audits"][0]["accepted"])
            self.assertNotIn("paper.,", production.managed_docs(f.conn, f.pid)[0]["body"])

    def test_short_scene_expansions_accumulate_before_rechecking(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            plan["chapters"][0].update(minimum=60, maximum=90)
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            f.change("start", version=1, mode="automatic")
            additions = iter(("Mara checked the shadows behind the cupboard for any movement.",
                              "Nera set the lantern beside the open drawer to light the faded record."))

            def expanding(lang, role, prompt, tokens, schema=None):
                if role == "rewrite" and "anchor" in schema["properties"]:
                    anchor = schema["properties"]["anchor"]["enum"][0]
                    return json.dumps({"anchor": anchor, "addition": next(additions)}), {}, "stop"
                return fake_model(lang, role, prompt, tokens, schema)

            f.worker.call = expanding
            row = f.drive()
            result = json.loads(row["result"])
            receipt = result["chapter_results"][0]
            self.assertEqual(receipt["corrections"], 2)
            self.assertEqual(len(receipt["patches"]), 2)
            self.assertLess(receipt["patches"][0]["words_after"], 60)
            self.assertEqual(receipt["patches"][1]["words_before"], receipt["patches"][0]["words_after"])
            self.assertTrue(receipt["candidate_audits"][0]["accepted"])
            self.assertGreaterEqual(receipt["words"], 60)

    def test_in_range_words_and_both_audit_proofs_gate_completion(self):
        with Fixture() as f:
            f.start()
            doc = production.managed_docs(f.conn, f.pid)[0]
            with f.conn:
                production.organizer.update_document(f.conn, doc, doc["title"], "Mara opened the drawer.", "Short draft", "user", "en")
            row = f.drive()
            self.assertEqual(production.public_job(row)["error"], "story_length_failed")
            self.assertEqual(production.manuscript(f.conn, f.pid)["chapters"][0]["words"], 4)
            self.assertFalse(production.public_job(row).get("downloads"))
        with Fixture() as f:
            f.start()
            def missing_proof(lang, role, prompt, tokens, schema=None):
                output, proof, stop = fake_model(lang, role, prompt, tokens, schema)
                if role == "human-audit":
                    proof["skills"] = []
                return output, proof, stop
            f.worker.call = missing_proof
            row = f.drive()
            report = production.public_job(row)
            self.assertEqual(report["error"], "production_audit_evidence")
            self.assertNotIn("human-writing", report["skills"])
            self.assertFalse(report.get("chapter_results"))
            self.assertFalse(report.get("downloads"))

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

    def reviewed(self, f, findings, passes):
        """Park a real reviewed checkpoint with injected findings and a chosen revision round count."""
        f.create()
        f.change("save-plan", plan=example_plan())
        f.change("approve-plan", version=1)
        identifier = f.change("start", version=1, mode="automatic", review_art=False)["id"]
        for _ in range(12):
            f.worker.tick()
            job = production.job_state(f.conn, f.pid)
            if production.public_job(job)["phase"] == "reviewed":
                break
        else:
            self.fail("Chapter never reached the reviewed checkpoint")
        body = production.managed_docs(f.conn, f.pid)[0]["body"]
        result = json.loads(job["result"])
        located = [{**finding, **(span := production.intact_span(body, finding["quote"]) or {})}
                   for finding in findings]
        result["current"]["review"].update(findings=located,
                                           unverified_findings=sum(item["status"] == "unconfirmed" for item in located))
        result["current"].update(passes=passes, automatic_version=result["current"]["version"])
        with f.conn:
            f.conn.execute("UPDATE jobs SET result=? WHERE id=?", (production.dump(result), identifier))
        return identifier

    def test_only_unconfirmed_notes_do_not_stop_the_production(self):
        notes = [{"chapter": "1", "quote": BLOCK, "related_quote": "", "issue": "Position not confirmed.",
                  "correction": "", "category": "continuity", "severity": "note", "status": "unconfirmed"},
                 {"chapter": "1", "quote": "the last bell", "related_quote": "", "issue": "Unverified reading.",
                  "correction": "", "category": "naturalness", "severity": "note", "status": "unconfirmed"}]
        with Fixture() as f:
            self.reviewed(f, notes, passes=2)
            job = f.drive()
            result = json.loads(job["result"])
            self.assertNotEqual(result.get("pause_reason"), "blocker")
            self.assertNotEqual(result.get("step"), "reviewed")

    def test_a_repaired_carried_over_defect_never_stays_a_blocking_finding(self):
        stale = {"chapter": "1", "quote": "raus kommen", "related_quote": "", "issue": "Repaired before the last save.",
                 "correction": "", "category": "grammar", "severity": "automatic", "status": "confirmed"}
        with Fixture() as f:
            self.reviewed(f, [stale], passes=2)
            f.worker.tick()
            result = json.loads(production.job_state(f.conn, f.pid)["result"])
            self.assertEqual(result["step"], "auditing")
            self.assertNotIn("review", result["current"])
            self.assertEqual(result["current"]["quality_history"][-1]["stale_defects"], ["raus kommen"])

    def test_a_confirmed_simple_defect_after_two_rounds_offers_repair_not_a_decision(self):
        defect = {"chapter": "1", "quote": "the last bell", "related_quote": "", "issue": "fixture verb",
                  "correction": "", "category": "grammar", "severity": "automatic", "status": "confirmed"}
        with Fixture() as f:
            self.reviewed(f, [defect], passes=2)
            job = f.drive()
            self.assertEqual(job["state"], "paused")
            report = production.public_job(job)
            self.assertEqual(report["pause_reason"], "blocker")
            self.assertTrue(report["language_retry_available"])
            self.assertFalse(report.get("recheck_available"))

    def test_confirmed_central_conflict_still_pauses_after_two_rounds(self):
        with Fixture() as f:
            self.reviewed(f, [{"chapter": "1", "quote": BLOCK, "related_quote": PROSE[:40],
                               "issue": "Two bible facts disagree.", "correction": "Needs an author choice.",
                               "category": "continuity", "severity": "blocking", "status": "confirmed"}], passes=2)
            job = f.drive()
            self.assertEqual(job["state"], "paused")
            report = production.public_job(job)
            self.assertEqual(report["pause_reason"], "blocker")
            self.assertFalse(report.get("language_retry_available") or report.get("recheck_available"))
            self.assertEqual(report["detail"][0]["quote"], BLOCK)

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
                "start": 0, "end": len(BLOCK), "quote": BLOCK, "issue": "Fixture correction."
            }]
            with f.conn:
                f.conn.execute("UPDATE jobs SET result=? WHERE id=?", (production.dump(result), job["id"]))

            def invalid_patch(lang, role, prompt, tokens, schema):
                self.assertEqual(role, "rewrite")
                return "{}", {}, "stop"

            f.worker.call = invalid_patch
            for _ in range(3):
                f.worker.tick()
            row = production.job_state(f.conn, f.pid)
            result = json.loads(row["result"])
            self.assertEqual(row["state"], "paused")
            self.assertEqual(result["pause_reason"], "blocker")
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
                f.backend["store_message"], f.backend["running_work"], exports=f.worker.exports, image_bytes=f.worker.image_bytes)
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
            result = json.loads(job["result"])
            self.assertEqual(result["pause_reason"], "blocker")
            self.assertNotIn("chapter_results", result)
            self.assertFalse(result["current"].get("corrections"))

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

    def test_one_unsafe_model_edit_keeps_the_other_verified_corrections(self):
        with Fixture() as f:
            skill = f.worker.fiction()[0]
            text = ("Er sah kurz zu seiner Schwester hinüber. Juri stand nicht nur da, weil Ada ihn gebeten hatte, "
                    "sondern because he wanted to be there. Er wollte helfen, und diese Erkenntnis gab ihr Kraft. "
                    "Der Hafen lag nun sicher hinter ihnen zurück, denn das Schiff fand seinen Platz am Steg "
                    "und ließ es langsam fest werden.")
            poisoned = {"before": "sondern because he wanted to be there.",
                        "after": "sondern weil er dabei sein wollte. Er wollte helfen, und diese Erkenntnis gab ihr Kraft."}
            valid = {"before": "denn das Schiff fand seinen Platz am Steg und ließ es langsam fest werden.",
                     "after": "denn die Fähre wurde schließlich sicher am Steg festgemacht."}
            with self.assertRaisesRegex(production.PlanError, "production_patch_regression"):
                production.patch_text(text, [poisoned, valid], [], skill)
            candidate, accepted, rejected = production.patch_text_partial(text, [poisoned, valid], [], skill)
            self.assertEqual(accepted, [valid])
            self.assertEqual([(item["edit"], item["error"]) for item in rejected],
                             [(poisoned, "production_patch_regression")])
            self.assertEqual(candidate, text.replace(valid["before"], valid["after"]))
            self.assertIn("because he wanted to be there", candidate)
            unchanged, none, only_rejected = production.patch_text_partial(text, [poisoned], [], skill)
            self.assertEqual((unchanged, none, [item["error"] for item in only_rejected]),
                             (text, [], ["production_patch_regression"]))
            # The next attempt is told what was rejected, as long as the span still exists in the text.
            current = {"patches": [{"method": "model_patch", "rejected_edits": rejected}]}
            hint = production.rejected_edit_feedback(current, candidate)
            self.assertIn("REJECTED EARLIER EDITS", hint)
            self.assertIn(poisoned["before"], hint)
            self.assertEqual(production.rejected_edit_feedback(current, "Ein ganz anderer Text."), "")

    def test_confirmed_finding_with_an_exact_replacement_becomes_a_minimal_edit(self):
        with Fixture() as f:
            skill = f.worker.fiction()[0]
            text = ("Juri stand nicht nur da, weil Ada ihn gebeten hatte, sondern because he wanted to be there. "
                    "Er wollte helfen, und diese Erkenntnis gab ihr Kraft. Die Crew erkannte das Licht an, was ihre "
                    "Ankunft bestätigt. Das Wort Licht stand zweimal da. Licht.")
            findings = [
                {"quote": "because he wanted to be there", "correction": "ersetze „because he wanted to be there“ durch „weil er dabei sein wollte“"},
                {"quote": "was ihre Ankunft bestätigt", "correction": 'replace "bestätigt" with "bestätigte"'},
                {"quote": "Licht", "correction": "ersetze „Licht“ durch „Schein“"},   # not unique in the text
                {"quote": "Er wollte helfen", "correction": "Den Satz natürlicher formulieren."},   # no exact replacement
                {"quote": "Er wollte helfen", "correction": "ersetze „anderer Text“ durch „x“"},    # not part of the quote
            ]
            edits = production.declared_edits(findings, text)
            self.assertEqual(edits, [{"before": "because he wanted to be there", "after": "weil er dabei sein wollte"},
                                     {"before": "bestätigt", "after": "bestätigte"}])
            candidate, accepted, rejected = production.patch_text_partial(
                text, edits, [], skill, targets=[{**item, "start": text.find(item["before"]),
                                                  "end": text.find(item["before"]) + len(item["before"])} for item in edits])
            self.assertEqual((accepted, rejected), (edits, []))
            self.assertIn("sondern weil er dabei sein wollte. Er wollte helfen", candidate)
            self.assertIn("was ihre Ankunft bestätigte.", candidate)
            self.assertNotIn("because", candidate)

    def test_carried_over_defect_is_dropped_once_its_quote_became_a_longer_word(self):
        quote = "was ihre Ankunft bestätigt"
        fixed = "Die Crew erkannte das Licht an, was ihre Ankunft bestätigte. Dann legte das Schiff an."
        faulty = "Die Crew erkannte das Licht an, was ihre Ankunft bestätigt. Dann legte das Schiff an."
        self.assertIsNone(production.intact_span(fixed, quote))
        span = production.intact_span(faulty, quote)
        self.assertEqual((span["start"], span["end"], span["line"]), (faulty.find(quote), faulty.find(quote) + len(quote), 1))
        # A later whole-phrase occurrence still keeps the defect.
        self.assertEqual(production.intact_span(fixed + " Es war so, was ihre Ankunft bestätigt.", quote)["start"],
                         (fixed + " Es war so, was ihre Ankunft bestätigt.").rfind(quote))
        self.assertIsNone(production.intact_span("Text ohne das Zitat.", quote))

    def test_retry_audits_the_saved_version_again_when_a_stored_defect_is_stale(self):
        with Fixture() as f:
            f.create()
            plan = example_plan()
            plan["chapters"][0].update(minimum=10, maximum=150)
            f.change("save-plan", plan=plan)
            f.change("approve-plan", version=1)
            identifier = f.change("start", version=1, mode="automatic")["id"]
            doc = production.managed_docs(f.conn, f.pid)[0]
            quote = "which confirmed the arrival"
            with f.conn:
                version = production.organizer.update_document(
                    f.conn, doc, doc["title"], "The crew saw the light, which confirmed the arrivals at once.", "Fix", "generated")
                stale = {"quote": quote, "category": "grammar", "severity": "automatic", "status": "confirmed",
                         "issue": "tense", "correction": "x", "start": 24, "end": 50}
                f.conn.execute("UPDATE jobs SET state='paused',result=? WHERE id=?", (production.dump({
                    "step": "reviewed", "number": 1, "plan_version": 1, "pause_reason": "blocker", "detail": [stale],
                    "current": {"document_id": doc["id"], "version": version, "automatic_version": version, "passes": 2,
                                "review": {"findings": [stale], "local": [], "quality_version": production.QUALITY_VERSION}},
                }), identifier))
            self.assertTrue(production.language_retry_available(json.loads(
                f.conn.execute("SELECT result FROM jobs WHERE id=?", (identifier,)).fetchone()[0])))
            f.change("retry", job_id=identifier)
            result = json.loads(f.conn.execute("SELECT result FROM jobs WHERE id=?", (identifier,)).fetchone()[0])
            current = result["current"]
            self.assertEqual(result["step"], "auditing")
            self.assertNotIn("review", current)
            self.assertEqual(current["quality_history"][-1]["stale_defects"], [quote])
            self.assertEqual(current["revision_batches"][-1]["passes"], 2)

    def test_verifier_stating_a_style_choice_does_not_block_as_a_language_defect(self):
        defect = {"status": "confirmed", "severity": "automatic", "category": "grammar", "quote": "x",
                  "verification": "Der Bindestrich ist hier eher eine stilistische Entscheidung als ein Fehler."}
        self.assertTrue(production.optional_language(defect))
        self.assertEqual(production.language_defects({"findings": [defect]}), [])
        real = {**defect, "verification": "Der Wechsel von Deutsch zu Englisch ist ein klarer Sprachbruch."}
        self.assertEqual(production.language_defects({"findings": [real]}), [real])

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

    def test_confirmed_spacing_join_inside_a_quotation_still_patches(self):
        with Fixture() as f:
            skill = f.worker.fiction()[0]
            text = ("Der Hafen lag ruhig da. \u201eWir m\u00fcssen hier raus kommen, wir sind gefangen!\u201c rief Juri. "
                    "Die Crew schwieg.")
            join = {"before": "\u201eWir m\u00fcssen hier raus kommen, wir sind gefangen!\u201c",
                    "after": "\u201eWir m\u00fcssen hier rauskommen, wir sind gefangen!\u201c"}
            self.assertEqual(production.patch_text(text, [join], [], skill), text.replace(join["before"], join["after"]))
            spoken = {"before": "\u201eWir m\u00fcssen hier raus kommen, wir sind gefangen!\u201c",
                      "after": "\u201eWir m\u00fcssen hier rauskommen, wir sind frei!\u201c"}
            with self.assertRaisesRegex(production.PlanError, "production_patch_invalid"):
                production.patch_text(text, [spoken], [], skill)

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
                      CREATIVE_STUDIO_RESEARCH=upstream)
    os.environ.setdefault("CREATIVE_STUDIO_WEB", str(ROOT / "packages/creative-studio/web/dist"))
    with Fixture() as fixture:
        fixture.backend["gpu_free"] = lambda **_: (True, "")
        fixture.worker.image_verify = fixture.backend["verify_production_image"]
        fixture.worker.image_bytes = fixture.backend["production_image_bytes"]
        fixture.backend["cmd_serve"]()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve-fixture":
        serve_fixture(int(sys.argv[2]))
    else:
        unittest.main()
