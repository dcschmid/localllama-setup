# Coding Model Candidates

Opt-in evaluation track for the six local coding candidates behind the Pi
comparison (Astro, TypeScript, KILN). Nothing here runs during the default
one-click install; the candidates live beside the production profiles and can
be removed on their own.

## Models and pinned files

| Preset id (Pi) | Model | GGUF | Revision | Size | License |
|---|---|---|---|---|---|
| `candidate-k2-horizon` | K2 Horizon 7B | `K2-Horizon-7B-Q4_K_M.gguf` | `7a75dbda` | 5.59 GB | apache-2.0 |
| `candidate-mellum` | Mellum 2.1 12B A2.5B Thinking | `Mellum2.1-12B-A2.5B-Thinking-Q4_K_M.gguf` | `4159d684` | 8.07 GB | apache-2.0 |
| `candidate-lfm8` | LFM2.5 8B A1B | `LFM2.5-8B-A1B-Q4_K_M.gguf` | `49c14831` | 5.16 GB | LFM Open 1.0 |
| `candidate-lfm24` | LFM2.5 24B A2B | `LFM2.5-24B-A2B-Q4_K_M.gguf` | `d790f111` | 14.53 GB | LFM Open 1.0 |
| `candidate-ornith` | Ornith 1.5 9B | `Ornith-1.5-9B-Q4_K_M.gguf` | `abdd624b` | 5.78 GB | MIT |
| `candidate-kat` | KAT-Coder V2.5 Dev 35B A3B | `Kwaipilot_KAT-Coder-V2.5-Dev-Q4_K_M.gguf` | `d8f684f0` | 21.39 GB | apache-2.0 |

Pinned revisions, byte sizes and SHA-256 digests live in
`packages/models-coding-candidates.tsv` (resolved from the Hugging Face API on
2026-11-21, verified against the downloaded files). Total download: 60.5 GB;
the installer demands an extra 4 GiB headroom. Files are shared from
`~/models/gguf` with the production models - one archive, no second cache.

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

## Architecture support (llama.cpp b12503)

`libllama.so.1.0.0` (b12503, commit `4577932fa`) carries all five architectures;
no engine update was required: `k2-horizon`, `mellum`/`mellum2`, `lfm2`,
`lfm2moe`, `qwen35moe` (KAT-Coder is a Qwen3.5-MoE fine-tune; `mtp_num_hidden_layers=0`
upstream, MTP stays off).

## Preset configuration

All six presets run at the native 262144 tokens per evaluation brief, with
Q4_0 KV cache, batch 2048/1024, and the per-model sampler from the model card:

| Preset | Sampler (model card) | Output cap | Placement |
|---|---|---|---|
| `candidate-k2-horizon` | temp 1.0, top-p 0.95, `reasoning-effort = high` | 16384 | auto-fit GPU |
| `candidate-mellum` | temp 0.6, top-p 0.95, top-k 20 | 16384 | auto-fit GPU, `cpu-moe` |
| `candidate-lfm8` | temp 0.2, top-k 80, repeat 1.05 | 8192 | auto-fit GPU, `cpu-moe` |
| `candidate-lfm24` | temp 0.2, top-k 80, repeat 1.05 | 8192 | auto-fit GPU, `cpu-moe` |
| `candidate-ornith` | coding: temp 0.6, top-p 0.95, top-k 20, min-p 0 | 16384 | auto-fit GPU |
| `candidate-kat` | temp 1.0, top-p 0.95, top-k 20 | 16384 | auto-fit GPU, `cpu-moe` |

Notes:

- Measured 2026-11-21 (smoke suite, warm, one model at a time, router presets
  as configured; `nvidia-smi` peak during each model's run):

  | Preset | Prefill t/s | Decode t/s | VRAM MiB | Smoke A–F |
  |---|---:|---:|---:|---|
  | `candidate-k2-horizon` | 38.7 | 13.7 | 6510 | PASS |
  | `candidate-mellum` | 42.5 | 26.7 | 4854 | PASS |
  | `candidate-lfm8` | 72.6 | 52.1 | 4434 | PASS |
  | `candidate-lfm24` | 46.9 | 30.0 | 5196 | PASS |
  | `candidate-ornith` | 24.5 | 13.3 | 6430 | PASS |
  | `candidate-kat` | 45.8 | 28.7 | 6392 | PASS |

- K2 Horizon's card recommends >=32768 output tokens for full reasoning runs.
  16384 was chosen to fit the 8 GB GPU alongside the KV cache; full-card runs
  need a reduced context - documented deviation.
- `cpu-moe = true` keeps MoE experts on host RAM (measured LFM2.5 baseline:
  ~567/~67 t/s prefill/decode with 40 CPU expert layers, MODEL_BENCHMARKS.md).
- At 262144 tokens the KV cache cannot live fully on the 8 GB RTX 5070 for any
  candidate; the auto-fit placement from `[*]` (`fit-target = 1024`) keeps the
  GPU headroom and places KV plus oversized tensors in the 46 GiB host RAM.
  Measured VRAM and decode rates per model: see MODEL_BENCHMARKS.md (measured
  section). Full-GPU placement stays available for the small models at 8K/16K.

## Pi integration

`libexec/pi-router.py` allows exactly seven model ids (production
`coding-long-256k` plus the six candidates) with per-id context/output limits,
caps output per model, and forces one slot. `libexec/pi-sandbox` builds the Pi
model store with all seven entries and the six candidate ids in
`enabledModels`, so `/model` and `pi --model candidate-…` work in every sandbox
session. The default model stays `coding-long-256k` until explicitly switched.

```bash
pi --model candidate-k2-horizon      # fresh Pi session on one candidate
```

Model switching unloads the previous model through the router
(`--models-max 1`); sessions of other models are untouched.

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
