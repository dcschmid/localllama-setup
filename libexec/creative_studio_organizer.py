"""Transactional organization for the studio's existing SQLite records."""

import hashlib
import json
import re
import time
import uuid

ID = re.compile(r"[a-f0-9]{32}")
TABLES = {
    "folder": ("folders", "name"),
    "chat": ("sessions", "title"),
    "project": ("projects", "name"),
    "document": ("documents", "title"),
    "image": ("studio_images", "name"),
    "attachment": ("attachments", "name"),
}
FALLBACK = {
    "folder": "Ordner", "chat": "Unterhaltung", "project": "Projekt",
    "document": "Dokument", "image": "Bild", "attachment": "Anhang",
}

MIGRATION = """
CREATE TABLE folders(id TEXT PRIMARY KEY, folder_id TEXT REFERENCES folders(id),
    name TEXT NOT NULL, updated REAL NOT NULL);
CREATE INDEX folders_parent ON folders(folder_id);
ALTER TABLE projects ADD COLUMN folder_id TEXT REFERENCES folders(id);
ALTER TABLE projects ADD COLUMN archived_at REAL;
ALTER TABLE sessions ADD COLUMN folder_id TEXT REFERENCES folders(id);
ALTER TABLE sessions ADD COLUMN archived_at REAL;
ALTER TABLE sessions ADD COLUMN updated REAL;
ALTER TABLE documents ADD COLUMN folder_id TEXT REFERENCES folders(id);
CREATE TABLE studio_images(id TEXT PRIMARY KEY, folder_id TEXT REFERENCES folders(id),
    name TEXT NOT NULL, updated REAL NOT NULL);
CREATE TABLE attachments(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
    folder_id TEXT REFERENCES folders(id), name TEXT NOT NULL, data BLOB NOT NULL, updated REAL NOT NULL);
CREATE TABLE studio_trash(kind TEXT NOT NULL, id TEXT NOT NULL, location TEXT NOT NULL,
    deleted_at REAL NOT NULL, PRIMARY KEY(kind, id));
CREATE TABLE studio_trash_contents(root_kind TEXT NOT NULL, root_id TEXT NOT NULL,
    kind TEXT NOT NULL, id TEXT NOT NULL, location TEXT NOT NULL,
    PRIMARY KEY(root_kind, root_id, kind, id),
    FOREIGN KEY(root_kind,root_id) REFERENCES studio_trash(kind,id) ON DELETE CASCADE);
CREATE INDEX studio_trash_contents_entry ON studio_trash_contents(kind,id);
CREATE TABLE image_purge(id TEXT PRIMARY KEY, finished INTEGER NOT NULL DEFAULT 0);
CREATE INDEX sessions_project ON sessions(project_id);
CREATE INDEX messages_session ON messages(session_id, created);
CREATE INDEX documents_project ON documents(project_id);
CREATE INDEX versions_document ON doc_versions(document_id);
CREATE INDEX attachments_project ON attachments(project_id);

CREATE VIEW live_folders AS
    WITH RECURSIVE tree(id) AS (
        SELECT id FROM folders WHERE folder_id IS NULL
            AND id NOT IN (SELECT id FROM studio_trash WHERE kind='folder')
        UNION ALL
        SELECT f.id FROM folders f JOIN tree ON f.folder_id=tree.id
            WHERE f.id NOT IN (SELECT id FROM studio_trash WHERE kind='folder')
    ) SELECT f.* FROM folders f JOIN tree USING(id);
CREATE VIEW live_projects AS SELECT * FROM projects
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='project')
    AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders));
CREATE VIEW live_sessions AS SELECT * FROM sessions
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='chat')
    AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders))
    AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.id=sessions.project_id
                    AND p.id NOT IN (SELECT id FROM live_projects));
CREATE VIEW chat_document_links AS
    SELECT session_id, json_extract(meta,'$.document_id') AS document_id
        FROM messages WHERE json_valid(meta) AND json_type(meta,'$.document_id')='text'
    UNION
    SELECT m.session_id, json_extract(j.result,'$.document_id')
        FROM messages m JOIN jobs j ON j.id=json_extract(m.meta,'$.job_id')
        WHERE json_valid(m.meta) AND json_valid(j.result) AND json_type(j.result,'$.document_id')='text';
CREATE VIEW live_documents AS SELECT * FROM documents
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='document')
    AND ((project_id IN (SELECT id FROM live_projects)
          AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders)))
         OR EXISTS (SELECT 1 FROM chat_document_links l JOIN live_sessions s ON l.session_id=s.id
                    WHERE l.document_id=documents.id AND s.project_id IS NOT documents.project_id));
CREATE VIEW live_attachments AS SELECT * FROM attachments
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='attachment')
    AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders))
    AND project_id IN (SELECT id FROM live_projects);
CREATE VIEW live_studio_images AS SELECT * FROM studio_images
    WHERE id NOT IN (SELECT id FROM studio_trash WHERE kind='image')
    AND id NOT IN (SELECT id FROM image_purge)
    AND (folder_id IS NULL OR folder_id IN (SELECT id FROM live_folders));
"""


