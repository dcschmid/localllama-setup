# Wiederherstellungstest

Geprüft am 18. November 2026 auf dem Framework Laptop 16 mit Fedora 44 und RTX 5070 Laptop. Die Installation wurde in frischen Test-Benutzerverzeichnissen ausgeführt. Die vorhandenen GGUF-Dateien waren dort über Symlinks verfügbar. Die Test-Router liefen separat in einem Netzwerk-Namespace mit Loopback.

## Historischer Restore mit Writing und Medien

Das Setup lief mit gesicherten Release-Archiven, vorhandenen Modellen und den drei gesicherten CUDA-Bibliotheken. npm und uv waren auf ihre lokalen Caches und den Offline-Modus eingestellt. Die vorhandene Atelier-CLI und das installierte Atelier-Programm wurden für den Test verlinkt. Die gemeinsame Skill-Sammlung wurde über `LLAMA_SETUP_SKILLS` eingebunden.

| Prüfung | Status | Nachweis |
|---|---|---|
| Frisches Benutzerverzeichnis | PASSED | Sieben GGUFs und drei CUDA-Bibliotheken per SHA-256 geprüft. llama.cpp b12503 erkannte die RTX 5070 als CUDA0. Node 24.22.1, GitHub MCP 2.2.0, Websearch und mcp-proxy 0.15.0 installiert. |
| Erneuter Setup-Lauf | PASSED | Die identische Konfiguration wurde akzeptiert. Abhängigkeiten und vorhandene Modelle wurden wiederverwendet. |
| WebUI und Router | PASSED | `GET /` lieferte mit `curl --compressed` HTTP 200. `GET /models` zeigte 16 Profile einschließlich `media-cpu`. `GET /props` zeigte fünf zentrale MCP-Einträge und Atelier mit `enabled: false`. |
| Atelier und Skills über MCP | PASSED | Der wiederhergestellte Streamable-HTTP-Gateway bot 16 freigegebene Atelier-Werkzeuge und zehn Filesystem-Werkzeuge an. Der Test las die Originaldatei von Human Writing über `read_text_file`. Die üblichen Filesystem-Schreibwerkzeuge fehlten. Der lokale Exportordner hatte Modus `0700`. |
| Human-Writing-Template | PASSED | Der Installationsstand renderte den Systemkontext aus dem Original-Skill. |
| Fehlende optionale Komponenten | PASSED | Der Konfigurationsrenderer wurde für alle vier Kombinationen aus vorhandenen und fehlenden Skills und Atelier ausgeführt. Die Serverkonfiguration und die Browser-Vorgaben stimmen jeweils überein. |
| KDE-Starter und Units | PASSED | `desktop-file-validate` und `systemd-analyze --user verify` meldeten keine Fehler. |
| Mediengenerierung, Firefox und Online-Recherche im isolierten Restore | SKIPPED | Der Restore-Test hat die Anbindung und Werkzeuglisten ohne neue Medienjobs geprüft. Die früheren Medienmesswerte stehen in [media-mcp.json](../benchmarks/results/media-mcp.json). |
| Neuinstallation der Medienprojekte und des Betriebssystems | SKIPPED | Atelier und Game Audio Forge haben eine separate Projektinstallation. Die Wiederherstellung dieser Projekte richtet sich nach ihren eigenen Setup-Anleitungen. |

## Ursprünglicher Restore mit 12 Profilen

| Prüfung | Status | Nachweis |
|---|---|---|
| Neuinstallation aus vorhandenen Daten | PASSED | Release-Archive, sieben GGUF-Dateien und drei CUDA-Bibliotheken per SHA-256 geprüft. Upstream-Build b12503 erkennt CUDA0. |
| MCP-Pakete aus dem Cache | PASSED | Node 24.22.1 und GitHub MCP 2.2.0 installiert. Beide npm-Installationen liefen mit den Lockfiles. Der Websearch-TypeScript-Build gelang auch mit npm im Offline-Modus und gesetztem `NODE_ENV=production`. |
| Setup erneut ausführen | PASSED | Wiederholung im selben Test-Benutzerverzeichnis akzeptiert vorhandene Profile und installierte Komponenten. |
| Systemd-Units und Anwendungsstarter | PASSED | Prüfung mit `systemd-analyze --user verify` und `desktop-file-validate`. |
| WebUI, Router und CUDA-Chat im isolierten Netzwerk | PASSED | Die eingebettete WebUI lieferte HTTP 200. `/models` listete 12 Profile. `fast-chat` antwortete auf die Probe mit `RESTORE_OK`. |
| Read-only Skills | PASSED | Der wiederhergestellte Router erkannte 10 Filesystem-Werkzeuge. Die gerenderte MCP-Konfiguration enthielt `--read-only`. |
| Benchmark-Aufrufe | PASSED | CUDA-Kurzbenchmark mit 128 Prompt- und 16 Decode-Tokens pro Teiltest. Der Router-Test für 8K verarbeitete 7.672 Eingabetokens vor Chat-Template und fand alle drei Fakten. |
| Vollständige Fedora-Neuinstallation und erneute große Downloads | SKIPPED | Geprüft wurde die Wiederherstellung aus vorhandenen Archiven, GNU/Linux-Systempaketen und Modellgewichten. |
| Desktop-Neuanmeldung, Online-Recherche und komplette Agentenläufe nach dem Restore | SKIPPED | Die ausführlichen Funktions- und Offline-Coding-Tests des ursprünglichen Stands stehen in [SETUP.md](SETUP.md) und [MODEL_BENCHMARKS.md](MODEL_BENCHMARKS.md). |

## Deinstallation

| Prüfung | Status | Nachweis |
|---|---|---|
| Vorschau am installierten System | PASSED | `--dry-run --remove-models` listete alle drei Units, die paketierten Komponenten und sieben GGUFs. |
| Deinstallation im Testverzeichnis | PASSED | Getrenntes Home mit simuliertem systemd-User-Manager. Dienste wurden vor dem Verschieben der Units gestoppt. Konfiguration und CUDA-Bibliotheken wurden gesichert. Browser, Cloud-Profile, Medien und Modelle blieben erhalten. |
| Optionale Modellentfernung | PASSED | Listeneinträge und Teildownloads wurden entfernt. Eine zusätzliche GGUF-Datei, eine Datei mit abweichender Größe und das Ziel eines Modell-Symlinks blieben erhalten. |
| Erneute Aufrufe und Fehlerfälle | PASSED | Wiederholter Aufruf erzeugte keine weitere Sicherung. Ein belegter Setup-Lock, eine Unit aus einem anderen Verzeichnis und ein fehlgeschlagener Dienststopp verhinderten das Entfernen der Dateien. |
| Deinstallation im laufenden Benutzerkonto | SKIPPED | Dort wurde nur die Vorschau ausgeführt. |

## Konfigurationsprüfung nach der MCP-Bereinigung

Die Setup-Vorlagen wurden mit und ohne gemeinsame Skill-Sammlung gerendert. Die Browserliste und die Gateway-Konfiguration stimmen in beiden Fällen überein. Das Modellmanifest entspricht den im Router eingetragenen GGUF-Dateien. Die vollständige paketbasierte Neuinstallation ist in diesem Prüfschritt nicht wiederholt worden. Die Funktionsprüfungen der aktualisierten Live-Installation stehen in [SETUP.md](SETUP.md#qa-der-modell--und-mcp-bereinigung).
