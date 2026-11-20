# Changelog

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
