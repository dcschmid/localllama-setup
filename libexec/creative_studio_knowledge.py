"""Optional folder knowledge (world bibles) with inheritance, proposals, and export."""

import json
import time
import uuid

import re

import creative_studio_organizer as organizer

MIGRATION = """
CREATE TABLE knowledge_entries(id TEXT PRIMARY KEY, folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    category TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'reference', version INTEGER NOT NULL DEFAULT 1,
    created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX knowledge_folder ON knowledge_entries(folder_id, category, title);
CREATE TABLE knowledge_versions(id TEXT PRIMARY KEY, entry_id TEXT NOT NULL REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    version INTEGER NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
    source TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX knowledge_versions_entry ON knowledge_versions(entry_id, version DESC);
CREATE TABLE knowledge_suggestions(id TEXT PRIMARY KEY, folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    entry TEXT NOT NULL, origin TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE INDEX knowledge_suggestions_folder ON knowledge_suggestions(folder_id, created);
"""

STATUSES = ("confirmed", "reference", "idea", "unresolved")
VISUAL_KEY = "visual-profile"
VISUAL_KEYS = ("template", "ratio", "style", "palette")
LIMITS = {"category": 60, "title": 200, "content": 20_000, "source": 300, "origin": 300}
SELECT_LIMIT = 24
BLOCK_CHARS = 10_000
SNIPPET_CHARS = 900
STR = {"type": "string", "minLength": 1, "maxLength": 4000}
SUGGESTION_SCHEMA = {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
    "category": {"type": "string", "minLength": 1, "maxLength": 60},
    "title": {"type": "string", "maxLength": 200},
    "content": STR, "source": {"type": "string", "maxLength": 300}},
    "required": ["category", "title", "content"]}}


class KnowledgeError(organizer.OrganizerError):
    """Folder knowledge failures ride the organizer error channel."""


def _text(value, limit, *, required=True):
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise KnowledgeError("knowledge_field_invalid")
    cleaned = value.strip()
    if required and not cleaned:
        raise KnowledgeError("knowledge_field_invalid")
    if len(cleaned) > limit:
        raise KnowledgeError("knowledge_field_invalid")
    return cleaned


def _id(value):
    if not isinstance(value, str) or not organizer.ID.fullmatch(value):
        raise KnowledgeError("knowledge_id_invalid")
    return value


def _folder(conn, identifier):
    if not isinstance(identifier, str) or not organizer.ID.fullmatch(identifier):
        raise KnowledgeError("knowledge_folder_invalid")
    return organizer.require(conn, "folder", identifier)


def _public(entry):
    return {"id": entry["id"], "folder_id": entry["folder_id"], "category": entry["category"],
            "title": entry["title"], "content": entry["content"], "source": entry["source"],
            "status": entry["status"], "version": entry["version"],
            "created": entry["created"], "updated": entry["updated"]}


def _row(conn, entry_id):
    row = conn.execute("SELECT * FROM knowledge_entries WHERE id=?", (entry_id,)).fetchone()
    if row is None:
        raise KnowledgeError("knowledge_entry_missing", 404)
    return _public(row)


def chain(conn, folder_id):
    """Folder first, parents last; depth guard mirrors the organizer tree limit."""
    _folder(conn, folder_id)
    steps, cursor, seen = [], folder_id, set()
    while cursor and len(steps) < 64:
        if cursor in seen:
            raise KnowledgeError("knowledge_folder_cycle")
        seen.add(cursor)
        row = conn.execute("SELECT id,folder_id,name FROM folders WHERE id=?", (cursor,)).fetchone()
        if row is None:
            break
        steps.append({"id": row["id"], "name": row["name"]})
        cursor = row["folder_id"]
    return steps


def _load(conn, folder_ids):
    holders = json.dumps(sorted(folder_ids))
    return [dict(entry) for entry in conn.execute(
        """SELECT * FROM knowledge_entries WHERE folder_id IN (SELECT value FROM json_each(?))
        ORDER BY category,title,updated DESC""", (holders,)).fetchall()]


