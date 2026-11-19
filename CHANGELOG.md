# Changelog

## 2026.11-pi-ext - Pi extensions, templates, context record

- manifest config/pi-manifest.json: pi-lens 4.5.1, pi-permission-modes 2.7.2,

- manifest config/pi-manifest.json: pi-lens 4.5.1, pi-permission-modes 2.7.2,
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
