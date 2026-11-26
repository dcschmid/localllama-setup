# Security

The managed Pi launcher isolates the selected project using Bubblewrap.
It mounts the system binaries and shared skills read-only and creates a
private home and a private PID, IPC and network namespace. Pi and its child
processes can write the selected project and its dedicated agent state.
Host SSH material, shell variables, runtime sockets and unrelated session
directories are absent. Choose only a project whose files the agent may
read and change. Files and sockets already inside the authorized project
remain visible to that project.

The host relay exposes Cyber-Tiel chat completions and a filtered catalog
through the llama.cpp Unix socket. It caps output at 8,192 tokens,
enforces a single sequence and declines router load, unload and download
routes. The productive router remains on loopback for the WebUI. The Pi
namespace reaches the relay on its own loopback. The default session has
no general external network route.

`pi --with-mcp` exposes the existing web search, Context7 and read-only
GitHub endpoints for a session. The host relay restricts MCP RPC methods
and tool names. The WebUI retains Deep Research and direct URL reading.
The Pi relay blocks direct URL reading because the upstream fetcher
follows redirects within the research service's network namespace.
Lookup requests can send search terms or repository identifiers to the
corresponding services.
[MCP configuration](MCP_SETUP.md)

Permission Modes applies its project policy inside Bubblewrap. Build mode
allows ordinary in-project development and denies elevated shell commands.
The outer namespace remains active for descendants and in all permission
modes. Automatic Git pushes and deployments cannot reach the network
through the default launcher. The authorized project can still contain
local scripts, hooks and generated files. Treat project code and tool
results as untrusted when deciding which commands to run.

The npm lockfile fixes the runtime and its package graph. The Zod override
pins 4.6.6 after npm audit reported CVE-2023-54404 on the prior graph.
Lifecycle scripts run only when a separate explicitly reviewed setup path
calls them. Pi Lens's optional Opengrep, typos and zizmor lanes start
disabled in the managed launcher. Pi Lens automatic tool and LSP installers
are also disabled. Project-local and visible host runtimes remain available.
Semgrep is the repository security review lane. [Zod advisory](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)

The local regression probe checks project writes, read-only shared skills,
credential and sibling isolation, child inheritance and model routing.
The offline relay tests exercise model and endpoint selection and the
8,192-token cap. The probe uses synthetic paths and credentials.
[Acceptance command](PI_CODING_AGENT.md#update-and-rollback)
