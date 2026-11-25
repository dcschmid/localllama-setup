#!/usr/bin/env python3
"""Visual profile persistence, live catalog contracts and durable image admission."""

import json
import os
import runpy
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_visual as visual


def catalog():
    models = [{"id": model, "installed": True, "formats": [
                  {"id": "16:9", "size": "1024x576", "preview_size": "768x432"},
                  {"id": "4:3", "size": "1024x768", "preview_size": "768x576"}],
               "sizes": ["1024x576", "1024x768", "768x432"], "negative": True,
               "verified_modes": ["text", "img2img"], "license": "Fixture"}
              for model in ("moss", "anima", "z-image")]
    recipes = {recipe: model for _, model, recipe, _ in visual.TEMPLATES.values() if recipe}
    return {"models": models, "recipes": [{"id": key, "model": model} for key, model in recipes.items()]}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.temp.name, "XDG_CONFIG_HOME": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        self.runtime = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
        self.runtime["migrate"]()
        self.conn = self.runtime["db"]()
        self.addCleanup(lambda: self.runtime["db"]().close())
        self.a, self.b, self.sid = ("a" * 32, "b" * 32, "c" * 32)
        with self.conn:
            for pid, name in ((self.a, "Signal House"), (self.b, "Riff Racers")):
                self.conn.execute("INSERT INTO projects(id,name,kind,lang) VALUES (?,?,'story','en')", (pid, name))
            self.conn.execute("INSERT INTO sessions(id,project_id) VALUES (?,?)", (self.sid, self.a))

    def test_switch_copy_and_reopen(self):
        with self.conn:
            first = visual.save(self.conn, self.a, {"version": 0, "ratio": "4:3"}, catalog())
            self.assertEqual(first["model"], "anima")
            visual.save(self.conn, self.a, {"version": 1, "template": "graphic-novel"}, catalog())
            self.assertEqual(visual.load(self.conn, self.b)["template"], "riff-racers-low-poly")
            copied = visual.save(self.conn, self.b, {"version": 0, "copy_from": self.a}, catalog())
            self.assertEqual((copied["id"], copied["version"]), (self.b, 1))
        self.conn.close()
        del self.runtime["_dbs"].conn
        self.conn = self.runtime["db"]()
        self.assertEqual(visual.load(self.conn, self.a)["ratio"], "4:3")
        self.assertEqual(visual.load(self.conn, self.b)["model"], "moss")
        with self.assertRaisesRegex(ValueError, "visual_profile_changed"):
            visual.save(self.conn, self.a, {"version": 0}, catalog())

    def test_no_model_or_aspect_fallback_and_safe_preview(self):
        config = catalog()
        profile = visual.load(self.conn, self.a)
        config["models"][1]["installed"] = False
        with self.assertRaisesRegex(ValueError, "visual_model_unavailable"):
            visual.available(config, profile)
        config["models"][1]["installed"] = True
        config["models"][1]["sizes"].remove("1024x576")
        request, metadata, size = visual.prepare(profile, config, "Lantern", "snow", 1)
        self.assertEqual((request["quality"], size), ("preview", "768x432"))
        self.assertEqual(metadata["ratio"], "16:9")
        config["models"][1]["sizes"].remove("768x432")
        with self.assertRaisesRegex(ValueError, "visual_format_unavailable"):
            visual.available(config, profile)
        with self.assertRaisesRegex(ValueError, "visual_recipe_unavailable"):
            visual.available(catalog(), {**profile, "recipe": "moss-comic"})
        self.assertIsNone(visual.requested_ratio("She arrived at 12:30."))
        self.assertEqual(visual.requested_ratio("Bitte im Format 5:4."), "5:4")
        self.assertEqual(visual.requested_ratio("Please use 4:3."), "4:3")
        self.assertIsNone(visual.choice("Illustrate a Riff Racers chase", riff=True))
        self.assertEqual(visual.choice("Use High-Poly for Riff Racers", riff=True), "riff-racers-high-poly")

    def test_chronology_palette_and_verified_conditioning(self):
        identifier = "d" * 32
        with self.conn:
            self.conn.execute("INSERT INTO attachments(id,project_id,name,data,updated) VALUES (?,?,'reference.png',?,0)",
                              (identifier, self.a, b"fixture"))
            profile = visual.save(self.conn, self.a, {"version": 0, "bible": {"characters": [
                {"name": "Ada", "clothing": "Rust-red coat", "from": 1, "to": 3,
                 "attachment": identifier, "use_image": True},
                {"name": "Ada", "clothing": "Blue uniform", "from": 4, "to": 6},
                {"name": "Nera", "clothing": "Silver jacket", "from": 2, "to": 5}]}}, catalog())
        config = catalog()
        body, props, size = visual.prepare(profile, config, "Ada lifts a lantern", "Snow covers the yard", 3,
                                           cover=True, upload=lambda ident: self.assertEqual(ident, identifier) or "e" * 32)
        self.assertEqual((body["model"], body["mode"], body["image_id"], size), ("anima", "img2img", "e" * 32, "1024x576"))
        self.assertIn("Rust-red coat", body["details"])
        self.assertNotIn("Blue uniform", body["details"])
        self.assertNotIn("Nera", body["details"])
        self.assertIn("ice-blue", props["palette"])
        next_body, next_props, _ = visual.prepare(profile, config, "Ada lifts a lantern", "A forest at noon", 4)
        self.assertIn("Blue uniform", next_body["details"])
        self.assertIn("Natural greens", next_props["palette"])
        config["models"][1]["verified_modes"] = ["text"]
        with self.assertRaisesRegex(ValueError, "visual_reference_unavailable"):
            visual.prepare(profile, config, "Ada", "snow", 3, upload=lambda _: "e" * 32)

    def test_confirmed_gpu_rejection_requeues_same_local_image(self):
        runtime = self.runtime
        parent_id = "e" * 32
        external = "f" * 32
        with self.conn:
            runtime["queue_image"](self.conn, {"size": "1024x576"}, {"project_id": self.a,
                "visual_profile": {"version": 1}}, identifier=parent_id)
            self.conn.execute("UPDATE jobs SET external_id=?,state='queued' WHERE id=?", (external, parent_id))
        runtime["http_json"] = lambda *_, **__: (200, {"id": external, "status": "failed",
                    "error": "GPU is occupied by another compute process"})
        runtime["advance_image"](parent_id)
        row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (parent_id,)).fetchone()
        self.assertEqual(row["state"], "waiting_gpu")
        self.assertIsNone(row["external_id"])
        payload = json.loads(row["payload"])
        self.assertEqual(payload["gpu_attempt"], 1)
        self.assertGreater(payload["not_before"], time.time())
        self.assertEqual(json.loads(row["result"])["previous_attempt"], external)


if __name__ == "__main__":
    unittest.main()
