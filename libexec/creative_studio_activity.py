"""Live activity of the production worker: heartbeat, model request and the derived health of a running job.

Only signals the studio really observes are recorded here:

* ``heartbeat``  the monitor thread saw the worker thread alive while it executes this job. It proves
  that the worker is reachable. It proves nothing about the model.
* ``progress``   the last time real work advanced: a stored checkpoint, a new model request, or a token
  counter reported by the model slot that moved.
* ``model``      one in-flight model request with the slot state the router reports for it.

A quiet job is not a failed job. ``health`` only reports ``stalled`` after the checks that can prove it.
The registry lives in memory. The persistent job events stay in the job record.
"""
import contextlib
import json
import os
import threading
import time

HEARTBEAT_INTERVAL = 2.0     # monitor tick
HEARTBEAT_TIMEOUT = 20.0     # no confirmed worker heartbeat for this long while the job claims to run
PROBE_INTERVAL = 4.0         # model slot probe while a request is in flight

# seconds without confirmed progress: "quiet" starts the verification, "stalled" needs a failed verification too
DEFAULT_THRESHOLDS = {
    "default": {"quiet": 600, "stalled": 2400},
    "writing": {"quiet": 480, "stalled": 2400},
    "auditing": {"quiet": 600, "stalled": 2400},
    "reviewed": {"quiet": 600, "stalled": 2400},
    "rewrite_audit": {"quiet": 600, "stalled": 2400},
    "image_wait": {"quiet": 900, "stalled": 3600},
    "export_generation": {"quiet": 300, "stalled": 1200},
}


def thresholds(environ=None):
    """Per-step thresholds. CREATIVE_STUDIO_ACTIVITY may override single values: {"writing": {"quiet": 900}}."""
    merged = {key: {name: float(limit) for name, limit in value.items()} for key, value in DEFAULT_THRESHOLDS.items()}
    raw = (environ if environ is not None else os.environ).get("CREATIVE_STUDIO_ACTIVITY", "")
    try:
        custom = json.loads(raw) if raw else {}
    except ValueError:
        custom = {}
    for phase, values in (custom.items() if isinstance(custom, dict) else ()):
        if isinstance(values, dict):
            target = merged.setdefault(phase, dict(merged["default"]))
            for key in ("quiet", "stalled"):
                if isinstance(values.get(key), (int, float)) and values[key] > 0:
                    target[key] = float(values[key])
    for values in merged.values():
        values["stalled"] = max(values["stalled"], values["quiet"])
    return merged


def parse_slots(slots):
    """Reduce a llama.cpp /slots answer to what proves model progress, or None if it carries no such facts."""
    if not isinstance(slots, list) or not slots:
        return None
    busy = [slot for slot in slots if isinstance(slot, dict) and slot.get("is_processing")]
    if not busy:
        return {"processing": False, "decoded": None, "task": None}
    decoded, task = 0, None
    for slot in busy:
        task = slot.get("id_task", task)
        for token in slot.get("next_token") or ():
            if isinstance(token, dict) and isinstance(token.get("n_decoded"), int):
                decoded = max(decoded, token["n_decoded"])
    return {"processing": True, "decoded": decoded, "task": task}


class Entry:
    def __init__(self, job_id):
        self.job_id = job_id
        self.active = False
        self.number = self.phase = None
        self.heartbeat_at = self.progress_at = self.progress_kind = None
        self.model = None
        self.last_model = None
        self.probe_at = 0.0


