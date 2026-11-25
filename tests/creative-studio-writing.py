#!/usr/bin/env python3
"""Writing resolver, patch invariants and the persisted article job entry point."""

import json
import os
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
import creative_studio_article as article
import creative_studio_chat as chats
import creative_studio_correction as correction
import creative_studio_skills as skills

URL = "https://docs.python.org/3/library/json.html"
EXTRACT = "The json module exposes dump and dumps. The dumps function serializes an object to a JSON formatted string."
ENGLISH = "The documentation includes two interfaces. The result is a JSON formatted string., but the object stays available."
GERMAN = "Das Modul liefert eine Zeichenkette., aber das ursprüngliche Objekt bleibt erhalten."
TECHNICAL = """---
title: "JSON with Python"
lang: en
---
# Calling dumps

The result is a JSON formatted string., but the object stays available.

[Python documentation](https://docs.python.org/3/library/json.html)

![An intact alt text](images/example.png)

```python
import json
print(json.dumps({"key": 3}))
```

| Name | Meaning |
| --- | --- |
| dumps | serialization |
"""


class WritingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        scoped = patch.dict(os.environ, {k: self.directory.name for k in
                            ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME")})
        scoped.start()
        self.addCleanup(scoped.stop)
        self.studio = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
        self.studio["migrate"]()
        self.conn = self.studio["db"]()
        self.addCleanup(self.close_database)
        self.fiction, self.language_tools = self.studio["production_skill"]()

    def close_database(self):
        self.studio["db"]().close()

    def test_intent_routes_before_subject_and_research_words(self):
        self.assertEqual(chats.requested_action(
            "Schreibe einen recherchierten Artikel über die Geschichte des Heavy Metal.", "auto"), "article")
        self.assertEqual(chats.requested_action("Plan a story with eight chapters.", "auto"), "outline")
        self.assertEqual(chats.outline_count("Schreibe eine Mystery-Geschichte mit acht Kapiteln."), 8)
        self.assertEqual(skills.document_domain("doc"), "general")

    def test_only_selected_rules_reach_router_and_are_hashed(self):
        studio = self.studio
        received = []

        def router(url, method="GET", body=None, **_kwargs):
            if url.endswith("/v1/models"):
                return 200, {"data": [{"id": "creative-writing", "status": {"args": ["--ctx-size", "8192"]}},
                                      {"id": "research", "status": {"args": ["--ctx-size", "8192"]}}]}
            if url.endswith("/health"):
                return 200, {"busy": False}
            if url.endswith("/apply-template"):
                return 200, {"prompt": "\n".join("<|turn>" + m["role"] + "\n" + m["content"] for m in body["messages"])}
            if url.endswith("/tokenize"):
                return 200, {"tokens": list(range(400))}
            if url.endswith("/v1/chat/completions"):
                received.append(body)
                return 200, {"choices": [{"message": {"content": "Result"}}]}
            raise AssertionError(url)

        studio["http_json"] = router
        _, story_proof, _ = studio["production_model"]("de", "write", "A scene", 900)
        _, article_proof, _ = studio["article_model"]("en", "audit", "A fact check", 900)
        _, human_proof, _ = studio["production_model"]("de", "human-audit", "Language check", 900)
        self.assertEqual([p["name"] for p in story_proof["skills"]], ["human-writing", "story-writing"])
        self.assertEqual([p["name"] for p in article_proof["skills"]], ["article-writing"])
        self.assertEqual([p["name"] for p in human_proof["skills"]], ["human-writing"])
        story_prompt, article_prompt, human_prompt = [r["messages"][0]["content"] for r in received]
        self.assertIn("# Chapter writing", story_prompt)
        self.assertEqual(story_prompt.count("# Chapter writing"), 1)
        self.assertNotIn("# Article Writing", story_prompt)
        self.assertIn("# Fact checking", article_prompt)
        self.assertNotIn("# Story Writing", article_prompt)
        self.assertNotIn("Grammar in context", human_prompt)
        self.assertIn("Prüfe Kasus", human_prompt)
        self.assertEqual([r["model"] for r in received], ["creative-writing", "research", "research"])
        with self.assertRaisesRegex(ValueError, "writing_skill_missing:story-writing"):
            skills.resolve(Path(self.directory.name), "de", "story", "audit", lane="domain")

    def test_fiction_canon_and_patch_fidelity(self):
        for text, language in ((ENGLISH, "en"), (GERMAN, "de")):
            with self.subTest(language=language):
                _, edits = self.fiction.local_quality(text)
                revised = correction.patch_text(text, edits, [], self.fiction, local=True,
                                                 base_hash=correction.digest(text))
                self.assertEqual(revised, text.replace(".,", ","))
                self.assertEqual(self.fiction.local_quality(revised)[1], [])
                with self.assertRaisesRegex(ValueError, "stale"):
                    correction.patch_text(revised, edits, [], self.fiction, local=True,
                                          base_hash=correction.digest(text))
        for text, fragment, replacement, canon in [
            ("The compartment held four badges.", "four badges", "three badges", "Exactly three badges had been issued."),
            ("Am Schrank klebte ein roter Punkt.", "roter Punkt", "rotes Kreuz", "Am Schrank klebte ein rotes Kreuz."),
        ]:
            start = text.index(fragment)
            target = {"start": start, "end": start + len(fragment), "category": "continuity",
                      "status": "confirmed", "related_quote": canon}
            edits = [{"before": fragment, "after": replacement}]
            self.assertEqual(correction.patch_text(text, edits, [], self.fiction, targets=[target], canon=canon),
                             text.replace(fragment, replacement))
            if fragment.startswith("four"):
                with self.assertRaisesRegex(ValueError, "invalid"):
                    correction.patch_text(text, edits, [], self.fiction, targets=[target], article=True)

    def test_story_evidence_needs_two_passages(self):
        cases = (
            ("Nadia knew how to open the box.", "Nadia does not learn the code until Chapter 6."),
            ("Using the compass, the driver found north.", "The driver left the compass with the survey crew."),
            ("Das Boot lag schon im Hafen.", "Der Anleger ist erst am nächsten Morgen erreichbar."),
        )
        for text, related in cases:
            raw = [{"chapter": "1", "quote": text, "related_quote": related, "category": "continuity",
                    "severity": "blocking", "issue": "The opening state contradicts the timeline.",
                    "correction": "Restore the established state at this point."}]
            self.assertTrue(self.fiction.qualify_findings(raw, {"1": text}, related)[0]["confirmation_eligible"])
            self.assertFalse(self.fiction.qualify_findings(raw, {"1": text}, "")[0]["confirmation_eligible"])

    def test_python_syntax_checks_never_execute_examples(self):
        ready = article.publishing_checks(TECHNICAL)
        self.assertEqual([check["verdict"] for check in ready], ["editorial"])
        damaged = TECHNICAL.replace('print(json.dumps({"key": 3}))', 'print(')
        self.assertEqual(article.publishing_checks(damaged)[0]["verdict"], "unsupported")
        self.assertEqual(article.publishing_checks("---\ntitle: unfinished")[0]["verdict"], "unsupported")

    def test_factual_changes_and_markup_are_protected(self):
        for before, after in [("3", "4"), ("An intact alt text", "Changed caption"),
                              ("images/example.png", "images/missing.png"), ("Calling dumps", "Breaking dumps")]:
            with self.subTest(before=before), self.assertRaisesRegex(ValueError, "patch_invalid"):
                correction.patch_text(TECHNICAL, [{"before": before, "after": after}], [], self.fiction, article=True)

    def dispatch_direct(self, text, language, instruction, claim=None, supported=True):
        sid, pid, task = (uuid.uuid4().hex for _ in range(3))
        studio = self.studio
        with self.conn:
            self.conn.execute("INSERT INTO projects(id,name,kind,lang) VALUES(?,'Test','article',?)", (pid, language))
            self.conn.execute("INSERT INTO sessions(id,project_id) VALUES(?,?)", (sid, pid))
            dossier_id = studio["save_document"](self.conn, pid, "Test dossier", f"[Python]({URL})\n\n> {EXTRACT}",
                                                "dossier", "en")
            payload = {"session_id": sid, "project_id": pid, "document_id": dossier_id,
                       "chat_first": True, "plan": {"writing": {"instruction": instruction, "lang": language,
                       "kind": "article", "words": None}, "title": ""}}
            result = {"steps": {key: {"status": "pending"} for key in ("project", "writing", "document")}}
            self.conn.execute("INSERT INTO jobs(id,service,state,payload,result,created,updated) "
                "VALUES(?,'chat_task','queued',?,?,?,?)", (task, json.dumps(payload), json.dumps(result), time.time(), time.time()))

        def fake(lang, role, prompt, tokens, schema=None):
            proof = {"alias": "stub", "role": role}
            if role == "write":
                return text, proof, "stop"
            fields = schema["properties"]
            if role == "plan":
                answer = {key: "Structured article plan" for key in fields}
            elif "claims" in fields:
                revised_quote = claim and claim.replace(".,", ",")
                quote = claim if claim and claim in prompt.split("\nPASSAGE\n")[-1] else revised_quote
                answer = {"claims": [] if quote is None else [{"quote": quote, "verdict": "supported",
                    "source_id": "AUTHOR" if "personal" in instruction else "S1",
                    "source_quote": ("I grouped successive list items" if "personal" in instruction
                                     else EXTRACT if supported else "Nonexistent source text."), "reason": "Claim in source."}]}
            elif "verdicts" in fields:
                answer = {"verdicts": [{"index": "0", "status": "supported",
                                       "reason": "The source explicitly describes serialization to a string."}]}
            elif "findings" in fields:
                answer = {"findings": []}
            else:
                raise AssertionError((role, fields))
            return json.dumps(answer), proof, "stop"

        studio["article_worker"].call = fake
        for step in range(20):
            row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (task,)).fetchone()
            if row["state"] == "completed":
                break
            studio["advance_task"](row)
            if step == 3:
                self.conn.close()
                del studio["_dbs"].conn
                self.conn = studio["db"]()
        else:
            self.fail("Article job did not complete")
        saved = json.loads(row["result"])
        document = self.conn.execute("SELECT * FROM documents WHERE id=?", (saved["document_id"],)).fetchone()
        return saved["article"], document

    def test_researched_article_keeps_original_and_verifies_candidate(self):
        claim = "The result is a JSON formatted string"
        job, doc = self.dispatch_direct(ENGLISH, "en", "Write a researched article using the dossier, offline.", claim)
        self.assertEqual(job["publishing"], "ready")
        self.assertEqual(job["corrections"], 1)
        self.assertEqual(doc["body"], ENGLISH.replace(".,", ","))
        self.assertEqual(doc["version"], 2)
        self.assertEqual(job["review"]["fact"]["claims"][0]["source_url"], URL)
        original = self.conn.execute("SELECT body FROM doc_versions WHERE document_id=? AND version=1", (doc["id"],)).fetchone()
        self.assertEqual(original["body"], ENGLISH)

    def test_technical_article_preserves_markdown_and_unresolved_claim(self):
        job, doc = self.dispatch_direct(TECHNICAL, "en", "Write a researched technical article using the dossier, offline.",
                                        "The result is a JSON formatted string", supported=False)
        self.assertEqual(job["publishing"], "needs_review")
        self.assertEqual(job["review"]["fact"]["claims"][0]["verdict"], "unsupported")
        self.assertEqual(doc["status"], "draft")
        self.assertEqual([m[0] for m in correction.markup(doc["body"])],
                         [m[0] for m in correction.markup(TECHNICAL)])

    def test_existing_frontmatter_is_not_wrapped_by_export(self):
        _, doc = self.dispatch_direct(TECHNICAL, "en", "Write a technical article using a dossier, offline.",
                                     "The result is a JSON formatted string")
        handler_class = self.studio["Handler"]
        handler = handler_class.__new__(handler_class)
        handler._json = lambda value, status=200: (status, value)
        for fmt in ("md", "mdx"):
            status, result = handler._export({"doc_id": doc["id"], "format": fmt})
            self.assertEqual(status, 200)
            self.assertTrue(result["files"][0]["path"].endswith("." + fmt))
            self.assertEqual(result["files"][0]["content"], doc["body"])
            self.assertEqual(result["files"][0]["content"].splitlines().count("---"), 2)

    def test_personal_example_uses_only_supplied_experience(self):
        text = "I grouped successive list items. The revised output showed them together."
        job, doc = self.dispatch_direct(text, "en", "Write a fictional personal account. I grouped successive list items.",
                                        "I grouped successive list items")
        self.assertEqual(doc["body"], text)
        self.assertEqual(job["publishing"], "ready")
        self.assertEqual(job["review"]["fact"]["claims"][0]["source_id"], "AUTHOR")
        self.assertEqual(doc["version"], 1)


if __name__ == "__main__":
    unittest.main()
