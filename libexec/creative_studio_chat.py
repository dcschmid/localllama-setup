"""Chat-owned content and server-side selection of creative actions."""

import json
import re
import time
import unicodedata
import uuid

import creative_studio_organizer as records
import creative_studio_story as story
import creative_studio_visual as visual

# The existing projects and session pointer remain readable by older callers.
MIGRATION = """
CREATE TABLE chat_contexts(chat_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    context_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created REAL NOT NULL, PRIMARY KEY(chat_id,context_id));
CREATE INDEX chat_contexts_context ON chat_contexts(context_id,chat_id);
INSERT INTO chat_contexts(chat_id,context_id,created)
    SELECT s.id,p.id,COALESCE(s.created,p.created,0) FROM sessions s JOIN projects p ON p.id=s.project_id;
CREATE TRIGGER chat_context_insert AFTER INSERT ON sessions WHEN NEW.project_id IS NOT NULL
    AND EXISTS(SELECT 1 FROM projects WHERE id=NEW.project_id)
    BEGIN INSERT OR IGNORE INTO chat_contexts VALUES(NEW.id,NEW.project_id,COALESCE(NEW.created,0)); END;
CREATE TRIGGER chat_context_activate AFTER UPDATE OF project_id ON sessions WHEN NEW.project_id IS NOT NULL
    AND EXISTS(SELECT 1 FROM projects WHERE id=NEW.project_id)
    BEGIN INSERT OR IGNORE INTO chat_contexts VALUES(NEW.id,NEW.project_id,COALESCE(NEW.updated,NEW.created,0)); END;
INSERT INTO sessions(id,project_id,title,folder_id,archived_at,created,updated)
    SELECT lower(hex(randomblob(16))),p.id,p.name,p.folder_id,p.archived_at,p.created,p.updated
    FROM projects p WHERE p.id NOT IN (SELECT id FROM studio_trash WHERE kind='project')
      AND NOT EXISTS(SELECT 1 FROM chat_contexts c JOIN sessions s ON s.id=c.chat_id
          WHERE c.context_id=p.id AND s.id NOT IN (SELECT id FROM studio_trash WHERE kind='chat'));
DROP VIEW live_projects;
CREATE VIEW live_projects AS SELECT * FROM projects p
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='project')
    AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders))
    AND (json_extract(meta,'$.chat_owned') IS NOT 1 OR EXISTS (
        SELECT 1 FROM chat_contexts c JOIN sessions s ON s.id=c.chat_id
        WHERE c.context_id=p.id AND s.id NOT IN (SELECT id FROM studio_trash WHERE kind='chat')
          AND (s.folder_id IS NULL OR s.folder_id IN (SELECT id FROM live_folders))));
DROP VIEW live_sessions;
CREATE VIEW live_sessions AS SELECT * FROM sessions s
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='chat')
    AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders))
    AND (s.project_id IS NULL OR EXISTS(SELECT 1 FROM live_projects WHERE id=s.project_id)
         OR EXISTS(SELECT 1 FROM chat_contexts c JOIN live_projects p ON p.id=c.context_id WHERE c.chat_id=s.id)
         OR NOT EXISTS(SELECT 1 FROM projects WHERE id=s.project_id));
"""

NUMBERS = dict(zip(("ein", "eins", "one", "zwei", "two", "drei", "three", "vier", "four",
                   "fünf", "five", "sechs", "six", "sieben", "seven", "acht", "eight",
                   "neun", "nine", "zehn", "ten"),
                   (1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10)))
