"""Deterministic routing for Creative Studio writing and image requests."""
import re
import unicodedata

ID = re.compile(r"[a-f0-9]{32}")
WRITE = r"(?:schreib\w*|verfass\w*|erzähle?|write|draft|compose|tell)"
DRAW = r"(?:erstell\w*|generier\w*|zeichn\w*|illustrier\w*|mal(?:e|en)|mach\w*|create|generate|draw|paint|render|illustrate)"
ACTION = rf"(?:{WRITE}|{DRAW}|speicher\w*|zeige?|save|show|nutze|verwende|use|display)"
STORY = re.compile(r"\b(?:geschichte[n]?|fantasyroman|roman\w*|novelle|kapitel|(?:anfangs|eröffnungs)?szene|story|fiction|novel|chapter|scene)\b", re.I)
ARTICLE = re.compile(r"\b(?:artikel\w*|devlog\w*|blogbeitr(?:ag|äge)|article|blog post|aufsatz|textentwurf)\b", re.I)
PICTURE = re.compile(r"\b(?:bild(?:er)?|foto\w*|titelbild\w*|konzeptbild\w*|cover\w*|illustration\w*|artwork|image\w*|picture\w*|poster)\b", re.I)
VARIANT = re.compile(r"\b(?:variante[n]?|variation[s]?)\b", re.I)
PROJECT = r"(?:projekt(?:\s+(?:namens|mit dem namen|mit dem titel))?|project(?:\s+(?:named|called|titled))?)"
QUOTED = r'["„“«»\']([^"“”„»«\'\n]{1,180})["“”«»\']'
LANGUAGES = {
    "en": re.compile(r"\b(?:englisch\w*|english)\b", re.I),
    "de": re.compile(r"\b(?:deutsch\w*|german)\b", re.I),
}
FORMATS = {"1:1": "1024x1024", "16:9": "1024x576", "9:16": "576x1024",
           "4:3": "1024x768", "3:4": "768x1024", "3:2": "960x640", "2:3": "640x960"}
SPLIT = re.compile(rf"\n+|(?<!\d)[.!?;]+\s+(?=(?:\d+[.)]\s*)?{ACTION}\b)|"
                   rf"\s+(?:und|sowie|danach|anschließend|and|then)\s+(?={ACTION}\b)", re.I)


class PlanError(ValueError):
    pass


def field(text, labels):
    match = re.search(rf"(?im)^\s*(?:\*\*)?(?:{labels})\s*(?:\*\*)?:\s*(?:\*\*)?\s*([^\n]+)", text)
    return match[1].strip(" *\"„“«»")[:180] if match else ""


def project_name(text):
    quoted = re.search(rf"\b{PROJECT}\s*:?\s+{QUOTED}", text, re.I)
    if quoted:
        return quoted[1].strip()
    named = re.search(r"\b(?:projekt\s+namens|projekt\s+mit\s+dem\s+namen|project\s+(?:named|called))"
                      r"\s+([^\n.!?;]{1,180})", text, re.I)
    if named:
        return re.split(r"\s+(?:speichern|ablegen|save)\b", named[1], maxsplit=1, flags=re.I)[0].strip()
    bare = re.search(r"\b(?:im|ins|in(?:\s+(?:das|dem|the))?|into(?:\s+the)?)\s+(?:projekt|project)\s+"
                     r"([^\n.!?;,]{1,180})", text, re.I)
    if bare and not bare[1].strip().lower().startswith(("speichern", "ablegen", "save", "anzeigen")):
        return re.split(r"\s+(?:speichern|ablegen|save)\b", bare[1], maxsplit=1, flags=re.I)[0].strip()
    return ""


