# Performance-Messung für llama.cpp

Messreihe vom 18. und 19. November 2026. Getestet auf dem Framework Laptop 16 mit Fedora 44, llama.cpp b12503 (`4577932fa`), CUDA 12.8 und NVIDIA-Treiber 615.78.08. Die drei installierten GGUF-Dateien bilden die Testbasis.

## Ausgangszustand

Der Produktionsrouter verwendet `models-max = 1`. Ausgangswerte sind 12 Decode- und 12 Batch-Threads, 512/256 Batch/Microbatch, automatische CUDA-Platzierung mit 1.024 MiB Reserve, Flash Attention, mmap und 512 MiB Prompt-Cache. Für die Coding-Profile ab 64K gelten 1.024/512 und Q4_0-K/V. Die 32K- und Writing-Profile verwenden Q8_0-K/V. Der installierte Build bietet bis zu 32 Kontext-Checkpoints pro Slot und standardmäßig einen Mindestabstand von 8.192 Tokens. Der Abstand wird bei der Verdrängung älterer Checkpoints relevant. [Upstream-Serveroptionen b12503](https://github.com/ggml-org/llama.cpp/blob/b12503/tools/server/README.md)

Der Ryzen AI 9 HX 370 hat 12 physische Kerne und 24 logische CPUs. Die Topologie meldet zwei L3-Gruppen mit vier bzw. acht physischen Kernen. CPU 0–11 umfasst je einen Thread pro Kern. Linux meldet rund 46,8 GiB nutzbaren RAM bei hoher bereits bestehender ZRAM-Belegung. Die Benchmarks speichern den Prozess-Swap getrennt davon. Der reguläre Start erfolgte im Energieprofil `low-power`.

Baseline, erste A/B-Tests und Langkontextreihe liefen unter Kernel 7.2.15. Nach dem Neustart übernahm Fedora Kernel 7.3.4. Am 19. November liefen die Kontrollpaare und Hardware-Vergleiche auf diesem Kernel mit demselben llama.cpp-Build und anfangs rund 33 GiB verfügbarem RAM. Verglichen werden jeweils Läufe aus derselben Reihe.

Die Baseline verwendet dieselbe Repository-förmige Retrieval-Aufgabe am Produktionsrouter. TTFT beginnt mit dem HTTP-Aufruf und endet beim ersten Token. Die Messwerte enthalten die tatsächlich im Modell gerenderten Prompt-Tokens, einschließlich der für StyleTune zusätzlich gerenderten Writing-Regeln.

| Profil | Prompt neu | Cache-Tokens | Prefill | Decode | TTFT | Gesamt | Retrieval |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cyber-Tiel `coding-fast` | 7.640 | 179 | 364,47 t/s | 36,43 t/s | 21,12 s | 24,08 s | 3/3 |
| Gemma 26B `research` | 7.596 | 0 | 388,29 t/s | 38,30 t/s | 19,86 s | 22,19 s | 3/3 |
| StyleTune `creative-writing` | 10.321 | 0 | 970,56 t/s | 18,69 t/s | 10,89 s | 16,15 s | 3/3 |

## Transparent Huge Pages

Tensward fand auf H100 und L4 bei mehreren gleichzeitigen Anfragen weniger Page Faults bei der Speicherallokation für Prompt-Zustände. glibc kann große anonyme Allokationen mit `glibc.malloc.hugetlb=1` für THP markieren. Auf diesem Laptop meldet glibc 2.43, THP `madvise` und die Defrag-Policy `madvise`. Die vorhandene Einstellung reichte für den Test. Die Benchmarks behielten mmap für die GGUF-Gewichte und änderten jeweils nur die Umgebungsvariable des temporären Routers und seines Modellprozesses. Für die sechs Cyber-Tiel-Durchläufe wurde A/B abwechselnd mit frischen Workern ausgeführt. [Tensward-Artikel](https://tensward.com/blog/huge-pages-llama-cpp) · [Technischer Bericht](https://github.com/Tensward/tensward/blob/main/docs/research/huge-pages.md) · [glibc](https://sourceware.org/glibc/manual/latest/html_node/Memory-Allocation-Tunables.html) · [Linux-Kernel](https://docs.kernel.org/admin-guide/mm/transhuge.html)

| Phase, je 3 Wiederholungen | TTFT A / B, Median | Gesamt A / B, Median | Minor Faults A / B, Median | AnonHugePages B, Median |
|---|---:|---:|---:|---:|
| Erster Prompt | 12,12 / 14,66 s | 13,34 / 15,86 s | 144.749 / 140.825 | 154 MiB |
| Bearbeitetes Präfix | 11,26 / 11,55 s | 12,59 / 12,88 s | 48.463 / 47.229 | 160 MiB |
| Identischer Folgeprompt | 0,15 / 0,36 s | 1,42 / 1,64 s | 16.301 / 16.301 | 160 MiB |

A hatte 0 MiB AnonHugePages. Der erste A-Lauf hatte 103.414 Major Faults, die späteren A-Läufe hatten 33 bzw. 0. Die Ausgangswärme des Dateicaches ist daher als Störgröße erkennbar. Die besseren A-Mediane liefern keinen Beleg für einen Zeitgewinn durch THP. Beide Gruppen bestanden alle neun Retrieval-Prüfungen. Die Umgebungsvariable wurde in Router und Worker verifiziert. Das glibc-Tunable bleibt im produktiven Cyber-Tiel-Profil aus.

Bei Gemma 26B und StyleTune folgte je ein zusätzliches A/B-Paar mit drei Anfragen pro Variante.

| Profil | Erster Prompt, TTFT A / B | Minor Faults beim ersten Prompt A / B | Peak AnonHugePages B | Gesamt A / B |
|---|---:|---:|---:|---:|
| Gemma 26B | 12,42 / 12,33 s | 119.847 / 744 | 1.112 MiB | 28,39 / 28,65 s |
| StyleTune | 8,12 / 8,06 s | 162.889 / 57.099 | 786 MiB | 20,49 / 20,46 s |

Die Allokation größerer Pages und die niedrigeren Fault-Zahlen führten in diesen Paaren zu keinem belastbaren Zeitgewinn. Produktiv gilt die Fedora-Policy `madvise` mit den regulären glibc-Einstellungen.

## Vollständiger 256K-Prefill

Ein frischer Worker mit Q4_0-K/V, 1.024/512 Batch/Microbatch und 256K Kontext verarbeitete 261.688 neue Prompt-Tokens bei null wiederverwendeten Tokens. Prefill erreichte 465,37 t/s. Der erste Token kam nach 562,76 s, die vollständige Antwort nach 576,33 s. Decode erreichte 6,93 t/s. Die strukturierte Repositoriums-Fixture lieferte 3/3 gesuchte Fakten. Gemessen wurde ein kalter **Prompt-Kontext**. Betriebssystem- und Dateicaches wurden für den Test regulär weiterverwendet.

Danach folgten kürzere Prompts im selben warmen 256K-Worker. Die verteilten Belege verschieben sich beim Vergrößern der Fixture. Deshalb wurden pro Wechsel nur 179 Tokens wiederverwendet.

| Ziel | Prompt gesamt | Prefill neu | Decode | TTFT | Fakten |
|---|---:|---:|---:|---:|---:|
| 16K | 16.024 | 597,73 t/s | 33,58 t/s | 26,56 s | 3/3 |
| 32K | 32.434 | 580,34 t/s | 26,36 t/s | 55,69 s | 3/3 |
| 64K | 65.006 | 558,95 t/s | 18,36 t/s | 116,19 s | 3/3 |
| 128K | 130.651 | 522,06 t/s | 11,86 t/s | 250,14 s | 3/3 |
| 192K | 196.291 | 500,51 t/s | 8,95 t/s | 392,17 s | 3/3 |

Über die Langkontextreihe lagen die beobachteten Spitzen bei 6.837 MiB VRAM, 83 °C und 86,81 W auf der GPU. CPU-Tctl erreichte 67,25 °C, der auslesbare Lüftersensor 3.536 U/min. Die Stichprobe der NVIDIA-Zähler meldete 0 µs für thermisches Drosseln. Der minimale verfügbare System-RAM lag während der Messreihe bei 16,52 GiB.

## MCP-Latenz

Der direkte Test umfasste Initialisierung und Tool-Discovery am vorhandenen Streamable-HTTP-Endpunkt und danach drei Aufrufe je Werkzeug. Alle 21 Aufrufe lieferten erwartete inhaltliche Merkmale.

| Werkzeug | Median | Bestanden |
|---|---:|---:|
| Websearch `search_web` | 13 ms | 3/3 |
| Websearch `read_url` | 12 ms | 3/3 |
| Context7 `resolve-library-id` | 1.166 ms | 3/3 |
| Context7 `query-docs` | 977 ms | 3/3 |
| GitHub `get_latest_release` | 267 ms | 3/3 |
| Skills `read_text_file` | 14 ms | 3/3 |
| Skills `read_multiple_files` | 11 ms | 3/3 |

Die Wiederholungen für Websearch und `read_url` verwenden dieselbe Anfrage und enthalten warme Provider- und Dienstcaches. Modell-Prefill, Tool-Auswahl sowie Freigabezeit in der WebUI gehören zu einer anderen Messgröße. Die vorhandenen Transporte wurden für diese Messreihe beibehalten.

## Prompt-Cache und Rückkehr zum Gesprächszweig

Cyber-Tiel lief im 128K-Profil. Jede Reihe startete mit einem neuen Worker, führte zwei verschiedene Repository-Zweige ein, kehrte zum ersten zurück, änderte dessen Prompt in der Mitte und wiederholte die geänderte Eingabe. Alle übrigen Optionen waren identisch. Der niedrige 512-MiB-Grenzwert verdrängte einen 303,44-MiB-Zustand, um Platz für den anderen Zweig zu schaffen.

| Cache-Grenze | Zurückwechseln, TTFT | Zurückwechseln, Gesamt | Cache-Tokens / neu | Alle fünf Anfragen | Peak-RSS |
|---|---:|---:|---:|---:|---:|
| 512 MiB | 14,13 s | 15,58 s | 179 / 9.230 | 65,95 s | 14,92 GiB |
| 1.024 MiB | 0,18 s | 1,59 s | 9.405 / 4 | 52,46 s | 15,00 GiB |
| 2.048 MiB | 0,17 s | 1,59 s | 9.405 / 4 | 52,16 s | 15,01 GiB |
| 4.096 MiB | 0,19 s | 1,63 s | 9.405 / 4 | 53,08 s | 15,01 GiB |

Bei 1.024 MiB dauerte das Cache-Update beim Zurückwechseln 56 ms. Die ganze Sequenz war um 20,5 % kürzer. Für die Änderung in der Mitte fielen weiterhin 9.242 neue Tokens an. Der Vorteil gilt für das Wiederaufnehmen des früheren Zweigs. Für diese Fixture war 1.024 MiB der kleinste ausreichende Grenzwert. Ein höherer RAM-Grenzwert reserviert den gesamten Betrag nicht beim Modellstart.

Am Folgetag ergab das erneute Paar im 128K-Profil beim Zurückwechseln 14,30 s gegenüber 0,17 s TTFT, erneut mit 179 gegenüber 9.405 Cache-Tokens. Fünf Anfragen dauerten 81,54 s bei 512 MiB und 60,87 s bei 1.024 MiB. Die ersten Anfragen kamen mit unterschiedlich warmem Dateicache an. Der Vergleich der Rückkehrphase zeigt den Effekt bei bereits geladenen Gewichten.

Für das 32K-Profil mit Q8_0-K/V blieb der ursprüngliche Prefill praktisch gleich. Die größere Cache-Grenze gewann die Zeit beim Zweigwechsel.

| 32K-Cache | Prefill erster Prompt | Rückkehr TTFT | Cache-Tokens / neu | Alle fünf Anfragen | Peak-RSS |
|---|---:|---:|---:|---:|---:|
| 512 MiB | 377,45 t/s | 23,68 s | 179 / 9.230 | 102,67 s | 14,76 GiB |
| 1.024 MiB | 377,67 t/s | 0,22 s | 9.405 / 4 | 79,15 s | 14,89 GiB |

## Kontext-Checkpoints

Verglichen wurden die Standardwerte mit vier Checkpoints pro Slot und mit 16.384 Tokens Mindestabstand. Jede Variante führte fünf Anfragen mit einem Wechsel und einem später bearbeiteten Präfix aus. Wiederverwendete Tokens und Wiederherstellungen waren bei allen drei Einstellungen gleich. Der Abstand wirkt in diesem Build erst bei der Auswahl zu löschender Checkpoints. Produktiv gelten 32 Checkpoints und 8.192 Tokens Mindestabstand.

| Profil | Standard | Vier Checkpoints | Abstand 16.384 | Wiederherstellungen je Lauf | Cache-Tokens bei Rückkehr |
|---|---:|---:|---:|---:|---:|
| `coding-long-128k` | 65,95 s | 67,33 s | 67,04 s | 4 | 179 |
| `research` | 102,71 s | 100,25 s | 100,39 s | 3 | 1 |

## Threads und CPU-Affinität

Jede Zeile ist ein neuer 32K-Cyber-Tiel-Worker im Profil `low-power` mit rund 4.500 Prompt-Tokens. Geändert wurde jeweils eine Einstellung. Die Affinität erlaubt mit der Maske `fff` je einen logischen Thread pro physischem Kern. Alle Varianten beantworteten die drei gesuchten Fakten korrekt. Peak-RSS lag bei 14,38–14,39 GiB, der VRAM-Peak jeweils bei 6.780 MiB.

| Einstellung | Prefill t/s | Decode t/s | Gesamt | Worker-CPU-Zeit |
|---|---:|---:|---:|---:|
| 12 / 12, Ausgangswert | 364,96 | 40,90 | 13,56 s | 27,64 s |
| 8 / 12 | 364,99 | 39,80 | 13,60 s | 23,08 s |
| 16 / 12 | 363,46 | 40,02 | 13,65 s | 33,08 s |
| 24 / 12 | 363,27 | 17,75 | 15,31 s | 79,03 s |
| 12 / 8 | 364,85 | 42,10 | 13,53 s | 26,82 s |
| 12 / 16 | 364,31 | 42,40 | 13,54 s | 27,48 s |
| 12 / 24 | 349,85 | 41,41 | 14,08 s | 30,94 s |
| 12 / 12 mit Affinität | 353,71 | 41,27 | 13,94 s | 28,05 s |

24 Decode-Threads erhöhten die CPU-Zeit auf fast das Dreifache und senkten Decode um 57 %. Die übrigen Änderungen verkürzten den Ablauf um höchstens 0,03 s. Der Router verwendet 12 / 12 mit regulärer Kernel-Affinität.

## Batch und Microbatch

Die folgenden Einzelmessungen vergleichen bei gleichem Testprompt die Batch-/Microbatch-Kombinationen. Jede Zeile beginnt mit einem geladenen, frischen Worker. Die Zahlen enthalten den Präfix-Prefill der Anfrage.

| Cyber-Tiel 32K | Prefill t/s | Decode t/s | TTFT | Gesamt | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 364,96 | 40,90 | 12,27 s | 13,56 s | 6.780 MiB |
| 1.024 / 256 | 353,16 | 40,31 | 12,68 s | 13,99 s | 6.780 MiB |
| 1.024 / 512 | 537,79 | 40,01 | 8,33 s | 9,68 s | 6.742 MiB |
| 2.048 / 512 | 541,80 | 40,15 | 8,27 s | 9,61 s | 6.742 MiB |
| 2.048 / 1.024 | 780,96 | 40,73 | 5,74 s | 7,02 s | 6.760 MiB |

Die anschließenden Kontrollpaare verwendeten 9.409 neue Prompt-Tokens und wechselten zweimal von 512/256 auf 2.048/1.024. TTFT sank in den Paaren von 26,01 auf 10,11 s und von 30,62 auf 11,12 s. Der Median des gesamten Ablaufs sank um 59 %. Der Median für Decode lag bei 38,28 bzw. 35,41 t/s. Alle vier Antworten erfüllten 3/3 Kriterien. Der gemessene Worker-Peak-RSS stieg von 14,39 auf 14,47 GiB.

| Coding 32K, Median zweier Läufe | Prefill t/s | Decode t/s | TTFT | Gesamt | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 334,86 | 38,28 | 28,32 s | 29,57 s | 6.780 MiB |
| 2.048 / 1.024 | 890,14 | 35,41 | 10,62 s | 12,23 s | 6.760 MiB |

Zusammen mit 1.024 MiB Cache dauerte die 32K-Zweigfolge 38,39 s. Dieselbe Folge mit 512/256 und 512 MiB benötigte 102,67 s. Alle fünf Antworten waren korrekt. Beim Zurückwechseln kamen erneut 9.405 Tokens aus dem Cache, der erste Token kam nach 0,19 s. Decode lag im kombinierten Lauf bei 33,22–41,59 t/s. Der Vorteil stammt aus schnellerem Prefill und der Wiederverwendung des Gesprächszustands.

| Gemma 26B Research 32K | Prefill t/s | Decode t/s | TTFT | Gesamt | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 311,26 | 37,58 | 14,86 s | 16,21 s | 6.694 MiB |
| 1.024 / 512 | 639,78 | 38,09 | 7,27 s | 8,62 s | 6.770 MiB |
| 2.048 / 512 | 634,40 | 37,09 | 7,36 s | 8,73 s | 6.770 MiB |

Für Research folgten zwei Dreierreihen mit demselben Prompt von rund 9.900 Tokens. 2.048/1.024 lieferte in beiden Wiederholungen ungefähr 9,4 s TTFT bei vollständigem Retrieval. Der Worker-Peak-RSS lag bei 14,55 GiB. Der Geräte-Peak lag bei 6.782 MiB VRAM.

| Research 32K, Median zweier Läufe | Prefill t/s | Decode t/s | TTFT | Gesamt |
|---|---:|---:|---:|---:|
| 512 / 256 | 346,50 | 32,89 | 29,09 s | 30,58 s |
| 1.024 / 512 | 585,39 | 33,14 | 17,36 s | 18,93 s |
| 2.048 / 1.024 | 1.062,75 | 36,71 | 9,40 s | 10,72 s |

| StyleTune 16K | Prefill t/s | Decode t/s | TTFT | Gesamt | Peak VRAM |
|---|---:|---:|---:|---:|---:|
| 512 / 256 | 910,37 | 17,70 | 7,94 s | 10,16 s | 6.814 MiB |
| 1.024 / 512 | 1.157,26 | 16,62 | 6,31 s | 9,39 s | 6.764 MiB |
| 2.048 / 512 | 1.155,09 | 16,09 | 6,30 s | 9,51 s | 6.764 MiB |
| 2.048 / 1.024 | 1.247,23 | 14,21 | 5,90 s | 8,69 s | 6.702 MiB |

Bei StyleTune fiel Decode mit jeder größeren Microbatch. Für lange Schreibaufgaben ist die Länge der Ausgabe entscheidend. Die Writing-Profile verwenden deshalb 512/256.

Im 128K-Profil für Cyber-Tiel sank TTFT mit 15.734 neuen Tokens von 31,41 auf 20,97 s. Die beiden vollständigen Antworten dauerten 33,75 und 23,88 s. Decode blieb mit 27,81 und 27,54 t/s praktisch gleich. Beide Antworten erfüllten 3/3 Kriterien.

Der kombinierte 128K-Zweigtest benötigte 43,36 s gegenüber 60,87 s bei gleichem Cache und 1.024/512. Fünf Antworten erfüllten alle Kriterien. Beim Wiederaufnehmen des ersten Zweigs lag TTFT bei 0,23 s. Der Router verwendete 9.405 Cache-Tokens und berechnete vier Tokens neu. Beide Testreihen liefen mit einem 128K-Fenster, die einzelnen Zweige enthielten jeweils rund 9.400 Tokens.

## CUDA-Platzierung und KV

Die automatische Platzierung berücksichtigt die Zielreserve. `cpu-moe` legt alle Expertengewichte auf die CPU. `moe-cache-mib` verwendet den im Build vorhandenen GPU-Zwischenspeicher für auf der CPU gelagerte Experten. Q4_0 wurde als Alternative zur bisherigen Q8_0-K/V-Quantisierung bei 32K getestet. Alle gezeigten Varianten beantworteten die jeweilige Retrieval-Aufgabe korrekt.

| Profil und Änderung | Prefill t/s | Decode t/s | TTFT | Peak VRAM |
|---|---:|---:|---:|---:|
| Cyber-Tiel automatisch, Q8_0 | 364,96 | 40,90 | 12,27 s | 6.780 MiB |
| Cyber-Tiel CPU-MoE | 250,16 | 31,68 | 17,89 s | 2.700 MiB |
| Cyber-Tiel 384 MiB Expert-Cache | 322,59 | 37,06 | 13,88 s | 6.784 MiB |
| Cyber-Tiel 768 MiB Reserve | 355,07 | 39,84 | 12,61 s | 6.978 MiB |
| Cyber-Tiel Q4_0-K/V | 348,45 | 38,94 | 12,85 s | 6.818 MiB |
| Cyber-Tiel KV auf der CPU | 322,36 | 19,33 | 13,89 s | 6.816 MiB |
| Gemma 26B automatisch, Q8_0 | 311,26 | 37,58 | 14,86 s | 6.694 MiB |
| Gemma 26B CPU-MoE | 292,70 | 35,04 | 15,78 s | 3.162 MiB |
| Gemma 26B 384 MiB Expert-Cache | 394,82 | 17,37 | 11,83 s | 6.672 MiB |
| Gemma 26B 768 MiB Reserve | 407,00 | 40,85 | 11,37 s | 6.970 MiB |
| Gemma 26B Q4_0-K/V | 406,93 | 35,89 | 11,38 s | 6.748 MiB |

CPU-MoE erreichte den geringsten VRAM-Verbrauch und die längste Aufgabenzeit. CPU-KV brachte für Cyber-Tiel weniger als die Hälfte des ursprünglichen Decode-Durchsatzes. Die niedrigere CUDA-Reserve und Q4_0 bei Gemma 26B zeigten einen Prefill-Gewinn in je einem Lauf bei veränderter GPU-Speicherbelegung. Batch-Vergleiche erreichten mit 1.024 MiB Reserve und Q8_0 mehr Durchsatz. Die regulären Profile verwenden Auto-Fit mit 1.024 MiB CUDA-Reserve, Flash Attention sowie Q8_0 bei 16K und 32K beziehungsweise Q4_0 ab 64K.

## Energie und Thermik

Fedora stellt die Profile über UPower und TuneD bereit. Balanced und Performance wechselten sich dreimal ab. Ein Durchlauf verwendete einen frischen Cyber-Tiel-Worker, denselben ersten Prompt, ein bearbeitetes Präfix und eine unveränderte Wiederholung. Alle sechs Durchläufe beantworteten die drei gesuchten Fakten in jeder Phase. Die Latenzen sind Mediane der drei Durchläufe. Sensorwerte sind Stichproben einschließlich Modellstart.

| Profil | Erster Prefill | Decode | TTFT | Drei Anfragen | CPU max. | GPU max. | GPU-Leistung Median / max. |
|---|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 316,31 t/s | 51,00 t/s | 14,15 s | 28,28 s | 95,75 °C | 57,97 °C | 43,53 / 51,14 W |
| Performance | 297,64 t/s | 52,60 t/s | 15,03 s | 33,66 s | 97,62 °C | 54,69 °C | 40,61 / 55,83 W |

Der Median der stichprobenweisen All-Core-Taktwerte lag bei 2,36 bzw. 3,30 GHz. Der GPU-Takt lag für beide im Median bei 2.437 MHz. Das Lüftermaximum lag bei 4.748 U/min. Die einzelne 128-MiB-`memmove`-Probe erreichte 16,78 bzw. 18,44 GiB/s kopierte Nutzdaten. Sie dient zur Einordnung des Host-Speicherpfads. CPU-Paketleistung und CPU-Drosselzähler waren für den Benutzerprozess nicht auslesbar. Das Performance-Profil brachte bei dieser präfilllastigen Sequenz keinen reproduzierbaren Zeitgewinn. UPower meldete nach der Reihe wieder `power-saver`, die Firmware `low-power`.

## Historische Profile vor der 256K-Vereinheitlichung

| Profile | Batch / Microbatch | Prompt-Cache | K/V |
|---|---:|---:|---|
| `coding-fast` | 2.048 / 1.024 | 1.024 MiB | Q8_0 |
| `coding-long-128k` | 2.048 / 1.024 | 1.024 MiB | Q4_0 |
| `research`, `deep-research` | 2.048 / 1.024 | 512 MiB | Q8_0 |
| `coding-long-64k`, `coding-long-192k` | 1.024 / 512 | 512 MiB | Q4_0 |
| `coding-long-256k` | 2.048 / 1.024 | 512 MiB | Q4_0 |
| Die vier StyleTune-Profile | 512 / 256 | 512 MiB | Q8_0 |

| Optimierung | Baseline | Optimiert | Veränderung | Qualität | Entscheidung |
|---|---:|---:|---:|---|---|
| 32K Batch, erster Token bei 9.409 Tokens | 28,32 s | 10,62 s | −62 % | 3/3 pro Antwort | Aktiv |
| 32K Batch und Cache, fünf Anfragen | 102,67 s | 38,39 s | −63 % | 5/5 Antworten je Lauf | Aktiv |
| 128K Cache, Rückkehr zum ersten Zweig | 14,30 s | 0,17 s | −99 % | 5/5 Antworten je Lauf | Aktiv |
| 128K Batch, erster Token bei 15.734 Tokens | 31,41 s | 20,97 s | −33 % | 3/3 pro Antwort | Aktiv |
| Research Batch, erster Token bei 9.859 Tokens | 29,09 s | 9,40 s | −68 % | 3/3 pro Antwort | Aktiv |
| Huge Pages, Cyber-Tiel, erster Token | 12,12 s | 14,66 s | +21 % | 9/9 Antworten je Gruppe | Reguläre glibc-Einstellungen |
| 24 Cyber-Tiel-Decode-Threads | 40,90 t/s | 17,75 t/s | −57 % | 3/3 pro Antwort | 12 Threads |
| Performance-Profil, drei Anfragen | 28,28 s | 33,66 s | +19 % | 9/9 Antworten je Gruppe | Ursprüngliches Energieprofil |

Die damals elf Aliase verwendeten CUDA, mmap, Flash Attention und einen Slot. Der Router lädt maximal einen Worker. Die Prompt-Cache-Werte sind RAM-Grenzen. Beim Entladen endet die Wiederverwendung des Zustands. Persistente Slot-Zustände und MTP sind deaktiviert. Die aktuelle 256K-Messung steht in der Nachmessung. Die 192K-Messung verwendet die oben gezeigten Produktionswerte.

## Praxisprüfung nach dem Neustart

Die beiden CLI-Clients erhielten dieselbe Ledger-Aufgabe in getrennten lokalen Fixtures. Sie sollten die Vertragsdatei lesen, global nach Event-ID deduplizieren, die Währungsnormalisierung in eine Hilfsfunktion auslagern und Regressionstests ausführen. Die Wrapper isolierten das Netz und leiteten die lokalen Anfragen über den Unix-Socket an den Router.

| Client und Profil | CLI-Ergebnis | Unabhängige Prüfung | Dauer | Decode Median |
|---|---|---|---:|---:|
| `codex-local`, 32K | Bestanden, 13 abgeschlossene Shell-Tool-Aufrufe | 5 Unit-Tests und Vertragsprüfung bestanden | 116,24 s | 40,09 t/s |
| `claude-local`, 32K | Client-Abbruch nach wiederholter Kontextkomprimierung | Der geschriebene Fix bestand 4 Unit-Tests und die Vertragsprüfung | 231,42 s | 39,20 t/s |
| `claude-local`, 128K | Bestanden, acht Werkzeugaufrufe | 6 Unit-Tests und Vertragsprüfung bestanden | 78,07 s | 34,14 t/s |

Codex meldete 100.388 Cache-Tokens über die Sitzung, Claude 16.322 bei 32K und 34.338 bei 128K. Summen über mehrere Turns können größer als das Kontextfenster sein. Die Gesamtdauern enthalten Modellaufrufe und Tool-Ausführung. Die älteren CLI-Zeiten gehören zu Durchläufen mit unterschiedlicher Systemlast. Der direkte Vergleich der Einstellungen steht in den kontrollierten Batch- und Cache-Reihen.

Der 128K-Praxistest übergab 100.708 Tokens aus vier Dateien des festgehaltenen llama.cpp-Quellstands in zwei Schritten. Cyber-Tiel erklärte den Reload-Endpunkt, die Preset-Vergleiche, das Freigeben der Sperre und das Verhalten von `load-on-startup` korrekt anhand der Quellfunktionen. Im zweiten Turn wurden 49.433 Tokens wiederverwendet und 51.480 neu verarbeitet. Der erste und zweite Prefill erreichten 874,11 und 782,28 t/s. Die beiden Anfragen dauerten zusammen 141,85 s. Decode im zweiten Turn erreichte 14,42 t/s.

Ein separater Tool-Calling-Test in `coding-fast` wählte nacheinander zwei Werkzeuge anhand des jeweils vorherigen Ergebnisses und gab die erwartete Build-ID mit Status zurück. Die drei Modellaufrufe dauerten zusammen 3,72 s.

Claude Code aktivierte `backend-api-engineering` mit seinem Skill-Werkzeug. Codex erklärte die Regeln des Skills und bestätigte den Dateizugriff in einem zweiten Lauf mit einem geloggten Leseaufruf auf die lokale `SKILL.md`. Der defensive Codeaudit erkannte den Autorisierungsfehler. Sein erster Reparaturvorschlag bestand sechs von acht Tests und warf bei fehlenden Tenant-Schlüsseln einen Fehler. Nach konkretem Testfeedback bestand die zweite Fassung alle acht Fälle.

Gemma 26B wählte `search_web` und `read_url` selbst. Die realen MCP-Aufrufe benötigten 1,03 und 2,04 s. Die Folgeantwort erklärte die Darstellung von Dezimalzahlen und verwies auf die abgerufene Python-Dokumentation. Anschließend startete Gemma einen Deep-Research-Auftrag. Er meldete nach 23,05 s Dienstlaufzeit eine gelesene Quelle. Beim Polling erschien der fertige Auftrag nach 29,58 s. Das lokale Synthese-Modell erreichte das 700-Token-Limit des MCP-Dienstes. Das Rechercheergebnis enthielt den vorgesehenen Ersatzbericht mit Quelle. [Quellendokumentation zum Test](https://docs.python.org/3/library/decimal.html)

| StyleTune-Test | Dauer | Qualität |
|---|---:|---|
| Englische Kart-Geschichte, erster Versuch | 85,46 s | Die Figuren sprechen unterschiedlich. Der erste Reparaturversuch scheitert, die Szene endet mit einer Handlung. Mit 1.030 Wörtern unter dem geforderten Bereich von 1.100–1.300. |
| Englische Kart-Geschichte, eine Überarbeitung | 75,65 s | 1.016 Wörter. Die Längenvorgabe blieb offen. Decode 18,38 t/s gegenüber 18,73 t/s im ersten Entwurf. |
| Englischer Musikartikel | 25,7 s | Die drei Stücke und 126 BPM blieben erhalten. Die unisono gespielte erste Passage war unbelegt. Der Test der Faktentreue schlug fehl. |
| Deutscher Devlog | 12,4 s | Zwei Sätze mit Datum, Zahl und unveränderter URL. Alle drei geschützten Angaben blieben erhalten. |

Der lokale Human-Writing-Linter meldete in beiden Geschichten und im deutschen Devlog keine Befunde. Im Musikartikel meldete er einen Befund. Faktenqualität und Wortzahl wurden separat geprüft.

Der KDE-Starter öffnete die installierte WebUI im regulären Firefox. Dort zeigte das MCP-Menü die vier erwarteten Verbindungen als verbunden, mit insgesamt 20 Werkzeugen. Die erneute direkte Dienstprüfung nach dem Router-Neustart umfasste 21 tatsächliche MCP-Aufrufe. Router, Research und MCP-Gateway waren aktiv. Die drei Ports waren an Loopback gebunden.

## Nachmessung für 256K, Deep Research und StyleTune

Im 256K-Profil wurde ein kalter Prompt mit 65.006 neuen Tokens bei gleichbleibender Q4_0-K/V-Quantisierung verglichen. Eine größere Microbatch kann bei diesem MoE-Typ Aufrufe über die CPU-GPU-Grenze besser bündeln. Der veröffentlichte Vergleich auf einer 16-GiB-GPU diente als Versuchshinweis. [Upstream-Optionen](https://github.com/ggml-org/llama.cpp/blob/b12503/tools/server/README.md) · [Veröffentlichte Qwen-MoE-Messung](https://github.com/ggml-org/llama.cpp/discussions/28363)

| Batch / Microbatch | Prefill | Decode | Erster Token | Gesamt | Retrieval |
|---|---:|---:|---:|---:|---:|
| 1.024 / 512 | 511,23 t/s | 17,40 t/s | 127,27 s | 132,74 s | 3/3 |
| 2.048 / 1.024 | 887,79 t/s | 17,02 t/s | 73,34 s | 79,57 s | 3/3 |

Danach folgte die vollständige Fixture mit 261.688 Prompt-Tokens. Der neue kalte Lauf erhielt dieselbe Eingabe und startete mit null Cache-Tokens. Die warme Wiederholung verwendete dieselbe Eingabe im selben Slot.

| Voller 256K-Prompt | Cache / neue Tokens | Erster Token | Erster gesuchter Wert | Gesamtdauer | Decode | Retrieval |
|---|---:|---:|---:|---:|---:|---:|
| Historischer Kaltlauf, 1.024 / 512 | 0 / 261.688 | 562,76 s | 564,68 s | 576,33 s | 6,93 t/s | 3/3 |
| Kaltlauf, 2.048 / 1.024 | 0 / 261.688 | 393,74 s | 395,68 s | 408,09 s | 6,89 t/s | 3/3 |
| Warme Wiederholung, 2.048 / 1.024 | 261.684 / 4 | 0,67 s | 2,58 s | 15,16 s | 6,84 t/s | 3/3 |

Die kalte Wartezeit sank um 30 %. Der aktuelle Lauf benötigte maximal 6.782 MiB Geräte-VRAM. Die Worker-Stichprobe zeigte 0 KiB Swap. Warm gilt der Vorteil bei übereinstimmendem Präfix und vorhandenem Slot.

Der installierte Websearch-MCP-Aufruf für die Evidenz-Synthese setzt 700 Ausgabetokens. Im lokalen Vergleich mit zwei belegten Prompts lieferte das bisherige Profil einmal vollständiges JSON und einmal einen Abbruch am Tokenlimit. Mit 128 Denktokens lieferten beide Prompts vollständiges JSON. Die Anfragen dauerten 9,26 und 7,95 s gegenüber 19,70 und 19,04 s. Das neue Profil `deep-research` läuft mit demselben GGUF und ist die Standardwahl des MCP-Dienstes. Zwei echte MCP-Aufträge mit DuckDuckGo lieferten nach 21,16 bzw. 24,18 s im Polling jeweils die Python-Quelle und eine Modellsynthese. Der erste Auftrag wählte das Profil explizit, der zweite verwendete nach dem Dienstneustart die Standardkonfiguration. [Websearch-MCP-Konfiguration](https://github.com/Danmoreng/websearch-mcp/blob/main/README.md)

StyleTune schrieb die Kart-Geschichte in vier getrennten Anfragen. Die Szenen umfassten 295, 278, 242 und 289 Wörter. Zusammen erfüllten 1.104 Wörter den Zielbereich von 1.100–1.300 Wörtern. Die vorherigen Gesamtentwürfe hatten 1.030 und 1.016 Wörter. Die Figurenstimmen und der Verlauf vom gescheiterten Versuch über die Fehlerursache bis zum erneuten Test waren in den vier Szenen nachvollziehbar. Die vier Anfragen dauerten zusammen 92,8 s. [Plan-and-Write](https://assets.amazon.science/ca/65/f3f3d737491dbc0bfb80a7dbfe47/length-control-paper-coral-kdd-camera.pdf)

Für den Musiktext wurden die vier belegten Angaben als F1–F4 bereitgestellt. StyleTune verknüpfte jeden Sachclaim mit seiner Fakten-ID und schrieb aus der knappen Vorlage einen 45 Wörter langen Text. Gemma 26B prüfte alte und neue Fassung jeweils separat gegen dieselbe Liste. Die alte Fassung enthielt unbelegte Aussagen zur Akustik und zur Spielweise des ersten Stücks. In der kurzen Fassung waren alle vier Tatsachen erhalten und der Vergleich ergab keine unbelegten Sachclaims. Die Prüfung gilt für diese Vorlage. [Unabhängige Verifikationsschritte](https://aclanthology.org/2024.findings-acl.212/) · [Quellenrecherche und gezielte Revision](https://aclanthology.org/2023.acl-long.910/)

## Coding Long 256K

Der Router lädt Cyber-Tiel in einem 262.144-Token-Slot unter der Modell-ID `coding-long-256k`. Kurze Prompts belegen nur ihren tatsächlich verwendeten Teil des Fensters. Research, Deep Research und die vier Writing-Presets ergeben zusammen mit Coding sieben Router-Einträge für drei GGUF-Dateien.

### Kontext und Auto-Compaction der Clients

Claude Code 2.1.328 verwendet `CLAUDE_CODE_MAX_CONTEXT_TOKENS=262144`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=262144`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192` und `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85` im lokalen Wrapper. Der Client meldete im Debug-Log 253.952 Tokens effektive Fenstergröße nach Ausgabereserve. Dieser Build berechnet 85 % auf dieser Größe. Daraus ergeben sich nominal 215.859 Tokens für die normale automatische Compaction. Die Zählung im Client kann gegenüber dem tatsächlichen Input des Servers abweichen. `/context` zeigte 262.144 Tokens und `/autocompact` das gesetzte Fenster an. `/status` zeigte die lokale Modell-ID und den Loopback-Endpunkt. Die frühere Meldung zur 100K-Untergrenze trat dabei nicht auf. [Claude-Modellkonfiguration](https://code.claude.com/docs/en/model-config#context-window-and-auto-compaction) · [Claude-Umgebungsvariablen](https://code.claude.com/docs/en/env-vars)

Codex 0.170.0 verwendet die unterstützten Einstellungen `model_context_window=262144` und `model_auto_compact_token_limit=222822`. Der Client verwendet im Fallback-Modellkatalog 95 % Kontext für Eingaben, also 249.036 Tokens. Die Compaction-Grenze von 222.822 lässt rund 26.214 Tokens bis zu dieser nutzbaren Grenze. Die serverseitigen 8.192 Tokens Ausgabevorgabe gelten, wenn ein Request kein eigenes Limit sendet. Codex komprimiert den Verlauf mit einer normalen Anfrage über `/v1/responses` an den lokalen Provider. Die konfigurierte SSE-Leerlaufzeit beträgt 900 s. Das Auslesen der wirksamen Konfiguration bestätigte Provider, Kontext, Compaction-Grenze und Zeitlimit. [Codex-Config-Schema v0.170.0](https://github.com/openai/codex/blob/rust-v0.170.0/codex-rs/core/config.schema.json)

### Langzeittest zum Erhalt von Projektvorgaben

Die lokale Python-Fixture prüft fachliche Regeln für Ledger und Exportautorisierung. Der Kontextstress entsteht durch einen generierten Anhang mit 225.432 Tokens einschließlich Auftrag. Die Änderungen werden anschließend mit eigenen Unit-Tests sowie zwei unabhängigen Vertragsprüfungen verifiziert. Ein Kennzeichen, das nur in der ersten Eingabe stand, muss im Abschlussbericht erhalten bleiben.

Codex setzte die Aufgabe nach der automatischen Komprimierung fort. Der Router protokollierte rund 238.040 Tokens vor der Komprimierung und 33.322 beim ersten regulären Antwortturn danach. Der CLI-Lauf endete mit Status 0 nach 1.199,73 s. Alle 16 Unit-Tests und beide unabhängigen Vertragsprüfungen bestanden, einschließlich des Kennzeichens im Bericht. Die Zeit enthält zwei Wiederverbindungen unter dem zu Sitzungsbeginn wirksamen SSE-Zeitlimit von 300 s. Der lokale Provider wird jetzt mit 900 s gestartet. Die Decode-Raten der Werkzeugturns nach Compaction lagen bei rund 22–25 t/s.

Der erste Claude-Versuch mit dem ganzen Anhang als Erstanfrage endete clientseitig mit `Prompt is too long`. Die mehrstufige Fassung löste in der dritten Anhangrunde tatsächlich eine automatische Compaction aus. Das Ereignis meldete `trigger=auto`, 202.194 Tokens vor und 63.239 Tokens nach der Komprimierung. Die Dauer betrug 304 s. Diese Ereigniszählung ist der beobachtete Arbeitswert für diese Sitzung. Der nominale 85-%-Wert des Clients bezieht sich auf das effektive Fenster und beschreibt keinen exakten serverseitigen Umschaltpunkt.

## Wiederholen und zurücksetzen

Die Konfiguration unmittelbar vor der Vereinheitlichung liegt unter `~/.local/state/localllma-setup/single-coding.oaKzZJjN/`. Für diesen Rückbau lokale Coding-Sitzungen beenden und die gesicherten Router- und Clientdateien zurückspielen.

```bash
backup=~/.local/state/localllma-setup/single-coding.oaKzZJjN
install -m 600 "$backup/models.ini" ~/.config/llama.cpp/models.ini
install -m 755 "$backup/llama-local-agent" ~/.local/libexec/llama-local-agent
install -m 600 "$backup/config.toml" ~/.config/llama.cpp/codex/config.toml
install -m 600 "$backup/llama-cpp.config.toml" ~/.config/llama.cpp/codex/llama-cpp.config.toml
curl -fsS 'http://127.0.0.1:8080/models?reload=1' >/dev/null
```

Die Rohdaten mit Fixture-Antworten, Fehlerzählern, Gerätewerten und Cache-Ereignissen stehen im Wiederherstellungspaket unter `benchmarks/results/advanced-performance.json`. Die Testbefehle stehen dort unter `benchmarks/README.md`. GPU-Speicher und Leistungsaufnahme stammen vom Gerät einschließlich Desktop. Worker-RSS, Swap und CPU-Zeit stammen aus `/proc`. Die THP-Läufe erfassten keinen separaten Zeitwert pro Snapshot. Die detaillierten Cache-Läufe erfassen die Dauer der vollständigen Cache-Updates.

Die Konfiguration vor dem Test liegt auf diesem Laptop unter `~/.local/state/localllma-setup/performance.48Q0UVUt/`. Für einen Rückbau der Profilparameter erst laufende Chats und Research-Aufträge abschließen. Dann die gesicherte Datei zurückspielen und den Router neu starten.

```bash
install -m 600 ~/.local/state/localllma-setup/performance.48Q0UVUt/models.ini ~/.config/llama.cpp/models.ini
systemctl --user restart llama-cpp.service
curl -fsS http://127.0.0.1:8080/health
```

Falls auch das Wiederherstellungspaket auf den alten Stand soll, die zurückgespielte `models.ini` mit `@HOME@` statt des absoluten Home-Verzeichnisses nach `localllma-setup/config/models.ini.in` übernehmen. Die Auswertung der Messreihe kann im Paket verbleiben.

Der Stand direkt vor der 256K- und Deep-Research-Nachmessung liegt in `~/.local/state/localllma-setup/follow-up.qCIGRqul/`. Für diesen Rückbau erst laufende Chats und Deep-Research-Aufträge abschließen.

```bash
backup=~/.local/state/localllma-setup/follow-up.qCIGRqul
install -m 600 "$backup/models.ini" ~/.config/llama.cpp/models.ini
install -m 755 "$backup/llama-research" ~/.local/libexec/llama-research
curl -fsS 'http://127.0.0.1:8080/models?reload=1' >/dev/null
systemctl --user restart llama-cpp-research.service
```

Die Rohdaten der Nachmessung einschließlich der englischen Szenen und Faktenprüfung stehen im Wiederherstellungspaket unter `benchmarks/results/follow-up.json`.