NUMBER = r"(?:\d{1,9}|" + "|".join(NUMBERS) + ")"
CHAPTER = re.compile(r"\b(?:kapitel|chapter)\s+(" + NUMBER + r")\b", re.I)
TITLE = re.compile(r'''(?im)^\s*(?:\*\*)?(?:titel|title)\s*:\s*(?:\*\*)?\s*([^\n]{1,180})|(?:\b(?:namens|titled|called)\s+|[„"«])([^\n"“»]{1,180})''')
NEW_STORY = re.compile(r"\b(?:neue[nrs]?\s+(?:geschichte|[a-zäöüß]*roman|story)|(?:new|another)\s+(?:story|novel))\b", re.I)
BIBLE = re.compile(r"\b(?:story[ -]?bibel|story bible|series bible)\b", re.I)
OUTLINE = re.compile(r"\b(?:kapitel(?:übersicht|plan)|chapter outline|(?:plan\w*|outline)\b[^\n!?]{0,100}\b" + NUMBER + r"\s+(?:kapitel(?:n)?|chapters))\b", re.I)
WRITE = re.compile(r"\b(?:schreib\w*|verfass\w*|entwirf\w*|write|draft|continue|fortsetz\w*|setze)\b", re.I)
IMAGE = re.compile(r"\b(?:erstelle\w*|generiere\w*|zeichn\w*|mach\w*|create|generate|draw|paint)\b[^\n.!?]{0,90}\b(?:titelbild|cover|bild|illustration|image|picture|artwork)\b", re.I)
COVER = re.compile(r"\b(?:titelbild|cover|book cover)\b", re.I)
RESEARCH = re.compile(r"\b(?:recherchier\w*|deep research|research (?:the|how|why|whether|what)|fact.check)\b", re.I)
ARTICLE = re.compile(r"\b(?:artikel|devlog|article|blog post)\b", re.I)
GAME = re.compile(r"\b(?:spielidee\w*|spiele?konzept|game idea|game design|godot|defold)\b", re.I)
STORY = re.compile(r"\b(?:geschichte|[a-zäöüß]*roman|novel|story|kapitel|chapter)\b", re.I)
EDITORIAL = re.compile(r"\b(?:prüf\w*|audit\w*|check|review|vergleich\w*|compare|überarbeit\w*|verbesser\w*|rewrite|revise)\b", re.I)
PLAN_REVISION = re.compile(r"\b(?:umplan\w*|korr?egier\w*|korrigier\w*)\b", re.I)
REWRITE = re.compile(r"\b(?:überarbeit\w*|verbesser\w*|sta?raff\w*|rewrite|revise)\b", re.I)
AUDIT = re.compile(r"\b(?:prüf\w*|audit\w*|check|review)\b", re.I)

PLAN_TARGET = re.compile(r"\b(?:story[ -]?planung|gesamtplanung|planung|kapitel[ -]?(?:planung|plan|übersicht)|"
                         r"(?:story|chapter|plot) (?:plan(?:ning)?|outline)|outline|handlungs(?:bogen|planung)|plot arc)\b", re.I)
PLAN_CONTENT = re.compile(r"\b(?:handlung|figuren?entwicklung|figuren?wissen|charakter\w*|motivationen?|"
                          r"zeitlinie|chronologie|reihenfolge|spannung\w*|ende|plausib\w*|plot|character\w*|"
                          r"timeline|ending|motivation|pacing|continuity|kontinuität|widerspr\w*|konsisten\w*)\b", re.I)
TEXT_TARGET = re.compile(r"\b(?:kapiteltext|manuskript|manuscript|chapter text|"
                         r"(?:geschrieben\w*|vorliegend\w*|written|existing)\s+(?:kapitel|text|prose|chapter)|"
                         r"grammatik\w*|rechtschreib\w*|zeichensetz\w*|grammar|spelling|punctuation|human writing|"
                         r"absatz|passage|formulierung\w*|formulier\w*|wortwahl|wording|prosa|prose|text|fassung|dokument|artikel|devlog|article)\b", re.I)
