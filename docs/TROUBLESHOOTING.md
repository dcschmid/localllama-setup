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
- **Pi reports no available model.** Run `./setup.sh doctor --pi-only`.
  The installed launch profile includes its local model catalog. Check the
  router service and verify `pi --list-models coding-cyber-tiel-35b` in a project.
- **A headless edit is blocked by Plan Mode.** Start the authorized job
  with `pi --perm build`. Check `/perm` when resuming an interactive session.
- **Pi cannot find the project or shared skills.** Use a project under your
  home, `/tmp` or `/var/tmp`. Set `LLAMA_SETUP_SKILLS` when the central
  skillset lives outside the default location.
- **Pi Lens omits language-server diagnostics.** Check the project's Pi
  trust and runner configuration. Prepare the language server and project
  dependencies outside the sandbox. Lens uses the installed tools made
  available to the managed launcher.
- **A dependency download fails in the sandbox.** Prepare the project's
  dependencies outside Pi, then run the build or tests in the sandbox.
- **An MCP tool is missing.** Start an explicit `pi --with-mcp` session and
  inspect `/mcp`. The relay permits lookup tools documented in the
  [Pi guide](PI_CODING_AGENT.md#mcp).
- **Pi starts from the wrong executable.** Run `type -a pi` and
  `./setup.sh doctor --pi-only`. A pre-existing regular-file launcher is
  preserved. Use `pi-sandbox` to start the managed release.
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
