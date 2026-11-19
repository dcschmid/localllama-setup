# Shared skills

`~/dev/github/skillset/skills` is the single source of truth (override with
`LLAMA_SETUP_SKILLS`). 27 skills, validated collision-free frontmatter,
Agent-Skills compatible.

- Pi registers the directory natively: discovery lists name+description only,
  `SKILL.md` loads on demand, `/skill:name` forces, arguments after the
  command append as a request. Scripts and references resolve relative to the
  skill directory; Pi announces the directory to the model.
- WebUI access stays read-only through the skills filesystem MCP (10 tools)
  via the gateway; writing profiles render the Human-Writing skill into the
  system context at service start (`render.py` builds the jinja cache and
  swaps it atomically; a render error leaves the last good cache active -
  check `journalctl --user -u llama-cpp.service`).
- No copies, no skill database, no filesystem-MCP-only fallback for Pi.
- Project `AGENTS.md` files are honoured by Pi from the working folder; the
  skill collection itself is never modified by setup.
- Missing skills dir: setup disables only the skills MCP entry (WebUI list
  drops to three), Pi registers the path when it appears; rerun `./setup.sh`
  or reload after adding the collection.
