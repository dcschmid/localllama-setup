#!/usr/bin/env python3
"""The central Human Writing quality pipeline across languages, text kinds and failure modes.

The language model is scripted: it audits like an editor who knows the planted defects of each text.
Everything else is real: the skill's rule registry, anchoring, verification flow, the patch validator,
the protected-content checks, the pass limit and the receipt."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_quality as quality
from creative_studio_plan import PlanError

SKILLS = Path.home() / "dev/github/skillset/skills"
TOOLS = quality.load_tools(SKILLS)
EVIDENCE = {"model": "scripted", "skill_version": "1.3.1", "mode": "audit",
            "skills": [{"name": "human-writing", "version": "1.3.1", "rules": [{"reference": "style-de", "sha256": "a" * 64}]}]}


class Editor:
    """A scripted model. `defects` are (quote, replacement, issue, category, action) the editor reports when it sees the quote;
    `genuine` are the quotes the verifier confirms; `fixes` map a defect quote to the (before, after) edit that repairs it."""

    def __init__(self, defects=(), genuine=None, fixes=None, per_audit=6, fail=None, invented=(), evidence=None, once=False, defended=(),
                 proofread=None, confirm_all=False, noted=()):
        self.defects, self.fixes, self.per_audit, self.fail = list(defects), fixes or {}, per_audit, fail
        self.proofread, self.confirm_all = proofread or {}, confirm_all
        self.noted = list(noted)
        self.once, self.audited, self.defended = once, False, set(defended)
        self.invented, self.evidence = list(invented), evidence or EVIDENCE
        self.genuine = {d[0] for d in self.defects} if genuine is None else set(genuine)
        self.calls = []

    def __call__(self, role, prompt, schema, tokens):
        self.calls.append((role, prompt))
        if self.fail:
            raise self.fail
        if role == "proofread":
            window = prompt.split("\nPASSAGE\n", 1)[1]
            for before, after in self.proofread.items():
                window = window.replace(before, after)
            return {"text": window}, self.evidence
        if role == "choose":
            a, b = prompt.split("\nA: ", 1)[1].split("\nB: ", 1)[0], prompt.split("\nB: ", 1)[1]
            pairs = [(q, r) for q, r, *_ in self.defects + self.invented + self.noted if r] + list(self.proofread.items())
            for before, after in pairs:
                for original, proposed, new_letter, old_letter in ((a, b, "B", "A"), (b, a, "A", "B")):
                    if before in original and original.replace(before, after, 1) == proposed:
                        answer = (old_letter if before in self.defended else
                                  new_letter if self.confirm_all or before in self.genuine else "both")
                        return {"answer": answer, "reason": "Compared against the rule in this sentence."}, self.evidence
            return {"answer": "both", "reason": "Both readings are acceptable in this sentence."}, self.evidence
        if role == "audit":
            window = prompt.split("\nPASSAGE\n", 1)[1]
            if self.noted:
                return {"findings": [{"quote": q, "issue": issue, "replacement": r, "category": c, "severity": "note", "action": a}
                                     for q, r, issue, c, a in self.noted if q in window]}, self.evidence
            seen = [d for d in self.defects if d[0] in window][:self.per_audit] if not (self.once and self.audited) else []
            self.audited = True
            return {"findings": [{"quote": q, "issue": issue, "replacement": r, "category": c, "severity": "editorial", "action": a}
                                 for q, r, issue, c, a in self.invented] + [{"quote": q, "issue": issue, "replacement": r, "category": c,
                                  "severity": "note" if c == "style-note" else "editorial", "action": a}
                                 for q, r, issue, c, a in seen if c != "style-note"] + [
                {"quote": q, "issue": issue, "replacement": "", "category": "repetition", "severity": "note", "action": "rewrite"}
                for q, r, issue, c, a in seen if c == "style-note"]}, self.evidence
        if role in ("verify", "defend"):
            items = json.loads(prompt.split("\nPROPOSED DEFECTS\n", 1)[1])
            def status(item):
                if role == "defend" and item["quote"] in self.defended:
                    return "refuted"
                return "confirmed" if self.confirm_all or item["quote"] in self.genuine else "unconfirmed"
            return {"verdicts": [{"index": i["index"], "reason": "Checked against the rule in the passage.",
                                  "status": status(i)} for i in items]}, self.evidence
        if role == "fix":
            wanted = json.loads(prompt.split("\nDEFECTS\n", 1)[1].split("\nPASSAGES\n", 1)[0])
            shown = prompt.split("\nPASSAGES\n", 1)[1]
            edits = []
            for item in wanted:
                for key, (before, after) in self.fixes.items():
                    if (key in item["quote"] or item["quote"] in key) and before in shown:
                        edits.append({"id": item["id"], "before": before, "after": after})
            return {"edits": edits}, self.evidence
        raise AssertionError(role)

    def roles(self):
        """The calls after the proofread pass, which every window gets and which is silent unless a test scripts it."""
        return [role for role, _ in self.calls if role != "proofread"]

    def all_roles(self):
        return [role for role, _ in self.calls]


def run(text, lang, kind, editor, **options):
    return quality.Pipeline(editor, TOOLS, lang, kind=kind, skill_version="1.3.1", **options).run(text)


def edit(text, *replacements):
    for before, after in replacements:
        assert text.count(before) == 1, before
        text = text.replace(before, after)
    return text


CASES = {}


def case(name, lang, kind, text, defects, fixes, expected, **options):
    CASES[name] = dict(lang=lang, kind=kind, text=text, defects=defects, fixes=fixes, expected=expected, options=options)


# 1. German description with a filler opener and a case error
DE_SHOP = ("Die Fahrradwerkstatt Kettenglied liegt direkt am Marktplatz und repariert Räder aller Art. In der heutigen schnelllebigen Welt "
           "ist es wichtig zu beachten, dass ein Fahrrad zuverlässig sein muss. Wegen den vielen Pendlern bleibt die Werkstatt von sieben "
           "bis neunzehn Uhr geöffnet. Eine Inspektion kostet 49 Euro, ein neuer Schlauch 12 Euro. Wer ein Rad abgibt, bekommt es meist "
           "noch am selben Tag zurück.")
FILLER_DE = "In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass ein Fahrrad zuverlässig sein muss. "
case("de_general", "de", "general", DE_SHOP,
     [("Wegen den vielen Pendlern", "Wegen der vielen Pendler", "Nach der Präposition 'wegen' steht im Standarddeutschen der Genitiv.", "grammar", "replace")],
     {"In der heutigen schnelllebigen Welt": (FILLER_DE, "")},
     edit(DE_SHOP, (FILLER_DE, ""), ("Wegen den vielen Pendlern", "Wegen der vielen Pendler")), terms=["Kettenglied"])

# 2. English description with a filler and an agreement error
EN_GARDEN = ("The Riverside Community Garden gives neighbors a place to grow vegetables together. It's important to note that anyone can join, "
             "and there is many free plots available this spring. Plots measure 3 by 4 meters, and the annual fee is $20. Volunteers meet "
             "every Saturday at 9:00 to water the beds and swap seeds.")
case("en_general", "en", "general", EN_GARDEN,
     [("there is many free plots", "there are many free plots", "The plural noun 'plots' needs 'are'.", "grammar", "replace")],
     {"It's important to note": ("It's important to note that anyone", "Anyone")},
     edit(EN_GARDEN, ("It's important to note that anyone", "Anyone"), ("there is many free plots", "there are many free plots")),
     terms=["Riverside Community Garden"])

# 3. German fiction: dialect speech, fragments and a verb agreement error
DE_STORY = ("Der Nebel lag schwer über dem See. Mara blieb stehen. Nacht. Kalt. Still.\n\n"
            "„Wat willste hier, Mädchen?“, brummte der Fährmann und spuckte aus. „Is doch längst dunkel.“\n\n"
            "Sie standen am Ufer und starrte auf das schwarze Wasser, bis die Glocke im Dorf schlug.")
case("de_story", "de", "story", DE_STORY,
     [("und starrte auf", "und starrten auf", "Das Subjekt 'Sie standen' verlangt die Pluralform 'starrten'.", "grammar", "replace"),
      ("Nacht. Kalt. Still.", "", "Mehrere Satzfragmente stehen hintereinander ohne Verb.", "style-note", "rewrite"),
      ("Wat willste hier", "Was willst du hier", "Die direkte Rede sollte standardsprachlich geschrieben werden.", "grammar", "replace")],
     {}, edit(DE_STORY, ("und starrte auf", "und starrten auf")), genuine=["und starrte auf", "Wat willste hier"])

# 4. English fiction: repetition as a device, dialect in speech, a tense error
EN_STORY = ("The harbor was empty by the time Ines arrived. Rain. Rain. Rain on the tin roofs, rain on the boats.\n\n"
            "\"Ain't nobody here but us, miss,\" said the old watchman, tipping his cap.\n\n"
            "She walk to the end of the pier and listened for the bell.")
case("en_story", "en", "story", EN_STORY,
     [("She walk to the end", "She walked to the end", "The past tense needs 'walked'.", "grammar", "replace"),
      ("Rain. Rain. Rain on the tin roofs", "", "The same word repeats three times in a row without variation.", "style-note", "rewrite"),
      ("Ain't nobody here but us", "There is nobody here but us", "The dialect in the dialogue should be standard English.", "grammar", "replace")],
     {}, edit(EN_STORY, ("She walk to the end", "She walked to the end")), genuine=["She walk to the end", "Ain't nobody here but us"])

# 5. German researched article: a missing comma, and a verifier that is fooled into changing a figure
DE_ARTICLE = ("# Wie Bienen Entfernungen messen\n\n"
              "Honigbienen schätzen Entfernungen über den optischen Fluss. Forschende der Universität Würzburg zeigten 1996 dass Bienen die "
              "Strecke an vorbeiziehenden Mustern messen, nicht an der Flugzeit. Die Tiere fliegen bis zu 5 Kilometer weit.\n\n"
              "> „Die Biene zählt, was sie sieht, nicht was sie fliegt.“\n\n"
              "Weitere Details stehen in der [Originalarbeit](https://example.org/bienen-1996).\n")
case("de_article", "de", "article", DE_ARTICLE,
     [("zeigten 1996 dass Bienen", "zeigten 1996, dass Bienen", "Vor 'dass' steht ein Komma.", "punctuation", "replace"),
      ("bis zu 5 Kilometer weit", "bis zu 10 Kilometer weit", "Die Angabe sollte laut Quelle genauer sein und auf zehn Kilometer lauten.", "grammar", "replace")],
     {}, edit(DE_ARTICLE, ("zeigten 1996 dass Bienen", "zeigten 1996, dass Bienen")),
     genuine=["zeigten 1996 dass Bienen", "bis zu 5 Kilometer weit"], terms=["Würzburg"])

# 6. English researched article with a calque and a link
EN_ARTICLE = ("## Why sourdough rises\n\n"
              "Sourdough starters hold wild yeast and lactic acid bacteria that ferment flour over several hours. Researchers at the University of "
              "Copenhagen reported in 2021 that starters from 500 bakeries shared a small core of microbes, as the "
              "[study summary](https://example.org/sourdough-2021) explains.\n\n"
              "Bakers have kept some starters alive since three decades, and the loaf keeps its sour edge.\n")
case("en_article", "en", "article", EN_ARTICLE,
     [("alive since three decades", "alive for three decades", "'Since' needs a point in time; a span takes 'for'.", "naturalness", "replace")],
     {}, edit(EN_ARTICLE, ("alive since three decades", "alive for three decades")), terms=["University of Copenhagen"])

# 7. German devlog: first-person voice stays, one comma is missing
DE_DEVLOG = ("## Devlog 12: Die Fahrphysik\n\n"
             "Diese Woche habe ich die Fahrphysik überarbeitet. Version `0.4.2` bringt weichere Kurven, die Trägheit der Karts wurde um 15 Prozent "
             "erhöht. Ich hab lange gebraucht, um das Driften zu verstehen und das Problem liegt am Reibwert nicht an der Kamera.\n\n"
             "Nächste Woche kommen die Boxengasse und der erste Streckenentwurf, versprochen!\n")
case("de_devlog", "de", "devlog", DE_DEVLOG,
     [("am Reibwert nicht an der Kamera", "am Reibwert, nicht an der Kamera", "Gegensatzpaare werden durch ein Komma getrennt.", "punctuation", "replace"),
      ("Ich hab lange gebraucht", "Ich habe lange gebraucht", "Die Kürzung klingt in einem Blogtext zu umgangssprachlich.", "style-note", "rewrite")],
     {}, edit(DE_DEVLOG, ("am Reibwert nicht an der Kamera", "am Reibwert, nicht an der Kamera")),
     genuine=["am Reibwert nicht an der Kamera"])

# 8. English technical text: code and versions stay; a verifier is fooled into a version bump and a code change
EN_TECH = ("# Retry helper\n\n"
           "The `retry()` function wraps a call and runs it again when it fails. In version v2.3.1 the default is 3 attempts with a delay of 200 ms.\n\n"
           "```python\ndef retry(fn, attempts=3, delay=0.2):\n    for _ in range(attempts):\n        try:\n            return fn()\n"
           "        except OSError:\n            time.sleep(delay)\n```\n\n"
           "The function return the result of the first call that succeeds. Install it with `pip install retrykit==2.3.1`.\n")
case("en_technical", "en", "technical", EN_TECH,
     [("The function return the result", "The function returns the result", "Third person singular needs the -s.", "grammar", "replace"),
      ("attempts=3", "attempts=5", "The default number of attempts should be higher than three for network calls.", "grammar", "replace"),
      ("version v2.3.1 the default", "version v2.3.2 the default", "Die Dokumentation sollte auf die neueste veröffentlichte Version verweisen.", "grammar", "replace")],
     {}, edit(EN_TECH, ("The function return the result", "The function returns the result")),
     genuine=["The function return the result", "attempts=3", "version v2.3.1 the default"])

# 9. German website copy with Markdown, promo wording and a typo
DE_SITE = ("# Studio Nordlicht\n\n"
           "Wir sind ein **revolutionäres** Entwicklerstudio, das nahtlos integrierte Spielerlebnisse schafft. Unser Team sitzt in "
           "[Kiel](https://example.com/kiel) und arbeitet seit 2019 an Rennspielen.\n\n"
           "## Was wir tun\n\n- Prototypen in zwei Wochen\n- Musik und Sounddesign\n- Betreuung nach dem Release\n\n"
           "Schreib uns: [kontakt@example.com](mailto:kontakt@example.com). Wir antworten inerhalb von zwei Werktagen.\n")
PROMO_BEFORE = "ein **revolutionäres** Entwicklerstudio, das nahtlos integrierte Spielerlebnisse schafft"
case("de_website", "de", "website", DE_SITE,
     [("inerhalb von zwei", "innerhalb von zwei", "Das Wort heißt korrekt 'innerhalb' und wird mit zwei n geschrieben.", "grammar", "replace")],
     {"revolutionäres": (PROMO_BEFORE, "ein Entwicklerstudio, das Spielerlebnisse entwickelt"),
      "nahtlos integrierte": (PROMO_BEFORE, "ein Entwicklerstudio, das Spielerlebnisse entwickelt")},
     edit(DE_SITE, (PROMO_BEFORE, "ein Entwicklerstudio, das Spielerlebnisse entwickelt"), ("inerhalb von zwei", "innerhalb von zwei")),
     terms=["Nordlicht"])

# 10. English text with terms and a quotation that contains a flagged phrase
EN_TERMS = ("Our edge runtime executes WebAssembly modules inside isolated V8 contexts, which keeps cold starts under 5 ms. "
            "As CTO Dana Whitfield put it: “Seamlessly integrating third-party modules is the whole point of this design.”\n\n"
            "The scheduler assigns each request to a worker based on a consistent hash of the tenant ID. This avoid hot spots when a single "
            "tenant sends a burst of traffic, and the p99 latency stays below 40 ms.\n")
case("en_terms_quotes", "en", "technical", EN_TERMS,
     [("This avoid hot spots", "This avoids hot spots", "Third person singular needs the -s.", "grammar", "replace"),
      ("Seamlessly integrating third-party", "Smoothly integrating third-party", "This wording sounds too promotional for a technical design document.", "naturalness", "replace")],
     {}, edit(EN_TERMS, ("This avoid hot spots", "This avoids hot spots")), genuine=["This avoid hot spots", "Seamlessly integrating third-party"],
     terms=["WebAssembly", "V8", "Dana Whitfield"])

# 11. A text that is already very good
EN_GOOD = ("The lighthouse on Cape Verde point was built in 1894 from local granite. Its lamp turned once every twelve seconds, and sailors "
           "could see it from nineteen miles out.\n\nThe keeper, Anselm Roe, kept a daily log. Most entries are short: wind, visibility, oil "
           "used. Once, in November, he wrote only one line: the sea was too loud to sleep.\n")
case("en_good", "en", "general", EN_GOOD, [], {}, EN_GOOD)
DE_GOOD = ("Am Hafen von Wismar legen jeden Morgen die Fischkutter an. Ihre Besatzungen laden Kisten voller Hering aus, die Händler "
           "warten schon mit Waagen und Eis. Gegen neun ist alles verkauft, und die Möwen teilen sich den Rest.\n")
case("de_good", "de", "general", DE_GOOD, [], {}, DE_GOOD)

# 12. A German text with several deliberate grammar and style problems; the editor reports one per audit
DE_MANY = ("Gestern haben wir ein neues Café eröffnet. Es ist wichtig zu betonen, dass es dort guten Kuchen gibt. Die Besitzerin heißt Lena "
           "und backt jeden Morgen selber. Der Laden hat 18 Plätze und öffnet um 8 Uhr. Wegen dem Wetter sitzt man draußen nur bei Sonne. "
           "Das Café liegt in der Gartenstraße 4 nahe dem Bahnhof und hat jeden Tag geöffnet, die Preise sind dabei fair.")
MANY_FILLER = "Es ist wichtig zu betonen, dass es dort guten Kuchen gibt. "
case("de_many", "de", "general", DE_MANY,
     [("Wegen dem Wetter", "Wegen des Wetters", "Nach der Präposition 'wegen' steht im Standarddeutschen der Genitiv.", "grammar", "replace"),
      ("backt jeden Morgen selber", "backt jeden Morgen selbst", "Das Wort 'selber' ist umgangssprachlich und wird in Texten meist durch 'selbst' ersetzt.", "naturalness", "replace"),
      ("geöffnet, die Preise sind", "geöffnet; die Preise sind", "Zwei vollständige Hauptsätze brauchen ein Semikolon oder einen Punkt dazwischen.", "punctuation", "replace")],
     {"Es ist wichtig zu betonen": (MANY_FILLER, "")},
     edit(DE_MANY, (MANY_FILLER, ""), ("Wegen dem Wetter", "Wegen des Wetters"), ("backt jeden Morgen selber", "backt jeden Morgen selbst")),
     per_audit=1, terms=["Gartenstraße 4"])

PROTECTED = {
    "de_article": ["„Die Biene zählt, was sie sieht, nicht was sie fliegt.“", "(https://example.org/bienen-1996)", "5 Kilometer", "1996"],
    "en_technical": ["attempts=3", "v2.3.1", "pip install retrykit==2.3.1", "def retry(fn, attempts=3, delay=0.2):"],
    "de_website": ["(https://example.com/kiel)", "(mailto:kontakt@example.com)", "- Musik und Sounddesign", "## Was wir tun", "2019"],
    "en_terms_quotes": ["“Seamlessly integrating third-party modules is the whole point of this design.”", "WebAssembly", "5 ms", "40 ms"],
    "de_story": ["„Wat willste hier, Mädchen?“", "„Is doch längst dunkel.“", "Nacht. Kalt. Still."],
    "en_story": ["Rain. Rain. Rain on the tin roofs", "\"Ain't nobody here but us, miss,\""],
    "de_devlog": ["`0.4.2`", "15 Prozent", "Ich hab lange gebraucht"],
    "en_article": ["(https://example.org/sourdough-2021)", "500 bakeries", "2021"],
    "de_general": ["49 Euro", "12 Euro", "Kettenglied"], "en_general": ["$20", "9:00", "3 by 4 meters"],
    "de_many": ["18 Plätze", "8 Uhr", "Gartenstraße 4"],
}


class MatrixTests(unittest.TestCase):
    def test_every_text_kind_in_both_languages_is_corrected_exactly(self):
        for name, c in CASES.items():
            with self.subTest(name):
                editor = Editor(c["defects"], c["options"].get("genuine"), c["fixes"], c["options"].get("per_audit", 6))
                options = {key: value for key, value in c["options"].items() if key in ("terms",)}
                result = run(c["text"], c["lang"], c["kind"], editor, **options)
                self.assertEqual(result["text"], c["expected"])
                self.assertEqual(result["changed"], c["text"] != c["expected"])
                for piece in PROTECTED.get(name, ()):
                    self.assertIn(piece, result["text"], f"{name}: {piece}")
                receipt = result["receipt"]
                self.assertEqual(receipt["final"]["sha256_after"], quality.digest(result["text"]))
                self.assertEqual(receipt["final"]["sha256_before"], quality.digest(c["text"]))
                self.assertTrue(receipt["audit"]["completed"])
                self.assertLessEqual(len(receipt["passes"]), 2)

    def test_a_text_that_is_already_good_is_left_alone_and_never_sent_to_a_fix_call(self):
        for name in ("en_good", "de_good"):
            editor = Editor()
            result = run(CASES[name]["text"], CASES[name]["lang"], "general", editor)
            self.assertFalse(result["changed"])
            self.assertEqual(editor.roles(), ["audit"], name)
            self.assertEqual(result["receipt"]["passes"], [])
            self.assertFalse(result["receipt"]["recheck"]["required"])
            self.assertTrue(quality.summary(result["receipt"])["audit_completed"])

    def test_deliberate_devices_and_dialogue_are_reported_but_not_edited(self):
        for name in ("de_story", "en_story"):
            c = CASES[name]
            result = run(c["text"], c["lang"], c["kind"], Editor(c["defects"], c["options"]["genuine"], c["fixes"]))
            statuses = {f["quote"]: f["status"] for f in result["receipt"]["findings"] if f["source"] == "model"}
            style = next(quote for quote in statuses if quote.startswith(("Nacht. Kalt", "Rain. Rain")))
            self.assertEqual(statuses[style], "info", name)
            self.assertIn(style, result["text"])

    def test_a_fooled_verifier_cannot_change_a_figure_a_version_or_code(self):
        # The verifier confirms every defect, including the ones that would change a fact. The patch validator must not.
        for name, forbidden, kept in (("de_article", "10 Kilometer", "bis zu 5 Kilometer weit"),
                                      ("en_technical", "v2.3.2", "version v2.3.1 the default")):
            c = CASES[name]
            result = run(c["text"], c["lang"], c["kind"], Editor(c["defects"], c["options"]["genuine"], c["fixes"]))
            self.assertNotIn(forbidden, result["text"], name)
            self.assertIn(kept, result["text"], name)
            first = result["receipt"]["passes"][0]
            self.assertEqual([r["error"] for r in first["rejected"]], ["production_patch_invalid"], name)
            self.assertEqual(len(first["applied"]), 1, name)   # only the genuine grammar or punctuation repair
        # A code defect is never even a candidate: the span is protected.
        tech = CASES["en_technical"]
        result = run(tech["text"], "en", "technical", Editor(tech["defects"], tech["options"]["genuine"], tech["fixes"]))
        code = next(f for f in result["receipt"]["findings"] if f["quote"] == "attempts=3")
        self.assertEqual((code["status"], code["automatic"], code["note"]), ("info", False, "protected_span"))
        self.assertIn("def retry(fn, attempts=3, delay=0.2):", result["text"])

    def test_a_single_word_term_survives_an_edit_that_would_rename_it(self):
        # The shared patch validator protects capitalised name pairs and figures. A one-word subject in an ordinary text
        # is protected only by the pipeline's term guard.
        text = ("Zeitlos ist eine kleine Bäckerei am Marktplatz. In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass Brot "
                "frisch sein muss. Zeitlos backt jeden Morgen um vier Uhr die ersten Brote.")
        before = "In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass Brot frisch sein muss. Zeitlos backt"
        rename = {"In der heutigen schnelllebigen Welt": (before, "Brot muss frisch sein. Zeitnah backt")}
        guarded = run(text, "de", "general", Editor(fixes=rename), terms=["Zeitlos"])
        self.assertEqual(guarded["text"], text)
        self.assertEqual([r["error"] for r in guarded["receipt"]["passes"][0]["rejected"]], ["quality_term_changed"])
        unguarded = run(text, "de", "general", Editor(fixes=rename))
        self.assertIn("Zeitnah", unguarded["text"])   # without the term the same edit is valid, so the guard is what stops it
        kept = run(text, "de", "general", Editor(fixes={"In der heutigen schnelllebigen Welt": (
            before, "Brot muss frisch sein. Zeitlos backt")}), terms=["Zeitlos"])
        self.assertEqual(kept["text"], text.replace("In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass Brot frisch sein muss.",
                                                    "Brot muss frisch sein."))

    def test_the_pass_limit_stops_a_text_with_more_defects_than_passes(self):
        c = CASES["de_many"]
        extra = c["defects"] + [("Gartenstraße 4 nahe", "Gartenstraße 4, nahe", "Vor dem nachgestellten Zusatz steht ein trennendes Komma.", "punctuation", "replace")]
        editor = Editor(extra, None, c["fixes"], per_audit=1)
        result = run(c["text"], "de", "general", editor)
        receipt = result["receipt"]
        self.assertEqual(len(receipt["passes"]), 2)
        self.assertTrue(all(entry["accepted"] for entry in receipt["passes"]))
        self.assertGreaterEqual(len(receipt["recheck"]["remaining"]), 1)   # reported, not hidden
        self.assertLessEqual(len(editor.roles()), 12)

    def test_a_fix_that_introduces_a_defect_is_rejected_whole_and_nothing_loops(self):
        # After the genitive repair the editor flags the new wording "Wegen des Wetters sitzt" as a defect.
        editor = Editor([("Wegen dem Wetter", "Wegen des Wetters", "Nach der Präposition 'wegen' steht der Genitiv.", "grammar", "replace"),
                         ("Wegen des Wetters sitzt", "Wegen des Wetter sitzt", "Der Genitiv Singular braucht hier ein s am Ende.", "grammar", "replace")],
                        None, {})
        result = run(CASES["de_many"]["text"], "de", "general", editor)
        receipt = result["receipt"]
        self.assertEqual([(entry["accepted"], entry["reason"]) for entry in receipt["passes"]], [(False, "introduced_defect")])
        self.assertIn("Wegen dem Wetter", result["text"])
        self.assertFalse(result["changed"])
        self.assertLessEqual(len(editor.roles()), 8)   # audit, verify, defend, audit, verify, defend: no further round

    def test_a_defect_that_only_surfaces_in_the_recheck_does_not_discard_verified_repairs(self):
        # The model audit reports one defect per window; the second existed all along and appears after the first repair.
        c = CASES["de_many"]
        editor = Editor(c["defects"], None, c["fixes"], per_audit=1)
        result = run(c["text"], "de", "general", editor, terms=c["options"]["terms"])
        self.assertEqual([entry["accepted"] for entry in result["receipt"]["passes"]], [True, True])
        self.assertNotIn("Wegen dem Wetter", result["text"])
        self.assertNotIn("selber", result["text"])

    def test_no_audit_is_claimed_when_the_model_is_not_available(self):
        for failure in (OSError("down"), PlanError("quality_model_format")):
            editor = Editor(CASES["de_general"]["defects"], None, CASES["de_general"]["fixes"], fail=failure)
            result = run(DE_SHOP, "de", "general", editor)
            receipt = result["receipt"]
            self.assertFalse(receipt["audit"]["completed"])
            self.assertTrue(any(limit.startswith("llm_audit_unavailable") for limit in receipt["audit"]["limits"]))
            self.assertTrue(receipt["audit"]["rules"])
            self.assertFalse(quality.summary(receipt)["audit_completed"])
            self.assertFalse(receipt["recheck"]["required"])
            self.assertEqual(result["text"], DE_SHOP)   # the rule hit needs a rewrite the model could not deliver

    def test_no_skill_is_claimed_when_the_transport_proved_none(self):
        bare = Editor(CASES["de_general"]["defects"], None, CASES["de_general"]["fixes"],
                      evidence={"model": "scripted", "skill_version": None, "skills": [], "mode": "audit"})
        result = run(DE_SHOP, "de", "general", bare)
        info = quality.summary(result["receipt"])
        self.assertEqual((info["skill_loaded"], info["skill_version"]), (False, "1.3.1"))
        self.assertEqual(result["receipt"]["skills"], [])
        loaded = run(DE_SHOP, "de", "general", Editor(CASES["de_general"]["defects"], None, CASES["de_general"]["fixes"]))
        self.assertTrue(quality.summary(loaded["receipt"])["skill_loaded"])

    def test_garbage_from_the_model_is_survived(self):
        class Garbage(Editor):
            def __call__(self, role, prompt, schema, tokens):
                self.calls.append((role, prompt))
                return {"findings": "nonsense", "verdicts": [None, 3], "edits": [{"before": 1}]}, EVIDENCE
        result = run(DE_SHOP, "de", "general", Garbage())
        self.assertEqual(result["text"], DE_SHOP)
        self.assertLessEqual(len(result["receipt"]["passes"]), 2)

    def test_unanchored_ambiguous_thin_and_optional_claims_are_never_applied(self):
        text = "Der Hafen ist groß. Der Hafen ist alt und der Hafen ist laut. Am Morgen kommen die Kutter an."
        invented = [("Satz den es nicht gibt", "x", "Ein erfundener Befund über einen Satz im Text.", "grammar", "replace"),
                    ("Der Hafen", "Das Hafen", "Der Artikel passt hier nicht zum Nomen im Satz.", "grammar", "replace"),
                    ("ist groß", "ist riesig", "Zu kurz.", "naturalness", "replace")]
        editor = Editor(invented=invented)
        result = run(text, "de", "general", editor)
        notes = {f["quote"]: f["note"] for f in result["receipt"]["findings"] if f["source"] == "model"}
        self.assertEqual(notes, {"Satz den es nicht gibt": "quote_not_found", "Der Hafen": "quote_not_unique", "ist groß": "issue_not_explained"})
        self.assertFalse(result["changed"])
        self.assertNotIn("fix", editor.roles())
        self.assertNotIn("verify", editor.roles())   # nothing anchored, so nothing to verify


class SeamTests(unittest.TestCase):
    """The two sentence-damaging edits the real models produced, and the repair that keeps a sentence whole."""

    DE = ("Das Café Morgenrot liegt mitten in der Altstadt. In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass viele "
          "Menschen Ruhe suchen. Der Garten ist groß und schattig.")
    DE_SENTENCE = "In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass viele Menschen Ruhe suchen."
    EN = ("Pixelforge turns sprite sheets into texture atlases. It's important to note that the tool is designed for indie developers. "
          "Version 2.4.0 reads PNG and WebP files.")
    EN_SENTENCE = "It's important to note that the tool is designed for indie developers."

    def attempt(self, text, lang, key, before, after, defects=()):
        editor = Editor(defects, fixes={key: (before, after)})
        return run(text, lang, "general", editor), editor

    def test_a_partial_deletion_that_leaves_a_fragment_is_rejected(self):
        for text, lang, key, before, reasons in (
                (self.DE, "de", "In der heutigen schnelllebigen Welt", "In der heutigen schnelllebigen Welt ist es wichtig zu beachten",
                 {"quality_seam_stray_punctuation", "quality_seam_space_before_punctuation"}),
                (self.EN, "en", "It's important to note", "It's important to note that", {"quality_seam_double_space"})):
            result, _ = self.attempt(text, lang, key, before, "")
            self.assertEqual(result["text"], text, lang)
            self.assertTrue(reasons & {r["error"] for r in result["receipt"]["passes"][0]["rejected"]}, lang)
            self.assertEqual(result["receipt"]["final"]["confirmed_after"], result["receipt"]["final"]["confirmed_before"])

    def test_a_lowercase_sentence_start_and_a_dangling_clause_are_caught(self):
        result, _ = self.attempt(self.EN, "en", "It's important to note", "It's important to note that ", "")
        self.assertEqual(result["text"], self.EN)
        self.assertIn("quality_seam_lowercase_sentence_start", [r["error"] for r in result["receipt"]["passes"][0]["rejected"]])
        result, _ = self.attempt(self.DE, "de", "In der heutigen schnelllebigen Welt", "In der heutigen schnelllebigen Welt ist es wichtig zu beachten, ", "")
        self.assertEqual(result["text"], self.DE)
        self.assertTrue(any(r["error"].startswith("quality_seam_") for r in result["receipt"]["passes"][0]["rejected"]))

    def test_a_whole_sentence_rewrite_or_deletion_is_accepted(self):
        result, editor = self.attempt(self.DE, "de", "In der heutigen schnelllebigen Welt", self.DE_SENTENCE, "Viele Menschen suchen Ruhe.")
        self.assertEqual(result["text"], self.DE.replace(self.DE_SENTENCE, "Viele Menschen suchen Ruhe."))
        self.assertEqual(result["receipt"]["passes"][0]["rejected"], [])
        fix_prompt = next(prompt for role, prompt in editor.calls if role == "fix")
        self.assertIn(json.dumps(self.DE_SENTENCE, ensure_ascii=False), fix_prompt)    # the model is given the whole sentence to copy
        result, _ = self.attempt(self.EN, "en", "It's important to note", self.EN_SENTENCE + " ", "")
        self.assertEqual(result["text"], self.EN.replace(self.EN_SENTENCE + " ", ""))

    def test_deleting_a_word_inside_emphasis_must_not_leave_empty_markers(self):
        # From a real run: "eine **innovative** Tischlerei" lost its word and kept "****".
        text = "Wir sind eine **innovative** Tischlerei in Husum. Unsere Meister bauen Tische. Die Lieferzeit beträgt sechs Wochen."
        flagged = [("innovative", "", "Das Wort ist leere Werbesprache und trägt keine Information bei.", "repetition", "rewrite")]
        for before, after in (("innovative", ""), ("**innovative** ", "**** ")):
            result, _ = self.attempt(text, "de", "innovative", before, after, flagged)
            self.assertEqual(result["text"], text, before)
            self.assertIn("quality_seam_empty_emphasis", [r["error"] for r in result["receipt"]["passes"][0]["rejected"]], before)
        whole, _ = self.attempt(text, "de", "innovative", "eine **innovative** Tischlerei", "eine Tischlerei", flagged)
        self.assertEqual(whole["text"], text.replace("eine **innovative** Tischlerei", "eine Tischlerei"))   # removing the whole span is fine
        self.assertEqual(whole["receipt"]["passes"][0]["rejected"], [])
        for broken in ("eine **innovative Tischlerei", "eine innovative** Tischlerei"):
            result, _ = self.attempt(text, "de", "innovative", "eine **innovative** Tischlerei", broken, flagged)
            self.assertEqual(result["text"], text, broken)    # a half marker unbalances the emphasis

    def test_the_seam_check_ignores_damage_that_was_already_there(self):
        text = "kleiner Text mit  doppeltem Leerzeichen. " + self.EN
        result, _ = self.attempt(text, "en", "It's important to note", self.EN_SENTENCE + " ", "")
        self.assertIn("kleiner Text mit  doppeltem", result["text"])
        self.assertNotIn("It's important", result["text"])

    def test_sentence_around_returns_exact_text(self):
        text = "Erster Satz. Zweiter Satz mit Defekt hier. Dritter Satz.\n\nNeuer Absatz mit Defekt."
        start = text.index("Defekt")
        self.assertEqual(quality.sentence_around(text, start, start + 6), "Zweiter Satz mit Defekt hier.")
        start = text.rindex("Defekt")
        self.assertEqual(quality.sentence_around(text, start, start + 6), "Neuer Absatz mit Defekt.")
        self.assertEqual(quality.sentence_around("Nur ein Satz ohne Punkt", 4, 7), "Nur ein Satz ohne Punkt")


class WindowTests(unittest.TestCase):
    def test_windows_are_ordered_slices_that_map_back_to_the_text(self):
        long = "Ein langer Satz folgt dem anderen. " * 120
        for text in ("Kurz.", "Erster Absatz.\n\nZweiter Absatz.\n\n" + long + "\n\nLetzter Absatz.\n", "Nur ein Absatz ohne Umbruch. " * 200,
                     "\n\n\nAbsatz nach Leerzeilen.\n\n", ""):
            parts = quality.windows(text)
            self.assertTrue(all(text[start:start + len(window)] == window for start, window in parts))
            self.assertEqual([start for start, _ in parts], sorted(start for start, _ in parts))
            self.assertTrue(all(start + len(window) <= nxt for (start, window), (nxt, _) in zip(parts, parts[1:])))
            self.assertEqual("".join(window for _, window in parts).strip(), text.strip())      # nothing but blank space is dropped
            self.assertTrue(all(len(window) <= quality.WINDOW_LIMIT + 400 for _, window in parts))

    def test_a_short_paragraph_is_audited_on_its_own_context_not_with_the_whole_text(self):
        paragraphs = [f"Absatz {i} erzählt etwas über das Thema und enthält mehrere vollständige Sätze für den Test. " * 3 for i in range(8)]
        editor = Editor()
        run("\n\n".join(paragraphs), "de", "general", editor)
        audits = [prompt for role, prompt in editor.calls if role == "audit"]
        self.assertGreater(len(audits), 1)
        self.assertTrue(all(len(prompt.split("\nPASSAGE\n", 1)[1]) <= quality.WINDOW_LIMIT + 400 for prompt in audits))

    def test_an_unchanged_paragraph_is_not_audited_again_after_a_repair(self):
        def paragraph(name, extra=""):
            return f"{name}: " + " ".join(f"Satz {number} dieses Teils steht ordentlich geschrieben da." for number in range(1, 24)) + extra
        first, last = paragraph("Erster Teil"), paragraph("Letzter Teil")
        middle = paragraph("Mittlerer Teil", " Wegen den vielen Pendlern bleibt die Werkstatt lange offen.")
        text = "\n\n".join((first, middle, last))
        defects = [("Wegen den vielen Pendlern", "Wegen der vielen Pendler", "Nach der Präposition 'wegen' steht der Genitiv.", "grammar", "replace")]
        editor = Editor(defects)
        run(text, "de", "general", editor)
        audited = [prompt.split("\nPASSAGE\n", 1)[1] for role, prompt in editor.calls if role == "audit"]
        for marker in ("Erster Teil", "Letzter Teil"):
            self.assertEqual(sum(marker in window for window in audited), 1, marker)    # read once, not again at the recheck
        self.assertGreaterEqual(sum("Mittlerer Teil" in window for window in audited), 2)  # the repaired paragraph is checked again

    def test_code_and_quotation_only_windows_are_not_sent_to_the_model(self):
        code = "```python\n" + "x = compute(value)\n" * 80 + "```\n\n"
        editor = Editor()
        result = run("Ein Satz davor, der normal ist.\n\n" + code + "Ein Satz danach, der ebenfalls normal ist.\n", "de", "technical", editor)
        self.assertNotIn("compute(value)", "".join(prompt for role, prompt in editor.calls if role == "audit"))
        self.assertTrue(result["receipt"]["audit"]["completed"])

    def test_overlapping_protected_spans_count_once(self):
        self.assertEqual(quality.covered([(0, 10), (0, 10), (5, 15)], 0, 20), 15)
        self.assertEqual(quality.covered([], 0, 20), 0)
        self.assertEqual(quality.covered([(0, 100)], 10, 20), 10)


class OrdinaryTextTests(unittest.TestCase):
    """Ordinary text may be reworded, so names are told from German nouns. Figures and invented names still cannot move."""

    def test_a_change_inside_a_word_is_not_an_inflection(self):
        same = quality.same_word
        self.assertTrue(same("Pendlern", "Pendler") and same("Wetter", "Wetters") and same("Kindern", "Kinder"))
        self.assertFalse(same("Seeblick", "Seeblock") or same("Anna", "Annabel") or same("Lena", "Leon"))
        self.assertEqual(quality.edit_problem("Seeblick", "Seeblock", opens_sentence=False), "quality_name_added")
        self.assertIsNone(quality.edit_problem("Wegen den Pendlern", "Wegen der Pendler", opens_sentence=False))

    def test_the_contract_tells_inflection_and_nouns_from_changed_facts(self):
        problem = quality.edit_problem
        self.assertIsNone(problem("Wegen den vielen Pendlern bleibt es offen.", "Wegen der vielen Pendler bleibt es offen."))
        self.assertIsNone(problem("dass viele Menschen Ruhe suchen.", "Viele Menschen suchen Ruhe."))     # two nouns are not a name
        self.assertIsNone(problem("Die Maschine hat einen Wassertank mit 1,2 Liter.", "Die Maschine hat einen Wassertank mit 1,2 Liter."))
        self.assertIsNone(problem("It's important to note that the tool is fast.", ""))
        self.assertEqual(problem("Ein Stück kostet 4,50 Euro.", "Ein Stück kostet 5,50 Euro."), "quality_number_changed")
        self.assertEqual(problem("Das Café liegt in der Altstadt.", "Das Café liegt in der Altstadt von Lübeck."), "quality_name_added")
        self.assertEqual(problem("He met her there.", "He met Dana Whitfield there."), "quality_name_added")
        self.assertEqual(problem("Kurz.", "x" * 400), "quality_edit_too_long")

    def test_a_fooled_verifier_cannot_change_a_figure_or_invent_a_name_in_ordinary_text(self):
        text = ("Die Werkstatt liegt am Marktplatz und öffnet früh. Eine Inspektion kostet 49 Euro, ein neuer Schlauch 12 Euro. "
                "Wer ein Rad abgibt, bekommt es meist noch am selben Tag zurück.")
        defects = [("kostet 49 Euro", "kostet 59 Euro", "Der Preis sollte laut der aktuellen Preisliste höher angegeben werden.", "grammar", "replace"),
                   ("meist noch am selben Tag", "meist noch am selben Tag, versprochen von Herrn Becker", "Eine Garantie würde die Aussage deutlich stärker machen.", "naturalness", "replace")]
        result = run(text, "de", "general", Editor(defects))
        self.assertEqual(result["text"], text)
        errors = {r["error"] for entry in result["receipt"]["passes"] for r in entry["rejected"]}
        self.assertEqual(errors, {"quality_number_changed", "quality_name_added"})

    def test_german_nouns_in_a_rewritten_sentence_are_accepted_where_the_strict_validator_refuses(self):
        text = ("Das Café liegt mitten in der Altstadt. In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass viele Menschen "
                "Ruhe suchen. Der Garten ist groß.")
        sentence = "In der heutigen schnelllebigen Welt ist es wichtig zu beachten, dass viele Menschen Ruhe suchen."
        fixes = {"In der heutigen schnelllebigen Welt": (sentence, "Viele Menschen suchen Ruhe.")}
        self.assertIn("Viele Menschen suchen Ruhe.", run(text, "de", "general", Editor(fixes=fixes))["text"])
        strict = run(text, "de", "article", Editor(fixes=fixes))     # a factual text keeps the studio's strict contract
        self.assertEqual(strict["text"], text)
        self.assertEqual([r["error"] for r in strict["receipt"]["passes"][0]["rejected"]], ["production_patch_invalid"])


class ProofreadTests(unittest.TestCase):
    """The correct-and-diff audit: the model returns a corrected passage and its changes become anchored findings."""

    EN = ("Turns out the collision mesh were two meters too narrow. Fixing it was a one line change, but finding it took three evenings. "
          "If everything go well, a public demo will follow in March 2025.")
    EN_FIX = {"mesh were": "mesh was", "everything go well": "everything goes well"}
    DE = ("Die Pension Seeblick hat zwölf Zimmer. Alle Gäste bekommt ein Frühstück. Wegen dem schönen Wetter sind die Tische besetzt.")

    def test_changes_become_findings_that_the_blind_comparison_confirms_and_the_fix_applies(self):
        editor = Editor(confirm_all=True, proofread=self.EN_FIX)
        result = run(self.EN, "en", "blog", editor)
        self.assertEqual(result["text"], self.EN.replace("mesh were", "mesh was").replace("everything go well", "everything goes well"))
        self.assertEqual(editor.all_roles()[:4], ["proofread", "audit", "choose", "choose"])
        self.assertNotIn("fix", editor.roles())      # the proofread version already holds the exact replacement
        receipt = result["receipt"]
        self.assertEqual({f["method"] for f in receipt["findings"] if f["source"] == "model"}, {"model_proofread+choice"})
        self.assertEqual((receipt["final"]["confirmed_before"], receipt["final"]["corrected"], receipt["final"]["confirmed_after"]), (2, 2, 0))

    def test_a_short_quote_that_is_a_prefix_of_its_own_correction_counts_as_corrected(self):
        # "go" is still a substring of "goes"; the repair has to be recognised by whole words, and a revision with only this edit accepted.
        text = "If everything go well, a public demo will follow in the spring after a long and careful test phase."
        result = run(text, "en", "blog", Editor(confirm_all=True, proofread={"everything go well": "everything goes well"}))
        self.assertEqual(result["text"], text.replace("go well", "goes well"))
        self.assertEqual([(e["accepted"], e["reason"]) for e in result["receipt"]["passes"]], [(True, None)])
        self.assertEqual((result["receipt"]["final"]["corrected"], result["receipt"]["final"]["confirmed_after"]), (1, 0))
        self.assertTrue(quality.present("go", "to go home") and not quality.present("go", "everything goes well"))
        self.assertTrue(quality.present("1996,", "im Jahr 1996, dass") and not quality.present("Welt", "Weltall"))

    def test_adjacent_changes_are_one_repair_that_cannot_be_applied_by_halves(self):
        text = "Wegen dem schönen Wetter sind die Tische besetzt. Der Garten ist groß und schattig und sehr beliebt bei allen Gästen."
        editor = Editor(confirm_all=True, proofread={"Wegen dem schönen Wetter": "Wegen des schönen Wetters"})
        result = run(text, "de", "general", editor)
        self.assertEqual(result["text"], text.replace("Wegen dem schönen Wetter", "Wegen des schönen Wetters"))
        quotes = [f["quote"] for f in result["receipt"]["findings"] if f["source"] == "model"]
        self.assertEqual(len(quotes), 1)
        self.assertIn("dem schönen Wetter", quotes[0])

    def test_a_typo_style_change_of_a_name_is_rejected_even_without_a_declared_term(self):
        editor = Editor(confirm_all=True, proofread={"Pension Seeblick": "Pension Seeblock"})
        result = run(self.DE, "de", "general", editor)
        self.assertEqual(result["text"], self.DE)
        errors = [r["error"] for entry in result["receipt"]["passes"] for r in entry["rejected"]]
        self.assertEqual(errors, ["quality_name_added"])

    def test_a_declared_term_blocks_the_same_change_in_factual_texts_too(self):
        editor = Editor(confirm_all=True, proofread={"Pension Seeblick": "Pension Seeblock"})
        result = run(self.DE, "de", "article", editor, terms=["Seeblick"])
        self.assertEqual(result["text"], self.DE)
        self.assertIn("Seeblick", result["text"])

    def test_a_proofread_that_rewrites_the_passage_is_discarded(self):
        rewritten = {self.EN: "In March 2025 a public demo will follow. The collision mesh had been too narrow by two meters, which cost three evenings."}
        editor = Editor(confirm_all=True, proofread=rewritten)
        result = run(self.EN, "en", "blog", editor)
        self.assertFalse(result["changed"])
        self.assertIn("proofread_rewrote_too_much", result["receipt"]["audit"]["limits"])

    def test_whitespace_and_trailing_newline_changes_are_no_edits(self):
        self.assertEqual(quality.word_edits("Ein Satz.  Und noch einer.\n", "Ein Satz. Und noch einer."), [])
        editor = Editor(confirm_all=True, proofread={"Satz.  Und": "Satz. Und"})
        self.assertFalse(run("Ein Satz.  Und noch einer.", "de", "general", editor)["changed"])

    def test_a_failing_proofread_still_runs_the_audit_and_is_reported(self):
        class NoProofread(Editor):
            def __call__(self, role, prompt, schema, tokens):
                if role == "proofread":
                    self.calls.append((role, prompt))
                    raise OSError("down")
                return Editor.__call__(self, role, prompt, schema, tokens)
        c = CASES["de_general"]
        editor = NoProofread(c["defects"], None, c["fixes"])
        result = run(DE_SHOP, "de", "general", editor)
        self.assertIn("audit", editor.roles())
        self.assertFalse(result["receipt"]["audit"]["completed"])
        self.assertTrue(any(limit.startswith("llm_proofread_unavailable") for limit in result["receipt"]["audit"]["limits"]))
        self.assertNotIn("schnelllebigen", result["text"])      # the rule hit is repaired nevertheless

    def test_a_defect_both_sources_found_is_one_finding(self):
        text = "Turns out the collision mesh were two meters too narrow. Fixing it took three evenings of careful work."
        defect = [("collision mesh were", "collision mesh was", "The verb has to agree with the singular subject mesh.", "grammar", "replace")]
        result = run(text, "en", "blog", Editor(defect, confirm_all=True, proofread={"mesh were": "mesh was"}))
        self.assertEqual(len([f for f in result["receipt"]["findings"] if f["source"] == "model"]), 1)
        self.assertEqual(result["text"], text.replace("mesh were", "mesh was"))

    def test_word_edits_give_every_quote_enough_context_to_be_unique(self):
        before = "He go home. She go home. They stay."
        edits = quality.word_edits(before, "He goes home. She goes home. They stay.")
        self.assertEqual(len(edits), 2)
        for quote, replacement in edits:
            self.assertEqual(before.count(quote), 1)
            self.assertNotEqual(quote, replacement)


class ChoiceTests(unittest.TestCase):
    """A finding with an exact replacement is judged blind: two versions of the sentence, no hint which one is new."""

    TEXT = ("The keeper, Anselm Roe, kept a daily log. Most entries are short: wind, visibility, oil used. "
            "Once, in November, he wrote only one line.")
    PROPOSAL = [("Most entries are short", "Most entries were short", "The surrounding sentence is past tense, so the verb should match.",
                 "grammar", "replace")]

    def statuses(self, result):
        return [f["status"] for f in result["receipt"]["findings"] if f["source"] == "model"]

    def test_the_prompt_never_says_which_version_is_the_new_one(self):
        editor = Editor(self.PROPOSAL)
        run(self.TEXT, "en", "general", editor)
        prompt = next(text for role, text in editor.calls if role == "choose")
        for word in ("propos", "original", "defect", "correction", "replacement"):
            self.assertNotIn(word, prompt.lower())
        self.assertIn("proper-name capitalisation", prompt)
        self.assertIn("A: ", prompt)
        self.assertIn("B: ", prompt)

    def test_a_confirmed_comparison_is_applied_and_needs_no_other_round(self):
        editor = Editor(self.PROPOSAL)
        result = run(self.TEXT, "en", "general", editor)
        self.assertIn("Most entries were short", result["text"])
        self.assertEqual(editor.roles()[:2], ["audit", "choose"])
        self.assertNotIn("verify", editor.roles())
        self.assertNotIn("defend", editor.roles())
        self.assertEqual(result["receipt"]["findings"][0]["method"], "model_audit+choice")

    def test_acceptable_both_ways_stays_unconfirmed_and_preferring_the_original_refutes(self):
        both = run(self.TEXT, "en", "general", Editor(self.PROPOSAL, genuine=[]))
        self.assertEqual((both["changed"], self.statuses(both)), (False, ["unconfirmed"]))
        original = run(self.TEXT, "en", "general", Editor(self.PROPOSAL, defended=["Most entries are short"]))
        self.assertEqual((original["changed"], self.statuses(original)), (False, ["refuted"]))

    def test_the_verdict_is_mapped_correctly_in_either_letter_order(self):
        letters, texts = set(), []
        for number in range(12):
            text = f"Report {number} is short. The crew of boat {number} were ready."
            fix = [(f"boat {number} were", f"boat {number} was", "The subject 'crew' takes the singular verb here.", "grammar", "replace")]
            editor = Editor(fix)
            result = run(text, "en", "general", editor)
            self.assertIn(f"boat {number} was ready", result["text"], number)
            prompt = next(p for role, p in editor.calls if role == "choose")
            first = prompt.split("\nA: ", 1)[1].split("\nB: ", 1)[0]
            letters.add("new first" if f"boat {number} was" in first else "old first")
        self.assertEqual(letters, {"new first", "old first"})   # the order really varies

    def test_neither_or_an_unusable_answer_never_confirms(self):
        class Unsure(Editor):
            def __init__(self, answer, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.answer = answer

            def __call__(self, role, prompt, schema, tokens):
                if role == "choose":
                    self.calls.append((role, prompt))
                    return self.answer, self.evidence
                return Editor.__call__(self, role, prompt, schema, tokens)
        for answer in ({"answer": "neither", "reason": "Both versions contain a different error here."}, {"answer": "C", "reason": "x"},
                       {"answer": "B", "reason": ""}, {}):
            result = run(self.TEXT, "en", "general", Unsure(answer, self.PROPOSAL))
            self.assertEqual((result["changed"], self.statuses(result)), (False, ["unconfirmed"]), answer)

    def test_the_number_of_comparisons_is_bounded_and_reported(self):
        sentences = [f"Boat number {i} were late again today." for i in range(quality.CHOICES + 5)]
        fixes = {f"number {i} were": f"number {i} was" for i in range(quality.CHOICES + 5)}
        editor = Editor(proofread=fixes, confirm_all=True)
        original = quality.PROOFREAD_EDITS
        quality.PROOFREAD_EDITS = 100
        try:
            pipe = quality.Pipeline(editor, TOOLS, "en", max_passes=0)
            result = pipe.run("\n\n".join(sentences))
        finally:
            quality.PROOFREAD_EDITS = original
        self.assertEqual(sum(role == "choose" for role, _ in editor.calls), quality.CHOICES)
        self.assertIn("verification_budget", {f.get("note") for f in result["receipt"]["findings"]})


class NoteSeverityTests(unittest.TestCase):
    """The auditor files plain errors as optional. The blind comparison, not the auditor's severity, decides about them."""

    TEXT = "Sie gingen langsam durch die Halle und blieb vor dem alten Klavier stehen. Draußen regnete es noch immer."
    ERROR = ("und blieb vor", "und blieben vor", "Das Subjekt im Plural verlangt auch beim zweiten Verb die Pluralform.", "grammar", "replace")

    def test_a_grammar_note_with_an_exact_replacement_is_judged_and_applied(self):
        editor = Editor(noted=[self.ERROR], genuine=["und blieb vor"])
        result = run(self.TEXT, "de", "story", editor)
        self.assertIn("und blieben vor", result["text"])
        self.assertIn("choose", editor.roles())
        self.assertNotIn("verify", editor.roles())

    def test_the_comparison_can_still_keep_the_original(self):
        result = run(self.TEXT, "de", "story", Editor(noted=[self.ERROR], genuine=[]))
        self.assertFalse(result["changed"])
        self.assertEqual([f["status"] for f in result["receipt"]["findings"] if f["source"] == "model"], ["unconfirmed"])

    def test_notes_about_wording_or_without_an_exact_replacement_stay_notes(self):
        for note in (("langsam durch die Halle", "gemächlich durch die Halle", "Ein anderes Wort klänge hier etwas lebendiger.", "naturalness", "replace"),
                     ("und blieb vor", "", "Das Verb passt nicht gut zum Subjekt dieses Satzes.", "grammar", "rewrite"),
                     ("regnete es noch", "regnete es noch", "Hier steht vielleicht ein Komma zu wenig im Satz.", "punctuation", "replace"),
                     ("Draußen regnete", "", "Die Wiederholung dieses Satzanfangs wirkt etwas eintönig.", "repetition", "delete")):
            editor = Editor(noted=[note], confirm_all=True)
            result = run(self.TEXT, "de", "general", editor)
            self.assertFalse(result["changed"], note)
            self.assertEqual(editor.roles(), ["audit"], note)
            self.assertEqual([f["note"] for f in result["receipt"]["findings"]], ["optional_style"], note)


