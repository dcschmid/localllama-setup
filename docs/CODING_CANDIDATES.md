# Coding Model Candidates

Opt-in evaluation track for the four local coding candidates behind the Pi
comparison (Astro, TypeScript, KILN). Nothing here runs during the default
one-click install; the candidates live beside the production profiles and can
be removed on their own.

## Models and pinned files

| Preset id (Pi) | Model | GGUF | Revision | Size | License |
|---|---|---|---|---|---|
| `coding-phai-256k` | Phai-A1 35B A3B 1M (MTP) | `Phai-A1-35B-1M-MTP.MXFP4_MOE.gguf` | `a3c7b4d8` | 20.26 GB | apache-2.0 |
| `coding-mellum-12b` | Mellum 2.1 12B A2.5B Thinking | `Mellum2.1-12B-A2.5B-Thinking-Q4_K_M.gguf` | `4159d684` | 8.07 GB | apache-2.0 |
| `coding-lfm-24b` | LFM2.5 24B A2B | `LFM2.5-24B-A2B-Q4_K_M.gguf` | `d790f111` | 14.53 GB | LFM Open 1.0 |
| `coding-ornith-9b` | Ornith 1.5 9B | `Ornith-1.5-9B-Q4_K_M.gguf` | `abdd624b` | 5.78 GB | MIT |
| `coding-kat-35b` | KAT-Coder V2.5 Dev 35B A3B | `Kwaipilot_KAT-Coder-V2.5-Dev-Q4_K_M.gguf` | `d8f684f0` | 21.39 GB | apache-2.0 |

Pinned revisions, byte sizes and SHA-256 digests live in
`packages/models-coding-candidates.tsv` (resolved from the Hugging Face API on
2026-11-21, verified against the downloaded files). Total download: 49.8 GB;
the installer demands an extra 4 GiB headroom. Files are shared from
`~/models/gguf` with the production models - one archive, no second cache.

K2 Horizon 7B (`candidate-k2-horizon`) and LFM2.5 8B A1B (`candidate-lfm8`)
were dropped from the track on 2026-11-22; their presets, manifest rows and
allowlist entries are gone.

## Installation

```bash
./setup.sh install --coding-candidates      # idempotent: reuses valid files, resumes partial downloads
./setup.sh doctor                            # reports candidate files + preset registration
./uninstall.sh --remove-candidates           # removes only the candidate GGUFs (production stays)
```

The command syncs `config/models.ini.in` into `~/.config/llama.cpp/models.ini`
(previous copy kept under `~/.local/state/localllma-setup/backups/`), fetches
missing files with SHA-256 verification, and reloads the router preset list
while the service runs.

## Architecture support (llama.cpp b12628)

`libllama.so.1.0.0` (b12628, commit `8a97fa98a`) carries all four model
families: `mellum`/`mellum2`, `lfm2moe`, and `qwen35moe` for KAT-Coder,
Cyber-Tiel, and Phai-A1. The engine moved from b12503 to b12628 on 2026-11-22
for the MTP-capable Phai preset (`--spec-type draft-mtp`); MXFP4_MOE tensors
load on CUDA with `cpu-moe` placement. KAT-Coder has `mtp_num_hidden_layers=0`
upstream (MTP stays off there); Phai-A1 ships embedded MTP weights.

## Preset configuration

Each preset runs at the model's native context ceiling with Q4_0 KV cache,
batch 2048/1024, and the per-model sampler from the model card. qwen35moe
(KAT-Coder, Phai-A1, and production Cyber-Tiel-Coder) and Ornith-1.5 native run
262144; Mellum2.1 and LFM2.5-24B are 131072 by model card — running them at
262144 exceeded the trained length, so the presets now cap at the native value:

| Preset | Sampler (model card) | Output cap | Placement |
|---|---|---|---|
| `coding-phai-256k` | temp 1.0, top-p 0.95, top-k 20 | 8192 | auto-fit GPU, `cpu-moe` |
| `coding-mellum-12b` | temp 0.6, top-p 0.95, top-k 20 | 16384 | auto-fit GPU, `cpu-moe` |
| `coding-lfm-24b` | temp 0.2, top-k 80, repeat 1.05 | 8192 | auto-fit GPU, `cpu-moe` |
| `coding-ornith-9b` | coding: temp 0.6, top-p 0.95, top-k 20, min-p 0 | 16384 | auto-fit GPU |
| `coding-kat-35b` | temp 1.0, top-p 0.95, top-k 20 | 16384 | auto-fit GPU, `cpu-moe` |