CREATE_PLAN = re.compile(r"\b(?:erstell\w*|entwirf\w*|plane|entwickl\w*|anlegen|plan|create|build|draft|design)\b", re.I)
IMPORT_PLAN = re.compile(r"\b(?:übernimm|übernehm\w*|importier\w*|adopt|import|save)\b", re.I)
QUESTION = re.compile(r"^\s*(?:was|wie|warum|findest|hältst|ist|sind|wäre|wirkt|what|how|why|do you|is|are|would)\b", re.I)
CHANGE = re.compile(r"\b(?:soll(?:en|te)?|sollten|ändere|ändern|ersetze|change|replace|should|make)\b", re.I)
DRAFT_CHAPTER = re.compile(r"^\s*(?:bitte\s+)?(?:schreib\w*|verfass\w*|setze|fortsetz\w*|write|draft|continue)"
                           r"\s+(?:mir\s+|uns\s+)?(?:das\s+|den\s+|the\s+)?(?:nächst\w*\s+|next\s+)?(?:kapitel|chapter)\b", re.I)
NO_DRAFT = re.compile(r"\b(?:(?:schreib\w*|verfass\w*)\s+(?:noch\s+)?(?:kein\w*|nicht)|(?:do not|don't)\s+(?:write|draft))\b[^.!?]*", re.I)


PRODUCTION_START = re.compile(
    r"(?:(?:bitte )?(?:(?:die |diese )?geschichte vollständig (?:erstellen|schreiben)|"
    r"(?:erstelle|schreibe) (?:(?:jetzt|nun) )?(?:(?:die |diese )?geschichte vollständig|(?:die )?(?:ganze|gesamte|vollständige) geschichte)|(?:starte|start) (?:die |the )?(?:manuskriptproduktion|story production)|"
    r"create the (?:complete|full) story|gemeinsam schreiben|write together))", re.I)
PLAN_APPROVAL = re.compile(
    r"(?:ich gebe (?:die )?planung frei|ich habe (?:die )?planung freigegeben|(?:die )?(?:story[ -]?)?planung (?:freigeben|freigegeben|ist freigegeben)|"
    r"(?:ist )?freigegeben|approve (?:the )?(?:story )?plan|plan approved)", re.I)
MANUSCRIPT_EXPORT = re.compile(
    r"(?:bitte )?(?:(?:exportier\w*|lade) (?:mir )?(?:(?:das |die |den )?(?:vollständige\w* )?)"
    r"(?:manuskript|geschichte|roman)|(?:export|download) (?:the )?(?:complete )?(?:manuscript|story)|"
    r"(?:manuskript|geschichte) exportieren)(?: (?:als|as) (?:markdown|mdx?|zip|astro mdx)(?: (?:und|and) (?:markdown|mdx?|zip))?)?(?: herunter)?", re.I)
SIMULATED_OUTPUT = re.compile(
    r"(?:simuliertes? (?:bild|titelbild|illustration|download|export)|hier würde (?:der|das|die) (?:gesamte|vollständige)|"
    r"bild würde hier erscheinen|simulated (?:image|download|export)|(?:image|manuscript) would (?:appear|go) here)", re.I)


def command(text):
    phrase = " ".join(text.strip().rstrip(".!").split())
    if PRODUCTION_START.fullmatch(phrase):
        return "together" if phrase.casefold().removeprefix("bitte ") in ("gemeinsam schreiben", "write together") else "automatic"
    if PLAN_APPROVAL.fullmatch(phrase):
        return "approve"
    if MANUSCRIPT_EXPORT.fullmatch(phrase):
        return "export"
    return None


# An explicit release of an existing plan, in free wording. It outranks the planning review,
# because "Planung ... Prüfe und korrigiere die Texte" is part of the production, not a review request.
_FILLER = r"(?:(?:bitte|jetzt|nun|gleich|sofort|mir|uns|noch|now|please|just)\s+)*"
_VERB = r"(?:erstell\w*|schreib\w*|verfass\w*|produzier\w*|generier\w*|generate|write|create|produce|draft)"
_WHOLE = (r"(?:(?:die|diese|meine|unsere|the|this|my|our)\s+)?"
          r"(?:(?:ganze|gesamte|vollständige|komplette|fertige|full|complete|whole|entire|finished)\s+)?"
          r"(?:geschichte|story|manuskript|manuscript|roman|novel)"
          r"|(?:alle|sämtliche|all)\s+(?:(?:\d+|ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|one|two|three|four|five|six|seven|eight|nine|ten)\s+)?"
          r"(?:kapitel\w*|chapters)")
