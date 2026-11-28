"""General content commissions: one request that writes a text and optionally adds a picture and a file.

The routing reads the whole request clause by clause. A creation clause with a text deliverable makes
the commission a creation, so a following "prüfe den Text" becomes a quality step instead of the main
task. A review stays the main task when it comes first or when the request names no new text."""

import hashlib
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from creative_studio_plan import FORMATS, ID, LANGUAGES, PlanError, word_bounds

CREATE = r"(?:erstell\w*|schreib\w*|verfass\w*|entwirf\w*|entwerf\w*|formulier\w*|generier\w*|write|create|draft|compose|produce|generate)"
REVIEW = (r"(?:prüf\w*|überprüf\w*|kontrollier\w*|audit\w*|korrigier\w*|lektorier\w*|überarbeit\w*|verbesser\w*|"
          r"check\w*|review\w*|proofread\w*|revise\w*|rewrite|polish\w*)")
SHOW = r"(?:zeig\w*|show|display|stell\w*|lad\w*|speicher\w*|exportier\w*|bereit\w*|provide|export|save|download)"
IMAGE = r"(?:titelbild\w*|konzeptbild\w*|bild\w*|illustration\w*|grafik\w*|foto\w*|cover\w*|artwork\w*|image\w*|picture\w*|poster)"
VISUAL = r"(?:zeichn\w*|illustrier\w*|render\w*|draw|paint|mach\w*)"
NOUN = (r"(?:steckbrief\w*|profil\w*|beschreibung\w*|zusammenfassung\w*|teaser|klappentext\w*|newsletter|e-?mail|mail|brief|post|"
        r"ankündigung\w*|pressemitteilung\w*|dossier|bericht\w*|rezension\w*|einleitung\w*|gedicht\w*|songtext\w*|dialog\w*|"
        r"slogan|headline|überschrift\w*|biografie|biographie|vorstellung\w*|anleitung\w*|text(?:e|en)?|"
        r"profiles?|summary|description|blurb|email|letter|announcement|press release|report|review|intro(?:duction)?|"
        r"dokumentation\w*|readme|changelog\w*|release notes?|faq|tutorial\w*|handbuch|handbücher|"
        r"documentation|manual|guide|walkthrough|spielanleitung|questtext\w*|npc-?text\w*|"
        r"poem|lyrics|speech|bio|copy|write-?up|fact sheet|one-pager)")
DELIVERABLE = re.compile(rf"(?<![\wäöüß])(?:[\wäöüß]+-)*[\wäöüß]*{NOUN}(?![\wäöüß])", re.I)
PICTURE_WORD = re.compile(r"bild|grafik|foto|image|cover|illustration|artwork|picture|poster", re.I)
# Subjects the other chat actions already own. They keep their routes.
OWNED = re.compile(r"\b(?:geschichte\w*|roman\w*|story|stories|novel|kapitel\w*|chapter\w*|szene\w*|scene\w*|artikel\w*|article\w*|devlog\w*|"
                   r"blog\w*|recherch\w*|research\w*|planung\w*|outline\w*|bibel|spielidee\w*|spielkonzept\w*|game design)\b", re.I)
STARTER = r"(?:(?:und|dann|danach|anschließend|außerdem|bitte|jetzt|nun|mir|uns|please|and|then|also)\s+)*"
FRAME = (r"(?:(?:kannst|könntest|würdest|magst) du|can you|could you|would you|"
         r"ich (?:möchte|will|brauche|hätte gern(?:e)?)|i (?:want|need|would like))")
VERBS = rf"(?:{CREATE}|{REVIEW}|{SHOW}|verwende\w*|nutze\w*|use|{VISUAL})"
NEGATION = re.compile(r"\b(?:kein\w*|nicht|ohne|no|not|without|don.t|do not)\b", re.I)
REWRITE = re.compile(r"\b(?:um|neu|noch\s?mal|erneut|again|over|besser|kürzer|länger|anders)\b", re.I)
DEFINITE = re.compile(r"\b(?:den|dem|das|die|diesen|dieses|diese|dieser|meinen|mein|unseren|the|this|these|my|our)\b", re.I)
COMPLEMENT = re.compile(r"\s*(?:für|fürs|zu|zum|zur|über|von|for|about|of|on)\b", re.I)
KEEP = re.compile(r"\b(?:nicht\s+(?:ändern|korrigieren|überarbeiten)|ohne\s+(?:zu\s+)?(?:ändern|korrigieren)|nur\s+prüfen|"
                  r"(?:do not|don.t)\s+(?:change|edit|correct)|only\s+(?:check|review))\b", re.I)
