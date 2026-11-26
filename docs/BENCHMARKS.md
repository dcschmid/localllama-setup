# Benchmarks

The [benchmark directory](../benchmarks/README.md) contains the scripts,
published machine-readable results and measurement conditions. Use the
same model build, quantization, context capacity, fixture, prompt and
runner for an A/B comparison. Record the power profile, first-request
cache counters and any other work on the router. The coding router has
one slot. Pi task timings and direct llama.cpp timings measure different
workloads.

## Historical inference and native Pi

The direct llama.cpp runs date from 18–19 November 2026. On the historical
256K workload, the warm request reused 261,684 of 261,688 prompt tokens.
Its time to first token was 0.67 seconds. The cold full-window workload
took 393.7 seconds to the first token and decoded at 6.89 tokens per second.
Instructions for repeating that workload are in the
[benchmark directory](../benchmarks/README.md).

The 19 November Pi comparison used a three-turn task on a 400-line
fixture. Both variants answered correctly.

| Pi tool set | Wall time | Peak reported context |
| --- | ---: | ---: |
| Native | 49 s | 9,826 |
| V1 with four extensions | 50 s | 16,951 |

Use this comparison to quantify the tool schema cost for that fixture.
It does not establish a whole-task gain for V2.
[Historical result](../benchmarks/results/pi-ext-ab-2026-11-19.json)

## V1 MetalVault baseline

On 20 November, the host reported Fedora 44, 24 CPU threads and
46 GiB of visible RAM. The RTX 5070 Laptop GPU reported 8,151 MiB of VRAM.
The run used the low-power platform profile, Pi 1.5.2, Node 22.23.2 and
llama.cpp b12503 (`4577932fa`). The managed Node link for the stack pointed
to 24.22.1. The router exposed Cyber-Tiel through one CUDA slot with
262,144 context tokens, 8,192 max output and 512 MiB cache. Two production
Pi launchers differed from the repository. The plain `pi` launched the
official CLI through the private profile's link and did not enter the
separate Bubblewrap wrapper.

The pre-change Pi settings named Pi Lens 4.5.1, Permission Modes 2.7.2,
Workspace History 0.5.2 and Todo Agent 0.3.0. Pi Condense and Pi Sessions
were absent from the active package list. Pi Sessions state files existed
from earlier use. Pi 1.5.2 provided native Codemode and native sessions.
The installed profile had four prompt templates, 27 shared skill files
and three MCP endpoints. Router, research gateway and MCP gateway were
active. Host tooling included TypeScript Language Server, Pyright, Ruff,
ShellCheck, rust-analyzer, `rg` and `fd`. These are presence checks.
Language-server diagnostics and MCP tool calls require runtime checks.

| V1 run | Wall time | Result |
| --- | ---: | --- |
| Implicit headless mode | 141.44 s | Aborted after Plan denied edits |
| Explicit Build A | 315.49 s | Router restart interrupted inference |
| Explicit Build B | 263.36 s | 70 existing tests and the independent duplicate-ID regression passed |

Build B made 20 successful model responses and 19 tool calls. Pi reported
24,871 fresh input tokens, 431,743 cache-read tokens, and 3,354 output
tokens over the run. The first response used 14,502 fresh tokens and zero
cache reads. The highest per-response total was 28,011 tokens. Two out-of-
project probes were denied. There were no manual approvals. The model's
first attempts used pytest, which was unavailable in the isolated profile.
It eventually ran the same suite through unittest. The later runner
requests unittest directly, so this wall time does not isolate a V1/V2
performance difference.
[Baseline and candidate observations](../benchmarks/results/pi-harness-v2-2026-11-20.json)

## V2 checks and candidate evidence

- Pi-only installation, a repeated install, Doctor, backup, restore and
  launcher rollback passed in a temporary home.
- The live Bubblewrap probe passed 11 assertions. Five independent relay
  tests passed with an offline upstream fixture. The relay test verifies
  its request limits and policy without exercising model quality.
