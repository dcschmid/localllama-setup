#!/usr/bin/env python3
"""Run a paused chapter through the real local quality gates on a disposable SQLite copy."""

import argparse
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_production as production


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="Source database opened read-only.")
    parser.add_argument("job")
    parser.add_argument("report", type=Path)
    parser.add_argument("--audit-alias", default="research")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="studio-real-quality-") as scratch:
        root = Path(scratch)
        os.environ.update(XDG_DATA_HOME=str(root / "data"), XDG_CONFIG_HOME=str(root / "config"))
        database = root / "data/creative-studio/studio.sqlite3"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(database) as copy:
            original.backup(copy)
        config = root / "config/creative-studio"
        config.mkdir(parents=True)
        (config / "story-model-roles.json").write_text(json.dumps({"audit": args.audit_alias}), encoding="utf-8")
        runtime = runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"].__globals__
        conn = runtime["db"]()
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND service='production' AND state='paused'", (args.job,)).fetchone()
        if not row:
            parser.error("Select a paused production job.")
        data, checkpoint = json.loads(row["payload"]), json.loads(row["result"])
        source = production.story.managed_chapter(conn, data["project_id"], checkpoint["current"]["document_id"])
        with conn:
            production.mutate(conn, data["project_id"], "resume", {"job_id": args.job},
                              runtime["save_document"], runtime["store_message"])
        deadline = time.monotonic() + 900
        while True:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (args.job,)).fetchone()
            result = json.loads(row["result"])
            if row["state"] in ("paused", "failed", "completed") or result["step"] == "illustrating":
                break
            if time.monotonic() >= deadline:
                break
            if not runtime["production_worker"].tick():
                time.sleep(5)
        saved = production.story.managed_chapter(conn, data["project_id"], source["id"])
        report = {"state": row["state"], "step": result["step"], "result": result, "saved_version": saved["version"],
                  "source_version": source["version"],
                  "chapter_documents": len(production.managed_docs(conn, data["project_id"])),
                  "images_enqueued": conn.execute("SELECT count(*) FROM jobs WHERE service='image'").fetchone()[0]}
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(row["state"], result["step"], f"v{source['version']} -> v{saved['version']}")
        conn.close()
        return 0 if result["step"] == "illustrating" else 2


if __name__ == "__main__":
    raise SystemExit(main())
