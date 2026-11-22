# Models

Exactly three GGUF files, pinned by revision and SHA-256 in
`packages/models.tsv`. Downloads only happen with `--download-models`, resume
via `.partial`, verify before rename, and never replace a valid local file.
No automatic upgrade to newer revisions.

| Display | Role | HF repo / revision | File | Quant | Ctx | Tools |
|---|---|---|---|---|---|---|
| Cyber-Tiel-Coder 35B A3B APEX-I MiniPlus V2.1 | coding via Pi | IsValorum/Cyber-Tiel-Coder-35B-A3B-APEX-I-MiniPlus-V2.1-GGUF @ eb8f29ae | Cyber-Tiel-Coder-35B-A3B.APEX-I-MiniPlus-V2.1.gguf | APEX-I mix | 262,144 | yes |
| Gemma 4 26B A4B QAT Q4_0 | research, deep research, coding test (`coding-research-26b`) | google/gemma-4-26B-A4B-it-qat-q4_0-gguf @ d1c082be | gemma-4-26B_q4_0-it.gguf | Q4_0 QAT | 262,144 | yes |
| Gemma 4 12B StyleTune Q4_K_M | story writer (dense exception) | mradermacher/Gemma-4-12B-StyleTune-GGUF @ fb2e8be6 | Gemma-4-12B-StyleTune.Q4_K_M.gguf | Q4_K_M | 262,144 | no |

Licenses: MIT (Cyber-Tiel), apache-2.0 (both Gemma). Chat templates: native
jinja for Gemma; writing profiles render the Human-Writing skill through
`config/writing/render.py` at service start.

Router profiles run at the native 262144 ceiling across the board (2026-11-22;
former 32K/16K caps retired - Gemma 4 states 256K for medium sizes, the
auto-fit placement keeps the RTX 5070 inside its headroom with Q4_0 KV):
`research`, `deep-research` (128 think tokens),
`coding-cyber-tiel-35b` (the only coding profile - no 32K/64K/128K/192K siblings;
those lengths only appear as benchmark workloads inside the 256K slot), and
`creative-writing`, `human-writing`, `human-rewrite`, `human-audit`.

Updating a model is deliberate: change the row in `packages/models.tsv`
(repo, revision, size, sha256), run `./setup.sh`, which downloads with the
gate and reloads the router. Pi and the WebUI pick up aliases automatically.