class Activity:
    """Thread-safe registry. ``clock`` and ``probe`` are injectable for tests."""

    def __init__(self, clock=time.time, probe=None):
        self.clock, self.probe = clock, probe
        self.lock = threading.RLock()
        self.entries = {}
        self.worker = None
        self.local = threading.local()
        self.started_at = clock()

    # --- worker side -------------------------------------------------------------------------------------
    def attach(self, thread):
        self.worker = thread

    @contextlib.contextmanager
    def step(self, job_id, number, phase):
        now = self.clock()
        with self.lock:
            entry = self.entries.setdefault(job_id, Entry(job_id))
            entry.active, entry.number, entry.phase = True, number, phase
            entry.heartbeat_at = now
            entry.progress_at, entry.progress_kind = now, "step"
            entry.model = None
        self.local.job = job_id
        try:
            yield entry
        finally:
            self.local.job = None
            with self.lock:
                entry.active, entry.model = False, None

    def checkpoint(self, job_id):
        """A stored checkpoint is real progress of the step."""
        with self.lock:
            entry = self.entries.get(job_id)
            if entry:
                entry.progress_at, entry.progress_kind = self.clock(), "checkpoint"

    @contextlib.contextmanager
    def model_request(self, alias, role, prompt_tokens, timeout):
        job_id = getattr(self.local, "job", None)
        entry = self.entries.get(job_id) if job_id else None
        if not entry:
            yield None
            return
        started = self.clock()
        request = {"alias": alias, "role": role, "prompt_tokens": prompt_tokens, "timeout": timeout, "started_at": started,
                   "state": "unknown", "decoded": None, "observed": False, "task": None, "progress_at": started}
        with self.lock:
            entry.model = request
            entry.progress_at, entry.progress_kind = started, "model_request"
            entry.probe_at = 0.0
        outcome = {"outcome": "ok"}
        try:
            yield outcome
        except BaseException as exc:
            outcome["outcome"] = "timeout" if isinstance(exc, TimeoutError) else "error"
            outcome["error"] = type(exc).__name__
            raise
        finally:
            finished = self.clock()
            with self.lock:
                entry.model = None
                entry.last_model = {"alias": alias, "role": role, "started_at": started, "finished_at": finished,
                                    "duration": finished - started, "prompt_tokens": prompt_tokens,
                                    "completion_tokens": outcome.get("completion_tokens"), "chars": outcome.get("chars"),
                                    "outcome": outcome["outcome"], "error": outcome.get("error")}
                entry.progress_at, entry.progress_kind = finished, "model_response"

    # --- monitor side ------------------------------------------------------------------------------------
    def tick(self):
        """One monitor pass: confirm the worker thread, and read the slot of an in-flight model request."""
        now = self.clock()
        alive = self.worker is not None and self.worker.is_alive()
        with self.lock:
            entries = [entry for entry in self.entries.values() if entry.active]
        for entry in entries:
            if alive:
                with self.lock:
                    entry.heartbeat_at = now
            request = entry.model
            if request and self.probe and now - entry.probe_at >= PROBE_INTERVAL:
                entry.probe_at = now
                try:
                    seen = parse_slots(self.probe(request["alias"]))
                except Exception:
                    seen = None
                with self.lock:
                    self.observe(entry, request, seen, now)

    @staticmethod
    def observe(entry, request, seen, now):
        if seen is None:
            request.update(state="unknown", observed=False)
            return
        request["observed"] = True
        if not seen["processing"]:
            request.update(state="idle_slot")
            return
        previous = request["decoded"]
        request.update(task=seen["task"], decoded=seen["decoded"])
        if seen["decoded"]:
            request["state"] = "generating"
            if previous != seen["decoded"]:
                request["progress_at"] = now
                entry.progress_at, entry.progress_kind = now, "tokens"
        else:
            request["state"] = "prefill"

    def run_monitor(self):
        while True:
            try:
                self.tick()
            except Exception:  # the monitor must outlive any single bad pass
                pass
            time.sleep(HEARTBEAT_INTERVAL)

    def start_monitor(self):
        threading.Thread(target=self.run_monitor, daemon=True, name="production-activity").start()

    # --- read side ---------------------------------------------------------------------------------------
    def snapshot(self, job_id):
        """Facts about one job for the API. ``None`` when this process never executed the job."""
        now = self.clock()
        with self.lock:
            entry = self.entries.get(job_id)
            busy = next((e.job_id for e in self.entries.values() if e.active), None)
            worker = {"alive": self.worker.is_alive() if self.worker is not None else None, "busy_with": busy,
                      "process_started_at": self.started_at}
            if not entry:
                return {"server_time": now, "worker": worker, "known": False}
            request = dict(entry.model) if entry.model else None
            return {"server_time": now, "worker": worker, "known": True, "job_id": job_id, "active": entry.active,
                    "number": entry.number, "phase": entry.phase, "heartbeat_at": entry.heartbeat_at,
                    "progress_at": entry.progress_at, "progress_kind": entry.progress_kind,
                    "model": request, "last_model": dict(entry.last_model) if entry.last_model else None}


