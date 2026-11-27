#!/usr/bin/env python3
"""Production monitor: derived job state, heartbeat and stalled detection, word facts, timeline and the real job.

The state machine runs through the real persistence layer with deterministic upstreams (see the production test).
Nothing here touches the live studio database: the real job is read from a read-only copy."""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libexec"))
import creative_studio_activity as live
import creative_studio_monitor as monitor
import creative_studio_production as production
import creative_studio_story as story

spec = importlib.util.spec_from_file_location("studio_production_fixture", ROOT / "tests/creative-studio-production.py")
assert spec and spec.loader
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
Fixture, fake_model, PROSE, example_plan = fixtures.Fixture, fixtures.fake_model, fixtures.PROSE, fixtures.example_plan

NOW = 1_800_000_000.0


def snapshot(**changes):
    base = {"server_time": NOW, "worker": {"alive": True, "busy_with": None, "process_started_at": NOW - 9999}, "known": True,
            "job_id": "j" * 32, "active": True, "number": 1, "phase": "writing", "heartbeat_at": NOW - 1, "progress_at": NOW - 5,
            "progress_kind": "checkpoint", "model": None, "last_model": None}
    return {**base, **changes}


def request(state, started, decoded=None, progress=None):
    return {"alias": "creative-writing", "role": "write", "prompt_tokens": 9000, "timeout": 600, "started_at": started, "state": state,
            "decoded": decoded, "observed": state != "unknown", "task": 1, "progress_at": progress or started}


def health(snap, phase="writing", updated=None, now=NOW):
    return live.health(snap, status="running", phase=phase, updated=updated if updated is not None else now - 5, now=now)


class Health(unittest.TestCase):
    def test_a_long_prefill_is_quiet_but_never_reported_as_failed(self):
        started = NOW - 20 * 60
        result = health(snapshot(model=request("prefill", started), progress_at=started), updated=started)
        self.assertEqual((result["level"], result["reason"]), ("quiet", "verifying"))
        # Even far beyond the stalled threshold a prefill is not proof of a stall: only the model timeout ends it.
        started = NOW - 3 * 3600
        self.assertEqual(health(snapshot(model=request("prefill", started), progress_at=started), updated=started)["level"], "quiet")

    def test_the_first_minutes_without_tokens_are_not_an_alarm(self):
        started = NOW - 90
        self.assertEqual(health(snapshot(model=request("prefill", started), progress_at=started), updated=started)["level"], "ok")

    def test_generating_tokens_keep_the_job_healthy_even_after_a_long_step(self):
        result = health(snapshot(model=request("generating", NOW - 1500, decoded=4200, progress=NOW - 3), progress_at=NOW - 3), updated=NOW - 1500)
        self.assertEqual((result["level"], result["reason"]), ("ok", "model_generating"))
        self.assertEqual(result["checks"]["tokens"], 4200)

    def test_worker_reachable_but_no_new_tokens_is_told_apart_and_proven(self):
        stuck = request("generating", NOW - 3000, decoded=777, progress=NOW - 700)
        quiet = health(snapshot(model=stuck, progress_at=NOW - 700), updated=NOW - 3000)
        self.assertEqual((quiet["level"], quiet["checks"]["tokens"]), ("quiet", 777))
        stuck = request("generating", NOW - 3000, decoded=777, progress=NOW - 2600)
        proven = health(snapshot(model=stuck, progress_at=NOW - 2600), updated=NOW - 3000)
        self.assertEqual((proven["level"], proven["reason"]), ("stalled", "no_new_tokens"))
        idle = health(snapshot(model=request("idle_slot", NOW - 2600), progress_at=NOW - 2600), updated=NOW - 2600)
        self.assertEqual((idle["level"], idle["reason"]), ("stalled", "model_slot_idle"))

    def test_a_missing_heartbeat_is_found_and_so_is_a_dead_worker_thread(self):
        lost = health(snapshot(heartbeat_at=NOW - 60))
        self.assertEqual((lost["level"], lost["reason"]), ("worker_down", "heartbeat_lost"))
        dead = health(snapshot(worker={"alive": False, "busy_with": None, "process_started_at": 0}))
        self.assertEqual((dead["level"], dead["reason"]), ("worker_down", "worker_not_running"))
        self.assertEqual(health(snapshot(heartbeat_at=NOW - 3))["level"], "ok")

    def test_between_steps_and_other_jobs_are_not_mistaken_for_trouble(self):
        between = health(snapshot(active=False), updated=NOW - 1)
        self.assertEqual((between["level"], between["reason"]), ("ok", "between_steps"))
        waiting = health(snapshot(active=False, worker={"alive": True, "busy_with": "other", "process_started_at": 0}))
        self.assertEqual(waiting["level"], "waiting")

    def test_without_any_live_signal_only_the_stored_checkpoint_speaks(self):
        self.assertEqual(health(None)["reason"], "checkpoint_only")
        unknown = health({"server_time": NOW, "known": False, "worker": {"alive": True, "busy_with": None, "process_started_at": 0}}, updated=NOW - 3)
        self.assertEqual(unknown["level"], "ok")

    def test_a_finished_job_has_no_health(self):
        self.assertEqual(live.health(snapshot(), status="failed", phase="reviewed", updated=NOW, now=NOW)["level"], "none")

    def test_thresholds_are_configurable_per_step(self):
        limits = live.thresholds({"CREATIVE_STUDIO_ACTIVITY": json.dumps({"writing": {"quiet": 30}, "x": {"quiet": -1}, "image_wait": "bad"})})
        self.assertEqual(limits["writing"]["quiet"], 30)
        self.assertEqual(limits["image_wait"], live.thresholds({})["image_wait"])
        self.assertGreaterEqual(limits["writing"]["stalled"], 30)
        self.assertEqual(live.thresholds({"CREATIVE_STUDIO_ACTIVITY": "not json"}), live.thresholds({}))
        self.assertEqual(live.health(snapshot(progress_at=NOW - 60), status="running", phase="writing", updated=NOW - 60, now=NOW, limits=limits)["level"], "quiet")

    def test_slots_reduce_to_real_progress_facts(self):
        self.assertIsNone(live.parse_slots({"error": "x"}))
        self.assertEqual(live.parse_slots([{"is_processing": False}]), {"processing": False, "decoded": None, "task": None})
        busy = [{"is_processing": True, "id_task": 7, "next_token": [{"n_decoded": 0}]}]
        self.assertEqual(live.parse_slots(busy), {"processing": True, "decoded": 0, "task": 7})
        busy[0]["next_token"][0]["n_decoded"] = 31
        self.assertEqual(live.parse_slots(busy)["decoded"], 31)


