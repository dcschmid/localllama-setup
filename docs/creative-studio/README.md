# Local Creative Studio

Lokales Schreiben, Deep Research, Bildgenerierung und Game-Ideen über die
bestehende llama.cpp-Installation, den bestehenden Image-Service und das
bestehende Skillset. Kein Cloud-Zwang, keine zweiten Engines.

- UI + API: `http://127.0.0.1:8700` (nur Loopback)
- Studio-Daten: `~/.local/share/creative-studio` (SQLite mit Chats, Projekten, Dokumenten und Anhängen). Bilddateien liegen im Archiv des lokalen Bilddienstes.
- Konfiguration: `~/.config/creative-studio`
- Backups: `~/.local/state/creative-studio/backups` (sqlite3-Tar.gz)

Der [Bericht zur Schreibpipeline](WRITING_PIPELINE.md) dokumentiert die aktiven Skills, automatische Korrekturen und die Abnahmeläufe.

## Im Studio arbeiten

Beginne im Chat mit einem freien Auftrag oder einem der vier Vorschläge. Das Studio erkennt Schreibaufträge, Deep Research, Bildwünsche und Spielideen anhand der Formulierung. Die **Tätigkeit** am Eingabefeld ist optional. Im Standardmodus erkennt das Studio die Aufgabe. Auch mit gewählter Tätigkeit kannst du im selben Chat etwa ein Bild oder eine Recherche anfordern. **Werkzeugoptionen** öffnet Bild- und Rechercheeinstellungen. [Ablauf und technische Diagnose](INTEGRATION.md)

- Ein Schreibauftrag speichert den Entwurf im aktuellen Chat. Öffne den Entwurf direkt aus der Antwort. Im Editor findest du **Text prüfen** und **Text verbessern** direkt am Dokument. Im Vergleich entscheidest du, welche Änderungen als neue Version gespeichert werden.
- Recherchen zeigen Arbeitsschritt, Runden, verfügbare Quellen und offene Fragen in der Unterhaltung. Du kannst pausieren, fortsetzen und das Dossier im Editor öffnen.
- Bilder erscheinen nach Abschluss im Chat und in **Bibliothek → Bilder**. Die dort abrufbaren Folgeseiten enthalten weitere gespeicherte Bilder. Der Auftragsverlauf zeigt Fehler und Abbrüche. In der Bildvorschau kannst du ein Bild zu einem Chat oder Dokument hinzufügen oder erneut generieren.
- Im Story-Chat öffnet **Bildstil** das gespeicherte Visual Profile und die Visual Bible. Ein Beispiel für die direkte Bedienung ist „Verwende ab jetzt Graphic Novel für diese Geschichte.“ Neue Titel- und Kapitelbilder beginnen mit 16:9. [Story Visual Profiles](STORY_VISUAL_PROFILES.md)
- Spielideen starten im Chat. Wähle bei Bedarf eine Rolle und verwende das **Decision Log**, um Entscheidungen festzuhalten. Die Seitenleiste öffnet Chats, der Button **Inhalte** zeigt deren Dokumente.
- Exportiere im Editor oder per Chat, etwa mit „Exportiere den Artikel als Astro MDX.“ Enthält das Dokument Studio-Bilder, bündelt der Download den Text und die Bilddateien in einem ZIP.

## Inhalte organisieren

- Lege Ordner über das Plus in der Seitenleiste an. Die drei Punkte öffnen die Aktionen für einen Eintrag. Zum Verschieben kannst du auch einen Eintrag auf einen Ordner ziehen. Öffne das Ordner-Menü, um direkt dort einen Chat oder Unterordner anzulegen.
- Unter **Chats → Alle** findest du die Suche nach Namen und Nachrichten, die Sortierung nach Änderungsdatum und die Mehrfachauswahl. **Inhalte** zeigt Dokumente, Bilder und Anhänge bis 10 MB pro Datei aus dem geöffneten Chat.
- Im Papierkorb siehst du den ursprünglichen Ort und das Löschdatum. Du kannst komplette Ordner und Chats oder einzelne enthaltene Einträge wiederherstellen. Beim endgültigen Löschen erscheint eine Vorschau. Der Papierkorb wird manuell geleert.
- Laufende Aufträge blockieren das Löschen der zugehörigen Inhalte. Gemeinsam verwendete Bilder bleiben erhalten, solange eine Verknüpfung besteht. Bestätigte Bildlöschungen werden über den lokalen Bilddienst abgewickelt und bei einem vorübergehenden Fehler wiederholt.

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
Vor der SQLite-Migration legt das Studio im Datenverzeichnis eine konsistente
Datenbankkopie mit dem Namen `studio-before-v*.sqlite3` an. [Migrationsplan](CHAT_MIGRATION.md)

