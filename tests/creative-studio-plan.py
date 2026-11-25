#!/usr/bin/env python3
"""Regression checks for the server planner and its bounded writing retry."""
import io
import runpy
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
studio = runpy.run_path(str(ROOT / "libexec" / "llama-creative-studio"))
from creative_studio_plan import PlanError, build_plan, check_text, word_bounds

TEXT = studio["skill_text"]()
EN = "The light was off. She had left it on for him."
DE = "Das Licht war aus. Sie hatte es für ihn angelassen."


def plan(text, mode="auto", default="de", image=None):
    return build_plan(text, mode, default, image or {}, TEXT.detect_lang)


class Planner(unittest.TestCase):
    def test_compound_request_uses_localized_language_and_exact_format(self):
        payload = plan("""**Titel:** Das letzte Licht
1. Schreibe eine englische Mystery-Geschichte mit ungefähr 350 Wörtern.
2. Verwende meinen Human Writing Skill.
3. Erstelle danach eine passende Illustration in 16:9. Stil: Graphic Novel.
4. Zeige das Bild hier im Chat und speichere alles im Projekt namens „Das letzte Licht“.""",
                       image={"size": "512x512"})
        self.assertEqual(payload["project_name"], "Das letzte Licht")
        self.assertEqual(payload["writing"]["kind"], "story")
        self.assertEqual(payload["writing"]["lang"], "en")
        self.assertEqual(payload["writing"]["words"], [315, 385])
        self.assertEqual(payload["image"]["request"]["size"], "1024x576")
        self.assertNotIn("Erstelle danach", payload["writing"]["instruction"])

    def test_single_image_and_references(self):
        self.assertIsNone(plan("Bitte kein Bild erstellen."))
        self.assertIsNone(plan("Ich möchte keine Geschichte schreiben."))
        self.assertIsNone(plan("Wie erstelle ich ein Bild?"))
        self.assertIsNone(plan("Erkläre mir, was heute ansteht."))
        self.assertTrue(plan("Erstelle eine Variante des vorherigen Bildes.")["image"]["variant"])
        self.assertEqual(plan("Create an image of a boat and save it in the project Light.")["project_name"], "Light")
        self.assertNotIn("writing", plan("Erstelle ein Cover für die Geschichte."))
        self.assertNotIn("writing", plan("Ich möchte ein passendes Bild zu meiner Geschichte."))

    def test_word_count_and_real_language_markers(self):
        self.assertEqual(word_bounds("genau 350 Wörter"), [350, 350])
        self.assertEqual(word_bounds("300 bis 350 Wörtern"), [300, 350])
        self.assertEqual(word_bounds("unter 250 Wörter"), [1, 249])
        self.assertEqual(word_bounds("A 350-word story"), [315, 385])
        req = {"lang": "en", "words": [9, 14]}
        self.assertEqual(check_text("# Das letzte Licht\n\n" + EN, req, TEXT)["issues"], [])
        self.assertIn("language_mismatch", check_text(DE, req, TEXT)["issues"])
        self.assertIn("word_count_mismatch", check_text(EN, {**req, "words": [50, 60]}, TEXT)["issues"])
        with self.assertRaisesRegex(PlanError, "word_range_unsupported"):
            word_bounds("ungefähr 30000 Wörter")

    def test_rewrite_revalidates_and_only_audits_accepted_prose(self):
        worker = studio["write_task"]
        evidence = {"skill_version": "fixture", "rules": []}
        stages = {}
        def stage(_id, result, key, **value):
            result["steps"][key] = value
        overrides = {
            "model_reply": lambda *args: (outputs.pop(0), evidence, "stop"),
            "task_step": stage, "writing_context": lambda *args: "", "task_source": lambda *args: "",
            "style_audit": lambda text, lang, genre: {"skill_version": "fixture", "findings": []},
        }
        data = plan("Schreibe eine englische Geschichte.", default="de")
        outputs = [DE, EN]
        with patch.dict(worker.__globals__, overrides):
            self.assertEqual(worker("test", data, {"session_id": "test"}, {"steps": stages}), EN)
        self.assertEqual(stages["writing"]["status"], "completed")
        checks = stages["writing"]["diagnostics"]
        self.assertEqual([c["validation"]["language"] for c in checks], ["de", "en"])
        self.assertIn("language_mismatch", checks[0]["validation"]["issues"])
        outputs = [DE, DE, DE]
        with patch.dict(worker.__globals__, overrides):
            self.assertIsNone(worker("test", data, {"session_id": "test"}, {"steps": stages}))
        self.assertEqual(stages["writing"]["status"], "failed")
        self.assertEqual(len(stages["writing"]["diagnostics"]), 3)

    def test_png_dimensions_are_required_before_success(self):
        import zlib
        verify = studio["verify_image_file"]
        image_id = "a" * 32
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

        header = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1024, 576, 8, 0, 0, 0, 0))
        png = header + chunk(b"IDAT", zlib.compress(bytes(1025 * 576))) + chunk(b"IEND", b"")
        contents = png
        with patch.dict(verify.__globals__, {
            "http_json": lambda *args, **kw: (200, {"id": image_id, "request": {"size": "1024x576"}}),
            "open_upstream": lambda *args, **kw: io.BytesIO(contents),
        }):
            self.assertEqual(verify(image_id, "1024x576"), [1024, 576])
            with self.assertRaisesRegex(PlanError, "image_dimensions_mismatch"):
                verify(image_id, "1024x1024")
            for contents in (png[:-12], png[:-1] + bytes([png[-1] ^ 1])):
                with self.assertRaisesRegex(PlanError, "image_invalid_png"):
                    verify(image_id, "1024x576")

    def test_editorial_preserves_protected_fragments_and_browser_offsets(self):
        self.assertEqual(studio["editorial_range"]("a🪶bc", [1, 4]), (1, 3))
        with self.assertRaisesRegex(PlanError, "editorial_range_invalid"):
            studio["editorial_range"]("a🪶bc", [2, 4])
        source = "# Report\n\nIn 1943 the *Marella* sailed. [Note](https://example.com)."
        self.assertTrue(studio["editorial_integrity"](source, source.replace("sailed", "left"), True))
        for protected in ("1943", "Marella", "https://example.com"):
            self.assertFalse(studio["editorial_integrity"](source, source.replace(protected, "changed"), True))

    def test_editorial_quotes_and_independent_paragraphs(self):
        source = "She held the lantern close.\n\nThe fog pressed against the shutters."
        edited = "She held the lantern high.\n\nThe fog leaned against the shutters."
        _, _, choices = studio["editorial_choices"](source, edited)
        self.assertEqual([choice["paragraph"] for choice in choices], [1, 2])
        _, _, choices = studio["editorial_choices"](source, edited.replace("\n\n", " "))
        self.assertEqual(choices, [])
        audit = studio["editorial_records"]([
            {"paragraph": 2, "quote": "A translated quote", "note": "Fidelity"},
            {"paragraph": 90, "quote": "A fabricated quote", "note": "Fidelity"},
        ], source, ("note",))
        self.assertEqual(audit, [{"line": 3, "quote": "The fog pressed against the shutters.",
                                  "anchor": "paragraph", "note": "Fidelity"}])


if __name__ == "__main__":
    unittest.main()
