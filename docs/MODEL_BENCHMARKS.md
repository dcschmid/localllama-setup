# Modellvergleich auf dem Framework Laptop 16

Stand 19. November 2026. GB bezeichnet die dezimale Dateigröße. GiB und MiB bezeichnen die binären Speicherwerte. Die Modellkarten nennen den Trainings- oder Metadatenkontext. Die nutzbare Kontextlänge ergibt sich aus den lokalen Tests.

## Modellbereinigung

Die spätere Performance-Reihe umfasst eine neue Baseline für alle drei Modelle, THP-A/B, Batch- und Cache-Vergleiche sowie einen vollständigen kalten 256K-Prefill. In der neuen Offline-Abnahme bestanden Codex mit 32K und Claude Code mit 128K. Die Messbedingungen und der 32K-Komprimierungsabbruch von Claude Code sind getrennt ausgewertet. Die 256K-Nachmessung erreichte 6:34 Minuten kalt und 0,67 Sekunden bis zum ersten Token bei identischer Wiederholung. [Performance-Messung](PERFORMANCE_OPTIMIZATION.md)

Gemma 4 26B A4B QAT, Cyber-Tiel 35B A3B und Gemma 4 12B StyleTune bilden den lokalen Modellbestand mit insgesamt 37,14 GB. Beide Coding-Wrapper verwenden standardmäßig Cyber-Tiel.

Die Modellbereinigung betrifft Dateien unter `~/models/gguf/`. Die Spalte „Exklusiv“ gibt die vor der Entfernung von Btrfs gemessenen exklusiv belegten Blöcke an.