## Resource Coordinator

Eine GPU-Schlange, keilfrei:

- Bildjobs bleiben `waiting_gpu`, bis `nvidia-smi` ≥ ~1 GiB frei meldet;
  erst dann Einreichung beim Image-Service (:7861). CPU-Offload bleibt respektiert.
- LLM-Aufrufe serialisieren über den llama.cpp-Router (:8080); eine Coding-Session
  (Pi/Cyber-Tiel) wird nie gestoppt oder verdrängt.
- Research- und Schreibjobs liegen persistent in SQLite und überleben
  Backend-Neustart (checkpoint/resume, Pause/Resume, Budget).

## Modelle (bestehende Aliase, keine neuen Modelle)

Produktiv sind genau zwei Gewichte (beide 262.144 Kontext / 8.192 Ausgabe,
Router `--models-max 1`, kein Profil unter 256K). Alle Aliase stammen aus
`~/.config/llama.cpp/models.ini` und laden eines der beiden Gewichte:

| Alias | Gewicht | Rolle |
|---|---|---|
| research / deep-research / research-code | Gemma 4 26B-A4B QAT HauhauCS | Recherche, Fakten, Bibeln, Kontinuität |
| story / creative-writing / human-* | UltimateIntent Gemory 26B-A4B | Geschichten, Artikel, Human Writing DE/EN |

Coding-Rollen sind aus der Produktion ausgeschieden; externe Entwickler
(yolo-auto, Claude) arbeiten unabhängig vom Router.

## Human Writing

Im Editor stehen Linter-Funde und redaktionelle Einschätzungen getrennt im Audit. Frühere Prüfungen und Fassungen bleiben erreichbar. Derselbe Ablauf ist aus dem normalen Chat verfügbar. [Redaktioneller Ablauf und technische Einbindung](EDITORIAL.md)

### Geschichten und Romane

Für ein neues Manuskript öffne **Story-Planung**. Die Produktionsmodi erstellen geprüfte Kapitel und Illustrationen auf Basis einer freigegebenen Planung. [Story-Produktion und Manuskriptexport](STORY_PRODUCTION.md)

Beginne im Chat mit „Erstelle eine Story-Bibel und plane acht Kapitel.“ Die Kapitelübersicht und die Story-Bibel findest du dann unter **Inhalte**. Die **Story-Bibel** speichert Figuren, Beziehungen, Weltregeln, Chronologie, offene Handlungsstränge, Perspektive und Ton. Wenn du ein vorhandenes Dokument als Eröffnung auswählst, übernimmt Kapitel 1 dessen Text wortgetreu in einen eigenen Entwurf.

- Mit **Kapitelübersicht erstellen** planst du mehrere Kapitel. Über **Kapitel planen** legst du ein einzelnes Kapitel mit eigener Wortspanne an. Für neue Kapitel gilt zunächst ein Ziel von 1.000–1.500 Wörtern.
- Wähle **Nächstes Kapitel schreiben** oder fordere im Projektchat zum Beispiel „Schreibe Kapitel 3 mit 1.200–1.500 Wörtern“ an. Das Studio lädt die Story-Bibel, passende Kapitelzusammenfassungen und das Ende des letzten Kapitels. Längere Kapitel werden in Abschnitte aufgeteilt.
- Im Editor findest du die Kapitelnavigation, den Status, die Wortzahl und die vorhandenen Werkzeuge für Textprüfung und Szenenüberarbeitung. Der Chat zeigt die Berichte zur Kapitelkontinuität und zur Gesamtprüfung der bisher geschriebenen Geschichte. Freigegebene Kapitel können erst nach dem Aufheben der Freigabe geändert werden. Alle Fassungen bleiben im Versionsverlauf.

