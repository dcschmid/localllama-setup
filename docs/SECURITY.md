# Security

- All services: unprivileged user units, loopback-only, UMask 0077, runtime
  dir 0700, router `--offline` (no downloads at runtime), unit-level
  `UnsetEnvironment` strips provider tokens before llama.cpp starts.
- Pi sandbox (`pi-sandbox`, bwrap): writable = current project + Pi agent
  state; skills read-only; SSH/AWS hidden behind tmpfs; PID namespace; host
  filesystem read-only; loopback kept for router/MCP; no sudo, no automatic
  pushes, no destructive git defaults.
- Gateway enforces browser origin and host header; websearch keeps its own
  network namespace and filter rules; github MCP read-only.
- Offline coding works without internet; research and dependency downloads
  happen only through the explicit controlled setup paths.
- Secrets live outside the repo: gh token via `gh auth token` at runtime, HF
  tokens from the usual caches, Pi credentials local-only. Example files:
  `.env.example` is not needed because no config expects dotenv; all template
  variables are paths, never secrets.
- Employer data: the sandbox default keeps Pi inside the opened project;
  anything outside is read-only at best and credentials stay hidden.

Verified with the ledger and security fixtures in acceptance: missing tenant
principal -> 401, unknown tenant -> 404, missing key -> 200 [] instead of
KeyError; sandbox write tests showed project-write/skills-read/SSH-hidden.
