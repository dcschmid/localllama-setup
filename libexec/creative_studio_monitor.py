"""Production monitor: one derived view of a story job, built only from stored job state and live signals.

Nothing here is estimated. A count is a count of stored artifacts, a word count is computed from the saved
chapter text, and a timeline entry is a persisted job event. The browser translates the codes into text.
"""
import creative_studio_activity as live
import creative_studio_story as story

OPEN = ("queued", "running", "paused", "failed")
CHAPTER_STEPS = ("generate", "human_audit", "story_audit", "correction", "final_check", "image", "image_check", "finish")
PHASE_STEP = {"writing": "generate", "reviewed": "correction", "rewrite_audit": "final_check", "text_finalize": "final_check",
              "illustrating": "image", "image_prompt": "image", "image_queue": "image", "image_wait": "image",
              "image_archive": "image_check", "finalizing": "finish", "awaiting_chapter": "finish", "advance": "finish"}
VERIFYING = frozenset(("auditing", "rewrite_audit", "text_finalize", "manuscript", "final_validation", "image_archive",
                       "planning_review", "planning_audit", "impact"))
CORRECTING = frozenset(("reviewed", "planning_repair", "planning_revise"))
EXPANSION_LIMIT = 2          # automatic scene-expansion attempts per revision batch (see ProductionWorker.improve)
TIMELINE_LIMIT = 120


def awaiting(status, result, *, language_retry, recheck):
    """What a paused job waits for."""
    if status != "paused":
        return None
    reason = result.get("pause_reason")
    if reason == "blocker":
        return "language_retry" if language_retry else "recheck" if recheck else "decision"
    return {"chapter": "chapter_approval", "art": "art_review", "user": "user"}.get(reason, "user")


def derive_state(status, result, phase, *, waiting_for, model_active, kind):
    """The one production state shown to the user. It follows the stored job state, never the step name alone."""
    if status in ("cancelled", "completed", "incomplete", "failed"):
        return status
    if status == "paused":
        return "needs_decision" if waiting_for == "decision" else "paused"
    if status == "queued" or (status == "running" and not result.get("events") and kind == "story" and phase in (None, "writing")
                              and not result.get("current")):
        return "preparing"
    if result.get("retry") and not result.get("error"):
        return "retrying"
    if phase in CORRECTING:
        return "correcting"
    if phase in VERIFYING:
        return "verifying"
    return "model_wait" if model_active else "running"


def step_statuses(finished, active, phase, state, current):
    """Real status of the eight stages of one chapter."""
    if finished:
        done = dict.fromkeys(CHAPTER_STEPS, "done")
        if finished.get("status") != "approved":
            done["finish"] = "pending"
        return done
    if not active:
        return dict.fromkeys(CHAPTER_STEPS, "pending")
    if phase == "auditing":
        at = "story_audit" if current.get("language_windows") else "human_audit"
    else:
        at = PHASE_STEP.get(phase, "generate")
    status = {"failed": "failed", "paused": "paused", "needs_decision": "blocked", "cancelled": "stopped"}.get(state, "running")
    index = CHAPTER_STEPS.index(at)
    return {name: "done" if position < index else status if position == index else "pending"
            for position, name in enumerate(CHAPTER_STEPS)}


def length_facts(plan, result, bodies):
    """Word facts of the current chapter, computed from the saved text. None unless that text is known."""
    current = result.get("current") or {}
    number = result.get("number")
    if not number or number > len(plan["chapters"]) or not current.get("document_id"):
        return None
    doc = (bodies or {}).get(current["document_id"])
    if not doc or doc["version"] != current.get("version"):
        return None
    chapter = plan["chapters"][number - 1]
    words = story.count_words(doc["body"])
    patches = [patch for patch in current.get("patches", []) if patch.get("method") == "scene_expansion"]
    reasons = {}
    for patch in patches:
        if patch.get("reason"):
            reasons[patch["reason"]] = reasons.get(patch["reason"], 0) + 1
    state = "short" if words < chapter["minimum"] else "long" if words > chapter["maximum"] else "ok"
    return {"number": number, "words": words, "minimum": chapter["minimum"], "maximum": chapter["maximum"], "state": state,
            "missing": max(0, chapter["minimum"] - words), "excess": max(0, words - chapter["maximum"]),
            "version": doc["version"], "attempts": len(patches), "failed_attempts": sum(bool(p.get("error")) for p in patches),
            "attempt_limit": EXPANSION_LIMIT, "passes": current.get("passes", 0), "reasons": reasons,
            "in_progress": "short_expansion" in current}


