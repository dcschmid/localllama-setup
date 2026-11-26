#!/usr/bin/env python3
"""Migrate Open WebUI's custom-model table to the two-role Creative Studio.

Creative Studio production surface = exactly two router roles:
  research-code  -> "Research & Analysis 256K" (Gemma 4 26B-A4B QAT HauhauCS)
  story          -> "Creative Writing DE/EN 256K" (UltimateIntent Gemory)

Router aliases (research, deep-research, creative-writing, human-*, coding-*)
stay in models.ini as the compatibility layer for Studio, Pi and starter
scripts; this script never edits models.ini. It only repairs Open WebUI's
`model` table so no user-created model points at a retired GGUF:

  1. back up webui.db (sqlite3 .backup -> ~/restore/owui-<ts>/webui.db)
  2. repoint base_model_id of every custom model from retired bases to the
     matching live role (hemmingway/* -> story, research* -> research-code)
  3. deactivate custom models whose base_model_id names a retired profile
     that has no live replacement (legacy coding models, small ollama helpers
     are left untouched - they were never part of the two GGUF migration)

Idempotent: a second run reports 0 changes. External models (yolo-auto,
ollama tags) are NOT touched - they are independent of the GGUF migration.
Dry-run with --dry-run; exit 0 on success (including "nothing to do").
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

DB = Path.home() / ".local/share/open-webui/webui.db"
LIVE_BASES = {"story", "research-code", "research", "creative-writing",
              "human-writing", "human-rewrite", "human-audit", "deep-research",
              "coding-long-256k"}  # router aliases that still resolve in models.ini
RETIRED_TO_LIVE = {
    "hemmingway": "story",
    "hemmingway15": "story",
    "story-12b": "story",
    "research": "research-code",
    "creative-writing": "story",
    "human-writing": "story",
}
EXTERNAL_HINTS = (":", ".")  # ollama tags / hub ids are not our GGUFs


def is_ollama_or_hub(base: str) -> bool:
    return any(h in base for h in EXTERNAL_HINTS) and base not in LIVE_BASES


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not DB.exists():
        print(f"missing {DB}", file=sys.stderr)
        return 1

    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = Path.home() / f"restore/owui-{ts}"
    if not args.dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(backup_dir / "webui.db")
        with dst:
            src.backup(dst)  # consistent snapshot incl. WAL, no CLI needed
        src.close()
        dst.close()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    changes: list[str] = []

    for row in con.execute("select id, name, base_model_id, is_active from model").fetchall():
        base = row["base_model_id"] or ""
        if not base or base in {"story", "research-code"}:
            continue  # already a production role or a standalone entry
        if is_ollama_or_hub(base):
            continue  # external models stay
        if base in RETIRED_TO_LIVE:
            new = RETIRED_TO_LIVE[base]
            changes.append(f"repoint {row['id']} ({row['name']}): {base} -> {new}")
            if not args.dry_run:
                con.execute("update model set base_model_id=?, updated_at=? where id=?",
                            (new, int(time.time()), row["id"]))
        elif base not in LIVE_BASES:
            changes.append(f"retire {row['id']} ({row['name']}): dead base {base}")
            if not args.dry_run:
                con.execute("update model set is_active='0', updated_at=? where id=?",
                            (int(time.time()), row["id"]))

    # register the two Creative Studio production roles as labeled OWUI
    # models on the live router aliases (router keeps serving the raw aliases
    # for Studio/Pi; these give the picker its two clear names)
    admin = con.execute("select user_id from model where user_id is not null limit 1")
    admin_user = admin.fetchone()[0] if admin else None
    for model_id, base, label, desc in (
        ("creative-studio-research", "research-code", "Research & Analysis 256K",
         "Deep Research, Quellenanalyse, Faktenpruefung, Story-Bibeln (Gemma 4 26B-A4B QAT, 262144 ctx)"),
        ("creative-studio-story", "story", "Creative Writing DE/EN 256K",
         "Storytelling, Romane, Artikel, Human Writing DE+EN (UltimateIntent Gemory, 262144 ctx)"),
    ):
        row = con.execute("select id from model where id=?", (model_id,)).fetchone()
        if row:
            changes.append(f"role {model_id} already registered")
            continue
        if admin_user is None:
            changes.append(f"skip {model_id}: no user_id in model table")
            continue
        changes.append(f"register {model_id} -> {base} ({label})")
        if not args.dry_run:
            con.execute(
                "insert into model (id,user_id,base_model_id,name,params,meta,updated_at,created_at,is_active,version_id)"
                " values (?,?,?,?,?,?,?,?,?,?)",
                (model_id, admin_user, base, label, "{}",
                 json.dumps({"profile_image_url": None, "background_image_url": None,
                             "description": desc, "i18n": None, "capabilities": None,
                             "knowledge": None, "voice": None, "voice_avatar": None}),
                 int(time.time()), int(time.time()), "1", model_id))

    if not args.dry_run:
        con.commit()
    con.close()
    print(json.dumps({"backup": str(backup_dir) if not args.dry_run else None,
                      "changes": changes}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
