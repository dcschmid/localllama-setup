# Benchmarks

Machine-readable results: `benchmarks/results/` (json/jsonl/csv), methodology
`benchmarks/README.md`. `./setup.sh benchmark` reruns the reproducible series.
No GPU in CI, so CI never runs these; numbers below are local measurements
only.

Current stack (Pi, b12503, production profiles):

| Test | Result |
|---|---|
| ledger bugfix + dedup + tests + context marker | 39.6 s, 2/2 green, marker kept |
| multi-domain (TS/Lua/GDScript/security api) | 163 s, 8/8 pytest green |
| long-context 60k words markers | 3/3 incl. resume |
| session resume | ~6 s, state preserved |
| warm 256K repeat | 261,684/261,688 cached, TTFT 0.67 s |
| cold 256K prefill | 393.7 s TTFT, 6.89 t/s decode, 3/3 |

Historical (models no longer installed - LFM-24B variants, MTP sidecar,
pre-256K coding profiles): preserved in results, marked by file name prefix
(`bench-lfm*`, `context-cyber-mtp*`). The old coding-claude/coding-codex
timings belong to the removed wrappers and are history.

Ranges: short-context agentic 35-41 t/s; 64K ~18 t/s; 128K ~12 t/s; 192K
~9 t/s; full 256K ~7 t/s decode with 2048/1024. MCP tool roundtrips 12 ms -
2.7 s (measured medians). Writing profile quality trials in
human-writing-*.json.
