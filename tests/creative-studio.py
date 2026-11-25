#!/usr/bin/env python3
"""Local API-contract tests for libexec/llama-creative-studio.

Runs against the backend already listening on 127.0.0.1:8700 (start it with
`libexec/llama-creative-studio serve` or the creative-studio.service unit).
Needs no GPU and no models: inference paths are only exercised through job
lifecycle, never through real generation.  Wire format and route dispatch
only — run with `./setup.sh creative-studio test`.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CREATIVE_STUDIO_TEST_URL", "http://127.0.0.1:8700").rstrip("/")
passed = failed = 0


def req(path, body=None, method=None, base=BASE, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
    return resp.status, (json.loads(raw) if raw.startswith(b"{") or raw.startswith(b"[")
                         else raw.decode("utf-8", "replace"))


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


def main():
    try:
        req("/api/health", timeout=5)
    except (urllib.error.URLError, OSError):
        print(f"backend not reachable at {BASE} - start it first "
              "(libexec/llama-creative-studio serve)", file=sys.stderr)
        return 2

    # -- health / status -------------------------------------------------
    st, doc = req("/api/health")
    check("health ok flag", st == 200 and doc.get("ok") is True, str(doc)[:120])
    st, doc = req("/api/status")
    check("status lists aliases", "creative-writing" in doc.get("aliases", []),
          str(doc.get("aliases"))[:120])
    check("status lists upstreams", any("llama" in u["service"]
          for u in doc.get("upstream", [])), str(doc.get("upstream"))[:160])

    # -- projects + documents + versions ---------------------------------
    st, created = req("/api/projects", {"name": f"test-{int(time.time())}",
                                        "kind": "custom"})
    pid = created.get("id")
    check("project created", st in (200, 201) and bool(pid), str(created)[:120])
    st, doc = req("/api/documents", {"project_id": pid, "title": "Kapitel 1",
                                     "kind": "chapter", "body": "Erster Wurf."})
    did = doc.get("id")
    check("document created", st in (200, 201) and bool(did), str(doc)[:120])
    st, doc = req(f"/api/documents/{did}", {"body": "Zweiter Wurf.", "note": "test"})
    check("edit bumps version", doc.get("version") == 2, str(doc)[:160])
    st, doc = req(f"/api/documents/{did}", {"body": "Dritter Wurf.", "note": "test2"})
    st, hist = req(f"/api/documents/{did}/versions")
    nums = {v.get("version") for v in hist}
    check("history keeps predecessors", {1, 2} <= nums, str(nums)[:160])

    # -- images: queue contract only (no generation asserted) ------------
    st, doc = req("/api/images/generate", {"prompt": "test katze", "width": 512,
                                           "height": 512, "steps": 4})
    job = doc.get("job", doc)
    check("image job queued", st == 202 and job.get("status") in
          ("queued", "pending", "running", "waiting_gpu", "completed", "succeeded")
          and not doc.get("error"), json.dumps(doc)[:160])

    # -- research lifecycle: start, checkpoint, pause, resume ------------
    st, job = req("/api/research", {"question": "Testfrage: Hauptstadt von Testland?",
                                    "mode": "quick", "budget_minutes": 4})
    rid = job.get("id")
    check("research started", st in (200, 202) and bool(rid), str(job)[:120])
    st, doc = req(f"/api/research/{rid}")
    check("research checkpoint readable", "checkpoint" in doc, json.dumps(doc)[:160])
    st, doc = req(f"/api/research/{rid}/pause", {})
    ok_pause = doc.get("paused") is True
    st, doc = req(f"/api/research/{rid}/resume", {})
    ok_resume = doc.get("paused") is False
    check("pause/resume roundtrip", ok_pause and ok_resume, json.dumps(doc)[:160])

    # -- catalog (read-only proxy, may be degraded but must answer) ------
    st, doc = req("/api/catalog")
    check("catalog responds", st == 200, str(doc)[:120])

    # -- unknown route / method → JSON, never HTML crash -----------------
    try:
        st, doc = req("/api/nope")
        check("unknown route json", isinstance(doc, dict) or st == 404, str(doc)[:80])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        check("unknown route json", body.startswith("{") or e.code == 404,
              body[:80])

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
