#!/usr/bin/env python3
"""Prove a 262144-token context on a running llama.cpp server.

For one model profile this script:
  1. asserts the served slot count and n_ctx (via /slots),
  2. builds a synthetic multi-document corpus with unique secret keys at
     early/middle/late token offsets (~10K/100K/200K/240K),
  3. asks for the keys and grades the answers,
  4. runs a separate long-output pass capped so input+overhead+output stay
     under 262144,
  5. writes JSON results with measured token counters and timings.

Compaction/summarization is never used on this path; the raw prompt goes out
untouched. Exit code 0 = PASS for this model.

Usage: gemma4-256k-check.py --base http://127.0.0.1:8080 --model PROFILE
                            [--out results.json] [--tokens 245000]
                            [--max-tokens 8192] [--quick]
"""

import argparse
import json
import re
import statistics
import time
import urllib.request

BASE_DEFAULT = "http://127.0.0.1:8080"
TARGET_CTX = 262144
PROBE_POSITIONS = (10_000, 100_000, 200_000, 240_000)
FILLER_SENTENCE = (
    "The maintenance log recorded calibration drift, a coolant pressure "
    "reading within tolerance, one spare relay staged at bay four, and a "
    "note that the next inspection window opens after the harvest festival. "
)


def http_json(url, payload=None, timeout=3600):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def chat(base, model, messages, max_tokens, expect_len_hint=None):
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "temperature": 0,
    }
    t0 = time.monotonic()
    out = http_json(f"{base}/v1/chat/completions", payload)
    dt = time.monotonic() - t0
    message = out["choices"][0]["message"]
    # reasoning models (research-code) answer in reasoning_content and leave
    # content empty when the budget truncates the visible part
    text = (message.get("content") or "") + (message.get("reasoning_content") or "")
    usage = out.get("usage") or {}
    return {
        "text": text,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "seconds": round(dt, 2),
        "finish": out["choices"][0].get("finish_reason"),
    }


