# Ultimate Pi Harness V2

Pi runs Cyber-Tiel-Coder on the local llama.cpp router through the
`coding-cyber-tiel-35b` profile. The managed launcher starts the official Pi
1.5.2 CLI in a Bubblewrap sandbox scoped to the current project. Pi sees a
262,144-token context and an 8,192-token output limit. The router uses a single
CUDA slot, Q4_0 K/V, 512 MiB of prompt cache and the existing context
checkpoints. MTP is off. [Performance settings](PERFORMANCE.md)

## Install and start

```bash
./setup.sh install --pi-only --dry-run
./setup.sh install --pi-only
./setup.sh doctor --pi-only
cd ~/dev/github/my-project
pi
```

The complete stack still uses `./setup.sh`. The Pi-only option leaves the
inference and WebUI services running and does not fetch models. It installs
the exact package graph in [the npm lockfile](../packages/pi/package-lock.json)
with lifecycle scripts disabled. The normal Pi and Pi Sandbox launchers use
the same release under `~/.local/opt/llama.cpp/pi-harness`. An existing
regular-file `pi` executable takes precedence until moved by its owner.
Use `pi-sandbox` in that configuration.

An absolute project path under the user home, `/tmp` or `/var/tmp` defines
the working area. Run Pi from inside that project. A fresh interactive
session starts in Build Mode when the permission configuration says
`defaultMode: build`. Use `--perm build` for an intentionally automated
job. Headless Permission Modes falls back to a restrictive mode when
there is no explicit or persisted mode.

Pi's normal project-trust decisions apply inside the sandbox. Pi Lens
starts language servers for trusted projects. Review project-local Pi
settings and extensions before approving them. For a one-time automated
run in an already-reviewed project, use `pi --approve --perm build -p`.
The sandbox still limits every child process to the selected project.

```bash
pi --continue
pi --resume
pi --perm build -p 'Diagnose the failing unit test and verify a targeted fix.'
pi --with-mcp
```

Pi stores new sessions and checkpoints under
`~/.local/state/localllma-setup/pi-projects/`, keyed by the canonical
project path. Resume and workspace history operate within that project.
Legacy Pi sessions stay in `~/.pi/agent/sessions` and are outside the
managed sandbox. Launcher rollback restores access through the legacy
client if it was present before installation.

## Tools and workflow

Start with targeted Pi search, `rg` or `fd`. Use Pi Lens symbols and
diagnostics when they narrow the code to inspect. The launcher keeps Lens
logs in its per-project sandbox state. Use project-local language servers
or preinstalled host tools that the launcher exposes read-only. Native read,
edit and write remain the edit engine. Add native Codemode explicitly with
`--tools +codemode`. The isolated test exercised a script that wrote and
read a Build project file. The sandbox kept a sibling file outside its
scope, and Plan Mode denied the script. Nested MCP calls remain untested.

The launcher reads shared skills from `~/dev/github/skillset/skills`
and mounts them read-only. Load a relevant skill on demand with
`/skill:name`. The `/finish`, `/review`, `/fix-ci` and `/finish-docs`
templates point to those skills. The managed workflow prompt asks for
targeted search, small edits, focused validation, a change of tactics
after repeated failures, and a final diff review.
[Workflow prompt](../config/pi-workflow.md)

The native footer displays Pi's model and context accounting. Build Mode
status comes from Permission Modes. Use the benchmark tools to capture
cache reuse and server-side rates. [Benchmark collection](BENCHMARKS.md)

## MCP

Enable the existing read-only lookup services for a specific session
with `pi --with-mcp`. The launcher forwards fixed endpoints and tool
names. Pi can call web search, Context7 and four read-oriented GitHub
tools through the existing gateways. URL reading and Deep Research are
available in the WebUI. Use `/mcp` in Pi or `pi --with-mcp mcp list` in
the terminal to inspect status. MCP lookups send query terms or repository
identifiers to the designated service.
[Sandbox and data boundaries](SECURITY.md)

## Update and rollback

```bash
./setup.sh backup --pi-only
./setup.sh update --pi-only
./setup.sh repair --pi-only
./setup.sh test --pi-only
./setup.sh restore --pi-only /path/to/backup.tar.gz
```

Updates follow the checked-in pins. Setup creates a backup before
switching an existing Pi release and keeps the previous release on disk.
Use `./setup.sh uninstall --pi-only` to remove the managed launcher and
restore the original launchers. Project sessions and configuration files
remain on disk. [Extension decisions](PI_EXTENSIONS.md)
