#!/usr/bin/env python3
"""Long-form data contract and repeat detection. The real model run is separate."""

import json
import runpy
import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_story as story

Fixture = runpy.run_path(str(ROOT / "tests/creative-studio-organizer.py"))["StudioFixture"]


class StoryTests(unittest.TestCase):
    def test_sections_and_repeat_detection(self):
        self.assertEqual(story.sections(330, 1000, 1500), 1)
        self.assertEqual(story.sections(0, 1000, 1500), 2)
        self.assertGreater(story.sections(0, 3500, 4200), 5)
        self.assertEqual(story.section_bounds(568, 1000, 1500, 1), (432, 932, 682))
        repeated = "With one hand Elara held the wet rail while the boat moved past the shoal."
        self.assertEqual(story.repeats(repeated + " The bell rang again.", repeated), [repeated])
        self.assertEqual(story.trim_echo(repeated + "\n\nThe bell rang again.", repeated), "The bell rang again.")
        self.assertRegex("Three hundred words earlier she had seen the ship.", story.PRODUCTION_ASIDE)
        self.assertNotRegex("Three hundred years earlier the ship had sunk.", story.PRODUCTION_ASIDE)
        self.assertEqual(story.count_words("# Title\nElara's lamp.\n\n![Picture caption](/image.png)"), 2)

    def test_chapter_plan_versions_and_release(self):
        with Fixture() as fixture:
            origin = fixture.req("/projects", {"name": "A lighthouse", "kind": "novel", "lang": "en"})["id"]
            source = fixture.req("/documents", {"project_id": origin, "title": "Opening", "body": "The lamp turned."})["id"]
            path = "/stories/" + origin
            fixture.req(path + "/settings", {"lang": "en", "opening": source, "bible": {"timeline": "Night."}})
            chapter_ids = [
                fixture.req(path + "/plan", {"title": f"Chapter {index}", "plan": "The keeper makes a decision."})["id"]
                for index in range(1, 12)
            ]
            data = fixture.req(path)
            self.assertEqual([row["number"] for row in data["chapters"]], list(range(1, 12)))
            self.assertEqual(data["settings"]["opening"], source)
            self.assertEqual(data["bible"], {"timeline": "Night."})
            self.assertEqual({(row["minimum"], row["maximum"]) for row in data["chapters"]}, {(1000, 1500)})
            chapter = chapter_ids[0]
            fixture.req(path + "/edit-plan", {"document_id": chapter, "minimum": 3500, "maximum": 4200})
            first = fixture.req("/documents/" + chapter, {"body": "Elara listened.", "version": 1})
            self.assertEqual(first["status"], "draft")
            fixture.req(path + "/status", {"document_id": chapter, "version": first["version"], "status": "approved"})
            for target, body in (
                ("/documents/" + chapter, {"body": "Changed."}),
                (path + "/generate", {"document_id": chapter, "replace_draft": True, "version": first["version"]}),
            ):
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    fixture.req(target, body)
                with exc.exception as response:
                    self.assertEqual(response.code, 409)
                    self.assertEqual(json.load(response)["error"], "story_approved")
            fixture.req(path + "/status", {"document_id": chapter, "version": first["version"], "status": "draft"})
            version = fixture.req("/documents/" + chapter, {"body": "Elara waited.", "version": first["version"]})["version"]
            self.assertEqual(version, 3)
            self.assertEqual(fixture.req("/documents/" + chapter + "/versions")[0]["version"], 2)
            self.assertEqual(fixture.req("/documents/" + source)["body"], "The lamp turned.")
            targets = fixture.req(path)["chapters"][0]
            self.assertEqual((targets["minimum"], targets["maximum"]), (3500, 4200))

if __name__ == "__main__":
    unittest.main()