def timeline(job_id, row, result):
    """Persisted step events of the job, oldest first. Every entry is a stored event, none is generated."""
    items = [{"at": row["created"], "id": "start", "number": None, "step": "started", "status": "completed",
              "duration": None, "ref": None}]
    for index, event in enumerate(result.get("events", [])):
        started, finished = event.get("started_at"), event.get("finished_at")
        error = event.get("error")
        item = {"at": started, "id": f"{event.get('number')}:{event.get('step')}", "number": event.get("number"),
                "step": event.get("step"), "status": event.get("status"),
                "duration": round(finished - started, 1) if started and finished else None,
                "attempts": event.get("attempts", 1), "ref": None}
        if error:
            item["error"] = error
            item["ref"] = f"{job_id[:8]}/{index + 1}/{error}"
        for key in ("words", "corrections"):
            if event.get(key) is not None:
                item[key] = event[key]
        if isinstance(event.get("detail"), dict) and event["detail"].get("words") is not None:
            item["words"] = event["detail"]["words"]
        if event.get("status") == "paused":
            item["blocked"] = isinstance(event.get("detail"), list)
        items.append(item)
    return items[-TIMELINE_LIMIT:]


def counts(plan, result, status, exported):
    chapters = len(plan["chapters"])
    approved = sum(item.get("status") == "approved" for item in result.get("chapter_results", []))
    images = len(result.get("chapter_results", [])) + bool(result.get("cover"))
    files = exported if status == "completed" else 0
    total = chapters + (chapters + 1) + len(("md", "mdx", "zip"))
    done = approved + images + files
    return {"chapters": {"done": approved, "total": chapters}, "images": {"done": images, "total": chapters + 1},
            "exports": {"done": files, "total": 3}, "steps": {"done": done, "total": total}}


def common(row, payload, result, *, phase, status, state_flags, snapshot, now, limits):
    waiting_for = awaiting(status, result, **state_flags)
    model = (snapshot or {}).get("model")
    state = derive_state(status, result, phase, waiting_for=waiting_for, model_active=bool(model), kind=payload["kind"])
    events = result.get("events") or []
    last = events[-1] if events else {}
    return {"state": state, "awaiting": waiting_for, "phase": phase, "step_started_at": last.get("started_at"),
            "last_saved_at": row["updated"], "created_at": row["created"], "server_time": now,
            "health": live.health(snapshot, status=row["state"], phase=phase, updated=row["updated"], now=now, limits=limits),
            "activity": snapshot, "timeline": timeline(row["id"], row, result)}


def view(row, payload, result, *, phase, status, state_flags, snapshot, bodies, now, limits=None):
    """The complete monitor record of one job. Story jobs add chapters, counters and word facts."""
    base = common(row, payload, result, phase=phase, status=status, state_flags=state_flags, snapshot=snapshot, now=now, limits=limits)
    if payload["kind"] != "story":
        return base
    plan, state = payload["plan"], base["state"]
    finished = {item["number"]: item for item in result.get("chapter_results", [])}
    current = result.get("current") or {}
    number = result.get("number")
    chapters = []
    for item in plan["chapters"]:
        done = finished.get(item["number"])
        approved = bool(done and done.get("status") == "approved")
        active = item["number"] == number and not approved and status not in ("completed", "cancelled")
        words = done["words"] if done else None
        saved = (bodies or {}).get(current.get("document_id")) if active else None
        if saved and saved["version"] == current.get("version"):
            words = story.count_words(saved["body"])
        chapters.append({"number": item["number"], "title": item["title"], "minimum": item["minimum"], "maximum": item["maximum"],
                         "status": "done" if approved else "review" if done else "active" if active else "pending",
                         "words": words, "image": bool(done and done.get("image")),
                         "steps": step_statuses(done, active, phase, state, current),
                         "corrections": (done or {}).get("corrections", 0) if done else current.get("corrections", 0) if active else 0})
    facts = length_facts(plan, result, bodies) if status != "completed" else None
    exports = (result.get("exports") or {}).get("files", {})
    exported = sum(f"manuscript.{fmt}" in exports for fmt in ("md", "mdx", "zip"))
    return {**base, "title": plan["title"], "language": plan["language"], "planned_chapters": len(plan["chapters"]),
            "current_chapter": number if number and number <= len(plan["chapters"]) else None,
            "counts": counts(plan, result, status, exported), "chapters": chapters, "length": facts,
            "failure": failure(result, facts, finished, status)
            if status in ("failed", "paused") and (result.get("error") or base["awaiting"] == "decision") else None}


def failure(result, facts, finished, status):
    """What happened, how often the studio tried, and where the last good checkpoint is."""
    saved = max(finished) if finished else None
    return {"code": result.get("error"), "number": result.get("number"), "attempts": result.get("current", {}).get("passes", 0),
            "automatic_retries": result.get("retry", {}).get("attempt", 0),
            "checkpoint": {"chapter": saved, "words": finished[saved]["words"] if saved else None},
            "exhausted": bool(facts and facts["state"] != "ok" and facts["passes"] >= facts["attempt_limit"]),
            "status": status}
