# Model Comparison on the Framework Laptop 16

As of 19. November 2026. GB denotes decimal file size. GiB and MiB denote binary memory values. The model cards state the training or metadata context. The usable context length comes from the local tests.

## Model cleanup

The later performance series includes a new baseline for all three models, THP-A/B, batch and cache comparisons, and a full cold 256K prefill. In the new offline sign-off, Codex passed at 32K and Claude Code at 128K. The measurement conditions and Claude Code's 32K compression abort are evaluated separately. The 256K remeasurement reached 6:34 minutes cold and 0,67 seconds to the first token under identical repetition. [Performance measurement](PERFORMANCE_OPTIMIZATION.md)

Gemma 4 26B A4B QAT, Cyber-Tiel 35B A3B, and Gemma 4 12B StyleTune make up the local model inventory with 37,14 GB in total. Both coding wrappers use Cyber-Tiel by default.

Model cleanup affects files under `~/models/gguf/`. The Exclusive column gives the exclusively occupied blocks measured before removal on Btrfs.

| Datei | Dateigröße | Exklusiv | Stand |
|---|---:|---:|---|
| `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | 2,33 GiB | 0 GiB | Entfernt |
| `gemma-4-12b-it-qat-q4_0.gguf` | 6,50 GiB | 6,50 GiB | Nach bestandener Claude-Abnahme entfernt |
| `LFM2.5-24B-A2B-Q4_K_M.gguf` | 13,53 GiB | 13,53 GiB | Entfernt |
| `mtp-Cyber-Tiel-Coder-35B-A3B.gguf` | 1,38 GiB | 1,38 GiB | Entfernt |
| **Gesamt** | **23,73 GiB** | **21,41 GiB** | **21,41 GiB freigegeben** |

Atelier uses a separate Qwen path with its own inode and jointly occupied Btrfs data blocks. The image pipeline still requires its own file. No model projector was found in the llama.cpp model library.

### Cyber-Tiel versus the Ledger task

The two CLI tests used the same original Ledger fixture and the same task contract as the historical Gemma-QAT runs. For Cyber-Tiel, Q8_0 K/V, 32K context, and 256 thinking tokens were the router default. The second Claude run listed here used a shortened system prompt. The models ran in separate tests within the existing local network isolation.

| Client | Ergebnis | Dauer und Durchsatz |
|---|---|---|
| Codex 0.169.0 | PASSED. Bugfix, helper function, six unit tests, and independent contract check. 46.699 prompt tokens were reused from the cache. | 403,31 s. First prefill 8.128 tokens at 73,6 t/s. Decode per turn 7,15–14,26 t/s. |
| Claude Code 2.1.326 | FAILED. The first run ended at the time limit after 520 s. The shortened run read all four files. The independent check of the unchanged code failed. | 550,00 s. First prefill 3.065 tokens at 8,47 t/s. The first full decode turn reached 2,09 t/s. |

Active system load and read access of up to roughly 720 MiB/s observed in `vmstat` coincided with the slow runs. In an earlier turn of the same sign-off, Cyber-Tiel reached 22,33 decode t/s. The 20–30 t/s range was not reliably reachable in the full coding runs.

After the authorized restart of the Stageground dev server, available RAM in the same system rose from about 4 to 18 GiB. Claude Code repeated the Ledger task with the normal system prompt and `--effort low`. The offline run passed all four unit tests and the independent contract check in 288,61 s. The first prefill processed 5.460 tokens at 359,08 t/s. Across 14 decode turns the values were 49,38–56,44 t/s, median 51,89 t/s. The measurement temporarily used the performance profile.

After both sign-offs, `coding-fast` takes the verified Cyber-Tiel preset with 32K and Q8_0 K/V. The earlier measurements show the throughput loss under tighter working memory.

### Repeat measurement under the normal power profile

After the switch to `coding-fast`, the native chat API answered the same retrieval fixture at 8K and 16K. This ran on the original laptop profile `low-power`. The measurement captures a structured answer over repository data.

| Kontextprofil | Prompt-Tokens | Wiederverwendet | Prefill | Decode | Retrieval |
|---|---:|---:|---:|---:|---:|
| 8K | 7.819 | 0 | 374,49 t/s | 44,69 t/s | 3/3 |
| 16K | 16.024 | 179 | 379,78 t/s | 43,18 t/s | 3/3 |

The tight 512 MiB CUDA reserve with Q4_0 K/V raised decode throughput from 9,70 to 10,99 t/s in the isolated short benchmark before the Stageground restart. The freed working memory brought the larger effect. The final profile keeps the 1.024 MiB CUDA reserve and Q8_0 K/V.

## Historical selection before the downloads

| Kriterium | Gewicht | Grundlage der Auswahl |
|---|---:|---|
| Coding quality | 25 % | Model card and repository benchmark with a matching harness, later locally confirmed correctness and unit tests |
| Agentic coding and tools | 20 % | Tool template, local API parser, multiple tool rounds in Claude Code and Codex |
| Speed | 20 % | Prefill and decode measured separately, plus task completion time |
| Long context | 15 % | Candidates from 128K upward preferred. Retrieval and reasoning over long inputs count |
| Memory need | 10 % | GGUF size, CPU/GPU split, KV/working buffers, and measured peak |
| Stability | 5 % | CUDA loading, model switching, tool and context errors |
| License and maintainability | 5 % | Origin, license chain, upstream format in use, documented template |

The weights steer the selection. For pure research candidates, shared local measurements are missing, so those have no numeric overall score yet. LFM took the first coding spot because of its compact active parameter count, the official quantization, and the agent training. Gemma 26B is the comparison for quality, MoE, and QAT. Gemma 12B serves as the smaller official comparison for everyday use and the first agent tests. The second round adds Cyber-Tiel and StyleTune.

## Researched coding and everyday models

| Modell und Quelle | Herkunft, Architektur und Nennkontext | Quantisierung und Größe | Template, MTP und Bewertung |
|---|---|---|---|
| [LiquidAI LFM2.5-24B-A2B](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B-GGUF) | Official LiquidAI GGUF from 09.10.2026. `lfm2moe`, 24B total, about 2B active, 4 of 64 experts. 10 Attention and 30 Conv blocks. 131.072 tokens. [LFM Open License 1.0](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B/blob/main/LICENSE) | Q4_K_M 14,53 GB. Q4_0 13,58 GB, QAD Q4_0 13,58 GB, Q5_K_M 17,03 GB. | Embedded LFM tool template. Published LiveClaw results are manufacturer measurements. Mixed Attention/Conv states determine context, caching, and speculation. No MTP head is documented for the selected file. |
| [Gemma 4 26B-A4B IT QAT](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf) | Official Google QAT GGUF from 01.05.2026. 25,23B GGUF tensor parameters, about 4B active, 8 of 128 experts. 5 full Attention blocks at 30 layers, otherwise SWA. 262.144 tokens. Apache 2.0. | QAT Q4_0 14,44 GB. The separate projector has 1,19 GB. [Community PTQ](https://huggingface.co/bartowski/google_gemma-4-26B-A4B-it-GGUF) IQ4_XS 14,21 GB, Q4_K_M 17,04 GB, Q5_K_M 19,32 GB. | Gemma tool template with optional reasoning. QAT and PTQ rest on different checkpoints. The community PTQ card lists assistant heads whose suitability for the official QAT would need separate proof. |
| [Gemma 4 12B IT QAT](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) | Official Google QAT GGUF from 05.06.2026. 11,91B dense, 8 full Attention blocks at 48 layers, otherwise SWA. 262.144 tokens. Apache 2.0. | QAT Q4_0 6,98 GB. Separate projector 0,175 GB. | Gemma tool template. For larger profiles, VRAM buffers and context rule out equating file size with full offload. |
| [Cyber-Tiel-Coder MiniPlus V2.1](https://huggingface.co/IsValorum/Cyber-Tiel-Coder-35B-A3B-APEX-I-MiniPlus-V2.1-GGUF) | IsValorum community quantization from 29.09.2026. Derived from ablated Ornith 1.5. `qwen35moe`, 34,66B GGUF parameters, 3B active, 262.144 tokens. The card reports MIT and refers to the base chain. | Tensor-wise APEX-I MiniPlus 14,75 GB, MTP sidecar 1,48 GB. A more lowly quantized NanoPlus exists separately. | Embedded Jinja template with XML/JSON tool format. Manufacturer values for Perplexity and the SWE subset are hints. On this machine, the local defensive code review counts. |
| [KAT-Coder V2.5 Dev](https://huggingface.co/Kwaipilot/KAT-Coder-V2.5-Dev) | Original from Kwaipilot, 23.07.2026, Apache 2.0. Qwen3.6-35B-A3B fine-tune, 8 of 256 experts, 10 full Attention blocks at 40 layers, 262.144 tokens. | Original safetensors, [Community GGUF](https://huggingface.co/bartowski/Kwaipilot_KAT-Coder-V2.5-Dev-GGUF) IQ4_XS 18,81 GB, Q4_K_M 21,39 GB, Q5_K_M 25,02 GB. [Abliterated Community GGUF](https://huggingface.co/PhillyLabs/KAT-Coder-V2.5-Dev-35B-A3B-ABLITERATED-UNCENSORED-PHILADELPHIA-CLASS) Q4_K_M 21,17 GB. | Kwaipilot evaluates with Claude Code or its own harness. Original configuration `mtp_num_hidden_layers=0`. The [community MTP output](https://huggingface.co/offmonreal/KAT-Coder-V2.5-Dev-MaxQuality-MTP-GGUF) is a divergent conversion. More CPU expert memory than Cyber/LFM. |
| [Tiel-Coder MiniPlus V2.1](https://huggingface.co/IsValorum/Tiel-Coder-35B-A3B-APEX-I-MiniPlus-V2.1-GGUF) | Community quantization from 22.09.2026, from the [Tiel quant of Ornith 1.5](https://huggingface.co/peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF). `qwen35moe`, 35,51B GGUF parameters, about 3B active, 262.144 tokens. The card reports MIT. | APEX-I MiniPlus 15,23 GB. The sister project offers additional quantizations and MTP outputs. | Jinja tool template. Comparison candidate for ordinary SWE tasks, instruction fidelity, and repeated tool calls. The published SWE sample covers 25 tasks. |
| [Qwen3.8-35B-A3B Distill](https://huggingface.co/empero-ai/Qwen3.8-35B-A3B-Distill-GGUF) | Openly published distillation by empero-ai, GGUF from 16.09.2026, Apache 2.0. `qwen35moe` with 8 of 256 experts, about 3B active, 10 full Attention blocks at 40 layers, 262.144 tokens. | IQ3_M 16,34 GB, IQ4_XS 19,63 GB, Q4_K_M 21,71 GB, Q5_K_M 25,35 GB. [Abliterated Community GGUF](https://huggingface.co/IsValorum/Qwen3.8-35B-A3B-Distill-MTP-APEX-I-MiniPlus-V2.1-Abliterated-GGUF) 14,66 GB plus Q4_0 and Q8_0 MTP sidecars. | Embedded Qwen tool template. The original configuration reports one MTP layer. Most economical variants trade weight precision for GPU space. Effects of the abliteration remain locally open. |
| [Sage A1.5](https://huggingface.co/InternScience/Sage-A1.5-Q4_K_M-GGUF) | InternScience original from 15.10.2026, official GGUF from 21.10.2026, Apache 2.0. `qwen35moe`, 35,51B parameters, 8/256, 262.144 tokens. | Q4_K_M 21,71 GB, official Q8 output and community quants available. | Newer coding candidate with a native MTP layer per the configuration. Embedded tool template. Held back due to weight size and measurement priority. |
| [Laguna XS 2.1](https://huggingface.co/poolside/Laguna-XS-2.1-GGUF) | Poolside original and official GGUF from June 2026. `laguna`, 33B/3B, 8/256, 262.144 tokens, OpenMDW 1.1. | Q4_K_M 20,27 GB, BF16 clearly larger. | Poolside evaluates agentic SWE tasks in its own environment. The model card points to [Upstream PR 25165](https://github.com/ggml-org/llama.cpp/pull/25165) for support. Utilization and the tool parser remained locally open. |
| [Nemotron 3.5 Lightning](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF) | NVIDIA original with ggml-org conversion from 11.08.2026. GGUF `nemotron_h_moe`, 31,58B parameters, about 3B active, 6 experts per token. The GGUF reports 1.048.576 and the original configuration 262.144. NVIDIA model license. | Official NVIDIA BF16/NVFP4 and further community formats exist. | Hybrid state, native template, and speculative variant outputs warrant a separate test. Context metadata is contradictory and no proof for the laptop. |
| [Horus Cyber Nano 1.0](https://huggingface.co/tokenaii/Horus-Cyber-Nano-1.0-GGUF) | TokenAI states 16B total parameters and MoE. Candidate for defensive audits, no local scoring. | Provider GGUF per the model card. | Technical ranking deferred until CUDA compatibility and reproducible defensive quality are proven. |

For Qwen35-MoE, the model configuration yields about 1,4 GiB Q4_0-KV at 262.144 tokens with 10 full Attention blocks and 2 KV heads of 256 dimensions. This computed value covers only K/V. Recurrent states, GGUF, CUDA context, compute buffers, and checkpoints are added on top. The router holds one model at a time. NVIDIA availability is checked before each measurement series.

## Writing models

The writing probe rates English prose, character voice, consistency, dialog, and adherence to concrete constraints. Tool calls do not count here.

| Kandidat | Kategorien und Metadaten | Auswahl |
|---|---|---|
| [Gryphe StyleTune 12B](https://huggingface.co/Gryphe/Gemma-4-12B-StyleTune) | Gemma-4 writing fine-tune, [community Q4_K_M 7,95 GB](https://huggingface.co/mradermacher/Gemma-4-12B-StyleTune-GGUF), Apache 2.0, 262.144 nominal. | Comparison with Gemma QAT on the same writing task. |
| [Gemma The Writer 9B Heretic](https://huggingface.co/DavidAU/Gemma-The-Writer-9B-HERETIC-Uncensored-Abliterated) | Revised abliteration of a Gemma-2 writing merge. [Q4_K_M 5,76 GB](https://huggingface.co/mradermacher/Gemma-The-Writer-9B-HERETIC-Uncensored-Abliterated-GGUF), 8192 nominal. Observe origin and Gemma-2 license terms. | Comparison candidate for short English stories and dialog. |
| [Restless Quill 10B](https://huggingface.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF) | Gemma-2 writing merge with an Uncensored marking. IQ4_XS 5,87 GB or Q4_K_M 6,10 GB, 8192 nominal. The quant repo reports Apache 2.0. | Optional second prose comparison once the license chain is clarified. |
| [Himeyuri Magnum 12B HereticLoRA](https://huggingface.co/yamatazen/Himeyuri-Magnum-12B-HereticLoRA-Q4_K_M-GGUF) | Community fine-tune and Q4_K_M 7,48 GB. The GGUF reports 1.024.000 tokens. The quant repo carries no license statement of its own. | No download. Style and license chain remain open. |

## Historical local measurements

The table uses the official `llama-bench` output. In these short tests, prefill and decode are measured separately. The decode value starts without a long prompt. The memory columns show peak RSS including file-backed mappings and the total dedicated GPU peak including the desktop. The power values are observed GPU peaks in 500 ms samples. Small models ran in the original Fedora profile Power Saver. Large models ran during a temporary performance lease.

| Modell | Quant | Prefill 8K / 16K t/s | Decode t/s | RAM Peak | VRAM Peak | GPU-Spitze | Coding und Tools |
|---|---|---:|---:|---:|---:|---:|---|
| Qwen3 4B Instruct 2507, existing file | Q4_K_M | 2.651 / 2.573 together with 96 decode tokens each | — | 2,80 GiB | 5.084 MiB* | 101,1 W | API smoke and small offline chat probe |
| Gemma 4 12B IT | QAT Q4_0 | 1.528 / 1.335 | 40,70 | 7,08 GiB | 6.924 MiB | 100,6 W | Bugfix and refactor with both CLI agents |
| Gemma 4 26B A4B IT | QAT Q4_0 | 535 / 528 | 54,73 | 14,21 GiB | 6.778 MiB | 58,8 W | Benchmark with GPU/CPU split |
| LFM2.5 24B A2B | Q4_K_M | 565 / 545 | 66,61 | 14,20 GiB | 6.804 MiB | 52,0 W | Long-context measurement further down |
| Cyber-Tiel-Coder 35B A3B | APEX-I MiniPlus | 417 / 563 | 66,59 | 14,55 GiB | 6.824 MiB | 65,5 W | 16K retrieval 3/3 and two-step tool chain passed |

*Sampler peak of the Qwen combined test: 5.084 MiB. The value is the raw device maximum. Qwen used two combined runs each, Gemma and LFM two repetitions per category. Cyber-Tiel used one run per category without additional warmup. Different starting states limit comparability.

### Practical coding fixture in an isolated network

| Client | Modell / Kontextgröße | Aufgabe | Verifizierte Unit Tests | Gesamtzeit |
|---|---|---|---:|---:|
| Claude Code 2.1.326 | Gemma 4 12B QAT / 32K | File analysis, global event deduplication, normalization of currency abbreviations, helper function, and regression tests | 4 passed | 177,8 s |
| Codex CLI 0.169.0 | Gemma 4 12B QAT / 32K | Equivalent task in a separate fixture, six confirmed shell calls | 5 passed | 85,6 s |

Both changes were verified independently with `python -m unittest discover -s tests -v`. Across several Claude coding turns, the actual decode rates were at about 25–26 t/s. Claude logged 16 agent turns and 4.079 emitted tokens. Codex logged 1.835 emitted tokens. Repeatedly submitted and cached prompt tokens are listed separately in the client traces.

### LFM2.5 on long repository-shaped inputs

All rows use the LFM profile loaded at 131.072 tokens, CUDA for the remaining tensors, all 40 MoE expert layers on the CPU, 1.024/512 batch/microbatch, and Q8_0 K/V. Reasoning was capped. Each row processes the prompt anew. The peak over the whole series was about 6,8 thousand MiB per `nvidia-smi` samples.

| Ziel | Tatsächliche Prompt-Tokens inkl. Template | Prefill t/s | Decode t/s | Erster Token | Erste sichtbare Ausgabe | Gesamt | Retrieval |
|---|---:|---:|---:|---:|---:|---:|---:|
| 8K | 7.499 | 450,0 | 46,4 | 16,7 s | 18,1 s | 24,9 s | 3/3 |
| 16K | 15.815 | 489,5 | 45,2 | 32,4 s | 33,8 s | 40,9 s | 2/3 |
| 32K | 32.195 | 447,6 | 42,9 | 72,0 s | 73,4 s | 80,9 s | 3/3 |
| 64K | 64.955 | 476,3 | 38,0 | 136,4 s | 138,3 s | 146,5 s | 2/3 |
| 128K | 130.475 | 459,9 | 35,1 | 283,8 s | 285,7 s | 294,7 s | 0/3 |

LFM passed the technical 128K run. The reproduction failed on this task. An earlier 16K run with automatic tensor placement and uncapped reasoning reached 36,5 decode t/s but emitted no visible solution within the 200-token budget. Suitability therefore counts response content as well as prefill and reasoning time.

### Offload and RAM

LFM at 4K with an explicit 26 CPU expert layers reached 567,1 prefill and 64,3 decode t/s. With 40 CPU expert layers it was 589,8 and 67,8 t/s in one pass. The long-context test therefore used all CPU experts. The local 128K run was called via the router in 1,24 s with an already warm file cache. The overall process of a benchmark additionally includes model loading, warmup, and repetitions.

### Multi-Token Prediction on Cyber-Tiel

Same 32K router window, same structured prompt with 16.024 tokens. The memory buffer was set from 1.024 to 2.048 MiB for the variant with the sidecar. This way the comparison covers the respectively runnable configuration including tensor fit.

| Modus | Prefill t/s | Decode t/s | Erster Token | Gesamt | Fakten | Toolkette |
|---|---:|---:|---:|---:|---:|---|
| Standard | 385,8 | 53,8 | 41,5 s | 43,2 s | 3/3 | bestanden |
| MTP-Sidecar | 312,9 | 53,0 | 51,2 s | 53,2 s | 3/3 | bestanden |

68 of 108 draft tokens were accepted. The measured task was slower with the sidecar. The regular coding profiles stay on standard inference. For repetition, the upstream options `--spec-type draft-mtp --spec-draft-model <Sidecar>` serve.

### Cyber-Tiel at 128K, 192K, and 256K

The three large prompts were processed in the same instance loaded at 262.144 tokens. CUDA fit, Flash Attention, 1.024/512 batch/microbatch, Q4_0 K/V, and capped reasoning applied throughout. The 128K and 192K aliases were loaded separately with their set context limits. The results rate three distributed facts and one rule from a repository-shaped input. The rule was correct in content. Individual file references in the 256K result were imprecise.

| Ziel | Prompt gesamt | Cache-Tokens | Prefill t/s neu | Decode t/s | Erster Token | Erster gesuchter Fakt | Gesamt | Fakten |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 128K | 130.651 | 0 | 558,7 | 12,32 | 233,9 s | 235,0 s | 240,8 s | 3/3 |
| 192K | 196.291 | 179 | 484,6 | 8,92 | 404,8 s | 406,3 s | 416,6 s | 3/3 |
| 256K | 261.688 | 195.775 | 413,3 | 7,11 | 159,7 s | 161,5 s | 173,5 s | 3/3 |

The 256K row is the continuation of the 192K prompt with 65.913 newly computed tokens. A 256K cold run has a different wait time. Live reuse depends on matching prefixes and recoverable hybrid states. In one intermediate state the router reported about 972 MiB against 512 MiB of allowed separate prompt cache. Active slot reuse at 256K still worked.

The long tests reserve space for the chat template and the response. A maximally configurable window therefore does not correspond to an equally large text input. These profiles suit targeted analyses with an acceptable wait time. For interactive coding, the shorter standard path was clearly more responsive.

In the extended Cyber-Tiel run, the observed peaks were 14,97 GiB RSS, 6.762 MiB VRAM, and 86,8 W GPU power draw. The startup measurement of the loaded 256K instance was 3,67 s. The short profiles needed 3,66 s without and 5,00 s with the sidecar in the MTP comparison, each including the router call and with a warm or partially warm file cache.

### Real source code in the 128K profile

Cyber-Tiel processed 100.708 measured archive tokens of real upstream source code from b12503 in a two-step run. The model found the reload endpoint, the comparison function for preset options, the reason for releasing the mutex, and the behavior of `load-on-startup` on reload. All four statements were checked against the source code. In the second turn, 49.433 tokens were reused and 51.480 were newly processed. Total duration 179,1 s, decode in the second turn 15,0 t/s. In addition, both local CLI clients answered with the expected test text in the same profile.

### NVMe and load paths

LFM Q4_K_M, CUDA plus 40 MoE expert layers on the CPU, one 4K prefill and 96 decode tokens. The filesystem stayed in its running state. The differing page-cache states limit the statement on isolated cold load time.

| Ladepfad | Prefill t/s | Decode t/s | Gesamt inkl. Laden | Peak RSS | Reportete Dateisystem-Eingaben |
|---|---:|---:|---:|---:|---:|
| mmap | 526,9 | 72,7 | 18,39 s | 14,20 GiB | 33.130.384 Blöcke |
| Direct I/O | 586,8 | 46,2 | 24,74 s | 8,46 GiB | 40.536.288 Blöcke |

The standard profiles use mmap. Direct I/O reduced the measured RSS but needed more time for the whole test. The filesystem or slot cache changes the provisioning of weights and precomputed prompt state. The measured decode rates stay dependent on GPU, host RAM, and context.

### Prose and defensive code review

Both writing profiles delivered the English station scene with the required dialog line and a physical action at the end. StyleTune distinguished the two character voices more clearly in dialog. Gemma 4 12B QAT generated faster in this probe (28,9 versus 19,2 t/s). The prose rating rests on one sample. For everyday use and research, QAT remains the fast choice; for English scenes, the specialized StyleTune profile is available.

In the local defensive review, Cyber-Tiel recognized the unsafe release on missing inputs and the requirement for non-empty, case-sensitive tenant IDs. The first fix proposal used direct key access and thereby left the missing-key edge case open. Model security recommendations remain subject to verification.

The separate slot test with Qwen3 4B stored 2.683 tokens in about 377 MiB in 78 ms. The model was unloaded and reloaded in 1,37 s. Restore took 60 ms. The following prompt used 2.663 cache tokens and needed 0,22 s including decode. The test state stayed limited to the test fixture. Persistent slots are off in normal chat operation.

## Human Writing with Gemma 4 12B StyleTune

As of 18. November 2026. Nine tasks measured once each with and without the skill on the same Q4_K_M GGUF and the same 16K profile on the RTX 5070. The baseline used the Gemma template from the model file; the second series added the skill. User texts and token budgets were identical per pair. Temperature 0,55, Top-p 0,90, Top-k 40, seed 90.210, thinking off and prompt cache off. Personal style samples and press texts in this test are synthetic.

The editorial review reads the answers pairwise. It considers narrative perspective, rhythm, variation, character voices, originality, and agreement with the supplied facts. The linter column counts the heuristic individual findings. For fictional texts, deliberate repetition and rhythm remain editorial decisions.

| Aufgabe | Wörter ohne / mit Skill | Linter-Befunde ohne / mit | Redaktioneller Vergleich |
|---|---:|---:|---|
| English Riff-Racers story | 1.048 / 1.072 | 5 / 4 | Both within the 900–1.200 target range with an open decision and recognizable voices. The baseline produces a contradiction around the driver. With the skill, Cleo's action decision at the timing desk is clearer, and the axle motif repeats strongly. The rain at the end stays without a transition. |
| Dialog on the ferry | 247 / 224 | 0 / 0 | Both within the target range. Bea and Rowan are distinguishable without naming. With the skill, her action at the radio set gives the interruption more consequence. The suddenly reported incident comes across as constructed. |
| English heavy-metal review | 290 / 296 | 0 / 1 | Both address the tempo. Both add an unsupported debut claim. With the skill, instruments and vocals contradict each other in the description of "Third Shift". In addition, the text makes it the only title with lyrics. The template restricts only the night-shift topic to this title. |
| German blog | 273 / 251 | 1 / 1 | Both name the planned 40 cm and switch from the requested first-person singular to we. Both add details outside the template. With the skill, the answer sits nine words below the minimum length. |
| English devlog | 202 / 168 | 1 / 0 | The concrete cornering scene works better with the skill. Both name the 90-second replay and the open multiplayer test but phrase the effect too definitively. Both stay below 220 words. |
| Refine boilerplate text | 44 / 27 | 0 / 0 | With the skill, the empty closing sentence is dropped. Both change "reduced" to "stopped" and thereby overstate the effect at the rehearsal room. |
| Preserve good text | 30 / 31 | 0 / 0 | The baseline strikes `me`. With the skill, the wording stays unchanged. |
| Protected facts, quote, numbers, and link | 49 / 47 | 0 / 0 | Heading, version, name, date, the 3,5-MB/s figure in its original format, quote, command, and Markdown link remain in both variants. Both turn the team-related test gap into an impersonal statement. |
| Personal style calibration | 157 / 169 | 3 / 3 | Both use recognizable text evidence and name uncertainties. With the skill, the profile has more reusable fields; individual entries go beyond the three evidence samples. |

| Messwert | Ohne Skill | Mit Skill |
|---|---:|---:|
| Decode, Median | 24,67 t/s | 23,50 t/s |
| Prompt-Verarbeitung, Median | 0,28 s | 2,88 s |
| Laufzeit aller neun Anfragen | 138,61 s | 164,08 s |
| Prompt-Tokens je Anfrage | 73–153 | 2.543–3.498 |
| Linter-Einzelbefunde gesamt | 10 | 9 |

The system context costs an additional **2.423–3.345 tokens** depending on the mode, median **2.725 tokens**. The runtime covers the HTTP request and the respective response length. For short revisions, the additional prompt processing is more noticeable. The creative-writing rules help with character work and with preserving an already good text. Factual texts with given facts still need a source and scope check. The comparison is a single measurement per task and proves no general quality gain.

Prompts, texts, timing answers, and linter findings are under `~/dev/github/localllma-setup/benchmarks/results/human-writing-ab.json`. The local cache holds the same measurement data in `~/.cache/llama.cpp/writing/benchmark-2026-11-18.json`.

### Source grounding and fact-checking

The follow-up repeated five nonfiction cases with `[fakten]` at the original sampling settings. The metal text still contained unsupported production details. The blog added room observations, and the devlog turned a successful test into a broad commitment. In the simple rewrite, "reduced" became "stopped" again. In the protected release text, the team-related test gap again shifted into an impersonal statement. In a control task without sources, the model reported the missing details.

In a second test, the existing Websearch MCP delivered the public RFC 2606. StyleTune extracted two supported facts and drafted from them. The draft kept the core facts and links and contained two additional interpretations. A separate audit order marked both. The corrected text matched the fact sheet on the checked statements. In a further test, the rewrite with an approved fact sheet explicitly preserved "reduced" and both original observations. [Primary source of the web test](https://www.rfc-editor.org/rfc/rfc2606.html)

The results show where a separate fact check helps. They prove no reliable error-freedom of the model. The raw data are under `~/dev/github/localllma-setup/benchmarks/results/human-writing-facts.json`.
