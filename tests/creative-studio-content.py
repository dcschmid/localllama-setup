#!/usr/bin/env python3
"""Combined writing commissions: intent contract, routing, and the small content workflow end to end."""

import json
import os
import re
import runpy
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_chat as chats
import creative_studio_content as content
import creative_studio_knowledge as knowledge
from creative_studio_plan import PlanError
from creative_studio_quality import digest as quality_digest

REAL = """Erstelle einen deutschsprachigen Strecken-Steckbrief für **Thunderforge aus Riff Racers** mit ungefähr 250 Wörtern.

Verwende ausschließlich das bestätigte Wissen aus diesem Ordner. Schreibe natürlich, lebendig und ohne typische KI-Floskeln. Prüfe und korrigiere den Text automatisch.

Erstelle dazu ein passendes Bild im Low-Poly Concept Art Stil, 16:9.

Zeige mir beides direkt im Chat und stelle den vollständigen Steckbrief als Markdown-Datei zum Herunterladen bereit."""

CONTRACT = {
    "primary_intent": "create_content", "content_type": "track_profile", "language": "de-DE", "target_words": 250,
    "subject": "Thunderforge", "use_folder_knowledge": True, "review_after_creation": True, "auto_correct": True,
    "generate_image": True, "image_aspect_ratio": "16:9", "image_profile": "Low-Poly Concept Art", "export_formats": ["md"],
}
SENTENCES = [
    "Thunderforge gehört zu den fünf Strecken von Metal World 1.",
    "Eine riesige Bergschmiede prägt das Bild, während ein Gewitter über den Hallen steht.",
    "Auf der nassen Fahrbahn spiegeln sich Blitze und glühende Öfen.",
    "Wer hier schnell sein will, liest die Kurven früh und hält den Kart ruhig.",
    "Zwei riskante Abkürzungen versprechen Zeit, kosten bei einem Fehler aber mehrere Sekunden.",
    "Zwei Sprünge setzen die Fahrer kurz über die Schienen der Schmiede.",
    "Faire Fallen verlangen Aufmerksamkeit, bestrafen mutige Linien jedoch nicht.",
    "Die Pitlane arbeitet zuverlässig und gibt jedem Rennen eine zweite Chance.",
    "Der Ton bleibt energiegeladen, stilisiert und zugänglich, ganz im Sinne eines Arcade-Rennens.",
    "Stahl, Funken und kaltes Blau verschmelzen zu einem Look mit hohem Wiedererkennungswert.",
    "Metal-Fahrer fühlen sich hier zu Hause, weil jeder Abschnitt Lärm und Tempo atmet.",
    "Am Ende zählt der Rhythmus der Runde mehr als jede einzelne Kurve.",
    "Zwischen den Öfen führt die Ideallinie knapp an glühenden Gussformen vorbei.",
    "Ein Blitzschlag taucht die Halle kurz in grelles Licht und zeigt den nächsten Sprung.",
    "Wer die Boxengasse klug nutzt, gewinnt Raum für einen späten Angriff.",
    "Die Abkürzung über die Förderbänder spart Zeit, verlangt aber ein präzises Timing.",
    "Fahrer mit Hard-Rock-Wurzeln lieben die direkten Geraden vor dem ersten Hochofen.",
    "Dahinter wird es enger, und die Strecke verwandelt sich in ein Labyrinth aus Stahlträgern.",
    "Jede Runde erzählt dieselbe Geschichte aus Funken, Donner und Geschwindigkeit.",
    "Die Zuschauer auf den Rampen hören das Dröhnen schon, bevor die Karts sichtbar werden.",
    "So bleibt Thunderforge die Strecke, an der Mut und Konzentration zusammenfinden.",
]
FILLER = "In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass diese Strecke ein echtes Highlight ist. "
HEAD = "# Thunderforge – Strecken-Steckbrief\n\n"
DRAFT = HEAD + FILLER + " ".join(SENTENCES)
FINAL = HEAD + " ".join(SENTENCES)


