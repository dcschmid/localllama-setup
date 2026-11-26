# Models

Exactly two GGUF files, pinned by revision and SHA-256 in
`packages/models.tsv`. Downloads only happen with `--download-models`, resume
via `.partial`, verify before rename, and never replace a valid local file.
No automatic upgrade to newer revisions.

| Display | Role | HF repo / revision | File | Quant | Ctx | Tools |
|---|---|---|---|---|---|---|
| Gemma 4 26B A4B QAT HauhauCS Balanced | research & analysis (research-code) | HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP @ f9093662 | Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf | Q4_K_M QAT | 262,144 | yes |
| UltimateIntent Gemory 26B A4B | creative writing DE/EN (story) | UltimateIntent/Gemory-26B-A4B-GGUF @ a8bb79d6 | Gemory-26B-A4B-Q4_K_M.gguf | Q4_K_M | 262,144 | no |

Licenses: `gemma` repo tag on the HauhauCS quant (Apache-2.0 Gemma-4 base;
open commercial-documentation case, local use OK — `docs/MODEL-LICENSES.md`),
apache-2.0 on Gemory. Chat templates: native jinja for both; writing profiles
render the Human-Writing skill through `~/.config/llama.cpp/writing/render.py`
at service start.

Router profiles run at the native 262144 ceiling across the board (2026-11-25;
former 32K/16K caps and the trio-era profiles retired — the auto-fit placement
is disabled (`fit off`), MoE experts sit in RAM (`cpu-moe`), KV is q8_0 at the
full window, which keeps the RTX 5070 inside its headroom): `research-code`
(`research`, `deep-research` + legacy coding aliases) and `story`
(`creative-writing`, `human-writing`, `human-rewrite`, `human-audit`). No
productive profile below 256K exists or may be added; benchmark workloads
below that length run inside the 256K slot.

Coding is out of the local production scope: Claude and yolo-auto own
software development. Coding-role aliases resolve to `research-code` only so
Pi and older clients keep answering; they are not offered as productive roles
in the WebUI.

Retired weights (rollback inventory, delete only after the 256K acceptance
passes for both live models — see `docs/MODEL-CLEANUP-MANIFEST.md`): the
pre-migration research/story/coding GGUFs.

Updating a model is deliberate: change the row in `packages/models.tsv`
(repo, revision, size, sha256), run `./setup.sh`, which downloads with the
gate and reloads the router. Pi and the WebUI pick up aliases automatically.