class OrganizerError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.status = status


def name_value(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 180:
        raise OrganizerError("organizer_name_invalid")
    if any(ord(char) < 32 for char in value.strip()):
        raise OrganizerError("organizer_name_invalid")
    return value.strip()


def require(conn, kind, identifier, *, live=True, include_data=False):
    table, _ = TABLES[kind]
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise OrganizerError("organizer_not_found", 404)
    if live:
        table = "live_" + table
    rows = conn.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)) if include_data else entry_rows(
        conn, table, "WHERE id=?", (identifier,))
    row = rows.fetchone()
    if row is None:
        raise OrganizerError("organizer_not_found", 404)
    return row


def validate_scope(conn, *, project_id=None, session_id=None, document_id=None):
    for kind, identifier in (("chat", session_id), ("project", project_id), ("document", document_id)):
        if identifier is not None:
            require(conn, kind, identifier)


def folder_path(conn, identifier):
    names = []
    while identifier:
        row = require(conn, "folder", identifier, live=False)
        names.append(row["name"])
        identifier = row["folder_id"]
    return list(reversed(names))


def folder_tree(conn, identifier):
    return {r["id"] for r in conn.execute("""WITH RECURSIVE tree(id) AS (
        SELECT ? UNION ALL SELECT f.id FROM folders f JOIN tree ON f.folder_id=tree.id
    ) SELECT id FROM tree""", (identifier,))}


def location(conn, row):
    folder = row["folder_id"]
    pid = row["project_id"] if "project_id" in row.keys() else None
    project = conn.execute("SELECT name,folder_id FROM projects WHERE id=?", (pid,)).fetchone()
    parts = folder_path(conn, folder or (project["folder_id"] if project else None))
    if project and not folder:
        parts.append(project["name"])
    return " / ".join(parts) or "Studio"


def summary(conn, kind, row):
    _, label = TABLES[kind]
    return {"kind": kind, "id": row["id"], "name": row[label] or FALLBACK[kind],
            "folder_id": row["folder_id"],
            "project_id": row["project_id"] if "project_id" in row.keys() else None,
            "location": location(conn, row)}


def entry_rows(conn, table, condition="", params=()):
    columns = "id,name,project_id,folder_id,updated" if table.endswith("attachments") else "*"
    return conn.execute(f"SELECT {columns} FROM {table} {condition}", params)


def folder_destination(conn, identifier):
    if identifier is not None:
        require(conn, "folder", identifier)
    return identifier


def check_folder_depth(conn, parent, identifier=None):
    depth = len(folder_path(conn, parent)) + 1
    if identifier:
        depth += conn.execute("""WITH RECURSIVE tree(id,depth) AS (
            SELECT ?,0 UNION ALL SELECT f.id,tree.depth+1 FROM folders f JOIN tree ON f.folder_id=tree.id
        ) SELECT max(depth) FROM tree""", (identifier,)).fetchone()[0]
    if depth > 64:
        raise OrganizerError("organizer_folder_depth", 409)


def available_name(conn, kind, name, folder, pid=None, exclude=None):
    table, label = TABLES[kind]
    query = f"SELECT id,{label} FROM live_{table} WHERE folder_id IS ?"
    params = [folder]
    if kind in ("document", "attachment"):
        query += " AND project_id=?"
        params.append(pid)
    names = {row[label].casefold() for row in conn.execute(query, params)
             if row["id"] != exclude and row[label]}
    candidate = name
    number = 2
    while candidate.casefold() in names:
        suffix = f" ({number})"
        candidate = name[:180 - len(suffix)] + suffix
        number += 1
    return candidate


def new_folder(conn, name, parent):
    name = name_value(name)
    folder_destination(conn, parent)
    check_folder_depth(conn, parent)
    if available_name(conn, "folder", name, parent) != name:
        raise OrganizerError("organizer_name_conflict", 409)
    identifier = uuid.uuid4().hex
    conn.execute("INSERT INTO folders(id,folder_id,name,updated) VALUES(?,?,?,?)",
                 (identifier, parent, name, time.time()))
    return identifier


def register_image(conn, identifier, name):
    if not isinstance(identifier, str) or not ID.fullmatch(identifier) or purged_image(conn, identifier):
        raise OrganizerError("image_not_found", 404)
    label = " ".join(str(name or "Bild").split())[:180] or "Bild"
    conn.execute("INSERT OR IGNORE INTO studio_images(id,name,updated) VALUES(?,?,?)",
                 (identifier, label, time.time()))


def purged_image(conn, identifier):
    return conn.execute("SELECT 1 FROM image_purge WHERE id=?", (identifier,)).fetchone() is not None