class DefenceTests(unittest.TestCase):
    """Findings without an exact replacement need two rounds: is the defect real, and can the original be defended."""

    TEXT = ChoiceTests.TEXT
    VAGUE = [("Most entries are short", "", "The surrounding sentence is in the past tense, so the verb should match.",
              "grammar", "rewrite")]
    FIX = {"Most entries are short": ("Most entries are short", "Most entries were short")}

    def test_a_defect_the_defender_can_save_is_not_applied(self):
        editor = Editor(self.VAGUE, fixes=self.FIX, defended=["Most entries are short"])
        result = run(self.TEXT, "en", "general", editor)
        self.assertFalse(result["changed"])
        self.assertEqual(editor.roles(), ["audit", "verify", "defend"])
        finding = next(f for f in result["receipt"]["findings"] if f["source"] == "model")
        self.assertEqual(finding["status"], "refuted")
        self.assertIn("Defence:", finding["verification"])
        self.assertNotIn("fix", editor.roles())

    def test_a_defect_both_rounds_confirm_is_applied(self):
        editor = Editor(self.VAGUE, fixes=self.FIX)
        result = run(self.TEXT, "en", "general", editor)
        self.assertEqual(editor.roles()[:3], ["audit", "verify", "defend"])
        self.assertIn("Most entries were short", result["text"])

    def test_the_defender_only_sees_what_the_verifier_confirmed(self):
        editor = Editor(self.VAGUE, genuine=[])
        run(self.TEXT, "en", "general", editor)
        self.assertEqual(editor.roles(), ["audit", "verify"])

    def test_a_missing_defence_never_counts_as_confirmation(self):
        class Silent(Editor):
            def __call__(self, role, prompt, schema, tokens):
                if role == "defend":
                    self.calls.append((role, prompt))
                    return {"verdicts": []}, self.evidence
                return Editor.__call__(self, role, prompt, schema, tokens)
        result = run(self.TEXT, "en", "general", Silent(self.VAGUE, fixes=self.FIX))
        self.assertFalse(result["changed"])
        finding = next(f for f in result["receipt"]["findings"] if f["source"] == "model")
        self.assertEqual(finding["status"], "unconfirmed")
        self.assertIn("unanswered", finding["verification"])

    def test_an_unavailable_verifier_leaves_model_findings_unconfirmed_but_keeps_rule_hits(self):
        class Down(Editor):
            def __call__(self, role, prompt, schema, tokens):
                if role in ("choose", "verify", "defend"):
                    raise OSError("down")
                return Editor.__call__(self, role, prompt, schema, tokens)
        c = CASES["de_general"]
        result = run(DE_SHOP, "de", "general", Down(c["defects"], None, c["fixes"]))
        statuses = {f["source"]: f["status"] for f in result["receipt"]["findings"]}
        self.assertEqual(statuses, {"rule": "confirmed", "model": "unconfirmed"})
        self.assertIn("Wegen den vielen Pendlern", result["text"])
        self.assertNotIn("schnelllebigen", result["text"])      # the rule hit is still repaired
        self.assertTrue(any(limit.startswith("verification_unavailable") for limit in result["receipt"]["audit"]["limits"]))


