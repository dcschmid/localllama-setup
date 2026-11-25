# Reparatur der Qualitätsprüfung in der autonomen Story-Produktion

## Nachgewiesene Ursache

Der Szenenentwurf von Kapitel 1, Version 2, enthält die Beschreibung der Wintersonne nur einmal. Der zweite gespeicherte Modellpatch ersetzte den Satzanfang `It was only nine in the morning`. Sein Ersatz enthielt eine weitere Beschreibung des Sonnenlichts und endete mit `It wasn't even ten yet.`. Die ursprüngliche Fortsetzung `, but already …` lag außerhalb des Patches und blieb stehen. Das Nachspielen der beiden gespeicherten Ersetzungen auf Version 2 ergibt exakt den Text von Version 3. Der Fehler entstand bei der Überarbeitung nach dem Zusammenfügen der Szenen.

Der alte Patchprüfer verlangte eine eindeutige Fundstelle und prüfte überlappende Bereiche. Satzgrenzen und neu eingefügte Doppelungen waren von dieser Prüfung nicht erfasst. Die anschließende Rangfolge verglich die Anzahl der Modellbefunde. Sie konnte dadurch einen beschädigten Kandidaten vorziehen. Ein exaktes Zitat und ein beliebiger nicht leerer `issue`-Wert galten zudem als Beleg. Der gespeicherte Pausegrund enthält `issue: "blocking"`. Die Stempelbemerkung enthält lediglich `issue: "editorial"`.

## Änderungen

- `libexec/creative_studio_production.py` verlangt eine Begründung, eine konkrete Korrektur und zitierbare Gegenbelege, bevor eine zweite Modellprüfung einen zentralen Konflikt bestätigen kann. Stilfragen und unbestätigte Behauptungen bleiben in den Prüfdetails. Fehlerhafte Kapitelzuordnungen, Versionen und Checkpoints werden vor dem Fortsetzen geprüft.
- `skillset/skills/human-writing/scripts/fiction_audit.py` erkennt in Version 1.2.0 fehlerhafte Zeichensetzungsübergänge und nahe Satzwiederholungen. Ein lokaler Zeitvergleich prüft plausible Lesarten von ungefähren Stundenangaben. Bei den vorliegenden Zeitangaben sind ungefähr vier Stunden mit `a few hours` vereinbar.
- Lokale Reparaturen werden auf einen Kandidaten angewandt. Die Patchprüfung schützt Satzanschlüsse, Nachbarsätze, Zitate, Uhrzeiten und Motive. Überlappende, mehrdeutige und bereits verbrauchte Patchstellen werden abgelehnt. Neue Wiederholungen oder Satzfehler verwerfen den Kandidaten vor dem Speichern.
- `production.ts` und `studio.ts` zeigen Fortschritt, gespeicherte Korrekturen und abgeschlossene Kapitel. Die Prüfdetails sind aufklappbar und bleiben während Statusaktualisierungen am zugehörigen Kapitel.
- Die ergänzten Tests decken den beobachteten Fehler und unabhängige deutsche und englische Texte ab. Auf einer Testdatenbank prüft die Suite explizites Fortsetzen, die Vorgängerversion, den Übergang zum nächsten Kapitel und die Wiederverwendung des ersten Bildauftrags.

## Abnahme

- Acht Python-Produktionstests und sechs Langformtests bestanden. Die bestehenden Planungs-, Story-, Chat-, Organizer-, Linter-, Projekt- und Website-Tests wurden erneut ausgeführt.
- Gemma 4 QAT prüfte den echten Kapiteltext auf einer SQLite-Kopie. Die Kopie erreichte nach zwei minimalen Textkorrekturen Version 4 mit 1.156 Wörtern und wechselte automatisch zur Illustration. Die doppelte Sonnenpassage kam einmal vor. Die Wiederholung mit dem endgültigen Stand und Human Writing 1.2.0 bestätigte den Wechsel zur Illustration nach einem Korrekturpass erneut. Die Manuskript- und Bilddaten der laufenden Instanz wurden dabei als Quelle gelesen.
- Firefox hat die Statusanzeige, aufklappbare Prüfdetails und den Manuskript-Export mit simulierten Bildantworten geprüft. Astro-Build und TypeScript-Check liefen erfolgreich. Semgrep meldete bei den geprüften Python-Pfaden keine Befunde.
- Der aktualisierte Audit ist konservativ. Ungefähre oder mehrdeutige Szenenabfolgen können offen bleiben. Eine Modellbestätigung ersetzt keine redaktionelle Entscheidung bei komplexen zentralen Konflikten. Fehlende Pflichtszenen werden aus einem Textfenster allein nicht als bestätigt eingestuft.

## Erhalt des Auftrags

Das Backup `output/story-production-acceptance/quality-gates/studio-before-quality-gates-20261125-061049.sqlite3` wurde vor der Arbeit an den Checkpoints mittels SQLite-Online-Backup erstellt. Integrität, Job-ID, Kapitelzuordnung, Versionsfolge und die Nutzdaten der relevanten Tabellen wurden geprüft. Der Auftrag hält auf dem ursprünglichen Kapitel und der bestehenden Version. Die ausdrückliche Aktion **Gespeichertes Kapitel erneut prüfen** nutzt den vorhandenen Checkpoint und bewahrt alte Audits und Patchversuche.

Der reproduzierbare Modelltest steht in `tests/creative-studio-real-quality.py`. Er arbeitet auf einer temporären Kopie, endet vor der Bildeinreichung und speichert Modellbelege und Prüfzustand in der angegebenen JSON-Datei.