NO_REVIEW = re.compile(r"\b(?:ohne|without)\s+(?:\w+\s+)?(?:prüfung|check|review)\b", re.I)
FOLDER = re.compile(r"\b(?:ordner\w*|bestätigte[sn]?\s+wissen|kanon|folder|knowledge)\b", re.I)
ONLY = re.compile(r"\b(?:ausschließlich|nur|only|exclusively)\b[^.!?\n]{0,60}\b(?:ordner\w*|wissen|kanon|knowledge|folder|bestätigt\w*)", re.I)
FILE = re.compile(r"\b(?:datei|download\w*|herunterlad\w*|exportier\w*|export|bereitstell\w*|speicher\w*\s+als)\b|\bals\s+(?:markdown|md|mdx|txt|pdf|docx)\b", re.I)
FORMAT_WORDS = (("md", r"markdown|\.md\b|\bmd\b"), ("mdx", r"\bmdx\b"), ("txt", r"\btxt\b|textdatei"),
                ("pdf", r"\bpdf\b"), ("docx", r"\bdocx\b|\bword\b"))
EXPORTS = ("md",)
# The quality profile (see creative_studio_quality) that fits a content type.
PROFILE_OF_TYPE = {"technical_doc": "technical", "website_copy": "marketing", "product_description": "marketing",
                   "announcement": "marketing", "dialogue": "dialogue", "poem": "story"}
VARIANTS = (("de-AT", r"österreichisch\w*|austrian german|de-AT"), ("de-CH", r"schweizer\w*|swiss german|de-CH"),
            ("en-GB", r"britisch\w*|british english|en-GB"), ("en-CA", r"kanadisch\w*|canadian english|en-CA"),
            ("en-AU", r"australisch\w*|australian english|en-AU"))
STYLE = re.compile(r"\b(?:im|in|mit)\s+(?:dem\s+|einem\s+|the\s+|an?\s+)?(?:(?:passenden|folgenden|gewünschten)\s+)?"
                   r"([\w/ -]{3,60}?)[\s-]*(?:stil|look|style)\b", re.I)
COUNT = re.compile(r"(\d{1,5})(?:\s*(?:–|—|-|bis|to)\s*(\d{1,5}))?\s+(?:wörter(?:n)?|words?)\b", re.I)
NAME = r"([A-ZÄÖÜ][\wäöüß'’-]*(?:\s+(?:[A-ZÄÖÜ][\wäöüß'’-]*|\d+))*)"
SUBJECT = re.compile(r"\b(?:für|fürs|über|zu|zum|zur|about|for|on)\s+(?:(?:den|die|das|dem|der|the|a|an)\s+)?" + NAME)
SERIES = re.compile(r"\b(?:aus|from|in|im)\s+(?:dem\s+|der\s+|the\s+)?" + NAME)
TYPES = (("technical_doc", r"dokumentation|readme|changelog|release notes?|faq|tutorial|handbuch|documentation|manual|guide|walkthrough|anleitung"),
         ("website_copy", r"website|webseiten|web-?text|landingpage|landing page"),
         ("product_description", r"produkt\w*[ -]?(?:beschreibung|text)|product[ -]?(?:description|text)"),
         ("dialogue", r"dialog\w*|quest\w*|npc|spieltext\w*"),
         ("track_profile", r"(?:strecke|track|rennstrecke|course|circuit)\w*[ -]?(?:steckbrief|profil|beschreibung|profile|description)"),
         ("character_profile", r"(?:charakter|figur|fahrer|character|driver|person)\w*[ -]?(?:steckbrief|profil|beschreibung|profile|bio)"),
         ("profile", r"steckbrief|profil|profile|fact sheet|bio"),
         ("summary", r"zusammenfassung|summary|teaser|klappentext|blurb"),
         ("description", r"beschreibung|description"),
         ("announcement", r"ankündigung|pressemitteilung|announcement|press release|newsletter"),
         ("message", r"e-?mail|mail|brief|letter"),
         ("poem", r"gedicht|songtext|poem|lyrics"),
         ("report", r"bericht|dossier|report|review|rezension"))


