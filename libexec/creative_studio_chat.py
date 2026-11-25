"""Chat-owned content and server-side selection of creative actions."""

import json
import re
import time
import uuid

import creative_studio_organizer as records
import creative_studio_story as story

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
                         r"absatz|passage|formulierung\w*|formulier\w*|wortwahl|wording|prosa|prose|fassung|dokument|artikel|devlog|article)\b", re.I)
CREATE_PLAN = re.compile(r"\b(?:erstell\w*|entwirf\w*|plane|entwickl\w*|anlegen|plan|create|build|draft|design)\b", re.I)
IMPORT_PLAN = re.compile(r"\b(?:übernimm|übernehm\w*|importier\w*|adopt|import|save)\b", re.I)
QUESTION = re.compile(r"^\s*(?:was|wie|warum|findest|hältst|ist|sind|wäre|wirkt|what|how|why|do you|is|are|would)\b", re.I)
CHANGE = re.compile(r"\b(?:soll(?:en|te)?|sollten|ändere|ändern|ersetze|change|replace|should|make)\b", re.I)
DRAFT_CHAPTER = re.compile(r"^\s*(?:bitte\s+)?(?:schreib\w*|verfass\w*|setze|fortsetz\w*|write|draft|continue)"
                           r"\s+(?:mir\s+|uns\s+)?(?:das\s+|den\s+|the\s+)?(?:nächst\w*\s+|next\s+)?(?:kapitel|chapter)\b", re.I)
NO_DRAFT = re.compile(r"\b(?:(?:schreib\w*|verfass\w*)\s+(?:noch\s+)?(?:kein\w*|nicht)|(?:do not|don't)\s+(?:write|draft))\b[^.!?]*", re.I)


def number(value):
    return NUMBERS[value.casefold()] if value.casefold() in NUMBERS else int(value)


def title(text, fallback):
    match = TITLE.search(text)
    name = next((part for part in match.groups() if part), "") if match else ""
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
            return active["id"]
        if active and kind == "story" and active["kind"] == "custom":
            # Promote the neutral context without moving any of its contents.
            conn.execute("UPDATE projects SET kind='story',meta=json_set(meta,'$.chat_owned',json('true')) WHERE id=?", (active["id"],))
            return active["id"]
        if not active and len(contexts) == 1 and (kind != "story" or contexts[0]["kind"] in ("story", "novel")):
            return activate(conn, session["id"], contexts[0]["id"])
    pid, at = uuid.uuid4().hex, time.time()
    conn.execute("""INSERT INTO projects(id,name,kind,lang,meta,created,updated)
        VALUES(?,?,?,?,'{"chat_owned":true}',?,?)""",
        (pid, (name or session["title"] or "Unterhaltung")[:180], kind, lang, at, at))
    conn.execute("UPDATE sessions SET project_id=?,updated=? WHERE id=?", (pid, at, session["id"]))
    return pid


def requested_action(text, preferred, *, has_plan=False, has_prose=None, story_context=False):
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
    if re.search(r"\b(?:auf englisch|in english|englischer text)\b", text, re.I):
        return "en"
    if re.search(r"\b(?:auf deutsch|in german|deutscher text)\b", text, re.I):
        return "de"
    return fallback


def outline_count(text):
    match = re.search(r"\b(" + NUMBER + r")\s+(?:kapitel(?:n)?|chapters)\b", text, re.I)
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
