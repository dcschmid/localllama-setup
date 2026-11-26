#!/usr/bin/env python3
"""Folder knowledge integration tests: storage, inheritance, proposals, injection, profiles."""

import json
import os
import runpy
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "libexec/llama-creative-studio"


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers();
        self.wfile.write(payload)

    def do_GET(self):
        self.respond(200, {"ok": True})

    def do_POST(self):
        self.respond(200, {"ok": True, "choices": [{"message": {"content": "{}"}}]})


class StudioFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="studio-knowledge-")
        self.root = Path(self.temp.name)
        self.data = self.root / "data/creative-studio"
        self.data.mkdir(parents=True)
        self.db = self.data / "studio.sqlite3"
        sys.path.insert(0, str(BACKEND.parent))
        migrations = runpy.run_path(str(BACKEND))["MIGRATIONS"]
        sys.path.pop(0)
        with sqlite3.connect(self.db) as connection:
            connection.execute("CREATE TABLE schema_version(v INTEGER)")
            for index, schema in enumerate(migrations, 1):
                connection.executescript(schema)
                connection.execute("INSERT INTO schema_version VALUES(?)", (index,))
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        with socket.socket() as allocator:
            allocator.bind(("127.0.0.1", 0))
            port = allocator.getsockname()[1]
        service = f"http://127.0.0.1:{self.upstream.server_port}"
        self.url = f"http://127.0.0.1:{port}"
        self.env = os.environ | {
            "XDG_DATA_HOME": str(self.data.parent), "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_STATE_HOME": str(self.root / "state"), "CREATIVE_STUDIO_PORT": str(port),
            "CREATIVE_STUDIO_IMAGES": service, "CREATIVE_STUDIO_ROUTER": service,
            "CREATIVE_STUDIO_RESEARCH": service, "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.start()
        return self

    def start(self):
        self.log = (self.root / "server.log").open("w+")
        self.process = subprocess.Popen([sys.executable, str(BACKEND), "serve"], env=self.env,
                                        stdout=self.log, stderr=self.log)
        for _ in range(120):
            try:
                if self.req("/health")["ok"]:
                    return self
            except OSError:
                if self.process.poll() is not None:
                    break
                time.sleep(.05)
        self.log.seek(0)
        raise RuntimeError("Studio failed to start: " + self.log.read())

    def restart(self):
        self.process.terminate()
        self.process.wait(timeout=10)
        self.start()

    def __exit__(self, *_args):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.log.close()
        self.temp.cleanup()

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        return urllib.request.urlopen(urllib.request.Request(
            self.url + "/api" + path, data=data, headers={"Content-Type": "application/json"}), timeout=15)

    def req(self, path, body=None):
        with self.request(path, body) as response:
            return json.load(response)


class KnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = StudioFixture()
        cls.fixture.__enter__()
        cls.addClassCleanup(cls.fixture.__exit__)
        cls.req = cls.fixture.req

    def connection(self):
        connection = sqlite3.connect(self.fixture.db, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def folder(self, name, parent=None):
        return self.req("/organizer/folder", {"name": name, "folder_id": parent})["id"]

    def knowledge(self, folder, **body):
        return self.req(f"/folders/{folder}/knowledge", body or None)

    def add(self, folder, *, category="fact", title="Fakt", content="Inhalt", status=None, source=""):
        body = {"action": "add", "category": category, "title": title, "content": content, "source": source}
        if status:
            body["status"] = status
        return self.knowledge(folder, **body)["entry"]

    def test_01_empty_folder_behaves_as_before(self):
        folder = self.folder("Leer ohne Wissen")
        view = self.knowledge(folder)
        self.assertEqual(view["entries"], view["own"], [])
        self.assertIsNone(view["hint"])
        listed = [entry for entry in self.req("/organizer/folders") if entry["id"] == folder]
        self.assertEqual(len(listed), 1)

    def test_02_entries_store_every_required_field(self):
        folder = self.folder("Felder")
        entry = self.add(folder, title="Eintrag", content="Text", source="Doku")
        for field in ("id", "category", "title", "content", "source", "status", "version", "created", "updated"):
            self.assertIn(field, entry)
        self.assertEqual(entry["status"], "reference")
        self.assertEqual(entry["version"], 1)

    def test_03_confirmed_status_is_explicit(self):
        folder = self.folder("Kanon Ordner")
        entry = self.add(folder, title="Regel", content="Musikalisches Arcade-Kart-Racing", status="confirmed")
        self.assertEqual(entry["status"], "confirmed")

    def test_04_chat_in_folder_reports_knowledge(self):
        folder = self.folder("Sichtbarer Ordner")
        self.add(folder, title="Mika", content="Fahrerin der Metal World", status="confirmed")
        chat = self.req("/sessions", {"title": "Chat im Ordner", "folder_id": folder})["id"]
        hint = self.req(f"/folders/hint?session={chat}")
        self.assertEqual(hint["name"], "Sichtbarer Ordner")
        self.assertEqual(hint["count"], 1)

    def test_05_child_inherits_parent_canon(self):
        parent = self.folder("Eltern")
        child = self.folder("Kind", parent)
        self.add(parent, title="Weltregel", content="Fünf Welten", status="confirmed")
        view = self.knowledge(child)
        self.assertEqual([item["title"] for item in view["inherited"]], ["Weltregel"])
        self.assertEqual([item["title"] for item in view["entries"]], ["Weltregel"])

    def test_06_child_adds_own_facts(self):
        parent = self.folder("Erbbasis")
        child = self.folder("Zusatz", parent)
        self.add(parent, title="Basis", content="Elternfakt")
        self.add(child, title="Extra", content="Kindfakt")
        view = self.knowledge(child)
        self.assertEqual({item["title"] for item in view["own"]}, {"Extra"})
        self.assertEqual({item["title"] for item in view["inherited"]}, {"Basis"})
        self.assertEqual(len(view["entries"]), 2)

    def test_07_conflicting_confirmed_facts_surface(self):
        parent = self.folder("Konflikt Basis")
        child = self.folder("Konflikt Kind", parent)
        self.add(parent, category="character", title="Rhythm", content="Freundin", status="confirmed")
        self.add(child, category="character", title="Rhythm", content="Rivalin", status="confirmed")
        view = self.knowledge(child)
        self.assertEqual(len(view["conflicts"]), 1)
        parent_side, child_side = view["conflicts"][0]
        self.assertEqual((parent_side["content"], child_side["content"]), ("Freundin", "Rivalin"))
        self.assertEqual(view["entries"][0]["content"], "Rivalin")

    def test_08_sibling_folders_stay_separate(self):
        first = self.folder("Weg Eins")
        second = self.folder("Weg Zwei")
        self.add(first, title="Nur Hier", content="Metallwelt")
        self.assertEqual(self.knowledge(second)["entries"], [])

    def test_09_imported_files_stay_unconfirmed(self):
        folder = self.folder("Vorschläge")
        imported = self.knowledge(folder, action="import", title="Doku.md", content="Streckentext",
                                  source="riff-racers/docs")["entry"]
        self.assertEqual(imported["status"], "reference")
        confirmed = self.knowledge(folder, action="status", entry_id=imported["id"], status="confirmed")["entry"]
        self.assertEqual((confirmed["status"], confirmed["version"]), ("confirmed", 2))

    def test_10_versions_are_restorable(self):
        folder = self.folder("Versionen")
        entry = self.add(folder, title="Chronik", content="v1")
        self.knowledge(folder, action="update", entry_id=entry["id"], content="v2", version=1)
        with self.assertRaises(urllib.error.HTTPError) as held:
            self.req(f"/folders/{folder}/knowledge", {"action": "update", "entry_id": entry["id"],
                                                      "content": "konkurrierend", "version": 1})
        self.assertEqual(held.exception.code, 409)
        history = self.knowledge(folder, action="versions", entry_id=entry["id"])["versions"]
        self.assertEqual([item["version"] for item in history], [1])
        restored = self.knowledge(folder, action="restore", entry_id=entry["id"], version=1)["entry"]
        self.assertEqual((restored["content"], restored["version"]), ("v1", 3))

    def test_11_delete_removes_entry(self):
        folder = self.folder("Löschen")
        entry = self.add(folder, title="Entwurf", content="weg")
        self.knowledge(folder, action="delete", entry_id=entry["id"])
        self.assertEqual(self.knowledge(folder)["entries"], [])

    def test_12_export_markdown_and_json(self):
        folder = self.folder("Export")
        self.add(folder, title="Exportfakt", content="Portable Fakten", status="confirmed")
        markdown = self.req(f"/folders/{folder}/knowledge?format=markdown")["content"]
        self.assertIn("Ordnerwissen · Export", markdown)
        self.assertIn("Exportfakt", markdown)
        payload = self.req(f"/folders/{folder}/knowledge?format=json")["content"]
        self.assertEqual(payload["entries"][0]["title"], "Exportfakt")

    def test_13_visual_profile_defaults_and_overrides(self):
        parent = self.folder("Profil Basis")
        self.knowledge(parent, action="profile", profile={"template": "riff-racers-low-poly", "ratio": "16:9",
                                                          "style": "Low-Poly Concept Art", "palette": "Metall"})
        child = self.folder("Profil Kind", parent)
        self.assertEqual(self.knowledge(child)["profile"]["template"], "riff-racers-low-poly")
        chat = self.req("/sessions", {"title": "Profil Chat", "folder_id": parent})["id"]
        sys.path.insert(0, str(BACKEND.parent))
        import creative_studio_knowledge as knowledge
        try:
            with self.connection() as connection:
                default = knowledge.profile_default(connection, {"template": "anima-aesthetic", "ratio": "1:1",
                                                                 "version": 0}, session_id=chat)
                self.assertEqual(default["template"], "riff-racers-low-poly")
                self.assertEqual(default["ratio"], "16:9")
                self.assertEqual(default["model"], "moss")
                self.assertEqual(default["style"], "Low-Poly Concept Art")
                authored = {"template": "graphic-novel", "ratio": "1:1", "version": 4}
                self.assertEqual(knowledge.profile_default(connection, authored, session_id=chat), authored)
        finally:
            sys.path.pop()

    def test_legacy_named_visual_profile_keeps_its_style_and_matching_model(self):
        folder = self.folder("Riff Racers")
        self.knowledge(folder, action="add", category="visual-profile", title="Visual Profile", status="confirmed",
            content=json.dumps({"template": "Riff Racers Default", "ratio": "", "style": "Low-Poly Concept Art, retro 3D game look",
                                "palette": "Metall und Orange"}))
        chat = self.req("/sessions", {"title": "Donner", "folder_id": folder})["id"]
        sys.path.insert(0, str(BACKEND.parent))
        import creative_studio_knowledge as knowledge
        try:
            with self.connection() as connection:
                profile = knowledge.profile_default(connection, {"template": "anima-aesthetic", "version": 0}, session_id=chat)
                self.assertEqual(profile["template"], "riff-racers-low-poly")
                self.assertEqual(profile["model"], "moss")
                self.assertEqual(profile["ratio"], "16:9")
                self.assertEqual(profile["style"], "Low-Poly Concept Art, retro 3D game look")
                self.assertEqual(profile["palette"], "Metall und Orange")
        finally:
            sys.path.pop()

    def test_14_knowledge_survives_restart(self):
        folder = self.folder("Dauerhaft")
        self.add(folder, title="Bleibt", content="Nach Neustart", status="confirmed")
        self.fixture.restart()
        self.assertEqual(self.req(f"/folders/{folder}/knowledge")["entries"][0]["title"], "Bleibt")

    def test_15_riff_racers_world_roundtrip(self):
        parent = self.folder("Riff Racers Stories")
        metal = self.folder("Metal World", parent)
        thunderforge = self.add(metal, category="place", title="Thunderforge",
                                content="Rennstrecke der Metal World (Referenz, noch nicht bestätigt)",
                                source="riff-racers/docs")
        self.assertEqual(thunderforge["status"], "reference")
        self.add(parent, category="rule", title="Rennregeln", content="Bestätigte Spielregeln sind Kanon.",
                 status="confirmed")
        self.add(parent, category="idea", title="Neue Strecke", content="Ideentext, nie Kanon")
        view = self.knowledge(metal)
        self.assertEqual(view["hint"]["name"], "Metal World")
        self.assertEqual(view["hint"]["count"], 1)
        self.assertEqual([item["title"] for item in view["inherited"]], ["Neue Strecke", "Rennregeln"])
        self.assertEqual([item["title"] for item in view["own"]], ["Thunderforge"])
        sys.path.insert(0, str(BACKEND.parent))
        import creative_studio_knowledge as knowledge
        try:
            with self.connection() as connection:
                block = knowledge.select(connection, metal, "Thunderforge Rennregeln")["text"]
                self.assertIn("Thunderforge", block)
                self.assertIn("Bestätigte Spielregeln", block)
                self.assertNotIn("Ideentext", block)
        finally:
            sys.path.pop()


if __name__ == "__main__":
    unittest.main()