def word_bounds(text):
    unit = r"(?:wörter(?:n)?|words?)\b"
    interval = re.search(rf"\b(\d{{1,5}})\s*(?:–|—|-|bis|to)\s*(\d{{1,5}})\s+{unit}", text, re.I)
    if interval:
        low, high = map(int, interval.groups())
    else:
        matched = re.search(rf"\b(?:(genau|exakt|exactly|max(?:imal|imum)?\.?|höchstens|unter|under|"
                            rf"mindestens|at least|at most|no more than)\s+)?"
                            rf"(\d{{1,5}})(?:\s+|\s*-\s*){unit}", text, re.I)
        if not matched:
            return None
        value = int(matched[2])
        qualifier = (matched[1] or "").lower().rstrip(".")
        if qualifier in ("genau", "exakt", "exactly"):
            low = high = value
        elif qualifier in ("unter", "under"):
            low, high = 1, value - 1
        elif qualifier in ("max", "maximal", "maximum", "höchstens", "at most", "no more than"):
            low, high = 1, value
        elif qualifier in ("mindestens", "at least"):
            low, high = value, min(2600, value + max(60, value // 5))
        else:
            tolerance = max(3, round(value * .1))
            low, high = max(1, value - tolerance), value + tolerance
    if not 1 <= low <= high <= 2600:
        raise PlanError("word_range_unsupported")
    return [low, high]


def has_action(clause, pattern):
    match = re.search(rf"(?:^|\b){pattern}\b", clause, re.I)
    if not match:
        return False
    intro = clause[:match.start()]
    return not re.search(r"\b(?:kein\w*|nicht|without|don't|do not|wie|how to)\b", intro, re.I)


def build_plan(raw, mode, default_lang, image_options, detect_lang):
    """Return None for regular conversation and other existing tools."""
    if mode in ("chat", "game", "research"):
        return None
    text = unicodedata.normalize("NFKC", raw).strip()
    clauses = [re.sub(r"^[\s*#>-]*(?:\d+[.)]\s*)?", "", line).strip() for line in SPLIT.split(text)]
    clauses = [line for line in clauses if line]
    denied_writing = re.compile(r"\b(?:kein\w*|ohne|no|without)\s+(?:ein\w*\s+)?"
                                r"(?:geschicht\w*|story|roman\w*|novel|artikel|article)\b", re.I)
    image_wish = re.compile(r"^(?:(?:ich\s+(?:möchte|will|brauche|hätte\s+gern(?:e)?)|"
                            r"i\s+(?:want|need|would\s+like))\s+)"
                            r"(?:gern(?:e)?\s+)?(?:ein\w*|an?|some)\s+(?:[\w-]+\s+){0,3}"
                            r"(?:bild|titelbild|illustration|foto|image|picture|cover)\b", re.I)
    writing = [line for line in clauses if not denied_writing.search(line) and not image_wish.search(line) and
               (has_action(line, WRITE) or (not PICTURE.search(line) and has_action(line, DRAW))) and
               (STORY.search(line) or ARTICLE.search(line) or mode in ("story", "article"))]
    if not writing and STORY.search(text) and re.search(r"\b(?:ich möchte|ich will|lass uns|let.s|i want to)\b", text, re.I):
        writing = [line for line in clauses if STORY.search(line) and not denied_writing.search(line) and not image_wish.search(line)
                   and not re.search(r"\b(?:speicher\w*|save)\b", line, re.I)]
    illustrations = [line for line in clauses if PICTURE.search(line) and (has_action(line, DRAW) or image_wish.search(line))
                     and not re.search(r"\b(?:kein\w*|ohne|without|no)\s+(?:ein\w*\s+)?(?:bild\w*|images?|illustration\w*)\b", line, re.I)]
    variants = [line for line in clauses if VARIANT.search(line) and (has_action(line, DRAW) or
                  re.match(r"^(?:bitte\s+)?(?:noch\s+)?(?:eine|a|another)\s+varia", line, re.I))]
    if mode in ("story", "article") and not writing:
        writing = clauses[:1]
    if mode == "image" and not illustrations and not variants:
        illustrations = clauses[:1]
    if not (writing or illustrations or variants):
        return None
    if writing and (illustrations or variants) and re.search(rf"\b(?:entweder|either)\b|\b(?:oder|or)\s+{DRAW}\b", text, re.I):
        raise PlanError("creative_choice_required")
    if not writing and not variants and illustrations and all(
            re.fullmatch(rf"(?:bitte\s+)?{DRAW}\s+(?:mir\s+)?(?:ein\s+|an?\s+)?"
                         r"(?:bild|image|foto|picture)(?:\s+(?:von|mit|of|with))?[.!]?", line, re.I)
            for line in illustrations):
        raise PlanError("image_prompt_required")

    story = mode == "story" or (mode != "article" and any(STORY.search(line) for line in writing))
    title = field(text, "Titel|Title")
    if not title and writing:
        title_match = re.search(rf"\b(?:namens|titled|called|mit dem titel)\s+{QUOTED}", writing[0], re.I)
        title = title_match[1].strip() if title_match else ""
    named = project_name(text)
    plan = {"title": title, "project_name": named}
    if writing:
        instruction = "\n".join(line for line in clauses if line not in illustrations and line not in variants
                                and not re.search(r"^(?:(?:bitte|please)\s+)?(?:zeig\w*|speicher\w*|show|display|save)\b", line, re.I)
                                and not re.match(r"^(?:wenn eine funktion|if (?:any|a) feature)\b", line, re.I))
        requests = [lang for lang, markers in LANGUAGES.items() if any(markers.search(line) for line in writing)]
        if len(requests) > 1:
            raise PlanError("creative_language_ambiguous")
        if not requests:
            requests = [lang for lang, markers in LANGUAGES.items() if markers.search(instruction)]
        inferred = detect_lang(instruction.lower()) if not requests else requests[0]
        plan["writing"] = {"kind": "story" if story else "article", "lang": inferred if
                           inferred in ("de", "en") else default_lang, "language_explicit": bool(requests),
                           "words": word_bounds(instruction),
                           "instruction": instruction[:12000]}
    if illustrations or variants:
        ratio = re.search(r"\b(\d{1,2})\s*:\s*(\d{1,2})\b", " ".join(illustrations + variants))
        image = dict(image_options)
        if ratio:
            aspect = ":".join(ratio.groups())
            if aspect not in FORMATS:
                raise PlanError("image_format_unsupported")
            image["size"] = FORMATS[aspect]
        plan["image"] = {"request": image, "variant": bool(variants and not any(line not in variants for line in illustrations)),
                         "brief": " ".join(illustrations + variants + [line for line in clauses
                             if re.match(r"^(?:\*\*)?(?:stil|style|motiv|setting)\b", line, re.I)])[:1800]}
    return plan


def check_text(text, writing, skill_text):
    content = re.sub(r"(?m)^\s*#{1,6}\s+[^\n]*\n?", "", text).strip()
    prose = skill_text.PROTECT_RE.sub("", content)
    prose = prose.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "„": '"'}))
    count = len(skill_text.words(prose))
    detected = skill_text.detect_lang(prose.lower())
    issues = []
    if not prose or re.match(r"^(?:as an ai\b|i (?:cannot|can.t) (?:generate|save|create)|"
                             r"da ich ein ki.modell bin\b|als (?:ki|sprachmodell)\b)", prose, re.I):
        issues.append("not_prose")
    if detected != writing["lang"]:
        issues.append("language_mismatch")
    if writing["words"] and not writing["words"][0] <= count <= writing["words"][1]:
        issues.append("word_count_mismatch")
    return {"language": detected, "words": count, "issues": issues, "language_check": "human-writing markers"}
