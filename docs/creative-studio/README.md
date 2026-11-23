# Local Creative Studio

Lokales Schreiben, Deep Research, Bildgenerierung und Game-Ideen über die
bestehende llama.cpp-Installation, den bestehenden Image-Service und das
bestehende Skillset. Kein Cloud-Zwang, keine zweiten Engines.

- UI + API: `http://127.0.0.1:8700` (nur Loopback)
- Daten: `~/.local/share/creative-studio` (SQLite, Galerie, Bilder)
- Konfiguration: `~/.config/creative-studio`
- Backups: `~/.local/state/creative-studio/backups` (sqlite3-Tar.gz)

## Lifecycle (optional, wiederholbar)

```bash
./setup.sh creative-studio install     # Unit + Launcher + Web-Dist, nie ohne Nutzerdaten
./setup.sh creative-studio update      # gleiche, idempotente Funktion
./setup.sh creative-studio status      # /api/status
./setup.sh creative-studio doctor      # Upstream-Probes (Router, Bilder, Recherche)
./setup.sh creative-studio test        # API-Contract-Suite (kein GPU nötig)
./setup.sh creative-studio backup      # Zeitstempel-Backup in state/backups
./setup.sh creative-studio restore [name]
./setup.sh creative-studio uninstall [--purge-data]   # Daten bleiben ohne Flag
```

`install` kopiert Unit → `~/.config/systemd/user`, Backend →
`~/.local/libexec/llama-creative-studio`, Launcher → `~/.local/bin/creative-studio`
(KDE-Starter `~/.local/share/applications/creative-studio.desktop` nach
`install` via Repair), Web-Dist → `~/.local/share/creative-studio/web`.
Autostart bleibt Hand-des-Nutzers:
`systemctl --user enable --now creative-studio.service`.
Die Standard-Installation ohne Creative Studio funktioniert unverändert weiter.

## Resource Coordinator

Eine GPU-Schlange, keilfrei:

- Bildjobs bleiben `waiting_gpu`, bis `nvidia-smi` ≥ ~1 GiB frei meldet;
  erst dann Einreichung beim Image-Service (:7861). CPU-Offload bleibt respektiert.
- LLM-Aufrufe serialisieren über den llama.cpp-Router (:8080); eine Coding-Session
  (Pi/Cyber-Tiel) wird nie gestoppt oder verdrängt.
- Research- und Schreibjobs liegen persistent in SQLite und überleben
  Backend-Neustart (checkpoint/resume, Pause/Resume, Budget).

## Modelle (bestehende Aliase, keine neuen Modelle)

| Alias | Modell | Verwendung |
|---|---|---|
| research / deep-research | Gemma 4 26B A4B QAT | Recherche, Fakten, Chat |
| creative-writing | Gemma 4 12B StyleTune | Geschichten, Artikel, Devlogs |
| human-writing / -rewrite / -audit | Schreibprofile render.py | Skill-Audit/Diff |
| coding (reserviert) | Cyber-Tiel Coder 35B | bleibt Pi-Coding, Studio nur lesend |

## Human Writing

Der Skill bleibt `~/dev/github/skillset/skills/human-writing`; das Studio nutzt
nur die existierenden render.py-Aliase und `lint_text.py`. Audits beurteilen
Textqualität (Rhythmus, Floskeln, Dialog), nie Urheberschaft. Voice Profiles
und Skill-/Profil-Version werden pro Dokument gespeichert; Übernahmen erfolgen
als Diff mit Versionsverlauf.

## Deep Research (Zero-Cost)

Autonomer Loop über den vorhandenen websearch-mcp (:8642, sandboxed, NFT):
Plan → Suchvarianten → Extraktion → Faktenprüfung → Gap-Analyse → Follow-up,
mit Dedup, Budget, Checkpoints und Dossier als `documents`-Eintrag. Keine
Bezahl-APIs; SearXNG/GPT-Researcher nur auf ausdrücklichen Wunsch.

## Export

`/api/export` liefert Astro-taugliche `md`/`mdx` Payloads (Frontmatter,
relative Bildpfade, Alt-Texte) als Download. Es wird nichts automatisch in
Repos geschrieben; Content-Collection-Schema bleibt frei.

## Tests

```bash
python3 tests/creative-studio.py        # API-Contract, braucht laufenden Dienst
tests/unit.sh                           # Installer-Regression (unverändert grün)
```
