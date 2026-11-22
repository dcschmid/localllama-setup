# Changelog
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