Notes:

- Measured 2026-11-21 (smoke suite, warm, one model at a time, router presets
  as configured; `nvidia-smi` peak during each model's run):

  | Preset | Prefill t/s | Decode t/s | VRAM MiB | Smoke A–F |
  |---|---:|---:|---:|---|
  | `coding-phai-256k` | 28.9 (cold chat) | 24.2 (cold chat) | 5197 | PASS |
  | `coding-mellum-12b` | 42.5 | 26.7 | 4854 | PASS |
  | `coding-lfm-24b` | 46.9 | 30.0 | 5196 | PASS |
  | `coding-ornith-9b` | 24.5 | 13.3 | 6430 | PASS |
  | `coding-kat-35b` | 45.8 | 28.7 | 6392 | PASS |

- `cpu-moe = true` keeps MoE experts on host RAM (measured LFM2.5 baseline:
  ~567/~67 t/s prefill/decode with 40 CPU expert layers, MODEL_BENCHMARKS.md).
- At 262144 tokens the KV cache cannot live fully on the 8 GB RTX 5070 for any
  candidate; the auto-fit placement from `[*]` (`fit-target = 1024`) keeps the
  GPU headroom and places KV plus oversized tensors in the 46 GiB host RAM.
  Measured VRAM and decode rates per model: see MODEL_BENCHMARKS.md (measured
  section). Full-GPU placement stays available for the small models at 8K/16K.

## Pi integration

`libexec/pi-router.py` allows exactly six model ids (production
`coding-cyber-tiel-35b` plus the five candidates) with per-id context/output limits,
caps output per model, and forces one slot. `libexec/pi-sandbox` builds the Pi
model store with all six entries and the five candidate ids in
`enabledModels`, so `/model` and `pi --model coding-…` work in every sandbox
session. The default model stays `coding-cyber-tiel-35b` until explicitly switched.

```bash
pi --model coding-mellum-12b      # fresh Pi session on one candidate
```

Model switching unloads the previous model through the router
(`--models-max 1`); sessions of other models are untouched.

## Long-context ladder (coding-phai-256k, 2026-11-22, b12628)

`benchmarks/bench-context.py` (repository-shaped prompts, three facts to
recover), router preset as configured, raw JSON: `benchmarks/results/phai-a1-long-context.json`.

| Context | Input tok | Retrieval | Prefill t/s | Decode t/s | TTFT s | Wall s |
|---:|---:|---|---:|---:|---:|---:|
| 8.192 | 7.641 | 3/3 | 645,0 | 33,1 | 11,9 | 14,6 |
| 32.768 | 32.256 | 3/3 | 672,7 | 16,8 | 48,0 | 54,2 |
| 65.536 | 64.828 | 3/3 | 550,2 | 12,9 | 118,0 | 126,2 |
| 131.072 | 130.473 | 3/3 | 522,1 | 11,1 | 250,1 | 258,8 |
| 196.608 | 196.113 | 3/3 | 521,4 | 8,5 | 715,5 | 726,5 |
| 262.144 | 261.510 | 3/3 | 468,7 | 6,7 | 1084,6 | 1096,9 |

Retrieval stays exact through the full 256K preset; decode falls to 6,7 t/s
at the ceiling (KV + CPU-expert traffic), which is an interactive-session cost,
not a capacity limit. MTP A/B (same file, 16K ctx, n=512): draft-mtp 37,0 vs
plain 39,2 t/s — no gain at temp 1.0, MTP stays off. Native MoE expert-cache
flags do not exist in b12628 (work-package F BLOCKED upstream-side).

## MXFP4 experiment (Mellum)

`Mellum2.1-12B-A2.5B-Thinking-MXFP4_MOE.gguf` (~7 GB) stays unresolved and
undownloaded: Q4_K_M with `cpu-moe` already fits the GPU budget, and MXFP4
needs a CUDA-side comparison first. Decision gate and measurement go into
MODEL_BENCHMARKS.md before any download.

## Rollback

1. `./uninstall.sh --remove-candidates` deletes only the candidate GGUFs.
2. Restore the preset file from `~/.local/state/localllma-setup/backups/models.ini.*`
   or rerun `./setup.sh repair`; reload presets via
   `curl 'http://127.0.0.1:8080/models?reload=1'`.
3. Rebuild the Pi harness with `./setup.sh repair --pi-only`; the relay keeps
   working with the production model alone if the candidate ids are removed
   from `MODEL_MODELS` in `libexec/pi-router.py`.
