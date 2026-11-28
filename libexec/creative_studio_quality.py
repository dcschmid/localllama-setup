"""Central Human Writing quality pipeline for every Creative Studio writing workflow.

Generate (by the caller) → Audit → Verify → Auto-Fix → Recheck → Finalize.

One implementation serves German and English texts of any kind. The caller names the language, the text
kind and the model transport, and receives the final text plus a receipt that proves what was executed:
which skill rules were loaded, which findings were confirmed, which edits were applied or rejected,
whether the revision was checked again, and the hash of the final version.

The pipeline never regenerates a text. It corrects confirmed defects with exact, validated span edits,
keeps passages that already read well, and stops after at most two correction passes."""

import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import creative_studio_correction as correction
import creative_studio_story as story
from creative_studio_plan import PlanError, check_text
from creative_studio_production import WaitForResource, array, dump, enum, fields

VERSION = 1
MAX_PASSES = 2
BATCH = 8
FINDINGS_PER_WINDOW = 6
EDITS_PER_PASS = 6
RECOVERABLE = (PlanError, OSError, ValueError, KeyError, TypeError, WaitForResource)

LANGUAGE_NAMES = {"de-DE": "German (Germany)", "de-AT": "German (Austria)", "de-CH": "German (Switzerland)",
                  "en-US": "English (United States)", "en-GB": "English (United Kingdom)",
                  "en-CA": "English (Canada)", "en-AU": "English (Australia)"}
DEFAULT_LOCALE = {"de": "de-DE", "en": "en-US"}
LANGUAGE_RULES = {
    "de": ("Go through the passage sentence by sentence. For each sentence check: spelling (ß/ss, capitalization, joined and "
           "separate spelling); that every verb, including the second verb of a predicate joined by 'und' or 'oder', agrees with "
           "its subject in person and number; tense and mood; article, case and gender; prepositions with their case; commas "
           "for clauses, infinitive groups and lists; verb position. Report literal translations from English ('Sinn machen', "
           "'in 2024', 'Informationen bekommen von') and anglicisms only where a common German word exists and the context is "
           "not technical or intended."),
    "en": ("Go through the passage sentence by sentence. For each sentence check: spelling; that every verb, including the "
           "second verb of a predicate joined by 'and' or 'or', agrees with its subject in person and number ('he needs', "
           "'you need', 'they have'); tense; articles and determiners; prepositions; punctuation (comma splices, apostrophes, "
           "quotation punctuation). Report literal translations from German ('since three years', 'become' for 'get') and "
           "misused idioms or false friends where a common English phrase exists and the context is not intended."),
}
VARIANT_RULES = {
    "de-DE": "", "en-US": "Use American spelling and punctuation.",
    "de-AT": "Austrian standard vocabulary (for example Jänner, heuer) is correct; do not report regionalisms.",
    "de-CH": "Swiss standard German has no ß (strasse is correct) and uses Swiss vocabulary; do not report these forms.",
    "en-GB": "Use British spelling (colour, organise); do not report it as an error.",
    "en-CA": "Canadian spelling mixes American and British forms; accept both.",
    "en-AU": "Australian spelling follows British forms; do not report them as errors.",
}

AI_PATTERNS = frozenset(("signposting", "promotional-inflation", "synthetic-enthusiasm", "empty-conclusion", "pseudo-profundity"))
MECHANICAL = frozenset(("punctuation", "repetition"))
GLUE = frozenset(("generic-transition", "hedging"))


@dataclass(frozen=True)
class Profile:
    """What counts as a defect depends on the kind of text."""
    name: str
    register: str
    actionable: frozenset   # rule categories that are corrected automatically
    naturalness: bool       # idiom, calque and anglicism corrections are automatic
    factual: bool           # strict patch mode: capitalised names and every claim stay
    guidance: str


