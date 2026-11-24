#!/usr/bin/env python3
"""Validate the two-model production profile without touching the router.

Checks the rendered router preset against the pinned manifest and the files
on disk: every production profile pins 262144/8192/fit=off, the two weights
exist, and their SHA-256 matches packages/models.tsv. Exit 0 = PASS.
"""

import configparser
import hashlib
import json
import sys
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[1]
INI = HOME / ".config/llama.cpp/models.ini"
TSV = REPO / "packages/models.tsv"
MODELS = HOME / "models/gguf"
PRODUCTION = ("research-code", "story")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failures: list[str] = []
    parser = configparser.ConfigParser()
    # the router preset carries a bare "version = 1" header before the first
    # section; configparser needs every key inside a section
    parser.read_string("[__header__]\n" + INI.read_text())

    pinned: dict[str, tuple[str, str]] = {}
    for row in TSV.read_text().splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) >= 5:
            pinned[cols[0]] = (cols[1], cols[4])  # filename -> (repo, sha256)

    if set(pinned) != {"Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf",
                       "Gemory-26B-A4B-Q4_K_M.gguf"}:
        failures.append(f"models.tsv must pin exactly the two production weights, got {sorted(pinned)}")

    for profile in parser.sections():
        if profile in ("*", "__header__"):
            continue
        row = parser[profile]
        for key, want in (("ctx-size", "262144"), ("n-predict", "8192"), ("fit", "off")):
            got = row.get(key)
            if got != want:
                failures.append(f"[{profile}] {key} = {got!r}, want {want}")
        target = row.get("model", "")
        if Path(target).parent != MODELS:
            failures.append(f"[{profile}] model outside ~/models/gguf: {target}")

    for profile in PRODUCTION:
        path = Path(parser[profile]["model"])
        if not path.is_file():
            failures.append(f"[{profile}] weight missing: {path}")
            continue
        name, repo, sha = path.name, *pinned[path.name]
        actual = sha256(path)
        if actual != sha:
            failures.append(f"{name}: sha256 {actual} != pinned {sha}")

    report = {"profiles_checked": len([s for s in parser.sections() if s not in ("*", "__header__")]),
              "production": list(PRODUCTION), "failures": failures,
              "verdict": "PASS" if not failures else "BLOCKED"}
    print(json.dumps(report, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