def hidden_images(conn):
    return {row[0] for row in conn.execute("""
        SELECT id FROM studio_images WHERE id NOT IN (SELECT id FROM live_studio_images)
        UNION SELECT id FROM image_purge""")}


def check_image_links(conn, *values):
    identifiers = set()
    for value in values:
        if isinstance(value, str):
            identifiers.update(re.findall(r"/api/images/files/([a-f0-9]{32})(?![a-f0-9])", value))
        elif isinstance(value, dict):
            identifiers.update(v for k, v in value.items()
                               if k in ("image_id", "origin_image_id", "cover") and isinstance(v, str))
    if any(purged_image(conn, identifier) for identifier in identifiers):
        raise OrganizerError("image_not_found", 404)


def update_document(conn, row, title, text, note, origin, lang=None, *, restoring_name=False):
    if "story_number" in row.keys() and row["story_number"] is not None and row["status"] == "approved" and not restoring_name:
        raise OrganizerError("story_approved", 409)
    check_image_links(conn, text)
    did = row["id"]
    conn.execute("INSERT INTO doc_versions(id,document_id,version,body,note,origin,created,title)"
                 " VALUES(?,?,?,?,?,?,?,?)",
                 (uuid.uuid4().hex, did, row["version"], row["body"], row["version_note"],
                  row["version_origin"], row["updated"] or row["created"], row["title"]))
    at = time.time()
    conn.execute("UPDATE documents SET body=?,title=?,lang=?,version=version+1,updated=?,"
                 " version_note=?,version_origin=? WHERE id=?",
                 (text, title, lang or row["lang"], at, note, origin, did))
    if "story_number" in row.keys() and row["story_number"] is not None and row["status"] == "planned" and text.strip():
        conn.execute("UPDATE documents SET status='draft' WHERE id=?", (did,))
    conn.execute("DELETE FROM documents_fts WHERE document_id=?", (did,))
    conn.execute("INSERT INTO documents_fts(title,body,document_id,kind) VALUES(?,?,?,?)",
                 (title, text, did, row["kind"]))
    conn.execute("UPDATE projects SET updated=? WHERE id=?", (at, row["project_id"]))
    return int(row["version"]) + 1


def list_entries(conn, view):
    if view == "folders":
        sources = (
            ("folder", "live_folders", ""),
            ("image", "live_studio_images", "WHERE folder_id IS NOT NULL"),
            ("document", "live_documents", "WHERE folder_id IS NOT NULL AND project_id IN "
             "(SELECT id FROM live_projects WHERE archived_at IS NULL)"),
            ("attachment", "live_attachments", "WHERE folder_id IS NOT NULL AND project_id IN "
             "(SELECT id FROM live_projects WHERE archived_at IS NULL)"),
        )
        return [summary(conn, kind, row) for kind, table, condition in sources
                for row in entry_rows(conn, table, condition)]
    if view == "archive":
        return [{**summary(conn, kind, row), "archived_at": row["archived_at"]}
                for kind, table in (("project", "live_projects"), ("chat", "live_sessions"))
                for row in conn.execute(f"SELECT * FROM {table} WHERE archived_at IS NOT NULL")]
    entries = {}
    for item in conn.execute("""SELECT kind,id,location,deleted_at,0 AS inherited FROM studio_trash
        UNION ALL SELECT c.kind,c.id,c.location,t.deleted_at,1 FROM studio_trash_contents c
            JOIN studio_trash t ON t.kind=c.root_kind AND t.id=c.root_id
        ORDER BY inherited,deleted_at DESC,kind,id"""):
        kind, identifier = item["kind"], item["id"]
        if (kind, identifier) in entries or (item["inherited"] and not is_trashed(conn, kind, identifier)):
            continue
        entries[kind, identifier] = {**summary(conn, kind, require(conn, kind, identifier, live=False)),
                                     "location": item["location"], "deleted_at": item["deleted_at"],
                                     "inherited": bool(item["inherited"])}
    return list(entries.values())


def is_trashed(conn, kind, identifier):
    if conn.execute("SELECT 1 FROM studio_trash WHERE kind=? AND id=?", (kind, identifier)).fetchone():
        return True
    table, _ = TABLES[kind]
    return conn.execute(f"""SELECT 1 FROM studio_trash_contents c WHERE c.kind=? AND c.id=?
        AND NOT EXISTS (SELECT 1 FROM live_{table} WHERE id=c.id) LIMIT 1""", (kind, identifier)).fetchone() is not None


def selected(body):
    entries = body.get("entries")
    if not isinstance(entries, list) or not entries:
        raise OrganizerError("organizer_selection_invalid")
    keys = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise OrganizerError("organizer_selection_invalid")
        kind, identifier = entry.get("kind"), entry.get("id")
        if not isinstance(kind, str) or kind not in TABLES or not isinstance(identifier, str) or not ID.fullmatch(identifier):
            raise OrganizerError("organizer_selection_invalid")
        keys.add((kind, identifier))
    return sorted(keys)


