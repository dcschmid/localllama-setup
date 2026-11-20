# Performance

All values are measured, not assumed; raw series and methodology in
[PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) (historical
record) and [BENCHMARKS.md](BENCHMARKS.md).

Production (`coding-long-256k`, Cyber-Tiel 35B-A3B, RTX 5070 8 GiB):

| Knob | Value | Evidence |
|---|---|---|
| batch/ubatch | 2048/1024 | -62 % first token at 9.4k prompt |
| CUDA reserve (fit-target) | 1024 MiB | stable with auto-placement |
| threads / batch-threads | 12/12 | 24 threads: -57 % decode |
| K/V cache | Q4_0 at 64K+ | fits 256K in 8 GiB with 512 MiB prompt cache |
| prompt cache | 512 MiB prod | 1024 tested better for branch return; kept 512 prod |
| context checkpoints | 32 @ 8192 spacing | neutral in tests, kept upstream default |
| mmap | on | equal to direct-io, keeps RAM shared |
| flash-attn | on | stable |
| THP / GLIBC_TUNABLES | off | A/B showed no gain, regressions possible |
| MTP | off | higher total time in tests |

Observed decode: 35-41 t/s near working context, ~17 t/s mid-context, 6.9 t/s
cold at full 256K; prefill 465-890 t/s. Warm repeat: 261,684/261,688 tokens
from cache (0.67 s to first token). 20-30 t/s is the honest short-context
band; long contexts are stability-first by physics on 8 GiB.

Research (Gemma 26B QAT): 585-1063 t/s prefill at 2048/1024, ~37 t/s decode.
StyleTune keeps 512/256 because every ubatch step cost decode rate.

Experimental (kept OFF, documented): THP madvise tuning, cpu-moe placement,
expert cache, 24 threads, Performance power profile. Optional/experimental
flags are never default-on. Kernel-level changes are out of scope.
