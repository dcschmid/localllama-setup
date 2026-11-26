#!/usr/bin/env python3
"""Regression checks for chat-owned creative work and legacy chapter identity."""
import json
import runpy
import sqlite3
import sys
import unittest
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_chat as chats

Fixture = runpy.run_path(str(ROOT / "tests/creative-studio-organizer.py"))["StudioFixture"]


def dispatch(f, sid, text, **options):
    return f.req("/chat/dispatch", {"workflow": "chat", "mode": "story", "default_lang": "en",
                                    "request_id": uuid.uuid4().hex, "session_id": sid, "text": text, **options})


def plan(f, pid, name, prose):
    doc = f.req(f"/stories/{pid}/plan", {"title": name, "plan": "The light moves."})["id"]
    f.req("/documents/" + doc, {"body": prose, "version": 1})
    return doc


class ChatTests(unittest.TestCase):
    def test_intent_and_formatted_words(self):
        self.assertEqual(chats.outline_count("Erstelle eine Story-Bibel und plane acht Kapitel."), 8)
        self.assertEqual(chats.outline_count("Write one chapter."), 1)
        self.assertEqual(chats.length_range("Schreibe Kapitel 1 mit 1.200 Wörtern."), {"minimum": 1080, "maximum": 1320})
        for text, action in (("Erstelle ein Titelbild.", "image"), ("Recherchiere die Quellen.", "research"),
                             ("Schreibe einen Artikel.", "article"), ("Prüfe Kapitel 1 nach meiner Story-Bibel.", "editorial")):
            self.assertEqual(chats.requested_action(text, "story"), action)

    def test_planning_and_prose_intents(self):
        cases = [
            ("Prüfe unsere vollständige Planung auf Widersprüche.", False, "planning-audit"),
            ("Prüfe die Planung auf Zeitfehler. Schreibe noch keinen Kapiteltext.", True, "planning-audit"),
            ("Prüfe die acht Kapitel auf Widersprüche.", True, "planning-audit"),
            ("Verbessere Kapitel 4 unserer Planung und überprüfe die Folgen für Kapitel 7.", False, "planning-revise"),
            ("Mara soll in Kapitel 7 eine andere Entscheidung treffen.", True, "planning-revise"),
            ("Ist das Ende glaubwürdig?", False, "planning-discuss"),
            ("das bitte umplanenn und korregieren und wir schreiben auf Deutsch bitte die ganze Geschichte", False, "planning-revise"),
            ("Lass uns die drei Schlüssel noch einmal durchgehen.", False, "planning-discuss"),
            ("Überarbeite unsere Story-Bibel.", False, "planning-revise"),
            ("Prüfe Kapitel 1 auf grammatische Fehler.", True, "editorial"),
            ("Prüfe Kapitel 1 auf Kontinuität.", True, "editorial"),
            ("Prüfe Kapitel 1 auf Kontinuität.", False, "planning-audit"),
            ("Überarbeite den geschriebenen Text von Kapitel 5.", False, "editorial"),
            ("Schreibe Kapitel 5 nach unserer Planung.", False, "chapter"),
            ("Prüfe das gesamte Manuskript.", False, "review-story"),
            ("Check the timeline across the chapter outline.", True, "planning-audit"),
        ]
        for text, prose, action in cases:
            with self.subTest(text=text):
                self.assertEqual(chats.requested_action(text, "auto", has_plan=True, has_prose=prose,
                                                        story_context=True), action)

    def test_das_letzte_licht_uses_stored_number_and_separate_contexts(self):
        with Fixture() as f:
            pid = f.req("/projects", {"name": "Das letzte Licht", "kind": "novel", "lang": "en"})["id"]
            sid = f.req("/sessions", {"title": "Das letzte Licht", "project_id": pid})["id"]
            first = plan(f, pid, "The First Response", "Elara watched the light.")
            second = plan(f, pid, "The Radio Gap", "The lamp turned.")
            active = dispatch(f, sid, "Prüfe Kapitel 1 mit meinem Human Writing Skill.", document_id=second)
            self.assertEqual(active["editorial"]["id"], first)
            self.assertEqual(active["editorial"]["mode"], "audit")

            other = f.req("/projects", {"name": "Das letzte Licht", "kind": "novel", "lang": "en"})["id"]
            other_first = plan(f, other, "A completely separate story", "A bell sounded.")
            f.req("/sessions/" + sid, {"project_id": other})
            state = f.req("/sessions/" + sid)
            self.assertEqual({p["id"] for p in state["contexts"]}, {pid, other})
            self.assertEqual(dispatch(f, sid, "Prüfe Kapitel 1.")["editorial"]["id"], other_first)
            self.assertEqual(dispatch(f, sid, "Prüfe Kapitel 1.", context_id=pid)["editorial"]["id"], first)

            with closing(sqlite3.connect(f.db)) as conn, conn:
                conn.execute("UPDATE documents SET story_number=1 WHERE id=?", (second,))
            choices = dispatch(f, sid, "Prüfe Kapitel 1.")
            self.assertEqual(choices["choice"], "document")
            self.assertEqual({d["id"] for d in choices["choices"]}, {first, second})
            self.assertEqual(dispatch(f, sid, "Prüfe Kapitel 1.", chapter_id=second)["editorial"]["id"], second)

    def test_free_wording_release_is_classified_before_the_planning_review(self):
        real = ("Die Planung ist freigegeben. Erstelle jetzt die vollständige Geschichte mit allen Kapiteln und Illustrationen. "
                "Prüfe und korrigiere die Texte automatisch und stelle mir am Ende die Markdown- und MDX-Dateien zum Herunterladen bereit.")
        # This message used to become the planning review ("Planung" + "Prüfe").
        self.assertEqual(chats.requested_action(real, "auto", has_plan=True, has_prose=False, story_context=True), "planning-audit")
        starts = (real, "Die Planung ist freigegeben. Erstelle jetzt die Geschichte.", "Passt so, bitte vollständig schreiben.",
                  "Starte die Manuskriptproduktion.", "Schreibe jetzt alle drei Kapitel.", "Generate the full story now.",
                  "I approve the outline. Start writing.", "Geschichte vollständig erstellen", "Ja so ist das gut dann leg los")
        for text in starts:
            for state in ("proposal", "approved"):
                with self.subTest(text=text[:50], state=state):
                    self.assertEqual(chats.production_command(text, state), "automatic")
        self.assertEqual(chats.production_command("Planung freigegeben, gemeinsam schreiben.", "proposal"), "together")
        self.assertEqual(chats.production_command("Start writing", "approved"), "automatic")
        for text in ("Die Planung ist freigegeben.", "Ich gebe die Planung frei.", "I approve the outline."):
            self.assertEqual(chats.production_command(text, "proposal"), "approve")
        # Questions, conditions, negations, single chapters, rewrites and planning work never start a production.
        for text in ("Prüfe die Planung auf Widersprüche.", "Schreibe Kapitel 1.", "Schreibe das nächste Kapitel.",
                     "Ist die Planung freigegeben?", "Die Planung ist noch nicht freigegeben.", "Schreibe nicht die ganze Geschichte.",
                     "Die Planung ist freigegeben, aber ändere Kapitel 2.", "Schreibe alle Kapitel neu.",
                     "Schreibe die Geschichte weiter.", "Erstelle ein Titelbild für die Geschichte.",
                     "Wenn die Planung passt, schreibe die Geschichte.", "Überarbeite die Planung und prüfe die Handlung.",
                     "Start writing", "Was passiert in Kapitel 3?"):
            with self.subTest(text=text):
                self.assertIsNone(chats.production_command(text, "proposal"))
        self.assertIsNone(chats.production_command(real, None))   # no stored plan: nothing to release

    def test_chat_release_approves_the_stored_plan_and_starts_one_real_job(self):
        example = runpy.run_path(str(ROOT / "tests/creative-studio-production.py"))["example_plan"]()
        real = ("Die Planung ist freigegeben. Erstelle jetzt die vollständige Geschichte mit allen Kapiteln und Illustrationen. "
                "Prüfe und korrigiere die Texte automatisch und stelle mir am Ende die Markdown- und MDX-Dateien zum Herunterladen bereit.")

        def jobs(f):
            with closing(sqlite3.connect(f.db)) as conn:
                return [(json.loads(p)["kind"], json.loads(p).get("action"), state) for p, state in conn.execute(
                    "SELECT payload,state FROM jobs WHERE service='production' ORDER BY created")]

        with Fixture() as f:
            pid = f.req("/projects", {"name": "Thunderforge", "kind": "story", "lang": "de"})["id"]
            sid = f.req("/sessions", {"title": "Thunderforge", "project_id": pid})["id"]
            with closing(sqlite3.connect(f.db)) as conn, conn:
                conn.execute("INSERT INTO story_production_plans(project_id,version,state,plan,impact,created) VALUES(?,?,?,?,?,?)",
                             (pid, 1, "proposal", json.dumps(example), "{}", 1.0))
            self.assertEqual(f.req(f"/production/{pid}")["stage"], "PLAN_READY")
            # A review request still reviews the plan and starts nothing.
            dispatch(f, sid, "Prüfe die Planung auf Widersprüche.", mode="auto")
            self.assertEqual([kind for kind, *_ in jobs(f)], ["planning"])
            self.assertEqual(f.req(f"/production/{pid}")["plan"] is not None, True)
            release = "Ja so ist das gut dann leg los"
            first = dispatch(f, sid, release, mode="auto")
            self.assertTrue(first["handled"] and first["production_id"] and first["project_id"] == pid)
            info = f.req(f"/production/{pid}")
            self.assertTrue(info["approved"])
            self.assertEqual(info["version"], 1)
            self.assertEqual(info["stage"], "PRODUCTION_RUNNING")
            self.assertEqual(info["job"]["id"], first["production_id"])
            self.assertEqual([kind for kind, *_ in jobs(f)], ["planning", "story"])
            # Repeating the instruction neither duplicates the job nor starts another review.
            again = dispatch(f, sid, "Ja so ist das gut dann leg los", mode="auto")
            self.assertEqual(again["production_id"], first["production_id"])
            self.assertEqual([kind for kind, *_ in jobs(f)], ["planning", "story"])
            with closing(sqlite3.connect(f.db)) as conn:
                said = [row[0] for row in conn.execute("SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY created,rowid", (sid,))]
            self.assertIn(release, said)

    def test_chat_release_without_a_stored_plan_does_not_start_production(self):
        real = "Die Planung ist freigegeben. Erstelle jetzt die vollständige Geschichte mit allen Kapiteln und Illustrationen."
        with Fixture() as f:
            pid = f.req("/projects", {"name": "Thunderforge", "kind": "story", "lang": "de"})["id"]
            sid = f.req("/sessions", {"title": "Thunderforge", "project_id": pid})["id"]
            answer = dispatch(f, sid, real, mode="auto")
            self.assertNotIn("production_id", answer)
            with closing(sqlite3.connect(f.db)) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM jobs WHERE service='production' AND json_extract(payload,'$.kind')='story'").fetchone()[0], 0)

    def test_natural_story_commission_routes_to_persistent_automatic_planning(self):
        texts = [
            ("Erstelle eine deutschsprachige Riff-Racers-Geschichte mit dem Titel Donner über Thunderforge. "
             "3 Kapitel mit jeweils 900–1.200 Wörtern. Im Mittelpunkt stehen Mika Blaze, Rhythm Kaur und ein Rennen auf Thunderforge.", "de", "auto_production"),
            ("Create an English-language story titled Thunder over Thunderforge. 3 chapters of 900–1,200 words each.", "en", "auto_production"),
            ("Erstelle eine deutsche Geschichte mit 3 Kapiteln. Zeige mir zuerst die Planung.", "de", "approval_first"),
            ("Erstelle die ganze Geschichte", "de", "auto_production"),
        ]
        for text, language, production_mode in texts:
            with self.subTest(text=text), Fixture() as f:
                sid = f.req("/sessions", {"title": "Autonome Geschichte"})["id"]
                request_id = uuid.uuid4().hex
                first = dispatch(f, sid, text, mode="auto", request_id=request_id)
                again = dispatch(f, sid, text, mode="auto", request_id=request_id)
                self.assertEqual(first["id"], again["id"])
                with closing(sqlite3.connect(f.db)) as conn:
                    rows = conn.execute("SELECT payload FROM jobs WHERE service='production'").fetchall()
                self.assertEqual(len(rows), 1)
                payload = json.loads(rows[0][0])
                self.assertEqual(payload["kind"], "plan")
                self.assertEqual(payload["language"], language)
                self.assertEqual(payload["production_mode"], production_mode)
                self.assertEqual(payload["count"], 3 if "3" in text else 8)
                if "900" in text:
                    self.assertEqual((payload["minimum"], payload["maximum"]), (900, 1200))

    def test_chat_owned_content_follows_folder_and_trash(self):
        with Fixture() as f:
            sid = f.req("/sessions", {"title": "A mixed chat"})["id"]
            context = f.req("/sessions/" + sid + "/context", {"kind": "story", "lang": "en"})["project_id"]
            first = plan(f, context, "A real stored chapter", "The keeper heard a bell.")
            folder = f.req("/organizer/folder", {"name": "Meine Geschichten"})["id"]
            entry = {"kind": "chat", "id": sid}
            f.req("/organizer/move", {"entries": [entry], "folder_id": folder})
            f.req("/organizer/rename", {"entries": [{"kind": "folder", "id": folder}], "name": "Stories"})
            self.assertEqual(f.req("/sessions/" + sid)["folder_id"], folder)
            self.assertEqual(dispatch(f, sid, "Prüfe Kapitel 1.")["editorial"]["id"], first)
            preview = f.req("/organizer/preview", {"entries": [entry], "operation": "trash"})
            self.assertIn(first, [item["id"] for item in preview["entries"]])
            f.req("/organizer/trash", {"entries": [entry], "token": preview["token"]})
            self.assertNotIn(context, [item["id"] for item in f.req("/projects")])
            f.req("/organizer/restore", {"entries": [entry]})
            self.assertEqual(f.req("/sessions/" + sid)["project_id"], context)
            self.assertEqual(f.req("/documents/" + first)["body"], "The keeper heard a bell.")
            self.assertTrue(f.req("/documents/" + first + "/versions"))
            illustration = dispatch(f, sid, "Erstelle eine Illustration für Kapitel 1.")
            with closing(sqlite3.connect(f.db)) as conn:
                payload = conn.execute("SELECT payload FROM jobs WHERE id=?", (illustration["id"],)).fetchone()[0]
            self.assertEqual(json.loads(payload)["document_id"], first)

    def test_recovery_chat_for_legacy_folder_and_safe_reopen(self):
        backend = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            for migration in backend["MIGRATIONS"][:4]:
                conn.executescript(migration)
            conn.execute("INSERT INTO folders(id,name,updated) VALUES('folder','Altbestand',1)")
            conn.execute("INSERT INTO projects(id,name,folder_id,created,updated) VALUES('p','Alttext','folder',1,1)")
            conn.execute("INSERT INTO documents(id,project_id,title,body) VALUES('d','p','Titel','Vorheriger Text')")
            conn.executescript(backend["chats"].MIGRATION)
            self.assertEqual(conn.execute("SELECT title,folder_id FROM sessions WHERE project_id='p'").fetchall(), [("Alttext","folder")])
            self.assertEqual(conn.execute("SELECT context_id FROM chat_contexts").fetchall(), [("p",)])
            self.assertEqual(conn.execute("SELECT id,body FROM documents").fetchall(), [("d", "Vorheriger Text")])


if __name__ == "__main__":
    unittest.main()
