# Context engineering (Cyber-Tiel 35B-A3B, 256K profile)

Productive profile: `coding-long-256k` — 262 144 ctx, 8 192 max output,
one model slot, CUDA + mmap + flash-attn + prompt cache (tested values in
PERFORMANCE.md; do not change without measuring).

## Budgets (settings.json via config/pi.json.in)

- compaction: enabled, `reserveTokens 39322` (~15 % headroom for output +
  tool calls), `keepRecentTokens 20000` — the tested 85 %-trigger baseline.
- 65/75/85 % comparison stays open; 85 % is productive until a real task
  shows late-context degradation.
- Output tokens are reserved for summaries and tool-call rounds too — a
  compaction request must fit 8 192 out plus keep-recent.

## Measured (2026-11-19, 3-turn fixture over 400-line log)

| Set | wall | peak ctx | result |
| --- | --- | --- | --- |
| native | 49 s | 9 826 | correct |
| +4 active extensions | 50 s | 16 951 | correct |

Schema cost is ~7K tokens and constant per turn; prompt cache absorbed the
rest (cacheRead ~55-67K of ~11K fresh input per run).

## Rules that keep the footprint small

- 256K is capacity, not a target; tasks stay small on purpose.
- Skills load relevant instructions only (skill descriptions, never the
  full collection); AGENTS.md per project, no giant global prompts.
- MCP: 3 servers via gateway, read-only; tool discovery lazy where the
  server supports it; no media MCPs.
- Shell outputs are capped by the harness; unchanged files are not re-read.
- One LLM at a time, no parallel subagents, no embeddings, no cloud
  fallbacks — compaction and summaries run on Cyber-Tiel locally.
- pi-condense stays opt-in for long sessions; short sessions do not pay
  summarizer calls.