class HonestyTests(unittest.TestCase):
    def test_the_verifier_is_told_to_leave_acceptable_variants_unconfirmed(self):
        editor = Editor([("Cape Verde point", "", "Der Name wird großgeschrieben, weil er ein Eigenname ist.", "grammar", "rewrite")], genuine=[])
        result = run(EN_GOOD, "en", "general", editor)
        verify = next(prompt for role, prompt in editor.calls if role == "verify")
        self.assertIn("answer unconfirmed", verify)
        self.assertIn("capitalisation of a proper name", verify)
        self.assertFalse(result["changed"])
        self.assertEqual(result["receipt"]["final"]["confirmed_before"], 0)

    def test_a_defect_that_is_still_in_the_text_is_never_counted_as_corrected(self):
        # The audit finds a grammar error it cannot repair and the filler it can. The recheck audit is silent (a model audit does
        # not repeat itself reliably), yet the grammar error is still in the final text and has to stay in the report.
        defects = [("Wegen den vielen Pendlern", "", "Nach der Präposition 'wegen' steht im Standarddeutschen der Genitiv.", "grammar", "rewrite")]
        editor = Editor(defects, None, {"In der heutigen schnelllebigen Welt": (FILLER_DE, "")}, once=True)
        result = run(DE_SHOP, "de", "general", editor)
        self.assertIn("Wegen den vielen Pendlern", result["text"])
        self.assertNotIn("schnelllebigen", result["text"])
        final = result["receipt"]["final"]
        self.assertEqual((final["confirmed_before"], final["corrected"], final["confirmed_after"]), (2, 1, 1))
        info = quality.summary(result["receipt"])
        self.assertEqual((info["corrected"], info["remaining"]), (1, 1))
        self.assertEqual([r["quote"] for r in result["receipt"]["recheck"]["remaining"]], ["Wegen den vielen Pendlern"])

    def test_an_audit_only_run_corrects_nothing_and_keeps_every_confirmed_defect_open(self):
        c = CASES["de_general"]
        result = quality.Pipeline(Editor(c["defects"], None, c["fixes"]), TOOLS, "de", kind="general", max_passes=0).run(c["text"])
        final = result["receipt"]["final"]
        self.assertEqual((final["corrected"], final["confirmed_before"], final["confirmed_after"], final["changed"]), (0, 2, 2, False))
        self.assertEqual(len(result["receipt"]["recheck"]["remaining"]), 2)
        self.assertEqual(quality.summary(result["receipt"])["corrected"], 0)