PROFILES = {
    "general": Profile("general", "general", AI_PATTERNS | MECHANICAL | GLUE, True, False,
                       "Keep the author's register. Make the text natural and clear for its readers."),
    "story": Profile("story", "literary", MECHANICAL | {"signposting"}, False, False,
                     "This is fiction. Keep voice, sentence fragments, rhythm, deliberate repetition and dialogue. "
                     "Report only objective errors."),
    "dialogue": Profile("dialogue", "literary", MECHANICAL, False, False,
                        "This is dialogue or game text. Spoken language, dialect, interruptions and fragments are intended. "
                        "Report only spelling and punctuation errors."),
    "article": Profile("article", "factual", AI_PATTERNS | MECHANICAL, True, True,
                       "This is a factual article. Never change a claim, figure, name, source or quotation. Fix language only."),
    "essay": Profile("essay", "factual", AI_PATTERNS | MECHANICAL | GLUE, True, True,
                     "This is an essay with an argument. Keep the position and every claim. Fix language only."),
    "blog": Profile("blog", "general", AI_PATTERNS | MECHANICAL | GLUE, True, False,
                    "This is a blog post or devlog. A personal, direct voice is intended. Keep it."),
    "technical": Profile("technical", "technical", AI_PATTERNS | MECHANICAL, False, True,
                         "This is technical text. Keep terminology, commands, versions, identifiers and precise qualifiers."),
    "marketing": Profile("marketing", "marketing", AI_PATTERNS | MECHANICAL | GLUE, True, False,
                         "This is product, project or website copy. Prefer concrete statements and remove empty superlatives "
                         "without inventing facts."),
}
ALIASES = {
    "story": ("story", "novel", "chapter", "fiction", "scene", "szene", "kurzgeschichte", "poem", "gedicht", "songtext", "lyrics"),
    "dialogue": ("dialogue", "dialog", "game_text", "spieltext", "quest", "npc"),
    "article": ("article", "artikel", "dossier", "music_article", "musikartikel", "report", "bericht"),
    "essay": ("essay", "kommentar", "opinion"),
    "blog": ("blog", "blogpost", "devlog"),
    "technical": ("technical", "technik", "documentation", "dokumentation", "readme", "changelog", "tutorial", "anleitung", "howto"),
    "marketing": ("marketing", "website", "web", "landing", "product", "produkt", "product_description", "project_description",
                  "announcement", "newsletter"),
}
PROFILE_OF = {alias: name for name, aliases in ALIASES.items() for alias in aliases}

STRUCTURE_TERMS = ("quote", "code", "link", "number", "term", "markup")
QUOTE = re.compile(r'„[^“\n]+“|“[^”\n]+”|"[^"\n]+"|«[^»\n]+»|»[^«\n]+«|‚[^‘\n]+‘|‘[^’\n]+’')
NUMBER = re.compile(r"\d+(?:[.,:/-]\d+)*")
# Structural observations without a safe local repair, and a join that the mechanical repair already owns.
SKIPPED_RULES = frozenset(("rhythm", "formatting", "enthusiasm-punct", "damaged-join"))
digest = correction.digest


def profile_for(kind):
    """The profile of a text kind. Content types, document kinds and plain names all work."""
    key = re.sub(r"[\s-]+", "_", str(kind or "general").strip().casefold())
    return PROFILES[PROFILE_OF.get(key, key if key in PROFILES else "general")]


def locale_for(lang, locale=None):
    """The language variant to audit against. An explicit, supported variant of the same language wins."""
    if lang not in DEFAULT_LOCALE:
        raise PlanError("quality_language_unsupported")
    return locale if isinstance(locale, str) and locale in LANGUAGE_NAMES and locale[:2] == lang else DEFAULT_LOCALE[lang]


@dataclass(frozen=True)
class Tools:
    fiction: object   # fiction_audit: anchoring, mechanical local repairs and the patch contract
    language: object  # hw_text: protected spans, word counts, language detection, German orthography
    rules: object     # hw_rules: the pattern registry that detects generic AI phrasing


def load_tools(root):
    """The Human Writing skill's own scripts, loaded from the skills directory."""
    directory = Path(root) / "human-writing" / "scripts"
    sys.path.insert(0, str(directory))
    try:
        import fiction_audit
        import hw_rules
        import hw_text
    except ImportError as exc:
        raise PlanError("writing_skill_missing:human-writing") from exc
    finally:
        sys.path.remove(str(directory))
    return Tools(fiction_audit, hw_text, hw_rules)


def spans_of(text, tools):
    """Passages no correction may touch: Markdown structure, code, links, quotations and the skill's protected spans."""
    found = [(m.start(), m.end()) for m in correction.markup(text)]
    found += [(m.start(), m.end()) for m in QUOTE.finditer(text)]
    found += [(m.start(), m.end()) for m in tools.language.PROTECT_RE.finditer(text)]
    return found


def covered(spans, start, stop):
    """How many characters of [start, stop) lie inside the spans, where overlapping spans count once."""
    total, reach = 0, start
    for begin, end in sorted(spans):
        begin, end = max(begin, reach), min(end, stop)
        if end > begin:
            total += end - begin
            reach = end
    return total


def signature(text, terms=()):
    """Everything a correction has to leave exactly as it was."""
    return (tuple(m[0] for m in correction.markup(text)), tuple(QUOTE.findall(text)), Counter(NUMBER.findall(text)),
            tuple(len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)) for term in terms),
            (text.count("**") % 2, text.count("__") % 2))


def difference(before, after, terms=()):
    """The first kind of protected content a candidate changed, or None."""
    names = ("markup_changed", "quote_changed", "number_changed", "term_changed", "emphasis_unbalanced")
    return next((name for name, old, new in zip(names, signature(before, terms), signature(after, terms)) if old != new), None)