- Hashline preserved Unicode, indentation and CRLF in a single anchored
  replacement. The direct test also covered multiline replacement, insertion,
  deletion, editing across files and the tail of an 8,000-line file. Old
  and invalid anchors left the file intact. With a mocked provider and
  the V2 packages loaded, the anchored edit worked in Build and was
  denied in Plan. Build could read the shared skill fixture with added
  anchors and could not modify it. Workspace History undo for alternate
  edit tools and comparative coding quality remain open.
- FFF found fuzzy paths and content in a 300-file game-style fixture,
  respected the Git ignore and symlink constraints, and picked up created,
  changed and deleted files. The follow-up probe recorded 2.41 seconds
  through Finder startup including Pi startup, 4 ms for a warm FFF
  content lookup and 11 ms for a ripgrep subprocess. A broader
  repository or coding comparison remains open.
- VCC compacted a generated transcript estimated by Pi at 29,742 tokens
  and retained all four markers. The isolated RPC run took 4.90 seconds
  including startup and issued zero model HTTP requests. This verifies
  the extraction path. In the separate live run, compaction took 5.30 s
  including startup. Cyber-Tiel recovered 4/4 markers after restarting in
  72.55 seconds. The resumed turn processed 42,646 fresh input tokens and
  reused zero cache tokens. It used no recall-tool call. Times include
  waiting for the shared router. A controlled native comparison is open.
- The first native context run ended before its asynchronous RPC result.
  The benchmark now waits for the response before closing stdin. A local
  mocked streaming backend verified the corrected runner and persisted
  summary. This run does not measure model performance. The shared slot
  was still busy with other work when the first evaluation window closed.
- SoL-Pi, BetterCompaction, Condense and Dynamic Footer loaded in separate
  RPC sessions. Startup alone establishes neither performance nor
  compatibility with other extensions.
  [Extension and overlap details](PI_EXTENSIONS.md)

The first V2 MetalVault run used the optional Lens settings and the
earlier pytest prompt. It reached a 420-second timeout after two model
responses and three tool calls. Four inference completions appeared in the
server journal during the interval. Another request processed more than
150,000 fresh prompt tokens in the shared slot. The run is excluded from
the performance comparison. The dedicated Python test runner now uses
the fixture's standard-library unittest suite to remove that dependency
from subsequent isolated runs.

The interactive TUI displayed the Cyber-Tiel profile and Build status.
A synthetic session restored 51 messages and forked them into a distinct
session ID.
The opt-in MCP relay returned HTTP 200 on initialization for all three
services and HTTP 403 for a Deep Research tool call. These checks cover
startup, protocol connectivity and routing policy.

## Follow-up with an idle router

The corrected RPC runner completed the same synthetic 32K target for all
three engines. Pi estimated the starting transcript at 29,742 tokens.
These are single observations with thinking off and zero cache hits on
the resumed request. The total includes both Pi process startups.

| Engine | Compaction | Restart and continuation | Total | Fresh continuation input | Markers recovered |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native | 38.99 s | 49.47 s | 88.46 s | 33,790 | 4/4 |
| BetterCompaction 1.3.1 | 40.23 s | 48.09 s | 88.32 s | 33,774 | 4/4 |
| VCC 0.11.2 | 4.07 s | 60.80 s | 64.87 s | 41,714 | 4/4 |

BetterCompaction handled the request through its extension hook and
reported zero cache-read tokens for the summary. The separate
`--prime-cache` runs warm the prefix with an acknowledgement turn before
measuring compaction. The prime is reported separately so its cost remains
visible. The results file records journal timings for each measured phase
where available.

The first completed V2 MetalVault run took 210.14 s with eight model
responses and seven tool calls. All 70 tests and the regression passed.
The file-diff gate rejected the run because Pi Lens wrote eight log files
under `.pi-lens-probe-home` in the temporary project. The launcher now
pins `PI_LENS_HOME` to its isolated state directory, and the acceptance
probe checks the workspace for log spillover.

