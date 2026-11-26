# Performance

All values are measured, not assumed; raw series and methodology in
[PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) (historical
record) and [BENCHMARKS.md](BENCHMARKS.md).

Production (2026-11-25: `research-code` + `story`, both 26B-A4B MoE, RTX 5070
8 GiB, presets `research-code`/`story` in models.ini):

| Knob | Value | Evidence |
|---|---|---|
| batch/ubatch | 2048/64 | prefill buffers inside VRAM at 256K |
| expert placement | cpu-moe (experts in RAM) | MoE needs it to fit 8 GiB |
| K/V cache | q8_0 at 262144 | only viable stage: f32 KV OOMs at 256K (measured cudaMalloc failure); q4_0 rejected (hybrid-attention recall already geometry-limited, KV loss on top risks early positions) |
| fit | off | no silent context reduction |
| threads / batch-threads | 12/12 | 24 threads: -57 % decode (historical A/B) |
| prompt cache | 512 MiB | historical A/B, kept |
| mmap | on | equal to direct-io, keeps RAM shared |
| flash-attn | on | stable |
| MTP/speculative | off | compat+benefit unproven on b12628 (rule: stay off until measured) |
| THP / GLIBC_TUNABLES | off | A/B showed no gain |

Measured at full window (docs/results/*-256k*.json): prefill 93-97 t/s at
229-245K prompts, decode 30.1 (research-code) / 33.5 (story) t/s; VRAM ~6.2 GB
loaded incl. ~0.4-1.9 GB desktop reserve, RAM load 23-26 Gi, no swap thrash.
Fact recall is released to ~100K density, beyond that experimental (hybrid
attention geometry: 25/30 full layers, SWA 1024 - see
GEMMA4-256K-MIGRATION-REPORT.md).

Historical (trio era, retired weights): `coding-cyber-tiel-35b` decode 35-41
t/s near working context, ~17 t/s mid, 6.9 t/s cold at 256K; prefill 465-890
t/s; K/V Q4_0 at 64K+; 585-1063 t/s prefill at 2048/1024 research (Gemma 26B
QAT), ~37 t/s decode; StyleTune 512/256.

Experimental (kept OFF, documented): THP madvise tuning, expert cache,
24 threads, Performance power profile. (cpu-moe moved into production with the
two-model rollout.) Optional/experimental flags are never default-on.
Kernel-level changes are out of scope.

## Pi harness measurements

The Pi task benchmark uses a fresh MetalVault copy with an independent
regression check. The shared router can serve another WebUI request
between Pi turns. Treat restarts and overlapping requests as interference
and retain the first request's actual cache counters. The generated
context benchmark records compaction and continuation separately.
[Method and results](BENCHMARKS.md)