_NOT_A_REWRITE = (r"(?!\s+(?:um|neu|weiter|fort|kürzer|länger|anders|besser|zusammen|again|over|shorter|longer|"
                  r"differently|better|further))")
WHOLE_START = re.compile(r"^\s*(?:(?:und|and|dann|then)\s+)?" + _FILLER + _VERB + r"\s+" + _FILLER + r"(?:" + _WHOLE + r")\b" + _NOT_A_REWRITE, re.I)
NAMED_START = re.compile(r"^\s*(?:bitte\s+)?(?:starte\w*|start|beginne\w*|begin|launch|run)\s+(?:die\s+|the\s+|mit\s+der\s+)?"
                         r"(?:(?:vollständige|komplette|full|complete)\s+)?(?:manuskript\w*|story[ -]?production|produktion|geschichtsproduktion)\b", re.I)
FULL_START = re.compile(r"\b(?:vollständig|komplett|in full|completely)\s+(?:schreib\w*|erstell\w*|ausschreib\w*|write|produz\w*)"
                        r"|\b(?:schreib\w*|erstell\w*|write)\b[^.!?\n]{0,24}\b(?:vollständig|komplett|in full|completely)\b", re.I)
WEAK_START = re.compile(r"^\s*(?:bitte\s+)?(?:start(?:e)?\s+(?:writing|mit dem schreiben)|(?:begin|beginne)\s+(?:writing|mit dem schreiben|zu schreiben)|"
                        r"schreib\s+los|leg\s+los|fang\s+an|go\s+ahead)\b", re.I)
APPROVAL_CLAUSE = re.compile(
    r"\b(?:planung|plan|gliederung|outline|exposé|kapitelplan|kapitelübersicht)\b[^.!?\n]{0,40}\b(?:freigegeben|freigeben|genehmigt|akzeptiert|bestätigt|approved|accepted)\b"
    r"|\bich\s+(?:gebe|habe)\b[^.!?\n]{0,50}\b(?:frei|freigegeben)\b|\bi\s+(?:approve|accept)\b|\b(?:approved|freigegeben)\b"
    r"|\bso\s+ist\s+das\s+gut\b|\bja[, ]+das\s+passt\b|\bgib\b[^.!?\n]{0,30}\bfrei\b|\bpasst\s+so\b|\beinverstanden\b|\bsieht\s+gut\s+aus\b|\blooks\s+good\b", re.I)
NEGATION = re.compile(r"\b(?:nicht|kein\w*|nie|never|not|no|unapproved)\b|n't\b", re.I)
HOLD = re.compile(r"\b(?:aber|jedoch|allerdings|but|however|vorher|zuerst|bevor|before|first|falls|wenn|if|sobald|erst)\b", re.I)
TOGETHER = re.compile(r"\b(?:gemeinsam schreiben|write together|kapitel für kapitel|chapter by chapter)\b", re.I)


def production_command(text, plan_state):
    """Classify an explicit release of the existing story plan.

    Returns "automatic" or "together" to approve the latest plan version and start the real
    production, "approve" for an approval without a start request, or None when the message is
    absent of a clear instruction, is a question, a condition or a negation, or no plan exists."""
    if plan_state not in ("proposal", "approved", "unknown"):
        return None
    phrase = " ".join(unicodedata.normalize("NFKC", text).split())
    if not phrase or "?" in phrase or HOLD.search(phrase) or QUESTION.match(phrase) or REWRITE.match(phrase) or re.search(r"\bumplan\w*", phrase, re.I):
        return None
    clauses = [part.strip() for part in re.split(r"[.!?;:,\n]+", phrase) if part.strip()]
    approval = any(APPROVAL_CLAUSE.search(part) and not NEGATION.search(part) for part in clauses)
    strong = any((WHOLE_START.match(part) or NAMED_START.match(part) or FULL_START.search(part)) and not NEGATION.search(part)
                 for part in clauses)
    weak = any(WEAK_START.match(re.sub(r"^.*?\b(?:dann|then)\s+", "", part, flags=re.I)) and not NEGATION.search(part) for part in clauses)
    if TOGETHER.search(phrase) and (approval or plan_state == "approved") and not NEGATION.search(phrase):
        strong = True
    if strong or (weak and (approval or plan_state == "approved")):
        return "together" if TOGETHER.search(phrase) else "automatic"
    return "approve" if approval else None


