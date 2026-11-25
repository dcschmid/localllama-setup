#!/usr/bin/env python3
"""Organizer integration tests using a temporary v2 database and local image stub."""

import base64
import concurrent.futures
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
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "libexec/llama-creative-studio"
SHARED_IMAGE = "1" * 32
PRIVATE_IMAGE = "2" * 32
LEGACY_PROJECT = "3" * 32
LEGACY_SESSION = "4" * 32
LEGACY_DOCUMENT = "5" * 32
PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGPYlOkCAAMwAWA8tcxnAAAAAElFTkSuQmCC")


class ImageStub(BaseHTTPRequestHandler):
    images = {identifier: {"id": identifier, "request": {"prompt": name}}
              for identifier, name in ((SHARED_IMAGE, "Gemeinsames Bild"), (PRIVATE_IMAGE, "Einzelbild"))}
    attempts = []
    stream_started = threading.Event()
    stream_release = threading.Event()

    def log_message(self, *_args):
        pass

    def respond(self, status, body):
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = self.path.partition("?")[0]
        identifier = path.rsplit("/", 1)[-1]
        if path in ("/health", "/healthz"):
            return self.respond(200, {"ok": True})
        if path == "/studio/api/catalog":
            return self.respond(200, {"models": [], "presets": []})
        if path == "/studio/api/gallery":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            offset = int(query.get("offset", [0])[0])
            return self.respond(200, list(self.images.values())[offset:offset + 60])
        if identifier in self.images:
            if path.startswith("/studio/api/gallery/"):
                return self.respond(200, self.images[identifier])
            if path.startswith("/studio/api/files/"):
                return self.respond(200, PIXEL)
        return self.respond(404, {"error": "not_found"})

    def do_DELETE(self):
        identifier = self.path.rsplit("/", 1)[-1]
        if not self.path.startswith("/studio/api/gallery/") or identifier not in self.images:
            return self.respond(404, {"error": "not_found"})
        self.attempts.append(identifier)
        if self.attempts.count(identifier) == 1:
            return self.respond(503, {"error": "temporary"})
        del self.images[identifier]
        return self.respond(200, {"id": identifier, "deleted": True})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self.respond(404, {"error": "not_found"})
        self.rfile.read(int(self.headers["Content-Length"]))
        self.stream_started.set()
        self.stream_release.wait(timeout=8)
        return self.respond(200, b'data: {"choices":[{"delta":{"content":"Ein fertiger Satz."}}]}\n\ndata: [DONE]\n\n')


class StudioFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="studio-organizer-")
        self.root = Path(self.temp.name)
        data = self.root / "data/creative-studio"
        data.mkdir(parents=True)
        self.db = data / "studio.sqlite3"
        sys.path.insert(0, str(BACKEND.parent))
        migrations = runpy.run_path(str(BACKEND))["MIGRATIONS"]
        sys.path.pop(0)
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE schema_version(v INTEGER)")
            for index, schema in enumerate(migrations[:2], 1):
                conn.executescript(schema)
                conn.execute("INSERT INTO schema_version VALUES(?)", (index,))
            conn.execute("INSERT INTO projects(id,name,created,updated) VALUES(?, 'Bestand', 1, 1)", (LEGACY_PROJECT,))
            conn.execute("INSERT INTO sessions(id,project_id,title,created) VALUES(?,?,'Bestandschat',1)",
                         (LEGACY_SESSION, LEGACY_PROJECT))
            conn.execute("INSERT INTO messages(id,session_id,role,content,created) VALUES('legacy',?,'user','Grüße aus dem Bestand',2)",
                         (LEGACY_SESSION,))
            conn.execute("INSERT INTO documents(id,project_id,title,body,created,updated) VALUES(?,?,'Altes Kapitel','Bestandstext',1,1)",
                         (LEGACY_DOCUMENT, LEGACY_PROJECT))
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), ImageStub)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        with socket.socket() as allocator:
            allocator.bind(("127.0.0.1", 0))
            port = allocator.getsockname()[1]
        service = f"http://127.0.0.1:{self.upstream.server_port}"
        self.url = f"http://127.0.0.1:{port}"
        env = os.environ | {
            "XDG_DATA_HOME": str(data.parent), "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_STATE_HOME": str(self.root / "state"), "CREATIVE_STUDIO_PORT": str(port),
            "CREATIVE_STUDIO_IMAGES": service, "CREATIVE_STUDIO_ROUTER": service, "CREATIVE_STUDIO_RESEARCH": service,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.log = (self.root / "server.log").open("w+")
        self.process = subprocess.Popen([sys.executable, str(BACKEND), "serve"], env=env,
                                        stdout=self.log, stderr=self.log)
        for _ in range(80):
            try:
                if self.req("/health")["ok"]:
                    return self
            except OSError:
                if self.process.poll() is not None:
                    break
                time.sleep(.05)
        self.log.seek(0)
        error = self.log.read()
        self.__exit__()
        raise RuntimeError("Studio failed to start: " + error)

    def __exit__(self, *_args):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.log.close()
        self.temp.cleanup()

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        return urllib.request.urlopen(urllib.request.Request(
            self.url + "/api" + path, data=data, headers={"Content-Type": "application/json"}), timeout=10)

    def req(self, path, body=None):
        with self.request(path, body) as response:
            return json.load(response)


def entry(kind, identifier):
    return {"kind": kind, "id": identifier}


class OrganizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = StudioFixture()
        cls.fixture.__enter__()
        cls.addClassCleanup(cls.fixture.__exit__)
        cls.req = cls.fixture.req

    def action(self, action, *entries, **values):
        return self.req("/organizer/" + action, {"entries": list(entries), **values})

    def confirm(self, action, *entries):
        preview = self.action("preview", *entries, operation=action)
        self.action(action, *entries, token=preview["token"])
        return preview

    def expect_error(self, status, key, call, *args, **kwargs):
        with self.assertRaises(urllib.error.HTTPError) as error:
            call(*args, **kwargs)
        with error.exception as response:
            self.assertEqual(response.code, status)
            self.assertEqual(json.load(response)["error"], key)

    def folder(self, name, folder=None):
        return self.action("folder", name=name, folder_id=folder)["id"]

    def project(self, name, folder=None):
        return self.req("/projects", {"name": name, "folder_id": folder})["id"]

    def chat(self, name, project=None, folder=None):
        return self.req("/sessions", {"title": name, "project_id": project, "folder_id": folder})["id"]

    def test_additive_migration_and_unicode_search(self):
        backups = list(self.fixture.db.parent.glob("studio-before-v3-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(backups[0]) as snapshot:
            self.assertEqual(snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(snapshot.execute("SELECT max(v) FROM schema_version").fetchone()[0], 2)
            self.assertEqual(snapshot.execute("SELECT title FROM sessions WHERE id=?", (LEGACY_SESSION,)).fetchone()[0],
                             "Bestandschat")
        found = self.req("/sessions?q=GR%C3%9CSSE")
        self.assertEqual([item["id"] for item in found], [LEGACY_SESSION])
        self.assertEqual(found[0]["updated"], 2)
        self.assertEqual(self.req("/documents/" + LEGACY_DOCUMENT)["body"], "Bestandstext")

    def test_tree_batch_restore_and_collisions(self):
        top = self.folder("Geschichten")
        sub = self.folder("Fantasy", top)
        child = self.folder("Kapitel", sub)
        self.expect_error(409, "organizer_name_conflict", self.folder, "geschICHTEN")
        self.expect_error(409, "organizer_folder_cycle", self.action, "move", entry("folder", top), folder_id=child)
        project = self.project("Das letzte Licht", child)
        chat = self.chat("Dialoge", project, child)
        other = self.chat("Ausarbeitung", project)
        self.req(f"/sessions/{chat}/messages", {"role": "user", "content": "Ein Satz bleibt erhalten."})
        self.action("move", entry("chat", chat), entry("chat", other), folder_id=sub)
        self.assertEqual(self.req(f"/sessions/{chat}")["project_id"], project)
        self.assertEqual(self.req(f"/sessions/{chat}/messages")[0]["content"], "Ein Satz bleibt erhalten.")
        self.action("archive", entry("chat", chat), entry("chat", other))
        self.assertTrue({chat, other} <= {r["id"] for r in self.req("/organizer/archive")})
        self.action("unarchive", entry("chat", chat), entry("chat", other))
        self.confirm("trash", entry("chat", other))
        impact = self.confirm("trash", entry("folder", top))
        self.assertTrue({top, sub, child, project, chat, other} <= {r["id"] for r in impact["entries"]})
        self.expect_error(404, "organizer_not_found", self.req, f"/sessions/{chat}/messages")
        trash = {r["id"]: r for r in self.req("/organizer/trash")}
        self.assertEqual(trash[other]["location"], "Geschichten / Fantasy")
        self.assertGreater(trash[other]["deleted_at"], 0)
        self.folder("Geschichten")
        self.action("restore", entry("folder", top), entry("chat", other))
        folders = {r["id"]: r for r in self.req("/organizer/folders")}
        self.assertEqual(folders[top]["name"], "Geschichten (2)")
        self.assertEqual(folders[child]["folder_id"], sub)
        self.assertEqual(self.req(f"/sessions/{other}")["folder_id"], sub)

    def test_project_copy_attachments_and_shared_documents(self):
        original = self.project("Roman")
        surviving = self.project("Spin-off")
        chat = self.chat("Entwürfe", original)
        doc = self.req("/documents", {"project_id": original, "title": "Kapitel eins", "body": "Erste Fassung"})["id"]
        attachment = self.req("/attachments", {"project_id": original, "name": "../../Notizen.txt",
                              "data": base64.b64encode(b"Notizen").decode()})["id"]
        self.req(f"/documents/{doc}", {"body": "Zweite Fassung", "note": "Lektorat"})
        self.action("rename", entry("document", doc), name="Regenkapitel")
        self.assertEqual(self.req("/search?q=Regenkapitel")[0]["document_id"], doc)
        self.req(f"/sessions/{chat}/messages", {"role": "assistant", "content": "Siehe #document/" + doc,
                 "meta": {"kind": "document", "document_id": doc}})
        copy = self.action("duplicate", entry("project", original))["id"]
        deep = self.req(f"/projects/{copy}")
        copied_doc = deep["documents"][0]["id"]
        copied_chat = deep["chats"][0]["id"]
        self.assertNotEqual(doc, copied_doc)
        self.assertNotEqual(chat, copied_chat)
        self.assertEqual(len(self.req(f"/documents/{copied_doc}/versions")), 2)
        message = self.req(f"/sessions/{copied_chat}/messages")[0]
        self.assertEqual(message["meta"]["document_id"], copied_doc)
        self.assertIn(copied_doc, message["content"])
        copied_attachment = deep["attachments"][0]["id"]
        self.assertNotEqual(attachment, copied_attachment)
        with self.fixture.request(f"/attachments/{copied_attachment}") as response:
            self.assertEqual(response.read(), b"Notizen")
            self.assertIn("attachment;", response.headers["Content-Disposition"])
            self.assertNotIn("%2F", response.headers["Content-Disposition"])
        self.action("assign", entry("chat", chat), project_id=surviving)
        self.action("archive", entry("project", original))
        self.assertNotIn(original, {r["id"] for r in self.req("/projects")})
        self.action("unarchive", entry("project", original))
        impact = self.confirm("trash", entry("project", original))
        self.assertEqual(impact["preserved_documents"], [doc])
        self.assertEqual(self.req(f"/documents/{doc}")["project_id"], original)
        self.confirm("purge", entry("project", original))
        self.assertEqual(self.req(f"/documents/{doc}")["project_id"], surviving)
        self.assertEqual(self.req(f"/sessions/{chat}/messages")[0]["meta"]["document_id"], doc)
        self.expect_error(404, "organizer_not_found", self.req, f"/attachments/{attachment}")

    def test_atomic_confirmation_and_running_jobs(self):
        project = self.project("Laufende Recherche")
        chat = self.chat("Recherchegespräch", project)
        job = "7" * 32
        with sqlite3.connect(self.fixture.db) as conn:
            conn.execute("INSERT INTO jobs(id,service,state,payload) VALUES(?,'research','running',?)",
                         (job, json.dumps({"project_id": project, "session_id": chat, "paused": True})))
        target = entry("project", project)
        preview = self.action("preview", target, operation="trash")
        self.expect_error(409, "organizer_work_running", self.action, "trash", target, token=preview["token"])
        self.req(f"/research/{job}/cancel", {})
        self.req("/documents", {"project_id": project, "title": "Neu"})
        self.expect_error(409, "organizer_selection_changed", self.action, "trash", target, token=preview["token"])
        preview = self.action("preview", target, operation="trash")

        def delete():
            try:
                self.action("trash", target, token=preview["token"])
                return 200
            except urllib.error.HTTPError as exc:
                with exc:
                    return exc.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as callers:
            statuses = list(callers.map(lambda _: delete(), range(2)))
        self.assertEqual(sorted(statuses), [200, 404])
        empty = self.action("preview", operation="empty")
        self.confirm("trash", entry("chat", self.chat("Neu im Papierkorb")))
        self.expect_error(409, "organizer_selection_changed", self.action, "empty", token=empty["token"])
        self.confirm("empty")
        self.assertEqual(self.req("/organizer/trash"), [])

    def test_image_reference_protection_and_retry(self):
        first = self.project("Bildprojekt")
        second = self.project("Zweites Bildprojekt")
        self.req("/memories", {"kind": "image", "key": SHARED_IMAGE, "project_id": first, "body": "Bild"})
        self.req("/projects/" + second, {"cover": SHARED_IMAGE})
        self.confirm("trash", entry("project", first))
        self.confirm("purge", entry("project", first))
        self.assertIn(SHARED_IMAGE, ImageStub.images)
        target = entry("image", SHARED_IMAGE)
        self.confirm("trash", target)
        self.assertNotIn(SHARED_IMAGE, {im["id"] for im in self.req("/images/gallery?managed=1")["images"]})
        with self.fixture.request(f"/images/files/{SHARED_IMAGE}") as response:
            self.assertEqual(response.read(), PIXEL)
        preview = self.action("preview", target, operation="purge")
        self.expect_error(409, "organizer_image_in_use", self.action, "purge", target, token=preview["token"])
        self.action("restore", target)
        private = entry("image", PRIVATE_IMAGE)
        self.confirm("trash", private)
        self.confirm("purge", private)
        self.expect_error(404, "image_not_found", self.req, f"/images/files/{PRIVATE_IMAGE}")
        self.expect_error(404, "image_not_found", self.req, "/memories",
                          {"kind": "image", "key": PRIVATE_IMAGE, "project_id": second, "body": "Bild"})
        deadline = time.monotonic() + 13
        while PRIVATE_IMAGE in ImageStub.images and time.monotonic() < deadline:
            time.sleep(.1)
        self.assertNotIn(PRIVATE_IMAGE, ImageStub.images)
        self.assertEqual(ImageStub.attempts, [PRIVATE_IMAGE, PRIVATE_IMAGE])
        self.assertIn(SHARED_IMAGE, ImageStub.images)
        self.expect_error(404, "organizer_not_found", self.req, "/attachments/%2e%2e%2fetc%2fpasswd")

    def test_project_can_be_trashed_after_its_stream_finishes(self):
        project = self.project("Schreibprojekt")
        chat = self.chat("Schreibchat", project)
        target = entry("project", project)

        def write():
            with self.fixture.request("/write", {"project_id": project, "session_id": chat,
                                                  "instruction": "Schreibe einen Satz."}) as response:
                return response.read().decode()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as workers:
            writing = workers.submit(write)
            try:
                self.assertTrue(ImageStub.stream_started.wait(timeout=4))
                preview = self.action("preview", target, operation="trash")
                self.expect_error(409, "organizer_work_running", self.action, "trash", target, token=preview["token"])
            finally:
                ImageStub.stream_release.set()
            self.assertIn("Ein fertiger Satz.", writing.result(timeout=8))
        self.assertEqual(self.req(f"/sessions/{chat}/messages")[-1]["content"], "Ein fertiger Satz.")
        self.confirm("trash", target)

    def test_restore_document_without_its_original_project(self):
        project = self.project("Dokumentprojekt")
        doc = self.req("/documents", {"project_id": project, "title": "Kapitel", "body": "Inhalt"})["id"]
        self.confirm("trash", entry("project", project))
        trashed = {row["id"]: row for row in self.req("/organizer/trash")}
        self.assertEqual(trashed[doc]["location"], "Dokumentprojekt")
        self.action("restore", entry("document", doc))
        restored = self.req(f"/documents/{doc}")
        self.assertEqual(restored["body"], "Inhalt")
        self.assertNotEqual(restored["project_id"], project)
        self.assertEqual(self.req(f"/projects/{restored['project_id']}")["name"], "Wiederhergestellte Dateien")


if __name__ == "__main__":
    unittest.main()