def affected(conn, keys):
    groups = {kind: set() for kind in TABLES}
    for kind, identifier in keys:
        groups[kind].add(identifier)
        if kind == "folder":
            groups[kind].update(folder_tree(conn, identifier))
    for kind in ("project", "chat", "document", "image", "attachment"):
        if kind == "document" and groups["chat"]:
            selected_chats = json.dumps(sorted(groups["chat"]))
            groups["project"].update(row["id"] for row in conn.execute("""
                SELECT p.id FROM projects p WHERE json_extract(p.meta,'$.chat_owned')=1
                AND EXISTS (SELECT 1 FROM chat_contexts c WHERE c.context_id=p.id
                    AND c.chat_id IN (SELECT value FROM json_each(?)))
                AND NOT EXISTS (SELECT 1 FROM chat_contexts c WHERE c.context_id=p.id
                    AND c.chat_id NOT IN (SELECT value FROM json_each(?)))""", (selected_chats, selected_chats)))
        table, _ = TABLES[kind]
        query = f"SELECT id FROM {table} WHERE folder_id IN (SELECT value FROM json_each(?))"
        params = [json.dumps(sorted(groups["folder"]))]
        if kind in ("chat", "document", "attachment"):
            query += " OR project_id IN (SELECT value FROM json_each(?))"
            params.append(json.dumps(sorted(groups["project"])))
        groups[kind].update(r["id"] for r in conn.execute(query, params))
    return groups


def referenced_jobs(conn, sessions):
    return {row[0] for row in conn.execute("""SELECT DISTINCT json_extract(meta,'$.job_id')
        FROM messages WHERE session_id IN (SELECT value FROM json_each(?))
          AND json_valid(meta) AND json_type(meta,'$.job_id')='text'""", (json.dumps(sorted(sessions)),))}


def blocked_by_work(conn, groups, in_flight):
    def matches(kind, identifier):
        return identifier in groups[kind]

    if any(any(matches(kind, identifier) for kind, identifier in scope) for scope in in_flight):
        return True
    refs = referenced_jobs(conn, groups["chat"])
    names = {r[0].casefold() for r in conn.execute("SELECT name FROM projects WHERE id IN (SELECT value FROM json_each(?))",
                                                 (json.dumps(sorted(groups["project"])),))}
    for row in conn.execute("""SELECT id,payload,result FROM jobs
        WHERE state NOT IN ('completed','partial','failed','cancelled')"""):
        payload, result = json.loads(row["payload"] or "{}"), json.loads(row["result"] or "{}")
        for meta in (payload, result, payload.get("meta", {})):
            if (matches("project", meta.get("project_id")) or matches("chat", meta.get("session_id"))
                    or matches("document", meta.get("document_id")) or matches("image", meta.get("origin_image_id"))):
                return True
        target = payload.get("plan", {}).get("project_name")
        if row["id"] in refs or (target and target.casefold() in names):
            return True
    return False


def visible_job(conn, row):
    payload = json.loads(row["payload"] or "{}")
    meta = payload.get("meta", {})
    references = conn.execute("""SELECT EXISTS(SELECT 1 FROM live_sessions WHERE id=m.session_id) AS visible
        FROM messages m WHERE json_valid(m.meta) AND json_extract(m.meta,'$.job_id') IN (?,?)
        ORDER BY visible DESC LIMIT 1""", (row["id"], meta.get("chat_task_id"))).fetchone()
    if references:
        return bool(references["visible"])
    try:
        validate_scope(conn, **{field: payload.get(field) or meta.get(field)
                                for field in ("project_id", "document_id", "session_id")})
    except OrganizerError:
        return False
    return True


def deletion_plan(conn, keys, action):
    if action == "empty":
        keys = [(row["kind"], row["id"]) for row in conn.execute("SELECT kind,id FROM studio_trash ORDER BY kind,id")]
    for kind, identifier in keys:
        if action == "trash":
            require(conn, kind, identifier)
        elif not is_trashed(conn, kind, identifier):
            raise OrganizerError("organizer_selection_changed", 409)
    groups = affected(conn, keys)
    preserved = shared_documents(conn, groups, keys)
    entries = [summary(conn, kind, require(conn, kind, identifier, live=False))
               for kind, group in groups.items() for identifier in sorted(group)]
    project_ids = json.dumps(sorted(groups["project"]))
    doc_ids = json.dumps(sorted(groups["document"]))
    details = {
        "versions": conn.execute("SELECT COUNT(*) FROM doc_versions WHERE document_id IN (SELECT value FROM json_each(?))",
                                 (doc_ids,)).fetchone()[0],
        "notes": conn.execute("SELECT COUNT(*) FROM memories WHERE project_id IN (SELECT value FROM json_each(?)) AND kind NOT IN ('image','document-image')",
                              (project_ids,)).fetchone()[0],
        "images": [{"id": row["key"], "name": row["body"][:180] or "Bild"}
                   for row in conn.execute("""SELECT key,body FROM memories WHERE kind='image'
                       AND project_id IN (SELECT value FROM json_each(?)) ORDER BY project_id,key""", (project_ids,))],
        "preserved_documents": sorted(preserved),
    }
    token = hashlib.sha256(json.dumps([action, keys, entries, details], ensure_ascii=False).encode()).hexdigest()
    return keys, groups, preserved, {"entries": entries, **details, "token": token}