def story_request(text):
    """A whole-story commission uses the persistent producer, including ordinary briefs."""
    if QUESTION.match(text) or NO_DRAFT.search(text) or REWRITE.search(text) or PLAN_REVISION.search(text):
        return None
    if not re.search(r"\b(?:geschichte|roman|story(?![ -]bi(?:ble|bel))|novel)\b", text, re.I) or not re.search(
            r"\b(?:erstell\w*|schreib\w*|verfass\w*|create|write|produce|generate)\b", text, re.I):
        return None
    image = IMAGE.search(text)
    narrative = re.search(r"\b(?:geschichte|roman|story|novel)\b", text, re.I)
    if image and image.end() < narrative.start():
        return None
    if PLAN_TARGET.search(text) and not outline_count(text):
        return None
    if re.search(r"\b(?:zeig\w*|show)\b[^.!?]{0,70}\b(?:planung|plan|outline)\b|"
                 r"\b(?:zuerst|erst|first)\b[^.!?]{0,60}\b(?:planung|plan|outline|freigabe|approval)\b|"
                 r"\b(?:warte|wait)\b[^.!?]{0,50}\b(?:freigabe|approval)\b", text, re.I):
        return "approval_first"
    return "auto_production"


def production_brief(text):
    return bool(outline_count(text) and STORY.search(text) and re.search(
        r"story[ -]produktion|manuskriptproduktion|(?:vollständig\w*|komplett\w*|complete|full)\b[^.!?\n]{0,75}"
        r"\b(?:geschichte|manuskript|roman|story|manuscript|novel)\b", text, re.I)
        and re.search(r"\b(?:möchte|will|want|erstelle|erstellt|create|schreibe|write|produzier\w*)\b", text, re.I))


def number(value):
    return NUMBERS[value.casefold()] if value.casefold() in NUMBERS else int(value)


def title(text, fallback):
    named = re.search(r"\b(?:mit dem titel|with the title|titled|called)\s+[„\"]?([^\n.!?„\"“]{1,180})", text, re.I)
    if named:
        return named[1].strip(" *'„“«»\".,:")
    match = TITLE.search(text)
    heading = re.search(r"(?m)^#\s+([^\n]{1,180})$", text) if not match and production_brief(text) else None
    name = next((part for part in match.groups() if part), "") if match else heading[1] if heading else ""
    return (name.strip(" *'„“«»\".,:") or fallback or "Unterhaltung")[:180]


def context_list(conn, sid):
    return [dict(row) for row in conn.execute("""SELECT p.id,p.name,p.kind FROM chat_contexts c
        JOIN live_projects p ON p.id=c.context_id WHERE c.chat_id=?
        ORDER BY c.created,p.id""", (sid,))]


def visible_chat(conn, pid):
    row = conn.execute("""SELECT s.id FROM chat_contexts c JOIN live_sessions s ON s.id=c.chat_id
        WHERE c.context_id=? ORDER BY s.archived_at IS NOT NULL,
          COALESCE(s.updated,(SELECT MAX(created) FROM messages WHERE session_id=s.id),s.created) DESC,s.id LIMIT 1""",
        (pid,)).fetchone()
    return row["id"] if row else None


def activate(conn, sid, pid):
    if not any(ctx["id"] == pid for ctx in context_list(conn, sid)):
        raise records.OrganizerError("chat_context_invalid", 404)
    conn.execute("UPDATE sessions SET project_id=?,updated=? WHERE id=?", (pid, time.time(), sid))
    return pid