SEAMS = {
    "double_space": re.compile(r"(?<=\S)[ \t]{2,}(?=\S)"),
    "space_before_punctuation": re.compile(r"(?<=\S)[ \t]+[,.;:!?](?=\s|$)"),
    "stray_punctuation": re.compile(r"(?:^|[.!?])[ \t]*[,;:](?=\s)|[,;:][ \t]*[,;:.](?!\.)", re.M),
    "lowercase_sentence_start": re.compile(r"(?:\A|\n[ \t]*\n[ \t]*|(?<=\w{3}[.!?])[ \t]+)[a-zäöüß]"),
    "empty_emphasis": re.compile(r"(?<!\*)\*{4}(?!\*)|(?<!_)_{4}(?!_)|(?<!\*)\*\*[ \t]+\*\*(?!\*)|(?<![\w`])``(?![\w`])"),
    "dangling_clause": re.compile(r"(?:\A|\n[ \t]*\n[ \t]*|(?<=\w{3}[.!?])[ \t]+)[Dd]ass\b"),
}


def seams(text):
    """Joints a deletion or a partial rewrite typically damages. Compared before and after an edit, never in absolute terms."""
    return Counter({name: len(pattern.findall(text)) for name, pattern in SEAMS.items()})


def seam_regression(before, start, end, after_text):
    """The first kind of joint damage an edit at before[start:end] introduced, or None. Only the edited neighbourhood counts."""
    delta = len(after_text) - len(before)
    left, right = max(0, start - 60), min(len(before), end + 60)
    old, new = seams(before[left:right]), seams(after_text[left:right + delta])
    return next((name for name in SEAMS if new[name] > old[name]), None)


CAPITALISED = re.compile(r"[A-ZÄÖÜ][\wäöüß'’-]*")


def inner_capitals(text):
    """Capitalised words that do not open a sentence: names, acronyms and, in German, nouns."""
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        words = re.findall(r"[\wäöüß'’-]+", sentence)
        found += [word for word in words[1:] if CAPITALISED.fullmatch(word)]
    return found


def same_word(left, right):
    """Inflected forms of one word (Pendler/Pendlern, tank/tanks) count as the same."""
    short = min(len(left), len(right))
    return left == right or (short >= 4 and left[:short - 3 if short > 6 else 4] == right[:short - 3 if short > 6 else 4])


def edit_problem(before, after):
    """Why an edit of ordinary text is unsafe, or None. A sentence may be reworded; facts, names and size may not move."""
    if len(after) > max(240, 2 * len(before) + 80):
        return "quality_edit_too_long"
    if Counter(NUMBER.findall(before)) != Counter(NUMBER.findall(after)):
        return "quality_number_changed"
    old = inner_capitals(before)
    if any(not any(same_word(word, known) for known in old) for word in inner_capitals(after)):
        return "quality_name_added"
    return None


def sentence_around(text, start, end):
    """The whole sentence a defect sits in, as exact text the model can copy."""
    found = [(at + len(mark), mark) for mark in (". ", "! ", "? ", "\n") if (at := text.rfind(mark, 0, start)) >= 0]
    begin = max((position for position, _ in found), default=0)
    stop = re.search(r"[.!?](?=\s|$)|\n", text[end:])
    return text[begin:end + (stop.end() if stop else len(text) - end)].strip()


WINDOW_TARGET = 1100   # characters: a few paragraphs, short enough that the model reads every sentence
WINDOW_LIMIT = 2200
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")


def windows(text):
    """Contiguous slices of the text, each a few whole paragraphs. They cover every character exactly once, so a finding in a
    window maps back to the text by its start offset. A long paragraph is cut at sentence ends."""
    cuts = [m.end() for m in PARAGRAPH_BREAK.finditer(text)] + [len(text)]
    pieces, begin = [], 0
    for end in cuts:
        if end <= begin:
            continue
        paragraph = text[begin:end]
        if len(paragraph) > WINDOW_LIMIT:
            sentence_ends = [begin + m.end() for m in re.finditer(r"[.!?](?=\s)\s*", paragraph)]
            at = begin
            for stop in sentence_ends + [end]:
                if stop - at >= WINDOW_TARGET or stop == end:
                    pieces.append((at, stop))
                    at = stop
        else:
            pieces.append((begin, end))
        begin = end
    merged = []
    for start, stop in pieces:
        if merged and merged[-1][1] - merged[-1][0] < WINDOW_TARGET and stop - merged[-1][0] <= WINDOW_LIMIT:
            merged[-1] = (merged[-1][0], stop)
        else:
            merged.append((start, stop))
    return [(start, text[start:stop]) for start, stop in merged if text[start:stop].strip()]


def around(text, items, margin=500):
    """The passages around the findings, merged where they overlap, instead of the whole text."""
    spans = sorted((max(0, item["start"] - margin), min(len(text), item["end"] + margin)) for item in items if "start" in item)
    merged = []
    for begin, end in spans:
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([begin, end])
    return "\n[…]\n".join(text[begin:end] for begin, end in merged)