class Registry(unittest.TestCase):
    def setUp(self):
        self.clock = [NOW]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.stop.wait, daemon=True)
        self.thread.start()
        self.slots = [{"is_processing": True, "id_task": 1, "next_token": [{"n_decoded": 0}]}]
        self.activity = live.Activity(clock=lambda: self.clock[0], probe=lambda alias: self.slots)
        self.activity.attach(self.thread)

    def tearDown(self):
        self.stop.set()

    def advance(self, seconds):
        self.clock[0] += seconds
        self.activity.tick()

    def test_request_phases_come_from_the_slot_and_progress_only_moves_with_tokens(self):
        with self.activity.step("job", 1, "writing"):
            with self.activity.model_request("creative-writing", "write", 9000, 600) as record:
                self.advance(5)
                seen = self.activity.snapshot("job")
                self.assertEqual((seen["model"]["state"], seen["model"]["decoded"]), ("prefill", 0))
                self.slots[0]["next_token"][0]["n_decoded"] = 40
                self.advance(5)
                first = self.activity.snapshot("job")
                self.assertEqual((first["model"]["state"], first["model"]["decoded"], first["progress_kind"]), ("generating", 40, "tokens"))
                self.advance(5)
                self.assertEqual(self.activity.snapshot("job")["progress_at"], first["progress_at"], "no new tokens: no new progress")
                record.update(completion_tokens=812, chars=3200)
            after = self.activity.snapshot("job")
        self.assertIsNone(after["model"])
        self.assertEqual((after["last_model"]["outcome"], after["last_model"]["completion_tokens"], after["last_model"]["chars"]), ("ok", 812, 3200))

    def test_the_heartbeat_follows_the_worker_thread_and_stops_with_it(self):
        with self.activity.step("job", 1, "writing"):
            self.advance(2)
            beat = self.activity.snapshot("job")["heartbeat_at"]
            self.assertEqual(beat, self.clock[0])
            self.stop.set()
            self.thread.join(2)
            self.advance(30)
            seen = self.activity.snapshot("job")
            self.assertEqual(seen["heartbeat_at"], beat)
            self.assertFalse(seen["worker"]["alive"])
            self.assertEqual(health(seen, now=self.clock[0], updated=self.clock[0] - 40)["level"], "worker_down")

    def test_a_model_timeout_is_recorded_as_a_timeout(self):
        with self.assertRaises(TimeoutError):
            with self.activity.step("job", 1, "writing"):
                with self.activity.model_request("creative-writing", "write", 1, 600):
                    self.advance(600)
                    raise TimeoutError
        self.assertEqual(self.activity.snapshot("job")["last_model"]["outcome"], "timeout")

    def test_an_unreachable_slot_probe_never_invents_progress(self):
        def broken(alias):
            raise OSError("no slots")
        self.activity.probe = broken
        with self.activity.step("job", 1, "writing"):
            with self.activity.model_request("creative-writing", "write", 1, 600):
                self.advance(5)
                model = self.activity.snapshot("job")["model"]
        self.assertEqual((model["state"], model["observed"], model["decoded"]), ("unknown", False, None))

    def test_calls_outside_a_tracked_step_are_ignored(self):
        with self.activity.model_request("creative-writing", "write", 1, 600) as record:
            self.assertIsNone(record)
        self.assertFalse(self.activity.snapshot("nobody")["known"])


