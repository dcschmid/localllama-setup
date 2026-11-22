# Architecture

Three models, one router, one agent. Everything runs as user services on
loopback; no platform installs, no cloud fallback.

```
                 llama.cpp b12628 router  127.0.0.1:8080 + $XDG_RUNTIME_DIR/llama-cpp/server.sock
                 one model loaded, autoload off, --offline, preset models.ini
                 profiles: research | deep-research | coding-cyber-tiel-35b | 4 writing
                      ^                                   ^
                      | llama.cpp provider                | native Llama Chat (WebUI)
                 Pi 1.5.2  (~/.local/opt/pi, cfg ~/.pi/agent)
                 default coding-cyber-tiel-35b, skills from shared collection
                 sandbox: pi-sandbox (bwrap)
                      |
   MCP: websearch :8642  +  gateway :8643 (context7, github, skills-fs)
        used by both Pi (mcp.json, codemode) and the WebUI (ui.json)
```

- systemd user units: `llama-cpp`, `llama-cpp-research`, `llama-cpp-mcp`
  (static; start on demand via `llama-webui`).
- Model weights in `~/models/gguf`, pinned in `packages/models.tsv` with
  SHA-256; never in git.
- Configs in `~/.config/llama.cpp` (router/webui/writing) and `~/.pi/agent`
  (Pi settings/auth/MCP) are rendered from `config/*.in` templates; managed
  files that differ abort the run instead of overwriting edits.
- Node 24.22.1 and the github MCP binary live under `~/.local/opt/llama.cpp`;
  Pi lives under `~/.local/opt/pi`. Cloud Claude/Codex are untouched.
