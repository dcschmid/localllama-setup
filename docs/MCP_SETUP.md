# MCP setup

Shared services, used by the WebUI (ui.json) and by Pi (mcp.json):

| Service | Endpoint | Tools | Notes |
|---|---|---|---|
| websearch-mcp | 127.0.0.1:8642/mcp | search_web, read_url, deep_research, deep_research_status | own netns, research profile for synthesis |
| gateway (mcp-proxy 0.15.0) | 127.0.0.1:8643/servers/<name>/mcp | context7: resolve-library-id, query-docs; github: 4 read-only tools; skills: fs read-only | stdio adapters from mcp.json |

Checks performed by `./setup.sh test`: `/healthz` and `/status` respond, tool
discovery counts (4/2/4), the WebUI list renders four entries, Pi calls a real
tool end-to-end. Playwright and Blender MCP are optional and never installed
unasked; media MCPs (image/audio) are excluded - those projects are separate.

Credentials: github token is resolved at runtime through `gh auth token`
inside the gateway wrapper; nothing is stored in git, logs, or configs.
After a reboot the units are static: start via `llama-webui` or
`systemctl --user start llama-cpp.service`. Pi keeps sessions in
`~/.pi/agent/sessions`; resuming reloads MCP lazily (`/mcp` shows state).
