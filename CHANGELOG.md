# Changelog
## 2026.11-monitor - Produktionsansicht mit Live-Aktivität

- Die Produktionskarte im Story-Chat zeigt den Zustand nur noch aus dem
  gespeicherten Jobstatus. Ein fehlgeschlagener Job meldete zuvor „Kapitel 2
  wird verbessert“, weil die Überschrift aus dem Schrittnamen `reviewed`
  entstand. Jetzt: Fehlgeschlagen, mit Ursache, Wortzahlen und Checkpoint.
- Neu: `libexec/creative_studio_monitor.py` (abgeleiteter Zustand, Kapitel-
  Teilschritte, Zähler, Wortzahl-Befund aus dem gespeicherten Text,
  Aktivitätsverlauf aus `result.events`) und
  `libexec/creative_studio_activity.py` (Heartbeat des Worker-Threads,
  Modellanfrage mit Slot-Fortschritt aus `/slots`, Health `ok/waiting/quiet/
  stalled/worker_down` mit schrittspezifischen, konfigurierbaren Schwellen
  über `CREATIVE_STUDIO_ACTIVITY`).
- `GET /api/production/jobs/<id>` liefert `monitor`. Neu:
  `GET /api/production/jobs/<id>/events` (Server-Sent Events), im Browser mit
  Polling-Fallback und Verbindungsstatus. Ein Verbindungsverlust bricht keinen
  Job ab.
- Szenenerweiterung speichert die Ursache jedes verworfenen Versuchs und nennt
  sie dem nächsten Versuch.
- UI: `production-monitor.ts`, breite Zweispaltenansicht auf Desktop,
  einspaltig mobil, Aktionen je Zustand, keine Retry-Knöpfe während eines
  laufenden Schritts, gesperrte Mehrfachklicks, ruhige Live-Ansagen.
  `docs/creative-studio/PRODUCTION_MONITOR.md`.
- Tests: `tests/creative-studio-monitor.py` (28 Fälle, inkl. echter Job
  „Donner über Thunderforge“ auf einer read-only-Kopie) und
  `tests/creative-studio-monitor.mjs` (Firefox: 14 Szenarien, Layout, axe,
  Tastatur, echter Job).

## 2026.11-knowledge - Ordnerwissen (optional, ordnergebundenes Weltwissen)

- `libexec/creative_studio_knowledge.py` + Migration: Ordnergebundenes Wissen
  (`knowledge_entries/-versions/-suggestions` in `studio.sqlite3`) mit
  Bestätigungsstufen (confirmed/reference/idea/unresolved), Versionierung mit
  Restore, Vorschlagswarteschlange und Markdown-/JSON-Export. Bestehende
  Ordner/Chats/Daten unverändert; leere Ordner funktionieren wie bisher.
- Vererbung an Unterordner (nächste Ebene gewinnt, bestätigte Gleichtitel-
  konflikte werden als ungeklärt gemeldet statt stillschweigend aufgelöst);
  keine Übertragung zwischen unabhängigen Ästen; Purge-Cascade mit dem Ordner.
- Selektive Injektion (Keyword-Relevanz + Budget, Ideen nie) in freien Chat,
  Schreib-Aufträge, Guided Writing, Story-/Produktions-Kanon (per
  Jobstart-Snapshot eingefroren) und Planungsschnappschuss; etablierte
  Kapitel-Fakten landen nur als Vorschlag, nie automatisch im Kanon.
- Visuelles Standardprofil pro Ordner; greift nur bei unberührten
  Story-Profilen (`version == 0`), autorisierte Profile gewinnen, andere
  Geschichten bleiben unverändert.
- UI: Ordner-Menü „Ordnerwissen verwalten“ (Übersicht, Bearbeiten,
  Vorschläge, Profil, Export); Chat-Hinweis über `GET /api/folders/hint`.
  `docs/creative-studio/FOLDER_KNOWLEDGE.md`.
- `tests/creative-studio-knowledge.py` (15 Fälle, inkl. Riff-Racers-Umlauf:
  Thunderforge nach Import `reference`, Neustart-Persistenz); Organizer-,
  Story-, Chat-, Produktions- und Writing-Suiten grün.

## 2026.11-creative - Creative Studio rollout completed, ladder proof, QA smoke

- Two-model production verified in place (no downloads): HauhauCS QAT
  research-code sha 3c131334…d73c, Gemory story sha 4991d114…4442, both equal
  their HF LFS OIDs; licenses documented in MODEL-LICENSES.md (gemma tag /
  apache-2.0).