def shared_documents(conn, groups, keys):
    candidates = groups["document"] - {identifier for kind, identifier in keys if kind == "document"}
    if not candidates:
        return {}
    targets = {}
    for row in conn.execute("""SELECT l.document_id,s.project_id FROM chat_document_links l
        JOIN sessions s ON s.id=l.session_id JOIN documents d ON d.id=l.document_id
        WHERE l.document_id IN (SELECT value FROM json_each(?))
            AND s.id NOT IN (SELECT value FROM json_each(?))
            AND s.project_id IS NOT d.project_id
            AND l.document_id NOT IN (SELECT id FROM studio_trash WHERE kind='document')
        ORDER BY s.project_id IS NULL,s.project_id""",
        (json.dumps(sorted(candidates)), json.dumps(sorted(groups["chat"])))):
        pid = row["project_id"]
        if pid not in groups["project"]:
            targets.setdefault(row["document_id"], pid)
    return targets


def recovery_project(conn):
    target = conn.execute("""SELECT id FROM live_projects WHERE folder_id IS NULL AND archived_at IS NULL
        AND json_extract(meta,'$.restored_files')=1""").fetchone()
    if target:
        return target["id"]
    pid = uuid.uuid4().hex
    at = time.time()
    conn.execute("INSERT INTO projects(id,name,meta,created,updated) VALUES(?,?,?,?,?)", (
        pid, available_name(conn, "project", "Wiederhergestellte Dateien", None),
        '{"restored_files":true}', at, at))
    conn.execute("INSERT INTO sessions(id,project_id,title,created,updated) VALUES(?,?,'Wiederhergestellte Dateien',?,?)",
                 (uuid.uuid4().hex, pid, at, at))
    return pid


def rehome_image_links(conn, identifier, old, new):
    source = list(conn.execute("SELECT key,body,created FROM memories WHERE project_id=? AND kind='document-image' AND substr(key,1,33)=?",
                               (old, identifier + "/")))
    for link in source:
        image = link["key"].partition("/")[2]
        conn.execute("INSERT OR IGNORE INTO memories VALUES(?,?,'image',?,?,?)",
                     (uuid.uuid4().hex, new, image, "Dokumentbild", link["created"]))
        conn.execute("UPDATE memories SET project_id=? WHERE project_id=? AND kind='document-image' AND key=?",
                     (new, old, link["key"]))


def orphan_image(conn, identifier):
    # Keep references from the paper bin and old versions as long as they can be restored.
    queries = (
        ("projects", "instr(meta,?) OR instr(description,?)"),
        ("documents", "instr(body,?)"),
        ("doc_versions", "instr(body,?)"),
        ("editorial_runs", "instr(source,?) OR instr(result,?)"),
        ("messages", "instr(content,?) OR instr(meta,?)"),
        ("memories", "instr(key,?) OR instr(body,?)"),
        ("jobs", "state NOT IN ('completed','partial','failed','cancelled') AND instr(payload,?)"),
        ("jobs", """instr(result,?) AND id IN (SELECT json_extract(meta,'$.job_id')
            FROM messages WHERE json_valid(meta) UNION SELECT json_extract(j.result,'$.image_job_id')
            FROM messages m JOIN jobs j ON j.id=json_extract(m.meta,'$.job_id') WHERE json_valid(m.meta))"""),
    )
    for table, condition in queries:
        if conn.execute(f"SELECT 1 FROM {table} WHERE {condition} LIMIT 1",
                        (identifier,) * condition.count("?")).fetchone():
            return False
    return True