def health(snapshot, *, status, phase, updated, now, limits=None):
    """Differentiate a working job from a quiet one and prove a stalled one.

    Returns {"level", "reason", "quiet_for", "checks"}. Levels:
      ok          progress within the step threshold, or the model reports tokens
      waiting     the worker executes a different job first
      quiet       no confirmed progress for longer than usual. The process state is being verified
      stalled     verified: no model activity can be shown any more, or the model slot made no progress
      worker_down the worker thread does not run, or its heartbeat stopped
      none        the job is not running
    """
    limits = limits or thresholds()
    if status not in ("queued", "running"):
        return {"level": "none", "reason": status, "quiet_for": None, "checks": {}}
    limit = limits.get(phase) or limits["default"]
    if snapshot is None or not snapshot.get("known"):
        worker = (snapshot or {}).get("worker", {})
        if snapshot is not None and worker.get("alive") is False:
            return {"level": "worker_down", "reason": "worker_not_running", "quiet_for": None, "checks": {"worker_alive": False}}
        if snapshot is not None and worker.get("busy_with"):
            return {"level": "waiting", "reason": "worker_busy", "quiet_for": None, "checks": {"worker_alive": True}}
        quiet = max(0.0, now - (updated or now))
        return {"level": "ok" if quiet < HEARTBEAT_TIMEOUT or snapshot is None else "worker_down",
                "reason": "checkpoint_only" if snapshot is None else "no_heartbeat",
                "quiet_for": quiet, "checks": {"worker_alive": None}}
    worker = snapshot["worker"]
    checks = {"worker_alive": worker.get("alive"), "heartbeat_age": None, "model_active": bool(snapshot.get("model")),
              "slot_processing": None, "tokens": None}
    if not snapshot.get("active"):
        if worker.get("busy_with") and worker["busy_with"] != snapshot.get("job_id"):
            return {"level": "waiting", "reason": "worker_busy", "quiet_for": None, "checks": checks}
        # Between two steps the worker commits and picks the job up again within a second.
        idle = now - max(updated or 0, snapshot.get("progress_at") or 0)
        if idle > HEARTBEAT_TIMEOUT and worker.get("alive") is False:
            return {"level": "worker_down", "reason": "worker_not_running", "quiet_for": idle, "checks": checks}
        return {"level": "ok", "reason": "between_steps", "quiet_for": max(0.0, idle), "checks": checks}
    checks["heartbeat_age"] = now - snapshot["heartbeat_at"] if snapshot.get("heartbeat_at") else None
    if worker.get("alive") is False or (checks["heartbeat_age"] is not None and checks["heartbeat_age"] > HEARTBEAT_TIMEOUT):
        return {"level": "worker_down", "reason": "worker_not_running" if worker.get("alive") is False else "heartbeat_lost",
                "quiet_for": None, "checks": checks}
    progress = max(snapshot.get("progress_at") or 0, updated or 0)
    quiet = max(0.0, now - progress)
    request = snapshot.get("model")
    if request:
        checks["slot_processing"] = {"generating": True, "prefill": True, "idle_slot": False}.get(request["state"])
        checks["tokens"] = request.get("decoded")
        if request["state"] == "generating" and now - request["progress_at"] < limit["quiet"]:
            return {"level": "ok", "reason": "model_generating", "quiet_for": quiet, "checks": checks}
    if quiet < limit["quiet"]:
        return {"level": "ok", "reason": "recent_progress", "quiet_for": quiet, "checks": checks}
    if quiet >= limit["stalled"] and request:
        # Verification: a slot that is idle for a pending request, or a token counter that stood still the whole time.
        if request["state"] == "idle_slot":
            return {"level": "stalled", "reason": "model_slot_idle", "quiet_for": quiet, "checks": checks}
        if request["state"] == "generating":
            return {"level": "stalled", "reason": "no_new_tokens", "quiet_for": quiet, "checks": checks}
    return {"level": "quiet", "reason": "verifying", "quiet_for": quiet, "checks": checks}
