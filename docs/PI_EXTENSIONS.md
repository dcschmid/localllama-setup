# Pi extension selection

[The manifest](../config/pi-manifest.json) records direct versions, sources,
activation and conflicts. [The npm lockfile](../packages/pi/package-lock.json)
pins transitive dependencies for the official CLI and four default packages.
Setup uses `npm ci --ignore-scripts` and leaves experiments out of the release.
Candidate probes ran with Pi 1.5.2 and Node 22.23.2. The managed Pi install
and repair also passed with Node 24.22.1.

## Decisions

| Component | Version | Quality impact | Performance impact | Security | Compatibility | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| Native Pi tools | 1.5.2 | MetalVault fix passed independent checks | Baseline reference | Project-scoped in V2 | Compatible | DEFAULT |
| Native compaction | 1.5.2 | Passed independent two-file coding acceptance after process restart | See the context report | Cyber-Tiel only in V2 | Compatible | DEFAULT |
| Native Codemode | 1.5.2 | Combined project write and read passed in Build | Not Tested | Plan denied execution. A sibling file stayed outside the Build sandbox | Conditionally Compatible | OPTIONAL |
| Pi Lens | 4.5.1 | Installed TypeScript server returned a diagnostic and Lens found the fixture symbol in an isolated tool test | Historical tool schema cost in the benchmark report | Auxiliary auto-installers disabled by the launcher | Compatible with native tools | DEFAULT |
| Pi Permission Modes | 2.7.2 | Build allows ordinary in-project tasks | Headless fallback observed | Retains the existing policy inside Bubblewrap | Compatible | DEFAULT |
| Pi Workspace History | 0.5.2 | Isolated undo restored the tracked file and clean Git worktree | Not Tested | V2 state scoped to one project | Compatible | DEFAULT |
| Pi Todo Agent | 0.3.0 | Pending task recovered from a saved session | Not Tested | V2 state scoped to one project | Compatible | DEFAULT |
| Pi Sessions | 0.23.4 | Native sessions cover the tested resume and fork workflows | Not Tested | Additional session access surface | Incompatible with V1 Node 22. Not Tested on V2 Node 24 | REJECTED |
| Pi Condense | 2.18.1 | Isolated `/pruner` registration | Historical short fixture only | Summarizer configuration needs local routing and quality checks | Conditionally Compatible | EXPERIMENTAL |
| NVIDIA SoL-Pi | 0.1.0 | Direct ObservationPack projection, recall and failure retention passed with a mocked provider | Not Tested for end-to-end task time | Action Fusion declined the Permission Modes backend. The reducer has its own model route | Incompatible with the published Pi peer range | REJECTED |
| BetterCompaction | 1.3.1 | Recovered all four markers and passed independent 32K coding acceptance | Similar time on the two-file coding fixture. Faster in one medium-thinking marker-only pair | Uses the selected model through Pi | Conditionally Compatible | EXPERIMENTAL |
| Pi VCC | 0.11.2 | The primed 32K and cold 64K samples recovered 3/4 markers. A two-file 32K coding change failed independent acceptance. Isolated archive recall passed after compaction and fork | Faster compaction on the measured fixtures | Local session transcript with recall scope | Conditionally Compatible | REJECTED |
| Hashline Edit Pro | 7.2.0 | Anchored edits preserved CRLF, Unicode and indentation. Alternate edits and skill read presentation differ from native | Not Tested for coding quality | Build changed the fixture, Plan denied it and the read-only skill refused mutation | Conditionally Compatible | EXPERIMENTAL |
| RTK Optimizer | 0.9.0 | Not Tested | Not Tested | Rewrites command parameters and filters results. Requires RTK runtime | Incompatible with declared Pi peer ranges | REJECTED |
| Pi FFF | 0.11.0 | Isolated search and file watcher checks passed | 4 ms warm content search in one fixture | Native libraries. Home and symlink scanning enabled upstream by default | Conditionally Compatible | EXPERIMENTAL |
| Dynamic Footer | 0.1.11 | Footer command loaded | Reports client-derived throughput | Adds a provider quota credential client | Conditionally Compatible | EXPERIMENTAL |
| Shared Skillset | Local files | Direct skill discovery | Small on-demand reads | Read-only mount | Compatible | DEFAULT |
| MCP services | Existing HTTP services | Lookup tools | Not Tested in coding benchmark | Opt-in relay with an endpoint and tool allowlist | Conditionally Compatible | OPTIONAL |

