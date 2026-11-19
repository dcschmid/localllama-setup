# Native llama.cpp-Installation

Stand 19. November 2026. [Quickstart](QUICKSTART.md) · [Modellvergleich und Messungen](MODEL_BENCHMARKS.md)

## System und Installation

- Framework Laptop 16, Fedora 44 KDE/Wayland, Kernel `7.3.4-200.fc44.x86_64` seit dem Neustart am 18. November. AMD Ryzen AI 9 HX 370 mit 12 Kernen und 24 Threads, AVX2, AVX-512, VNNI und FMA. Radeon 890M mit Vulkan/RADV und AMD XDNA wurden erkannt.
- Linux meldete 46,8 GiB RAM, anfangs rund 23 GiB verfügbar und rund 8 GiB belegten ZRAM-Swap. Die Radeon meldete 16 GiB VRAM-Apertur. Die 16 GiB Grafikreservierung erklären plausibel den größten Teil der Abweichung zur 64-GB-Ausstattung.
- RTX 5070 Laptop, NVIDIA-Treiber `615.78.08`, Compute Capability `12.0`. `nvidia-smi` meldete 8.151 MiB, die CUDA-Laufzeit 7.799 MiB. Der Treiber meldete CUDA 13.4. Der installierte Upstream-Build nutzt CUDA 12.8.
- WD PC SN8000S NVMe mit rund 1,5 TiB frei unter `/home`. Btrfs auf LUKS. Die NVMe ist im Kernel als nicht rotierend ausgewiesen. Das Fedora-Profil Energiesparen begrenzte die CPU auf 2,0 GHz. Zeitlich begrenzte Leistungsmessungen verwenden eine D-Bus-Lease und geben sie anschließend frei.
- Offizielles `llama.cpp` [b12503](https://github.com/ggml-org/llama.cpp/releases/tag/b12503), Commit `4577932fab595eaa8b27ad71734d5de1f3c07d8c`. Upstream-Binärpaket Linux x86_64 CUDA 12.8, GNU 13.3.0, CUDA mit `sm_120a`-Kernels und Zen-4-CPU-Backend sowie eingebettete offizielle Llama Chat WebUI. Die SHA-256 des Pakets wurde gegen das GitHub-Release geprüft. Vorhandene NVIDIA-Laufzeitbibliotheken wurden in die neue versionierte Installation kopiert.
- Programmdateien unter `~/.local/opt/llama.cpp/b12503`. `current` zeigt auf den aktiven Build. `llama-server`, `llama-cli` und `llama-bench` sind in `~/.local/bin` erreichbar.
- Gewichte liegen in `~/models/gguf`. `models.ini` verwendet absolute Pfade und native Router-Aliase. Mehrere Profile teilen dasselbe GGUF. Ein Modell und ein Slot laufen gleichzeitig. Der Router lädt bei Bedarf und entlädt beim Wechsel. Für Inaktivität ist der native Sleep-Timeout auf 15 Minuten gesetzt.
- Der Router bindet an `127.0.0.1:8080` und einen privaten Unix-Socket unter `$XDG_RUNTIME_DIR/llama-cpp/server.sock`. Modell-Downloads sind in der Router-Laufzeit gesperrt. Bestehende Audio-, Bild-, Open-WebUI- und TinySearch-Dienste behalten ihre eigenen Ports und Konfigurationen.

## Bedienung und Profile

`~/.config/llama.cpp/models.ini` enthält die Profile und gemessenen Startwerte. Für eine Liste ohne Modellladung dient `curl -fsS http://127.0.0.1:8080/models`. Zur Diagnose zeigt `/props?model=NAME` die effektive Kontextgröße. Dieser Aufruf kann ein Modell laden.

Die sieben aktiven Profile verwenden drei GGUF-Dateien. Die SHA-256-Prüfsummen stehen im Wiederherstellungspaket unter `packages/models.tsv`.

| Profil | Modell | Kontext |
|---|---|---:|
| `research` | Gemma 4 26B A4B IT QAT Q4_0 | 32K |
| `deep-research` | Gemma 4 26B A4B IT QAT Q4_0, 128 Denktokens je Anfrage | 32K |
| `coding-long-256k` | Cyber-Tiel-Coder 35B A3B APEX-I MiniPlus | 256K |
| `creative-writing`, `human-writing`, `human-rewrite`, `human-audit` | Gemma 4 12B StyleTune Q4_K_M | 16K |

Cyber-Tiel wird über `coding-long-256k` mit 262.144 Tokens, 2.048/1.024 Batch/Microbatch und Q4_0 für K und V geladen. Die Servervorgabe für die Ausgabe beträgt 8.192 Tokens. Die Profile nutzen mmap, CUDA mit 1.024 MiB Zielreserve und Flash Attention. Der Router lädt maximal einen Modellprozess. MTP ist aus. [Performance-Messung und Rückbau](PERFORMANCE_OPTIMIZATION.md)

- `llama-webui` startet die Benutzerdienste bei Bedarf und öffnet den Browser.
- `llama-webui --check` prüft den Inference-Dienst ohne Browseröffnung.
- `systemctl --user stop llama-cpp.service` beendet den Router und den zugehörigen Research-Dienst.
- `journalctl --user -u llama-cpp.service -n 80` zeigt Modellstart und CUDA-Speicher. Für Websuche `journalctl --user -u llama-cpp-research.service -n 80`.
- Nach Änderungen der Presets lädt `curl -fsS 'http://127.0.0.1:8080/models?reload=1'` die Liste erneut. Eine laufende Generation vorher abschließen. Änderungen an systemd-Units benötigen `daemon-reload` und einen Neustart des Benutzerdienstes.

## WebUI, Recherche und MCP

Der KDE-Starter öffnet die native WebUI auf `http://127.0.0.1:8080`. Modell-API und UI teilen den Port. Die lokalen Coding-Wrapper greifen weiterhin über den privaten Socket `$XDG_RUNTIME_DIR/llama-cpp/server.sock` zu. Firefox speichert Chats, Einstellungen und Tool-Freigaben pro Origin. `localhost`, `127.0.0.1` und verschiedene Ports bezeichnen unterschiedliche Origins.

`llama-server` b12503 übernimmt die zentralen Browser-Vorgaben aus `--webui-config-file ~/.config/llama.cpp/ui.json`. Der gleichwertige Kurzname ist `--ui-config-file`. `mcpServers` enthält eine JSON-kodierte Liste direkter HTTP-Verbindungen. Der Server veröffentlicht sie in `/props.ui_settings`. Firefox übernimmt diese Vorgaben beim ersten Besuch. Vorhandene Profile behalten ihre Einstellungen. Im regulären Profil wurden die vier MCP-Einträge einmalig über die Oberfläche ergänzt.

| Anzeige in der WebUI | MCP-Endpunkt | Dienst |
|---|---|---|
| Websearch & Deep Research | `http://127.0.0.1:8642/mcp` | `llama-cpp-research.service`, bestehender Danmoreng/websearch-mcp |
| Context7 | `http://127.0.0.1:8643/servers/context7/mcp` | Bestehendes Context7 über `llama-cpp-mcp.service` |
| GitHub | `http://127.0.0.1:8643/servers/github/mcp` | Bestehendes GitHub MCP über `llama-cpp-mcp.service` |
| Skill-Sammlung (read-only) | `http://127.0.0.1:8643/servers/skills/mcp` | Bestehendes Filesystem MCP über `llama-cpp-mcp.service` |

Alle Verbindungen nutzen Streamable HTTP direkt aus der WebUI. Der Benutzer-Dienst `llama-cpp-mcp.service` verwendet [mcp-proxy 0.15.0](https://github.com/sparfenyuk/mcp-proxy/releases/tag/v0.15.0) als Transportadapter für die drei vorhandenen stdio-Programme aus `mcp.json`. Websearch bindet bereits selbst an Loopback und wird direkt verbunden. Der Router verwendet die Browser-Einträge statt der bisher parallel eingeblendeten Server-Tools. Das Modell sieht die ursprünglichen Tool-Namen wie `search_web`, `read_url`, `deep_research` und `read_text_file`.

Der Websearch-Dienst behält seinen eigenen Netzwerk-Namespace, die Filterregeln und den lokalen Inference-Socket. Deep Research startet einen Hintergrundjob und verwendet über die bestehende lokale API standardmäßig das Profil `deep-research`. Das Tool-Argument `model` kann das Profil überschreiben. Der Timeout für die lokale Inference beträgt 90 Sekunden. Das Recherchebudget beträgt 240 Sekunden. Der Status kommt über `deep_research_status` mit der Job-ID. Der Gateway bindet an `127.0.0.1`, prüft Host und Browser-Origin und akzeptiert die WebUI unter `http://127.0.0.1:8080`. GitHub verkapselt die vorhandene `gh`-Anmeldung weiterhin im schreibgeschützten Serverprozess. Die Skills-Freigabe bleibt auf `~/dev/github/skillset/skills` beschränkt. Die WebUI fragt pro Tool-Aufruf nach Freigabe, soweit für dieses Tool noch keine Entscheidung gespeichert ist.

### Diagnose

```bash
systemctl --user status llama-cpp.service llama-cpp-research.service llama-cpp-mcp.service
curl -fsS http://127.0.0.1:8080/props | jq -r '.ui_settings.mcpServers | fromjson[] | [.displayName,.url] | @tsv'
curl -fsS http://127.0.0.1:8642/healthz
curl -fsS http://127.0.0.1:8643/status
```

Die ursprünglichen Firefox-Tests verwendeten neue temporäre Profile und riefen die serverseitig registrierten Werkzeuge über **Tools → Server** auf. Die Anzeige „Add your first MCP server“ gehört dagegen zur Browser-Liste und war bei der früheren Vorgabe `mcpServers = []` zu erwarten. Issue #26497 dokumentiert ein ähnliches Symptom. Der Bericht #28077 wurde vom Autor zurückgezogen. Der installierte Build übernimmt die zentralen Vorgaben beim ersten Besuch auch im Router-Modus. [Upstream-Serverdoku b12503](https://github.com/ggml-org/llama.cpp/blob/b12503/tools/server/README.md) · [Issue #26497](https://github.com/ggml-org/llama.cpp/issues/26497) · [Issue #28077](https://github.com/ggml-org/llama.cpp/issues/28077)

## Human Writing in der WebUI

Ein früherer Firefox-Chat mit `human-writing` bekam ohne das Tag `[web]` keine Suchwerkzeuge übergeben. Das Template erkennt jetzt auch ausgewählte eindeutige Aufträge am Beginn der ersten Zeile, etwa „Recherchiere im Web“, „Verwende ausdrücklich unseren Websearch MCP“ und „Search the web“. Es reicht bei diesen Aufträgen nur `search_web` und `read_url` an StyleTune weiter. Für Deep Research steht `deep-research` zur Auswahl. Für die übrigen Research-Aufgaben verwende `research`.

Der Router-Build b12503 unterstützt das Gemma-Systemformat und `chat-template-file` sowie `chat-template-kwargs` je Modellsammlungseintrag. Die installierte WebUI bietet kein natives Laden und Ausführen eines Agent-Skills. Die Writing-Profile verwenden deshalb das native Gemma-Template mit einer zusätzlichen Systemnachricht. Das eingebettete Gemma-Format für Benutzer- und Assistentenrollen, Tools und Toolantworten gilt weiterhin. Die WebUI kann eine eigene Systemnachricht ergänzen. Die vier Writing-Profile starten mit ausgeschaltetem Thinking. [Upstream-Dokumentation für b12503](https://github.com/ggml-org/llama.cpp/blob/b12503/tools/server/README.md)

| Router-Profil | Standardmodus | Geeignet für |
|---|---|---|
| `creative-writing` | Generate, Fiction | Englische Kurzgeschichten, Riff-Racers-Szenen, Figuren und Dialoge |
| `human-writing` | Generate, Editorial | Deutsch und Englisch, Musikrezensionen, Blog, Devlog und persönliche Texte |
| `human-rewrite` | Rewrite | Behutsame Bearbeitung bereits vorhandener Texte |
| `human-audit` | Audit | Konkrete Befunde zu Mustern, Dichte und Substanz |

Alle vier Profile verwenden `Gemma-4-12B-StyleTune.Q4_K_M.gguf`, 16.384 Kontexttokens und Q8_0-K/V. Die erste Auftragszeile kann mit `[generate]`, `[rewrite]`, `[audit]`, `[website-audit]`, `[website-rewrite]` oder `[voice]` den Modus setzen. `[de]` und `[en]` wählen die Sprachreferenz. Weitere Genre-Tags sind `[fiction]`, `[editorial]`, `[technical]`, `[business]`, `[marketing]` und `[ux]`. Naheliegende deutsche und englische Auftragswörter werden in der ersten Zeile erkannt. Bei mehrdeutigen oder fremdsprachigen Anweisungen sind die Tags die verlässliche Steuerung. Die gewählte Einordnung gilt auch für Folgefragen, bis ein neuer Auftrag sie ändert.

### Systemkontext und Aktualisierung

- Quelle der Regeln ist `~/dev/github/skillset/skills/human-writing` beziehungsweise der freigegebene Skill-Pfad in `mcp.json`. Der Serverstart baut den Jinja-Cache mit `~/.config/llama.cpp/writing/render.py` aus dieser Quelle. Der generierte Cache unter `~/.cache/llama.cpp/writing/gemma4-human-writing.jinja` wird bei Änderungen im Checkout ausgetauscht. Für die Übernahme in bereits geladene Modelle den Benutzerdienst neu starten.
- Jede Writing-Anfrage erhält das vollständige `SKILL.md` und die Quality Gates. Die Sprache wählt `style-de.md` oder `style-en.md`. Genrearbeit erhält den passenden Abschnitt von `genre-guides.md` oder `creative-writing.md`. Rewrite ergänzt `fidelity-rules.md` und `patterns-core.md`. Audit erhält die Muster für die Befundbewertung. Voice Calibration erhält `voice-calibration.md` und die Profilvorlage. Die Website-Modi laden ihre Audit- oder Rewrite-Regeln einschließlich der relevanten SEO- und A11y-Hinweise.
- Die Systemnachricht verlangt bei Generate und Rewrite standardmäßig den fertigen Text. Audit liefert die angeforderten Befunde und Voice Calibration das Profil zu den Beispielen. Die Skill-Regeln begrenzen revidierende Durchläufe auf zwei. Geschützte Fakten, Zitate, Zahlen, URLs und technische Spans sind in der Rewrite-Anweisung priorisiert. Modellantworten mit wichtigen Fakten vor Weitergabe redaktionell prüfen.
- Meldet der Dienststart einen Fehler beim Rendern, siehe `journalctl --user -u llama-cpp.service -n 60`. Das Skript stellt die generierte Datei erst nach erfolgreichem Lesen aller Quellen um. Für eine Neuinstallation der Writing-Profile wird die lokale Skill-Sammlung benötigt.

### Quellengebundene Schreibaufträge

`[fakten]` oder `[facts]` aktiviert die Quellenbindung pro Auftrag. Das Template ergänzt die Fidelity-Regeln und fordert den Abgleich jeder Sachbehauptung mit einem eingegebenen Faktenblatt, Quellenauszügen oder tatsächlichen Tool-Ergebnissen. Beobachtung, Planung, Ergebnis, Unsicherheit und Zuschreibung sollen erhalten bleiben. Der zusätzliche Systemkontext ist eine Modellanweisung. Ein separater Durchlauf mit `human-audit` und die Prüfung der Originalquellen bleiben die Freigabeschritte für wichtige Texte.

Recherchiere öffentliche Fakten zuerst und prüfe das Faktenblatt. Schreibe danach mit StyleTune im lokalen Writing-Profil. Der Tag `[fakten]` blendet den Rechercheprozess nicht in den Schreiblauf ein. Die Freigabe für eingeblendete Webtools erfolgt über `[web]`. Bei internen Themen liefert der Nutzer das Faktenblatt. Die [Quickstart-Anleitung](QUICKSTART.md#sachtexte-aus-quellen) enthält die Aufträge für die einzelnen Schritte.

### Linter, Website-Audit und Freigaben

Der bestehende Filesystem-MCP bietet zehn schreibgeschützte Dateiwerkzeuge. Der Schreibkontext wird direkt beim Formatieren des Prompts geladen. Bei gewöhnlichen Writing-Aufträgen blendet das Template die Tool-Beschreibungen im Modellprompt aus. Steht `[web]` am Anfang des aktuellen Auftrags, rendert es ausschließlich die in der WebUI für diesen Chat angebotene Websuche und den Seitenabruf. Die Freigaben der WebUI gelten dabei weiter. Die installierten MCP-Tools bieten keinen auf `lint_text.py` beschränkten Prozessaufruf. Die optionale Textprüfung läuft separat und verwendet die unveränderte Skill-CLI.

```bash
skill="$HOME/dev/github/skillset/skills/human-writing"
python3 "$skill/scripts/lint_text.py" /pfad/zum/text.md --lang auto
python3 "$skill/scripts/website_audit.py" https://example.com --format json --out audit.json
python3 "$skill/scripts/project_audit.py" audit /pfad/zum/projekt
```

Der erste und dritte Befehl arbeiten lokal. Der zweite ruft ausdrücklich die angegebene öffentliche Website ab. Linter- oder Auditreports können anschließend als Dateien an einen Writing-Chat angehängt werden. `[website-rewrite]` liefert Vorschläge. Das Anwenden über die vorhandene Projekt-CLI oder im CMS erfordert die vorgesehene Freigabe. Die Schreibprofile schalten keine Shell-Ausführung frei.

## Lokales Coding

- `claude-local` startet Claude Code mit llama.cpp `/v1/messages`. `codex-local` verwendet `/v1/responses`. Die CLI-Profile und Zustände liegen unter `~/.config/llama.cpp/claude` bzw. `~/.config/llama.cpp/codex`. Die Skills werden über die vorhandenen Sammlungen eingebunden. Beide Wrapper prüfen die 262.144 Tokens des einzigen Coding-Profils. Claude verwendet 8.192 Ausgabetokens und 85 % als Compaction-Ziel. Codex verwendet die explizite Grenze 222.822 und bezieht seine Ausgabevorgabe vom Server.
- Beide Wrapper starten den Router bei Bedarf, prüfen das gewählte Profil und starten den lokalen Client in einem eigenen Netzwerk-Namespace. Eine TCP-Verbindung im Namespace leitet ausschließlich über den privaten Router-Socket weiter. Die Clients erhalten eine minimale Umgebung. Claude verwendet einen lokalen Platzhalter und Codex keine OpenAI-Authentifizierung.
- Die regulären Cloud-Clients, Zugangsdaten und Cloud-Konfigurationen werden durch die Wrapper nicht beschrieben. Der lokale Codex übernimmt über eine Kopie die aktuellen Benutzereinstellungen. Änderungen an der Cloud-Konfiguration fließen deshalb erst nach gezielter Übernahme in den lokalen Modus ein. Remote-MCPs sind im isolierten Netzwerk nicht erreichbar. Die gewöhnlichen Datei- und Shell-Berechtigungen der Clients gelten weiterhin.
- Coding-Tests liefen in separaten lokalen Git-Fixtures. Tests mit Berechtigungen zum Bearbeiten und Ausführen waren auf die jeweilige Fixture begrenzt. Der beim Claude-SDK angezeigte USD-Wert ist eine Client-Schätzung. Die Requests gingen während der Tests an den lokalen Socket.

## Updates und Fehlersuche

Die pro Modell geprüften Performance-Einstellungen, Messbedingungen und der Rückweg zur Ausgangskonfiguration stehen in [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md).

Bei einem Update einen offiziellen Release-Build mit kompatibler CUDA-Laufzeit nach `~/.local/opt/llama.cpp/<build>` entpacken und dessen Release-Hash prüfen. `llama-server --version` und `--list-devices` direkt im neuen Verzeichnis ausführen, dann `current` umstellen und die Benutzerdienste neu starten. Den alten Build für einen Rückwechsel behalten. Änderungen an den Router- oder CLI-Optionen gegen deren `--help` prüfen.

Beim Laden eines großen Modells helfen `nvidia-smi`, `free -h` und das Journal beim Unterscheiden von VRAM-, Host-RAM- und Templatefehlern. Für kleine Coding-Aufgaben genügen kurze Prompts im 256K-Profil. Bei Firefox trat ein HTTP 415 für die eingebettete variable Schriftdatei auf. Chat, Modellwahl und Textanhänge funktionierten mit der Ersatzschrift. Die Dateinavigationsprobe der WebUI wird bei deaktivierten Host-Dateitools abgewiesen. Freigegebene Skills bleiben über Filesystem MCP erreichbar.

## Verwendete Skills und Testumfang

Skill Orchestrator erfasste 27 Skills im Repository. Agent Harness strukturierte die Offline- und Tooltests. QA und Code Review lieferten Prüfkriterien für Firefox, die API-Verträge und die Setup-Dateien. Für Modell- und Agententests wurden keine Skripte aus den Skills gestartet.

Die Artefakte der Messungen liegen in `~/.cache/llama.cpp/setup`. Das Verzeichnis enthält die Download-Protokolle, die offizielle Benchmark-Ausgabe, Gerätetelemetrie und die Ausgaben synthetischer QA-Aufgaben. Die beiden Coding-Fixtures sind eigenständige Testverzeichnisse.

## QA der Modell- und MCP-Bereinigung

Dieser Abschnitt dokumentiert die historische Abnahme vor der Vereinheitlichung auf 256K.

| Prüfung | Status | Nachweis |
|---|---|---|
| Websuche im regulären Firefox | PASSED | Gemma 4 26B im Profil `research` rief nach **Allow once** `search_web` auf. Die Antwort verlinkte die offizielle Python-Dokumentation zu Decimal. Ein separater Playwright-Lauf prüfte zusätzlich den tatsächlichen HTTP-Tool-Response. |
| Deep Research im regulären Firefox | PASSED | `deep_research` wurde nach **Allow once** eingereicht. Die Statusabfrage über MCP meldete `completed`. Der Dienst erfasste eine offizielle Python-Quelle und lieferte nach dem Timeout der lokalen LLM-Synthese eine quellenbasierte Ersatz-Zusammenfassung. |
| Seitenabruf, Entwicklerdoku, GitHub und Skills | PASSED | Tatsächliche MCP-Aufrufe von `read_url`, `resolve-library-id`, `query-docs`, `get_latest_release` und `read_text_file`. |
| Keine Medien-MCPs in Llama Chat | PASSED | Nach dem Neustart der llama.cpp-Dienste zeigte ein neu geöffnetes Fenster im regulären Firefox-Profil vier verbundene Einträge. Die Atelier-Karte wurde über das native Menü entfernt. Der Gateway führte nur die drei statischen stdio-Server für Context7, GitHub und Skills. |
| Codex mit Cyber-Tiel | PASSED | Isolierter Coding-Lauf mit Bugfix, Refactoring, sechs Unit-Tests und unabhängiger Vertragsprüfung. |
| Claude Code mit Cyber-Tiel | PASSED | Nach dem Neustart des speicherintensiven Stageground-Entwicklungsservers bestand dieselbe Ledger-Fixture vier Unit-Tests und die unabhängige Vertragsprüfung. Die früheren Timeouts stehen im Benchmark-Verlauf. |
| Tool Calling mit Cyber-Tiel | PASSED | Zwei aufeinander aufbauende Tool-Aufrufe über die lokale Chat-API. Der zweite Aufruf verwendete die zuvor gelieferte Build-ID. |
| Defensive Prüfung mit Cyber-Tiel | FAILED | Die Prüfung erkannte, dass fehlende Principals abgelehnt werden müssen. Der vorgeschlagene Fix konnte bei einem fehlenden Tenant-Schlüssel weiterhin einen `KeyError` auslösen. |
| StyleTune und Human Writing | PASSED | Sechs native Template-Tests. Englische Szene mit zwei Dialogstimmen und deutsche Überarbeitung mit erhaltenem Datum, Zahl und Link. |
| Cyber-Tiel-Kontextprofile | PASSED | Fünf Profile von 32K bis 256K sind registriert. 64K lud mit 65.536 Tokens und beantwortete einen kurzen Retrieval-Test. Die Vollkontext-Messungen für 128K bis 256K stammen aus der früheren Messreihe. |
| Abschließender Dienstneustart | PASSED | Router, Websearch und MCP-Gateway antworteten nach dem Neustart. Beide lokalen Wrapper starteten mit `coding-fast` und Cyber-Tiel. Der Codex-Smoke-Test erzeugte die erwartete Antwort über die lokale Responses API. Atelier und Game Audio Forge waren weiterhin aktiv. |

## Historische QA vor der Modellbereinigung

| Prüfung | Status | Ergebnis |
|---|---|---|
| CUDA, CLI-Werkzeuge und Bindings | PASSED | CUDA0 auf RTX 5070, native sm_120a-Kernels, keine LAN-Bindung des neuen Routers oder Research-Dienstes |
| Offizielle WebUI, KDE-Starter und systemd | PASSED | Starter ausgeführt, Benutzerdienste neu gestartet, Modellwahl, Chat, Textanhang und wiedergeöffneter Chat im Firefox geprüft |
| Chat-Suche, Gesprächsexport und -import | PASSED | Testchat per Suche gefunden, als ZIP exportiert und in einem frischen Firefox-Profil importiert |
| Router-Modellwechsel und Idle-Sleep | PASSED | Maximal eine Instanz, Wechsel zwischen Modellen und Status sleeping im verkürzten Test |
| Websuche, HTML und PDF per MCP | PASSED | DuckDuckGo-Websuche aus Firefox nach einmaliger Freigabe. Python-Dokumentation und PDF-Text aus arXiv gelesen, Testadressbereich abgewiesen |
| Deep Research | PASSED | Zwei Jobs mit je zwei gelesenen Quellen, darunter ein Job durch den nativen Router in 39,3 s. Ergänzende Quellen unterschiedlicher Qualität erfordern Sichtprüfung |
| Filesystem, Context7, GitHub | PASSED | SKILL.md und Referenz gelesen, Pfad außerhalb der Freigabe abgewiesen. Astro-Dokumentation und read-only GitHub-Release gelesen |
| Hugging Face | PASSED | Anonyme Repo-Suche funktionierte im Test. Der optionale Streamable-HTTP-Zugang ist im Browser bei Bedarf hinzufügbar |
| Claude Code und Codex offline | PASSED | Getrennte Git-Fixtures bearbeitet und unabhängig mit Unit Tests geprüft. Beide Clients bestätigten auch den 128K-Alias |
| Skill-Zugriff | PASSED | Claude verwendete den Skill-Toolaufruf für backend-api-engineering. Codex lud die vorhandene Skill-Sammlung und beantwortete den Skill-Auftrag. Llama Chat nutzt read-only Filesystem-Zugriff |
| 128K, 192K und 256K | PASSED | Cyber-Tiel extrahierte drei Fakten je Test. Reeller 100K-Quellcode im 128K-Profil geprüft. Bei 256K wurden rund 196K Tokens wiederverwendet |
| LFM-Retrieval bei 128K | FAILED | Technischer Durchlauf abgeschlossen, 0 von 3 gesuchten Fakten im ersten vollständigen Langkontexttest |
| Coding-Security | PASSED | Defekt im kontrollierten lokalen Quelltext erkannt. Der erste Patch ließ den Randfall fehlender Schlüssel offen |
| Prosa und Deutsch | PASSED | StyleTune und Gemma QAT lieferten die englische Dialogprobe, QAT beantwortete die deutsche Alltagsprompt |
| MTP | PASSED | Sidecar und Toolkette lauffähig. Die Gesamtdauer war höher, daher in den Standardprofilen deaktiviert |
| NVMe und persistenter Slot | PASSED | mmap und Direct I/O verglichen. Nach Speichern, Entladen und Laden wurden 2.663 Tokens aus dem Slotzustand wiederverwendet |
| Optionale Integrationen | SKIPPED | Vulkan-Benchmark, SearXNG-Instanz, Playwright-MCP, zusätzlicher Gemma-Community-Quant und YOLO-Auto |
| Vollständiger Systemneustart | SKIPPED | Laufende Desktop-Sitzung, Dienstneustart geprüft |
| Medienpipelines, Status | PASSED | Audio-Webinterface HTTP 200, Dienstzustände vor und nach dem Setup geprüft. Keine Generierungsprobe ausgelöst |

### QA der Writing-Integration

| Prüfung | Status | Ergebnis |
|---|---|---|
| Systemkontext und Routing | PASSED | Native `/apply-template`-Tests decken alle vier Profile, alle sechs Modi und beide Sprachreferenzen ab. Vorhandene Benutzer-Systemnachricht bleibt wirksam. |
| Firefox ohne externes Netz | PASSED | Profilwechsel, Dialog und Audit in der offiziellen WebUI über den lokalen Unix-Socket. Beide Antworten wurden im Chat gerendert. Das Modell gab keine Tool-Aufrufe aus. |
| Tool-Filter | PASSED | Bei lokalem Schreiben und Audit werden Tool-Beschreibungen ausgeblendet. Im damaligen Test mit `[web]` rendert das Template ausschließlich die angebotenen Such- und Seitenabruf-Tools. Es erkennt sowohl die direkten MCP-Namen als auch die zuvor serverseitig verwendeten Namen. Die lokale Dateinavigationsprobe des Browsers wurde abgewiesen. |
| Skill-Werkzeuge | PASSED | Alle drei vorhandenen CLI-Tests bestanden in einer temporären Testkopie. Filesystem MCP bietet weiterhin zehn reine Lesewerkzeuge. |
| Wiederherstellung der Writing-Konfiguration | PASSED | Das Wiederherstellungspaket rendert im Test-Benutzerverzeichnis eine bytegleiche Vorlage aus dem zentralen Skill-Checkout. |
| Redaktioneller Vergleich | GETESTET | Neun A/B-Paare ergaben Verbesserungen bei einzelnen Texten und weiterhin Fehler bei Umfang und Faktentreue. Siehe [Modellvergleich](MODEL_BENCHMARKS.md#human-writing-mit-gemma-4-12b-styletune). |

Die Mitschnitte der Routing- und Firefox-Prüfung liegen für diesen Lauf unter `~/.cache/llama.cpp/writing.hmhXLZBN`. Die Web- und Projekt-CLIs wurden mit lokalen Testdaten geprüft.

### QA der MCP-Umstellung

| Prüfung | Status | Nachweis |
|---|---|---|
| Einträge aus zentraler Konfiguration | PASSED | Vier Karten mit insgesamt 20 Tools in einem neu angelegten Firefox-Profil am Produktions-Origin. |
| Websuche und Seitenabruf | PASSED | Tatsächliche Streamable-HTTP-Aufrufe für `search_web` und `read_url` aus einem Chat der installierten WebUI. Treffer und Seiteninhalt aus der offiziellen Python-Dokumentation. |
| Deep Research | PASSED | Job aus der WebUI gestartet. `deep_research_status` meldete `completed` und lieferte eine Quelle aus der offiziellen Python-Dokumentation. |
| Context7 und GitHub | PASSED | `resolve-library-id` und `query-docs` lieferten Astro-Dokumentation. `get_latest_release` lieferte die Upstream-Release-Daten von llama.cpp. |
| Skill-Sammlung | PASSED | `read_text_file` lieferte das echte Human-Writing-SKILL.md. Das Modell wandte die Regel für maximal zwei Überarbeitungsschritte an. Der direkte MCP-Test wies einen Pfad außerhalb der Freigabe ab. |
| Writing | PASSED | Dialog und Audit mit StyleTune in Firefox. Das Systemtemplate lädt die Skill-Regeln automatisch. In der Prompt-Probe wurden die direkten Werkzeugnamen nur mit `[web]` angeboten. |
| Tool-Freigaben | PASSED | Vor den geprüften MCP-Aufrufen erschien **Allow once**. Im UI-Test wurde jede Freigabe einzeln erteilt. |
| HTTP-Grenzen des Gateways | PASSED | Erlaubter WebUI-Origin HTTP 200. Fremder Browser-Origin HTTP 403 und fremder Host-Header HTTP 421. |
| Neustart der Dienste | PASSED | Alle drei Benutzerdienste wurden neu gestartet. Der reguläre Firefox zeigte beim Wiedereinstieg am KDE-Origin die vier verbundenen Einträge. |
| Browser-Neustart | PASSED | Ein persistentes Firefox-Testprofil wurde geschlossen und nach dem Dienstneustart neu geöffnet. Die vier Einträge blieben gespeichert und verbanden sich erneut. |

Die ausführlichen Tool-Ergebnisse der Firefox-Automation liegen für diesen Lauf unter `~/.cache/llama.cpp/mcp-menu.7I318ZkC`. Die Migration im regulären Browser hat nur MCP-Einträge über die vorhandene Oberfläche ergänzt.

Historische Medienmessungen bleiben im Wiederherstellungspaket unter `benchmarks/results/media-mcp.json`. Atelier und Game Audio Forge laufen als eigenständige Projekte.
