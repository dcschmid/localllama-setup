# Restore Test

Verified on November 18, 2026 on the Framework Laptop 16 with Fedora 44 and RTX 5070 Laptop. The installation ran in fresh test user directories. The existing GGUF files were available there via symlinks. The test routers ran separately in a network namespace with loopback.

## Historical Restore with Writing and Media

The setup ran with saved release archives, existing models and the three saved CUDA libraries. npm and uv were set to their local caches and offline mode. The existing Atelier CLI and the installed Atelier program were linked in for the test. The shared skill collection was linked in via `LLAMA_SETUP_SKILLS`.

| Check | Status | Evidence |
|---|---|---|
| Fresh user directory | PASSED | Seven GGUFs and three CUDA libraries verified via SHA-256. llama.cpp b12503 detected the RTX 5070 as CUDA0. Node 24.22.1, GitHub MCP 2.2.0, Websearch and mcp-proxy 0.15.0 installed. |
| Repeated setup run | PASSED | The identical configuration was accepted. Dependencies and existing models were reused. |
| WebUI and router | PASSED | `GET /` returned HTTP 200 with `curl --compressed`. `GET /models` showed 16 profiles including `media-cpu`. `GET /props` showed five central MCP entries and Atelier with `enabled: false`. |
| Atelier and skills via MCP | PASSED | The restored Streamable-HTTP gateway offered 16 shared Atelier tools and ten filesystem tools. The test read the original Human Writing file via `read_text_file`. The usual filesystem write tools were missing. The local export folder had mode `0700`. |
| Human-writing template | PASSED | The install state rendered the system context from the original skill. |
| Missing optional components | PASSED | The configuration renderer was run for all four combinations of present and missing skills and Atelier. The server configuration and the browser settings match in each case. |
| KDE launcher and units | PASSED | `desktop-file-validate` and `systemd-analyze --user verify` reported no errors. |
| Media generation, Firefox and online research in the isolated restore | SKIPPED | The restore test checked the linkage and tool lists without new media jobs. The earlier media measurements are in [media-mcp.json](../benchmarks/results/media-mcp.json). |
| Reinstallation of the media projects and the operating system | SKIPPED | Atelier and Game Audio Forge have a separate project installation. Restoring these projects follows their own setup guides. |

## Original Restore with 12 Profiles

| Check | Status | Evidence |
|---|---|---|
| Reinstallation from existing data | PASSED | Release archives, seven GGUF files and three CUDA libraries verified via SHA-256. Upstream build b12503 detects CUDA0. |
| MCP packages from the cache | PASSED | Node 24.22.1 and GitHub MCP 2.2.0 installed. Both npm installs ran with the lockfiles. The websearch TypeScript build also succeeded with npm in offline mode and `NODE_ENV=production` set. |
| Run setup again | PASSED | Repetition in the same test user directory accepts existing profiles and installed components. |
| Systemd units and application launchers | PASSED | Checked with `systemd-analyze --user verify` and `desktop-file-validate`. |
| WebUI, router and CUDA chat in the isolated network | PASSED | The embedded WebUI returned HTTP 200. `/models` listed 12 profiles. `fast-chat` answered the probe with `RESTORE_OK`. |
| Read-only skills | PASSED | The restored router detected 10 filesystem tools. The rendered MCP configuration contained `--read-only`. |
| Benchmark calls | PASSED | Short CUDA benchmark with 128 prompt and 16 decode tokens per subtest. The 8K router test processed 7,672 input tokens before the chat template and found all three facts. |
| Full Fedora reinstall and renewed large downloads | SKIPPED | Verification covered restoration from existing archives, GNU/Linux system packages and model weights. |
| Desktop re-login, online research and complete agent runs after the restore | SKIPPED | The detailed functional and offline coding tests of the original state are in [SETUP.md](SETUP.md) and [MODEL_BENCHMARKS.md](MODEL_BENCHMARKS.md). |

## Uninstallation

| Check | Status | Evidence |
|---|---|---|
| Preview on the installed system | PASSED | `--dry-run --remove-models` listed all three units, the packaged components and seven GGUFs. |
| Uninstall in the test directory | PASSED | Separate home with a simulated systemd user manager. Services were stopped before moving the units. Configuration and CUDA libraries were backed up. Browsers, cloud profiles, media and models were preserved. |
| Optional model removal | PASSED | List entries and partial downloads were removed. One additional GGUF file, one file with a differing size and the target of a model symlink were preserved. |
| Repeated calls and error cases | PASSED | A repeated call produced no further backup. A busy setup lock, a unit from a different directory and a failed service stop prevented file removal. |
| Uninstall in the running user account | SKIPPED | Only the preview was run there. |

## Configuration Check After the MCP Cleanup

The setup templates were rendered with and without the shared skill collection. The browser list and the gateway configuration match in both cases. The model manifest matches the GGUF files registered in the router. The full package-based reinstallation was not repeated in this check step. The functional checks of the updated live installation are in [SETUP.md](SETUP.md#qa-of-the-model-and-mcp-cleanup).
