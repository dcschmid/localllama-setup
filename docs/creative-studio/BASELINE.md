# Local Creative Studio — Bestandsanalyse & Architekturentscheidung (Phase 0)

Stand: 2026-11-23. Quellen: Live-Probe (systemctl, ss, curl), Quellcode-Audit
(localllama-setup, local-image-ai-service, skillset), scouts mit file:line-Belegen.

## 1. Bereits vorhanden und wiederverwendbar

| Komponente | Fakt | Beleg |
|---|---|---|
| llama.cpp-Router | b12628 CUDA, `127.0.0.1:8080` + Socket `$XDG_RUNTIME_DIR/llama-cpp/server.sock`, `--models-max 1`, SSE `/v1/chat/completions`, Loading-on-demand, Idle-Unload 900 s | `units/llama-cpp.service:8`, `setup.sh:88` |
| Modellprofile | `research`, `deep-research` (26B), `creative-writing`/`human-writing`/`human-rewrite`/`human-audit` (12B StyleTune, Jinja-Template), `coding-cyber-tiel-35b` (reserviert); alle 262K ctx / 8K out | `config/models.ini.in`, `~/.config/llama.cpp/models.ini` |
| Native WebUI | läuft auf :8080 mit, `ui.json` zentral — darf nicht angefasst werden | `config/ui.json` |
| Human-Writing-Pipeline | `config/writing/render.py` kompiliert skillset/human-writing → Jinja-Template (`ExecStartPre`); Routing über Tags/Erste-Zeile (`routing.jinja`); Linter `skillset/.../scripts/lint_text.py` (stdout JSON) vorhanden | `render.py`, `routing.jinja` |
| Deep Research | websearch-mcp :8642 (`/mcp`, Healthz `/healthz`): `deep_research`+`deep_research_status` als Hintergrund-Jobs, Budgets via `libexec/llama-research`, Sandbox netns/nft/pasta | `libexec/llama-research:26-31` |
| MCP-Gateway | :8643 mcp-proxy 0.15.0 (context7, github, skills-fs read-only skillsFS) | `config/mcp.json.in` |
| Image-Service | :7861, `/studio/api/jobs` (Queue 16), `/studio/api/compose`, `/studio/api/gallery`, `/studio/api/catalog`, `/v1/models`, `/health`,`/ready`; **Polling-Vertrag, kein SSE, kein CORS, keine Export-Route**; Jobs SQLite-persistiert, Restart ⇒ nicht-terminale Jobs `failed` (client: erst `jobs` listen!) | Service-Audit `src/service.py`, `studio_service.py` |
| CLI/Lifecycle | `./setup.sh install|update|repair|doctor|status|test|backup|restore|uninstall`, flock, SHA256-Gates, dry-run, `uninstall.sh` | setup.sh |
| Design-/Skill-Reuse | human-writing (Audit+Rewrite), accessibility (WCAG 2.2 AA), design-authenticity, design-system-ui, ultimate-testing-qa, godot 4.7.2, defold 1.14.1 | skillset |

Belegte Live-Hardware: research 6573 MiB / writing 6553 MiB VRAM bei 256K+Q4_0 —
Router und Image-Service teilen sich 8 GB VRAM zeitversetzt (models-max=1, GPU-Lock).

## 2. Vorhanden, aber anzupassen

- Setup-CLI: Subcommand-Schema bleibt; Creative Studio hängt sich als `creative-studio`-Zweig an (`setup.sh creative-studio …` delegiert an `libexec/llama-creative-studio` analog `llama-webui`).
- research.nft/pasta: gilt nur für die :8642-netns; Studio-Backend braucht keine neue Firewall-Route (loopback).
- `render.py`-Tag-Routing: Studio muss Tags/Erste-Zeile-Konvention respektieren (`[de|en]`, `[generate|rewrite|audit]`, Genre) — Adapter, keine Kopie.

## 3. Neu zu implementieren (die echte Lücke)

1. Studio-Backend: HTTP auf `127.0.0.1:8700`, **stdlib-only Python 3** (Konvention: `libexec/`, Image-Service; kein FastAPI — kein neues Dependency-Footprint, Lockfile-Drift unmöglich), SQLite + Migrationen, SSE-Passthrough-Proxy zum Router.
2. Studio-Frontend: Astro+TS, statischer Build, ausgeliefert **vomselben Backend auf :8700** (ein Port wie :8080; Image-Service-CORS problemfrei, da Server-zu-Server).
3. Resource Coordinator (In-Process): eine GPU-Warteschlange, Modellwechsel-Log, keine Preemption laufender Coding-Sessions.
4. Studio-Funktionen: Projekte/Dokumente/Sessions, Story-Bibel+Memory (FTS, **keine Embeddings**), Image-Jobs, Research-Dossier, Decision Log, Astro-Export, Voice Profiles.
5. systemd-Unit `creative-studio.service`, KDE-Starter, Doctor/Backup/Restore-Äste.

## 4. Technische Risiken & Abhängigkeiten

- **VRAM**: Router lädt pro Wechsel neu (~8 s–2 min bei 262K-KV) → Coordinator bündelt Phasen; Image-Jobs nie parallel zu Schreib-Generierung (GPU-Lock 7861 intern, Server-seitig 429 `generation_busy`).
- **:8642-Budgets** (MAX_QUERIES 2, 240 s) sind niedrig → Studio-Forschungsloop ruft `deep_research` mehrfach mit Teilfragen auf, statt ein Mega-Job.
- **Image-Service-Restart** ⇒ offene Jobs `failed`: Client muss nach Reconnect erst `GET /studio/api/jobs` (Dup-Schutz).
- **Seed-Stabilität** nur innerhalb Runtime-Version ⇒ `recipe_version`/`fingerprint` mitführen.
- Skill-Checkout livesymlink: Audit zur Laufzeit, Drift-Fehler als Status, nicht Crash.
- Kein Push, keine produktiven Coding-Profile (`coding-*`) anfassen; nur lesen.
- Ports fest: 8700 neu, sonst unverändert; alles 127.0.0.1.

## Architekturentscheidung

```
Browser ──► 127.0.0.1:8700 creative-studio (stdlib-HTTP: statischer Astro-Build + /api)
              │ /api/chat ──► Router :8080 /v1/chat/completions (SSE-Passthrough)
              │ /api/image ─► Image :7861 /studio/api (Polling)
              │ /api/research ► websearch-mcp :8642 (deep_research) + Router-Synthese
              └─ SQLite ~/.local/share/creative-studio/studio.sqlite3 (Migrationen)
                 Dateien ~/.local/share/creative-studio/  Config ~/.config/creative-studio/
```

Kein zweiter Inference-Server, kein zweiter Crawler, keine Cloud, keine Embeddings,
keine neuen Dienste außer `creative-studio.service` (optional, nur bei Bedarf).
Human Writing = vorhandene Aliase + Skill-Audit + lint_text.py. Phase 1 beginnt hier.