class States(unittest.TestCase):
    derive = staticmethod(monitor.derive_state)

    def state(self, status, phase="writing", result=None, waiting=None, model=False):
        stored = {"events": [{}], "current": {"x": 1}} if result is None else result
        return self.derive(status, stored, phase, waiting_for=waiting, model_active=model, kind="story")

    def test_every_state_is_reachable_and_distinct(self):
        self.assertEqual(self.state("queued"), "preparing")
        self.assertEqual(self.state("running", result={}), "preparing")
        self.assertEqual(self.state("running"), "running")
        self.assertEqual(self.state("running", model=True), "model_wait")
        self.assertEqual(self.state("running", "auditing", model=True), "verifying")
        self.assertEqual(self.state("running", "reviewed", model=True), "correcting")
        self.assertEqual(self.state("running", result={"events": [{}], "current": {"x": 1}, "retry": {"attempt": 1, "code": "c"}}), "retrying")
        self.assertEqual(self.state("paused", waiting="user"), "paused")
        self.assertEqual(self.state("paused", waiting="decision"), "needs_decision")
        self.assertEqual(self.state("failed", "reviewed"), "failed")
        for status in ("completed", "cancelled", "incomplete"):
            self.assertEqual(self.state(status), status)

    def test_a_step_name_alone_never_turns_a_failed_job_into_work(self):
        # The step "reviewed" reads as "being improved" while the stored state says the job failed.
        self.assertEqual(self.state("failed", "reviewed", {"error": "story_length_failed"}), "failed")
        self.assertEqual(self.state("paused", "reviewed", waiting="user"), "paused")

    def test_pauses_name_what_they_wait_for(self):
        for reason, expected in (("blocker", "decision"), ("chapter", "chapter_approval"), ("art", "art_review"), ("user", "user")):
            self.assertEqual(monitor.awaiting("paused", {"pause_reason": reason}, language_retry=False, recheck=False), expected)
        self.assertEqual(monitor.awaiting("paused", {"pause_reason": "blocker"}, language_retry=True, recheck=False), "language_retry")
        self.assertEqual(monitor.awaiting("paused", {"pause_reason": "blocker"}, language_retry=False, recheck=True), "recheck")
        self.assertIsNone(monitor.awaiting("running", {}, language_retry=False, recheck=False))


def two_chapters(f):
    plan = example_plan()
    plan["chapters"] = [plan["chapters"][0], {**plan["chapters"][0], "title": "The second drawer", "beats": "Nera searches the archive.",
                                              "number": 2}]
    return plan