Das lokale Profil `creative-writing` ist für ein Kontextfenster von 262.144 Tokens und ein eigenes Ausgabebudget von 8.192 Tokens konfiguriert. Das Studio verwendet kleinere Ausgabebudgets pro Modellaufruf und begrenzt den automatisch geladenen Erzählkontext.

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
python3 tests/creative-studio.py        # API-Vertrag, erzeugt Testeinträge
python3 tests/creative-studio-organizer.py   # Migration, Papierkorb und Bildfreigaben in einer temporären Instanz
python3 tests/creative-studio-chat.py        # Chat-Kontexte, Kapitelnumerierung, Migration und Papierkorb
python3 tests/creative-studio-story.py       # Kapitelplanung, Versionen, Freigabeschutz und Wortbereiche
tests/unit.sh                           # Installer-Regression
```

Die Browserprüfung läuft gegen ein Studio mit temporärem Datenverzeichnis und verwendet die konfigurierten lokalen Dienste. Das Bildszenario kann ein Testbild in der Galerie des Bilddienstes ablegen. Die Prüfung benötigt Firefox über Playwright, axe-core sowie `unzip` für den Bildexport. Mit einer optionalen Prototyp-URL und ImageMagick vergleicht sie den Startbereich mit Design A.

```bash
npm --prefix packages/creative-studio/web run build
studio_test_data=$(mktemp -d)
XDG_DATA_HOME="$studio_test_data" CREATIVE_STUDIO_PORT=8707 \
  CREATIVE_STUDIO_WEB="$PWD/packages/creative-studio/web/dist" \
  python3 libexec/llama-creative-studio serve
```

In einem zweiten Terminal mit `playwright` und `axe-core` im Node-Modulpfad starten.

```bash
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:8707/ node tests/creative-studio-browser.mjs
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:8707/ node tests/creative-studio-organizer.mjs
```

`CREATIVE_STUDIO_TEST_FLOWS` nimmt eine kommagetrennte Auswahl aus `image,story,article,game,research,layout,regression,assets` an. Für die Galerieprüfung wird mindestens ein gespeichertes Bild benötigt. Für den visuellen Vergleich starte [Prototyp A](prototypes/README.md) und setze `CREATIVE_STUDIO_TEST_DESIGN_URL` auf seine Adresse.

### Prüfung der Umstellung auf Design A

| Ablauf | Beobachtung in Firefox mit separater Studio-Datenbank |
| --- | --- |
| Anwendung öffnen, direkt chatten | llama.cpp antwortete auf eine freie Nachricht. |
| Geschichte beginnen, bearbeiten und prüfen | Der Auftrag legte den Roman und einen Entwurf an. Der Editor speicherte eine neue Version, öffnete eine ältere Fassung und zeigte den Human Writing Audit. Eine markierte Passage wurde mit dem Schreibmodell überarbeitet, übernommen und wieder rückgängig gemacht. |
| Deep Research | Pause und Fortsetzen funktionierten. Die Recherche lieferte zwei Quellen und ein gespeichertes Dossier. |
| Bild erstellen | Der Bilddienst erzeugte eine Datei, die im Chat, in der Großansicht und nach dem Neuladen sichtbar war. |
| Spielidee und Projekt | Das Modell antwortete im Game Lab. Eine Entscheidung war nach dem Wiederöffnen des Projekts verfügbar. Das Romanprojekt ließ sich umbenennen. |
| Artikel exportieren | Markdown und Astro MDX waren herunterladbar. Der Export mit eingefügtem Bild enthielt die MDX-Datei und das PNG im ZIP. |
| Desktop, Tablet und Mobil | Hell und Dunkel, 320-Pixel-Reflow und Tastaturbedienung geprüft. Der Startbereich war in sechs Ansichten pixelgleich mit dem Prototyp. |
| Navigation und Galerie | Die Recherche bleibt bei einem verspäteten Projektabruf sichtbar. In der produktiven Galerie erschienen nach dem Laden der Folgeseite 107 eindeutige Bilder. |

Die axe-Prüfung der getesteten Startansichten, Bildvorschau und des Schreibstil-Dialogs meldete keine automatisierten A- oder AA-Verstöße. Die Orca-Prüfung scheiterte in der isolierten Sitzung am AT-SPI-Dienst. Eine vollständige WCAG-2.2-AA-Prüfung steht damit aus.
