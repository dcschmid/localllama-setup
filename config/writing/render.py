#!/usr/bin/env python3
"""Compile a llama.cpp writing template from the local skill checkout."""

import json
import os
import re
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent


def skill_root():
    if root := os.environ.get("LLAMA_SETUP_SKILLS"):
        return Path(root).expanduser() / "human-writing"
    config = CONFIG / "mcp.json"
    if config.is_file():
        skills = json.loads(config.read_text(encoding="utf-8"))["mcpServers"].get("skills")
        if skills:
            return Path(skills["args"][-1]) / "human-writing"
    return Path.home() / "dev/github/skillset/skills/human-writing"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"The base template changed near {old!r}")
    return text.replace(old, new, 1)


def render(skill):
    refs = (
        "style-en", "style-de", "quality-gates", "fidelity-rules", "patterns-core",
        "website-audit", "website-rewrite", "website-voice", "seo-content",
        "accessibility-content", "voice-calibration",
    )
    docs = {
        name: (skill / "references" / f"{name}.md").read_text(encoding="utf-8").strip()
        for name in refs
    }
    docs["skill"] = (skill / "SKILL.md").read_text(encoding="utf-8").strip()
    docs["voice-profile"] = (skill / "assets/voice-profile.template.md").read_text(encoding="utf-8").strip()
    docs["genre-fiction"] = (skill / "references/creative-writing.md").read_text(encoding="utf-8").strip()
    genres = (skill / "references/genre-guides.md").read_text(encoding="utf-8")
    for genre, heading in (
        ("technical", "Technical documentation"), ("business", "Business communication"),
        ("editorial", "Editorial"), ("marketing", "Marketing"), ("ux", "UX writing"),
    ):
        section = next((part for part in re.split(r"(?m)(?=^## )", genres)
                        if part.startswith(f"## {heading}")), None)
        if not section:
            raise ValueError(f"Genre section missing: {heading}")
        docs[f"genre-{genre}"] = section.strip()

    prelude = "{%- set hw_docs = " + json.dumps(docs, ensure_ascii=False) + " -%}\n"
    routing = (HERE / "routing.jinja").read_text(encoding="utf-8")
    native = (HERE / "gemma4-base.jinja").read_text(encoding="utf-8")
    native = replace_once(
        native,
        "{%- if (enable_thinking is defined and enable_thinking) or tools or messages[0]['role'] in ['system', 'developer'] -%}",
        "{%- if hw_context or (enable_thinking is defined and enable_thinking) or tools or messages[0]['role'] in ['system', 'developer'] -%}",
    )
    system = "    {%- if messages[0]['role'] in ['system', 'developer'] -%}"
    native = replace_once(native, system, "    {{- hw_context | trim + '\\n\\n' -}}\n" + system)
    return prelude + routing + native


def main():
    target = Path.home() / ".cache/llama.cpp/writing/gemma4-human-writing.jinja"
    try:
        compiled = render(skill_root())
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") == compiled:
            return
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as staged:
            try:
                staged.write(compiled)
                staged.close()
                os.replace(staged.name, target)
            finally:
                Path(staged.name).unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Human Writing template: {exc}") from exc


if __name__ == "__main__":
    main()
