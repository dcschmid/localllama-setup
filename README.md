# localllma-setup

Reproducible one-click installation of the local AI stack on a Framework
Laptop 16 (Fedora KDE). One command installs, validates, and repairs the
router, three models, the WebUI, the Pi coding agent, MCP services, skills,
and the tested performance settings. The repository is the source of truth;
repeated runs are idempotent and resumable.

## Architecture

```
llama.cpp b12628 (official CUDA build)         127.0.0.1:8080  +  unix socket
  router, one model at a time, autoload off
  profiles: research-code (research-code + aliases) \| story (story + writing aliases)
  WebUI (Llama Chat, native)                     same port
Pi 1.5.2 (coding agent)  ── llama.cpp provider ──► router
  default model research-code (HauhauCS Balanced), 262K ctx, 8K out
  skills: ~/dev/github/skillset/skills (native discovery, shared)
  pi-sandbox (bwrap): project write, skills read, no credentials
MCP: websearch+deep research :8642 ─┐
     gateway :8643 (context7, github, skills-fs) ─┘ shared by WebUI and Pi
systemd user units: llama-cpp, llama-cpp-research, llama-cpp-mcp
```

Claude Code and Codex stay untouched cloud tools. The stack installs nothing
cloud-side and starts no extra inference platform.

## Hardware

Tested: Framework Laptop 16, Ryzen AI 9 HX 370 (12c/24t), RTX 5070 Laptop 8
GiB, 64 GiB RAM, NVMe, Fedora 44 KDE, NVIDIA driver 615.78.08, CUDA 12.8
build. Detection warns when RAM < 32 GiB, VRAM < 6 GiB, or CPU threads < 12;
outside that range profiles are unverified and nothing is auto-guessed.

## One-click install

```bash
sudo dnf install curl jq python3 socat bubblewrap passt nftables util-linux xdg-utils tar xz time nodejs npm
# uv is required for the pinned MCP gateway: pip/uv itself or dnf install uv
cd ~/dev/github/localllma-setup
./setup.sh                      # first run installs everything missing
./setup.sh --download-models    # only if GGUF backups are absent (37.1 GB)
```

Missing GGUFs, CUDA libs, or archives fail with a hint instead of silent
redownload. Reboots are never automatic. Privileged steps are the dnf line
above only; everything else runs as the user.

## Commands

| Command | Purpose |
|---|---|
| `./setup.sh` / `install` | full setup, repeatable, resumes after interruption |
| `./setup.sh update` | reinstall drift + pinned `pi update` (models never move) |
| `./setup.sh repair` | recreate links/units/config from the repo |
| `./setup.sh doctor` | hardware, services, router, WebUI, Pi, MCP, skills, sandbox |
| `./setup.sh status` | one-screen state |
| `./setup.sh test` | acceptance incl. a real Pi inference roundtrip |
| `./setup.sh benchmark` | reproducible benches in `benchmarks/` |
| `./setup.sh backup` / `restore [file]` | versioned config backups, validated restore |
| `./setup.sh uninstall` | managed files only; models/user data need `--remove-models` |
| `--dry-run` | validate everywhere, write nothing |

## Model library (exactly two, no extras)

| Model | Role | File | License |
|---|---|---|---|
| Gemma 4 26B-A4B QAT HauhauCS Balanced Q4_K_M | coding, agents, research (research-code) | `Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf` | gemma (Basis Apache-2.0, siehe docs/MODEL-LICENSES.md) |
| UltimateIntent Gemory 26B-A4B Q4_K_M | story, articles, human writing (story) | `Gemory-26B-A4B-Q4_K_M.gguf` | apache-2.0 |

Manifest with repo, revision, byte size, SHA-256, context, and profiles:
`packages/models.tsv`. Revisions are pinned; updates are manual and go through
the same checksum gate. GGUFs never live in git.

## Pi as the coding agent

`cd ~/dev/github/my-project && pi` starts Cyber-Tiel through the router,
262,144 context / 8,192 output, compaction `39322/20000` (≈85 %), shared
skills, MCP via codemode, sessions in `~/.pi/agent/sessions`. No cloud
fallback, no other harnesses. Pinned extension set, prompt templates
(`/finish`, `/review`, `/fix-ci`, `/finish-docs`) and context budgets:
[docs/PI_EXTENSIONS.md](docs/PI_EXTENSIONS.md),
[docs/PI_COMMANDS.md](docs/PI_COMMANDS.md),
[docs/CONTEXT_ENGINEERING.md](docs/CONTEXT_ENGINEERING.md),
[docs/PI_CODING_AGENT.md](docs/PI_CODING_AGENT.md).

[Coding candidates](docs/CODING_CANDIDATES.md) ·
## WebUI, MCP, skills

WebUI is the server-native Llama Chat on :8080 with four MCP entries (websearch,
context7, github, skills-fs read-only); media MCPs are excluded by design.
Skills are read from the shared collection at runtime — no copies, no
database. Writing profiles render the Human-Writing skill into the system
context via `config/writing/render.py`.

## Local Creative Studio (optional, opt-in)

`./setup.sh creative-studio install` puts a writing/research/image/GDD studio
on `127.0.0.1:8700` (Astro UI + stdlib backend, `libexec/llama-creative-studio`)
on top of the existing router, image service and skills — separate UI, never a
replacement for :8080, Pi or the coding profiles. Single GPU queue: image jobs
wait for a real VRAM slot, LLM calls serialize through the router, jobs and
documents persist in `~/.local/share/creative-studio` (backup/restore/uninstall
keep data unless `--purge-data`). Lifecycle and gates:
`./setup.sh creative-studio {update|status|doctor|test|backup|restore|uninstall}`,
details in `docs/creative-studio/README.md`. Base install stays fully functional
without it.

## Performance

Production values come from measured series, not defaults: 2048/1024 batch,
1024 MiB CUDA reserve, 12/12 threads, Q4_0 K/V at 64K+, 512 MiB prompt cache,
32 checkpoints at 8192 spacing, THP off, MTP off. See
[docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md) and
[docs/MODEL_BENCHMARKS.md](docs/MODEL_BENCHMARKS.md).

## Security

User units, loopback binding, 0700 runtime dirs, `--offline` router,
bwrap project sandbox for Pi (project write, skills read, credentials
hidden, no sudo, no auto push). Pi starts in Build mode: autonomous inside
the project, sandbox and credential masks stay on, pushes and destructive
git prompt. Secrets (gh token via `gh auth token` at runtime, HF tokens)
never enter git, logs, or generated configs.

## Operations

- Start after login: `systemctl --user start llama-cpp.service` (units are static).
- `~/.local/bin/llama-webui` starts everything and opens the browser.
- Docs drift: managed docs in `~/.config/llama.cpp` refresh on install with a
  one-time backup in `~/.local/state/localllma-setup/doc-backup/`.
- Troubleshooting: `./setup.sh doctor`, then
  `journalctl --user -u llama-cpp.service -n 80`.

## Backup & recovery

`./setup.sh backup` writes timestamped archives under
`~/.local/state/localllma-setup/backups/`. Models are recovered from your own
GGUF backup or `--download-models` (pinned revisions). Full history of
historical benchmarks incl. retired models: `benchmarks/results/`.

## License

Setup code and configs: MIT. Model weights keep the licenses listed in the
manifest.
