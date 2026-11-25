"""Persistent chapter plans, bounded narrative context, and reviewable drafts."""

import json
import math
import re
import sqlite3
import time
import uuid

import creative_studio_organizer as organizer
import creative_studio_knowledge as knowledge
from creative_studio_plan import PlanError, check_text

MIGRATION = """
ALTER TABLE documents ADD COLUMN story_number INTEGER;
ALTER TABLE documents ADD COLUMN story_plan TEXT NOT NULL DEFAULT '';
ALTER TABLE documents ADD COLUMN story_min INTEGER;
ALTER TABLE documents ADD COLUMN story_max INTEGER;
ALTER TABLE documents ADD COLUMN story_summary TEXT NOT NULL DEFAULT '';
ALTER TABLE documents ADD COLUMN story_summary_version INTEGER;
CREATE INDEX story_chapters ON documents(project_id,story_number);
CREATE INDEX story_jobs ON jobs(service,state,created);
"""
BIBLE = ("characters", "relationships", "places", "world", "timeline", "events",
         "threads", "perspective", "voice")
DEFAULTS = {"lang": "en", "minimum": 1000, "maximum": 1500, "opening": None}
OUTLINE_ACTIONS = ("outline", "generate", "review-chapter", "review-story")
STR = {"type": "string"}
MODEL = "story"
OUTPUT_BUDGET = 8192
CONTEXT_CHARS = 16_000
REVIEW_SLICE = 11_000
PRODUCTION_ASIDE = re.compile(
    r"\b(?:words?\s+(?:earlier|ago|remaining|of prose)|wörter\s+(?:zuvor|pro abschnitt)|"
    r"(?:this|the)\s+section\s+(?:of prose|meets the word count)|"
    r"(?:satisfies|meets)\s+the\s+(?:minimum|maximum|word count))\b", re.I)


def error(code, status=400):
    raise organizer.OrganizerError(code, status)


def count_words(text):
    prose = re.sub(r"(?m)^\s*#{1,6}\s+[^\n]*$", "", text)
    prose = re.sub(r"!\[[^\]]*\]\([^)]*\)|\x60{3}.*?\x60{3}", "", prose, flags=re.S)
    return len(re.findall(r"[^\W_]+(?:[’'\-][^\W_]+)*", prose, re.UNICODE))