For the primed 32K workload, each engine first ran an acknowledgement
turn. Native compaction and continuation then took 96.83 s with four
markers recovered. BetterCompaction took 87.92 s and recovered four
markers. Its summary reported zero reused tokens and the server
processed 17,526 fresh tokens, compared with 17,175 for native.
Both resumed requests had zero cache hits. VCC took 48.09 s with
zero requests during compaction, but recovered only three markers.
The marker-only comparison leaves recall tools disabled for every engine.

The same-directory 32K repeats exposed a different cache condition.
On the first repeat, native and BetterCompaction took 75.32 s and
75.45 s through restart and continuation. The second repeat took
61.60 s and 59.05 s, respectively. Both summary requests processed
just four fresh tokens on that second repeat. BetterCompaction reported
14,771 cached tokens. Both resumed requests still had zero cache hits,
and all four runs recovered four markers. Identical summary requests
could reuse the prefix with either engine.

The VCC tool itself recovered the original compiler marker after
compaction, process restart and a fork in a separate isolated test
with a mocked provider. The marker-only test with a nominal 64K
transcript started at a Pi estimate of 59,678 tokens. Native recovered
four markers in 161.07 s. VCC recovered three in 66.92 s and used
44,419 fresh continuation tokens, compared with 34,371 for native.
Both engines declined manual compaction at the nominal 16K target
because the transcript fit inside the 20K recent-message budget.

The 32K coding fixture required a stable replay order, first-wins
duplicate handling and an exact checkpoint field. The agent resumed
in a new process and could edit two Python files. Native passed the
independent acceptance in 178.06 s. VCC took 128.29 s and recovered
all four markers, but its two-file change failed independent
acceptance. Native stays the default. Marker recall alone missed a
coding regression on this workload.
[Raw phase timings](../benchmarks/results/pi-harness-v2-2026-11-20.json)

On 21 November, a clean BetterCompaction run passed all three independent
checks and recovered all four markers in 181.60 s. It made nine requests,
compared with eight for native. The native run took 178.06 s. These are
single coding observations on the same fixture. An earlier BetterCompaction
run overlapped an extra request from the first MCP catalog probe. It is
excluded from the timing comparison. The corrected catalog command
completed with zero model requests.

With Pi configured for medium thinking, BetterCompaction took 89.62 s
and native took 127.50 s through marker recovery. Both recovered 4/4.
The summary used 600 generated tokens with BetterCompaction and 930
with native. The journal also measured different prefill and decode
rates across the runs. This is one marker-only pair. It leaves the
size of any repeatable gain and the effect on coding quality in medium
thinking open.

The calibrated 128K and 192K transcripts contained 130,333 and 196,308
tokens. Native compaction and restart took 196.65 s and 317.15 s,
respectively. Both runs recovered all four markers. This was manual
compaction on the full generated transcript. The server processed
96,507 and 162,092 fresh tokens for the two summary requests.

In the near-256K run, the tokenizer counted 245,028 tokens in the
synthetic transcript. The actual priming response reported 246,957
tokens including its output and triggered native compaction. The
server processed 214,548 fresh summary tokens at 725.31 tokens/s and
decoded 674 tokens at 5.93 tokens/s. These two server phases took
409.42 s combined. The priming command took 804.54 s including that
compaction. A new Pi process recovered all four markers in 39.80 s
with 32,283 fresh input tokens. No phase recorded a cache hit.
[Near-window phase data](../benchmarks/results/pi-harness-v2-2026-11-20.json)

The matched MetalVault runs used identical source files, the same
unittest prompt and requested seed 42. All four passed the 70 tests,
independent duplicate-ID check and exact file-diff gate. All first
requests had zero cache hits. The V1 reference replayed the saved
V1 profile with Node 22 through the same coding-only relay. The V2
runs used Node 24 and the managed launcher.

| Profile | Task wall time | Model responses | Tool calls | Fresh input | Cache-read input | Output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 reference | 135.07 s | 7 | 9 | 24,072 | 119,985 | 2,264 |
| V2 default | 74.09 s | 9 | 8 | 17,425 | 130,823 | 1,146 |
| V2 without Lens context insertion and read expansion | 72.09 s | 9 | 9 | 17,222 | 131,522 | 1,086 |
| V2 with thinking off | 69.08 s | 10 | 9 | 17,272 | 146,161 | 908 |

