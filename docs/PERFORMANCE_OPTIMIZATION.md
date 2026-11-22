# Performance Measurement for llama.cpp

Measurement series from November 18 and 19, 2026. Tested on a Framework Laptop 16 running Fedora 44, llama.cpp b12503 (`4577932fa`), CUDA 12.8, and NVIDIA driver 615.78.08. The three installed GGUF files form the test basis.

## Baseline State

The production router uses `models-max = 1`. Starting values are 12 decode and 12 batch threads, 512/256 batch/microbatch, automatic CUDA placement with a 1.024 MiB reserve, Flash Attention, mmap, and a 512 MiB prompt cache. The coding profiles from 64K up use 1.024/512 and Q4_0 K/V. The 32K and writing profiles use Q8_0 K/V. The installed build provides up to 32 context checkpoints per slot and a default minimum spacing of 8.192 tokens. The spacing matters when older checkpoints are evicted. [Upstream server options b12503](https://github.com/ggml-org/llama.cpp/blob/b12628/tools/server/README.md)

The Ryzen AI 9 HX 370 has 12 physical cores and 24 logical CPUs. The topology reports two L3 groups with four and eight physical cores respectively. CPUs 0–11 cover one thread per core. Linux reports about 46,8 GiB of usable RAM with a high amount of pre-existing ZRAM usage. The benchmarks record process swap separately. Regular starts ran under the `low-power` power profile.

Baseline, the first A/B tests, and the long-context series ran under kernel 7.2.15. After a reboot, Fedora took over kernel 7.3.4. On November 19, the control pairs and hardware comparisons ran on this kernel with the same llama.cpp build and initially about 33 GiB of available RAM. Only runs from the same series are compared with each other.

The baseline uses the same repository-shaped retrieval task against the production router. TTFT starts with the HTTP request and ends at the first token. The measurements include the prompt tokens actually rendered in the model, including the writing rules additionally rendered for StyleTune.

| Profile | New prompt | Cache tokens | Prefill | Decode | TTFT | Total | Retrieval |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cyber-Tiel `coding-fast` | 7.640 | 179 | 364,47 t/s | 36,43 t/s | 21,12 s | 24,08 s | 3/3 |
| Gemma 26B `research` | 7.596 | 0 | 388,29 t/s | 38,30 t/s | 19,86 s | 22,19 s | 3/3 |
| StyleTune `creative-writing` | 10.321 | 0 | 970,56 t/s | 18,69 t/s | 10,89 s | 16,15 s | 3/3 |

## Transparent Huge Pages

Tensward reported fewer page faults when allocating memory for prompt states under multiple concurrent requests on H100 and L4. glibc can mark large anonymous allocations for THP with `glibc.malloc.hugetlb=1`. On this laptop, glibc reports 2.43, THP `madvise`, and the defrag policy `madvise`. The existing setting was sufficient for the test. The benchmarks kept mmap for the GGUF weights and changed only the environment variable of the temporary router and its model process. The six Cyber-Tiel runs were executed alternating A/B with fresh workers. [Tensward article](https://tensward.com/blog/huge-pages-llama-cpp) · [Technical report](https://github.com/Tensward/tensward/blob/main/docs/research/huge-pages.md) · [glibc](https://sourceware.org/glibc/manual/latest/html_node/Memory-Allocation-Tunables.html) · [Linux kernel](https://docs.kernel.org/admin-guide/mm/transhuge.html)

| Phase, 3 repetitions each | TTFT A / B, median | Total A / B, median | Minor faults A / B, median | AnonHugePages B, median |
|---|---:|---:|---:|---:|
| First prompt | 12,12 / 14,66 s | 13,34 / 15,86 s | 144.749 / 140.825 | 154 MiB |
| Edited prefix | 11,26 / 11,55 s | 12,59 / 12,88 s | 48.463 / 47.229 | 160 MiB |
| Identical follow-up prompt | 0,15 / 0,36 s | 1,42 / 1,64 s | 16.301 / 16.301 | 160 MiB |

A had 0 MiB AnonHugePages. The first A run had 103.414 major faults; the later A runs had 33 and 0 respectively. The starting warmth of the file cache is therefore identifiable as a confounder. The better A medians provide no evidence of a time gain from THP. Both groups passed all nine retrieval checks. The environment variable was verified in the router and the worker. The glibc tunable stays off in the production Cyber-Tiel profile.

For Gemma 26B and StyleTune, one additional A/B pair each followed, with three requests per variant.

| Profile | First prompt, TTFT A / B | Minor faults on first prompt A / B | Peak AnonHugePages B | Total A / B |
|---|---:|---:|---:|---:|
| Gemma 26B | 12,42 / 12,33 s | 119.847 / 744 | 1.112 MiB | 28,39 / 28,65 s |
| StyleTune | 8,12 / 8,06 s | 162.889 / 57.099 | 786 MiB | 20,49 / 20,46 s |

The larger page allocation and the lower fault counts produced no reliable time gain in these pairs. Production uses the Fedora `madvise` policy with the regular glibc settings.

## Full 256K Prefill

A fresh worker with Q4_0 K/V, 1.024/512 batch/microbatch, and 256K context processed 261.688 new prompt tokens with zero reused tokens. Prefill reached 465,37 t/s. The first token came after 562,76 s, the full answer after 576,33 s. Decode reached 6,93 t/s. The structured repository fixture delivered 3/3 searched facts. The measurement covered a cold **prompt context**. OS and file caches stayed in regular use during the test.

Shorter prompts in the same warm 256K worker followed. The distributed evidence shifts when the fixture grows. This is why only 179 tokens were reused per switch.

| Target | Total prompt | New prefill | Decode | TTFT | Facts |
|---|---:|---:|---:|---:|---:|
| 16K | 16.024 | 597,73 t/s | 33,58 t/s | 26,56 s | 3/3 |
| 32K | 32.434 | 580,34 t/s | 26,36 t/s | 55,69 s | 3/3 |
| 64K | 65.006 | 558,95 t/s | 18,36 t/s | 116,19 s | 3/3 |
| 128K | 130.651 | 522,06 t/s | 11,86 t/s | 250,14 s | 3/3 |
| 192K | 196.291 | 500,51 t/s | 8,95 t/s | 392,17 s | 3/3 |

Across the long-context series, observed peaks were 6.837 MiB VRAM, 83 °C, and 86,81 W on the GPU. CPU Tctl reached 67,25 °C; the readable fan sensor reached 3.536 rpm. The NVIDIA counter sample reported 0 µs of thermal throttling. Minimum available system RAM during the series was 16,52 GiB.

## MCP Latency

The direct test covered initialization and tool discovery on the existing Streamable HTTP endpoint, followed by three calls per tool. All 21 calls returned the expected content features.

| Tool | Median | Passed |
|---|---:|---:|
| Websearch `search_web` | 13 ms | 3/3 |
| Websearch `read_url` | 12 ms | 3/3 |
| Context7 `resolve-library-id` | 1.166 ms | 3/3 |
| Context7 `query-docs` | 977 ms | 3/3 |
| GitHub `get_latest_release` | 267 ms | 3/3 |
| Skills `read_text_file` | 14 ms | 3/3 |
| Skills `read_multiple_files` | 11 ms | 3/3 |

The repetitions for Websearch and `read_url` use the same query and include warm provider and service caches. Model prefill, tool selection, and approval time in the WebUI belong to a different measurement. The existing transports were kept for this measurement series.

## Prompt Cache and Conversation-Branch Return

Cyber-Tiel ran in the 128K profile. Each series started with a fresh worker, introduced two different repository branches, returned to the first, edited its prompt in the middle, and repeated the edited input. All other options were identical. The low 512-MiB limit evicted a 303,44-MiB state to make room for the other branch.

| Cache limit | Branch return, TTFT | Branch return, total | Cache tokens / new | All five requests | Peak RSS |
|---|---:|---:|---:|---:|---:|
| 512 MiB | 14,13 s | 15,58 s | 179 / 9.230 | 65,95 s | 14,92 GiB |
| 1.024 MiB | 0,18 s | 1,59 s | 9.405 / 4 | 52,46 s | 15,00 GiB |
| 2.048 MiB | 0,17 s | 1,59 s | 9.405 / 4 | 52,16 s | 15,01 GiB |
| 4.096 MiB | 0,19 s | 1,63 s | 9.405 / 4 | 53,08 s | 15,01 GiB |

At 1.024 MiB, the cache update on return took 56 ms. The whole sequence was 20,5 % shorter. The mid-sequence edit still incurred 9.242 new tokens. The benefit applies to resuming the earlier branch. For this fixture, 1.024 MiB was the smallest sufficient limit. A higher RAM limit does not reserve the full amount at model start.

The next day, the repeated pair in the 128K profile gave 14,30 s versus 0,17 s TTFT on branch return, again with 179 versus 9.405 cache tokens. Five requests took 81,54 s at 512 MiB and 60,87 s at 1.024 MiB. The first requests arrived with differently warm file caches. The comparison of the return phase shows the effect with weights already loaded.

For the 32K profile with Q8_0 K/V, the original prefill stayed practically equal. The larger cache limit won the time on the branch switch.

| 32K cache | First prompt prefill | Return TTFT | Cache tokens / new | All five requests | Peak RSS |
|---|---:|---:|---:|---:|---:|
| 512 MiB | 377,45 t/s | 23,68 s | 179 / 9.230 | 102,67 s | 14,76 GiB |
| 1.024 MiB | 377,67 t/s | 0,22 s | 9.405 / 4 | 79,15 s | 14,89 GiB |

## Context Checkpoints

The comparison covered the defaults against four checkpoints per slot and against a minimum spacing of 16.384 tokens. Each variant ran five requests with one switch and a later edited prefix. Reused tokens and restorations were equal across all three settings. In this build, the spacing only takes effect when selecting checkpoints for deletion. Production uses 32 checkpoints and a minimum spacing of 8.192 tokens.

| Profile | Default | Four checkpoints | Spacing 16.384 | Restorations per run | Cache tokens on return |
|---|---:|---:|---:|---:|---:|
| `coding-long-128k` | 65,95 s | 67,33 s | 67,04 s | 4 | 179 |
| `research` | 102,71 s | 100,25 s | 100,39 s | 3 | 1 |

## Threads and CPU Affinity

Each row is a fresh 32K Cyber-Tiel worker in the `low-power` profile with about 4.500 prompt tokens. One setting changed per row. The affinity mask `fff` allows one logical thread per physical core. All variants answered the three searched facts correctly. Peak RSS sat at 14,38–14,39 GiB; the VRAM peak was 6.780 MiB in each case.

| Setting | Prefill t/s | Decode t/s | Total | Worker CPU time |
|---|---:|---:|---:|---:|
| 12 / 12, baseline | 364,96 | 40,90 | 13,56 s | 27,64 s |
| 8 / 12 | 364,99 | 39,80 | 13,60 s | 23,08 s |
| 16 / 12 | 363,46 | 40,02 | 13,65 s | 33,08 s |
| 24 / 12 | 363,27 | 17,75 | 15,31 s | 79,03 s |
| 12 / 8 | 364,85 | 42,10 | 13,53 s | 26,82 s |
| 12 / 16 | 364,31 | 42,40 | 13,54 s | 27,48 s |
| 12 / 24 | 349,85 | 41,41 | 14,08 s | 30,94 s |
| 12 / 12 with affinity | 353,71 | 41,27 | 13,94 s | 28,05 s |

24 decode threads raised CPU time to almost three times the baseline and lowered decode by 57 %. The remaining changes shortened the run by at most 0,03 s. The router uses 12 / 12 with regular kernel affinity.

## Batch and Microbatch

The following single measurements compare the batch/microbatch combinations with the same test prompt. Each row begins with a loaded, fresh worker. The numbers include the request's prefix prefill.

| Cyber-Tiel 32K | Prefill t/s | Decode t/s | TTFT | Total | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 364,96 | 40,90 | 12,27 s | 13,56 s | 6.780 MiB |
| 1.024 / 256 | 353,16 | 40,31 | 12,68 s | 13,99 s | 6.780 MiB |
| 1.024 / 512 | 537,79 | 40,01 | 8,33 s | 9,68 s | 6.742 MiB |
| 2.048 / 512 | 541,80 | 40,15 | 8,27 s | 9,61 s | 6.742 MiB |
| 2.048 / 1.024 | 780,96 | 40,73 | 5,74 s | 7,02 s | 6.760 MiB |

The control pairs that followed used 9.409 new prompt tokens and switched from 512/256 to 2.048/1.024 twice. TTFT fell from 26,01 to 10,11 s and from 30,62 to 11,12 s across the pairs. The median of the full run fell by 59 %. Decode median was 38,28 and 35,41 t/s respectively. All four answers met 3/3 criteria. Measured worker peak RSS rose from 14,39 to 14,47 GiB.

| Coding 32K, median of two runs | Prefill t/s | Decode t/s | TTFT | Total | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 334,86 | 38,28 | 28,32 s | 29,57 s | 6.780 MiB |
| 2.048 / 1.024 | 890,14 | 35,41 | 10,62 s | 12,23 s | 6.760 MiB |

Combined with a 1.024 MiB cache, the 32K branch sequence took 38,39 s. The same sequence with 512/256 and 512 MiB needed 102,67 s. All five answers were correct. On branch return, 9.405 tokens again came from the cache; the first token came after 0,19 s. Decode in the combined run sat at 33,22–41,59 t/s. The advantage comes from faster prefill and reuse of the conversation state.

| Gemma 26B Research 32K | Prefill t/s | Decode t/s | TTFT | Total | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 311,26 | 37,58 | 14,86 s | 16,21 s | 6.694 MiB |
| 1.024 / 512 | 639,78 | 38,09 | 7,27 s | 8,62 s | 6.770 MiB |
| 2.048 / 512 | 634,40 | 37,09 | 7,36 s | 8,73 s | 6.770 MiB |

For Research, two series of three followed with the same prompt of about 9.900 tokens. 2.048/1.024 delivered about 9,4 s TTFT in both repetitions with complete retrieval. Worker peak RSS was 14,55 GiB. Device peak was 6.782 MiB VRAM.

| Research 32K, median of two runs | Prefill t/s | Decode t/s | TTFT | Total |
|---|---:|---:|---:|---:|
| 512 / 256 | 346,50 | 32,89 | 29,09 s | 30,58 s |
| 1.024 / 512 | 585,39 | 33,14 | 17,36 s | 18,93 s |
| 2.048 / 1.024 | 1.062,75 | 36,71 | 9,40 s | 10,72 s |

| StyleTune 16K | Prefill t/s | Decode t/s | TTFT | Total | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 910,37 | 17,70 | 7,94 s | 10,16 s | 6.814 MiB |
| 1.024 / 512 | 1.157,26 | 16,62 | 6,31 s | 9,39 s | 6.764 MiB |
| 2.048 / 512 | 1.155,09 | 16,09 | 6,30 s | 9,51 s | 6.764 MiB |
| 2.048 / 1.024 | 1.247,23 | 14,21 | 5,90 s | 8,69 s | 6.702 MiB |

For StyleTune, decode fell with each larger microbatch. For long writing tasks, output length is decisive. The writing profiles therefore use 512/256.

In the 128K profile for Cyber-Tiel, TTFT fell from 31,41 to 20,97 s with 15.734 new tokens. The two full answers took 33,75 and 23,88 s. Decode stayed practically equal at 27,81 and 27,54 t/s. Both answers met 3/3 criteria.

The combined 128K branch test needed 43,36 s versus 60,87 s with the same cache and 1.024/512. Five answers met all criteria. Resuming the first branch gave 0,23 s TTFT. The router used 9.405 cache tokens and recomputed four tokens. Both test series ran with a 128K window; the individual branches each held about 9.400 tokens.

## CUDA Placement and KV

Automatic placement honors the target reserve. `cpu-moe` places all expert weights on the CPU. `moe-cache-mib` uses the GPU cache present in the build for experts stored on the CPU. Q4_0 was tested as an alternative to the previous Q8_0 K/V quantization at 32K. Every variant shown answered its retrieval task correctly.

| Profile and change | Prefill t/s | Decode t/s | TTFT | Peak VRAM |
|---|---:|---:|---:|---:|
| Cyber-Tiel automatic, Q8_0 | 364,96 | 40,90 | 12,27 s | 6.780 MiB |
| Cyber-Tiel CPU-MoE | 250,16 | 31,68 | 17,89 s | 2.700 MiB |
| Cyber-Tiel 384 MiB expert cache | 322,59 | 37,06 | 13,88 s | 6.784 MiB |
| Cyber-Tiel 768 MiB reserve | 355,07 | 39,84 | 12,61 s | 6.978 MiB |
| Cyber-Tiel Q4_0-K/V | 348,45 | 38,94 | 12,85 s | 6.818 MiB |
| Cyber-Tiel KV on the CPU | 322,36 | 19,33 | 13,89 s | 6.816 MiB |
| Gemma 26B automatic, Q8_0 | 311,26 | 37,58 | 14,86 s | 6.694 MiB |
| Gemma 26B CPU-MoE | 292,70 | 35,04 | 15,78 s | 3.162 MiB |
| Gemma 26B 384 MiB expert cache | 394,82 | 17,37 | 11,83 s | 6.672 MiB |
| Gemma 26B 768 MiB reserve | 407,00 | 40,85 | 11,37 s | 6.970 MiB |
| Gemma 26B Q4_0-K/V | 406,93 | 35,89 | 11,38 s | 6.748 MiB |

CPU-MoE reached the lowest VRAM use and the longest task time. CPU KV brought Cyber-Tiel less than half of its original decode throughput. The lower CUDA reserve and Q4_0 on Gemma 26B each showed a prefill gain in one run under changed GPU memory occupancy. The batch comparisons reached higher throughput with 1.024 MiB reserve and Q8_0. The regular profiles use auto-fit with a 1.024 MiB CUDA reserve, Flash Attention, and Q8_0 at 16K and 32K or Q4_0 from 64K up.

## Power and Thermals

Fedora provides the profiles through UPower and TuneD. Balanced and Performance alternated three times. One pass used a fresh Cyber-Tiel worker, the same first prompt, an edited prefix, and an unchanged repeat. All six passes answered the three searched facts in every phase. The latencies are medians of the three passes. Sensor values are samples including model start.

| Profile | First prefill | Decode | TTFT | Three requests | CPU max. | GPU max. | GPU power median / max. |
|---|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 316,31 t/s | 51,00 t/s | 14,15 s | 28,28 s | 95,75 °C | 57,97 °C | 43,53 / 51,14 W |
| Performance | 297,64 t/s | 52,60 t/s | 15,03 s | 33,66 s | 97,62 °C | 54,69 °C | 40,61 / 55,83 W |

The median of the sampled all-core clock values was 2,36 and 3,30 GHz respectively. GPU clock median was 2.437 MHz for both. Fan maximum was 4.748 rpm. The single 128-MiB `memmove` probe reached 16,78 and 18,44 GiB/s of copied payload. It serves to place the host memory path. CPU package power and CPU throttle counters were not readable for the user process. The Performance profile brought no reproducible time gain in this prefill-heavy sequence. After the series, UPower again reported `power-saver` and the firmware `low-power`.

## Historical Profiles Before the 256K Unification

| Profiles | Batch / microbatch | Prompt cache | K/V |
|---|---:|---:|---|
| `coding-fast` | 2.048 / 1.024 | 1.024 MiB | Q8_0 |
| `coding-long-128k` | 2.048 / 1.024 | 1.024 MiB | Q4_0 |
| `research`, `deep-research` | 2.048 / 1.024 | 512 MiB | Q8_0 |
| `coding-long-64k`, `coding-long-192k` | 1.024 / 512 | 512 MiB | Q4_0 |
| `coding-cyber-tiel-35b` | 2.048 / 1.024 | 512 MiB | Q4_0 |
| The four StyleTune profiles | 512 / 256 | 512 MiB | Q8_0 |

| Optimization | Baseline | Optimized | Change | Quality | Decision |
|---|---:|---:|---:|---|---|
| 32K batch, first token at 9.409 tokens | 28,32 s | 10,62 s | −62 % | 3/3 per answer | Active |
| 32K batch and cache, five requests | 102,67 s | 38,39 s | −63 % | 5/5 answers per run | Active |
| 128K cache, return to the first branch | 14,30 s | 0,17 s | −99 % | 5/5 answers per run | Active |
| 128K batch, first token at 15.734 tokens | 31,41 s | 20,97 s | −33 % | 3/3 per answer | Active |
| Research batch, first token at 9.859 tokens | 29,09 s | 9,40 s | −68 % | 3/3 per answer | Active |
| Huge pages, Cyber-Tiel, first token | 12,12 s | 14,66 s | +21 % | 9/9 answers per group | Regular glibc settings |
| 24 Cyber-Tiel decode threads | 40,90 t/s | 17,75 t/s | −57 % | 3/3 per answer | 12 threads |
| Performance profile, three requests | 28,28 s | 33,66 s | +19 % | 9/9 answers per group | Original power profile |

The eleven aliases of that time used CUDA, mmap, Flash Attention, and one slot. The router loads at most one worker. The prompt-cache values are RAM limits. Eviction ends state reuse. Persistent slot states and MTP are disabled. The current 256K measurement is in the follow-up measurement. The 192K measurement uses the production values shown above.

## Real-World Check After Reboot

Both CLI clients received the same ledger task in separate local fixtures. They were to read the contract file, deduplicate globally by event ID, move currency normalization into a helper function, and run regression tests. The wrappers isolated the network and routed local requests to the router over the Unix socket.

| Client and profile | CLI result | Independent check | Duration | Decode median |
|---|---|---|---:|---:|
| `codex-local`, 32K | Passed, 13 completed shell tool calls | 5 unit tests and contract check passed | 116,24 s | 40,09 t/s |
| `claude-local`, 32K | Client abort after repeated context compaction | The written fix passed 4 unit tests and the contract check | 231,42 s | 39,20 t/s |
| `claude-local`, 128K | Passed, eight tool calls | 6 unit tests and contract check passed | 78,07 s | 34,14 t/s |

Codex reported 100.388 cache tokens across the session, Claude 16.322 at 32K and 34.338 at 128K. Sums across multiple turns can exceed the context window. The total durations include model calls and tool execution. The older CLI times belong to runs under differing system load. The direct comparison of settings is in the controlled batch and cache series.

The 128K practical test passed 100.708 tokens from four files of the pinned llama.cpp source state in two steps. Cyber-Tiel correctly explained the reload endpoint, the preset comparisons, the lock release, and the `load-on-startup` behavior from the source functions. The second turn reused 49.433 tokens and processed 51.480 new. The first and second prefill reached 874,11 and 782,28 t/s. The two requests together took 141,85 s. Decode in the second turn reached 14,42 t/s.

A separate tool-calling test in `coding-fast` selected two tools in sequence, each from the previous result, and returned the expected build ID with status. The three model calls together took 3,72 s.

Claude Code activated `backend-api-engineering` with its skill tool. Codex explained the skill's rules and confirmed file access in a second run with a logged read call on the local `SKILL.md`. The defensive code audit recognized the authorization flaw. Its first repair proposal passed six of eight tests and threw an error on missing tenant keys. After concrete test feedback, the second version passed all eight cases.

Gemma 26B chose `search_web` and `read_url` itself. The real MCP calls needed 1,03 and 2,04 s. The follow-up answer explained decimal representation and referred to the retrieved Python documentation. Gemma then started a deep-research job. It reported one source read after 23,05 s of service runtime. Polling showed the finished job at 29,58 s. The local synthesis model reached the 700-token limit of the MCP service. The research result contained the intended replacement report with its source. [Source documentation for the test](https://docs.python.org/3/library/decimal.html)

| StyleTune test | Duration | Quality |
|---|---:|---|
| English card story, first attempt | 85,46 s | The characters speak differently. The first repair attempt fails; the scene ends with an action. At 1.030 words it is under the required range of 1.100–1.300. |
| English card story, one revision | 75,65 s | 1.016 words. The length requirement stayed open. Decode 18,38 t/s versus 18,73 t/s in the first draft. |
| English music article | 25,7 s | The three tracks and 126 BPM were retained. The first unison passage was unattributed. The fact-fidelity test failed. |
| German devlog | 12,4 s | Two sentences with a date, a number, and an unchanged URL. All three protected details were retained. |

The local human-writing linter reported no findings in either story or in the German devlog. In the music article it reported one finding. Fact quality and word count were checked separately.

The KDE launcher opened the installed WebUI in regular Firefox. There, the MCP menu showed the four expected connections as connected, with 20 tools in total. The renewed direct service check after the router restart covered 21 actual MCP calls. Router, Research, and MCP gateway were active. The three ports were bound to loopback.

## Follow-Up Measurement for 256K, Deep Research, and StyleTune

In the 256K profile, a cold prompt with 65.006 new tokens was compared at unchanged Q4_0 K/V quantization. For this MoE type, a larger microbatch can batch calls across the CPU-GPU boundary better. The published comparison on a 16-GiB GPU served as a test hint. [Upstream options](https://github.com/ggml-org/llama.cpp/blob/b12628/tools/server/README.md) · [Published Qwen MoE measurement](https://github.com/ggml-org/llama.cpp/discussions/28363)

| Batch / microbatch | Prefill | Decode | First token | Total | Retrieval |
|---|---:|---:|---:|---:|---:|
| 1.024 / 512 | 511,23 t/s | 17,40 t/s | 127,27 s | 132,74 s | 3/3 |
| 2.048 / 1.024 | 887,79 t/s | 17,02 t/s | 73,34 s | 79,57 s | 3/3 |

The full fixture with 261.688 prompt tokens followed. The new cold run received the same input and started with zero cache tokens. The warm repeat used the same input in the same slot.

| Full 256K prompt | Cache / new tokens | First token | First searched value | Total duration | Decode | Retrieval |
|---|---:|---:|---:|---:|---:|---:|
| Historical cold run, 1.024 / 512 | 0 / 261.688 | 562,76 s | 564,68 s | 576,33 s | 6,93 t/s | 3/3 |
| Cold run, 2.048 / 1.024 | 0 / 261.688 | 393,74 s | 395,68 s | 408,09 s | 6,89 t/s | 3/3 |
| Warm repeat, 2.048 / 1.024 | 261.684 / 4 | 0,67 s | 2,58 s | 15,16 s | 6,84 t/s | 3/3 |

The cold wait fell by 30 %. The current run needed at most 6.782 MiB device VRAM. The worker sample showed 0 KiB swap. When warm, the benefit applies to a matching prefix and a present slot.

The installed Websearch MCP call for evidence synthesis sets 700 output tokens. In the local comparison with two sourced prompts, the previous profile delivered complete JSON once and a token-limit abort once. With 128 thinking tokens, both prompts delivered complete JSON. The requests took 9,26 and 7,95 s versus 19,70 and 19,04 s. The new profile `deep-research` runs on the same GGUF and is the MCP service's default choice. Two real MCP jobs with DuckDuckGo returned the Python source and a model synthesis after 21,16 and 24,18 s of polling respectively. The first job selected the profile explicitly; the second used the default configuration after the service restart. [Websearch MCP configuration](https://github.com/Danmoreng/websearch-mcp/blob/main/README.md)

StyleTune wrote the card story in four separate requests. The scenes held 295, 278, 242, and 289 words. Together, 1.104 words met the target range of 1.100–1.300 words. The earlier full drafts had held 1.030 and 1.016 words. The character voices and the arc from failed attempt through root cause to renewed test were traceable across the four scenes. The four requests together took 92,8 s. [Plan-and-Write](https://assets.amazon.science/ca/65/f3f3d737491dbc0bfb80a7dbfe47/length-control-paper-coral-kdd-camera.pdf)

For the music text, the four sourced details were provided as F1–F4. StyleTune linked each factual claim to its fact ID and wrote a 45-word text from the brief template. Gemma 26B checked the old and new versions separately against the same list. The old version held unsourced statements about the acoustics and the playing style of the first track. In the short version, all four facts were retained and the comparison yielded no unsourced factual claims. The check applies to this template. [Independent verification steps](https://aclanthology.org/2024.findings-acl.212/) · [Source research and targeted revision](https://aclanthology.org/2023.acl-long.910/)

## Coding Long 256K

The router loads Cyber-Tiel in a 262.144-token slot under the model ID `coding-cyber-tiel-35b`. Short prompts occupy only their actually used part of the window. Research, Deep Research, and the four writing presets together with Coding make seven router entries for three GGUF files.

### Client Context and Auto-Compaction

Claude Code 2.1.328 uses `CLAUDE_CODE_MAX_CONTEXT_TOKENS=262144`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=262144`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192`, and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85` in the local wrapper. The client reported 253.952 tokens of effective window size after output reserve in its debug log. This build computes 85 % on that size. That gives a nominal 215.859 tokens for normal automatic compaction. The client's count can differ from the server's actual input. `/context` showed 262.144 tokens and `/autocompact` the set window. `/status` showed the local model ID and the loopback endpoint. The earlier report about a 100K lower bound did not occur. [Claude model configuration](https://code.claude.com/docs/en/model-config#context-window-and-auto-compaction) · [Claude environment variables](https://code.claude.com/docs/en/env-vars)

Codex 0.170.0 uses the supported settings `model_context_window=262144` and `model_auto_compact_token_limit=222822`. In the fallback model catalog, the client uses 95 % of context for inputs, so 249.036 tokens. The compaction limit of 222.822 leaves about 26.214 tokens up to that usable bound. The server-side output default of 8.192 tokens applies when a request sends no limit of its own. Codex compacts the history with a regular request through `/v1/responses` to the local provider. The configured SSE idle timeout is 900 s. Reading the effective configuration confirmed provider, context, compaction limit, and time limit. [Codex config schema v0.170.0](https://github.com/openai/codex/blob/rust-v0.170.0/codex-rs/core/config.schema.json)

### Long-Run Test for Project Guideline Retention

The local Python fixture checks domain rules for ledger and export authorization. Context stress comes from a generated attachment of 225.432 tokens including the task. The changes are then verified with own unit tests and two independent contract checks. A marker that appeared only in the first input must survive into the final report.

Codex continued the task after automatic compaction. The router logged about 238.040 tokens before compaction and 33.322 on the first regular answer turn after it. The CLI run ended with status 0 after 1.199,73 s. All 16 unit tests and both independent contract checks passed, including the marker in the report. The time includes two reconnects under the 300 s SSE limit in effect at session start. The local provider now starts with 900 s. Decode rates of the tool turns after compaction were around 22–25 t/s.

The first Claude attempt, with the whole attachment as the first request, ended client-side with `Prompt is too long`. The staged version did trigger an automatic compaction in the third attachment round. The event reported `trigger=auto`, 202.194 tokens before and 63.239 tokens after compaction. Duration was 304 s. This event count is the observed working value for this session. The client's nominal 85 % figure refers to the effective window and does not describe an exact server-side switch point.

## Reproducing and Rolling Back

The configuration from immediately before the unification is under `~/.local/state/localllma-setup/single-coding.oaKzZJjN/`. For this rollback, end local coding sessions and restore the backed-up router and client files.

```bash
backup=~/.local/state/localllma-setup/single-coding.oaKzZJjN
install -m 600 "$backup/models.ini" ~/.config/llama.cpp/models.ini
install -m 755 "$backup/llama-local-agent" ~/.local/libexec/llama-local-agent
install -m 600 "$backup/config.toml" ~/.config/llama.cpp/codex/config.toml
install -m 600 "$backup/llama-cpp.config.toml" ~/.config/llama.cpp/codex/llama-cpp.config.toml
curl -fsS 'http://127.0.0.1:8080/models?reload=1' >/dev/null
```

Raw data with fixture answers, error counters, device values, and cache events is in the restore package under `benchmarks/results/advanced-performance.json`. The test commands are there under `benchmarks/README.md`. GPU memory and power draw come from the device including the desktop. Worker RSS, swap, and CPU time come from `/proc`. The THP runs did not record a separate time value per snapshot. The detailed cache runs record the duration of full cache updates.

The pre-test configuration on this laptop is under `~/.local/state/localllma-setup/performance.48Q0UVUt/`. To roll back the profile parameters, first finish running chats and research jobs. Then restore the backed-up file and restart the router.

```bash
install -m 600 ~/.local/state/localllma-setup/performance.48Q0UVUt/models.ini ~/.config/llama.cpp/models.ini
systemctl --user restart llama-cpp.service
curl -fsS http://127.0.0.1:8080/health
```

If the restore package should also go back to the old state, port the restored `models.ini` to `localllma-setup/config/models.ini.in` with `@HOME@` instead of the absolute home directory. The evaluation of the measurement series can stay in the package.

The state directly before the 256K and deep-research follow-up is in `~/.local/state/localllma-setup/follow-up.qCIGRqul/`. For this rollback, first finish running chats and deep-research jobs.

```bash
backup=~/.local/state/localllma-setup/follow-up.qCIGRqul
install -m 600 "$backup/models.ini" ~/.config/llama.cpp/models.ini
install -m 755 "$backup/llama-research" ~/.local/libexec/llama-research
curl -fsS 'http://127.0.0.1:8080/models?reload=1' >/dev/null
systemctl --user restart llama-cpp-research.service
```

Raw data for the follow-up measurement, including the English scenes and the fact check, is in the restore package under `benchmarks/results/follow-up.json`.