class StoredJobs(unittest.TestCase):
    def view(self, f, job, **extra):
        row = f.conn.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
        return production.public_job(row, bodies=production.job_bodies(f.conn, row), now=extra.pop("now", None), **extra)

    def test_a_running_model_request_is_reported_as_waiting_for_the_model(self):
        with Fixture() as f:
            job = f.start()
            activity = f.backend["ACTIVITY"]
            f.worker.tick()
            entered, release = threading.Event(), threading.Event()

            def blocking(lang, role, prompt, tokens, schema=None):
                with activity.model_request("creative-writing", role, 900, 600):
                    entered.set()
                    release.wait(10)
                return fake_model(lang, role, prompt, tokens, schema)

            f.worker.call = blocking
            thread = threading.Thread(target=f.worker.tick)
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                seen = activity.snapshot(job)
                report = self.view(f, job, snapshot=seen)
                self.assertEqual(report["status"], "running")
                self.assertIn(report["monitor"]["state"], ("model_wait", "verifying", "correcting"))
                self.assertTrue(report["monitor"]["activity"]["model"]["alias"])
                self.assertTrue(seen["active"] and seen["heartbeat_at"])
                self.assertEqual(report["monitor"]["health"]["level"], "ok")
            finally:
                release.set()
                thread.join(10)
            after = activity.snapshot(job)
            self.assertIsNone(after["model"])
            self.assertEqual(after["last_model"]["outcome"], "ok")

    def test_exhausted_length_fix_reports_the_stored_word_counts_and_the_reasons(self):
        with Fixture() as f:
            job = f.start()
            short = PROSE.rsplit(" The lock", 1)[0]
            prompts = []

            def unusable(lang, role, prompt, tokens, schema=None):
                if role == "write":
                    return short, {}, "stop"
                if role == "rewrite" and "anchor" in schema["properties"]:
                    prompts.append(prompt)
                    return json.dumps({"anchor": "this is not in the chapter", "addition": "Nera waited at the door of the archive."}), {}, "stop"
                return fake_model(lang, role, prompt, tokens, schema)

            f.worker.call = unusable
            row = f.drive()
            self.assertEqual(row["state"], "failed")
            report = self.view(f, job)
            m = report["monitor"]
            self.assertEqual((report["status"], m["state"], report["error"]), ("failed", "failed", "story_length_failed"))
            body = production.managed_docs(f.conn, f.pid)[0]["body"]
            words = story.count_words(body)
            facts = m["length"]
            self.assertEqual((facts["words"], facts["minimum"], facts["maximum"], facts["state"]), (words, 38, 60, "short"))
            self.assertEqual(facts["missing"], 38 - words)
            self.assertEqual((facts["attempts"], facts["failed_attempts"], facts["reasons"]), (2, 2, {"anchor": 2}))
            self.assertTrue(m["failure"]["exhausted"])
            self.assertIsNone(m["failure"]["checkpoint"]["chapter"])
            self.assertEqual(m["chapters"][0]["steps"]["correction"], "failed")
            self.assertEqual(m["chapters"][0]["steps"]["generate"], "done")
            self.assertIn("EARLIER ADDITIONS WERE REJECTED", prompts[1], "the next attempt must learn why the last one failed")
            self.assertNotIn("EARLIER ADDITIONS WERE REJECTED", prompts[0])
            self.assertEqual(m["health"]["level"], "none")
            # A retry resumes the same job. A second click finds it already queued and must not create another one.
            f.change("retry", job_id=job)
            with self.assertRaises(Exception) as caught:
                f.change("retry", job_id=job)
            self.assertEqual(getattr(caught.exception, "code", None) or str(caught.exception), "production_transition_invalid")
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='production' AND json_extract(payload,'$.kind')='story'").fetchone()[0], 1)

    def test_a_timed_out_model_retries_visibly_without_a_second_job_and_ends_as_a_timeout(self):
        with Fixture() as f:
            job = f.start()
            f.worker.tick()

            def slow(lang, role, prompt, tokens, schema=None):
                raise TimeoutError

            f.worker.call = slow
            states = []
            for _ in range(8):
                row = f.conn.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
                if row["state"] == "failed":
                    break
                f.worker.tick()
                row = f.conn.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
                states.append(self.view(f, job)["monitor"]["state"])
                with f.conn:
                    f.conn.execute("UPDATE jobs SET result=json_remove(result,'$.next_at') WHERE id=?", (job,))
            self.assertIn("retrying", states)
            report = self.view(f, job)
            self.assertEqual((report["status"], report["monitor"]["state"], report["detail"]["exception"]), ("failed", "failed", "TimeoutError"))
            attempts = [e["attempts"] for e in report["monitor"]["timeline"] if e.get("error")]
            self.assertTrue(attempts and max(attempts) == 3, attempts)
            self.assertEqual(f.conn.execute("SELECT count(*) FROM jobs WHERE service='production'").fetchone()[0], 1)
            self.assertTrue((report["monitor"]["timeline"][-1]["ref"] or "").endswith("production_upstream_unavailable"))

    def test_the_chapter_change_is_reflected_in_counts_and_steps(self):
        with Fixture() as f:
            f.create()
            plan = f.change("save-plan", plan=two_chapters(f))
            f.change("approve-plan", version=plan["version"])
            job = f.change("start", version=plan["version"], mode="together", session_id=f.sid)["id"]
            first = f.drive()
            self.assertEqual(first["state"], "paused")
            m = self.view(f, job)["monitor"]
            self.assertEqual((m["state"], m["awaiting"], m["current_chapter"]), ("paused", "chapter_approval", 1))
            self.assertEqual((m["chapters"][0]["status"], m["chapters"][1]["status"]), ("review", "pending"))
            self.assertEqual(m["counts"]["chapters"], {"done": 0, "total": 2})
            self.assertEqual(m["chapters"][0]["steps"]["finish"], "pending")
            f.change("resume", job_id=job)
            f.drive(stop=("paused",))
            after = self.view(f, job)["monitor"]
            self.assertEqual((after["current_chapter"], after["chapters"][0]["status"]), (2, "done"))
            self.assertEqual(after["counts"]["chapters"]["done"], 1)
            self.assertIn(after["chapters"][1]["status"], ("active", "review"))

    def test_a_finished_production_counts_only_what_exists(self):
        with Fixture() as f:
            job = f.start()
            paused = f.drive()
            self.assertEqual(json.loads(paused["result"])["pause_reason"], "art")
            f.change("approve-art", job_id=job)
            f.drive()
            report = self.view(f, job)
            m = report["monitor"]
            self.assertEqual((report["status"], m["state"]), ("completed", "completed"))
            self.assertEqual(m["counts"], {"chapters": {"done": 1, "total": 1}, "images": {"done": 2, "total": 2},
                                           "exports": {"done": 3, "total": 3}, "steps": {"done": 6, "total": 6}})
            self.assertTrue(all(status == "done" for status in m["chapters"][0]["steps"].values()))
            self.assertEqual(sorted(report["downloads"]), ["md", "mdx", "zip"])
            self.assertIsNone(m["length"])
            self.assertEqual(m["health"]["level"], "none")

    def test_the_timeline_is_the_persisted_event_list_and_nothing_else(self):
        with Fixture() as f:
            job = f.start()
            f.drive()
            row = f.conn.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
            events = json.loads(row["result"])["events"]
            line = self.view(f, job)["monitor"]["timeline"]
            self.assertEqual(len(line), len(events) + 1)
            self.assertEqual(line[0]["step"], "started")
            for entry, event in zip(line[1:], events):
                self.assertEqual((entry["at"], entry["step"], entry["status"]), (event["started_at"], event["step"], event["status"]))


