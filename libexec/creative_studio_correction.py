"""Shared exact-span editorial patches and protected document structure."""

import hashlib
import re
from collections import Counter

from creative_studio_plan import PlanError

FRONTMATTER = re.compile(r"\A(?:\ufeff)?---[ \t]*\r?\n.*?^---[ \t]*(?:\r?\n|\Z)", re.M | re.S)
MARKUP = re.compile(
    r"^[ \t]*(?:`{3,}|~{3,})[^\n]*\n.*?^[ \t]*(?:`{3,}|~{3,})[^\n]*$"
    r"|^[ \t]*(?:`{3,}|~{3,})[^\n]*\n[\s\S]*\Z"
    r"|^[ \t]{0,3}#{1,6}[ \t]+[^\n]*"
    r"|^[ \t]*(?:\|[^\n]*|[^\n|]+\|[^\n]*)$"
    r"|^[ \t]*(?:import|export)\s+[^\n]*"
    r"|^[ \t]*\[[^\]\n]+\]:[^\n]*"
    r"|!?(?:\[[^\]\n]*\])(?:\([^\n]*?\)(?=[\s.,;:!?]|$)|\[[^\]\n]*\])"
    r"|`+[^`\n]+`+|<[^<>\n]+>|\{[^{}\n]*\}|https?://[^\s<>\]]+", re.M | re.S)
QUANTITY = re.compile(r"\b(?:\d[\w.,:%/-]*|one|two|three|four|five|six|seven|eight|nine|ten|"
                      r"zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn)\b", re.I)
NAMES = re.compile(r"\b(?:[A-ZÄÖÜ]{2,}[\w.-]*|[A-ZÄÖÜ][a-zäöüß]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß]+)+)\b")
CAPITAL = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß]{2,}\b")


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def markup(text):
    frontmatter = FRONTMATTER.match(text)
    start = frontmatter.end() if frontmatter else 0
    return ([frontmatter] if frontmatter else []) + list(MARKUP.finditer(text, start))


def improvements(original, candidate, blockers, automatic):
    """Only admit progress without introducing independently confirmed defects."""
    before, after = blockers(original), blockers(candidate)
    return not (after - before) and (sum(after.values()), automatic(candidate)) < (sum(before.values()), automatic(original))


def patch_text(text, edits, motifs, tools, *, local=False, targets=(), base_hash=None,
               article=False, canon="", language_tools=None, language=None, canonical_names=()):
    if base_hash is not None and digest(text) != base_hash:
        raise PlanError("production_patch_stale")
    if not isinstance(edits, list) or not edits:
        return text
    spans = []
    protected_motifs = [tools.normalized(motif) for motif in motifs]
    protected_markup = markup(text)
    canonical_names = [name for name in canonical_names if name and "\n" not in name]
    for edit in edits:
        if not isinstance(edit, dict):
            raise PlanError("production_patch_invalid")
        before, after = edit.get("before"), edit.get("after")
        if not isinstance(before, str) or not isinstance(after, str) or not before:
            raise PlanError("production_patch_invalid")
        if len(before) > 1800 or len(after) > 2600 or tools.protected(before, protected_motifs):
            raise PlanError("production_patch_invalid")
        start = edit.get("start") if local else text.find(before)
        if (type(start) is not int or start < 0 or not text.startswith(before, start)
                or (not local and text.find(before, start + 1) >= 0)):
            raise PlanError("production_patch_invalid")
        end = start + len(before)
        related = [t for t in targets if "end" in t and start < t["end"] and end > t["start"]]
        if (targets and not related) or any(start < m.end() and end > m.start() for m in protected_markup):
            raise PlanError("production_patch_invalid")
        if after.rstrip().endswith((".", "!", "?")) and re.match(r"\s*[.!?,;:]", text[end:]):
            raise PlanError("production_patch_boundary")
        left, right = text[start - 1:start] if start else "", text[end:end + 1]
        if (after and (left.isalnum() and after[0].isalnum() or right.isalnum() and after[-1].isalnum())
                or not after and left.isalnum() and right.isalnum()):
            raise PlanError("production_patch_boundary")
        if not local and len(after) > max(240, 2 * len(before) + 80):
            raise PlanError("production_patch_invalid")

        def facts(value):
            quantities = QUANTITY.findall(value)
            names = NAMES.findall(value)
            if article and not local:
                names += CAPITAL.findall(value)
            names += [name for name in canonical_names if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", value)]
            return quantities, names, tools.protected_facts(value)

        if local and not after:
            # Exact mechanical duplicate deletion keeps the first occurrence.
            duplicate = next((item for item in tools.local_quality(text, motifs)[1]
                              if item["start"] == start and item["before"] == before and not item["after"]), None)
        else:
            duplicate = None
        if facts(before) != facts(after) and not duplicate:
            supported = (not article and any(t.get("status") == "confirmed" and t.get("category") == "continuity"
                         and (quote := t.get("related_quote", "")) and quote in canon
                         and after.strip() and after.strip() in quote for t in related)
                         and NAMES.findall(before) == NAMES.findall(after)
                         and all(re.fullmatch(r"\d+(?:[.,:]\d+)*", value)
                                 for value in tools.PROTECTED.findall(before) + tools.PROTECTED.findall(after)))
            if not supported:
                raise PlanError("production_patch_invalid")
        spans.append((start, end, after))
    if not local and sum(end - start for start, end, _ in spans) > min(2400, max(140, len(text) // 4)):
        raise PlanError("production_patch_invalid")
    candidate, end_limit = text, len(text)
    for start, end, after in sorted(spans, reverse=True):
        if end > end_limit:
            raise PlanError("production_patch_invalid")
        candidate = candidate[:start] + after + candidate[end:]
        end_limit = start
    if [m[0] for m in markup(text)] != [m[0] for m in markup(candidate)]:
        raise PlanError("production_patch_regression")
    if language and language_tools:
        prose = language_tools.PROTECT_RE.sub("", candidate)
        if len(language_tools.words(prose)) >= 45 and language_tools.detect_lang(prose.lower()) != language:
            raise PlanError("production_patch_regression")

    def defects(value):
        checks, _ = tools.local_quality(value, motifs)
        repeated = tools.repetitions({"draft": value}, motifs, limit=96)
        return Counter((f["category"], tools.normalized(f["quote"])) for f in checks + repeated)

    if defects(candidate) - defects(text):
        raise PlanError("production_patch_regression")
    return candidate