class Pipeline:
    """One run of the quality standard for one text.

    `ask(role, prompt, schema, tokens)` returns (data, evidence) for the roles `audit`, `verify` and `fix`.
    It raises a recoverable error when the model is unavailable. Evidence is what the transport proved
    about the call: model alias, skill versions and the hashes of the rules that were loaded."""

    def __init__(self, ask, tools, lang, *, locale=None, kind="general", terms=(), constraints=None,
                 skill_version=None, max_passes=MAX_PASSES, progress=None):
        self.ask_model, self.tools, self.lang = ask, tools, lang
        self.progress = progress or (lambda phase: None)
        self.locale = locale_for(lang, locale)
        self.profile = profile_for(kind)
        self.terms = tuple(term for term in terms if isinstance(term, str) and term.strip())
        self.constraints = constraints
        self.skill_version = skill_version
        self.max_passes = max(0, min(MAX_PASSES, max_passes))
        self.calls, self.limits, self.cache = [], [], {}

    # ---- model transport -----------------------------------------------------
    def ask(self, role, prompt, schema, tokens):
        data, evidence = self.ask_model(role, prompt, schema, tokens)
        if not isinstance(data, dict):
            raise PlanError("quality_model_format")
        self.calls.append({"role": role, "model": (evidence or {}).get("model"),
                           "skill_version": (evidence or {}).get("skill_version"),
                           "skills": (evidence or {}).get("skills", []), "mode": (evidence or {}).get("mode")})
        return data

    # ---- audit -----------------------------------------------------------------
    def audit(self, text):
        """Deterministic rules, mechanical repairs, orthography and the language-model audit, all verified."""
        protected = spans_of(text, self.tools)
        findings = self.rule_findings(text) + self.local_findings(text) + self.orthography(text)
        model = self.model_findings(text)
        findings += model["findings"]
        for item in findings:
            if "start" in item and item["status"] != "info" and any(item["start"] < b and item["end"] > a for a, b in protected):
                item.update(status="info", severity="note", note="protected_span")
        self.verify(text, findings)
        for number, item in enumerate(findings, 1):
            item["id"] = f"f{number}"
            item["automatic"] = self.is_automatic(item)
        return {"findings": findings, "llm_completed": model["completed"], "windows": model["windows"]}

    def is_automatic(self, item):
        if item["status"] != "confirmed" or "start" not in item:
            return False
        if item["source"] == "rule":
            return item["rule_category"] in self.profile.actionable
        if item["source"] == "local":
            return item.get("edit") is not None
        if item["category"] == "naturalness":
            return self.profile.naturalness
        return item["category"] in ("grammar", "punctuation", "repetition")

    def rule_findings(self, text):
        offsets = [0]
        for line in text.splitlines():
            offsets.append(offsets[-1] + len(line) + 1)
        found = []
        for raw in self.tools.rules.scan(text, self.lang, max_findings=400):
            data = raw.as_dict()
            item = {"source": "rule", "rule": data["rule"], "rule_category": data["category"], "category": "style",
                    "issue": data["why"], "correction": data["fix"] or "Rephrase without this wording and keep every fact.",
                    "quote": data["excerpt"], "status": "confirmed" if data["rule"] not in SKIPPED_RULES else "info",
                    "severity": "note", "method": "human-writing:" + data["rule"]}
            if item["status"] == "confirmed" and 0 < data["line"] <= len(offsets):
                begin = offsets[data["line"] - 1] + data["col"] - 1
                words = data["excerpt"].split()
                match = re.compile(r"\s+".join(map(re.escape, words))).match(text, begin) if words else None
                if match:
                    item.update(start=match.start(), end=match.end(), quote=match[0])
            if "start" not in item:
                item["status"] = "info"
            found.append(item)
        return found

    def local_findings(self, text):
        checks, edits = self.tools.fiction.local_quality(text, ())
        found = []
        for check in checks:
            edit = next((e for e in edits if e["start"] == check["start"] and e["before"] == check["quote"]), None)
            found.append({"source": "local", "rule_category": check["category"], "category": check["category"],
                          "issue": check["issue"], "correction": check["correction"], "quote": check["quote"],
                          "start": check["start"], "end": check["end"], "status": "confirmed", "severity": "note",
                          "method": "human-writing:local_quality", "edit": edit})
        return found

    def orthography(self, text):
        function = getattr(self.tools.language, "editorial_orthography", None)
        proposals = function(text, self.lang) if function else []
        return [{"source": "orthography", "rule_category": "grammar", "category": "grammar", "issue": item["issue"],
                 "correction": item["correction"], "action": "replace", "replacement": item["correction"],
                 "quote": item["quote"], "start": item["start"], "end": item["end"], "status": "unconfirmed",
                 "severity": "note", "method": "human-writing:" + item["rule"]} for item in proposals]

    def model_findings(self, text):
        """The language audit in windows. A window that did not change keeps its earlier result."""
        findings, completed, count = [], True, 0
        protected = spans_of(text, self.tools)
        for start, window in windows(text):
            count += 1
            if covered(protected, start, start + len(window)) >= .9 * len(window):
                continue   # code, quotations and markup only: nothing for a language audit to read
            key = digest(window)
            if key not in self.cache:
                try:
                    self.cache[key] = self.audit_window(window)
                except RECOVERABLE as exc:
                    completed = False
                    self.limits.append("llm_audit_unavailable:" + (str(exc) if isinstance(exc, PlanError) else type(exc).__name__))
                    continue
            findings += [{**item, "start": item["start"] + start, "end": item["end"] + start}
                         if "start" in item else dict(item) for item in self.cache[key]]
        return {"findings": findings, "completed": completed, "windows": count}

    def audit_window(self, window):
        language, rules = LANGUAGE_NAMES[self.locale], LANGUAGE_RULES[self.lang]
        data = self.ask("audit",
            f"Audit this passage of a text written in {language}. {rules} {VARIANT_RULES[self.locale]} {self.profile.guidance} "
            "Report only objective defects you can demonstrate in the passage: spelling, grammar, punctuation, unnatural "
            "or unclear phrasing, accidental repetition of wording or of a sentence pattern, and a sentence that only repeats another one. "
            "Preserve deliberate devices, voice, quotations, names, numbers, technical terms, code and Markdown. "
            "In quote copy the shortest exact phrase that is unique in the passage. In issue name the concrete rule that is "
            "broken in a complete sentence. In action use replace when the quote can be fixed by replacing it, delete when the "
            "quote only has to go, rewrite when the fix needs more than the quote. In replacement give the exact new text "
            "for replace, otherwise an empty string. Use severity note for optional style. Return an empty list when the "
            "passage is clean.\nPASSAGE\n" + window,
            story.schema({"findings": array(story.schema({
                **fields(("quote", "issue", "replacement")),
                "category": enum(("grammar", "punctuation", "naturalness", "repetition")),
                "severity": enum(("editorial", "note")), "action": enum(("replace", "delete", "rewrite"))}),
                FINDINGS_PER_WINDOW)}), 1500)
        found = []
        for raw in data.get("findings", [])[:FINDINGS_PER_WINDOW]:
            if not isinstance(raw, dict):
                continue
            quote, issue = str(raw.get("quote", "")), str(raw.get("issue", ""))
            span = self.tools.fiction.evidence(window, quote) if window.count(quote) == 1 else None
            reason = ("quote_not_unique" if quote and window.count(quote) > 1 else "quote_not_found" if not span
                      else "issue_not_explained" if not self.tools.fiction.substantive(issue)
                      else "optional_style" if raw.get("severity") != "editorial" else None)
            item = {"source": "model", "category": raw.get("category") if raw.get("category") in (
                        "grammar", "punctuation", "naturalness", "repetition") else "naturalness", "rule_category": None,
                    "issue": issue, "quote": quote, "action": raw.get("action"), "replacement": str(raw.get("replacement", "")),
                    "correction": str(raw.get("replacement", "")), "method": "model_audit",
                    "status": "unconfirmed", "severity": "note"}
            if reason is None:
                item.update(start=span["start"], end=span["end"], severity="editorial", eligible=True)
            else:
                item.update(status="info", note=reason)
            found.append(item)
        return found

    def judge(self, role, brief, text, items):
        """One verdict round over anchored findings. Returns {item index: (status, reason)} for the answered ones."""
        numbered = {str(i): item for i, item in enumerate(items)}
        data = self.ask(role, brief + "PASSAGES\n" + around(text, items) + "\nPROPOSED DEFECTS\n" + dump([
            {"index": key, **{field: item.get(field, "") for field in ("quote", "category", "issue", "action", "replacement")}}
            for key, item in numbered.items()]),
            story.schema({"verdicts": {"type": "array", "minItems": len(items), "maxItems": len(items),
                "items": story.schema({"index": enum(list(numbered)), "status": enum(("confirmed", "unconfirmed", "refuted")),
                                       "reason": story.STR})}}), 2100)
        found = {}
        for verdict in data.get("verdicts", []):
            if isinstance(verdict, dict):
                found.setdefault(str(verdict.get("index")), []).append(verdict)
        return {key: (v[0]["status"], v[0]["reason"]) for key, v in found.items() if len(v) == 1 and v[0].get("status") in (
            "confirmed", "unconfirmed", "refuted") and self.tools.fiction.substantive(v[0].get("reason"))}

    def verify(self, text, findings):
        """Two independent rounds. The first asks whether a proposed defect is real. The second defends the original, because
        the verifier is the same local model as the auditor and their mistakes are correlated. A defect is confirmed only when
        both rounds confirm it. Rule hits are confirmed by their rule."""
        language = LANGUAGE_NAMES[self.locale]
        confirm = (f"Independently verify each proposed defect in a text written in {language}. {self.profile.guidance} "
                   "Confirm only an objective error of spelling, grammar, punctuation, an unnatural or wrong phrase, or accidental "
                   "repetition. The replacement has to keep the meaning, every fact, name, number and the sentence context. Optional "
                   "style, deliberate devices, dialogue and quotations are not errors. Confirm only when a competent editor would "
                   "certainly correct it. Where two forms are acceptable (capitalisation of a proper name or a descriptive noun, "
                   "regional or variant spelling, an optional comma, synonyms) answer unconfirmed. Ambiguity stays unconfirmed. "
                   "Explain the concrete rule. Return every index.\n")
        defend = (f"You defend the author of a text written in {language}. For each proposed defect try to show that the original "
                  "wording is acceptable: standard usage, a tense or number that fits the context the passage implies, a deliberate "
                  "device, a regional or variant form, an accepted idiom, or a matter of taste. Answer refuted when you can defend "
                  "it, unconfirmed when you are unsure, and confirmed only when no acceptable reading exists. Explain with the "
                  "context of the passage. Return every index.\n")
        pending = [item for item in findings if item["status"] == "unconfirmed" and "start" in item]
        for first in range(0, len(pending), BATCH):
            batch = pending[first:first + BATCH]
            try:
                verdicts = self.judge("verify", confirm, text, batch)
                for index, item in enumerate(batch):
                    if str(index) in verdicts:
                        item.update(status=verdicts[str(index)][0], verification=verdicts[str(index)][1],
                                    method=item["method"] + "+verified")
                survivors = [item for item in batch if item["status"] == "confirmed"]
                answers = self.judge("defend", defend, text, survivors) if survivors else {}
                for index, item in enumerate(survivors):
                    status, reason = answers.get(str(index), ("unconfirmed", "unanswered"))
                    if status != "confirmed":   # an answer the defender did not give is no confirmation either
                        item.update(status=status, verification=f"{item.get('verification', '')} Defence: {reason}".strip())
            except RECOVERABLE as exc:
                self.limits.append("verification_unavailable:" + (str(exc) if isinstance(exc, PlanError) else type(exc).__name__))
                for item in batch:
                    if item["status"] == "confirmed" and item["source"] != "rule":
                        item["status"] = "unconfirmed"
        for item in findings:
            if item["status"] == "unconfirmed" and item.get("source") == "orthography":
                item["status"] = "info"
                item["note"] = "orthography_unverified"

    # ---- fix -------------------------------------------------------------------
    def fix(self, text, findings):
        """Exact span edits for confirmed findings. Mechanical repairs first, then declared and model edits."""
        rejected, applied, stage = [], [], text
        local = [item["edit"] for item in findings if item["automatic"] and item["source"] == "local"]
        if local:
            stage, accepted, refused = correction.patch_text_partial(
                text, local, [], self.tools.fiction, local=True, base_hash=digest(text))
            rejected += [{"before": r["edit"]["before"][:160], "error": r["error"]} for r in refused]
            applied += [{"before": e["before"][:160], "after": e["after"][:160],
                         "finding": next((f["id"] for f in findings if f.get("edit") == e), None)} for e in accepted]
        targets = []
        for item in findings:
            if not item["automatic"] or item["source"] == "local":
                continue
            span = self.tools.fiction.evidence(stage, item["quote"]) if stage.count(item["quote"]) == 1 else None
            if span:
                targets.append({**span, "category": item["category"], "status": "confirmed", "id": item["id"], "item": item})
        edits = []
        for target in targets[:EDITS_PER_PASS]:
            item = target["item"]
            if item.get("action") in ("replace", "delete") and (item.get("replacement") or item["action"] == "delete") \
                    and item["replacement"] != item["quote"]:
                edits.append({"before": item["quote"], "after": item["replacement"] if item["action"] == "replace" else "",
                              "finding": item["id"]})
        asked = [t for t in targets[:EDITS_PER_PASS] if t["id"] not in {e["finding"] for e in edits}]
        if asked:
            try:
                data = self.ask("fix",
                    f"Provide exact before/after edits for these confirmed defects of a text written in {LANGUAGE_NAMES[self.locale]}. "
                    f"{self.profile.guidance} For each defect copy the whole sentence given in sentence exactly as before, "
                    "and write after as the corrected sentence. When the defect is filler or an empty lead-in, rewrite the "
                    "sentence so that it says the same thing directly, or delete the whole sentence (after is empty) when it "
                    "carries no fact. The text around the sentence stays as it is, so after must be a complete, grammatical "
                    "sentence that starts with a capital letter and ends with its punctuation. Never leave a fragment, a clause "
                    "that starts with a conjunction, a lowercase sentence start or a doubled space. Change only what the defect "
                    "names. Keep every fact, name, number, quotation, link, code and Markdown. Do not add information. "
                    "Return no edit for a defect that cannot be fixed without changing a fact.\nDEFECTS\n" + dump([
                        {"id": t["id"], "quote": t["quote"], "sentence": sentence_around(stage, t["start"], t["end"]),
                         "issue": t["item"]["issue"], "hint": t["item"]["correction"]} for t in asked])
                    + "\nPASSAGES\n" + around(stage, asked),
                    story.schema({"edits": array(story.schema({**fields(("before", "after")), "id": story.STR}), EDITS_PER_PASS)}), 1800)
                edits += [{"before": e["before"], "after": e["after"], "finding": e.get("id")}
                          for e in data.get("edits", []) if isinstance(e, dict) and isinstance(e.get("before"), str)
                          and isinstance(e.get("after"), str)]
            except RECOVERABLE as exc:
                self.limits.append("fix_unavailable:" + (str(exc) if isinstance(exc, PlanError) else type(exc).__name__))
        protected = spans_of(stage, self.tools)
        usable, seen = [], set()
        for edit in edits:
            if (edit["before"], edit["after"]) in seen:
                continue   # one repair that several findings point to is one edit
            seen.add((edit["before"], edit["after"]))
            start = stage.find(edit["before"]) if edit["before"] else -1
            if start < 0:
                rejected.append({"before": edit["before"][:160], "error": "quality_edit_not_found"})
            elif any(start < b and start + len(edit["before"]) > a for a, b in protected):
                rejected.append({"before": edit["before"][:160], "error": "quality_protected_span"})
            elif any(edit["before"].count(term) != edit["after"].count(term) for term in self.terms):
                rejected.append({"before": edit["before"][:160], "error": "quality_term_changed"})
            elif (damage := seam_regression(stage, start, start + len(edit["before"]),
                                            stage[:start] + edit["after"] + stage[start + len(edit["before"]):])):
                rejected.append({"before": edit["before"][:160], "error": "quality_seam_" + damage})
            else:
                usable.append(edit)
        if usable:
            patched, accepted, refused = self.apply(stage, usable, targets)
            rejected += refused
            done = {(e["before"], e["after"]) for e in accepted}

            def owner(edit):
                return next((t["id"] for t in targets if t["quote"] in edit["before"] or edit["before"] in t["quote"]),
                            edit.get("finding"))

            applied += [{"before": e["before"][:160], "after": e["after"][:160], "finding": owner(e)}
                        for e in usable if (e["before"], e["after"]) in done]
            stage = patched
        return stage, applied, rejected

    def apply(self, stage, edits, targets):
        """Apply validated edits. Factual texts use the studio's strict patch contract, which also pins every capitalised
        word. Ordinary text uses the pipeline's own contract, which tells names from German nouns."""
        plain = [{"before": e["before"], "after": e["after"]} for e in edits]
        if self.profile.factual:
            patched, accepted, refused = correction.patch_text_partial(
                stage, plain, [], self.tools.fiction, targets=targets, base_hash=digest(stage), article=True,
                language=self.lang, language_tools=self.tools.language)
            return patched, accepted, [{"before": r["edit"]["before"][:160], "error": r["error"]} for r in refused]
        accepted, refused, spans = [], [], []
        budget = max(400, len(stage) // 3)
        for edit in plain:
            start = stage.find(edit["before"])
            end = start + len(edit["before"])
            problem = edit_problem(edit["before"], edit["after"])
            if problem is None and stage.count(edit["before"]) != 1:
                problem = "quality_edit_not_unique"
            elif problem is None and any(start < b and end > a for a, b in spans):
                problem = "quality_edit_overlaps"
            elif problem is None and not any(start < t["end"] and end > t["start"] for t in targets):
                problem = "quality_edit_untargeted"
            elif problem is None and sum(b - a for a, b in spans) + (end - start) > budget:
                problem = "quality_edit_budget"
            if problem:
                refused.append({"before": edit["before"][:160], "error": problem})
            else:
                accepted.append(edit)
                spans.append((start, end))
        patched = stage
        for edit in sorted(accepted, key=lambda e: stage.find(e["before"]), reverse=True):
            at = stage.find(edit["before"])
            patched = patched[:at] + edit["after"] + patched[at + len(edit["before"]):]
        local = self.tools.fiction.local_quality
        if accepted and len(local(patched, [])[0]) > len(local(stage, [])[0]):
            return stage, [], refused + [{"before": e["before"][:160], "error": "quality_mechanical_regression"} for e in accepted]
        return patched, accepted, refused

    # ---- run -------------------------------------------------------------------
    def counts(self, report):
        findings = report["findings"]
        return {status: sum(item["status"] == status for item in findings) for status in ("confirmed", "unconfirmed", "refuted", "info")} | {
            "automatic": sum(item["automatic"] for item in findings)}

    def accepts(self, before, after, reports):
        """A revision is kept when it left protected content and length alone, repaired a confirmed defect and
        introduced none. A defect counts as introduced only when its wording did not exist in the original: a model
        audit reports a limited, varying set per window, so a defect that was already there and only surfaced in the
        recheck must not discard the verified repairs."""
        if (changed := difference(before, after, self.terms)):
            return False, changed
        if self.constraints and check_text(after, self.constraints, self.tools.language)["issues"]:
            return False, "constraint_violated"
        old, new = seams(before), seams(after)
        if any(new[name] > old[name] for name in SEAMS):
            return False, "seam_damaged"
        was = [f for f in reports[before]["findings"] if f["automatic"]]
        now = [f for f in reports[after]["findings"] if f["automatic"]]
        introduced = [f for f in now if f["quote"] and f["quote"] not in before]
        if introduced:
            return False, "introduced_defect"
        resolved = [f for f in was if f["quote"] and f["quote"] not in after]
        return (True, None) if resolved else (False, "no_improvement")

    def run(self, text):
        original, current = text, text
        started = time.time()
        self.progress("validating")
        report = self.audit(current)
        first = report
        reports = {current: report}
        passes = []
        for number in range(1, self.max_passes + 1):
            if not any(item["automatic"] for item in report["findings"]):
                break
            self.progress("revising")
            candidate, applied, rejected = self.fix(current, report["findings"])
            entry = {"pass": number, "confirmed": self.counts(report)["confirmed"], "applied": applied, "rejected": rejected}
            if candidate == current:
                passes.append({**entry, "accepted": False, "reason": "no_valid_edit"})
                break
            recheck = self.audit(candidate)
            reports[candidate] = recheck
            ok, why = self.accepts(current, candidate, reports)
            entry.update(accepted=ok, reason=why, recheck=self.counts(recheck))
            passes.append(entry)
            if not ok:
                break
            current, report = candidate, recheck
        return self.finalize(original, current, first, report, passes, time.time() - started)

    def finalize(self, original, final, first, last, passes, seconds):
        """Corrected and remaining are read off the final text. A confirmed defect counts as corrected only when its anchored
        wording is gone, and as remaining while its wording is still there, whether or not the recheck reported it again:
        a model audit does not repeat itself reliably."""
        confirmed = [f for f in first["findings"] if f["status"] == "confirmed" and f["quote"]]
        corrected = [f for f in confirmed if f["quote"] not in final]
        carried = [f for f in confirmed if f["quote"] in final]
        rechecked = [f for f in last["findings"] if f["status"] in ("confirmed", "unconfirmed")]
        open_items = {}
        for f in carried + rechecked:
            open_items.setdefault(f["quote"], f)
        remaining = [{"category": f["category"], "status": f["status"], "quote": f["quote"][:160], "issue": f["issue"][:240]}
                     for f in open_items.values()][:40]
        applied = [edit for entry in passes if entry["accepted"] for edit in entry["applied"]]
        revised = [entry for entry in passes if entry["reason"] != "no_valid_edit"]
        skills, seen = [], set()
        for call in self.calls:
            for skill in call["skills"]:
                marker = (skill["name"], skill["version"], tuple(rule["sha256"] for rule in skill["rules"]))
                if marker not in seen:
                    seen.add(marker)
                    skills.append(skill)
        script = getattr(self.tools.rules, "__file__", None)
        receipt = {
            "pipeline": {"name": "human-writing-quality", "version": VERSION},
            "language": self.locale, "profile": self.profile.name, "register": self.profile.register,
            "skill_version": self.skill_version or next((c["skill_version"] for c in self.calls if c["skill_version"]), None),
            "skills": skills, "rules_sha256": digest(Path(script).read_text(encoding="utf-8")) if script else None,
            "audit": {"completed": bool(first["llm_completed"]), "rules": True, "windows": first["windows"],
                      "models": sorted({c["model"] for c in self.calls if c["model"]}), "calls": len(self.calls),
                      "findings": self.counts(first), "limits": list(dict.fromkeys(self.limits))},
            "passes": passes,
            "findings": [{key: f.get(key) for key in ("id", "source", "category", "status", "automatic", "method")}
                         | {"quote": f["quote"][:160], "issue": f["issue"][:240], "verification": (f.get("verification") or "")[:240],
                          "note": f.get("note")}
                         for f in first["findings"] if f["status"] != "info" or f["source"] != "rule"][:60],
            "recheck": {"required": bool(revised), "completed": all(p.get("recheck") is not None for p in revised),
                        "remaining": remaining, "counts": self.counts(last)},
            "final": {"changed": final != original, "applied": len(applied), "confirmed_before": len(confirmed),
                      "corrected": len(corrected), "confirmed_after": sum(f["status"] == "confirmed" for f in open_items.values()),
                      "sha256_before": digest(original),
                      "sha256_after": digest(final), "seconds": round(seconds, 2)},
        }
        return {"text": final, "changed": final != original, "receipt": receipt, "remaining": remaining}


def summary(receipt):
    """The facts a person needs from a receipt, without claiming more than was executed."""
    audit, final = receipt["audit"], receipt["final"]
    return {"audit_completed": audit["completed"], "rules_checked": audit["rules"], "skill_loaded": bool(receipt["skills"]),
            "skill_version": receipt["skill_version"], "confirmed": final["confirmed_before"],
            "corrected": final["corrected"],
            "remaining": len(receipt["recheck"]["remaining"]), "passes": len(receipt["passes"]), "changed": final["changed"],
            "rechecked": receipt["recheck"]["completed"] if receipt["recheck"]["required"] else None, "limits": audit["limits"]}