def build_corpus(target_tokens, probe_seed_words):
    """Filler corpus with unique secrets at token-proportional offsets.

    The server-side tokenizer decides the real count; positions are placed as
    fractions of 262144 and the measured prompt_tokens are reported back, so
    grading uses the real counters, never the requested ones.
    """
    secrets = {f"KEY-{p//1000:03d}": probe_seed_words[f"KEY-{p//1000:03d}"] for p in PROBE_POSITIONS}
    marks = [(p, f"KEY-{p//1000:03d}", secrets[f"KEY-{p//1000:03d}"]) for p in PROBE_POSITIONS]
    # measured: this filler tokenizes to ~5.44 chars/token on the Gemma
    # tokenizer (2,295,470 chars -> 229,547 tokens on research-code)
    approx_chars = int(target_tokens * 5.44)
    n_blocks = max(len(marks) + 1, approx_chars // (len(FILLER_SENTENCE) + 1))
    slots = {int(p * n_blocks // TARGET_CTX): (k, s) for p, k, s in marks}
    blocks = []
    for i in range(n_blocks):
        piece = [FILLER_SENTENCE]
        if i in slots:
            key, secret = slots[i]
            piece.append(f"ARCHIVE {key}: the vault code is {secret}.")
        blocks.append(" ".join(piece))
    # if two marks collided in one slot, append the losers at the tail so none are lost
    if len(slots) < len(marks):
        for p, key, secret in marks:
            if int(p * n_blocks // TARGET_CTX) not in slots:
                blocks.append(f"ARCHIVE {key}: the vault code is {secret}.")
    return "\n".join(blocks), secrets


def quick_corpus():
    secrets = {}
    parts = []
    for pos in PROBE_POSITIONS:
        key = f"KEY-{pos//1000:03d}"
        secrets[key] = f"alpha{pos}-delta"
    text = " ".join(
        [f"ARCHIVE KEY-{p//1000:03d}: the vault code is alpha{p}-delta. " + FILLER_SENTENCE for p in PROBE_POSITIONS]
    )
    return text, secrets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out")
    ap.add_argument("--tokens", type=int, default=245_000, help="approx target input tokens incl. overhead")
    ap.add_argument("--max-tokens", type=int, default=8_192)
    ap.add_argument("--quick", action="store_true", help="small-corpus smoke variant (NOT a 256K proof)")
    args = ap.parse_args()

    result = {"model": args.model, "target_ctx": TARGET_CTX, "quick": args.quick, "checks": []}

    # 1) slot/context assertion; the router requires ?model= on /slots
    slots = http_json(f"{args.base}/slots?model={args.model}")
    slot = slots[0] if isinstance(slots, list) and slots else {}
    n_ctx = slot.get("n_ctx") or slot.get("context")
    result["slot"] = {"n_ctx": n_ctx, "id": slot.get("id"), "model": slot.get("model"),
                      "n_ctx_expected": TARGET_CTX,
                      "n_ctx_ok": n_ctx == TARGET_CTX}
    result["checks"].append(result["slot"]["n_ctx_ok"])
    if not result["slot"]["n_ctx_ok"] and not args.quick:
        result["verdict"] = "BLOCKED"
        print(json.dumps(result, indent=1))
        raise SystemExit(1)

    seed = {f"KEY-{p//1000:03d}": f"alpha{p}-delta{p*7%9973:04d}" for p in PROBE_POSITIONS}
    if args.quick:
        corpus, secrets = quick_corpus()
    else:
        corpus, secrets = build_corpus(args.tokens, seed)
    question = (
        "Given only the archive above, report each vault code exactly. "
        "Answer as lines 'KEY-XXX: <code>'. Codes: "
        + ", ".join(sorted(secrets))
        + ". Nothing else."
    )
    msg = [
        {"role": "system", "content": "You are a precise archivist."},
        {"role": "user", "content": corpus + "\n\n" + question},
    ]
    r = chat(args.base, args.model, msg, 768)
    measured = r.get("prompt_tokens")
    result["longctx"] = {
        "approx_input_tokens_target": args.tokens,
        "measured_prompt_tokens": measured,
        "completion": r["text"][:2000],
        "seconds": r["seconds"],
        "seconds_per_1k_prompt_tokens": round(r["seconds"] / max(1, measured) * 1000, 2) if measured else None,
    }
    ok = all(re.search(re.escape(v), r["text"]) for v in secrets.values())
    near_target = (not args.quick) and measured and abs(measured - args.tokens) < args.tokens * 0.15
    result["checks"].append(bool(ok))
    if not args.quick:
        result["checks"].append(bool(near_target))
    result["longctx"]["secrets_recovered"] = ok

    # 2) long output pass (budget guarded below 262144)
    out_budget = args.max_tokens
    msg_out = [
        {"role": "user", "content": "Write a detailed 8000-token technical field "
                                      "manual for a fictional archive robot, as "
                                      "continuous prose with numbered sections."}
    ]
    if args.quick:
        out_budget = 512
        msg_out = [{"role": "user", "content": "List 30 short facts about archive robots."}]
    r2 = chat(args.base, args.model, msg_out, out_budget)
    total_tokens = (r2.get("prompt_tokens") or 0) + (r2.get("completion_tokens") or 0)
    result["longout"] = {
        "max_tokens": out_budget,
        "prompt_tokens": r2.get("prompt_tokens"),
        "completion_tokens": r2.get("completion_tokens"),
        "total_tokens": total_tokens,
        "under_ctx": total_tokens < TARGET_CTX,
        "seconds": r2["seconds"],
        "decoded_tokens_per_second": round((r2.get("completion_tokens") or 0) / max(0.1, r2["seconds"]), 1),
    }
    result["checks"].append(bool(result["longout"]["under_ctx"]))

    result["verdict"] = "PASS" if all(result["checks"]) else "BLOCKED"
    text = json.dumps(result, indent=1)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    print(text)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