def purge(conn, keys, groups, preserved):
    image_keys = {identifier for kind, identifier in keys if kind == "image"}
    for identifier, pid in preserved.items():
        doc = require(conn, "document", identifier, live=False)
        target = pid if pid and conn.execute("SELECT 1 FROM live_projects WHERE id=?", (pid,)).fetchone() else recovery_project(conn)
        if target != doc["project_id"]:
            rehome_image_links(conn, identifier, doc["project_id"], target)
        conn.execute("UPDATE documents SET project_id=?,folder_id=NULL WHERE id=?", (target, identifier))
        groups["document"].remove(identifier)
    job_ids = referenced_jobs(conn, groups["chat"])
    owned = dict(conn.execute("SELECT id,payload FROM jobs"))
    for identifier, raw in owned.items():
        payload = json.loads(raw or "{}")
        if any(meta.get("project_id") in groups["project"] or meta.get("session_id") in groups["chat"]
               for meta in (payload, payload.get("meta", {}))):
            job_ids.add(identifier)
    for kind, dependencies in (
        ("chat", (("messages", "session_id"),)),
        ("document", (("documents_fts", "document_id"), ("doc_versions", "document_id"),
                      ("editorial_runs", "document_id"))),
        ("attachment", ()), ("project", (("memories", "project_id"),)),
    ):
        table, _ = TABLES[kind]
        for identifier in groups[kind]:
            for related, column in dependencies:
                conn.execute(f"DELETE FROM {related} WHERE {column}=?", (identifier,))
            if kind == "document":
                conn.execute("DELETE FROM memories WHERE kind='document-image' AND substr(key,1,33)=?",
                             (identifier + "/",))
            conn.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))
    retained = {row[0] for row in conn.execute(
        "SELECT DISTINCT json_extract(meta,'$.job_id') FROM messages WHERE json_valid(meta)")}
    for identifier in job_ids - retained:
        conn.execute("""DELETE FROM jobs WHERE id=? AND state IN ('completed','partial','failed','cancelled')
            AND NOT EXISTS (SELECT 1 FROM jobs parent
                WHERE json_extract(parent.result,'$.image_job_id')=jobs.id
                AND parent.id IN (SELECT value FROM json_each(?)))""",
                     (identifier, json.dumps([job for job in retained if isinstance(job, str)])))
    for identifier in groups["image"]:
        explicit = identifier in image_keys or conn.execute(
            "SELECT 1 FROM studio_trash WHERE kind='image' AND id=?", (identifier,)).fetchone()
        if not orphan_image(conn, identifier):
            if explicit:
                raise OrganizerError("organizer_image_in_use", 409)
            conn.execute("UPDATE studio_images SET folder_id=NULL WHERE id=?", (identifier,))
            continue
        conn.execute("INSERT OR IGNORE INTO image_purge(id) VALUES(?)", (identifier,))
        conn.execute("DELETE FROM studio_images WHERE id=?", (identifier,))
    conn.execute("DELETE FROM folders WHERE id IN (SELECT value FROM json_each(?))",
                 (json.dumps(sorted(groups["folder"])),))
    for kind, identifiers in groups.items():
        conn.executemany("DELETE FROM studio_trash WHERE kind=? AND id=?",
                         ((kind, identifier) for identifier in identifiers))
        conn.executemany("DELETE FROM studio_trash_contents WHERE kind=? AND id=?",
                         ((kind, identifier) for identifier in identifiers))


def trash_entries(conn, keys, groups, previews):
    locations = {(item["kind"], item["id"]): item["location"] for item in previews}
    at = time.time()
    conn.executemany("INSERT INTO studio_trash(kind,id,location,deleted_at) VALUES(?,?,?,?)",
                     ((kind, identifier, locations[kind, identifier], at) for kind, identifier in keys))
    for kind, identifier in keys:
        descendants = groups if len(keys) == 1 else affected(conn, [(kind, identifier)])
        conn.executemany("""INSERT INTO studio_trash_contents(root_kind,root_id,kind,id,location)
            VALUES(?,?,?,?,?)""",
                         ((kind, identifier, item_kind, item_id, locations[item_kind, item_id])
                          for item_kind, items in descendants.items() for item_id in items
                          if (kind, identifier) != (item_kind, item_id)))