def merge(conn, folder_id):
    """Inheritance view: nearest folder wins per category+title; equal confirmed titles surface as conflicts."""
    steps = chain(conn, folder_id)
    owned = {folder["id"]: _load(conn, [folder["id"]]) for folder in steps}
    entries, depth = [], {}
    for level, folder in enumerate(steps):
        for entry in owned[folder["id"]]:
            slot = (entry["category"].casefold(), entry["title"].casefold())
            if slot not in depth:
                depth[slot] = level
                entries.append(entry)
    conflicts = []
    for level, folder in enumerate(steps):
        for entry in owned[folder["id"]]:
            slot = (entry["category"].casefold(), entry["title"].casefold())
            holder = depth.get(slot)
            if holder is None or holder >= level or entry["status"] != "confirmed":
                continue
            winner = next((item for item in entries
                           if item["folder_id"] == steps[holder]["id"]
                           and (item["category"].casefold(), item["title"].casefold()) == slot), None)
            if winner and winner["status"] == "confirmed" and winner["content"] != entry["content"]:
                conflicts.append((entry, winner))  # (inherited parent entry, overriding nearest entry)
    return steps, entries, conflicts


def profile(conn, folder_id):
    """Standard visual profile: newest along the chain; None keeps existing behaviour."""
    for folder in chain(conn, folder_id):
        row = conn.execute("""SELECT content FROM knowledge_entries WHERE folder_id=? AND category=?
            ORDER BY updated DESC LIMIT 1""", (folder["id"], VISUAL_KEY)).fetchone()
        if row:
            try:
                saved = json.loads(row["content"])
            except ValueError:
                raise KnowledgeError("knowledge_profile_invalid") from None
            return {key: str(saved.get(key, ""))[:400] for key in VISUAL_KEYS}
    return None


def select(conn, folder_id, query, *, limit=SELECT_LIMIT, budget=BLOCK_CHARS):
    """Selective, budgeted injection for chats and writing jobs; never a full dump."""
    steps, entries, conflicts = merge(conn, folder_id)
    if not entries and not conflicts:
        return {"text": "", "used": 0, "folders": []}
    names = {folder["id"]: folder["name"] for folder in steps}
    injectable = [entry for entry in entries if entry["status"] != "idea" and entry["category"] != "idea"]
    if query:
        terms = _terms(query)
        ranked = sorted(injectable, key=lambda entry: (
            -len(terms & _terms(entry["title"] + " " + entry["content"])),
            STATUSES.index(entry["status"]) if entry["status"] in STATUSES else len(STATUSES),
            entry["category"], entry["title"]))
        chosen, overflow = ranked[:limit], ranked[limit:]
        chosen += [entry for entry in overflow if entry["status"] == "confirmed"][:4]
    else:
        chosen = injectable[:limit]
    used, chunks = 0, []
    for entry in chosen:
        body = _clip(entry["content"], SNIPPET_CHARS) if len(entry["content"]) > SNIPPET_CHARS else entry["content"]
        chunk = f"{entry['category']} · {entry['title']}: {body}"
        if used + len(chunk) > budget:
            break
        chunks.append(chunk)
        used += len(chunk)
    for parent, child in conflicts:
        note = ("Konflikt (als ungeklärt melden, nicht auflösen): "
                f"{parent['category']} · {parent['title']} — {names.get(parent['folder_id'], '')}: "
                f"{_clip(parent['content'], 220)} vs. {names.get(child['folder_id'], '')}: "
                f"{_clip(child['content'], 220)}")
        if used + len(note) > budget:
            break
        chunks.append(note)
        used += len(note)
    return {"text": "\n".join(chunks), "used": len(chunks),
            "folders": sorted({names[entry["folder_id"]] for entry in chosen if entry["folder_id"] in names})}