EN_FILLER = "It's important to note that every kitchen deserves a machine that makes mornings easier. "
EN_SENTENCES = [
    "The Brewmaster K2 is a compact espresso machine for small kitchens.",
    "It heats up in 25 seconds and fits under a standard cabinet.",
    "A removable 1.2 liter water tank slides out at the side, so refilling takes a few seconds.",
    "The steam wand turns milk into a dense foam without spattering.",
    "Two programmable buttons store the shot length you like best.",
    "The drip tray lifts out and goes into the dishwasher.",
    "Daily cleaning takes about a minute, and the descaling program runs on its own.",
    "The body is made of brushed steel and weighs 4.8 kilograms.",
    "Replacement parts stay available for ten years.",
    "The K2 costs 249 euros and comes with a two year warranty.",
]
EN_HEAD = "# Brewmaster K2\n\n"
EN_DRAFT, EN_FINAL = EN_HEAD + EN_FILLER + " ".join(EN_SENTENCES), EN_HEAD + " ".join(EN_SENTENCES)
EN_REQUEST = ("Write a product description for the Brewmaster K2 in about 120 words. Use only the confirmed knowledge from this folder. "
              "Check and correct the text automatically. Provide the finished text as a Markdown file.")
STORY = ("Der Leuchtturmwärter stieg die Wendeltreppe hinauf, wie er es seit dreißig Jahren tat. Draußen schlug der Wind gegen die Scheiben, "
         "und unten im Hafen suchten die Kutter den Weg nach Hause. Er zündete die Lampe an und sah dem Licht nach, das über das dunkle "
         "Wasser wanderte. Dann setzte er sich an den kleinen Tisch, goss Tee ein und wartete auf den Morgen.")