def restore(conn, keys):
    for kind, identifier in keys:
        if not is_trashed(conn, kind, identifier):
            raise OrganizerError("organizer_selection_changed", 409)
    pending = {(kind, identifier): require(conn, kind, identifier, live=False) for kind, identifier in keys}
    # Parents before children, then projects before their contents.
    order = {kind: index for index, kind in enumerate(TABLES)}
    for (kind, identifier), row in sorted(pending.items(), key=lambda item: (
            order[item[0][0]], len(folder_path(conn, item[1]["folder_id"])))):
        if not is_trashed(conn, kind, identifier):
            continue  # Restoring a selected ancestor already restored this entry.
        table, label = TABLES[kind]
        folder = row["folder_id"]
        if folder and not conn.execute("SELECT 1 FROM live_folders WHERE id=?", (folder,)).fetchone():
            folder = None
        pid = row["project_id"] if "project_id" in row.keys() else None
        if pid and not conn.execute("SELECT 1 FROM live_projects WHERE id=?", (pid,)).fetchone():
            if kind == "chat":
                # An owned context is temporarily hidden by its own chat tombstone.
                # Keep the pointer when restoring the chat makes the context visible again.
                can_reopen = conn.execute("""SELECT 1 FROM projects p JOIN chat_contexts c ON c.context_id=p.id
                    WHERE p.id=? AND c.chat_id=? AND json_extract(p.meta,'$.chat_owned')=1
                    AND p.id NOT IN (SELECT id FROM studio_trash WHERE kind='project')
                    AND (p.folder_id IS NULL OR p.folder_id IN (SELECT id FROM live_folders))""",
                    (pid, identifier)).fetchone()
                if not can_reopen:
                    pid = None
            else:
                pid = recovery_project(conn)
                if kind == "document":
                    rehome_image_links(conn, identifier, row["project_id"], pid)
        name = available_name(conn, kind, row[label] or FALLBACK[kind], folder, pid, identifier)
        if kind == "document" and name != row[label]:
            update_document(conn, row, name, row["body"], "Name beim Wiederherstellen angepasst", "restored", restoring_name=True)
        conn.execute(f"UPDATE {table} SET folder_id=?,{label}=?,updated=? WHERE id=?",
                     (folder, name, time.time(), identifier))
        if kind in ("chat", "document", "attachment"):
            conn.execute(f"UPDATE {table} SET project_id=? WHERE id=?", (pid, identifier))
        conn.execute("DELETE FROM studio_trash WHERE kind=? AND id=?", (kind, identifier))
    for kind, identifier in keys:
        if kind != "project" or conn.execute("""SELECT 1 FROM live_sessions s JOIN chat_contexts c ON c.chat_id=s.id
                WHERE c.context_id=?""", (identifier,)).fetchone():
            continue
        restored = require(conn, "project", identifier, live=False)
        at = time.time()
        conn.execute("INSERT INTO sessions(id,project_id,title,folder_id,archived_at,created,updated) VALUES(?,?,?,?,?,?,?)",
                     (uuid.uuid4().hex, identifier, restored["name"], restored["folder_id"], restored["archived_at"], at, at))


