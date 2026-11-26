# Modell-Inventar & Bereinigungs-Manifest (Stand 2026-11-24, Final-Setup)

Finale Konfiguration: genau zwei Modelle. Gelöscht wird erst, wenn beide
den 256K-Nachweis bestanden haben (`docs/results/*.json`, verdict PASS).
Bis dahin ist jede Datei unten Rollback-Bestand. SHA256 aller Alt-Dateien:
`~/restore/2026-11-24-gemma4-256k-migration/models-sha256.txt`.

## 256K-Status (2026-11-25, Ladder-Nachweis)

- story (Gemory): BLOCKED für späte Faktenabrufe nahe 256K
  (docs/results/story-256k.json, story-256k-ladder.json). Kein Löschen des
  Altbestands; alle Rollback-Gewichte bleiben. Produktiv nutzbar bis ~100K
  Faktendichte.
- research-code: BLOCKED (Voll 229K leer/spät falsch; Ladder 131K 3/4,
  research-code-256k-ladder.json). Freigabe ≤100K Faktendichte.
- Ursache bytebelegt: hybride Attention (25/30 Full-Layer, SWA 1024) —
  Modellgeometrie, kein Konfigurationsfehler; Dual-PASS kann auf dieser
  Hardware-Kombination nicht gelingen, Altbestand bleibt Rollback.

## Produktiv bleiben (NEVER löschen)

| Datei | Rolle |
|---|---|
| ~/models/gguf/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf | research-code (Coding/Research/Pi) |
| ~/models/gguf/Gemory-26B-A4B-Q4_K_M.gguf | story (Story/Artikel/Human Writing) |

## Altbestand — GELÖSCHT 2026-11-25 (Nutzerfreigabe über Dual-PASS-Hürde)

Delete-Vollzug 2026-11-25: alle neun Dateien entfernt (lsof leer, Router-Presets
prüfen nur noch die zwei Produktivgewichte, story-Inferenz nach Löschung OK).
Wiederherstellung über `packages/models.tsv`-Revisionspins +
`./setup.sh install --download-models` (Kandidaten mit `--coding-candidates`).
SHA-256 der gelöschten Dateien: `~/restore/2026-11-24-gemma4-256k-migration/models-sha256.txt`.

Exakte Allowlist (keine Wildcards):

1. ~/models/gguf/gemma-4-26B_q4_0-it.gguf            (14G, Vorgänger research/deep-research)
1b. ~/models/gguf/gemma-4-Ortenzya-The-Creative-Wordsmith-31B-it-uncensored-heretic.i1-Q4_K_M.gguf (17G, aussortiert: 31B-dense ist auf der 8GB-Karte zu langsam)
2. ~/models/gguf/Gemma-4-12B-StyleTune.Q4_K_M.gguf   (7,5G, Vorgänger creative-writing/human-*)
3. ~/models/gguf/Cyber-Tiel-Coder-35B-A3B.APEX-I-MiniPlus-V2.1.gguf (14G, Pi-Coding-Vorgänger)
4. ~/models/gguf/Ornith-1.5-9B-Q4_K_M.gguf           (5,4G, Coding-Kandidat)
5. ~/models/gguf/Mellum2.1-12B-A2.5B-Thinking-Q4_K_M.gguf (7,6G, Coding-Kandidat)
6. ~/models/gguf/Kwaipilot_KAT-Coder-V2.5-Dev-Q4_K_M.gguf (20G, Coding-Kandidat)
7. ~/models/gguf/LFM2.5-24B-A2B-Q4_K_M.gguf          (14G, Coding-Kandidat)
8. ~/models/gguf/Phai-A1-35B-1M-MTP.MXFP4_MOE.gguf   (19G, Coding-Kandidat)

Abhängigkeiten: `packages/models.tsv` + `packages/models-coding-candidates.tsv`
und die Router-Presets in `config/models.ini.in` verweisen noch auf 1–8.
Beim Löschen immer beide Seiten + Router-Neuladen zusammen entfernen,
sonst zeigt der Router auf leere Pfade. Coding-Kandidaten (4–8) sind nur mit
`--coding-candidates` installiert; fehlen sie im Restore-Fall, holt
`./setup.sh install --coding-candidates --download-models` sie neu.

## Caches

- ~/.cache/huggingface (894M): nur MiniLM (Studio-Suche) + Artefakte —
  von den Trio-Gewichten unabhängig (kein HF-Cache unter ~/models/gguf),
  Löschen optional, Neu-Laden billig.
- ~/models/gguf-new existiert nicht mehr (Downloads inline verifiziert,
  dann verschoben; kein Duplikat).

## Nicht löschen (Konfiguration/Daten)

systemd-User-Units, ~/.config/llama.cpp/*, Open-WebUI-DB + Chats, Pi-Sessions,
Skills, MCPs, Repo-History, ~/restore/2026-11-24-gemma4-256k-migration/.