## Pairing and package audit

| Modified surface | Pairing | Evidence |
| --- | --- | --- |
| Edit and write | SoL-Pi Action Fusion + Hashline | Incompatible as co-defaults. Both change the edit interface. The Hashline package also replaces read and grep. |
| Edit checkpoints | Hashline + Permission Modes + Workspace History + Lens | Build and Plan dispatch passed with the managed packages loaded. Lens and Workspace History parity for anchored edits remain Not Tested. |
| Shell execution | SoL-Pi Action Fusion + Permission Modes | Incompatible for fused validation in this profile. The isolated probe returned an unsupported backend because Permission Modes owns bash. Pi still has separate edit and validation tools. |
| Context | Native + one of VCC or BetterCompaction | Conditionally Compatible. Each uses Pi's compaction callback. Runtime tests must measure how the selected hook hands off and resumes. |
| Context | VCC + BetterCompaction, or either plus SoL-Pi context management | Incompatible as co-defaults. Compaction ownership and replay order can differ. |
| Tool output | RTK + SoL-Pi ObservationPack or Condense | Redundant where both remove content from the same terminal result. Preserve diagnostics and originals before considering any pairing. |
| Search | FFF + native Pi + Lens | Conditionally Compatible with distinct FFF tool names and project-only indexing. FFF can also replace native find/grep, which duplicates the default surface. |
| Footer | Dynamic Footer + native footer + Permission Modes | Not Tested in the TUI. The extension sets a custom footer and polls quota for supported cloud providers. |
| Codemode and MCP | Native Codemode + Pi tools/MCP | Conditionally Compatible. The Build/Plan and project-isolation probe covered nested file operations. Nested MCP calls remain untested. |
| Skill paths | Shared Skillset + Hashline or FFF | Hashline added anchors to the shared skill fixture's read output. The skill remained unchanged after an attempted mutation. Shared skill indexing with FFF remains Not Tested. |

The active candidates use MIT licenses in the audited metadata. The package
named `pi-vcc` in npm has a different maintainer and repository. The reviewed
artifact is `@sting8k/pi-vcc@0.11.2`. BetterCompaction's Git release 1.3.1
was audited at commit `38801c4865eacbe877ed9f5cae075e5889d4423f`. Its
internal package manifest reports 0.1.0. NVIDIA's stable npm artifact
0.1.0 declares Pi 0.84.2 or 0.85.1. The direct mechanism probes bypassed
npm peer resolution in scratch. The source checkout reported 0.1.1
and was inspected for differences. The published Evidence-Preserving Reducer has a cloud provider
as its default route. The reducer and all other SoL-Pi mechanisms were off
during the startup probe.
[SoL-Pi source](https://github.com/NVlabs/SoL-Pi) ·
[BetterCompaction release](https://github.com/NotSoSeriouss/BetterCompaction/releases/tag/1.3.1) ·
[VCC release](https://github.com/sting8k/pi-vcc/releases/tag/v0.11.2)

Hashline 7.2.0 depends on diff, file-type, xxhash-wasm and web-tree-sitter.
FFF 0.11.0 uses the published Node FFI package and Linux native libraries
for search, plus the Bun package in its dependency graph. RTK Optimizer's
postinstall can start a dependency patcher in certain installation paths.
Its terminal rewrite, raw-output recovery and exit-code preservation
remain unverified here. The separately published RTK runtime was 1.2.1 at
review time. Dynamic Footer 0.1.11 includes the provider usage fetcher.
The audit pinned that dependency to 0.3.4 during the isolated probe.
[Hashline source](https://github.com/YuGiMob/pi-hashline-edit-pro) ·
[FFF source](https://github.com/dmtrKovalenko/fff) ·
[RTK Optimizer source](https://github.com/MasuRii/pi-rtk-optimizer) ·
[RTK runtime](https://github.com/rtk-ai/rtk) ·
[Dynamic Footer source](https://github.com/huaxel/pi-dynamic-footer)

Candidate installs used separate scratch directories with npm lifecycle
scripts disabled. Startup means Pi answered its RPC state request. It
does not imply a candidate passed tool permission checks, session recovery,
quality gates or a performance benchmark. See the [benchmark evidence](BENCHMARKS.md).

Before updating a candidate, check its exact artifact and dependency
versions. Repeat the isolated checks for that candidate without enabling
another output reducer, edit replacement or compaction hook in the same
profile. A release switches only after the reviewed default lockfile and
managed files are installed.