def context(conn, folder_id, query, *, budget=BLOCK_CHARS):
    """Prompt block for chat/task assembly; '' when the folder chain is empty."""
    block = select(conn, folder_id, query, budget=budget)
    if not block["text"]:
        return ""
    source = "Bestätigtes Ordnerwissen (Kanon) und Referenzen dieser Ordnerkette. " \
             "Behandle Widersprüche als ungeklärt und melde sie; übernehme nichts Neues ohne Rückfrage.\n\n"
    return source + block["text"]


def view(conn, folder_id):
    steps, entries, conflicts = merge(conn, folder_id)
    names = {folder["id"]: folder["name"] for folder in steps}
    return {"folder_id": folder_id, "chain": [{"id": folder["id"], "name": folder["name"]} for folder in steps],
            "entries": [{**entry, "folder_name": names.get(entry["folder_id"], "")} for entry in entries],
            "own": [entry for entry in entries if entry["folder_id"] == folder_id],
            "inherited": [{**entry, "folder_name": names.get(entry["folder_id"], "")}
                          for entry in entries if entry["folder_id"] != folder_id],
            "conflicts": [[parent, child] for parent, child in conflicts],
            "suggestions": suggestions(conn, folder_id), "profile": profile(conn, folder_id),
            "hint": hint(conn, folder_id)}


def hint(conn, folder_id):
    try:
        steps, entries, _ = merge(conn, folder_id)
    except (KnowledgeError, organizer.OrganizerError):
        return None
    names = {folder["id"]: folder["name"] for folder in steps}
    for folder in steps:
        rows = [entry for entry in entries if entry["folder_id"] == folder["id"]]
        if any(entry["status"] in ("confirmed", "reference") for entry in rows):
            return {"folder_id": folder["id"], "name": names[folder["id"]], "count": len(rows)}
    return None


def _terms(text):
    return {word for word in re.findall(r"[^\W\d_]{4,}", (text or "").casefold())}


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit // 2] + "\n[… ]\n" + text[-limit // 2:]


def owner_folder(conn, *, project_id=None, session_id=None):
    """Folder owning knowledge for a project or chat; context projects resolve via their chat."""
    if isinstance(project_id, str) and organizer.ID.fullmatch(project_id):
        row = conn.execute("SELECT folder_id FROM projects WHERE id=?", (project_id,)).fetchone()
        if row and row["folder_id"]:
            return row["folder_id"]
        owned = conn.execute("""SELECT s.folder_id FROM sessions s JOIN chat_contexts c ON c.chat_id=s.id
            WHERE c.context_id=? AND s.folder_id IS NOT NULL LIMIT 1""", (project_id,)).fetchone()
        if owned:
            return owned["folder_id"]
    if isinstance(session_id, str) and organizer.ID.fullmatch(session_id):
        row = conn.execute("SELECT folder_id FROM sessions WHERE id=?", (session_id,)).fetchone()
        return row["folder_id"] if row else None
    return None


def context_for(conn, *, project_id=None, session_id=None, query=""):
    """Prompt block for chat/task assembly; '' without a folder or knowledge."""
    folder = owner_folder(conn, project_id=project_id, session_id=session_id)
    if not folder:
        return ""
    try:
        block = select(conn, folder, query)
    except (KnowledgeError, organizer.OrganizerError):
        return ""
    if not block["text"]:
        return ""
    return ("Bestätigtes Ordnerwissen (Kanon) und Referenzen dieser Ordnerkette. Widersprüche bleiben ungeklärt "
            "und werden gemeldet; nichts Neues ohne Rückfrage übernehmen.\n\n" + block["text"])


def profile_default(conn, current, *, project_id=None, session_id=None):
    """Folder standard applies only to untouched profiles; authored profiles keep priority."""
    if not current or current.get("version"):
        return current
    folder = owner_folder(conn, project_id=project_id, session_id=session_id)
    saved = profile(conn, folder) if folder else None
    if not saved:
        return current
    import creative_studio_visual as visual
    key = saved.get("template")
    if key not in visual.TEMPLATES:
        description = " ".join((key or "", saved.get("style", "")))
        key = visual.choice(description, riff=bool(visual.RIFF.search(description))) or current["template"]
    updated = {**current, **visual.template(key)}
    for key in ("ratio", "palette", "style"):
        if saved.get(key):
            updated[key] = saved[key]
    return updated


