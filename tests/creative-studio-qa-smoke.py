#!/usr/bin/env python3
"""Quick creative-studio QA smoke (test groups A/B/C, short-form).

Long-form and 256K proofs live in tests/gemma4-256k-check.py; this covers the
productive writing/research surface at human-scale prompt sizes: German story
voice, German article prose, English story voice, English devlog, and the
research roles' fact discipline. Runs against the live router; each call is a
real generation. Exit 0 when every probe answers with usable prose (graded
deterministically on structure, not taste).

Usage: creative-studio-qa-smoke.py [--base http://127.0.0.1:8080] [--out f.json]
"""
import argparse
import json
import re
import time
import urllib.request

BASE_DEFAULT = "http://127.0.0.1:8080"

PROBES = [
    # (id, alias, language, system, user, minimum expectation)
    ("story-de", "creative-writing", "de",
     "Du schreibst natürliche deutsche Kurzprosa ohne KI-Floskeln.",
     "Schreibe eine Szene von ca. 120 Woertern: Zwei Schwestern reparieren "
     "abends ein Fahrrad in einer Werkstatt. Erklaere nichts, erzaehle nicht "
     "ueber Stimmen, keine Erklaerungen. Nur Szenen, keine Erklaerungen.",
     lambda t: len(t.split()) >= 60 and "!" not in t[:20]),
    ("story-en", "creative-writing", "en",
     "You write natural English short prose without AI filler.",
     "Write a ~120-word scene: two sisters fix a bicycle in a garage at "
     "night. Keep it plain and concrete.",
     lambda t: len(t.split()) >= 60),
    ("article-de", "human-writing", "de",
     "Du schreibst klare deutsche Sachtexte.",
     "Fasse in ca. 80 Woertern zusammen, was ein GPU-KV-Cache bei langen "
     "LLM-Kontexten kostet. Keine Listen, ein Absatz.",
     lambda t: 40 <= len(t.split()) <= 220),
    ("devlog-en", "human-writing", "en",
     "You write terse technical devlogs.",
     "Two sentences for a devlog: why 8-bit KV cache was chosen over f32 on "
     "an 8 GB VRAM laptop for a 262144-token window.",
     lambda t: 12 <= len(t.split()) <= 120),
    ("research-facts", "research-code", "de",
     "Du pruefst Fakten und kennst Unsicherheit.",
     "Nenne drei verifizierbare Fakten ueber den AMD Ryzen AI 9 HX 370 "
     "(CPU fuer den Framework Laptop 16). Kurz, mit Zahl, kein Schmuck.",
     lambda t: any(c.isdigit() for c in t)),
    ("research-audit", "research-code", "de",
     "Du pruefst Texte auf sachliche Fehler.",
     "Pruefe diesen Absatz auf sachliche Fehler und nenne sie: 'Gemory 26B "
     "hat 30 Layer, davon sind 5 reines Full-Attention-Modelle.' Antworte "
     "mit der Kernaussage in einem Satz.",
     lambda t: len(t.split()) >= 5),
]


def chat(base, model, system, user, timeout=300):
    payload = {"model": model,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "max_tokens": 700, "temperature": 0.4}
    req = urllib.request.Request(f"{base}/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    msg = out["choices"][0]["message"]
    text = (msg.get("content") or "") + (msg.get("reasoning_content") or "")
    return text.strip(), round(time.monotonic() - t0, 1), out.get("usage") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--out")
    args = ap.parse_args()
    rows = []
    ok_all = True
    for pid, alias, lang, system, user, grade in PROBES:
        try:
            text, secs, usage = chat(args.base, alias, system, user)
            ok = bool(text) and grade(text)
        except Exception as exc:  # a dead router is a finding, not a pass
            text, secs, usage, ok = f"ERROR {exc}", 0.0, {}, False
        ok_all = ok_all and ok
        rows.append({"probe": pid, "alias": alias, "language": lang, "ok": ok,
                     "seconds": secs, "completion_tokens": usage.get("completion_tokens"),
                     "excerpt": text[:280]})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    result = {"date": time.strftime("%Y-%m-%d"), "verdict": "PASS" if ok_all else "BLOCKED",
              "probes": rows}
    print(json.dumps({"verdict": result["verdict"]}, ), flush=True)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(json.dumps(result, indent=1) + "\n")
    raise SystemExit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