- `tests/gemma4-256k-check.py --ladder`: proportional-probe ladder added;
  results in docs/results/*-256k-ladder.json. Verdict stays BLOCKED with a
  measured cause: both GGUFs ship hybrid attention (25/30 full layers,
  sliding_window 1024, KV 512/256 B) - byte-verified from metadata, not
  config. f32 KV at 256K OOMs on 8 GiB (measured); q8_0 stays.
- docs/PERFORMANCE.md rewritten to the two-model production knobs + measured
  prefill 93-97 t/s / decode 30.1/33.5 t/s; trio-era numbers kept as history.
- Open WebUI: `libexec/owui-migrate-creative-studio.py` (idempotent, python
  backup) registered Research & Analysis 256K / Creative Writing DE/EN 256K
  roles on the live aliases and repointed the orphaned riff-racers base
  (hemmingway -> story). Nine legacy GGUF weights deleted same day on user
  release over the open Dual-PASS gate (~101 GB freed; SHA list in
  ~/restore/2026-11-24-gemma4-256k-migration/models-sha256.txt, re-download
  via packages/models.tsv pins + setup.sh --download-models).

## 2026.11-studio - Local Creative Studio (opt-in) on the existing stack

- `libexec/llama-creative-studio` + `packages/creative-studio/web`: writing,
  deep research, image queue and game-design studio on 127.0.0.1:8700 —
  separate UI over the router/image-service/skills, base install unaffected.
- lifecycle over `./setup.sh creative-studio …` (install/update/serve/status/
  doctor/test/backup/restore/uninstall, data kept by default), systemd user
  unit + KDE starter; research dossiers land in the Recherche project, worker
  failures now settle as `failed` (no retry loop).
- `tests/creative-studio.py`: API-contract suite (runs live, no GPU);
  `tests/unit.sh` stays green untouched.

## 2026.11-gemma256 - Production profiles at the native 256K ceiling

- research, deep-research, creative-writing, human-writing/-rewrite/-audit:
  ctx 32768/16384 -> 262144, KV q8_0 -> q4_0, n-predict 8192 (Gemma 4 states
  256K for medium sizes; auto-fit keeps the 5070 in budget - measured 6573
  MiB research / 6553 MiB writing at load, no OOM).
- setup.sh: models.ini becomes a managed-synced file (backup on change like
  the candidate track) instead of aborting with "existing file differs".

## 2026.11-phai - Phai-A1-35B-1M joins the coding track on b12628

- coding-phai-256k: Phai-A1 35B A3B 1M, MXFP4_MOE with embedded MTP weights
  (prithivMLmods/Phai-A1-35B-1M-MTP-Repacked rev a3c7b4d8, apache-2.0,
  sha256 a59ab81d…, 20.26 GB). Native 262144, n-predict 8192, cpu-moe, Q4_0
  KV, sampler temp 1.0/top-p 0.95/top-k 20. Preset, TSV (five candidates,
  about 70 GB), router allowlist, Pi store/enabledModels, doctor, tests.
- Engine bump llama.cpp b12503 -> b12628 (commit 8a97fa98a, CUDA 12.8 build,
  SHA-256 pinned, current link switched, b12503 kept for rollback): needed
  for --spec-type draft-mtp; MXFP4 CUDA kernels load verified.
- Measured: router cold 28.9/24.2 t/s prefill/decode, VRAM 5197 MiB;
  retrieval 3/3 at 8K/32K/64K/128K; MTP A/B (n=512, 16K) 37.0 vs 39.2 t/s -
  no gain at temp 1.0, MTP stays off in the preset. Native MoE expert cache
  flags absent in b12628 (documented BLOCKED upstream-side).

## 2026.11-presets - Self-describing preset ids and native context ceilings

- Preset ids now carry model family and size: coding-cyber-tiel-35b (was
  coding-long-256k), coding-mellum-12b, coding-lfm-24b, coding-ornith-9b,
  coding-kat-35b (were candidate-*); production research/writing profile
  names stay stable (they share names with the research subnet, services,
  and the human-writing skill path). Renamed across presets, router, sandbox,
  manifests, doctor, tests, benchmarks, and docs.
- Presets now cap at each model's native context ceiling instead of a flat
  262144: Mellum2.1 and LFM2.5-24B are 131072 by model card (the old presets
  overran the trained length); qwen35moe (Cyber-Tiel, KAT-Coder) and
  Ornith-1.5 keep 262144. Router allowlist, Pi model store, manifest, and
  tests follow.

## 2026.11-candidates-slim - Coding candidate track trimmed to four models

- Dropped candidate-k2-horizon (K2 Horizon 7B) and candidate-lfm8 (LFM2.5 8B
  A1B) from the evaluation track: presets (config/models.ini.in), manifest
  rows (packages/models-coding-candidates.tsv, now 49.8 GB), router allowlist
  (libexec/pi-router.py), Pi model store/enabledModels (libexec/pi-sandbox),
  doctor counts (setup.sh) and tests. Mellum, LFM2.5 24B, Ornith and
  KAT-Coder remain; production models and profiles untouched.

## 2026.11-candidates - Coding candidate track for the six-model Pi comparison

- packages/models-coding-candidates.tsv: six pinned coding candidates (K2 Horizon
  7B, Mellum 2.1 12B A2.5B Thinking, LFM2.5 8B A1B, LFM2.5 24B A2B, Ornith 1.5
  9B, KAT-Coder V2.5 Dev 35B A3B), Q4_K_M, revisions/sizes/SHA-256 pinned from
  the HF API (2026-11-21), 60.5 GB total; production models and profiles intact.
- setup.sh install --coding-candidates: idempotent fetch (reuse, resume,
  SHA-256, headroom check), preset sync with backup, router preset reload;
  doctor reports candidate files + preset registration.
- uninstall.sh --remove-candidates: removes only the candidate GGUFs.
- config/models.ini.in: six candidate presets, native 262144 context per
  evaluation brief, Q4_0 KV, per-model samplers, cpu-moe for the MoE models.
- libexec/pi-router.py: model allowlist with per-id context/output limits;
  catalog filter and output caps follow the selected model.
- libexec/pi-sandbox: seven-entry offline model store (production + six
  candidates), enabledModels covers all ids, `pi --model candidate-…` and
  /model selection, coding-long-256k default unchanged.
- tests/pi-router.py: candidate limit and allowlist regressions (8/8).
- new docs: CODING_CANDIDATES.md (install, presets, Pi, MXFP4 gate, rollback).
- smoke A-F 2026-11-21, all six PASS incl. tool-call emit/roundtrip, reasoning
  separation, context recall, model switching without OOM; warm decode/prefill
  t/s and VRAM: k2 13.7/38.7 6510MiB, mellum 26.7/42.5 4854, lfm8 52.1/72.6
  4434, lfm24 30.0/46.9 5196, ornith 13.3/24.5 6430, kat 28.7/45.8 6392
  (auto-fit placement, 262144 preset, KV on host; tests/pi-sandbox.ts allowlist
  now covers the seven coding models, 11/11 probe flags true).

## 2026.11-permissions - Pi autonomy: Build as the standard mode

- config/permission-mode.json.in: pi-permission-modes profile rendered on
  install to ~/.pi/agent/permission-mode/permission-mode.json — defaultMode
  build; autonomous file/bash/tool/skill work inside the project, OS sandbox
  on, denyRead masks ssh/gnupg/aws/netrc/browser/cloud/pi-auth, skills
  read-only, network allowlist (npm/PyPI/GitHub/crates/localhost), push and
  destructive git stay ask, plan approval switches to build.
- libexec/pi-sandbox: mount ~/.pi-lens writable (pi-lens state); bwrap
  nesting verified on Fedora (allowNestedUserNamespaces in the mode profile).
- setup.sh renders the profile on install (existing kept), doctor checks
  defaultMode==build; unit tests 10/10, --dry-run clean.
- policy matrix 24/24 deterministic (allow/ask/deny per surface incl. bash
  AST rules); headless inference roundtrip through router verified.

## 2026.11-pi-ext - Pi extensions, templates, context record

- manifest config/pi-manifest.json: pi-lens 4.5.1, pi-permission-modes 2.7.2,
  pi-workspace-history 0.5.2, pi-todo-agent 0.3.0 (pinned, doctor-checked);
  pi-condense experimental-off, pi-sessions excluded (node>=24 vs pinned 22).
- setup.sh installs manifest-pinned extensions + config/prompts templates
  (finish/review/fix-ci/finish-docs); backup/uninstall cover prompts+npm.
- doctor reports extensions, templates, LSPs; unit tests 10/10.
- new docs: PI_EXTENSIONS.md, PI_COMMANDS.md, CONTEXT_ENGINEERING.md;
  measured A/B: native 49s/9826 vs +ext 50s/16951 ctx, both correct.


## 2026.11 - Pi one-click stack

- setup.sh becomes a command interface: install/update/repair/doctor/status/
  test/benchmark/backup/restore/uninstall plus --dry-run; resumable,
  idempotent, lock-protected, managed-file drift aborts.
- Pi Coding Agent 1.5.2 joins the stack: pinned npm prefix install, native
  llama.cpp provider to the router, coding-long-256k default (262,144/8,192),
  compaction 39322/20000, shared skills natively, MCP via mcp.json, sessions
  under ~/.pi/agent.
- bwrap project sandbox `pi-sandbox` ships as a managed tool.
- claude-local/codex-local wrappers and their API-compat shims removed;
  cloud Claude Code and Codex untouched. Recovery bundle documented.
- models.tsv extended: license, role, quant, context, tools, profile,
  display name; revisions and SHA-256 still pinned, downloads stay manual.
- hardware detection reports distro/arch/CPU/RAM/VRAM/glibc/THP and warns
  outside the tested envelope instead of guessing.
- English docs for architecture, models, Pi, MCP, skills, performance,
  benchmarks, security, backup, troubleshooting; German measurement record
  preserved; README rewritten.
- CI: shell syntax, shellcheck, JSON/manifest/doc-link gates and platform
  independent unit tests; CUDA/Fedora lanes documented as local-only.

## 2026.11-restore - b12503 restore kit

- llama.cpp b12503 CUDA, seven router profiles over three GGUFs, WebUI MCP
  registry, writing templates, units, benchmarks. Initial state.