class ModelCall(unittest.TestCase):
    def test_the_production_model_call_registers_its_request_and_what_the_slot_reports(self):
        with Fixture() as f:
            backend, activity, seen = f.backend, f.backend["ACTIVITY"], {}

            def router(url, method="GET", body=None, headers=None, timeout=30):
                if url.endswith("/v1/models"):
                    args = ["--ctx-size", "32768", "--n-predict", "4096", "--parallel", "1", "--model", "/m/Fake-Q4_K_M.gguf"]
                    return 200, {"data": [{"id": "creative-writing", "status": {"value": "loaded", "args": args}}]}
                if "/slots" in url:
                    return 200, [{"is_processing": True, "id_task": 3, "next_token": [{"n_decoded": 17}]}]
                if url.endswith("/health"):
                    return 200, {"busy": False}
                if url.endswith("/apply-template"):
                    system = "".join(m["content"] for m in body["messages"] if m["role"] == "system")
                    return 200, {"prompt": system + "<|turn>user" + body["messages"][-1]["content"]}
                if url.endswith("/tokenize"):
                    return 200, {"tokens": list(range(500))}
                assert url.endswith("/v1/chat/completions"), url
                activity.entries["job"].probe_at = 0.0
                activity.tick()      # the monitor thread's pass, taken while the request is open
                seen["during"] = activity.snapshot("job")
                seen["timeout"] = timeout
                return 200, {"model": "creative-writing", "choices": [{"message": {"content": "Der Text."}, "finish_reason": "stop"}],
                             "usage": {"completion_tokens": 321}}

            backend["http_json"] = router
            with activity.step("job", 1, "writing"):
                text, evidence, finish = backend["production_model"]("en", "write", "Write the scene.", 800)
            self.assertEqual((text, finish, evidence["prompt_tokens"]), ("Der Text.", "stop", 500))
            model = seen["during"]["model"]
            self.assertEqual((model["alias"], model["role"], model["state"], model["decoded"], model["prompt_tokens"], model["timeout"]),
                             ("creative-writing", "write", "generating", 17, 500, 600))
            self.assertEqual(seen["timeout"], 600)
            after = activity.snapshot("job")
            self.assertIsNone(after["model"])
            self.assertEqual((after["last_model"]["outcome"], after["last_model"]["completion_tokens"], after["last_model"]["chars"]), ("ok", 321, 9))

    def test_a_calls_timeout_is_recorded_before_the_error_travels_on(self):
        with Fixture() as f:
            backend, activity = f.backend, f.backend["ACTIVITY"]

            def router(url, method="GET", body=None, headers=None, timeout=30):
                if url.endswith("/v1/models"):
                    return 200, {"data": [{"id": "creative-writing", "status": {"value": "loaded", "args": ["--ctx-size", "32768", "--parallel", "1"]}}]}
                if "/slots" in url:
                    return 200, [{"is_processing": False}]
                if url.endswith("/health"):
                    return 200, {"busy": False}
                if url.endswith("/apply-template"):
                    return 200, {"prompt": "".join(m["content"] for m in body["messages"] if m["role"] == "system") + "<|turn>user"}
                if url.endswith("/tokenize"):
                    return 200, {"tokens": [1, 2, 3]}
                raise TimeoutError

            backend["http_json"] = router
            with self.assertRaises(TimeoutError):
                with activity.step("job", 1, "writing"):
                    backend["production_model"]("en", "write", "Write the scene.", 800)
            self.assertEqual(activity.snapshot("job")["last_model"]["outcome"], "timeout")


