# Benchmarks

Die [Auswertung](../docs/MODEL_BENCHMARKS.md) dokumentiert Hardware, Modellwahl, Testbedingungen und Grenzen der ursprünglichen Messreihe vom 18. November 2026.

| Dateien in [results/](results/) | Inhalt |
|---|---|
| `bench-*.json`, `*.stderr`, `*.csv` | Offizieller `llama-bench`, Zeit und Peak-RSS aus GNU time sowie Gerätewerte aus `nvidia-smi` |
| `context-*.jsonl` | Repositoriumsähnliche Testprompts, Prompt- und Decode-Raten, Latenz, Cache-Wiederverwendung und Retrieval |
| `qa-real-repo.json`, `qa-slot-final.jsonl` | Metriken des 100K-Quellcodetests und Test des Speicherns und Ladens eines Slots |
| `qa-*-tools.json`, `coding-*.time` | Tool-Erfolgsstatus und Laufzeit der getrennten Coding-Aufgaben |
| `human-writing-ab.json` | Neun gepaarte Writing-Aufgaben mit identischen Prompts, Textausgaben, Timing und Linter-Befunden |
| `media-mcp.json` | Drei Atelier-PNGs mit Seeds, Laufzeiten und Transport sowie technische WAV-Analyse für sechs GAF-Aufträge |
| `final-cleanup.json` | Cyber-Tiel-Abnahme mit den beiden lokalen CLI-Clients sowie die neuen Research-, Tool- und Writing-Prüfungen |
| `advanced-performance.json` | Neue Baseline, A/B-Vergleiche, Cache-Zähler und Prozess- sowie GPU-Messwerte |
| `follow-up.json` | Voller 256K-Kalt-/Warmlauf, Deep-Research-Synthese, vier Writing-Szenen und getrennte Faktenprüfung |

Absolute lokale Home-Pfade wurden normalisiert. Vom realen Repository-Test sind nur Status und Messwerte enthalten. Die ursprünglichen vollständigen Agententraces bleiben auf dem Laptop.

## Kurzbenchmark wiederholen

Die GPU sollte genügend freien VRAM haben. Schließe einen laufenden Chat ab und beende bei Bedarf den llama.cpp-Benutzerdienst vor dem direkten Benchmark. Die Messungen für große Modelle verwendeten zeitweise das Fedora-Leistungsprofil. Halte beim Vergleichen Energieprofil, GPU-Auslastung, Modell und Parameter fest.

```bash
mkdir -p "$HOME/llama-bench-neu"
./benchmarks/run.sh "$HOME/llama-bench-neu/cyber-tiel" \
  "$HOME/models/gguf/Cyber-Tiel-Coder-35B-A3B.APEX-I-MiniPlus-V2.1.gguf" -p 8192,16384 -n 128 -r 2
```

Die Option `-p` misst Prefill und `-n` Decode separat. Für Decode nach einem gefüllten Kontext den Router-Test verwenden. Das Skript lässt vorhandene Ausgabedateien unangetastet.

## Langkontext wiederholen

Starte dafür den Router. Der Test lädt das gewählte Profil und belegt dessen einzigen Modellslot. Die Eingabe besteht aus generiertem Python-Quellcode mit drei bekannten Fakten. `--reuse-prefix` prüft zusätzlich wiederverwendete Prompt-Tokens in den aufeinanderfolgenden Läufen.

```bash
mkdir -p "$HOME/llama-bench-neu"
set -o pipefail
python3 benchmarks/bench-context.py coding-long-256k 8192 16384 32768 65536 131072 196608 253952 \
  --structured --reuse-prefix --fixed-prefix-modules 20 | tee "$HOME/llama-bench-neu/context-256k.jsonl"
```

Die Retrieval-Spalte prüft, ob drei erwartete Werte in der Antwort vorkommen. Für Coding-Qualität zählen zusätzlich der reale Repository-Test, die beiden Agentenaufgaben und deren Unit Tests.

`--cache-prompt` aktiviert die serverseitige Wiederverwendung bei gleichbleibender Position der gesuchten Fakten. Für einen Kalt-/Warm-Vergleich lade das Profil frisch und wiederhole genau dieselbe Eingabe.

```bash
python3 benchmarks/bench-context.py coding-long-256k 253952 --structured --repeat 2 --cache-prompt
```

Die drei 8K-Baselines verwenden denselben Aufruf ohne `--reuse-prefix` und mit genau einem Zielwert. Warte jeweils auf das Ende des Aufrufs, bevor der Router zum nächsten Modell wechselt.

```bash
for profile in coding-long-256k research creative-writing; do
  python3 benchmarks/bench-context.py "$profile" 8192 --structured
done
```

## Temporäre Router-Vergleiche wiederholen

Der Produktionsrouter muss während des Vergleichs frei von geladenen Modellen sein. Warte laufende Chats und Research-Aufträge ab und entlade das aktuelle Modell im Modellmenü. Der Benchmark startet einen temporären Benutzerdienst auf `127.0.0.1:18083` und beendet ihn nach dem Test. Der Testlauf bricht ab, wenn der Produktionsrouter wieder ein Modell lädt.

```bash
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" thp-a1 coding-long-256k A prefix,48
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" thp-b1 coding-long-256k B prefix,48
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" cache-2048 coding-long-256k A branch,104 cache-ram=2048 verbosity=6
./benchmarks/run-perf-case.sh "$HOME/llama-perf-neu" cold256 coding-long-256k A context,253952
```

`A` übernimmt die glibc-Umgebung des Produktionsrouters. `B` setzt zusätzlich `glibc.malloc.hugetlb=1` und übernimmt die übrigen Tunables. Um eine frühere Ausgangskonfiguration zu reproduzieren, setze `LLAMA_PERF_PRESETS` auf die gesicherte `models.ini`. Verwende pro Durchlauf eine eigene ID. Die JSONL-Dateien enthalten Antwortqualität, Cache-Tokens, Latenz und Prozessdaten. `gpu.csv` enthält die während des gesamten Falls gemessenen Gerätewerte. [Auswertung und Rollback](../docs/PERFORMANCE_OPTIMIZATION.md)