The default V2 run used 45% less wall time on this fixture and made
two more model calls. Fresh input fell by about 28%, and output fell
by about 49%. The Lens variant saved two seconds in one run and recorded
two tool failures. Turning thinking off saved five seconds and required
one more model response. Both defaults stay in place. These paired
observations leave repeatability across tasks and the effect of individual
V2 changes open. [Measurement data](../benchmarks/results/pi-harness-v2-2026-11-20.json)

V1 and V2 default both ran on the low-power platform profile and peaked
at 6,841 MiB VRAM. Peak reported context fell from 26,192 to 18,311
tokens. First client delta took 17.65 s on V1 and 16.82 s on V2. These are
client timings. The JSON records separate server prefill and decode rates,
GPU samples and the router cgroup's CPU time for each run.

In the isolated SoL-Pi preflight, Action Fusion returned an unsupported
command backend because Permission Modes owns bash. A separate
ObservationPack test used a mocked provider and real Pi tool dispatch.
It projected an 18,069-byte successful result to 1,401 bytes, retained
the original and retrieved the compiler marker through recall. A result
marked as failed stayed in full. An earlier test with a restricted
tool list kept the full result. Treat projection and recall as verified
for the direct mechanism with the tested tool set. Live workload savings
remain open.

The final managed-launcher smoke check passed on live Cyber-Tiel, and
six offline relay tests passed, including MCP exposure and policy parity.
The isolated sandbox checks covered project writes, sibling isolation,
read-only shared skills, credentials, child processes and the coding-only
relay. Pi Lens left no log files in the project. With Pi's normal project
trust enabled, a separate mocked-provider tool test used the installed
TypeScript language server, returned a TS2322 diagnostic and found the
fixture symbol with `symbol_search`. The launcher disables Lens's
automatic tool and language-server installers.
Another isolated mocked-provider test wrote a tracked file through Pi
and restored its exact bytes through Workspace History's `/undo`.
The Git worktree was clean afterward. The Todo Agent recovered a
pending task from a saved session in a new Pi process.
An opt-in Codemode run against the mocked provider combined a project
write and read in Build. The script could not read a sibling fixture,
and Plan denied the Codemode call before it executed.
Doctor detected the pinned extension list and both sandbox dependencies.
It reported context and edit overlaps in a disposable project configuration
that selected Condense and Hashline.

## Repeat the coding and context tests

```bash
./setup.sh benchmark pi --repeat 3
./setup.sh benchmark pi --variant lens-lean --repeat 3
./setup.sh benchmark pi-context --target 32768 --repeat 3
```

The MetalVault runner restores a fresh copy before each run, validates
the file diff, runs 70 project tests and executes an independent duplicate
ID regression. It gathers client token counters, tool counts and time
from turn start to first streamed delta. The latter is a client latency
measurement. It reads prefill and decode rates from the llama.cpp journal
and samples GPU use during the run. Journal request counts and router PID
changes help identify interference. The shared-slot benchmark records
first-request cache counters. For a true cold/warm A/B, reserve a dedicated
idle measurement window and verify the cache state on each first request.

The context runner has a separate target for each workload size.
`--calibrate` uses the local chat template and tokenizer to size the
transcript before inference. Calibration is automatic at 128K and
above. This count excludes the Pi-specific system text and tool schemas.
Use `--coding` to resume a small two-file replay task instead of just
retrieving the markers. The expected replay order, duplicate handling and
checkpoint format appear early in the transcript. The independent
grader runs outside the agent's project and checks the two-file diff.
Use it to measure the elapsed time from compaction through a new process's
continued response. Keep one candidate active per run. Record the measured
token count, the requirement markers, and the continuation tool calls.
[Context procedure](CONTEXT_ENGINEERING.md#compaction-comparison)

Only MetalVault contained source among the eight planned benchmark
directories during the inventory. The Astro, React, Defold, Godot,
security, existing-codebase and long-running project suites remain open.
The generated context fixtures cover marker retention, process restart
and a small replay implementation. They leave domain-level work and
the remaining integration gates open.