class RealJob(unittest.TestCase):
    """The production job "Donner über Thunderforge" from the live studio, read from a read-only copy."""
    live = Path(os.environ.get("CREATIVE_STUDIO_LIVE_DB", Path.home() / ".local/share/creative-studio/studio.sqlite3"))
    job = "71410090bf0448529c3987c87f37cb63"

    def setUp(self):
        if not self.live.exists():
            self.skipTest("no live studio database")
        self.tmp = tempfile.TemporaryDirectory()
        source = sqlite3.connect(f"file:{self.live}?mode=ro", uri=True)
        copy = Path(self.tmp.name) / "copy.sqlite3"
        target = sqlite3.connect(copy)
        source.backup(target)
        source.close()
        target.close()
        self.before = sqlite3.connect(f"file:{self.live}?mode=ro", uri=True).execute("SELECT updated,state FROM jobs WHERE id=?", (self.job,)).fetchone()
        self.conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (self.job,)).fetchone()
        if not self.row:
            self.skipTest("the job is not in this studio database")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_the_contradiction_is_gone_and_the_numbers_come_from_the_saved_text(self):
        report = production.public_job(self.row, bodies=production.job_bodies(self.conn, self.row), now=self.row["updated"] + 90)
        m = report["monitor"]
        # The stored job is failed. The old card read "Kapitel 2 wird verbessert" from the step name.
        self.assertEqual((self.row["state"], report["status"], m["state"], report["phase"]), ("failed", "failed", "failed", "reviewed"))
        self.assertEqual((m["title"], m["language"], m["planned_chapters"], m["current_chapter"]), ("Donner über Thunderforge", "de", 3, 2))
        facts = m["length"]
        self.assertEqual((facts["number"], facts["words"], facts["minimum"], facts["maximum"], facts["missing"], facts["state"]),
                         (2, 827, 900, 1200, 73, "short"))
        self.assertGreaterEqual(facts["attempts"], 2)
        self.assertTrue(m["failure"]["exhausted"])
        self.assertEqual(m["failure"]["checkpoint"], {"chapter": 1, "words": 1053})
        self.assertEqual(m["counts"]["chapters"], {"done": 1, "total": 3})
        self.assertEqual(m["counts"]["images"], {"done": 1, "total": 4})
        self.assertEqual([c["status"] for c in m["chapters"]], ["done", "active", "pending"])
        self.assertTrue(m["chapters"][0]["image"] and m["chapters"][0]["words"] == 1053)
        self.assertEqual(m["chapters"][1]["steps"]["correction"], "failed")
        self.assertEqual(m["health"]["level"], "none")
        self.assertEqual(report["error"], "story_length_failed")
        self.assertEqual(report["skills"], {"human-writing": "1.3.0", "story-writing": "1.0.0"})
        self.assertEqual(report["model"]["alias"], "creative-writing")
        self.assertGreater(len(m["timeline"]), 10)
        self.assertTrue(any(e.get("error") == "story_length_failed" and e["ref"] for e in m["timeline"]))

    def test_reading_the_job_changes_nothing_in_the_live_database(self):
        production.public_job(self.row, bodies=production.job_bodies(self.conn, self.row))
        after = sqlite3.connect(f"file:{self.live}?mode=ro", uri=True).execute("SELECT updated,state FROM jobs WHERE id=?", (self.job,)).fetchone()
        self.assertEqual(tuple(after), tuple(self.before))