def clean(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        error("story_input_invalid")
    return value.strip()


def bounds(low, high):
    if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 2**31 - 1:
        error("story_words_invalid")
    return low, high


def settings(project):
    values = json.loads(project["meta"]).get("story", {})
    return {**DEFAULTS, "lang": "de" if project["lang"] == "de" else "en", **values}


def bible(conn, pid):
    return {row["key"]: row["body"] for row in conn.execute(
        "SELECT key,body FROM memories WHERE project_id=? AND kind='story-bible'", (pid,)) if row["key"] in BIBLE}


def chapters(conn, pid, *, bodies=False, context_only=False):
    columns = """id,title,story_number AS number,story_plan AS plan,story_min AS minimum,
        story_max AS maximum,status,version,updated,story_summary,story_summary_version,lang"""
    if bodies:
        columns += ",body"
    if context_only:
        columns += ",length(trim(body)) AS text_length,substr(body,-2200) AS tail"
    rows = conn.execute(f"SELECT {columns} FROM live_documents WHERE project_id=? AND story_number IS NOT NULL"
                        " ORDER BY story_number,created,id", (pid,)).fetchall()
    return [dict(row) for row in rows]


def project_info(conn, pid):
    project = organizer.require(conn, "project", pid)
    rows = chapters(conn, pid)
    bodies = conn.execute("SELECT id,body FROM live_documents WHERE project_id=? AND story_number IS NOT NULL", (pid,))
    word_counts = {identifier: count_words(body) for identifier, body in bodies}
    for row in rows:
        # The word count is derived from the current version, including manual edits.
        row["words"] = word_counts.get(row["id"], 0)
    return {"settings": settings(project), "bible": bible(conn, pid), "chapters": rows}


def project_document(conn, pid, identifier):
    doc = organizer.require(conn, "document", identifier)
    if doc["project_id"] != pid:
        error("story_chapter_missing", 404)
    return doc


def managed_chapter(conn, pid, identifier):
    doc = project_document(conn, pid, identifier)
    if doc["story_number"] is None:
        error("story_chapter_missing", 404)
    return doc


def active_job(conn, pid):
    return conn.execute("""SELECT 1 FROM jobs WHERE service='story' AND state IN ('queued','running')
        AND json_extract(payload,'$.project_id')=?""", (pid,)).fetchone()


def add_chapter(conn, pid, item, profile, save_document, number=None):
    low, high = bounds(item.get("minimum", profile["minimum"]), item.get("maximum", profile["maximum"]))
    title = organizer.name_value(item.get("title"))
    plan = clean(item.get("plan", ""), 5000, required=True)
    if number is None:
        number = conn.execute("SELECT COALESCE(MAX(story_number),0)+1 FROM documents WHERE project_id=?",
                              (pid,)).fetchone()[0]
    identifier = save_document(conn, pid, title, "", "chapter", profile["lang"], "user", "Kapitelplanung")
    conn.execute("""UPDATE documents SET story_number=?,story_plan=?,story_min=?,story_max=?,status='planned'
        WHERE id=?""", (number, plan, low, high, identifier))
    return identifier


def mutate(conn, pid, action, body, save_document, store_message, *, job_id=None):
    project = organizer.require(conn, "project", pid)
    profile = settings(project)
    if action == "cancel":
        changed = conn.execute("""UPDATE jobs SET state='cancelled',updated=?
            WHERE id=? AND service='story' AND state IN ('queued','running') AND json_extract(payload,'$.project_id')=?""",
            (time.time(), body.get("job_id"), pid))
        if not changed.rowcount:
            error("story_job_closed", 409)
        return {"ok": True}, 200
    if action == "status":
        doc = managed_chapter(conn, pid, body.get("document_id"))
        status = body.get("status")
        if body.get("version") != doc["version"]:
            error("document_changed", 409)
        if status not in ("draft", "review", "approved") or not doc["body"].strip():
            error("story_status_invalid", 409)
        if doc["status"] == "approved" and status != "draft":
            error("story_approved", 409)
        conn.execute("UPDATE documents SET status=?,updated=? WHERE id=?", (status, time.time(), doc["id"]))
        return {"ok": True, "status": status}, 200
    if active_job(conn, pid):
        error("story_job_running", 409)
    if action in ("plan", "edit-plan", "generate", "outline") and conn.execute("""SELECT 1 FROM jobs
            WHERE service='production' AND json_extract(payload,'$.kind')='story'
            AND json_extract(payload,'$.project_id')=? AND state IN ('queued','running','paused','failed')""", (pid,)).fetchone():
        error("production_manages_chapters", 409)
    if action == "settings":
        low, high = bounds(body.get("minimum", profile["minimum"]), body.get("maximum", profile["maximum"]))
        lang = body.get("lang", profile["lang"])
        opening = body.get("opening", profile["opening"])
        if lang not in ("en", "de"):
            error("story_input_invalid")
        if opening is not None:
            doc = project_document(conn, pid, opening)
            if doc["story_number"] is not None or not doc["body"].strip():
                error("story_input_invalid")
        notes = body.get("bible", {})
        if not isinstance(notes, dict) or not notes.keys() <= set(BIBLE):
            error("story_input_invalid")
        at = time.time()
        for key, text in notes.items():
            text = clean(text, 5000)
            conn.execute("""INSERT INTO memories(id,project_id,kind,key,body,created)
                VALUES(?,?,'story-bible',?,?,?) ON CONFLICT(project_id,kind,key) DO UPDATE SET body=excluded.body""",
                (uuid.uuid4().hex, pid, key, text, at))
        conn.execute("UPDATE projects SET meta=json_set(meta,'$.story',json(?)),updated=? WHERE id=?",
                     (json.dumps({"lang": lang, "minimum": low, "maximum": high, "opening": opening}), at, pid))
        return project_info(conn, pid), 200
    if action == "plan":
        return {"id": add_chapter(conn, pid, body, profile, save_document)}, 201
    if action == "edit-plan":
        doc = managed_chapter(conn, pid, body.get("document_id"))
        if doc["status"] == "approved":
            error("story_approved", 409)
        low, high = bounds(body.get("minimum", doc["story_min"]), body.get("maximum", doc["story_max"]))
        plan = clean(body.get("plan", doc["story_plan"]), 5000, required=True)
        conn.execute("UPDATE documents SET story_plan=?,story_min=?,story_max=?,updated=? WHERE id=?",
                     (plan, low, high, time.time(), doc["id"]))
        return {"ok": True}, 200
    if action not in OUTLINE_ACTIONS:
        error("not_found", 404)
    sid = body.get("session_id")
    if sid and organizer.require(conn, "chat", sid)["project_id"] != pid:
        error("story_chat_mismatch", 409)
    instruction = clean(body.get("instruction", ""), 8000)
    user_message = clean(body.get("message", ""), 12000)
    payload = {"project_id": pid, "session_id": sid, "action": action, "instruction": instruction,
               "profile": profile, "bible": bible(conn, pid), "project_name": project["name"]}
    if action == "outline":
        total = body.get("count", 8)
        auto_bible = body.get("auto_bible") is True
        if type(total) is not int or not (0 if auto_bible else 1) <= total <= 2**31 - 1:
            error("story_input_invalid")
        payload["count"] = total
        payload["auto_bible"] = auto_bible
    elif action in ("generate", "review-chapter"):
        doc = managed_chapter(conn, pid, body.get("document_id"))
        if action == "generate":
            replacement = body.get("replace_draft") is True
            if doc["status"] == "approved":
                error("story_approved", 409)
            if replacement and body.get("version") != doc["version"]:
                error("document_changed", 409)
            if not replacement and (doc["status"] != "planned" or doc["body"].strip()):
                error("story_has_draft", 409)
            low, high = bounds(body.get("minimum", doc["story_min"]), body.get("maximum", doc["story_max"]))
            payload.update(minimum=low, maximum=high, replace_draft=replacement)
        if action == "review-chapter" and not doc["body"].strip():
            error("story_status_invalid", 409)
        payload.update(document_id=doc["id"], version=doc["version"], number=doc["story_number"],
                       for_review=body.get("for_review") is True)
    elif not any(row["body"].strip() for row in chapters(conn, pid, bodies=True)):
        error("story_no_text", 409)
    identifier, at = job_id or uuid.uuid4().hex, time.time()
    conn.execute("""INSERT INTO jobs(id,service,state,payload,result,created,updated)
        VALUES(?,'story','queued',?,'{}',?,?)""", (identifier, json.dumps(payload, ensure_ascii=False), at, at))
    if sid:
        labels = {"outline": "Kapitelübersicht", "generate": "Kapitelentwurf",
                  "review-chapter": "Kontinuitätsprüfung", "review-story": "Redaktionelle Gesamtprüfung"}
        store_message(conn, sid, "user", user_message or labels[action])
        store_message(conn, sid, "assistant", labels[action], {"kind": "story-job", "job_id": identifier})
    return {"id": identifier, "status": "queued"}, 202


def words_for_relevance(text):
    return {word for word in re.findall(r"[^\W\d_]{4,}", text.casefold())
            if word not in {"that", "with", "this", "from", "their", "chapter", "there", "have",
                            "eine", "einer", "werden", "kapitel", "diesen", "nicht"}}


def snippet(text, limit):
    return text if len(text) <= limit else text[:limit // 2] + "\n[… ]\n" + text[-limit // 2:]


def latest_summary(row):
    return row["story_summary"] if row["story_summary_version"] == row["version"] else ""


def context(conn, payload, current=None, source_limit=2200):
    anchor_id = payload["profile"].get("opening")
    opening = project_document(conn, payload["project_id"], anchor_id) if anchor_id else None
    rows = chapters(conn, payload["project_id"], context_only=True)
    if current:
        rows = [row for row in rows if row["number"] < current["story_number"]]
    finished = [row for row in rows if row["text_length"]]
    query = words_for_relevance(payload["instruction"] + " " + (current["story_plan"] if current else ""))
    prior = finished[:-2]
    prior = sorted(prior, key=lambda r: (len(query & words_for_relevance(r["plan"] + latest_summary(r))),
                                         r["number"]), reverse=True)[:5]
    chosen = sorted(prior + finished[-2:], key=lambda r: r["number"])
    legacy = conn.execute("""SELECT kind,key,body FROM memories WHERE project_id=?
        AND kind IN ('character','place','plot','timeline','continuity','bible','voice-profile')
        ORDER BY created DESC LIMIT 16""", (payload["project_id"],)).fetchall()
    chunks = [f"{key}: {snippet(payload['bible'][key], 650)}" for key in BIBLE if payload["bible"].get(key)]
    chunks += [f"{row['kind']} {row['key']}: {snippet(row['body'], 280)}" for row in legacy]
    if folder := knowledge.context_for(conn, project_id=payload["project_id"],
                                       query=payload["instruction"] + " " + (current["story_plan"] if current else "")):
        chunks.append("Folder canon (inherited):\n" + snippet(folder, 2000))
    if opening and source_limit:
        chunks.append("Canonical opening (source excerpt):\n" + snippet(opening["body"], source_limit))
    for row in chosen:
        summary = latest_summary(row) or ("Plan: " + row["plan"] + "\nText excerpt: " + row["tail"][-650:])
        chunks.append(f"Chapter {row['number']} {row['title']} ({row['status']}):\n" + snippet(summary, 760))
    if finished:
        recent_chars = 1800 if source_limit else 360
        chunks.append("End of chapter " + str(finished[-1]["number"]) + ":\n" + finished[-1]["tail"][-recent_chars:])
    versions = {row["id"]: row["version"] for row in chosen}
    if opening:
        versions[opening["id"]] = opening["version"]
    return snippet("\n\n".join(chunks), CONTEXT_CHARS), chosen, opening, versions


def chapter_prefix(current, opening):
    return opening["body"] if current["story_number"] == 1 and opening else ""


def sections(word_count, low, high):
    if word_count > high:
        raise PlanError("story_opening_too_long")
    if word_count >= low and (low + high) // 2 <= word_count:
        return 0
    remaining = (low + high) / 2 - word_count
    return 1 if remaining <= 950 else math.ceil(remaining / 650)


def section_bounds(words, low, high, left):
    target = round(((low + high) / 2 - words) / left)
    if left == 1:
        return max(1, low - words), high - words, max(1, target)
    return max(1, target - 170), max(1, target + 145), max(1, target)


def repeats(text, earlier):
    def sentences(prose):
        for sentence in re.split(r"(?<=[.!?])\s+|\n{2,}", prose):
            normalized = re.findall(r"[^\W_]+", sentence.casefold())
            if len(normalized) >= 12:
                yield " ".join(normalized), sentence.strip()[:240]

    seen = dict(sentences(earlier))
    found = []
    for key, quote in sentences(text):
        if key in seen and quote not in found and len(found) < 12:
            found.append(quote)
        seen[key] = quote
    return found


def trim_echo(text, previous):
    """Remove a copied lead paragraph from a generated candidate only."""
    def normalize(value):
        return " ".join(re.findall(r"[^\W_]+", value.casefold()))

    existing = {normalize(part) for part in re.split(r"\n[ \t]*\n", previous) if count_words(part) >= 12}
    parts = re.split(r"\n[ \t]*\n", text)
    start = next((index for index, part in enumerate(parts) if normalize(part) not in existing), len(parts))
    return "\n\n".join(parts[start:])


def schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def rejected(code, answer, finish, evidence=None):
    """A model failure that keeps a bounded copy of the original answer for the protected diagnostics.

    `evidence` is the proof of the failed call (alias, variant, loaded skills), so the failure names its model."""
    error = PlanError(code)
    error.raw, error.finish, error.evidence = str(answer)[:6000], finish, evidence
    return error


def structured(call, lang, mode, prompt, properties, limit):
    answer, evidence, finish = call(lang, mode, prompt, limit, schema(properties))
    if finish == "length":
        raise rejected("story_output_truncated", answer, finish, evidence)
    try:
        data = json.loads(answer)
    except json.JSONDecodeError as exc:
        raise rejected("story_model_format", answer, finish, evidence) from exc
    if not isinstance(data, dict):
        raise rejected("story_model_format", answer, finish, evidence)
    return data, evidence


def review(call, lang, text, canon, *, whole=False):
    categories = ("continuity", "repetition", "pov", "structure", "style")
    fields = schema({"quote": STR, "issue": STR, "category": {"type": "string", "enum": list(categories)}})
    prompt = (
        "Conduct a critical narrative audit. Check character facts, world rules, timeline, spatial cause and "
        "effect, point of view, repetitions and whether the ending or open threads follow from earlier beats. "
        "Use the supplied canon as reference. Preserve deliberate motifs and ambiguity. Distinguish contradictions "
        "from weaknesses and do not invent a canon fact. Quote an exact contiguous passage from the reviewed text "
        "for every actual problem. Return an empty findings array if there is no problem. Do not list strengths or use 'None' as an issue. "
        "Return up to four findings and a concrete synopsis of decisions, events and unresolved "
        "threads (up to 115 words). Write synopsis and findings in " + ("English" if lang == "en" else "German") +
        (" for the whole-story material." if whole else ".") + "\n\nCANON\n" + canon + "\n\nREVIEWED TEXT\n" + text)
    result, evidence = structured(call, lang, "audit", prompt, {"summary": STR,
                                  "findings": {"type": "array", "maxItems": 4, "items": fields}}, 900)
    summary, findings = result.get("summary"), result.get("findings")
    if not isinstance(summary, str) or not summary.strip() or not isinstance(findings, list):
        raise PlanError("story_model_format")
    kept = [{"quote": f["quote"][:280], "issue": f["issue"][:700], "category": f["category"][:100]}
            for f in findings if isinstance(f, dict) and all(isinstance(f.get(k), str) for k in ("quote", "issue", "category"))
            and f["category"] in categories and f["issue"].strip().casefold() not in ("", "none", "n/a", "kein problem")
            and f["quote"].strip() and f["quote"] in text]
    return {"summary": summary[:1600], "findings": kept[:4], "discarded_findings": len(findings) - len(kept[:4]),
            "evidence": evidence}


def text_windows(body):
    start = 0
    while start < len(body):
        end = min(len(body), start + REVIEW_SLICE)
        if end < len(body):
            split = body.rfind("\n\n", start + REVIEW_SLICE // 2, end)
            if split > start:
                end = split + 2
        yield body[start:end]
        start = end


class StoryWorker:
    def __init__(self, db, lock, call, style_audit, skill_text, save_document):
        self.db, self.lock, self.call = db, lock, call
        self.style_audit, self.skill_text, self.save_document = style_audit, skill_text, save_document

    def public(self, row):
        payload, result = json.loads(row["payload"]), json.loads(row["result"] or "{}")
        return {**{key: value for key, value in result.items() if key not in ("pieces", "versions")},
                "id": row["id"], "status": row["state"], "project_id": payload["project_id"],
                "document_id": payload.get("document_id"), "action": payload["action"]}

    def store(self, conn, ident, result, state="running"):
        changed = conn.execute("UPDATE jobs SET result=?,state=?,updated=? WHERE id=? AND state IN ('queued','running')",
                               (json.dumps(result, ensure_ascii=False), state, time.time(), ident)).rowcount
        if not changed:
            raise PlanError("story_job_closed")

    def checkpoint(self, ident, result, **update):
        result.update(update)
        with self.lock, self.db() as conn:
            self.store(conn, ident, result)

    def verify_sources(self, conn, versions):
        for ident, version in versions.items():
            live = organizer.require(conn, "document", ident)
            if live["version"] != version:
                raise PlanError("story_context_changed")

    def valid_target(self, doc, payload):
        return (doc["version"] == payload["version"] and doc["status"] != "approved" and
                (payload.get("replace_draft") or (doc["status"] == "planned" and not doc["body"].strip())))

    def plan_sections(self, lang, canon, doc, payload, total, completed, count):
        size = min(8, total - count)
        response, evidence = structured(self.call, lang, "generate",
            f"Split the chapter into exactly {size} successive scene beats, sections {count + 1} to {count + size} "
            f"out of {total}. Assign each action to only one section. Give a brief stage and stopping point "
            "for each section. Do not summarize the opening already written. Only the final section may reach the final beat. "
            "Be concrete about which event is saved for a later section. Use the author's stated closing beat. "
            "\n\nCHAPTER PLAN\n" + doc["story_plan"] + "\n\nAUTHOR BRIEF\n" + payload["instruction"] +
            "\n\nCANON\n" + canon + "\n\nPRIOR SECTION PLANS\n" + "\n".join(completed[-8:]),
            {"sections": {"type": "array", "items": STR}}, min(1800, 115 * size + 160))
        values = response.get("sections")
        if not isinstance(values, list) or len(values) != size:
            raise PlanError("story_outline_incomplete")
        return [clean(item, 1600, required=True) for item in values], evidence

    def draft(self, ident, payload, result):
        conn = self.db()
        doc = managed_chapter(conn, payload["project_id"], payload["document_id"])
        if not self.valid_target(doc, payload):
            raise PlanError("story_context_changed")
        canon, earlier, opening, versions = context(conn, payload, doc, source_limit=0)
        if result.get("versions", versions) != versions:
            raise PlanError("story_context_changed")
        prefix = chapter_prefix(doc, opening)
        parts = result.get("pieces", [])
        low, high = payload.get("minimum", doc["story_min"]), payload.get("maximum", doc["story_max"])
        total = sections(count_words(prefix), low, high)
        lang = doc["lang"] or payload["profile"]["lang"]
        if opening and not (payload["bible"].get("events") or payload["bible"].get("timeline")):
            digest = result.get("opening_summary")
            if not digest:
                digest = review(self.call, lang, snippet(opening["body"], REVIEW_SLICE), canon)["summary"]
                self.checkpoint(ident, result, opening_summary=digest, versions=versions)
            canon = snippet(canon + "\n\nOpening events already on the page:\n" + digest, CONTEXT_CHARS)
        count = count_words(prefix) + sum(map(count_words, parts))
        plans = result.get("section_plans", [])
        proofs = result.get("section_evidence", [])
        self.checkpoint(ident, result, stage="writing", total_sections=total, completed_sections=len(parts), versions=versions)
        for index in range(len(parts), total):
            if total > 1 and index == len(plans):
                batch, evidence = self.plan_sections(lang, canon, doc, payload, total, plans, index)
                plans.extend(batch)
                self.checkpoint(ident, result, section_plans=plans, section_plan_evidence=evidence)
            tail = parts[-1][-360:] if parts else ""
            earlier_beats = "\n".join(f"Section {position + 1} ended: {part[-200:]}"
                                      for position, part in enumerate(parts[-8:-2], max(0, index - 8)))
            lower, upper, target = section_bounds(count, low, high, total - index)
            if upper <= 0:
                raise PlanError("story_length_failed")
            phase = ("End this chapter at its planned closing beat." if index == total - 1 else
                     "Stop before the other sections' events. Do not resolve the chapter or reach its closing beat.")
            beat = plans[index] if total > 1 else doc["story_plan"]
            instruction = (
                f"Write NEW prose for chapter {doc['story_number']}, {doc['title']}, section {index + 1} of {total}. "
                f"Use about {target} words, within {lower}–{upper}. Use only {'English' if lang == 'en' else 'German'}. "
                "Begin with the next physical action after the supplied excerpt. Never quote, restart or recap it, add headings, "
                "explain the process, jump ahead to later chapters, or quote the instructions. " + phase +
                "\n\nONLY BEAT TO WRITE\n" + beat + "\n\nAUTHOR BRIEF FOR THE CHAPTER\n" + payload["instruction"] +
                ("\nLater planned beat (do not write this yet): " + plans[index + 1] if index + 1 < len(plans) else "") +
                "\n\nSTORY CANON\n" + canon + "\n\nEARLIER SECTION BEATS\n" + earlier_beats +
                "\n\nALREADY WRITTEN (DO NOT COPY)\n" + tail +
                "\n\nWrite only the new scene prose for the assigned beat.")
            earlier_text = "\n\n".join([prefix, *parts, *(row["tail"] for row in earlier[-2:])])
            for attempt in range(3):
                prompt = instruction
                if attempt:
                    prompt += (f"\n\nEarlier attempt contained {measured} words. Replace that attempt completely. "
                               f"Deliver about {target} words of new prose, without a heading.")
                    if repeated:
                        prompt += " The attempt repeated text already present in the manuscript. Advance the action with new sentences."
                piece, evidence, finish = self.call(lang, "generate", prompt, min(5400, max(520, target * 2 + 350)))
                piece = re.sub(r"^\s*#{1,6}\s+[^\n]*\n+", "", piece).strip()
                piece = trim_echo(piece, earlier_text)
                measured = count_words(piece)
                report = check_text(piece, {"lang": lang, "words": None}, self.skill_text())
                repeated = repeats(piece, earlier_text)
                copied = len(repeated) >= 2
                aside = bool(PRODUCTION_ASIDE.search(piece))
                self.checkpoint(ident, result, attempt={"section": index + 1, "number": attempt + 1, "words": measured,
                                                       "language": report["language"], "copied_sentences": len(repeated),
                                                       "finish_reason": finish, "production_aside": aside})
                if finish != "length" and lower <= measured <= upper and not report["issues"] and not copied and not aside:
                    break
            else:
                raise PlanError("story_repetition_failed" if copied else "story_metatext" if aside else "story_length_failed")
            parts.append(piece)
            proofs.append(evidence)
            count += measured
            self.checkpoint(ident, result, pieces=parts, completed_sections=len(parts),
                            words=count, generation=evidence, section_evidence=proofs)
        continuation = "\n\n".join(parts)
        body = prefix + ("\n\n" if prefix and continuation else "") + continuation
        count = count_words(body)
        if not low <= count <= high:
            raise PlanError("story_length_failed")
        self.checkpoint(ident, result, stage="checking", words=count)
        audited = self.audit_chapter(lang, body, canon, continuation or body, earlier, prefix if continuation else "")
        with self.lock, conn:
            saved = managed_chapter(conn, payload["project_id"], doc["id"])
            if not self.valid_target(saved, payload):
                raise PlanError("story_context_changed")
            self.verify_sources(conn, versions)
            version = organizer.update_document(conn, saved, saved["title"], body, "Kapitelentwurf mit Human Writing", "generated")
            status = "review" if payload["for_review"] else "draft"
            conn.execute("""UPDATE documents SET status=?,story_summary=?,story_summary_version=?,
                story_min=?,story_max=? WHERE id=?""", (status, audited.get("summary", ""), version, low, high, doc["id"]))
            result.update(stage="done", review=audited, words=count, version=version, chapter_status=status,
                          opening_preserved=bool(prefix and body.startswith(prefix)),
                          context_documents=list(versions), title=doc["title"])
            result.pop("pieces", None)
            self.store(conn, ident, result, "completed")

    def audit_chapter(self, lang, body, canon, new_text, earlier, prefix=""):
        report = self.style_audit(body, lang, "fiction")
        checked = {"style": {"skill_version": report["skill_version"], "findings": report["findings"][:25],
                            "finding_count": len(report["findings"])},
                   "repetitions": repeats(new_text, "\n\n".join([prefix, *(row["tail"] for row in earlier[-2:])])),
                   "findings": []}
        summaries = []
        for part in text_windows(body):
            try:
                audit = review(self.call, lang, part, canon)
                summaries.append(audit["summary"])
                checked["findings"].extend(audit["findings"])
                checked["evidence"] = audit["evidence"]
                canon = snippet(canon + "\n\nPrevious section synopsis:\n" + audit["summary"], CONTEXT_CHARS)
            except (OSError, ValueError, KeyError) as exc:
                checked["error"] = str(exc) if isinstance(exc, PlanError) else "story_review_unavailable"
            else:
                checked["discarded_findings"] = checked.get("discarded_findings", 0) + audit["discarded_findings"]
        checked["summary"] = snippet("\n".join(summaries), 2200)
        return checked

    def outline(self, ident, payload, result):
        conn = self.db()
        canon, _, _, versions = context(conn, payload)
        existing = chapters(conn, payload["project_id"])
        outlines = result.get("outline", [])
        if result.get("versions", versions) != versions:
            raise PlanError("story_context_changed")
        lang = payload["profile"]["lang"]
        language = "English" if lang == "en" else "German"
        total = payload["count"]
        bible_draft = result.get("bible_draft")
        batches = range(len(outlines), total, 8) if total else ((0,) if bible_draft is None else ())
        for start in batches:
            size = min(8, total - start)
            brief = (
                f"Plan exactly {size} chapters, slots {start + 1} to {start + size} of this {total}-chapter arc, "
                f"in {language} for {payload['project_name']}. Each plan is 35–60 words with concrete events, "
                "a character decision and a closing beat. Respect established events and close the main arc at the "
                "end of the requested total; do not write prose or change existing chapters.\n\nAUTHOR BRIEF\n" +
                payload["instruction"] + "\n\nCANON\n" + canon + "\n\nEXISTING PLANS AND PARTS\n" +
                "\n".join(x["title"] + ": " + x["plan"][:420] for x in (existing + outlines)[-8:]))
            fields = {"chapters": {"type": "array", "items": schema({"title": STR, "plan": STR})}} if size else {}
            if payload.get("auto_bible") and bible_draft is None:
                fields["bible"] = schema({key: STR for key in BIBLE})
                brief += ("\nDraft a concise story bible in the requested language, 25–65 words per field. "
                          "Describe named characters and their relationships, places, world rules, relative timeline, "
                          "important events, open threads, a consistent point of view and a distinctive voice. "
                          "Keep established facts and treat new material as a proposal.")
            proposal, evidence = structured(self.call, lang, "generate", brief, fields,
                                             min(3500, 190 * size + (1250 if "bible" in fields else 180)))
            batch = proposal.get("chapters", [])
            if not isinstance(batch, list) or len(batch) != size:
                raise PlanError("story_outline_incomplete")
            for item in batch:
                if not isinstance(item, dict):
                    raise PlanError("story_model_format")
                clean(item.get("title"), 180, required=True)
                clean(item.get("plan"), 5000, required=True)
            outlines.extend(batch)
            if "bible" in fields:
                guide = proposal.get("bible")
                if not isinstance(guide, dict) or set(guide) != set(BIBLE):
                    raise PlanError("story_model_format")
                bible_draft = {key: clean(guide[key], 5000, required=True) for key in BIBLE}
            self.checkpoint(ident, result, stage="planning", outline=outlines, planned=len(outlines),
                            versions=versions, evidence=evidence, bible_draft=bible_draft)
        with self.lock, conn:
            self.verify_sources(conn, versions)
            for key, value in (bible_draft or {}).items():
                conn.execute("""INSERT INTO memories(id,project_id,kind,key,body,created)
                    VALUES(?,?,'story-bible',?,?,?) ON CONFLICT(project_id,kind,key)
                    DO UPDATE SET body=excluded.body WHERE trim(memories.body)=''""",
                    (uuid.uuid4().hex, payload["project_id"], key, value, time.time()))
            ids = [add_chapter(conn, payload["project_id"], item, payload["profile"], self.save_document) for item in outlines]
            result.update(stage="done", chapter_ids=ids, bible_saved=bool(bible_draft))
            result.pop("bible_draft", None)
            self.store(conn, ident, result, "completed")

    def run_review(self, ident, payload, result):
        conn = self.db()
        doc = (managed_chapter(conn, payload["project_id"], payload["document_id"])
               if payload["action"] == "review-chapter" else None)
        canon, earlier, _, versions = context(conn, payload, doc)
        if payload["instruction"]:
            canon = snippet(canon + "\n\nAUTHOR REVIEW FOCUS\n" + payload["instruction"], CONTEXT_CHARS)
        lang = doc["lang"] if doc else payload["profile"]["lang"]
        self.checkpoint(ident, result, stage="checking")
        if doc:
            versions[doc["id"]] = doc["version"]
            if doc["version"] != payload["version"]:
                raise PlanError("story_context_changed")
            audited = self.audit_chapter(lang, doc["body"], canon, doc["body"], earlier)
        else:
            material = []
            problems = []
            for row in chapters(conn, payload["project_id"], bodies=True):
                if not row["body"].strip():
                    continue
                versions[row["id"]] = row["version"]
                summary = latest_summary(row)
                if not summary:
                    checked = self.audit_chapter(lang, row["body"], canon, row["body"], [])
                    summary = checked["summary"] or snippet(row["body"], 850)
                    problems.extend(checked["findings"])
                material.append(f"Chapter {row['number']} {row['title']}\n{summary}")
            # Review every batch of chapter summaries, carrying forward the conclusions.
            synopsis, evidence, omitted = "", {}, 0
            for part in text_windows("\n\n".join(material)):
                reviewed = review(self.call, lang, part, snippet(canon + "\nPrior review: " + synopsis, CONTEXT_CHARS), whole=True)
                synopsis = reviewed["summary"]
                problems.extend(reviewed["findings"])
                omitted += reviewed["discarded_findings"]
                evidence = reviewed["evidence"]
            audited = {"summary": synopsis, "findings": problems, "evidence": evidence,
                       "discarded_findings": omitted, "chapters_reviewed": len(material)}
        with self.lock, conn:
            self.verify_sources(conn, versions)
            if doc and audited.get("summary") and not audited.get("error"):
                conn.execute("UPDATE documents SET story_summary=?,story_summary_version=? WHERE id=?",
                             (audited["summary"], doc["version"], doc["id"]))
            self.store(conn, ident, {**result, "stage": "done", "review": audited}, "completed")

    def run(self):
        while True:
            conn = self.db()
            row = conn.execute("SELECT * FROM jobs WHERE service='story' AND state IN ('queued','running')"
                               " ORDER BY created LIMIT 1").fetchone()
            if not row:
                time.sleep(.5)
                continue
            ident, payload, result = row["id"], json.loads(row["payload"]), json.loads(row["result"] or "{}")
            try:
                if payload["action"] == "generate":
                    self.draft(ident, payload, result)
                elif payload["action"] == "outline":
                    self.outline(ident, payload, result)
                else:
                    self.run_review(ident, payload, result)
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                with self.lock, conn:
                    conn.execute("""UPDATE jobs SET state='failed',result=?,updated=?
                        WHERE id=? AND state IN ('queued','running')""",
                        (json.dumps({**result, "error": str(exc) if isinstance(exc, (PlanError, organizer.OrganizerError))
                                     else "story_service_unavailable"}, ensure_ascii=False), time.time(), ident))
