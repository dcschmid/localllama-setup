# llama.cpp auf dem Framework Laptop 16

1. Im KDE-Anwendungsmenü **llama.cpp** öffnen. Der Starter startet den Benutzerdienst und öffnet [Llama Chat](http://127.0.0.1:8080).
2. Im Chat unten das Modell wählen. **research** ist für den Alltag, Dokumente, Websuche und Deep Research. **coding-long-256k** öffnet Cyber-Tiel. **creative-writing** ist für Geschichten und Dialoge. Das Modell lädt beim ersten Zugriff.
3. Für Textdokumente **+** und **Add files** wählen. Die Unterhaltung im Chatverlauf wieder öffnen oder im Einstellungsmenü **Import/Export** verwenden.
4. Öffne **MCP Servers** über den MCP-Eintrag in der Seitenleiste. Dort stehen **Websearch & Deep Research**, **Context7**, **GitHub** und **Skill-Sammlung (read-only)**. [MCP Servers öffnen](http://127.0.0.1:8080/#/mcp-servers)
5. Wähle im Chat **research** und bei Bedarf unter **+ → Tools** den gewünschten MCP-Server. Beispielauftrag `Suche mit search_web nach der offiziellen Python-Dokumentation zu Decimal. Gib die URL aus dem Tool-Ergebnis an.` Bestätige den einzelnen Aufruf mit **Allow once**. Für Deep Research wähle **deep-research**, starte `deep_research` und frage anschließend mit `deep_research_status` und der Job-ID nach. Das Profil verwendet dieselbe Gemma-Datei mit einem kürzeren Denkbudget für die Synthese.
6. Die Skill-Sammlung kannst du mit `read_text_file` lesen lassen. Beispiel `Lies das Human-Writing-SKILL.md aus unserer lokalen Skill-Sammlung und nenne die Regel für Überarbeitungsschritte.` Die Writing-Profile laden ihre Human-Writing-Regeln auch automatisch beim Schreiben.

Wähle in einem wieder geöffneten Chat bei Bedarf ein vorhandenes Profil. Der KDE-Starter verwendet immer `http://127.0.0.1:8080`. Nimm diese Adresse für den Zugriff auf dieselben Chats, MCP-Einträge und Freigaben.

## Schreiben mit StyleTune

Wähle in einem neuen Chat unten **creative-writing**, **human-writing**, **human-rewrite** oder **human-audit**. Diese Profile verwenden dieselbe StyleTune-Datei und laden den Human-Writing-Skill automatisch. Für eine Geschichte oder Szene passt **creative-writing**. Für Blogartikel, Reviews und Devlogs passt **human-writing**. **human-rewrite** bearbeitet vorhandenen Text. **human-audit** liefert Befunde.

Schreib den Auftrag in die erste Zeile und setze den Ausgangstext oder die Stilproben darunter. Optionale Tags am Anfang steuern Sprache, Modus oder Genre ausdrücklich.

- `[en] [fiction] Write a Riff Racers paddock scene from Cleo's point of view.`
- `[de] [editorial] Schreibe einen Blogartikel aus diesen drei Beobachtungen.`
- `[de] [rewrite] Überarbeite den folgenden Abschnitt. Lass Zitate und Links exakt stehen.`
- `[en] [audit] Audit the prose below for vague claims and repetition.`
- `[de] [voice] Kalibriere meinen Stil anhand dieser drei Textproben.`
- `[website-audit] Prüfe diese HTML-Auszüge oder diesen Auditbericht.`
- `[website-rewrite] Erstelle Ersatzvorschläge für die freigegebenen Textstellen.`

Normales Schreiben und Prüfen von eingefügtem Text laufen offline. Für einen konkreten Abruf beginne mit `[web]`, „Recherchiere im Web“ oder „Verwende ausdrücklich unseren Websearch MCP“. Aktiviere bei Bedarf das vorhandene Websearch-Werkzeug unter **+ → Tools → Websearch & Deep Research**. Für die zusätzliche Text-Linter-Prüfung mit einer gespeicherten Datei steht der Befehl in [SETUP.md](SETUP.md#human-writing-in-der-webui).

### Sachtexte aus Quellen

1. Erstelle im Profil **research** ein Faktenblatt. Beispielauftrag `Sammle nur Belege zur Fragestellung. Liste pro Fakt eine ID, die genaue Aussage, den Quellenausschnitt und die URL. Markiere Widersprüche und fehlende Belege. Schreibe noch keinen Artikel.` Für Devlogs und andere interne Themen kannst du bestätigte Notizen, Testergebnisse oder Textauszüge selbst als Faktenblatt einfügen.
2. Wechsle zu **human-writing**. Füge das Faktenblatt unter `[fakten] [de] Schreibe aus F1, F2 usw. Setze zu jeder Tatsachenbehauptung die passende F-ID. Wenn die Belege kurz sind, darf der Text kürzer ausfallen.` ein. Wiederhole `[fakten]` bei quellengebundenen Folgeaufträgen.
3. Prüfe den Entwurf in einem separaten **research**-Chat. Gib dem Modell das Faktenblatt und den Entwurf. Frage nach unbelegten Aussagen, Sinnverschiebungen und Beobachtungen, die der Autor nur abgeleitet hat. Lass beanstandete Stellen mit **human-rewrite** gezielt kürzen. Bei wichtigen Aussagen prüfe die Originalquelle.

### Geschichten mit Wortvorgabe

Teile eine Geschichte mit Zielgröße 1.200 Wörter in vier Szenen mit je etwa 300 Wörtern. Gib StyleTune pro Anfrage den nächsten Handlungsschritt, die vorherige Szene und die gewünschten Figurenstimmen. Zähle anschließend die Wörter im zusammengefügten Text. Wenn ein Abschnitt zu kurz ist, ergänze einen konkreten Handlungsschritt an dieser Stelle.

## Lokales Coding

Beide Befehle starten **Coding Long 256K** mit Cyber-Tiel. Das Kontextfenster umfasst 262.144 Tokens und die Ausgabevorgabe beträgt 8.192 Tokens. In Claude zeigt `/context` die Belegung, `/status` den lokalen Server und `/autocompact` den eingestellten Fensterwert. [Messung und Rollback](PERFORMANCE_OPTIMIZATION.md)

```bash
claude-local
codex-local
```

Lange Anhänge lassen sich auf mehrere Eingaben verteilen. Für Folgefragen behältst du das Gespräch im selben Profil. Beim Entladen verliert der Router den gespeicherten Prompt-Zustand.

Research und Inference lassen sich einzeln kontrollieren:

```bash
systemctl --user status llama-cpp.service llama-cpp-research.service llama-cpp-mcp.service
systemctl --user stop llama-cpp.service
```

Ein erneuter Start über das Anwendungsmenü bringt die Oberfläche zurück. Details stehen in [SETUP.md](SETUP.md) und [MODEL_BENCHMARKS.md](MODEL_BENCHMARKS.md).