def serve_real(port):
    """Serve the repo's studio over a private copy of the live database, for browser tests against the real job.

    The live database and its files are only read. Active jobs of other services are cancelled in the copy and all
    upstream services point to a closed port, so nothing of the live system can be started or changed."""
    import runpy
    import shutil
    live_dir = RealJob.live.parent
    work = Path(tempfile.mkdtemp(prefix="monitor-real-"))
    data = work / "creative-studio"
    (data / "production-images").mkdir(parents=True)
    source = sqlite3.connect(f"file:{RealJob.live}?mode=ro", uri=True)
    target = sqlite3.connect(data / "studio.sqlite3")
    source.backup(target)
    source.close()
    with target:
        target.execute("""UPDATE jobs SET state='cancelled' WHERE service!='production'
                          AND state IN ('queued','running','submitting','loading','generating','waiting_gpu','paused')""")
    row = target.execute("SELECT result,payload FROM jobs WHERE id=?", (RealJob.job,)).fetchone()
    target.close()
    result, payload = json.loads(row[0]), json.loads(row[1])
    images = [c["image"]["id"] for c in result.get("chapter_results", []) if c.get("image")]
    images += [result["cover"]["id"]] if result.get("cover") else []
    for image in images:
        original = live_dir / "production-images" / f"{image}.png"
        if original.exists():
            shutil.copy(original, data / "production-images" / original.name)
    print(json.dumps({"job": RealJob.job, "project": payload["project_id"], "session": payload["session_id"]}), flush=True)
    dead = "http://127.0.0.1:9"
    os.environ.update(XDG_DATA_HOME=str(work), CREATIVE_STUDIO_PORT=str(port), CREATIVE_STUDIO_IMAGES=dead,
                      CREATIVE_STUDIO_ROUTER=dead, CREATIVE_STUDIO_RESEARCH=dead)
    os.environ.setdefault("CREATIVE_STUDIO_WEB", str(ROOT / "packages/creative-studio/web/dist"))
    runpy.run_path(str(ROOT / "libexec/llama-creative-studio"))["cmd_serve"]()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve-real":
        serve_real(int(sys.argv[2]))
    else:
        unittest.main()
