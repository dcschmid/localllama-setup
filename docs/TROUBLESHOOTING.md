# Troubleshooting

Start with `./setup.sh doctor`, then the targeted checks:

- **Router down / model stuck loading**: `systemctl --user status
  llama-cpp.service`, `journalctl --user -u llama-cpp.service -n 80`.
  nvidia-smi distinguishes VRAM, RAM, and template errors. A model switch
  can take minutes (unload + load); `/props?model=` may block meanwhile.
- **WebUI shows no MCP entries**: entries live in `ui.json`; check
  `curl -fsS 127.0.0.1:8080/props | jq .ui_settings.mcpServers`. The
  "Add your first MCP server" text is the browser-side list, not the
  server registration.
- **Pi: "No models available"**: llama.cpp provider comes from
  `~/.pi/agent/auth.json` (`llama.cpp.env.LLAMA_BASE_URL`). A fresh Pi
  install needs one TUI `/login llama.cpp` if auth.json was deleted; then
  `coding-long-256k` appears in `/model`.
- **Pi: sandbox bash spawn EACCES**: bwrap bind order changed or
  `--ro-bind / /` shadowed /dev - use the repo `libexec/pi-sandbox`.
- **setup aborts "existing file differs"**: intended protection. Compare,
  back up, or point at the backup; do not delete blindly.
- **writing render failure**: `journalctl --user -u llama-cpp.service -n 60`;
  render.py only swaps the cache after all sources read.
- **Firefox HTTP 415 on the WebUI font**: cosmetic; chat/uploads work.
- **Gateway/websearch**: `curl 127.0.0.1:8643/status`,
  `curl 127.0.0.1:8642/healthz`; restart
  `systemctl --user restart llama-cpp-mcp llama-cpp-research`.
- **Interrupted model download**: `*.partial` resumes on the next run; a
  hash mismatch keeps the partial for inspection - save it before retry.