def ensure_context(conn, session, kind, lang, name=None, *, fresh=False):
    contexts = context_list(conn, session["id"])
    active = next((item for item in contexts if item["id"] == session["project_id"]), None)
    if not fresh:
        if active and (kind != "story" or active["kind"] in ("story", "novel")):
            conn.execute("UPDATE projects SET meta=json_set(meta,'$.chat_owned',json('true')) WHERE id=?", (active["id"],))
            if active["kind"] in visual.KINDS:
                visual.ensure(conn, active["id"])
            return active["id"]
        if active and kind == "story" and active["kind"] == "custom":
            # Promote the neutral context without moving any of its contents.
            conn.execute("UPDATE projects SET kind='story',meta=json_set(meta,'$.chat_owned',json('true')) WHERE id=?", (active["id"],))
            visual.ensure(conn, active["id"])
            return active["id"]
        if not active and len(contexts) == 1 and (kind != "story" or contexts[0]["kind"] in ("story", "novel")):
            return activate(conn, session["id"], contexts[0]["id"])
    pid, at = uuid.uuid4().hex, time.time()
    conn.execute("""INSERT INTO projects(id,name,kind,lang,meta,created,updated)
        VALUES(?,?,?,?,'{"chat_owned":true}',?,?)""",
        (pid, (name or session["title"] or "Unterhaltung")[:180], kind, lang, at, at))
    conn.execute("UPDATE sessions SET project_id=?,updated=? WHERE id=?", (pid, at, session["id"]))
    if kind in visual.KINDS:
        visual.ensure(conn, pid)
    return pid


def requested_action(text, preferred, *, has_plan=False, has_prose=None, story_context=False):
    if story_request(text) or production_brief(text):
        return "outline"
    text = NO_DRAFT.sub("", text)
    chapter = CHAPTER.search(text)
    bible_reference = re.search(r"\b(?:nach|anhand|mit|against|using)\b[^,;.!?]{0,48}\b(?:story[ -]?bibel|story bible)\b", text, re.I)
    target = bool(PLAN_TARGET.search(text) or BIBLE.search(text) and not bible_reference or OUTLINE.search(text))
    prose = TEXT_TARGET.search(text)
    question = QUESTION.search(text)
    writing = WRITE.search(text)
    review = EDITORIAL.search(text)
    if not question and ARTICLE.search(text) and writing and (not review or writing.start() < review.start()):
        return "article"
    if not question and prose and review:
        return "review-story" if re.search(r"\b(?:manuskript|manuscript)\b", text, re.I) and AUDIT.search(text) else "editorial"
    if IMAGE.search(text) and not DRAFT_CHAPTER.search(text):
        return "image"
    if RESEARCH.search(text):
        return "research"
    if target and IMPORT_PLAN.search(text) and not question:
        return "planning-import"
    if target and CREATE_PLAN.search(text) and not EDITORIAL.search(text) and not question:
        return "outline"
    if not question and not target and AUDIT.search(text) and re.search(r"\b(?:gesamte geschichte|ganzen roman|whole story|entire novel)\b", text, re.I):
        return "planning-audit" if has_plan and not has_prose else "review-story"
    if not question and has_plan and PLAN_REVISION.search(text) and not AUDIT.search(text) and not prose:
        return "planning-revise"
    if not question and (target or chapter and CHANGE.search(text) or has_plan and PLAN_CONTENT.search(text)):
        if REWRITE.search(text) or chapter and CHANGE.search(text):
            return "planning-revise"
        if AUDIT.search(text) and (target or not chapter or not has_prose):
            return "planning-audit"
    if not question and EDITORIAL.search(text) and chapter:
        # A bare chapter reference follows the available artefact. Explicit prose targets were handled above.
        if has_plan and has_prose is False:
            return "planning-revise" if REWRITE.search(text) else "planning-audit"
        if has_prose is not False or AUDIT.search(text):
            return "editorial"
    if DRAFT_CHAPTER.search(text):
        return "chapter"
    if GAME.search(text):
        return "game"
    if NEW_STORY.search(text) and not question:
        return "story"
    if target or (story_context and (question or has_plan or chapter or STORY.search(text))):
        return "planning-discuss"
    if STORY.search(text) and WRITE.search(text) and not question:
        return "story"
    if question or preferred == "story":
        return "chat"
    return preferred


