# Native llama.cpp Installation

As of November 19, 2026. [Quickstart](QUICKSTART.md) · [Model comparison and measurements](MODEL_BENCHMARKS.md)

## System and Installation

- Framework Laptop 16, Fedora 44 KDE/Wayland, kernel `7.3.4-200.fc44.x86_64` since the reboot on November 18. AMD Ryzen AI 9 HX 370 with 12 cores and 24 threads, AVX2, AVX-512, VNNI and FMA. Radeon 890M with Vulkan/RADV and AMD XDNA were detected.
- Linux reported 46.8 GiB RAM, initially around 23 GiB available and around 8 GiB of ZRAM swap in use. The Radeon reported a 16 GiB VRAM aperture. The 16 GiB graphics reservation plausibly explains most of the deviation from the 64 GB configuration.
- RTX 5070 Laptop, NVIDIA driver `615.78.08`, Compute Capability `12.0`. `nvidia-smi` reported 8,151 MiB, the CUDA runtime 7,799 MiB. The driver reported CUDA 13.4. The installed upstream build uses CUDA 12.8.
- WD PC SN8000S NVMe with around 1.5 TiB free under `/home`. Btrfs on LUKS. The kernel marks the NVMe as non-rotational. The Fedora power-save profile limited the CPU to 2.0 GHz. Time-limited performance measurements take a D-Bus lease and release it afterwards.
- Official `llama.cpp` [b12503](https://github.com/ggml-org/llama.cpp/releases/tag/b12503), commit `4577932fab595eaa8b27ad71734d5de1f3c07d8c`. Upstream binary package Linux x86_64 CUDA 12.8, GNU 13.3.0, CUDA with `sm_120a` kernels and the Zen-4 CPU backend, plus the embedded official Llama Chat WebUI. The SHA-256 of the package was verified against the GitHub release. Existing NVIDIA runtime libraries were copied into the new versioned installation.
- Program files under `~/.local/opt/llama.cpp/b12503`. `current` points to the active build. `llama-server`, `llama-cli` and `llama-bench` are reachable in `~/.local/bin`.
- Weights live in `~/models/gguf`. `models.ini` uses absolute paths and native router aliases. Several profiles share the same GGUF. One model and one slot run at a time. The router loads on demand and unloads on switch. For inactivity, the native sleep timeout is set to 15 minutes.
- The router binds to `127.0.0.1:8080` and a private Unix socket under `$XDG_RUNTIME_DIR/llama-cpp/server.sock`. Model downloads are locked in the router runtime. Existing audio, image, Open-WebUI and TinySearch services keep their own ports and configurations.

## Operation and Profiles

`~/.config/llama.cpp/models.ini` contains the profiles and the measured start values. `curl -fsS http://127.0.0.1:8080/models` lists them without loading a model. For diagnostics, `/props?model=NAME` shows the effective context size. That call can load a model.

The seven active profiles use three GGUF files. The SHA-256 checksums are in the restore package under `packages/models.tsv`.

| Profile | Model | Context |
|---|---|---:|
| `research` | Gemma 4 26B A4B IT QAT Q4_0 | 32K |
| `deep-research` | Gemma 4 26B A4B IT QAT Q4_0, 128 thinking tokens per request | 32K |
| `coding-long-256k` | Cyber-Tiel-Coder 35B A3B APEX-I MiniPlus | 256K |
| `creative-writing`, `human-writing`, `human-rewrite`, `human-audit` | Gemma 4 12B StyleTune Q4_K_M | 16K |

Cyber-Tiel is loaded via `coding-long-256k` with 262,144 tokens, 2,048/1,024 batch/microbatch and Q4_0 for K and V. The server default for the output is 8,192 tokens. The profiles use mmap, CUDA with a 1,024 MiB target reserve and Flash Attention. The router loads at most one model process. MTP is off. [Performance measurement and rollback](PERFORMANCE_OPTIMIZATION.md)

- `llama-webui` starts the user services on demand and opens the browser.
- `llama-webui --check` checks the inference service without opening a browser.
- `systemctl --user stop llama-cpp.service` stops the router and the associated research service.
- `journalctl --user -u llama-cpp.service -n 80` shows model start-up and CUDA memory. For web search use `journalctl --user -u llama-cpp-research.service -n 80`.
- After preset changes, `curl -fsS 'http://127.0.0.1:8080/models?reload=1'` reloads the list. Finish a running generation first. Changes to systemd units need `daemon-reload` and a restart of the user service.

## WebUI, Research and MCP

The KDE launcher opens the native WebUI at `http://127.0.0.1:8080`. Model API and UI share the port. The local coding wrappers continue to access the private socket `$XDG_RUNTIME_DIR/llama-cpp/server.sock`. Firefox stores chats, settings and tool approvals per origin. `localhost`, `127.0.0.1` and different ports denote different origins.

`llama-server` b12503 takes the central browser settings from `--webui-config-file ~/.config/llama.cpp/ui.json`. The equivalent short name is `--ui-config-file`. `mcpServers` contains a JSON-encoded list of direct HTTP connections. The server publishes them in `/props.ui_settings`. Firefox adopts these settings on the first visit. Existing profiles keep their settings. In the regular profile the four MCP entries were added once through the interface.

| Shown in the WebUI | MCP endpoint | Service |
|---|---|---|
| Websearch & Deep Research | `http://127.0.0.1:8642/mcp` | `llama-cpp-research.service`, existing Danmoreng/websearch-mcp |
| Context7 | `http://127.0.0.1:8643/servers/context7/mcp` | Existing Context7 via `llama-cpp-mcp.service` |
| GitHub | `http://127.0.0.1:8643/servers/github/mcp` | Existing GitHub MCP via `llama-cpp-mcp.service` |
| Skill collection (read-only) | `http://127.0.0.1:8643/servers/skills/mcp` | Existing Filesystem MCP via `llama-cpp-mcp.service` |

All connections use Streamable HTTP directly from the WebUI. The user service `llama-cpp-mcp.service` uses [mcp-proxy 0.15.0](https://github.com/sparfenyuk/mcp-proxy/releases/tag/v0.15.0) as a transport adapter for the three existing stdio programs from `mcp.json`. Websearch already binds to loopback itself and is connected directly. The router uses the browser entries instead of the previously parallel server-side tools. The model sees the original tool names such as `search_web`, `read_url`, `deep_research` and `read_text_file`.

The websearch service keeps its own network namespace, the filter rules and the local inference socket. Deep Research starts a background job and uses the `deep-research` profile by default through the existing local API. The tool argument `model` can override the profile. The local inference timeout is 90 seconds. The research budget is 240 seconds. The status comes through `deep_research_status` with the job ID. The gateway binds to `127.0.0.1`, checks host and browser origin and accepts the WebUI at `http://127.0.0.1:8080`. GitHub continues to wrap the existing `gh` login inside the read-only server process. The skills share remains limited to `~/dev/github/skillset/skills`. The WebUI asks for approval per tool call, as long as no decision is stored for that tool.

### Diagnostics

```bash
systemctl --user status llama-cpp.service llama-cpp-research.service llama-cpp-mcp.service
curl -fsS http://127.0.0.1:8080/props | jq -r '.ui_settings.mcpServers | fromjson[] | [.displayName,.url] | @tsv'
curl -fsS http://127.0.0.1:8642/healthz
curl -fsS http://127.0.0.1:8643/status
```

The original Firefox tests used new temporary profiles and invoked the server-side registered tools via **Tools → Server**. The "Add your first MCP server" notice, by contrast, belongs to the browser list and was expected under the earlier default `mcpServers = []`. Issue #26497 documents a similar symptom. Report #28077 was withdrawn by its author. The installed build applies the central settings on the first visit also in router mode. [Upstream server docs b12503](https://github.com/ggml-org/llama.cpp/blob/b12503/tools/server/README.md) · [Issue #26497](https://github.com/ggml-org/llama.cpp/issues/26497) · [Issue #28077](https://github.com/ggml-org/llama.cpp/issues/28077)

## Human Writing in the WebUI

An earlier Firefox chat with `human-writing` received no search tools without the `[web]` tag. The template now also recognizes selected unambiguous tasks at the start of the first line, such as „Recherchiere im Web", „Verwende ausdrücklich unseren Websearch MCP" and „Search the web". For these tasks it passes on only `search_web` and `read_url` to StyleTune. For Deep Research, `deep-research` is available. For the other research tasks use `research`.

The router build b12503 supports the Gemma system format and `chat-template-file` and `chat-template-kwargs` per model collection entry. The installed WebUI offers no native loading and running of an agent skill. The writing profiles therefore use the native Gemma template with an additional system message. The embedded Gemma format for user and assistant roles, tools and tool responses still applies. The WebUI can add its own system message. The four writing profiles start with thinking disabled. [Upstream documentation for b12503](https://github.com/ggml-org/llama.cpp/blob/b12503/tools/server/README.md)

| Router profile | Default mode | Suited for |
|---|---|---|
| `creative-writing` | Generate, Fiction | English short stories, Riff-Racers scenes, characters and dialogue |
| `human-writing` | Generate, Editorial | German and English, music reviews, blog, devlog and personal texts |
| `human-rewrite` | Rewrite | Gentle editing of already existing texts |
| `human-audit` | Audit | Concrete findings on patterns, density and substance |

All four profiles use `Gemma-4-12B-StyleTune.Q4_K_M.gguf`, 16,384 context tokens and Q8_0 K/V. The first task line can set the mode with `[generate]`, `[rewrite]`, `[audit]`, `[website-audit]`, `[website-rewrite]` or `[voice]`. `[de]` and `[en]` select the language reference. Further genre tags are `[fiction]`, `[editorial]`, `[technical]`, `[business]`, `[marketing]` and `[ux]`. Common German and English task words are recognized in the first line. For ambiguous or foreign-language instructions the tags are the reliable control. The chosen classification applies to follow-up questions until a new task changes it.

### System Context and Updates

- The source of the rules is `~/dev/github/skillset/skills/human-writing` or the shared skill path in `mcp.json`. Server start builds the Jinja cache with `~/.config/llama.cpp/writing/render.py` from this source. The generated cache under `~/.cache/llama.cpp/writing/gemma4-human-writing.jinja` is replaced on changes in the checkout. To apply changes in already-loaded models, restart the user service.
- Every writing request receives the full `SKILL.md` and the quality gates. The language selects `style-de.md` or `style-en.md`. Genre work receives the matching section of `genre-guides.md` or `creative-writing.md`. Rewrite adds `fidelity-rules.md` and `patterns-core.md`. Audit receives the patterns for findings assessment. Voice Calibration receives `voice-calibration.md` and the profile template. The website modes load their audit or rewrite rules including the relevant SEO and A11y notes.
- The system message requires the finished text by default for Generate and Rewrite. Audit delivers the requested findings and Voice Calibration the profile for the examples. The skill rules limit revising passes to two. Protected facts, quotes, numbers, URLs and technical spans are prioritized in the rewrite instruction. Editorially review model answers with important facts before passing them on.
- If the service start reports an error while rendering, see `journalctl --user -u llama-cpp.service -n 60`. The script replaces the generated file only after all sources have been read successfully. A fresh installation of the writing profiles requires the local skill collection.

### Source-Bound Writing Tasks

`[fakten]` or `[facts]` activates source binding per task. The template adds the fidelity rules and requires checking every factual claim against an entered fact sheet, source excerpts or actual tool results. Observation, plan, result, uncertainty and attribution are to be preserved. The additional system context is a model instruction. A separate pass with `human-audit` and the review of the original sources remain the release steps for important texts.

Research public facts first and check the fact sheet. Then write with StyleTune in the local writing profile. The tag `[fakten]` does not blend the research process into the writing run. Approval for the embedded web tools goes through `[web]`. For internal topics, the user supplies the fact sheet. The [quickstart guide](QUICKSTART.md#fact-sheets-from-sources) contains the tasks for the individual steps.

### Linter, Website Audit and Approvals

The existing Filesystem MCP offers ten read-only file tools. The writing context is loaded directly when formatting the prompt. For ordinary writing tasks the template hides the tool descriptions in the model prompt. If `[web]` stands at the start of the current task, it renders exclusively the web search and page fetch offered for this chat in the WebUI. The approvals of the WebUI remain in force. The installed MCP tools offer no process call restricted to `lint_text.py`. The optional text check runs separately and uses the unchanged skill CLI.

```bash
skill="$HOME/dev/github/skillset/skills/human-writing"
python3 "$skill/scripts/lint_text.py" /pfad/zum/text.md --lang auto
python3 "$skill/scripts/website_audit.py" https://example.com --format json --out audit.json
python3 "$skill/scripts/project_audit.py" audit /pfad/zum/projekt
```

The first and third commands work locally. The second explicitly fetches the specified public website. Linter or audit reports can then be attached as files to a writing chat. `[website-rewrite]` delivers suggestions. Applying them via the existing project CLI or in the CMS requires the intended approval. The writing profiles do not enable shell execution.

## Local Coding

- `claude-local` starts Claude Code with llama.cpp `/v1/messages`. `codex-local` uses `/v1/responses`. The CLI profiles and states live under `~/.config/llama.cpp/claude` and `~/.config/llama.cpp/codex` respectively. The skills are linked in via the existing collections. Both wrappers check the 262,144 tokens of the single coding profile. Claude uses 8,192 output tokens and 85 % as the compaction target. Codex uses the explicit limit 222,822 and takes its output budget from the server.
- Both wrappers start the router on demand, check the selected profile and start the local client in its own network namespace. A TCP connection in the namespace forwards exclusively through the private router socket. The clients receive a minimal environment. Claude uses a local placeholder and Codex no OpenAI authentication.
- The wrappers do not write the regular cloud clients, credentials or cloud configurations. The local Codex takes over the current user settings via a copy. Changes to the cloud configuration therefore flow into local mode only after a targeted takeover. Remote MCPs are unreachable in the isolated network. The usual file and shell permissions of the clients remain in force.
- Coding tests ran in separate local Git fixtures. Tests with edit and execute permissions were limited to the respective fixture. The USD value shown by the Claude SDK is a client estimate. The requests went to the local socket during the tests.

## Updates and Troubleshooting

The per-model verified performance settings, measurement conditions and the path back to the original configuration are in [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md).

For an update, unpack an official release build with a compatible CUDA runtime into `~/.local/opt/llama.cpp/<build>` and verify its release hash. Run `llama-server --version` and `--list-devices` directly in the new directory, then switch `current` and restart the user services. Keep the old build for a switch-back. Check router or CLI option changes against their `--help`.

When loading a large model, `nvidia-smi`, `free -h` and the journal help to distinguish VRAM, host-RAM and template errors. For small coding tasks, short prompts in the 256K profile suffice. Firefox showed an HTTP 415 for the embedded variable font file. Chat, model selection and text attachments worked with the fallback font. The file navigation probe of the WebUI is rejected while host file tools are disabled. Shared skills remain reachable via Filesystem MCP.

## Skills Used and Test Scope

Skill Orchestrator covered 27 skills in the repository. Agent Harness structured the offline and tool tests. QA and Code Review supplied review criteria for Firefox, the API contracts and the setup files. No scripts from the skills were started for model and agent tests.

The artifacts of the measurements are in `~/.cache/llama.cpp/setup`. The directory contains the download logs, the official benchmark output, device telemetry and the outputs of synthetic QA tasks. The two coding fixtures are standalone test directories.

## QA of the Model and MCP Cleanup

This section documents the historical acceptance before the unification on 256K.

| Check | Status | Evidence |
|---|---|---|
| Web search in the regular Firefox | PASSED | Gemma 4 26B in the `research` profile called `search_web` after **Allow once**. The answer linked the official Python documentation on Decimal. A separate Playwright run additionally checked the actual HTTP tool response. |
| Deep Research in the regular Firefox | PASSED | `deep_research` was submitted after **Allow once**. The status query over MCP reported `completed`. The service captured one official Python source and delivered a source-based fallback summary after the local LLM synthesis timed out. |
| Page fetch, developer docs, GitHub and skills | PASSED | Actual MCP calls of `read_url`, `resolve-library-id`, `query-docs`, `get_latest_release` and `read_text_file`. |
| No media MCPs in Llama Chat | PASSED | After restarting the llama.cpp services, a newly opened window in the regular Firefox profile showed four connected entries. The Atelier card was removed via the native menu. The gateway listed only the three static stdio servers for Context7, GitHub and skills. |
| Codex with Cyber-Tiel | PASSED | Isolated coding run with bugfix, refactoring, six unit tests and an independent contract check. |
| Claude Code with Cyber-Tiel | PASSED | After restarting the memory-intensive Stageground development server, the same Ledger fixture passed four unit tests and the independent contract check. The earlier timeouts are in the benchmark history. |
| Tool calling with Cyber-Tiel | PASSED | Two chained tool calls over the local chat API. The second call used the previously delivered build ID. |
| Defensive check with Cyber-Tiel | FAILED | The check detected that missing principals must be rejected. The proposed fix could still raise a `KeyError` when a tenant key is missing. |
| StyleTune and Human Writing | PASSED | Six native template tests. English scene with two dialogue voices and a German revision with preserved date, number and link. |
| Cyber-Tiel context profiles | PASSED | Five profiles from 32K to 256K are registered. 64K loaded with 65,536 tokens and answered a short retrieval test. The full-context measurements for 128K to 256K come from the earlier measurement series. |
| Final service restart | PASSED | Router, websearch and MCP gateway responded after the restart. Both local wrappers started with `coding-fast` and Cyber-Tiel. The Codex smoke test produced the expected response via the local Responses API. Atelier and Game Audio Forge remained active. |

## Historical QA Before the Model Cleanup

| Check | Status | Result |
|---|---|---|
| CUDA, CLI tools and bindings | PASSED | CUDA0 on RTX 5070, native sm_120a kernels, no LAN binding of the new router or research service |
| Official WebUI, KDE launcher and systemd | PASSED | Launcher executed, user services restarted, model selection, chat, text attachment and reopened chat checked in Firefox |
| Chat search, conversation export and import | PASSED | Test chat found via search, exported as ZIP and imported into a fresh Firefox profile |
| Router model switch and idle sleep | PASSED | At most one instance, switching between models and sleeping status in the shortened test |
| Web search, HTML and PDF via MCP | PASSED | DuckDuckGo web search from Firefox after a one-time approval. Read the Python documentation and PDF text from arXiv, test address range rejected |
| Deep Research | PASSED | Two jobs with two sources read each, including one job through the native router in 39.3 s. Supplementary sources of differing quality require visual inspection |
| Filesystem, Context7, GitHub | PASSED | Read SKILL.md and a reference, path outside the share rejected. Read the Astro documentation and read-only GitHub release |
| Hugging Face | PASSED | Anonymous repo search worked in the test. The optional Streamable-HTTP access can be added in the browser when needed |
| Claude Code and Codex offline | PASSED | Separate Git fixtures edited and independently checked with unit tests. Both clients also confirmed the 128K alias |
| Skill access | PASSED | Claude used the skill tool call for backend-api-engineering. Codex loaded the existing skill collection and answered the skill task. Llama Chat uses read-only filesystem access |
| 128K, 192K and 256K | PASSED | Cyber-Tiel extracted three facts per test. Real 100K source code checked in the 128K profile. At 256K around 196K tokens were reused |
| LFM retrieval at 128K | FAILED | Technical run completed, 0 of 3 searched facts in the first full long-context test |
| Coding security | PASSED | Defect in the controlled local source code detected. The first patch left the missing-key edge case open |
| Prose and German | PASSED | StyleTune and Gemma QAT delivered the English dialogue probe, QAT answered the German everyday prompt |
| MTP | PASSED | Sidecar and tool chain runnable. Total duration was higher, therefore disabled in the standard profiles |
| NVMe and persistent slot | PASSED | Compared mmap and direct I/O. After save, unload and load, 2,663 tokens were reused from the slot state |
| Optional integrations | SKIPPED | Vulkan benchmark, SearXNG instance, Playwright-MCP, additional Gemma community quant and YOLO-Auto |
| Full system reboot | SKIPPED | Running desktop session, service restart verified |
| Media pipelines, status | PASSED | Audio web interface HTTP 200, service states checked before and after the setup. No generation probe triggered |

### QA of the Writing Integration

| Check | Status | Result |
|---|---|---|
| System context and routing | PASSED | Native `/apply-template` tests cover all four profiles, all six modes and both language references. An existing user system message remains effective. |
| Firefox without external network | PASSED | Profile switch, dialogue and audit in the official WebUI over the local Unix socket. Both answers rendered in the chat. The model emitted no tool calls. |
| Tool filter | PASSED | For local writing and audit, tool descriptions are hidden. In the then-current test with `[web]` the template renders exclusively the offered search and page-fetch tools. It recognizes both the direct MCP names and the previously server-side names. The local file navigation probe of the browser was rejected. |
| Skill tools | PASSED | All three existing CLI tests passed in a temporary test copy. Filesystem MCP still offers ten pure read tools. |
| Restore of the writing configuration | PASSED | The restore package renders a byte-identical template from the central skill checkout in the test user directory. |
| Editorial comparison | TESTED | Nine A/B pairs produced improvements in individual texts and still errors in scope and factual fidelity. See [model comparison](MODEL_BENCHMARKS.md#human-writing-with-gemma-4-12b-styletune). |

The recordings of the routing and Firefox check for this run are under `~/.cache/llama.cpp/writing.hmhXLZBN`. The web and project CLIs were checked with local test data.

### QA of the MCP Conversion

| Check | Status | Evidence |
|---|---|---|
| Entries from central configuration | PASSED | Four cards with 20 tools in total in a newly created Firefox profile on the production origin. |
| Web search and page fetch | PASSED | Actual Streamable-HTTP calls for `search_web` and `read_url` from a chat of the installed WebUI. Hits and page content from the official Python documentation. |
| Deep Research | PASSED | Job started from the WebUI. `deep_research_status` reported `completed` and delivered a source from the official Python documentation. |
| Context7 and GitHub | PASSED | `resolve-library-id` and `query-docs` delivered Astro documentation. `get_latest_release` delivered the upstream release data of llama.cpp. |
| Skill collection | PASSED | `read_text_file` delivered the real Human-Writing SKILL.md. The model applied the rule of at most two revision steps. The direct MCP test rejected a path outside the share. |
| Writing | PASSED | Dialogue and audit with StyleTune in Firefox. The system template loads the skill rules automatically. In the prompt probe the direct tool names were offered only with `[web]`. |
| Tool approvals | PASSED | **Allow once** appeared before the checked MCP calls. In the UI test every approval was granted individually. |
| Gateway HTTP boundaries | PASSED | Allowed WebUI origin HTTP 200. Foreign browser origin HTTP 403 and foreign host header HTTP 421. |
| Restart of the services | PASSED | All three user services were restarted. On re-entry at the KDE origin the regular Firefox showed the four connected entries. |
| Browser restart | PASSED | A persistent Firefox test profile was closed and reopened after the service restart. The four entries remained stored and reconnected. |

The detailed tool results of the Firefox automation for this run are under `~/.cache/llama.cpp/mcp-menu.7I318ZkC`. The migration in the regular browser only added MCP entries via the existing interface.

Historical media measurements stay in the restore package under `benchmarks/results/media-mcp.json`. Atelier and Game Audio Forge run as standalone projects.
