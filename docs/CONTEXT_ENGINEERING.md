# Context engineering

Coding Long 256K exposes 262,144 context tokens and an 8,192-token generation
budget. One local model handles coding and native compaction. The native
engine uses `reserveTokens: 39322` and `keepRecentTokens: 20000`.
When the context approaches the reserve, Pi can compose a summary and retain
recent messages. Use `/compact` to request compaction during an interactive
session. [Pi profile](../config/pi.json.in)

## Keep the working context small

Begin with targeted search and Pi Lens symbol navigation. Read the relevant
range before reading the whole file. Load a skill when its instructions
apply. After a test run, keep the failing test name, error, path and exit
status. Preserve acceptance criteria, decisions, open work and concrete
test outcomes before compacting. There are no default third-party output
filters.

Measure the input a tool adds end to end. In the historical 400-line
fixture, both variants produced the correct answer. The native tool set
used 9,826 peak context tokens and took 49 seconds. The V1 extension set
used 16,951 peak context tokens and took 50 seconds.
[Historical A/B record](../benchmarks/results/pi-ext-ab-2026-11-19.json)

## Compaction comparison

BetterCompaction tries to keep the model-facing message prefix while
appending a summary request. Its opt-in thinking setting changes the
request. Confirm actual server cache reuse during both the summary and the
next request. VCC extracts a summary without requesting generation. Its
recall tool operates on the local session transcript. SoL-Pi's
ObservationPack and Online Context Compact both change the projected
context. Its Evidence-Preserving Reducer can request another inference
call and requires explicit local routing. Pi Condense also has its own
tool-output summarization path. Keep these engines isolated during
comparison. [Reviewed versions and overlaps](PI_EXTENSIONS.md)

Native compaction stays the default. BetterCompaction reported zero summary
cache reads after the separate priming turn. In a second same-directory
repeat, both engines processed just four fresh summary tokens. Each next
request still needed a new prefill. VCC compacted faster but lost one
marker in the primed 32K and cold 64K runs. On the 32K coding task, VCC
recovered all four markers and still failed independent acceptance.
Native passed that task. [Benchmark results](BENCHMARKS.md)

```bash
./setup.sh benchmark pi-context --target 32768
./setup.sh benchmark pi-context --target 32768 \
  --extension-root /path/to/reviewed/vcc-fixture \
  --extension node_modules/@sting8k/pi-vcc/index.ts --recall-tool vcc_recall
```

Use `--thinking medium` for the supported thinking comparison on Cyber-Tiel.
Use `--prime-cache` to warm the prefix before compaction and measure priming
separately. Use `--coding` to measure an actual edit and independent tests
after compaction.
The generated transcript contains four known requirements. The runner
records whether compaction completed, which markers survived the summary,
and whether a new Pi process recovered the markers with the allowed tools.
Use the nominal `--target` values 16384, 32768, 65536, 131072, 196608 and
245760. Report the actual observed token count and distinguish startup from
model work. The runner measures manual compaction or records automatic
compaction during priming, then starts a new process to test continuation.
Evaluate session branching and the coding acceptance separately.
[Benchmark results and gaps](BENCHMARKS.md)