def length_range(text):
    digits = r"(\d+(?:[.,]\d{3})*)"
    match = re.search(digits + r"(?:\s*(?:–|—|-|bis|to)\s*" + digits + r")?\s+(?:wörter(?:n)?|words)\b", text, re.I)
    if not match:
        return {}
    first = int(re.sub(r"[.,]", "", match[1]))
    second = int(re.sub(r"[.,]", "", match[2])) if match[2] else None
    if second is not None:
        low, high = story.bounds(first, second)
    else:
        low, high = story.bounds(max(1, round(first * .9)), round(first * 1.1))
    return {"minimum": low, "maximum": high}


def story_language(text, fallback):
    if re.search(r"\b(?:auf englisch|in english|englischsprachig\w*|english[ -]language|english story|englischer text|sprache:\*?\*?\s*englisch|\ben-us\b)\b", text, re.I):
        return "en"
    if re.search(r"\b(?:auf deutsch|in german|deutschsprachig\w*|german[ -]language|german story|deutscher text|sprache:\*?\*?\s*deutsch|\bde-de\b)\b", text, re.I):
        return "de"
    if re.match(r"\s*(?:please\s+)?(?:create|write|generate|produce)\b", text, re.I):
        return "en"
    if re.match(r"\s*(?:bitte\s+)?(?:erstelle|schreibe|verfasse)\b", text, re.I):
        return "de"
    return fallback


def outline_count(text):
    match = re.search(r"\b(" + NUMBER + r")\s+(?:kapitel(?:n)?|chapters?)\b", text, re.I)
    return number(match[1]) if match else 8 if OUTLINE.search(text) else 0


def candidates(conn, pid, sid, ordinal=None):
    rows = list(conn.execute("""SELECT d.* FROM live_documents d WHERE d.project_id=?
        OR d.id IN (SELECT document_id FROM chat_document_links WHERE session_id=?)
        ORDER BY COALESCE(d.story_number,2147483648),d.updated DESC,d.id""", (pid, sid)))
    if pid:
        owned = [row for row in rows if row["project_id"] == pid]
    else:
        owned = rows
    if ordinal is None:
        return [row for row in owned if row["body"].strip()]
    numbered = [row for row in owned if row["story_number"] == ordinal]
    if numbered:
        return numbered
    return [row for row in owned if row["story_number"] is None and row["kind"] == "chapter"
            and (match := re.match(r"^\s*(?:kapitel|chapter)\s+(\d+)\b", row["title"], re.I))
            and int(match[1]) == ordinal]


def choice(rows, kind):
    return {"handled": True, "choice": kind, "choices": [
        {"id": row["id"], "label": row["name"] if kind == "context" else row["title"]} for row in rows]}


def editorial_mode(text):
    if re.search(r"\b(?:vergleich\w*|compare)\b", text, re.I) and re.search(r"version|fassung|edition", text, re.I):
        return "compare"
    if re.search(r"story quality review|literary review", text, re.I):
        return "review"
    return ("both" if AUDIT.search(text) else "rewrite") if REWRITE.search(text) else "audit"


def cover_prompt(conn, pid, text):
    if not COVER.search(text):
        return text
    context = records.require(conn, "project", pid)
    bible = story.bible(conn, pid)
    notes = " ".join(bible.get(key, "")[:360] for key in ("places", "characters", "world", "voice"))
    return (f"Atmospheric book cover art for {context['name']}. {notes} "
            "Show one compelling scene, strong silhouette, leave space for title, no lettering or watermark. " + text).strip()[:1600]
