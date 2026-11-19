# Pi extensions and tooling decisions

Pinned in `config/pi-manifest.json`; installed only by `setup.sh` (no
automatic updates, no unchecked community packages). Decision matrix as
tested 2026-11-19 on Pi 1.5.2 + Cyber-Tiel-Coder 35B A3B (coding-long-256k).

| Package | Version | Compatible | Safe | Benefit | Overhead | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| pi-lens | 4.5.1 | yes (node>=22.19) | MIT, no postinstall | code intelligence (LSP diagnostics, symbol search) | +7K ctx schema, +11 s on small tasks | active |
| pi-permission-modes | 2.7.2 | yes | MIT, echo postinstall | read-only/plan gates for an abliterated model | minimal | active |
| pi-workspace-history | 0.5.2 | yes | MIT, no deps churn | /undo checkpoints next to git | minimal | active |
| pi-todo-agent | 0.3.0 | yes | MIT, zero deps | visible task lists for big jobs | minimal | active |
| pi-condense | 2.18.1 | yes | MIT, zero deps | tool-output pruning in long sessions | extra summarizer calls | experimental-off |
| pi-sessions | 0.23.4 | node>=24 vs pinned 22 | MIT | session search | n/a | excluded |

Rules: one extension is accepted only if it is safe to run, demonstrably
works, never calls cloud models, and does not duplicate a native Pi or skill
feature. Security features are judged by protection value, not speed.
Experimental stays off until real-task proof exists.

## Measured context cost (3-turn long-read A/B, 400-line fixture)

| Config | Wall | Peak ctx | Correct |
| --- | --- | --- | --- |
| native baseline | 49 s | 9 826 | yes |
| full active set | 50 s | 16 951 | yes |

Wall time is equal; tool schemas cost ~7K tokens of context. That is fine at
262K capacity but keeps the rule: 256K is capacity, not a goal.

## LSP/linters (host-provided, not Pi packages)

typescript-language-server, pyright, ruff, shellcheck, rust-analyzer
(npm/pip globals). shfmt needs sudo (dnf) and is reported as missing by
doctor, not required. Godot and Lua tooling stay project-local.

## Native Pi features used instead of packages

compaction (enabled, reserve 39322/keep 20000), prompt templates
(`config/prompts/` -> installed to `~/.pi/agent/prompts/`), skill discovery
(read-only skillset), llama.cpp provider, MCP via gateway. Codemode arrives
with pi-lens; read-heavy use only, no parallel LLM fanout.