def _clauses(text):
    cut = rf"\s+(?:und|sowie|danach|anschließend|and|then)\s+(?={VERBS}\b)|,\s+(?={VERBS}\b)"
    return [part.strip() for line in re.split(r"\n+|(?<=[.!?])\s+", text) for part in re.split(cut, line, flags=re.I) if part.strip()]


def _starts(clause, verbs):
    return bool(re.match(rf"\s*{STARTER}(?:{verbs})\b", clause, re.I))


def _creation(clause):
    """The deliverable-noun match of a clause that asks for newly written text, else None."""
    imperative = _starts(clause, CREATE)
    framed = re.match(rf"\s*{STARTER}{FRAME}\b", clause, re.I)
    verb = re.search(rf"\b{CREATE}\b", clause, re.I)
    if not verb or not (imperative or framed):
        return None
    begin = verb.end() if imperative else framed.end() if framed else 0
    match = DELIVERABLE.search(clause, begin)
    if not match or PICTURE_WORD.search(match[0]):
        return None
    gap, rest = clause[begin:match.start()], clause[match.end():]
    if re.search(rf"\b{IMAGE}\b", gap, re.I) or NEGATION.search(clause[:match.start()]) or OWNED.search(clause):
        return None
    # "den Text neu schreiben" or "diesen Text besser machen" work on an existing text.
    if REWRITE.match(rest.lstrip()) or (DEFINITE.search(gap) and not COMPLEMENT.match(rest)):
        return None
    return match


def _wants_image(clause):
    wish = re.search(rf"\b(?:{CREATE}|{VISUAL}|{SHOW})\b[^.!?\n]{{0,90}}\b{IMAGE}\b", clause, re.I) or re.search(
        rf"\b(?:mit|samt|inklusive|inkl\.?|plus|with|including)\s+(?:[\wäöüß-]+\s+){{0,3}}{IMAGE}\b", clause, re.I)
    return bool(wish and not NEGATION.search(clause[:wish.start() + 24])
                and not re.search(rf"\b(?:kein\w*|ohne|without|no)\s+(?:\w+\s+)?{IMAGE}\b", clause, re.I))


def _target(text):
    found = COUNT.search(text)
    if not found:
        return None
    first, second = int(found[1]), int(found[2]) if found[2] else None
    return (first + second) // 2 if second else first


def _parse(text):
    plain = re.sub(r"\*{1,3}|`", "", unicodedata.normalize("NFKC", text)).strip()
    parts = _clauses(plain)
    found = next(((index, match) for index, clause in enumerate(parts) if (match := _creation(clause))), None)
    if not found:
        return None
    created, noun = found
    reviews = [index for index, clause in enumerate(parts) if _starts(clause, REVIEW)]
    if any(index < created for index in reviews):
        return None  # a review in front of the creation is an ordinary review
    clause, label = parts[created], noun[0]
    after = clause[noun.end():]
    subject = SUBJECT.search(after)
    series = SERIES.search(after[subject.end():] if subject else after)
    kind = next((name for name, pattern in TYPES if re.search(pattern, clause[:noun.end()], re.I)), "text")
    languages = [lang for lang, marker in LANGUAGES.items() if marker.search(plain)]
    pictures = [item for index, item in enumerate(parts) if index != created and _wants_image(item)]
    asked = [item for item in parts if FILE.search(item) or any(re.search(pattern, item, re.I) for _, pattern in FORMAT_WORDS)]
    requested = [name for name, pattern in FORMAT_WORDS if any(re.search(pattern, item, re.I) for item in asked)]
    if asked and not requested:
        requested = ["md"]
    # The brief keeps the writing request and its style notes; pictures, files and the review run as workflow steps.
    kept = [item for index, item in enumerate(parts) if index not in reviews and item not in pictures
            and not _starts(item, SHOW) and (index == created or not _creation(item) and item not in asked)]
    instruction = "\n".join(kept)
    bounds = word_bounds(instruction)
    look = " ".join(pictures or ([clause] if _wants_image(clause) else []))
    ratio = re.search(r"\b(\d{1,2})\s*:\s*(\d{1,2})\b", look)
    style = STYLE.search(look)
    contract = {
        "primary_intent": "create_content",
        "content_type": kind,
        "content_label": label,
        "language": next((name for name, pattern in VARIANTS if re.search(pattern, plain, re.I)),
                         {"de": "de-DE", "en": "en-US"}[languages[0]] if len(languages) == 1 else None),
        "quality_profile": PROFILE_OF_TYPE.get(kind, "general"),
        "target_words": _target(instruction),
        "word_range": bounds,
        "subject": subject[1].strip() if subject else "",
        "context_name": series[1].strip() if series else "",
        "use_folder_knowledge": bool(FOLDER.search(plain)),
        "knowledge_only": bool(ONLY.search(plain)),
        "review_after_creation": not NO_REVIEW.search(plain),
        "auto_correct": not KEEP.search(plain) and not NO_REVIEW.search(plain),
        "generate_image": bool(pictures) or _wants_image(clause),
        "image_aspect_ratio": ":".join(ratio.groups()) if ratio else None,
        "image_profile": re.sub(r"\s+", " ", style[1]).strip(" -") if style else None,
        "export_formats": [name for name in requested if name in EXPORTS],
        "export_unsupported": [name for name in requested if name not in EXPORTS],
    }
    return contract, instruction, pictures


