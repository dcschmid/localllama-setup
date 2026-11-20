# Benchmarks

The [evaluation](../docs/MODEL_BENCHMARKS.md) documents the hardware, model choices, test conditions, and limits of the original measurement series of 18 November 2026.

| Files in [results/](results/) | Content |
|---|---|
| `bench-*.json`, `*.stderr`, `*.csv` | Official `llama-bench`, time and peak RSS from GNU time, device values from `nvidia-smi` |
| `context-*.jsonl` | Repository-like test prompts, prompt and decode rates, latency, cache reuse, and retrieval |
| `qa-real-repo.json`, `qa-slot-final.jsonl` | Metrics of the 100K source-code test and the test of saving and loading a slot |
| `qa-*-tools.json`, `coding-*.time` | Tool success status and runtime of the separate coding tasks |
| `human-writing-ab.json` | Nine paired writing tasks with identical prompts, text outputs, timing, and linter findings |
| `media-mcp.json` | Three Atelier PNGs with seeds, runtimes, and transport, plus technical WAV analysis for six GAF tasks |
| `final-cleanup.json` | Cyber-Tiel acceptance with the two local CLI clients plus the new research, tool, and writing checks |
| `advanced-performance.json` | New baseline, A/B comparisons, cache counters, and process and GPU measurements |
| `follow-up.json` | Full 256K cold/warm run, deep-research synthesis, four writing scenes, and separate fact checking |

Absolute local home paths were normalized. Of the real repository test, only status and measurements are included. The original full agent traces remain on the laptop.

## Repeat the short benchmark

The GPU should have enough free VRAM. Finish a running chat and, if needed, stop the llama.cpp user service before the direct benchmark. The measurements for large models temporarily used the Fedora performance profile. When comparing, record the energy profile, GPU utilization, model, and parameters.

```bash
mkdir -p "$HOME/llama-bench-neu"
./benchmarks/run.sh "$HOME/llama-bench-neu/cyber-tiel" \
  "$HOME/models/gguf/Cyber-Tiel-Coder-35B-A3B.APEX-I-MiniPlus-V2.1.gguf" -p 8192,16384 -n 128 -r 2
```

The `-p` option measures prefill and `-n` measures decode separately. For decode after a filled context, use the router test. The script leaves existing output files untouched.

## Repeat the long-context test

Start the router for this. The test loads the selected profile and occupies its single model slot. The input consists of generated Python source code with three known facts. `--reuse-prefix` additionally checks reused prompt tokens across consecutive runs.

```bash
mkdir -p "$HOME/llama-bench-neu"
set -o pipefail
python3 benchmarks/bench-context.py coding-long-256k 8192 16384 32768 65536 131072 196608 253952 \
  --structured --reuse-prefix --fixed-prefix-modules 20 | tee "$HOME/llama-bench-neu/context-256k.jsonl"
```

The retrieval column checks whether three expected values appear in the answer. For coding quality, the real repository test, the two agent tasks, and their unit tests also count.

`--cache-prompt` activates server-side reuse when the position of the searched facts stays the same. For a cold/warm comparison, load the profile fresh and repeat exactly the same input.

```bash
python3 benchmarks/bench-context.py coding-long-256k 253952 --structured --repeat 2 --cache-prompt
```

The three 8K baselines use the same call without `--reuse-prefix` and with exactly one target value. Wait for each call to finish before the router switches to the next model.

```bash
for profile in coding-long-256k research creative-writing; do
  python3 benchmarks/bench-context.py "$profile" 8192 --structured
done
```

## Repeat the temporary router comparisons

The production router must have no loaded models during the comparison. Wait for running chats and research jobs to finish and unload the current model in the model menu. The benchmark starts a temporary user service on `127.0.0.1:18083` and stops it after the test. The test run aborts if the production router loads a model again.

```bash
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" thp-a1 coding-long-256k A prefix,48
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" thp-b1 coding-long-256k B prefix,48
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" cache-2048 coding-long-256k A branch,104 cache-ram=2048 verbosity=6
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" cold256 coding-long-256k A context,253952
```

`A` takes over the glibc environment of the production router. `B` additionally sets `glibc.malloc.hugetlb=1` and takes over the remaining tunables. To reproduce an earlier baseline configuration, set `LLAMA_PERF_PRESETS` to the saved `models.ini`. Use a separate ID per run. The JSONL files contain response quality, cache tokens, latency, and process data. `gpu.csv` contains the device values measured over the entire case. [Evaluation and rollback](../docs/PERFORMANCE_OPTIMIZATION.md)
