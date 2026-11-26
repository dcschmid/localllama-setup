# Local Creative Studio – Abschlussbericht (2026-11-25)

Auftrag: Drei-Modell-Setup → Local Creative Studio (Deep Research + DE/EN
Creative Writing, kein produktives Coding, zwei Modelle, fest 256K).
Regel: gemessen statt behauptet; jede Zahl hat eine JSON-Quelle.

## 1. Bestandsaufnahme vor der Migration

Ausgang war bereits der Zwei-Modell-Rollout vom 2026-11-24 (`652c515`,
docs/GEMMA4-256K-MIGRATION-REPORT.md). Offene Punkte waren: 256K-Akzeptanz
(BLOCKED), Open-WebUI-Rollen, Human-Writing-Template-Stand, Doku-Stände,
Altmodell-Bereinigung. Laufende Prozesse (Router, Studio :8700, Open WebUI
:8090, Image-Service, websearch :8642) wurden nicht unterbrochen; keine
Download-Prozesse aktiv.

## 2. Installierte Modelle (verifiziert, kein Download nötig)

| Modell | Datei | SHA-256 (= HF LFS OID) | Lizenz |
|---|---|---|---|
| research-code | Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf (16.796.015.520 B) | 3c13133469e43131…d73c | `gemma`-Tag auf Apache-2.0-Basis; lokal OK, kommerzielle Doku offen (MODEL-LICENSES.md §1) |
| story | Gemory-26B-A4B-Q4_K_M.gguf (16.796.016.096 B) | 4991d114e7219e43…4442 | apache-2.0, kommerziell OK (Attribution bei Weitergabe) |

Kompatibilität: arch `gemma4`, läuft nativ auf b12628 CUDA (Produktivbetrieb
ist der Beweis). MTP-Drafter vorhanden, bleibt deaktiviert (Nutzen unbelegt).

## 3. 256K-Funktionalität (Abnahmekriterium)

Slot: n_ctx 262144 bei beiden verifiziert (n_ctx_ok true), fit off, keine
Compaction im Nachweis, 8192-Output-Budget eingehalten. Beide Modelle
verarbeiten 229–245K Prompt-Tokens ohne Truncation. **Faktabruf nahe der
Grenze bleibt BLOCKED** – Ursache bytebelegt aus GGUF-Metadaten: hybride
Attention (30 Layer, 25 Full / 5 SWA bei sliding_window 1024, KV 512/256 B).
Das ist Modellgeometrie, keine Konfiguration; ein Kontext-Downgrade wurde
nicht vorgenommen. Freigabe: Faktendichte bis ~100K, darüber experimentell.
Belege: docs/results/story-256k.json, research-code-256k.json,
*-256k-ladder.json (Ladder-Modus neu in tests/gemma4-256k-check.py).

## 4. Optimierte llama.cpp-Parameter (gemessen)

Beide Profile: ctx 262144, n-predict 8192, parallel 1, fit off, flash-attn on,
KV q8_0 (einzige tragbare Stufe: f32-KV → cudaMalloc-OOM bei 256K gemessen;
q4_0 verworfen, da die abrufbegrenzte Geometrie nicht zusätzlich belastet
werden soll), batch 2048/ubatch 64, cpu-moe, threads 12/12, sleep-idle 900.
research-code temp 0.6; story 0.7/0.95/64 (Kartenband 0.2–0.7).

## 5. Messwerte (docs/results/*-256k*.json, docs/PERFORMANCE.md)

| Größe | research-code | story |
|---|---|---|
| Prefill (volle Länge) | 95,4 t/s (229.547 tok) | 93,0–96,9 t/s (244.823/131.048 tok) |
| Decode | 30,1 t/s (3.722 out) | 33,5 t/s (4.411 out) |
| VRAM geladen | ~6,2 GB (Desktop-Reserve 0,4–1,9 GB) | wie links; kein Swap-Thrashing |
| RAM-Last | 23–26 Gi | wie links |
| 256K-Prefill-Zeit | ~40 min (2.407 s / 229K) | ~44 min (2.634 s / 245K) |