def analyze(text):
    """The intent contract of a text-creation commission, or None for any other request."""
    parsed = _parse(text)
    return parsed[0] if parsed else None


def make_plan(raw, default_lang, image_options, detect_lang):
    """A chat-task plan for a creation commission; None when the request is something else."""
    parsed = _parse(raw)
    if not parsed:
        return None
    contract, instruction, pictures = parsed
    lang = contract["language"][:2] if contract["language"] else detect_lang(instruction.lower())
    plan = {"title": "", "project_name": "", "writing": {
        "kind": "content", "lang": lang if lang in ("de", "en") else default_lang, "language_explicit": bool(contract["language"]),
        "words": contract["word_range"], "instruction": instruction[:12000], "content": contract}}
    if contract["generate_image"]:
        image = dict(image_options)
        if contract["image_aspect_ratio"]:
            if contract["image_aspect_ratio"] not in FORMATS:
                raise PlanError("image_format_unsupported")
            image["size"] = FORMATS[contract["image_aspect_ratio"]]
        subject = " ".join(item for item in (contract["subject"], contract["context_name"]) if item)
        plan["image"] = {"request": image, "variant": False,
                         "brief": " ".join(pictures)[:1800] or subject or contract["content_label"]}
    if contract["export_formats"]:
        plan["export"] = {"formats": contract["export_formats"]}
    return plan


def heading(text):
    found = re.search(r"(?m)^#{1,3}\s+(.{1,160}?)\s*#*\s*$", text)
    return found[1] if found else ""


def slug(title):
    base = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60] or "text"


def render(title, text):
    body = text.strip()
    return (body if re.match(r"#\s", body) else f"# {title}\n\n{body}") + "\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def export(root, task_id, title, text, formats):
    """Write each requested file, read it back and return the receipt that licenses the download."""
    if not ID.fullmatch(task_id):
        raise PlanError("content_export_invalid")
    directory = Path(root) / task_id
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    files = []
    for fmt in formats:
        if fmt not in EXPORTS:
            raise PlanError("content_export_invalid")
        name, expected = f"{slug(title)}.{fmt}", render(title, text).encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            handle.write(expected)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, directory / name)
        files.append({"name": name, "format": fmt, "bytes": len(expected), "sha256": sha(expected)})
    receipt = {"files": files}
    for entry in files:
        verify(root, task_id, receipt, entry["name"], text)
    return {**receipt, "validated": True}


def verify(root, task_id, receipt, name, text=None):
    """The path of a stored file whose bytes still match the receipt (and the saved text, when given)."""
    entry = next((item for item in receipt.get("files", []) if item["name"] == name), None)
    if not entry or not ID.fullmatch(task_id) or "/" in name:
        raise PlanError("content_export_missing")
    path = Path(root) / task_id / name
    try:
        data = path.read_bytes()
        decoded = data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanError("content_export_missing") from exc
    if not data or len(data) != entry["bytes"] or sha(data) != entry["sha256"]:
        raise PlanError("content_export_missing")
    if text is not None and (not decoded.startswith("#") or text.strip() not in decoded):
        raise PlanError("content_export_invalid")
    return path
