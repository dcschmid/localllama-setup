# Gemma 4 Final-Setup Migration Report (2026-11-24)

Finale Konfiguration: **zwei** Modelle, beide nativ 262144 Kontext / 8192
Ausgabe / Compaction 85 %, llama.cpp b12628 (offizieller CUDA-Build, Commit
8a97fa98a), Router `--models-max 1` (eine Instanz zur Zeit).

## Modellinventar & Freigabestatus

| Modell | Datei | Revision-Pin | SHA256 (== HF-LFS) | Lizenz | 256K-Status |
|---|---|---|---|---|---|
| research-code (Coding/Research/Pi) | Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf | f9093662 | 3c13133469e43131… | gemma-Tag, Basis Apache-2.0 | s. results |
| story (Story/Artikel/Human Writing) | Gemory-26B-A4B-Q4_K_M.gguf | a8bb79d6 | 4991d114e7219e43… | apache-2.0 | s. results |

Aussortiert: Ortenzya 31B dense (gpu-layers 0–24 gemessen; 8 GB VRAM +
256K-KV q8_0 → Lade-OOM bzw. Desktop-Reserve verletzt; Prefill auf CPU ~3–4
T/s zu langsam für Produktion). Dateien bleiben bis zum Dual-PASS als
Rollback.

## Serverprofile (deploymentfertig in config/models.ini.in)

Beide: `ctx-size 262144, parallel 1, fit off, flash-attn on,
cache-type k/v q8_0, batch 2048, ubatch 64, cpu-moe (MoE-Experten auf RAM),
sleep-idle 900s`. research-code temp 0.6; story temp 0.7/top-p 0.95/top-k 64
(Q4-Sampler-Hinweis der Gemory-Karte: 0.2–0.7 Bereich, bewusst nicht 0.6
erzwungen). n-gpu-layers: Router-Standard (volle Offload-Entscheidung pro
Schicht durch llama.cpp fit=off-Pfad); Artikel-Variante brauchte gpu-layers
und wurde verworfen — Messwerte siehe cleanup manifest.

## 256K-Nachweise

Urteil bleibt BLOCKED (256K-Akzeptanz), aber jetzt mit vermessener Grenze
statt Pauschale. Ladder-Modus (proportionale Sonden 4 %/40 %/80 %/92 %,
docs/results/*-256k-ladder.json, 2026-11-25, Router temp 0):

- docs/results/research-code-256k.json — Voll 244 K/229 K: Antwort leer bzw.
  später Abruf falsch. Ladder 131 K: 3/4 korrekt (KEY-080 falsch) — die
  Fehlerkante ist nicht monoton; verlässlich verifiziert ist Faktabruf bis
  ~40 K, freigegeben bis 100 K, darüber experimentell.
- docs/results/story-256k.json — Voll 244.823 Prompt-Tokens real verarbeitet
  (kein Truncation), Faktenabruf 10K/100K korrekt, 200K/240K falsch (bei 0 °C
  reproduziert: alle Schlüssel mit KEY-100-Wert). Ladder 131 K: 0/4 —
  Ladder-Zeilen behalten keinen Antworttext, damit nicht auswertbar als
  Freigabe; Freigabe bleibt ≤100 K Faktendichte.
- decode 33,5/30,1 T/s, Prefill 93–97 T/s bei voller Länge, 8192-Output-Budget
  eingehalten, n_ctx 262144 Slot-verifiziert, kein Downgrade, keine
  Compaction im Nachweis.
- **Ursache (bytebelegt aus GGUF-Metadaten, beide Modelle identisch):**
  hybride Attention — 30 Layer, 25 Full-Attention (Muster: Layer 5/11/17/23/29
  SWA), sliding_window 1024, KV 512 B full / 256 B SWA. Die späte Abrufgrenze
  ist Modellgeometrie, kein Konfigurationsfehler; q8_0 ist die einzig
  tragbare KV-Stufe (f32 KV bei 256 K → cudaMalloc-OOM, gemessen).
  → Kein Fenster-Downgrade: 262144 bleibt konfiguriert; Produktionseinsatz
  für Faktendichte bis ~100 K freigegeben, Rest als experimentell gekennzeichnet.
  Freigaberegel erfüllt: BLOCKED statt Verschleierung.

## Ressourcen (Messung Phase 2)

- MoE-Modelle (beide 26B-A4B, cpu-moe): VRAM ~6,2 GB geladen (inkl. Desktop
  ~0,4–1,9 GB Reserve), RAM-Last ~23–26 Gi, kein Swap-Thrashing
- Swap 8 GiB bleibt gefüllt, aber stabil; OOM-Fälle traten nur bei der
  verworfenen 31B-Variante auf

## Betrieb

- Pi: defaultModel research-code, models-store = Duo + Aliasse, Relay
  Whitelist research-code/story; Pi-Akzeptanztest PASS (Sandkasten,
  Credential-Isolation, Live-Inferenz)
- Studio/Pi-Relay/WebUI-Aliasse (research, deep-research, human-*,
  creative-writing, coding-*) zeigen auf die zwei Gewichte; keine
  Kontextverkleinerung, keine toten Pfad-Referenzen
- Cleanup-Manifest: docs/MODEL-CLEANUP-MANIFEST.md (Allowlist, erst nach
  Dual-PASS löschen)
- Restore: ~/restore/2026-11-24-gemma4-256k-migration/ +
  setup.sh backup/restore (localllma-20261124-183939)

## Offene Risiken

- HauhauCS-Lizenzkennzeichnung (Repo-Tag vs. Apache-Basis) → lokal OK,
  kommerzielle Nutzung siehe docs/MODEL-LICENSES.md
- Gemory Q4 Sampler-Sensitivität: Kreativwerte bewusst je Rolle, nicht
  einheitlich
- 256K-KV q8_0 = große RAM-Bewegung; Desktop-Last bei Volllast beobachten
