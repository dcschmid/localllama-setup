# Installation

`./setup.sh` runs the phases in order, skips what already exists, and resumes
after any interruption (each phase re-validates before touching anything):

1. hardware detection + tested-range warnings (RAM/VRAM/threads/distro/arch)
2. dependency checks (curl jq python3 jq uv nvidia-smi socat bwrap pasta nft
   setpriv xdg-open node npm >= 22.19), driver probe
3. llama.cpp b12628 CUDA build unpack (archive cache, SHA-256 gate),
   CUDA0 verification via `--list-devices`
4. model gate: GGUFs must exist or come via `--download-models` (pinned
   revision, resumable, checksum before rename)
5. Node 24.22.1, github-mcp v2.2.0, mcp-proxy 0.15.0 venv, node MCP servers,
   websearch-mcp (all lockfile-pinned)
6. router/WebUI/MCP configs rendered from templates; managed-file drift aborts
7. systemd user units, KDE launcher, llama-webui
8. Install Pi 1.5.2 and the default extensions from the npm lockfile with
   lifecycle scripts disabled. Link the sandbox launcher to the installed release.
9. skills path registered natively (no copies)
10. Refresh managed docs with a backup, reload user units and start the services.
11. summary distinguishes ok/skipped/failed/optional

Privileged changes are only the documented dnf line; setup itself is user
scope. Run `./setup.sh --dry-run` to validate the local prerequisites and
see the planned work. Use `./setup.sh install --pi-only` to install Pi without
restarting the router or touching the models. [Pi guide](PI_CODING_AGENT.md)