Kapitel-/Research-Zeiten: Kurzantwort 2,9–115 s je nach Länge
(creative-studio-qa-smoke.json); ein 1.200-Wort-Kapitel liegt damit im
Minutenbereich, lange Research-Aufträge dominieren Prefill.

## 6. Schreibqualität DE/EN (docs/results/creative-studio-qa-smoke.json)

PASS 6/6 über die Produktionsaliase: DE-Szene (creative-writing, natürlich,
ohne Floskeln), EN-Szene, DE-Artikel, EN-Devlog (human-writing, gerendertes
Human-Writing-Template), Research-Fakten + Quellenaudit (research-code).
Gemory ist DE ≠ EN automatisch: der EN-Devlog traf die Vorgabe in 2,9 s,
DE-Szenen brauchen die Template-Führung – gemerkt, nicht verallgemeinert.
Ein drittes Modell wurde nicht installiert.

## 7. Integrationen

- Human-Writing: skillset 1.2.0 → render.py → gemma4-human-writing.jinja
  (53.396 B, 2026-11-25 neu gerendert; war 18.11.-Stand). Aliase
  creative-writing/human-* nutzen es; Studio-Editor-Audit unverändert.
- Research: websearch-mcp :8642 + gateway :8643 aktiv, Deep-Research-Loop im
  Studio produktiv; keine Zusatzinfrastruktur.
- Open WebUI: zwei Rollen registriert (Research & Analysis 256K →
  research-code; Creative Writing DE/EN 256K → story), riff-racers-Basis
  repariert; Skript libexec/owui-migrate-creative-studio.py (idempotent).
- Image-Service: GPU-Schlange (waiting_gpu) unverändert, keine neue
  Bildinfrastruktur.

## 8. Altmodelle / Cleanup

Gelöscht 2026-11-25 per Nutzerfreigabe über die offene Dual-PASS-Hürde:
alle neun Altgewichte (~101 GB frei; Allowlist + SHA-Liste in
MODEL-CLEANUP-MANIFEST.md bzw. ~/restore/2026-11-24-gemma4-256k-migration/
models-sha256.txt). Router-Presets zeigen nur noch auf die zwei Produktiv-
gewichte, story-Inferenz nach Löschung geprüft. Rückweg: Revisionspins in
packages/models.tsv + `./setup.sh install --download-models`
(Kandidaten zusätzlich `--coding-candidates`).

## 9. Offene Einschränkungen

1. 256K-Faktabruf >~100K BLOCKED (Geometrie; Freigabe ≤100K).
2. HauhauCS-Lizenzkette für kommerzielle Nutzung zu klären (MODEL-LICENSES.md).
3. Ladder-Zeilen von story behielten keinen Antworttext (0/4 nicht als
   Format-/Positionsfehler trennbar) – bei Bedarf --out je Stufe ergänzen.
4. WCAG-Vollprüfung Studio steht aus (AT-SPI in der Sitzung).

## 10. Restore

Konfiguration: `./setup.sh backup` → `~/.local/state/localllma-setup/backups/`;
Einspielen `./setup.sh restore [datei]`. Whole-state 2026-11-24:
`~/restore/2026-11-24-gemma4-256k-migration/` (models.ini, SHA-Listen, Dienste).
Open WebUI: `~/restore/owui-20261125-064614/webui.db` (vor Migration) bzw.
`…064656/webui.db`; Rollen entfernen = insert-Zeilen creative-studio-{research,story}
löschen + riff-racers base zurück auf hemmingway. Studio:
`./setup.sh creative-studio restore [name]`. Modellgewichte lagen nie in git –
Wiederherstellung über packages/models.tsv (Revision + SHA-Gate).

## 11. Start des Local Creative Studio

```bash
systemctl --user status llama-cpp llama-cpp-research llama-cpp-mcp   # Router :8080
creative-studio   # bzw. ./setup.sh creative-studio status  → http://127.0.0.1:8700
# Open WebUI :8090 → "Research & Analysis 256K" / "Creative Writing DE/EN 256K"
# Freigaberegeln: Faktendichte ≤100K; >100K nur als experimentell gekennzeichnet.
```
