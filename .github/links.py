#!/usr/bin/env python3
"""Markdown relative link checker for repository docs."""
import re
import sys
from pathlib import Path

bad = []
root = Path(__file__).resolve().parents[1]
for md in sorted(root.rglob("*.md")):
    if ".git" in md.parts or "__pycache__" in md.parts:
        continue
    for match in re.finditer(r"\[[^\]]*\]\(([^)#][^)]*)\)", md.read_text(encoding="utf-8")):
        target = match.group(1).split("#")[0].strip()
        if not target or target.startswith(("http", "mailto:")):
            continue
        resolved = (md.parent / target).resolve()
        if not resolved.exists():
            bad.append(f"{md.relative_to(root)} -> {target}")
for line in bad:
    print("broken:", line)
sys.exit(1 if bad else 0)