def seed_profile(conn, project_id, current):
    """Persist the folder standard onto a not-yet-authored story profile."""
    updated = profile_default(conn, current, project_id=project_id)
    if updated is not current and not current.get("version"):
        updated["version"] = 1
        conn.execute("""UPDATE projects SET meta=json_set(meta,'$.visual_profile',json(?))
            WHERE id=? AND json_extract(meta,'$.visual_profile.version')=0""",
                     (json.dumps(updated, ensure_ascii=False), project_id))
    return updated


def propose_from_job(conn, payload, result):
    """Established chapter facts wait as suggestions; nothing becomes canon automatically."""
    if payload.get("kind") != "story":
        return 0
    folder = owner_folder(conn, project_id=payload.get("project_id"), session_id=payload.get("session_id"))
    if not folder:
        return 0
    items = [{"category": entry.get("kind", "fact"), "title": f"Kapitel {item['number']}",
              "content": entry.get("fact", ""), "source": f"production:{payload.get('project_id', '')}"}
             for item in result.get("chapter_results", []) for entry in item.get("memory", [])
             if entry.get("status") == "established" and entry.get("fact", "").strip()]
    return len(propose(conn, folder, items, origin="story-production"))


def list_entries(conn, folder_id):
    _folder(conn, folder_id)
    return [_public(entry) for entry in conn.execute(
        "SELECT * FROM knowledge_entries WHERE folder_id=? ORDER BY category,title,updated DESC",
        (folder_id,)).fetchall()]


def suggestions(conn, folder_id):
    return [{"id": row["id"], "folder_id": row["folder_id"], "origin": row["origin"], "created": row["created"],
             **json.loads(row["entry"])}
            for row in conn.execute("SELECT * FROM knowledge_suggestions WHERE folder_id=?"
                                    " ORDER BY created DESC LIMIT 60", (folder_id,)).fetchall()]


def propose(conn, folder_id, items, origin=""):
    """Produced facts wait as suggestions; never automatic canon."""
    added = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            entry = {"category": _text(item.get("category"), LIMITS["category"]),
                     "title": _text(item.get("title"), LIMITS["title"]),
                     "content": _text(item.get("content"), LIMITS["content"]),
                     "source": _text(item.get("source", origin), LIMITS["source"], required=False)}
        except KnowledgeError:
            continue
        entry_id = uuid.uuid4().hex
        conn.execute("INSERT INTO knowledge_suggestions(id,folder_id,entry,origin,created) VALUES(?,?,?,?,?)",
                     (entry_id, folder_id, json.dumps(entry, ensure_ascii=False),
                      _text(origin, LIMITS["origin"], required=False), time.time()))
        added.append({"id": entry_id, "folder_id": folder_id, **entry})
    return added


def mutate(conn, folder_id, body):
    action = body.get("action")
    _folder(conn, folder_id)
    if action == "add":
        return {"entry": _add(conn, folder_id, body)}
    if action == "update":
        return {"entry": _update(conn, body)}
    if action == "restore":
        return {"entry": _restore(conn, body)}
    if action == "versions":
        return {"versions": [{"version": row["version"], "category": row["category"], "title": row["title"],
                              "content": row["content"], "source": row["source"], "status": row["status"],
                              "created": row["created"]}
                             for row in conn.execute(
            "SELECT version,category,title,content,source,status,created FROM knowledge_versions"
            " WHERE entry_id=? ORDER BY version DESC", (_id(body.get("entry_id")),)).fetchall()]}
    if action == "delete":
        return _delete(conn, body)
    if action == "status":
        return {"entry": _status(conn, body)}
    if action == "accept":
        return _decide(conn, body, "confirmed")
    if action == "keep":
        return _decide(conn, body, "reference")
    if action == "reject":
        return _reject(conn, body)
    if action == "import":
        return _import(conn, folder_id, body)
    if action == "profile":
        return _profile(conn, folder_id, body)
    raise KnowledgeError("knowledge_action_invalid")