| Datei | Dateigröße | Exklusiv | Stand |
|---|---:|---:|---|
| `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | 2,33 GiB | 0 GiB | Entfernt |
| `gemma-4-12b-it-qat-q4_0.gguf` | 6,50 GiB | 6,50 GiB | Nach bestandener Claude-Abnahme entfernt |
| `LFM2.5-24B-A2B-Q4_K_M.gguf` | 13,53 GiB | 13,53 GiB | Entfernt |
| `mtp-Cyber-Tiel-Coder-35B-A3B.gguf` | 1,38 GiB | 1,38 GiB | Entfernt |
| **Gesamt** | **23,73 GiB** | **21,41 GiB** | **21,41 GiB freigegeben** |

Atelier nutzt einen separaten Qwen-Pfad mit eigener Inode und gemeinsam belegten Btrfs-Datenblöcken. Die Bildpipeline benötigt ihre eigene Datei weiterhin. In der llama.cpp-Modellbibliothek wurde kein Modellprojektor gefunden.

### Cyber-Tiel gegen die Ledger-Aufgabe

Die beiden CLI-Tests verwendeten dieselbe ursprüngliche Ledger-Fixture und denselben Aufgabenvertrag wie die historischen Gemma-QAT-Läufe. Für Cyber-Tiel wurden Q8_0-K/V, 32K Kontext und 256 Denk-Tokens als Router-Vorgabe verwendet. Für den zweiten hier aufgeführten Claude-Lauf wurde ein kürzerer Systemprompt gesetzt. Die Modelle liefen in getrennten Tests in der bestehenden lokalen Netzwerkisolation.

| Client | Ergebnis | Dauer und Durchsatz |
|---|---|---|
| Codex 0.169.0 | PASSED. Bugfix, Hilfsfunktion, sechs Unit-Tests und unabhängige Vertragsprüfung. 46.699 Prompt-Tokens wurden aus dem Cache wiederverwendet. | 403,31 s. Erster Prefill 8.128 Tokens mit 73,6 t/s. Decode je Turn 7,15–14,26 t/s. |
| Claude Code 2.1.326 | FAILED. Der erste Lauf endete am Zeitlimit nach 520 s. Der verkürzte Lauf las alle vier Dateien. Die unabhängige Prüfung des unveränderten Codes schlug fehl. | 550,00 s. Erster Prefill 3.065 Tokens mit 8,47 t/s. Der erste vollständige Decode-Turn erreichte 2,09 t/s. |

Die aktive Systemlast und in `vmstat` beobachtete Lesezugriffe von bis zu rund 720 MiB/s fielen mit den langsamen Läufen zusammen. In einem früheren Turn derselben Abnahme erreichte Cyber-Tiel 22,33 Decode-t/s. Die Spanne von 20–30 t/s war in den vollständigen Coding-Läufen nicht stabil erreichbar.

Nach dem autorisierten Neustart des Stageground-Entwicklungsservers stieg der verfügbare RAM im selben System von rund 4 auf 18 GiB. Claude Code wiederholte die Ledger-Aufgabe mit normalem Systemprompt und `--effort low`. Der Offline-Lauf bestand alle vier Unit-Tests und die unabhängige Vertragsprüfung in 288,61 s. Der erste Prefill verarbeitete 5.460 Tokens mit 359,08 t/s. In 14 Decode-Turns lagen die Werte bei 49,38–56,44 t/s, der Median bei 51,89 t/s. Die Messung verwendete vorübergehend das Leistungsprofil.

Nach beiden Abnahmen übernimmt `coding-fast` den geprüften Cyber-Tiel-Preset mit 32K und Q8_0-K/V. Die früheren Messungen zeigen den Durchsatzverlust bei knapperem Arbeitsspeicher.

### Wiederholungsmessung im normalen Energieprofil

Die native Chat-API beantwortete nach dem Wechsel auf `coding-fast` dieselbe Retrieval-Fixture bei 8K und 16K. Hier lief das ursprüngliche Laptop-Profil `low-power`. Die Messung erfasst eine strukturierte Antwort auf Repositoriumsdaten.

| Kontextprofil | Prompt-Tokens | Wiederverwendet | Prefill | Decode | Retrieval |
|---|---:|---:|---:|---:|---:|
| 8K | 7.819 | 0 | 374,49 t/s | 44,69 t/s | 3/3 |
| 16K | 16.024 | 179 | 379,78 t/s | 43,18 t/s | 3/3 |

Die knappe CUDA-Reserve von 512 MiB mit Q4_0-K/V erhöhte im isolierten Kurzbenchmark vor dem Stageground-Neustart den Decode-Durchsatz von 9,70 auf 10,99 t/s. Der freigewordene Arbeitsspeicher brachte den größeren Effekt. Das finale Profil behält die CUDA-Reserve von 1.024 MiB und Q8_0-K/V.

## Historische Auswahl vor den Downloads

| Kriterium | Gewicht | Grundlage der Auswahl |
|---|---:|---|
| Coding-Qualität | 25 % | Modellkarte und Repository-Benchmark mit passendem Harness, später lokal bestätigte Korrektheit und Unit Tests |
| Agentic Coding und Tools | 20 % | Tool-Template, lokaler API-Parser, mehrere Tool-Runden in Claude Code und Codex |
| Geschwindigkeit | 20 % | Prefill und Decode getrennt, dazu Bearbeitungszeit der Aufgabe |
| Langkontext | 15 % | Kandidaten ab 128K bevorzugt. Retrieval und Schlussfolgerungen bei langen Eingaben zählen |
| Speicherbedarf | 10 % | GGUF-Größe, CPU/GPU-Aufteilung, KV/Arbeitsbuffer und gemessener Peak |
| Stabilität | 5 % | CUDA-Laden, Modellwechsel, Tool- und Kontextfehler |
| Lizenz und Wartbarkeit | 5 % | Herkunft, Lizenzkette, eingesetztes Upstream-Format, dokumentiertes Template |

Die Gewichte steuern die Auswahl. Für reine Recherchekandidaten fehlen gemeinsame lokale Messwerte, daher gibt es für diese noch keine numerische Gesamtwertung. LFM erhielt den ersten Coding-Platz wegen der kompakten aktiven Parameterzahl, der offiziellen Quantisierung und des Agent-Trainings. Gemma 26B ist der Vergleich für Qualität, MoE und QAT. Gemma 12B dient als kleinerer offizieller Vergleich für den Alltag und die ersten Agententests. Die zweite Runde ergänzt Cyber-Tiel und StyleTune.

## Recherchierte Coding- und Alltagsmodelle

| Modell und Quelle | Herkunft, Architektur und Nennkontext | Quantisierung und Größe | Template, MTP und Bewertung |
|---|---|---|---|
| [LiquidAI LFM2.5-24B-A2B](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B-GGUF) | Offizielles LiquidAI-GGUF vom 09.10.2026. `lfm2moe`, 24B gesamt, rund 2B aktiv, 4 von 64 Experten. 10 Attention- und 30 Conv-Blöcke. 131.072 Tokens. [LFM Open License 1.0](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B/blob/main/LICENSE) | Q4_K_M 14,53 GB. Q4_0 13,58 GB, QAD Q4_0 13,58 GB, Q5_K_M 17,03 GB. | Eingebettetes LFM-Tool-Template. Publizierte LiveClaw-Ergebnisse sind Herstellermessungen. Gemischte Attention/Conv-Zustände bestimmen Kontext, Caching und Spezulation. Für die ausgewählte Datei ist kein MTP-Head dokumentiert. |
| [Gemma 4 26B-A4B IT QAT](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf) | Offizielles Google-QAT-GGUF vom 01.05.2026. 25,23B GGUF-Tensorparameter, rund 4B aktiv, 8 von 128 Experten. 5 volle Attention-Blöcke bei 30 Layern, sonst SWA. 262.144 Tokens. Apache 2.0. | QAT Q4_0 14,44 GB. Der separate Projektor hat 1,19 GB. [Community-PTQ](https://huggingface.co/bartowski/google_gemma-4-26B-A4B-it-GGUF) IQ4_XS 14,21 GB, Q4_K_M 17,04 GB, Q5_K_M 19,32 GB. | Gemma-Tool-Template mit optionalem Reasoning. QAT und PTQ basieren auf verschiedenen Checkpoints. Die Community-PTQ-Karte listet Assistant-Heads, deren Eignung für das offizielle QAT separat zu belegen wäre. |
| [Gemma 4 12B IT QAT](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) | Offizielles Google-QAT-GGUF vom 05.06.2026. 11,91B dense, 8 volle Attention-Blöcke bei 48 Layern, sonst SWA. 262.144 Tokens. Apache 2.0. | QAT Q4_0 6,98 GB. Separater Projektor 0,175 GB. | Gemma-Tool-Template. VRAM-Puffer und Kontext verhindern bei größeren Profilen die Gleichsetzung von Dateigröße und Vollauslagerung. |
| [Cyber-Tiel-Coder MiniPlus V2.1](https://huggingface.co/IsValorum/Cyber-Tiel-Coder-35B-A3B-APEX-I-MiniPlus-V2.1-GGUF) | IsValorum-Community-Quantisierung vom 29.09.2026. Ableitung von abliteriertem Ornith 1.5. `qwen35moe`, 34,66B GGUF-Parameter, 3B aktiv, 262.144 Tokens. Karte meldet MIT und verweist auf die Basiskette. | Tensorweise APEX-I MiniPlus 14,75 GB, MTP-Sidecar 1,48 GB. Ein niedriger quantisiertes NanoPlus existiert separat. | Eingebettetes Jinja-Template mit XML/JSON-Toolformat. Herstellerwerte für Perplexity und SWE-Subset sind Hinweise. Auf diesem Rechner zählt die lokale defensive Codeprüfung. |
| [KAT-Coder V2.5 Dev](https://huggingface.co/Kwaipilot/KAT-Coder-V2.5-Dev) | Original von Kwaipilot, 23.07.2026, Apache 2.0. Qwen3.6-35B-A3B-Fine-Tune, 8 von 256 Experten, 10 volle Attention-Blöcke bei 40 Layern, 262.144 Tokens. | Original-Safetensors, [Community GGUF](https://huggingface.co/bartowski/Kwaipilot_KAT-Coder-V2.5-Dev-GGUF) IQ4_XS 18,81 GB, Q4_K_M 21,39 GB, Q5_K_M 25,02 GB. [Abliterated Community GGUF](https://huggingface.co/PhillyLabs/KAT-Coder-V2.5-Dev-35B-A3B-ABLITERATED-UNCENSORED-PHILADELPHIA-CLASS) Q4_K_M 21,17 GB. | Kwaipilot evaluiert mit Claude Code bzw. eigenem Harness. Original-Konfiguration `mtp_num_hidden_layers=0`. Die [Community-MTP-Ausgabe](https://huggingface.co/offmonreal/KAT-Coder-V2.5-Dev-MaxQuality-MTP-GGUF) ist eine abweichende Konvertierung. Mehr CPU-Expertenspeicher als Cyber/LFM. |
| [Tiel-Coder MiniPlus V2.1](https://huggingface.co/IsValorum/Tiel-Coder-35B-A3B-APEX-I-MiniPlus-V2.1-GGUF) | Community-Quantisierung vom 22.09.2026, aus dem [Tiel-Quant von Ornith 1.5](https://huggingface.co/peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF). `qwen35moe`, 35,51B GGUF-Parameter, rund 3B aktiv, 262.144 Tokens. Karte meldet MIT. | APEX-I MiniPlus 15,23 GB. Das Schwesterprojekt bietet zusätzliche Quantisierungen und MTP-Ausgaben. | Jinja-Tool-Template. Vergleichskandidat für normale SWE-Aufgaben, Instruktionstreue und wiederholte Tools. Die publizierte SWE-Stichprobe umfasst 25 Aufgaben. |
| [Qwen3.8-35B-A3B Distill](https://huggingface.co/empero-ai/Qwen3.8-35B-A3B-Distill-GGUF) | Offen publizierte Distillation von empero-ai, GGUF vom 16.09.2026, Apache 2.0. `qwen35moe` mit 8 von 256 Experten, rund 3B aktiv, 10 volle Attention-Blöcke bei 40 Layern, 262.144 Tokens. | IQ3_M 16,34 GB, IQ4_XS 19,63 GB, Q4_K_M 21,71 GB, Q5_K_M 25,35 GB. [Abliterated Community GGUF](https://huggingface.co/IsValorum/Qwen3.8-35B-A3B-Distill-MTP-APEX-I-MiniPlus-V2.1-Abliterated-GGUF) 14,66 GB sowie Q4_0- und Q8_0-MTP-Sidecars. | Eingebettetes Qwen-Tool-Template. Originalkonfig meldet einen MTP-Layer. Die meisten sparsamen Varianten tauschen Gewichtspräzision gegen GPU-Platz. Wirkungen der Abliteration sind lokal offen. |
| [Sage A1.5](https://huggingface.co/InternScience/Sage-A1.5-Q4_K_M-GGUF) | InternScience-Original vom 15.10.2026, offizielles GGUF vom 21.10.2026, Apache 2.0. `qwen35moe`, 35,51B Parameter, 8/256, 262.144 Tokens. | Q4_K_M 21,71 GB, offizielle Q8-Ausgabe und Community-Quants verfügbar. | Neuerer Coding-Kandidat mit nativem MTP-Layer laut Konfiguration. Eingebettetes Tool-Template. Rückstellung wegen Gewichtsgröße und Messpriorität. |
| [Laguna XS 2.1](https://huggingface.co/poolside/Laguna-XS-2.1-GGUF) | Poolside Original und offizielles GGUF vom Juni 2026. `laguna`, 33B/3B, 8/256, 262.144 Tokens, OpenMDW 1.1. | Q4_K_M 20,27 GB, BF16 deutlich größer. | Poolside evaluiert agentische SWE-Aufgaben mit eigener Umgebung. Die Model Card verweist für Unterstützung auf [Upstream-PR 25165](https://github.com/ggml-org/llama.cpp/pull/25165). Auslastung und Tool-Parser blieben lokal offen. |
| [Nemotron 3.5 Lightning](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF) | NVIDIA-Original mit ggml-org-Konvertierung vom 11.08.2026. GGUF `nemotron_h_moe`, 31,58B Parameter, rund 3B aktiv, 6 Experten je Token. GGUF meldet 1.048.576 und die Original-Konfiguration 262.144. NVIDIA-Modelllizenz. | Offizielle NVIDIA-BF16/NVFP4- und weitere Community-Formate vorhanden. | Hybridzustand, natives Template und spekulative Variantenausgaben verdienen einen separaten Test. Kontext-Metadaten sind widersprüchlich und kein Nachweis für den Laptop. |
| [Horus Cyber Nano 1.0](https://huggingface.co/tokenaii/Horus-Cyber-Nano-1.0-GGUF) | TokenAI nennt 16B Gesamtparameter und MoE. Kandidat für defensive Audits, keine lokale Wertung. | Anbieter-GGUF nach Modellkarte. | Technisches Ranking zurückgestellt, bis CUDA-Kompatibilität und reproduzierbare defensive Qualität belegt sind. |

Für Qwen35-MoE ergibt die Modellkonfiguration bei 10 vollen Attention-Blöcken und 2 KV-Köpfen à 256 Dimensionen rund 1,4 GiB Q4_0-KV bei 262.144 Tokens. Dieser Rechenwert umfasst nur K/V. Recurrent-Zustände, GGUF, CUDA-Kontext, Compute-Buffer und Checkpoints kommen hinzu. Der Router hält je ein Modell. Die NVIDIA-Verfügbarkeit wird vor jeder Messreihe geprüft.

## Schreibmodelle

Die Schreibprobe bewertet englische Prosa, Figurenstimme, Konsistenz, Dialog und Befolgung konkreter Vorgaben. Tool-Abrufe fließen hier nicht ein.

| Kandidat | Kategorien und Metadaten | Auswahl |
|---|---|---|
| [Gryphe StyleTune 12B](https://huggingface.co/Gryphe/Gemma-4-12B-StyleTune) | Gemma-4-Schreib-Fine-Tune, [Community Q4_K_M 7,95 GB](https://huggingface.co/mradermacher/Gemma-4-12B-StyleTune-GGUF), Apache 2.0, 262.144 nominal. | Vergleich mit Gemma QAT bei gleicher Schreibaufgabe. |
| [Gemma The Writer 9B Heretic](https://huggingface.co/DavidAU/Gemma-The-Writer-9B-HERETIC-Uncensored-Abliterated) | Überarbeitete Abliteration eines Gemma-2-Schreibmerges. [Q4_K_M 5,76 GB](https://huggingface.co/mradermacher/Gemma-The-Writer-9B-HERETIC-Uncensored-Abliterated-GGUF), 8192 nominal. Herkunft und Gemma-2-Lizenzbedingungen beachten. | Vergleichskandidat für kurze englische Geschichten und Dialog. |
| [Restless Quill 10B](https://huggingface.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF) | Gemma-2-Schreibmerge mit Uncensored-Kennzeichnung. IQ4_XS 5,87 GB oder Q4_K_M 6,10 GB, 8192 nominal. Quant-Repo meldet Apache 2.0. | Optionaler zweiter Prosa-Vergleich bei geklärter Lizenzkette. |
| [Himeyuri Magnum 12B HereticLoRA](https://huggingface.co/yamatazen/Himeyuri-Magnum-12B-HereticLoRA-Q4_K_M-GGUF) | Community-Fine-Tune und Q4_K_M 7,48 GB. GGUF meldet 1.024.000 Tokens. Das Quant-Repo führt keine eigene Lizenzangabe. | Kein Download. Stil und Lizenzkette bleiben offen. |

## Historische lokale Messwerte

Die Tabelle verwendet die offizielle `llama-bench`-Ausgabe. Prefill und Decode werden in diesen Kurztests separat gemessen. Der Decode-Wert beginnt ohne langen Prompt. Die Speicherspalten zeigen Peak-RSS inklusive dateigestützter Mappings und den gesamten dedizierten GPU-Peak inklusive Desktop. Die Leistungswerte sind beobachtete GPU-Spitzen in 500-ms-Stichproben. Kleine Modelle liefen im ursprünglichen Fedora-Profil Energiesparen. Große Modelle liefen während einer temporären Performance-Lease.

| Modell | Quant | Prefill 8K / 16K t/s | Decode t/s | RAM Peak | VRAM Peak | GPU-Spitze | Coding und Tools |
|---|---|---:|---:|---:|---:|---:|---|
| Qwen3 4B Instruct 2507, vorhandene Datei | Q4_K_M | 2.651 / 2.573 gemeinsam mit je 96 Decode-Tokens | — | 2,80 GiB | 5.084 MiB* | 101,1 W | API-Smoke und kleine Offline-Chatprobe |
| Gemma 4 12B IT | QAT Q4_0 | 1.528 / 1.335 | 40,70 | 7,08 GiB | 6.924 MiB | 100,6 W | Bugfix und Refactor mit beiden CLI-Agenten |
| Gemma 4 26B A4B IT | QAT Q4_0 | 535 / 528 | 54,73 | 14,21 GiB | 6.778 MiB | 58,8 W | Benchmark mit GPU/CPU-Aufteilung |
| LFM2.5 24B A2B | Q4_K_M | 565 / 545 | 66,61 | 14,20 GiB | 6.804 MiB | 52,0 W | Langkontextmessung weiter unten |
| Cyber-Tiel-Coder 35B A3B | APEX-I MiniPlus | 417 / 563 | 66,59 | 14,55 GiB | 6.824 MiB | 65,5 W | 16K-Retrieval 3/3 und zweistufige Toolkette bestanden |

*Sampler-Spitze des Qwen-Kombitests: 5.084 MiB. Der Wert ist das rohe Geräte-Maximum. Qwen verwendete je zwei Kombiläufe, Gemma und LFM je zwei Wiederholungen pro Rubrik. Cyber-Tiel verwendete einen Lauf pro Rubrik ohne zusätzlichen Warmup. Unterschiedliche Startzustände begrenzen die Vergleichbarkeit.

### Praktische Coding-Fixture in isoliertem Netzwerk

| Client | Modell / Kontextgröße | Aufgabe | Verifizierte Unit Tests | Gesamtzeit |
|---|---|---|---:|---:|
| Claude Code 2.1.326 | Gemma 4 12B QAT / 32K | Dateianalyse, globales Event-Deduplizieren, Normalisierung von Währungskürzeln, Hilfsfunktion und Regressionstests | 4 bestanden | 177,8 s |
| Codex CLI 0.169.0 | Gemma 4 12B QAT / 32K | Äquivalente Aufgabe in getrennter Fixture, sechs bestätigte Shell-Aufrufe | 5 bestanden | 85,6 s |

Beide Änderungen wurden unabhängig mit `python -m unittest discover -s tests -v` geprüft. Bei mehreren Claude-Coding-Turns lagen die tatsächlichen Decode-Raten bei ungefähr 25–26 t/s. Claude protokollierte 16 Agententurns und 4.079 ausgegebene Tokens. Codex protokollierte 1.835 ausgegebene Tokens. Wiederholt eingesandte und zwischengespeicherte Prompt-Tokens sind in den Client-Traces separat ausgewiesen.

### LFM2.5 bei langen Repository-förmigen Eingaben

Alle Zeilen verwenden das auf 131.072 Tokens geladene LFM-Profil, CUDA für die übrigen Tensoren, alle 40 MoE-Expertenschichten auf der CPU, 1.024/512 Batch/Microbatch und Q8_0-K/V. Das Reasoning wurde begrenzt. Jede Zeile verarbeitet den Prompt neu. Der Peak über die gesamte Reihe lag bei rund 6,8 Tausend MiB laut `nvidia-smi`-Stichproben.

| Ziel | Tatsächliche Prompt-Tokens inkl. Template | Prefill t/s | Decode t/s | Erster Token | Erste sichtbare Ausgabe | Gesamt | Retrieval |
|---|---:|---:|---:|---:|---:|---:|---:|
| 8K | 7.499 | 450,0 | 46,4 | 16,7 s | 18,1 s | 24,9 s | 3/3 |
| 16K | 15.815 | 489,5 | 45,2 | 32,4 s | 33,8 s | 40,9 s | 2/3 |
| 32K | 32.195 | 447,6 | 42,9 | 72,0 s | 73,4 s | 80,9 s | 3/3 |
| 64K | 64.955 | 476,3 | 38,0 | 136,4 s | 138,3 s | 146,5 s | 2/3 |
| 128K | 130.475 | 459,9 | 35,1 | 283,8 s | 285,7 s | 294,7 s | 0/3 |

LFM bestand den technischen 128K-Lauf. Die Wiedergabe versagte bei dieser Aufgabe. Ein früherer 16K-Lauf mit automatischer Tensorplatzierung und unbeschränktem Reasoning erreichte 36,5 Decode-t/s, gab im 200-Token-Budget aber keine sichtbare Lösung aus. Für die Eignung zählen daher sowohl Antwortinhalt als auch Prefill und Reasoning-Zeit.

### Offload und RAM

LFM bei 4K mit explizit 26 CPU-Expertenschichten erreichte 567,1 Prefill- und 64,3 Decode-t/s. Mit 40 CPU-Expertenschichten waren es 589,8 und 67,8 t/s bei einem Durchlauf. Der Langkontexttest nutzte deshalb alle CPU-Experten. Der lokale 128K-Lauf wurde über den Router in 1,24 s bei bereits warmem Dateicache aufgerufen. Der Gesamtprozess eines Benchmarks umfasst außerdem Modellladen, Warmup und Wiederholungen.

### Multi-Token Prediction bei Cyber-Tiel

Gleiche 32K-Routerfenster, gleicher strukturierter Prompt mit 16.024 Tokens. Der Speicherpuffer wurde für die Variante mit Sidecar von 1.024 auf 2.048 MiB gesetzt. Dadurch umfasst der Vergleich die jeweils lauffähige Konfiguration inklusive Tensor-Fit.

| Modus | Prefill t/s | Decode t/s | Erster Token | Gesamt | Fakten | Toolkette |
|---|---:|---:|---:|---:|---:|---|
| Standard | 385,8 | 53,8 | 41,5 s | 43,2 s | 3/3 | bestanden |
| MTP-Sidecar | 312,9 | 53,0 | 51,2 s | 53,2 s | 3/3 | bestanden |

68 von 108 Draft-Tokens wurden akzeptiert. Die gemessene Aufgabe war mit Sidecar langsamer. Die normalen Coding-Profile bleiben auf der Standard-Inference. Zum Wiederholen dienen die Upstream-Optionen `--spec-type draft-mtp --spec-draft-model <Sidecar>`.

### Cyber-Tiel bei 128K, 192K und 256K

Die drei großen Prompts wurden in derselben auf 262.144 Tokens geladenen Instanz durchlaufen. CUDA-Fit, Flash Attention, 1.024/512 Batch/Microbatch, Q4_0-K/V und begrenztes Reasoning galten durchgehend. Die 128K- und 192K-Aliase wurden separat mit ihren eingestellten Kontextgrenzen geladen. Die Ergebnisse bewerten drei verteilte Fakten und eine Regel aus einer Repository-förmigen Eingabe. Die Regel war inhaltlich richtig. Einzelne Dateiverweise im 256K-Ergebnis waren ungenau.

| Ziel | Prompt gesamt | Cache-Tokens | Prefill t/s neu | Decode t/s | Erster Token | Erster gesuchter Fakt | Gesamt | Fakten |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 128K | 130.651 | 0 | 558,7 | 12,32 | 233,9 s | 235,0 s | 240,8 s | 3/3 |
| 192K | 196.291 | 179 | 484,6 | 8,92 | 404,8 s | 406,3 s | 416,6 s | 3/3 |
| 256K | 261.688 | 195.775 | 413,3 | 7,11 | 159,7 s | 161,5 s | 173,5 s | 3/3 |

Die 256K-Zeile ist die Fortsetzung des 192K-Prompts mit 65.913 neu berechneten Tokens. Ein 256K-Kaltlauf hat eine andere Wartezeit. Die Live-Wiederverwendung ist abhängig von übereinstimmenden Präfixen und wiederherstellbaren Hybridzuständen. Der Router meldete bei einem Zwischenzustand rund 972 MiB gegenüber 512 MiB zulässigem separatem Prompt-Cache. Die aktive Slot-Wiederverwendung bei 256K funktionierte trotzdem.

Die langen Tests verwenden reservierten Platz für das Chat-Template und die Antwort. Ein maximal konfigurierbares Fenster entspricht daher keiner gleich großen Texteingabe. Diese Profile eignen sich für gezielte Analysen mit akzeptabler Wartezeit. Für interaktives Coding war der kürzere Standardpfad deutlich reaktionsschneller.

Im erweiterten Cyber-Tiel-Lauf lagen die beobachteten Spitzen bei 14,97 GiB RSS, 6.762 MiB VRAM und 86,8 W GPU-Leistungsaufnahme. Die Startmessung der geladenen 256K-Instanz war 3,67 s. Die Kurzprofile brauchten im MTP-Vergleich 3,66 s ohne und 5,00 s mit Sidecar, jeweils einschließlich Router-Aufruf und bei warmem oder teilweise warmem Dateicache.

### Reeller Quellcode im 128K-Profil

Cyber-Tiel bearbeitete 100.708 gemessene Archivtokens aus echtem Upstream-Quellcode von b12503 in einem zweistufigen Verlauf. Das Modell fand den Reload-Endpunkt, die Vergleichsfunktion für Preset-Optionen, den Grund für das Freigeben des Mutex und das Verhalten von `load-on-startup` beim Reload. Alle vier Aussagen wurden im Quelltext gegengeprüft. Im zweiten Turn wurden 49.433 Tokens wiederverwendet und 51.480 neu verarbeitet. Gesamtdauer 179,1 s, Decode im zweiten Turn 15,0 t/s. Zusätzlich antworteten beide lokalen CLI-Clients im gleichen Profil mit dem erwarteten Testtext.

### NVMe und Ladepfade

LFM Q4_K_M, CUDA plus 40 MoE-Expertenschichten auf der CPU, ein 4K-Prefill und 96 Decode-Tokens. Das Dateisystem blieb im laufenden Zustand. Die unterschiedlichen Page-Cache-Zustände begrenzen die Aussage zu isolierter Kaltladezeit.

| Ladepfad | Prefill t/s | Decode t/s | Gesamt inkl. Laden | Peak RSS | Reportete Dateisystem-Eingaben |
|---|---:|---:|---:|---:|---:|
| mmap | 526,9 | 72,7 | 18,39 s | 14,20 GiB | 33.130.384 Blöcke |
| Direct I/O | 586,8 | 46,2 | 24,74 s | 8,46 GiB | 40.536.288 Blöcke |

Die Standardprofile verwenden mmap. Direct I/O reduzierte den gemessenen RSS, benötigte für den gesamten Test aber mehr Zeit. Der Dateisystem- oder Slot-Cache verändert die Bereitstellung von Gewichten und vorberechnetem Prompt-Zustand. Die gemessenen Decode-Raten bleiben von GPU, Host-RAM und Kontext abhängig.

### Prosa und defensive Codeanalyse

Beide Schreibprofile lieferten die englische Bahnhofsszene mit der vorgegebenen Dialogzeile und einer physischen Handlung am Schluss. StyleTune unterschied die beiden Figurenstimmen im Dialog deutlicher. Gemma 4 12B QAT generierte in dieser Probe schneller (28,9 gegenüber 19,2 t/s). Die Prosawertung beruht auf einer Stichprobe. Für Alltag und Recherche bleibt QAT die schnelle Wahl, für englische Szenen steht das spezialisierte StyleTune-Profil bereit.

Cyber-Tiel erkannte im lokalen defensiven Review die unsichere Freigabe bei fehlenden Eingaben und die Pflicht zu nichtleeren, case-sensitiven Tenant-IDs. Der erste Korrekturvorschlag verwendete einen direkten Schlüsselzugriff und ließ damit den Randfall fehlender Schlüssel offen. Modellempfehlungen für Sicherheit bleiben überprüfungsbedürftig.

Der separate Slot-Test mit Qwen3 4B speicherte 2.683 Tokens in rund 377 MiB in 78 ms. Das Modell wurde entladen und in 1,37 s neu geladen. Restore brauchte 60 ms. Der nachfolgende Prompt nutzte 2.663 Cache-Tokens und brauchte inklusive Decode 0,22 s. Der Testzustand blieb auf die Test-Fixture begrenzt. Persistente Slots sind im normalen Chatbetrieb aus.

## Human Writing mit Gemma 4 12B StyleTune

Stand 18. November 2026. Neun Aufgaben je einmal mit und ohne Skill auf demselben Q4_K_M-GGUF und demselben 16K-Profil auf der RTX 5070 gemessen. Die Baseline verwendete das Gemma-Template aus der Modelldatei, die zweite Reihe ergänzte den Skill. Nutzertexte und Tokenbudgets waren je Paar identisch. Temperatur 0,55, Top-p 0,90, Top-k 40, Seed 90.210, Thinking aus und Prompt-Cache aus. Persönliche Stilproben und Pressetexte in diesem Test sind synthetisch.

Die redaktionelle Prüfung liest die Antworten paarweise. Sie betrachtet Erzählperspektive, Rhythmus, Abwechslung, Figurenstimmen, Originalität und Übereinstimmung mit den gelieferten Fakten. Die Linter-Spalte zählt die heuristischen Einzelbefunde. Bei fiktionalen Texten bleiben bewusst eingesetzte Wiederholung und Rhythmus redaktionelle Entscheidungen.

| Aufgabe | Wörter ohne / mit Skill | Linter-Befunde ohne / mit | Redaktioneller Vergleich |
|---|---:|---:|---|
| Englische Riff-Racers-Geschichte | 1.048 / 1.072 | 5 / 4 | Beide im Zielbereich 900–1.200 mit offener Entscheidung und erkennbaren Stimmen. In der Baseline entsteht ein Widerspruch um den Fahrer. Mit Skill ist Cleos Handlungsentscheidung am Zeitnahmetisch klarer, das Achsenmotiv wiederholt sich stark. Der Regen am Schluss bleibt ohne Übergang. |
| Dialog auf der Fähre | 247 / 224 | 0 / 0 | Beide im Zielbereich. Bea und Rowan sind ohne Namensnennung unterscheidbar. Ihre Handlung am Funkgerät gibt der Unterbrechung mit Skill mehr Folgen. Der plötzlich gemeldete Vorfall wirkt konstruiert. |
| Englische Heavy-Metal-Rezension | 290 / 296 | 0 / 1 | Beide behandeln das Tempo. Beide ergänzen eine unbelegte Debütbehauptung. Mit Skill widersprechen sich Instrumente und Gesang in der Beschreibung von „Third Shift“. Zudem macht der Text daraus den einzigen Titel mit Gesangstext. Die Vorlage beschränkt nur das Thema Nachtarbeit auf diesen Titel. |
| Deutscher Blog | 273 / 251 | 1 / 1 | Beide nennen die geplanten 40 cm und wechseln von der gewünschten Ich-Perspektive zu Wir. Beide ergänzen Details außerhalb der Vorlage. Mit Skill liegt die Antwort neun Wörter unter dem Mindestumfang. |
| Englischer Devlog | 202 / 168 | 1 / 0 | Die konkrete Kurvenszene funktioniert mit Skill besser. Beide nennen den 90-Sekunden-Replay und den offenen Mehrspielertest, formulieren die Wirkung dennoch zu verbindlich. Beide bleiben unter 220 Wörtern. |
| Floskeltext überarbeiten | 44 / 27 | 0 / 0 | Mit Skill entfällt der leere Schlusssatz. Beide ändern „reduced“ zu „stopped“ und überzeichnen damit den Effekt am Proberaum. |
| Guten Text erhalten | 30 / 31 | 0 / 0 | Die Baseline streicht `me`. Mit Skill bleibt der Wortlaut unverändert. |
| Geschützte Fakten, Zitat, Zahlen und Link | 49 / 47 | 0 / 0 | Überschrift, Version, Name, Datum, 3,5-MB/s-Angabe im Originalformat, Zitat, Befehl und Markdown-Link bleiben in beiden Varianten erhalten. Beide machen aus der teambezogenen Testlücke eine unpersönliche Aussage. |
| Persönliche Stilkalibrierung | 157 / 169 | 3 / 3 | Beide verwenden erkennbare Textbelege und nennen Unsicherheiten. Mit Skill hat das Profil mehr wiederverwendbare Felder, einzelne Einträge gehen über die drei Belege hinaus. |

| Messwert | Ohne Skill | Mit Skill |
|---|---:|---:|
| Decode, Median | 24,67 t/s | 23,50 t/s |
| Prompt-Verarbeitung, Median | 0,28 s | 2,88 s |
| Laufzeit aller neun Anfragen | 138,61 s | 164,08 s |
| Prompt-Tokens je Anfrage | 73–153 | 2.543–3.498 |
| Linter-Einzelbefunde gesamt | 10 | 9 |

Der Systemkontext kostet je nach Modus zusätzlich **2.423–3.345 Tokens**, im Median **2.725 Tokens**. Die Laufzeit umfasst die HTTP-Anfrage und die jeweilige Antwortlänge. Für kurze Überarbeitungen fällt die zusätzliche Prompt-Verarbeitung stärker auf. Die Creative-Writing-Regeln helfen bei Figurenarbeit und bei der Erhaltung eines bereits guten Textes. Sachtexte mit vorgegebenen Fakten brauchen weiterhin eine Quellen- und Umfangsprüfung. Der Vergleich ist eine Einzelmessung pro Aufgabe und belegt keine allgemeine Qualitätssteigerung.

Prompts, Texte, Timing-Antworten und Linter-Einzelbefunde liegen unter `~/dev/github/localllma-setup/benchmarks/results/human-writing-ab.json`. Der lokale Cache enthält dieselben Messdaten in `~/.cache/llama.cpp/writing/benchmark-2026-11-18.json`.

### Quellenbindung und Faktenprüfung

Die Nachprüfung wiederholte fünf Sachtext-Fälle mit `[fakten]` bei den ursprünglichen Sampling-Einstellungen. Der Metal-Text enthielt weiterhin unbelegte Produktionsdetails. Der Blog ergänzte Raumbeobachtungen, und der Devlog machte aus einem erfolgreichen Test eine breite Zusage. Beim einfachen Rewrite wurde aus „reduced“ wieder „stopped“. Im geschützten Release-Text wechselte die teambezogene Testlücke erneut in eine unpersönliche Aussage. Bei einer Kontrollaufgabe ohne Quellen gab das Modell die fehlenden Angaben an.

In einem zweiten Test lieferte der vorhandene Websearch-MCP den öffentlichen RFC 2606. StyleTune extrahierte zwei belegte Fakten und schrieb daraus einen Entwurf. Der Entwurf behielt die Kernfakten und Links und enthielt zwei zusätzliche Einordnungen. Ein separater Audit-Auftrag markierte beide. Der korrigierte Text stimmte bei den geprüften Aussagen mit dem Faktenblatt überein. In einem weiteren Test bewahrte der Rewrite mit freigegebenem Faktenblatt ausdrücklich „reduced“ und beide ursprünglichen Beobachtungen. [Primärquelle des Webtests](https://www.rfc-editor.org/rfc/rfc2606.html)

Die Ergebnisse zeigen, wo eine separate Faktenprüfung hilft. Sie belegen keine verlässliche Fehlerfreiheit des Modells. Die Rohdaten liegen unter `~/dev/github/localllma-setup/benchmarks/results/human-writing-facts.json`.
