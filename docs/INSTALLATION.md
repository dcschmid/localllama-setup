# Installation

`./setup.sh` runs the phases in order, skips what already exists, and resumes
after any interruption (each phase re-validates before touching anything):

1. hardware detection + tested-range warnings (RAM/VRAM/threads/distro/arch)
2. dependency checks (curl jq python3 jq uv nvidia-smi socat bwrap pasta nft
   setpriv xdg-open node npm >= 22.19), driver probe
3. llama.cpp b12503 CUDA build unpack (archive cache, SHA-256 gate),
   CUDA0 verification via `--list-devices`
4. model gate: GGUFs must exist or come via `--download-models` (pinned
   revision, resumable, checksum before rename)
5. Node 24.22.1, github-mcp v2.2.0, mcp-proxy 0.15.0 venv, node MCP servers,
   websearch-mcp (all lockfile-pinned)
6. router/WebUI/MCP configs rendered from templates; managed-file drift aborts
7. systemd user units, KDE launcher, llama-webui
8. Pi 1.5.2 install (`npm install -g @earendil-works/pi-coding-agent@1.5.2`
   into `~/.local/opt/pi`), settings/auth/MCP rendered into `~/.pi/agent`
9. skills path registered natively (no copies)
10. docs refresh with drift backup; daemon-reload; services restart
11. summary distinguishes ok/skipped/failed/optional

Privileged changes are only the documented dnf line; setup itself is user
scope, no reboots, no sudo. A failed optional MCP stops that section, not the
coding path. Re-run any number of times: second run writes nothing
(`./setup.sh --dry-run` shows exactly this).
