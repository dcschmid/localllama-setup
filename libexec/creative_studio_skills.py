"""Task and phase selection for local writing instructions."""

import hashlib
import re
from dataclasses import dataclass

from creative_studio_plan import PlanError

HUMAN = "human-writing"
STORY = "story-writing"
ARTICLE = "article-writing"

PROFILES = {
    "story": {
        "plan": ("story-planning", "story-bible"),
        "generate": ("chapter-writing", "narrative-pacing", "dialogue"),
        "audit": ("continuity", "story-quality"),
        "rewrite": ("continuity", "revision-workflow"),
        "whole": ("story-quality", "continuity", "character-development"),
        "image": (),
    },
    "article": {
        "plan": ("article-planning", "research-integrity"),
        "generate": ("article-structure", "research-integrity"),
        "audit": ("fact-checking", "research-integrity", "editorial-quality"),
        "rewrite": ("article-revision", "publishing"),
    },
}
VERSION = re.compile(r"""(?m)^\s+version:\s*['"]?([0-9]+\.[0-9]+\.[0-9]+(?:[-+][\w.-]+)?)['"]?\s*$""")


@dataclass(frozen=True)
class SkillContext:
    rules: dict
    versions: dict

    def evidence(self):
        return [{"name": name, "version": version,
                 "rules": [{"reference": key.split("/", 1)[1], "sha256": hashlib.sha256(value.encode()).hexdigest()}
                           for key, value in self.rules.items() if key.startswith(name + "/")]}
                for name, version in self.versions.items()]


def document_domain(kind, request=""):
    if kind in ("story", "novel", "chapter"):
        return "story"
    if kind in ("article", "devlog", "dossier"):
        return "article"
    if re.search(r"\b(?:article|artikel|devlog|blogpost|blog post)\b", request, re.I):
        return "article"
    if re.search(r"\b(?:novel|fiction|story|roman|geschichte|chapter|kapitel)\b", request, re.I):
        return "story"
    return "general"


def resolve(root, language, domain, phase, *, lane="combined"):
    if language not in ("de", "en") or domain not in (*PROFILES, "general"):
        raise PlanError("writing_skill_route_invalid")
    rules, versions = {}, {}

    def load(skill, references):
        try:
            directory = root / skill
            heading = (directory / "SKILL.md").read_text(encoding="utf-8").strip()
            frontmatter = heading.split("\n---", 1)[0]
            match = VERSION.search(frontmatter)
            if not match or f"\nname: {skill}\n" not in frontmatter + "\n":
                raise PlanError(f"writing_skill_invalid:{skill}")
            versions[skill] = match[1]
            rules[f"{skill}/SKILL.md"] = heading
            for name in references:
                path = f"references/{name}.md"
                rule = (directory / path).read_text(encoding="utf-8").strip()
                if not rule:
                    raise PlanError(f"writing_skill_invalid:{skill}/{path}")
                rules[f"{skill}/{path}"] = rule
        except OSError as exc:
            missing = getattr(exc, "filename", None)
            reference = f"/{str(missing).rsplit("/", 1)[-1]}" if missing else ""
            raise PlanError(f"writing_skill_missing:{skill}{reference}") from exc

    if lane != "domain" and phase != "image":
        references = [f"style-{language}"]
        if phase in ("audit", "rewrite"):
            references += ["patterns-core", "fidelity-rules"]
        if phase in ("generate", "audit", "rewrite"):
            references.append("quality-gates")
            if domain == "story":
                references.append("long-form-fiction")
        load(HUMAN, references)
    if domain in PROFILES and lane != "language" and phase != "image":
        load(STORY if domain == "story" else ARTICLE, PROFILES[domain][phase])
    return SkillContext(rules, versions)
