# Creative-Studio-Aufträge mit Text und Bild

## Ursache des Fehlers

Die gespeicherte Unterhaltung zum fehlgeschlagenen Auftrag enthält eine Anfrage mit dem Modellprofil `creative-writing`, die Antwort des Modells und die Studio-Nachricht mit einer Dokument-ID. Das Studio hatte den Modelltext also tatsächlich gespeichert. Für den kombinierten Auftrag wurde kein Bildjob ausgeführt.

- Der bisherige Client-Router gab genau einen Intent zurück. Mit dem Wortlaut aus der gespeicherten Anfrage liefert er im Automatikmodus `clarify`. Die anschließende Werkzeugwahl führte genau einen Zweig aus. Der gespeicherte Verlauf belegt den Schreibzweig. Welcher UI-Schritt zu dieser Auswahl führte, lässt sich daraus nicht rekonstruieren. [Client-Intent](../../packages/creative-studio/web/src/lib/intent.ts)
- Der Schreibzweig reichte den ganzen Auftrag an das Sprachmodell weiter, einschließlich Bildgenerierung, Anzeige und Speicherung. Er setzte die Standardsprache aus dem Browser zusätzlich als Schreibsprache und verwendete einen pauschalen Längenbereich. Eine Deutsch-Einstellung konnte dadurch eine ausdrückliche Englisch-Anweisung überlagern. Nach der Modellantwort speicherte das Studio den Text ohne Sprach- und Wortzahlprüfung. [Bisheriger Schreibpfad](../../packages/creative-studio/web/src/lib/studio.ts)
- Im laufenden Router ist Jinja für das Modellprofil aktiv. `/apply-template` hat beim Schreiben den eingebundenen Human Writing Skill und seine Regeln gezeigt. Der frühere Studio-Chat übergab keine Schemas für Bild- oder Speicherfunktionen und verarbeitete nur Text aus `choices[].delta.content`. Das Writing-Template lässt beim Schreiben die vorgesehenen Web-Tools nur auf ausdrücklichen Wunsch zu. Eine Textantwort kann deshalb keine Studio-Aktion bestätigen. [Writing-Template](../../config/writing/routing.jinja) · [llama.cpp-Server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

## Ausführung und Nachweis

Der Browser übergibt den normalen Chat-Auftrag an `POST /api/chat/dispatch`. Der Server erkennt Text und Bild unabhängig, legt einen persistenten Auftrag an und verknüpft ihn mit der Unterhaltung. Dieselbe Auftrags-ID kann nach einem Verbindungsabbruch erneut eingereicht werden. Sie liefert dieselbe Referenz.

1. Ein ausdrücklich genanntes Projekt hat Vorrang. Der Server verknüpft die Unterhaltung mit dem gefundenen oder neu angelegten Projekt.
2. `creative-writing` erhält einen Schreibauftrag mit der gewünschten Sprache und dem Genre. Vor jeder Generierung prüft das Studio den gerenderten llama.cpp-Prompt gegen die tatsächlich ausgewählten Skill-Referenzen.
3. Die Prüfung verwendet die deutschen und englischen Sprachmarker des Skills und zählt die Wörter des Fließtexts. „Ungefähr 350“ ergibt 315 bis 385 Wörter. Eine Abweichung löst bis zu zwei gezielte Überarbeitungen aus. Der Human Writing Audit liefert die festgestellten Stilhinweise.
4. Das Studio speichert einen akzeptierten Text und seinen Auftragsschritt in derselben SQLite-Transaktion. Ein Bildwunsch wird als persistenter Job an den lokalen Bilddienst übergeben. Die Standardeinstellung für das kreative Schreibprofil gibt im Leerlauf nach 15 Sekunden GPU-Speicher frei. Der Koordinator prüft den verfügbaren Slot vor der Übergabe.
5. Der Bildauftrag wird erst als erfolgreich angezeigt, wenn der Bilddienst die Archiv-ID bestätigt, der PNG-Header gelesen wurde und die Dimensionen den Vorgaben entsprechen. Die Projekt- und Dokumentzuordnung speichert Bild- und Job-IDs. Varianten übernehmen im selben Chat das Ausgangsbild, seine Einstellungen und die Dokumentzuordnung und lassen einen neuen Seed bestimmen. [Studio-API des Bilddienstes](https://github.com/dcschmid/local-image-ai-service/blob/main/docs/api.md)

`GET /api/chat/tasks/<id>` zeigt den Zustand jeder Teilaufgabe. Die Schreibdiagnose enthält Modellprofil, Skill-Version, Hashes der nachgewiesenen Referenzen, gezählte Wörter, erkannte Sprache und die echten Stilbefunde. Das Bildarchiv hält das PNG und die Generierungsmetadaten. Im Chat steht die Bildreferenz.

## Wiederholbare Prüfung

```sh
python3 tests/creative-studio-plan.py
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:8707/ node tests/creative-studio-workflow.mjs
```

Die Browserprüfung erwartet Playwright mit Firefox und ein [isoliertes Studio](README.md#tests). Setze nach dem Neustart des Test-Studios `CREATIVE_STUDIO_TEST_REOPEN` auf den ausgegebenen Chat-Pfad, um denselben Auftrag und dasselbe Bild zu prüfen.

Der reale Regressionstest speicherte unter „Das letzte Licht“ eine englische Szene mit 340 Wörtern. Der Human Writing Skill meldete einen Stilbefund. Firefox dekodierte das archivierte PNG mit 1024 × 576 Pixeln im selben Chat. Nach dem Neustart stimmten Dokument- und Bild-IDs weiterhin mit dem ursprünglichen Auftrag überein.
