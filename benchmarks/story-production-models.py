#!/usr/bin/env python3
"""Compare two explicitly chosen llama.cpp aliases on existing DE/EN story material."""

import argparse
import hashlib
import json
import os
import runpy
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_production as production
import creative_studio_story as story


def sources(database):
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        english = conn.execute("""SELECT d.body FROM documents d JOIN projects p ON p.id=d.project_id
            WHERE p.name LIKE 'The Missing Sundays%' AND d.story_number=1 AND length(d.body)>0
            ORDER BY d.updated DESC LIMIT 1""").fetchone()
        german = conn.execute("""SELECT d.body FROM documents d JOIN projects p ON p.id=d.project_id
            WHERE p.name='Das letzte Licht' AND d.lang='de' AND length(d.body)>500
            ORDER BY length(d.body) DESC LIMIT 1""").fetchone()
    if not english or not german:
        raise ValueError("Required local story samples not found")
    return {"en": english[0], "de": german[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path, help="Isolated Studio state for the benchmark.")
    parser.add_argument("aliases", nargs=2, metavar="ALIAS")
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(XDG_CONFIG_HOME=str(scratch / "config"), XDG_DATA_HOME=str(scratch / "data"))
    backend = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
    backend["migrate"]()
    official = backend["production_models"]
    _, available = official()
    if any(alias not in available for alias in args.aliases):
        parser.error("Both aliases must be available on the local router.")
    cases = sources(args.source_db)
    report = []
    for alias in args.aliases:
        backend["production_models"] = lambda: ({role: alias for role in ("plan", "write", "audit", "rewrite")}, official()[1])
        for lang, body in cases.items():
            prompt = ("Continue the narrative or develop the story premise below as a self-contained scene in the requested language. "
                      "Use 130–220 words. Keep named characters and established facts. Give the protagonist a concrete decision. "
                      "Return only prose.\n\n" + body)
            for kind in ("write", "audit"):
                while True:
                    try:
                        start = time.monotonic()
                        if kind == "write":
                            text, proof, finish = backend["production_model"](lang, kind, prompt, 600)
                            issues = backend["production_skill"]()[0].audit({"excerpt": text}, lang)["findings"]
                            row = {"text": text, "words": story.count_words(text), "findings": issues, "finish_reason": finish,
                                   "evidence": proof}
                        else:
                            row = backend["production_worker"].audit_window(lang, body, "Review only the supplied story source.", 1)
                        break
                    except production.WaitForResource:
                        time.sleep(8)
                row.update(alias=alias, language=lang, kind=kind, seconds=round(time.monotonic() - start, 2),
                           source_sha256=hashlib.sha256(body.encode()).hexdigest())
                report.append(row)
                prefix = scratch / "model-comparison.json"
                prefix.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(alias, lang, kind, row["seconds"], flush=True)


if __name__ == "__main__":
    main()
