# Pi Coding Agent

Pi is the only local coding agent in this stack. Claude Code and Codex stay
native cloud tools; `claude-local` and `codex-local` no longer exist.
Research and story writing remain in the llama.cpp WebUI.

## Installation

- Pi 1.5.2 (stable), official installer or `npm install -g
  @earendil-works/pi-coding-agent@1.5.2` through the setup script.
- Managed prefix: `~/.local/opt/pi`, launcher `~/.local/bin/pi`.
- Configuration: `~/.pi/agent/` (`settings.json`, `auth.json`, `mcp.json`),
  independent from any other agent profile.
- Requires Node.js >= 22.19 (setup installs Node 24.22.1 if absent).

## Model and router

- Built-in llama.cpp provider, wired in `auth.json`
  (`llama.cpp` -> `http://127.0.0.1:8080`). No cloud fallback.
- Default model `coding-long-256k` = Cyber-Tiel-Coder-35B A3B APEX-I MiniPlus
  V2.1, 262,144 context, 8,192 output, CUDA, mmap, flash attention, Q4_0 K/V,
  2048/1024 batch, one slot, MTP off, prompt cache 512 MiB, 32 context
  checkpoints.
- Pi reads context and output limits from `/props`; compaction and tool calls
  reuse the same model, no secondary model.

## Compaction

```json
"compaction": { "enabled": true, "reserveTokens": 39322, "keepRecentTokens": 20000 }
```

About 85 % of 262,144. Manual: `/compact`. Compared 65/75/85 % and 16k/20k/32k
keepRecent on this hardware: prefill dominates for 35B-A3B on 8 GiB VRAM,
smaller thresholds only shift the switch point without time savings. 39322/20000
stays the production value; deeper cuts pay off only with more VRAM.

## Skills

`~/dev/github/skillset/skills` is registered directly as a Pi skill path (27
skills, no copies, no skill database). Discovery validates every `SKILL.md`;
names and descriptions are collision-free; the central collection remains the
single source of truth. The model loads a skill's `SKILL.md` on demand;
`/skill:name` forces it.

## MCP (native, mcp.json)

| Server | Endpoint | Tools |
|---|---|---|
| `websearch` | `http://127.0.0.1:8642/mcp` | `search_web`, `read_url`, `deep_research`, `deep_research_status` |
| `context7` | `http://127.0.0.1:8643/servers/context7/mcp` | `resolve-library-id`, `query-docs` |
| `github` | `http://127.0.0.1:8643/servers/github/mcp` | read-only: `get_file_contents`, `get_latest_release`, `list_releases`, `search_repositories` |

`codemode` exposure by default (deferred, search path instead of schema flood);
`/mcp` shows status. Playwright/Blender/media MCPs are not part of this profile.

## Usage

```bash
cd ~/dev/github/my-project
pi                    # starts on coding-long-256k, footer shows 262k (auto)
pi --continue         # last session of this folder
pi -r                 # pick a saved session
/model  /llama        # model and router status
/mcp                  # MCP status
/compact              # manual compaction
Escape / Ctrl+C       # interrupt running work
pi-sandbox            # sandbox mode (see Security)
```

The `llama.cpp` KDE launcher keeps the WebUI (research/writing) independent of Pi.

## Security

`pi-sandbox` (bwrap): writable = project directory + Pi agent state, skills
read-only, SSH/AWS hidden behind tmpfs, no sudo, no auto pushes; loopback to
router and MCP stays. Without the sandbox the regular Pi rights apply inside
the project. The router never downloads models (`--offline`) and WebUI rights
are unchanged.

## Performance (inherited measurements)

Production profile `coding-long-256k` with values validated in
PERFORMANCE_OPTIMIZATION.md: 2048/1024 batch, 1024 MiB CUDA reserve, auto-fit,
12/12 threads (24 threads: -57 % decode), THP off, energy profile unchanged,
prompt cache 512 MiB, checkpoints 32/8192.
Agent measurements: ledger bugfix 39.6 s total (2/2 independent tests green,
context marker preserved); multi-domain fixture TS/Lua/GDScript/Security 163 s
(8/8 pytest green); long-context retrieval 3/3 markers over 60k words;
session resume persists. Decode: 35-41 t/s near working context (target met),
6.9 t/s cold at full 256K; the 20-30 t/s goal holds for short working
contexts, long contexts stay slower because prefill dominates.
Cache hits: 261,684/261,688 tokens on warm repeat.

## Rollback

Delete `~/.pi/agent/`, rerun `pi update` or the installer. Wrapper recovery
(claude-local/codex-local + llama-local-agent + configs) from
`~/.local/share/llama-cpp-backup/20261119-184809/`.

## Known limits

- `/llama` downloads use the router download path; the router runtime stays
  `--offline`, loading existing aliases works, HF downloads remain reserved for
  the WebUI/maintenance path.
- The router loads one model at a time; coding and research alternate as before.
- Compaction summaries are model text; keep critical project decisions in
  files (AGENTS.md, notes) as well.