class ReceiptAndLocaleTests(unittest.TestCase):
    def test_the_receipt_proves_what_ran(self):
        c = CASES["de_general"]
        self.last_editor = Editor(c["defects"], None, c["fixes"])
        result = run(c["text"], "de", "general", self.last_editor, terms=["Kettenglied"])
        receipt = result["receipt"]
        self.assertEqual(receipt["pipeline"], {"name": "human-writing-quality", "version": quality.VERSION})
        self.assertEqual((receipt["language"], receipt["profile"], receipt["skill_version"]), ("de-DE", "general", "1.3.1"))
        self.assertEqual(receipt["skills"][0]["name"], "human-writing")
        self.assertEqual(len(receipt["rules_sha256"]), 64)
        self.assertEqual(receipt["audit"]["models"], ["scripted"])
        self.assertEqual(receipt["audit"]["calls"], len(self.last_editor.calls))
        sources = {f["source"] for f in receipt["findings"]}
        self.assertEqual(sources, {"rule", "model"})
        first = receipt["passes"][0]
        self.assertTrue(first["accepted"])
        self.assertEqual({e["before"][:20] for e in first["applied"]}, {"In der heutigen schn", "Wegen den vielen Pen"})
        self.assertEqual(first["recheck"]["automatic"], 0)
        self.assertTrue(receipt["recheck"]["required"] and receipt["recheck"]["completed"])
        self.assertEqual(receipt["final"]["confirmed_before"], 2)
        self.assertEqual(receipt["final"]["confirmed_after"], 0)
        info = quality.summary(receipt)
        self.assertEqual((info["audit_completed"], info["corrected"], info["remaining"], info["rechecked"]), (True, 2, 0, True))
        json.dumps(receipt)

    def test_language_variants_reach_the_audit_and_unknown_ones_fall_back(self):
        for locale, lang, fragment in (("en-GB", "en", "British spelling"), ("de-CH", "de", "no ß"), ("de-AT", "de", "Austrian"),
                                       ("en-US", "en", "American spelling")):
            editor = Editor()
            run("A short, plain sentence for the audit.", lang, "general", editor, locale=locale)
            for role in ("proofread", "audit"):
                self.assertIn(fragment, next(text for name, text in editor.calls if name == role), (locale, role))
        self.assertEqual(quality.locale_for("en", "de-DE"), "en-US")
        self.assertEqual(quality.locale_for("de", "fr-FR"), "de-DE")
        with self.assertRaises(PlanError):
            quality.locale_for("fr")

    def test_the_audit_names_the_language_rules_of_each_language(self):
        german, english = Editor(), Editor()
        run("Ein kurzer Satz für die Prüfung.", "de", "general", german)
        run("A short sentence for the audit.", "en", "general", english)
        prompt = lambda editor, role: next(text for name, text in editor.calls if name == role)
        self.assertIn("German (Germany)", prompt(german, "audit"))
        self.assertIn("including the second verb of a predicate joined by 'und'", prompt(german, "audit"))
        self.assertIn("infinitive groups", prompt(german, "audit"))
        self.assertIn("English (United States)", prompt(english, "audit"))
        self.assertIn("including the second verb of a predicate joined by 'and'", prompt(english, "audit"))
        self.assertIn("literal translations", prompt(english, "audit"))
        for editor, language in ((german, "German (Germany)"), (english, "English (United States)")):
            self.assertIn(language, prompt(editor, "proofread"))
            self.assertIn("Correct only objective errors", prompt(editor, "proofread"))

    def test_profiles_follow_the_kind_of_text(self):
        names = {kind: quality.profile_for(kind).name for kind in (
            "story", "Kurzgeschichte", "dialogue", "game_text", "article", "music_article", "essay", "devlog", "blogpost", "technical",
            "documentation", "readme", "website", "product_description", "doc", "unknown-kind", None)}
        self.assertEqual(names["story"], "story")
        self.assertEqual(names["Kurzgeschichte"], "story")
        self.assertEqual((names["dialogue"], names["game_text"]), ("dialogue", "dialogue"))
        self.assertEqual((names["article"], names["music_article"], names["essay"]), ("article", "article", "essay"))
        self.assertEqual((names["devlog"], names["blogpost"]), ("blog", "blog"))
        self.assertEqual((names["technical"], names["documentation"], names["readme"]), ("technical", "technical", "technical"))
        self.assertEqual((names["website"], names["product_description"]), ("marketing", "marketing"))
        self.assertEqual((names["doc"], names["unknown-kind"], names[None]), ("general", "general", "general"))
        self.assertFalse(quality.profile_for("story").naturalness)
        self.assertTrue(quality.profile_for("article").factual)

    def test_audit_only_mode_changes_nothing(self):
        c = CASES["de_general"]
        editor = Editor(c["defects"], None, c["fixes"])
        result = quality.Pipeline(editor, TOOLS, "de", kind="general", max_passes=0).run(c["text"])
        self.assertFalse(result["changed"])
        self.assertNotIn("fix", editor.roles())
        self.assertGreaterEqual(result["receipt"]["audit"]["findings"]["confirmed"], 2)

    def test_a_length_contract_rejects_a_revision_that_breaks_it(self):
        c = CASES["de_general"]
        words = len(DE_SHOP.split())
        editor = Editor(c["defects"], None, c["fixes"])
        result = quality.Pipeline(editor, TOOLS, "de", kind="general", constraints={"lang": "de", "words": [words - 2, words + 2]}).run(c["text"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["receipt"]["passes"][0]["reason"], "constraint_violated")


if __name__ == "__main__":
    unittest.main()