class IntentTests(unittest.TestCase):
    def test_real_request_yields_the_contract(self):
        contract = content.analyze(REAL)
        self.assertEqual({key: contract[key] for key in CONTRACT}, CONTRACT)
        self.assertEqual(contract["word_range"], [225, 275])
        self.assertTrue(contract["knowledge_only"])
        self.assertEqual(contract["context_name"], "Riff Racers")

    def test_the_writing_brief_excludes_the_workflow_steps(self):
        plan = content.make_plan(REAL, "de", {}, lambda prose: "de")
        instruction = plan["writing"]["instruction"]
        self.assertIn("Strecken-Steckbrief", instruction)
        self.assertIn("ausschließlich das bestätigte Wissen", instruction)
        for step in ("Prüfe und korrigiere", "Bild", "Markdown-Datei", "Zeige mir"):
            self.assertNotIn(step, instruction)
        self.assertEqual(plan["image"]["request"], {"size": "1024x576"})
        self.assertEqual(plan["export"], {"formats": ["md"]})
        self.assertEqual(plan["writing"]["words"], [225, 275])

    def test_the_main_task_is_decided_by_the_whole_request(self):
        create = ("Erstelle einen Text und prüfe ihn danach.", "Schreibe einen Steckbrief mit Bild und Export.",
                  "Kannst du mir einen Steckbrief für Iron Chorus schreiben?", "Schreibe den Steckbrief für Thunderforge.",
                  "Write a track profile for Thunderforge in 120 words and check it afterwards.",
                  "Erstelle eine Zusammenfassung von Metal World 1. Prüfe sie anschließend.", REAL)
        for text in create:
            with self.subTest(text=text[:50]):
                self.assertEqual(chats.requested_action(text, "auto"), "content")
        review = ("Prüfe diesen Text.", "Prüfe den Text und erstelle ein Bild.", "Verbessere diesen Text.",
                  "Schreibe den Text neu.", "Schreibe diesen Text besser.", "Prüfe diesen Text und schreibe ihn kürzer.")
        for text in review:
            with self.subTest(text=text):
                self.assertNotEqual(chats.requested_action(text, "auto"), "content")
        self.assertEqual(chats.requested_action("Prüfe diesen Text.", "auto"), "editorial")

    def test_other_actions_keep_their_routes(self):
        for text, action in (("Erstelle ein Titelbild.", "image"),
                             ("Schreibe einen Artikel über Heavy Metal.", "article"), ("Recherchiere die Quellen.", "research"),
                             ("Schreibe eine Geschichte mit acht Kapiteln.", "outline"), ("Schreibe Kapitel 2.", "chapter")):
            with self.subTest(text=text):
                self.assertEqual(chats.requested_action(text, "auto"), action)
        self.assertNotEqual(chats.requested_action("Erstelle ein Profilbild.", "auto"), "content")
        # An explicit chat, image or research mode is never overruled.
        self.assertNotEqual(chats.requested_action("Schreibe einen Steckbrief für Thunderforge.", "chat"), "content")
        self.assertFalse(content.analyze("Schreibe einen Steckbrief für Mara ohne Prüfung.")["review_after_creation"])

    def test_the_export_is_verified_and_tamper_evident(self):
        with tempfile.TemporaryDirectory() as root:
            task = uuid.uuid4().hex
            receipt = content.export(root, task, "Thunderforge – Strecken-Steckbrief", FINAL, ["md"])
            name = receipt["files"][0]["name"]
            self.assertEqual(name, "thunderforge-strecken-steckbrief.md")
            self.assertEqual(content.verify(root, task, receipt, name, FINAL).read_text(encoding="utf-8"), FINAL + "\n")
            (Path(root) / task / name).write_text("# Thunderforge – Strecken-Steckbrief\n\nGeändert\n", encoding="utf-8")
            with self.assertRaisesRegex(PlanError, "content_export_missing"):
                content.verify(root, task, receipt, name)
            with self.assertRaisesRegex(PlanError, "content_export_missing"):
                content.verify(root, task, receipt, "../secret.md")
            with self.assertRaisesRegex(PlanError, "content_export_invalid"):
                content.export(root, task, "x", "text", ["pdf"])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        scoped = patch.dict(os.environ, {key: self.directory.name for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME")})
        scoped.start()
        self.addCleanup(scoped.stop)
        self.studio = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
        self.studio["migrate"]()
        self.conn = self.studio["db"]()
        self.addCleanup(lambda: self.studio["db"]().close())
        self.calls = []
        self.draft, self.filler = DRAFT, FILLER
        self.studio["http_json"] = self.upstream
        handler = self.studio["Handler"].__new__(self.studio["Handler"])
        handler._json = lambda value, status=200: (status, value)
        handler._serve_file = lambda path, mime, name=None: (200, path.read_bytes(), mime, name)
        self.handler = handler

    def upstream(self, url, method="GET", body=None, **_kwargs):
        if url.endswith("/apply-template"):
            return 200, {"prompt": "\n".join("<|turn>" + m["role"] + "\n" + m["content"] for m in body["messages"])}
        if url.endswith("/v1/chat/completions"):
            self.calls.append(body)
            if body["model"] == "creative-writing":
                return 200, {"choices": [{"message": {"content": self.draft}, "finish_reason": "stop"}]}
            # The central quality pipeline: the rule registry finds the filler itself, the audit model has nothing to add,
            # and the rewrite model returns the one exact edit that removes the confirmed filler sentence.
            properties = body["response_format"]["schema"]["properties"]
            if "text" in properties:   # the proofread pass: a clean passage comes back unchanged
                answer = {"text": body["messages"][-1]["content"].split("\nPASSAGE\n", 1)[1]}
            else:
                answer = ({"findings": []} if "findings" in properties else {"verdicts": []} if "verdicts" in properties else
                          {"edits": [{"id": "f1", "before": self.filler, "after": ""}]})
            return 200, {"choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}]}
        if url.endswith("/studio/api/catalog"):
            return 200, {"models": [{"id": "moss", "installed": True, "negative": True, "sizes": ["1024x576"], "verified_modes": [],
                                     "license": "mit", "formats": [{"id": "16:9", "size": "1024x576", "preview_size": "1024x576"}]}],
                         "recipes": [{"id": "lowpoly-retro", "model": "moss"}]}
        if url.endswith("/studio/api/compose"):
            return 200, {"model": body["model"], "size": "1024x576", "steps": 30,
                         "prompt": f"Low-poly. {body['subject']}. {body['scene']} {body['details']}"}
        raise AssertionError("unexpected upstream call: " + url)

    def kinds(self):
        """The quality-pipeline calls so far by what they asked for, read from the answer schema each call demanded."""
        names = {"text": "proofread", "findings": "audit", "verdicts": "verdict", "edits": "fix"}
        return [names[next(key for key in names if key in call["response_format"]["schema"]["properties"])]
                for call in self.calls if call["model"] == "human-audit"]

    def folder_chat(self, *, knowledge_entries=True, visual_profile=True, name="Riff Racers"):
        folder, sid = uuid.uuid4().hex, uuid.uuid4().hex
        with self.conn:
            self.conn.execute("INSERT INTO folders(id,folder_id,name,updated) VALUES(?,NULL,?,?)", (folder, name, time.time()))
            self.conn.execute("INSERT INTO sessions(id,title,folder_id,created,updated) VALUES(?,'Thunderforge',?,?,?)",
                              (sid, folder, time.time(), time.time()))
            if knowledge_entries:
                for title, content_text, status, category in (
                        ("Weltstruktur", "Metal World 1 enthält fünf Strecken, darunter Thunderforge.", "confirmed", "general"),
                        ("Thunderforge – Streckenprofil", "Industrielle Bergschmiede im Gewitter mit glühenden Öfen.", "reference", "general"),
                        ("Idee Lava-Strecke", "Eine Lavastrecke, nie Kanon.", "idea", "idea"),
                        *((("Visual Profile", json.dumps({"template": "Riff Racers Default", "ratio": "", "palette": "glühendes Orange, kaltes Blau",
                                                          "style": "Low-Poly Concept Art, retro 3D game look"}), "confirmed", "visual-profile"),)
                          if visual_profile else ())):
                    knowledge.mutate(self.conn, folder, {"action": "add", "category": category, "title": title,
                                                         "content": content_text, "status": status})
        return folder, sid

    def commission(self, sid, text=REAL):
        task = uuid.uuid4().hex
        status, answer = self.handler._dispatch_chat({"workflow": "chat", "mode": "auto", "default_lang": "de",
                                                      "request_id": task, "session_id": sid, "text": text})
        self.assertEqual((status, answer["handled"]), (202, True), answer)
        return task

    def run_task(self, task, *, image=True):
        for _ in range(6):
            row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (task,)).fetchone()
            if row["state"] in ("completed", "failed", "partial", "cancelled"):
                return row
            result = json.loads(row["result"])
            if result.get("image_job_id") and image:
                with self.conn:
                    self.conn.execute("UPDATE jobs SET state='completed',result=? WHERE id=?",
                                      (json.dumps({"image_id": uuid.uuid4().hex, "status": "completed"}), result["image_job_id"]))
            self.studio["advance_task"](row)
        self.fail("task did not finish")

    def test_the_real_commission_writes_corrects_illustrates_and_exports(self):
        _, sid = self.folder_chat()
        row = self.run_task(self.commission(sid))
        result = json.loads(row["result"])
        self.assertEqual(row["state"], "completed", result)
        steps = result["steps"]
        self.assertEqual({key: steps[key]["status"] for key in ("project", "writing", "document", "review", "export", "image")},
                         dict.fromkeys(("project", "writing", "document", "review", "export", "image"), "completed"))
        # Text: stored twice, first draft and corrected final version, the checked ones only.
        document = self.conn.execute("SELECT * FROM documents WHERE id=?", (result["document_id"],)).fetchone()
        self.assertEqual((document["kind"], document["version"], document["body"]), ("doc", 2, FINAL))
        first = self.conn.execute("SELECT body FROM doc_versions WHERE document_id=? AND version=1", (document["id"],)).fetchone()
        self.assertEqual(first["body"], DRAFT)
        self.assertEqual((steps["review"]["corrections"], steps["review"]["remaining"]), (1, 0))
        receipt = result["quality"]
        self.assertEqual(receipt["audit"]["models"], ["human-audit"])    # one alias for every role: no weight reload between calls
        self.assertEqual({item["source"] for item in receipt["findings"]}, {"rule"})    # the registry found it, the audit model found nothing
        self.assertTrue(steps["review"]["summary"]["audit_completed"])
        self.assertEqual(receipt["final"]["sha256_after"], quality_digest(document["body"]))
        self.assertEqual(receipt["findings"][0]["quote"], "In der heutigen schnelllebigen Welt")
        self.assertEqual([(f["quote"], f["verdict"]) for f in steps["review"]["findings"]], [("In der heutigen schnelllebigen Welt", "corrected")])
        self.assertIn(receipt["final"]["sha256_after"][:12], document["version_note"])
        self.assertEqual({call["model"] for call in self.calls}, {"creative-writing", "human-audit"})
        # Proofread and audit, the one correction, then the recheck. Nothing to verify: the rule registry confirmed the filler itself.
        self.assertEqual(self.kinds(), ["proofread", "audit", "fix", "proofread", "audit"])
        modes = {next(iter(call["response_format"]["schema"]["properties"])): call["chat_template_kwargs"]["writing_mode"]
                 for call in self.calls if call["model"] == "human-audit"}
        self.assertEqual(modes, dict.fromkeys(("text", "findings", "edits"), "rewrite"))
        # One system prompt for every role: the router can keep it cached between the calls of a run.
        systems = {call["messages"][0]["content"] for call in self.calls if call["model"] == "human-audit"}
        self.assertEqual(len(systems), 1)
        tags = {call["messages"][-1]["content"].split("\n", 1)[0] for call in self.calls if call["model"] == "human-audit"}
        self.assertEqual(tags, {"[de][rewrite][editorial]"})
        # Only folder knowledge, no ideas, and the model was told to stay inside it.
        prompt = self.calls[0]["messages"][-1]["content"]
        self.assertIn("Thunderforge – Streckenprofil", prompt)
        self.assertIn("Metal World 1 enthält fünf Strecken", prompt)
        self.assertNotIn("Lavastrecke", prompt)
        self.assertIn("Use only facts stated in the folder knowledge", prompt)
        self.assertEqual({item["title"] for item in result["knowledge"]["entries"]},
                         {"Weltstruktur", "Thunderforge – Streckenprofil"})
        self.assertNotIn("palette", prompt)
        self.assertNotIn("Recherche", json.dumps(self.calls))
        # Picture: the studio's Low-Poly template at 16:9, composed from a short digest of the final text.
        image = self.conn.execute("SELECT payload FROM jobs WHERE id=?", (result["image_job_id"],)).fetchone()
        queued = json.loads(image["payload"])
        request, meta = queued["request"], queued["meta"]
        self.assertEqual((request["model"], request["size"]), ("moss", "1024x576"))
        self.assertIn("Thunderforge, Riff Racers", request["prompt"])
        self.assertIn("Bergschmiede", request["prompt"])
        self.assertNotIn("Am Ende zählt", request["prompt"])
        self.assertNotIn("#", request["prompt"])
        self.assertNotIn("story", request["prompt"].lower().replace("storybook", ""))
        self.assertEqual(meta["visual_profile"]["template"], "riff-racers-low-poly")
        self.assertEqual(meta["alt"], "Strecken-Steckbrief: Thunderforge, Riff Racers")
        # File: validated before it is offered, served only while its bytes match.
        export = steps["export"]
        self.assertTrue(export["validated"])
        name = export["files"][0]["name"]
        status, data, mime, filename = self.handler._get(["chat", "tasks", row["id"], "files", name])
        self.assertEqual((status, data.decode(), filename), (200, FINAL + "\n", name))
        self.assertTrue(mime.startswith("text/markdown"))
        path = Path(self.directory.name) / "creative-studio/content" / row["id"] / name
        path.write_text("# manipuliert\n", encoding="utf-8")
        self.assertEqual(self.handler._get(["chat", "tasks", row["id"], "files", name])[0], 404)
        # Nothing else ran: no research, no production, no story planning.
        services = {r[0] for r in self.conn.execute("SELECT DISTINCT service FROM jobs")}
        self.assertEqual(services, {"chat_task", "image"})

    def test_a_clean_draft_is_audited_but_never_rewritten(self):
        _, sid = self.folder_chat()
        original = self.upstream

        def clean(url, method="GET", body=None, **kwargs):
            status, answer = original(url, method, body, **kwargs)
            if url.endswith("/v1/chat/completions") and body["model"] == "creative-writing":
                answer["choices"][0]["message"]["content"] = FINAL
            return status, answer

        self.studio["http_json"] = clean
        row = self.run_task(self.commission(sid))
        result = json.loads(row["result"])
        review = result["steps"]["review"]
        self.assertEqual((review["corrections"], review["remaining"], review["summary"]["passes"]), (0, 0, 0))
        self.assertTrue(review["summary"]["audit_completed"])
        self.assertEqual(self.kinds(), ["proofread", "audit"])      # a clean draft is read twice and never sent to a fix call
        document = self.conn.execute("SELECT version,body FROM documents WHERE id=?", (result["document_id"],)).fetchone()
        self.assertEqual((document["version"], document["body"]), (1, FINAL))

    def test_a_style_without_studio_template_becomes_a_short_scene_prompt(self):
        _, sid = self.folder_chat(visual_profile=False)
        row = self.run_task(self.commission(sid, REAL.replace("Low-Poly Concept Art Stil", "Aquarell Stil")))
        result = json.loads(row["result"])
        queued = json.loads(self.conn.execute("SELECT payload FROM jobs WHERE id=?", (result["image_job_id"],)).fetchone()["payload"])
        prompt = queued["request"]["prompt"]
        self.assertEqual(queued["request"]["size"], "1024x576")
        self.assertNotIn("visual_profile", queued["meta"])
        for fragment in ("Thunderforge, Riff Racers", "Style: Aquarell", "Bergschmiede", "no text, no lettering"):
            self.assertIn(fragment, prompt)
        self.assertNotIn("Am Ende zählt", prompt)
        self.assertLess(len(prompt), 600)

    def test_a_writer_that_misses_the_length_is_corrected_by_its_measured_factor(self):
        _, sid = self.folder_chat()
        original, aims = self.upstream, []
        words = " ".join(SENTENCES).split()

        def short_writer(url, method="GET", body=None, **kwargs):
            if url.endswith("/v1/chat/completions") and body["model"] == "creative-writing":
                prompt = body["messages"][-1]["content"]
                aim = int(re.search(r"about (\d+) words in total", prompt)[1])
                aims.append(aim)
                # A steady writer delivers 70 % of what it is asked for and copies nothing from earlier attempts.
                text = HEAD + " ".join(words[:round(aim * .7)])
                return 200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
            return original(url, method, body, **kwargs)

        self.studio["http_json"] = short_writer
        row = self.run_task(self.commission(sid))
        result = json.loads(row["result"])
        words = [item["validation"]["words"] for item in result["steps"]["writing"]["diagnostics"]]
        self.assertEqual((row["state"], aims[0], len(aims)), ("completed", 250, 2), (aims, words))
        self.assertGreater(aims[1], aims[0])
        self.assertTrue(words[0] < 225 and 225 <= words[1] <= 275, words)
        self.assertEqual({item["mode"] for item in result["steps"]["writing"]["diagnostics"]}, {"generate"})

    def test_an_english_commission_in_an_unrelated_folder_uses_the_same_pipeline(self):
        _, sid = self.folder_chat(name="Nordlicht Appliances", knowledge_entries=False, visual_profile=False)
        folder = self.conn.execute("SELECT folder_id FROM sessions WHERE id=?", (sid,)).fetchone()[0]
        knowledge.mutate(self.conn, folder, {"action": "add", "category": "product", "title": "Brewmaster K2", "status": "confirmed",
                                             "content": "The Brewmaster K2 is a compact espresso machine. Heat-up time is 25 seconds."})
        self.conn.commit()
        self.draft, self.filler = EN_DRAFT, EN_FILLER
        row = self.run_task(self.commission(sid, EN_REQUEST))
        result = json.loads(row["result"])
        self.assertEqual(row["state"], "completed", result)
        self.assertEqual(result["requirements"]["language"], "en")
        document = self.conn.execute("SELECT kind,version,body FROM documents WHERE id=?", (result["document_id"],)).fetchone()
        self.assertEqual((document["kind"], document["version"], document["body"]), ("doc", 2, EN_FINAL))
        receipt = result["quality"]
        self.assertEqual((receipt["language"], receipt["profile"]), ("en-US", "marketing"))   # a product description
        self.assertEqual(receipt["final"]["sha256_after"], quality_digest(EN_FINAL))
        self.assertEqual(result["steps"]["review"]["summary"]["corrected"], 1)
        prompt = self.calls[0]["messages"][-1]["content"]
        self.assertIn("English", prompt)
        self.assertIn("Heat-up time is 25 seconds", prompt)
        self.assertNotIn("Riff", json.dumps(self.calls))
        self.assertEqual(result["steps"]["export"]["files"][0]["name"], "brewmaster-k2.md")
        self.assertNotIn("image", result["steps"])

    def test_a_one_shot_story_runs_through_the_central_quality_pipeline_too(self):
        sid = uuid.uuid4().hex
        with self.conn:
            self.conn.execute("INSERT INTO sessions(id,title,created,updated) VALUES(?,'Geschichte',?,?)", (sid, time.time(), time.time()))
        self.draft = "# Der Wärter\n\n" + STORY
        task = uuid.uuid4().hex
        status, answer = self.handler._dispatch_chat({"mode": "story", "default_lang": "de", "request_id": task, "session_id": sid,
                                                      "text": "Schreibe eine kurze Geschichte über einen Leuchtturmwärter."})
        self.assertEqual((status, answer["handled"]), (202, True), answer)
        row = self.run_task(task, image=False)
        result = json.loads(row["result"])
        self.assertEqual(row["state"], "completed", result)
        self.assertEqual({key: step["status"] for key, step in result["steps"].items() if key in ("document", "review")},
                         {"document": "completed", "review": "completed"})
        self.assertEqual(result["quality"]["profile"], "story")
        self.assertEqual(result["quality"]["audit"]["models"], ["human-audit"])
        self.assertTrue(result["steps"]["review"]["summary"]["audit_completed"])
        document = self.conn.execute("SELECT kind,version,body FROM documents WHERE id=?", (result["document_id"],)).fetchone()
        self.assertEqual((document["kind"], document["version"]), ("chapter", 1))   # clean text: audited, left alone

    def test_an_existing_document_is_audited_or_corrected_on_demand(self):
        with self.conn:
            pid = uuid.uuid4().hex
            self.conn.execute("INSERT INTO projects(id,name,kind,lang) VALUES(?,'Notizen','custom','de')", (pid,))
            did = self.studio["save_document"](self.conn, pid, "Steckbrief", DRAFT, "doc", "de")
        handler = self.handler
        status, audited = handler._quality_request(did, {"mode": "audit"})
        self.assertEqual((status, audited["changed"], audited["version"]), (200, False, 1))
        self.assertEqual(audited["summary"]["confirmed"], 1)
        self.assertNotIn("fix", self.kinds())      # an audit changes nothing, so it never asks for a repair
        status, fixed = handler._quality_request(did, {"mode": "fix", "version": 1})
        self.assertEqual((status, fixed["changed"], fixed["version"]), (200, True, 2))
        document = self.conn.execute("SELECT body,version_note,version_origin FROM documents WHERE id=?", (did,)).fetchone()
        self.assertEqual(document["body"], FINAL)
        self.assertIn(quality_digest(FINAL)[:12], document["version_note"])
        self.assertEqual(fixed["receipt"]["final"]["sha256_after"], quality_digest(document["body"]))
        before = self.conn.execute("SELECT body FROM doc_versions WHERE document_id=? AND version=1", (did,)).fetchone()
        self.assertEqual(before["body"], DRAFT)                                     # the original stays reachable
        status, again = handler._quality_request(did, {"mode": "fix"})
        self.assertEqual((status, again["changed"], again["version"]), (200, False, 2))   # nothing left to correct
        self.assertEqual(handler._quality_request(did, {"mode": "fix", "version": 1})[0], 409)
        for bad in ({"mode": "destroy"}, {"terms": "x"}, {"terms": [""]}, {"lang": "fr"}, {"kind": "k" * 41}):
            self.assertEqual(handler._quality_request(did, bad)[0], 422, bad)
        self.assertEqual(handler._quality_request("0" * 32, {})[0], 404)

    def test_a_review_interrupted_by_a_restart_resumes_instead_of_hanging(self):
        # The server died while the review step was "revising". The persisted step is not "pending", yet it has to run again.
        sid, pid, task = (uuid.uuid4().hex for _ in range(3))
        with self.conn:
            self.conn.execute("INSERT INTO projects(id,name,kind,lang) VALUES(?,'T','custom','de')", (pid,))
            self.conn.execute("INSERT INTO sessions(id,project_id) VALUES(?,?)", (sid, pid))
            did = self.studio["save_document"](self.conn, pid, "T", DRAFT, "doc", "de")
            plan = {"title": "", "project_name": "", "writing": {"kind": "content", "lang": "de", "words": None, "instruction": "x",
                    "content": {"subject": "", "context_name": "", "auto_correct": True, "language": "de-DE", "quality_profile": "general"}}}
            result = {"project_id": pid, "document_id": did, "steps": {"project": {"status": "completed"}, "writing": {"status": "completed"},
                      "document": {"status": "completed"}, "review": {"status": "revising"}}}
            self.conn.execute("INSERT INTO jobs(id,service,state,payload,result,created,updated) VALUES(?,'chat_task','running',?,?,?,?)",
                              (task, json.dumps({"session_id": sid, "project_id": pid, "chat_first": True, "plan": plan}),
                               json.dumps(result), time.time(), time.time()))
        row = self.run_task(task, image=False)
        saved = json.loads(row["result"])
        self.assertEqual((row["state"], saved["steps"]["review"]["status"]), ("completed", "completed"))
        self.assertEqual(self.conn.execute("SELECT version,body FROM documents WHERE id=?", (did,)).fetchone()["body"], FINAL)

    def test_the_card_lists_corrected_and_open_findings_including_late_ones(self):
        _, sid = self.folder_chat()
        # The audit model names one more defect, but only in the recheck, and no edit can repair it.
        original = self.upstream
        late = {"audits": 0}

        def with_late_defect(url, method="GET", body=None, **kwargs):
            if url.endswith("/v1/chat/completions") and body["model"] == "human-audit" and \
                    "findings" in body["response_format"]["schema"]["properties"]:
                late["audits"] += 1
                if late["audits"] == 2:
                    quote = "Fahrer mit Hard-Rock-Wurzeln lieben"
                    answer = {"findings": [{"quote": quote, "issue": "Die Wortfolge klingt hier nicht natürlich.", "replacement": "",
                                            "category": "naturalness", "severity": "editorial", "action": "rewrite"}]}
                    return 200, {"choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}]}
            return original(url, method, body, **kwargs)

        self.studio["http_json"] = with_late_defect
        row = self.run_task(self.commission(sid))
        review = json.loads(row["result"])["steps"]["review"]
        verdicts = {f["quote"]: f["verdict"] for f in review["findings"]}
        self.assertEqual(verdicts["In der heutigen schnelllebigen Welt"], "corrected")
        self.assertEqual(verdicts["Fahrer mit Hard-Rock-Wurzeln lieben"], "open")
        self.assertEqual((review["corrections"], review["remaining"]), (1, 1))

    def test_missing_folder_knowledge_stops_before_any_model_call(self):
        _, sid = self.folder_chat(knowledge_entries=False)
        row = self.run_task(self.commission(sid), image=False)
        result = json.loads(row["result"])
        self.assertEqual((row["state"], result["error"]), ("failed", "content_knowledge_missing"))
        self.assertEqual(self.calls, [])
        self.assertEqual({key: step["status"] for key, step in result["steps"].items() if key in ("review", "export", "image")},
                         {"review": "skipped", "export": "skipped", "image": "skipped"})
        self.assertIsNone(self.conn.execute("SELECT 1 FROM jobs WHERE service='image'").fetchone())

    def test_a_review_request_without_new_text_is_not_hijacked(self):
        _, sid = self.folder_chat()
        status, answer = self.handler._dispatch_chat({"workflow": "chat", "mode": "auto", "default_lang": "de", "request_id": uuid.uuid4().hex,
                                                      "session_id": sid, "text": "Prüfe diesen Text."})
        self.assertEqual(status, 202)
        self.assertTrue(answer.get("missing_text"))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM jobs WHERE service='chat_task'").fetchone())


if __name__ == "__main__":
    unittest.main()