def _add(conn, folder_id, body, *, status=None):
    final = status if status in STATUSES else (
        body.get("status") if body.get("status") in ("confirmed", "reference", "idea", "unresolved") else "reference")
    entry_id, at = uuid.uuid4().hex, time.time()
    conn.execute("""INSERT INTO knowledge_entries(id,folder_id,category,title,content,source,status,version,created,updated)
        VALUES(?,?,?,?,?,?,?,1,?,?)""", (entry_id, folder_id, _text(body.get("category"), LIMITS["category"]),
        _text(body.get("title"), LIMITS["title"]), _text(body.get("content"), LIMITS["content"]),
        _text(body.get("source"), LIMITS["source"], required=False), final, at, at))
    return _row(conn, entry_id)


def _snapshot(conn, entry, at):
    conn.execute("""INSERT INTO knowledge_versions(id,entry_id,version,category,title,content,source,status,created)
        VALUES(?,?,?,?,?,?,?,?,?)""", (uuid.uuid4().hex, entry["id"], entry["version"], entry["category"],
        entry["title"], entry["content"], entry["source"], entry["status"], at))


def _update(conn, body):
    entry = conn.execute("SELECT * FROM knowledge_entries WHERE id=?", (_id(body.get("entry_id")),)).fetchone()
    if entry is None:
        raise KnowledgeError("knowledge_entry_missing", 404)
    if body.get("version", entry["version"]) != entry["version"]:
        raise KnowledgeError("knowledge_stale", 409)
    at = time.time()
    _snapshot(conn, entry, at)
    status = body.get("status", entry["status"])
    conn.execute("""UPDATE knowledge_entries SET category=?,title=?,content=?,source=?,status=?,version=?,updated=?
        WHERE id=?""", (_text(body.get("category", entry["category"]), LIMITS["category"]),
        _text(body.get("title", entry["title"]), LIMITS["title"]),
        _text(body.get("content", entry["content"]), LIMITS["content"]),
        _text(body.get("source", entry["source"]), LIMITS["source"], required=False),
        status if status in STATUSES else entry["status"], entry["version"] + 1, at, entry["id"]))
    return _row(conn, entry["id"])


def _status(conn, body):
    entry = conn.execute("SELECT * FROM knowledge_entries WHERE id=?", (_id(body.get("entry_id")),)).fetchone()
    if entry is None:
        raise KnowledgeError("knowledge_entry_missing", 404)
    if body.get("status") not in STATUSES:
        raise KnowledgeError("knowledge_status_invalid")
    at = time.time()
    _snapshot(conn, entry, at)
    conn.execute("UPDATE knowledge_entries SET status=?,version=?,updated=? WHERE id=?",
                 (body["status"], entry["version"] + 1, at, entry["id"]))
    return _row(conn, entry["id"])


def _restore(conn, body):
    entry = conn.execute("SELECT * FROM knowledge_entries WHERE id=?", (_id(body.get("entry_id")),)).fetchone()
    if entry is None:
        raise KnowledgeError("knowledge_entry_missing", 404)
    try:
        version = int(body.get("version"))
    except (TypeError, ValueError):
        raise KnowledgeError("knowledge_field_invalid") from None
    past = conn.execute("SELECT * FROM knowledge_versions WHERE entry_id=? AND version=?",
                        (entry["id"], version)).fetchone()
    if past is None:
        raise KnowledgeError("knowledge_version_missing", 404)
    at = time.time()
    _snapshot(conn, entry, at)
    conn.execute("""UPDATE knowledge_entries SET category=?,title=?,content=?,source=?,status=?,version=?,updated=?
        WHERE id=?""", (past["category"], past["title"], past["content"], past["source"], past["status"],
        entry["version"] + 1, at, entry["id"]))
    return _row(conn, entry["id"])


def _delete(conn, body):
    entry_id = _id(body.get("entry_id"))
    conn.execute("DELETE FROM knowledge_versions WHERE entry_id=?", (entry_id,))
    conn.execute("DELETE FROM knowledge_entries WHERE id=?", (entry_id,))
    return {"ok": True}