def duplicate_project(conn, original):
    source = original["id"]
    new = uuid.uuid4().hex
    at = time.time()
    mapping = {source: new}

    def clone(table, row, **changes):
        values = dict(row) | changes
        values["id"] = mapping.get(row["id"]) or uuid.uuid4().hex
        cols = ",".join(values)
        params = ",".join("?" for _ in values)
        conn.execute(f"INSERT INTO {table}({cols}) VALUES({params})", tuple(values.values()))

    contents = {kind: entry_rows(conn, "live_" + TABLES[kind][0], "WHERE project_id=?", (source,)).fetchall()
                for kind in ("document", "chat", "attachment")}
    for records in contents.values():
        mapping.update({row["id"]: uuid.uuid4().hex for row in records})
    rows = list(conn.execute("""WITH linked(id) AS (
        SELECT json_extract(meta,'$.job_id') FROM messages WHERE json_valid(meta)
          AND session_id IN (SELECT value FROM json_each(?))
        UNION SELECT json_extract(j.result,'$.image_job_id') FROM messages m
          JOIN jobs j ON j.id=json_extract(m.meta,'$.job_id') WHERE json_valid(m.meta)
          AND m.session_id IN (SELECT value FROM json_each(?))
    ) SELECT * FROM jobs WHERE id IN (SELECT id FROM linked)""",
        (json.dumps([row["id"] for row in contents["chat"]]),) * 2))
    mapping.update({row["id"]: uuid.uuid4().hex for row in rows})

    def remap(value):
        if isinstance(value, dict):
            return {key: (mapping.get(item, item) if isinstance(item, str) and key in
                    ("project_id", "session_id", "document_id", "chat_task_id", "job_id", "image_job_id")
                    else [mapping.get(identifier, identifier) if isinstance(identifier, str) else identifier for identifier in item]
                    if isinstance(item, list) and key in ("chapter_ids", "context_documents")
                    else remap(item)) for key, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        return value

    def remap_links(text):
        return re.sub(r"(?P<prefix>#(?:chat|document|project)/|/api/attachments/)(?P<id>[a-f0-9]{32})"
                      r"(?:/(?P<doc>[a-f0-9]{32}))?",
                      lambda m: m["prefix"] + mapping.get(m["id"], m["id"]) +
                      ("/" + mapping.get(m["doc"], m["doc"]) if m["doc"] else ""), text)

    name = available_name(conn, "project", original["name"][:172] + " (Kopie)", original["folder_id"])
    meta = json.loads(original["meta"] or "{}")
    if isinstance(meta.get("story"), dict) and meta["story"].get("opening"):
        meta["story"]["opening"] = mapping.get(meta["story"]["opening"])
    clone("projects", original, name=name, created=at, updated=at, archived_at=None,
          meta=json.dumps(meta, ensure_ascii=False))
    for kind, records in contents.items():
        table, _ = TABLES[kind]
        for row in records:
            identifier = mapping[row["id"]]
            if kind == "attachment":
                conn.execute("""INSERT INTO attachments(id,project_id,name,data,updated)
                    SELECT ?,?,name,data,updated FROM attachments WHERE id=?""", (identifier, new, row["id"]))
                continue
            changes = {"body": remap_links(row["body"])} if kind == "document" else {}
            clone(table, row, project_id=new, folder_id=None, **changes)
            if kind == "document":
                conn.execute("INSERT INTO documents_fts(title,body,document_id,kind) VALUES(?,?,?,?)",
                             (row["title"], changes["body"], identifier, row["kind"]))
                for version in conn.execute("SELECT * FROM doc_versions WHERE document_id=?", (row["id"],)).fetchall():
                    clone("doc_versions", version, document_id=identifier, body=remap_links(version["body"]))
                for run in conn.execute("SELECT * FROM editorial_runs WHERE document_id=?", (row["id"],)).fetchall():
                    clone("editorial_runs", run, document_id=identifier)
            if kind == "chat":
                for message in conn.execute("SELECT * FROM messages WHERE session_id=?", (row["id"],)).fetchall():
                    clone("messages", message, session_id=identifier, content=remap_links(message["content"]),
                          meta=json.dumps(remap(json.loads(message["meta"] or "{}")), ensure_ascii=False))
    for row in conn.execute("SELECT * FROM memories WHERE project_id=?", (source,)).fetchall():
        changes = {"project_id": new}
        if row["kind"] == "document-image":
            doc, _, image = row["key"].partition("/")
            if not conn.execute("SELECT 1 FROM documents WHERE id=?", (mapping.get(doc),)).fetchone():
                continue
            changes.update(key=mapping[doc] + "/" + image,
                           body=json.dumps(remap(json.loads(row["body"])), ensure_ascii=False))
        clone("memories", row, **changes)
    for row in rows:
        changes = {field: json.dumps(remap(json.loads(row[field])), ensure_ascii=False)
                   for field in ("payload", "result") if row[field]}
        clone("jobs", row, **changes)
    return new


def apply(conn, action, body, in_flight=()):
    if action == "folder":
        return {"id": new_folder(conn, body.get("name"), body.get("folder_id"))}
    operation = body.get("operation") if action == "preview" else action
    if action == "preview" and operation not in ("trash", "purge", "empty"):
        raise OrganizerError("organizer_action_invalid")
    keys = [] if operation == "empty" else selected(body)
    if operation in ("trash", "purge", "empty"):
        keys, groups, preserved, plan = deletion_plan(conn, keys, operation)
        if action == "preview":
            return plan
        if not isinstance(body.get("token"), str) or body["token"] != plan["token"]:
            raise OrganizerError("organizer_selection_changed", 409)
        if blocked_by_work(conn, groups, in_flight):
            raise OrganizerError("organizer_work_running", 409)
        if action == "trash":
            trash_entries(conn, keys, groups, plan["entries"])
        else:
            purge(conn, keys, groups, preserved)
        return {"ok": True}
    if action == "restore":
        restore(conn, keys)
        return {"ok": True}
    rows = [(kind, require(conn, kind, identifier)) for kind, identifier in keys]
    if action == "duplicate" and len(rows) == 1 and rows[0][0] == "project":
        if blocked_by_work(conn, affected(conn, keys), in_flight):
            raise OrganizerError("organizer_work_running", 409)
        return {"id": duplicate_project(conn, rows[0][1])}
    if action == "assign":
        pid = body.get("project_id")
        validate_scope(conn, project_id=pid)
        if blocked_by_work(conn, affected(conn, keys), in_flight):
            raise OrganizerError("organizer_work_running", 409)
    for kind, row in rows:
        table, label = TABLES[kind]
        identifier, at = row["id"], time.time()
        if action in ("archive", "unarchive") and kind in ("project", "chat"):
            conn.execute(f"UPDATE {table} SET archived_at=?,updated=? WHERE id=?",
                         (at if action == "archive" else None, at, identifier))
        elif action == "assign" and kind == "chat":
            conn.execute("UPDATE sessions SET project_id=?,updated=? WHERE id=?", (pid, at, identifier))
        elif action in ("rename", "move"):
            folder = folder_destination(conn, body.get("folder_id")) if action == "move" else row["folder_id"]
            name = name_value(body.get("name")) if action == "rename" else row[label]
            if kind == "folder" and folder in folder_tree(conn, identifier):
                raise OrganizerError("organizer_folder_cycle", 409)
            if kind == "folder" and action == "move":
                check_folder_depth(conn, folder, identifier)
            if kind == "folder" and available_name(conn, kind, name, folder, exclude=identifier) != name:
                raise OrganizerError("organizer_name_conflict", 409)
            if kind == "document" and action == "rename" and name != row[label]:
                update_document(conn, row, name, row["body"], "Umbenannt", "user")
            else:
                conn.execute(f"UPDATE {table} SET {label}=?,folder_id=?,updated=? WHERE id=?",
                             (name, folder, at, identifier))
        else:
            raise OrganizerError("organizer_action_invalid")
    return {"ok": True}