def _decide(conn, body, status):
    row = conn.execute("SELECT * FROM knowledge_suggestions WHERE id=?", (_id(body.get("suggestion_id")),)).fetchone()
    if row is None:
        raise KnowledgeError("knowledge_suggestion_missing", 404)
    added = _add(conn, row["folder_id"], json.loads(row["entry"]), status=status)
    conn.execute("DELETE FROM knowledge_suggestions WHERE id=?", (row["id"],))
    return {"entry": added}


def _reject(conn, body):
    removed = conn.execute("DELETE FROM knowledge_suggestions WHERE id=?", (_id(body.get("suggestion_id")),)).rowcount
    if not removed:
        raise KnowledgeError("knowledge_suggestion_missing", 404)
    return {"ok": True}


def _import(conn, folder_id, body):
    """Files arrive as text through the safe upload path; imports stay unconfirmed proposals."""
    return {"entry": _add(conn, folder_id, {"category": "reference-document",
                                            "title": _text(body.get("title"), LIMITS["title"]),
                                            "content": _text(body.get("content"), LIMITS["content"]),
                                            "source": _text(body.get("source"), LIMITS["source"], required=False)
                                            or "import"}, status="reference")}


def _profile(conn, folder_id, body):
    values = body.get("profile")
    if not isinstance(values, dict):
        raise KnowledgeError("knowledge_profile_invalid")
    saved = {key: (_text(values.get(key, ""), 400, required=False) if isinstance(values.get(key, ""), str) else "")
             for key in VISUAL_KEYS}
    existing = conn.execute("""SELECT id FROM knowledge_entries WHERE folder_id=? AND category=?
        ORDER BY updated DESC LIMIT 1""", (folder_id, VISUAL_KEY)).fetchone()
    if existing:
        _update(conn, {"entry_id": existing["id"], "category": VISUAL_KEY, "title": "Visual Profile",
                       "content": json.dumps(saved, ensure_ascii=False), "status": "confirmed",
                       "version": conn.execute("SELECT version FROM knowledge_entries WHERE id=?",
                                               (existing["id"],)).fetchone()[0]})
    else:
        _add(conn, folder_id, {"category": VISUAL_KEY, "title": "Visual Profile",
                               "content": json.dumps(saved, ensure_ascii=False)}, status="confirmed")
    return {"profile": saved}


def export(conn, folder_id, fmt="markdown"):
    steps, entries, conflicts = merge(conn, folder_id)
    names = {folder["id"]: folder["name"] for folder in steps}
    if fmt == "json":
        return {"folder_id": folder_id, "chain": [{"id": folder["id"], "name": folder["name"]} for folder in steps],
                "entries": entries, "conflicts": [[parent, child] for parent, child in conflicts],
                "suggestions": suggestions(conn, folder_id)}
    lines = [f"# Ordnerwissen · {names[folder_id]}", ""]
    for folder in steps:
        rows = [entry for entry in entries if entry["folder_id"] == folder["id"]]
        header = "Eigene Einträge" if folder["id"] == folder_id else f"Geerbt · {folder['name']}"
        lines += [f"## {header}", ""] + _markdown(rows, names)
    if conflicts:
        lines += ["## Konflikte (ungeklärt)", ""]
        lines += [f"- {parent['category']} · {parent['title']}: {names.get(parent['folder_id'])} "
                  f"„{_clip(parent['content'], 120)}“ vs. {names.get(child['folder_id'])} "
                  f"„{_clip(child['content'], 120)}“" for parent, child in conflicts]
    return "\n".join(lines) + "\n"


def _markdown(entries, names):
    lines = []
    for entry in entries:
        lines += [f"### {entry['category']} · {entry['title']} "
                  f"[{entry['status']} · v{entry['version']} · {names.get(entry['folder_id'], '')}]",
                  str(entry["content"]), ""]
        if entry["source"]:
            lines += [f"Quelle: {entry['source']}", ""]
    return lines
