# Migration zu Ordnern und Chats

SQLite v5 ergänzt aktive Chat-Kontexte und eine Zuordnungstabelle für bestehende und künftige Kontexte. Projekte bleiben als interne Speicherobjekte erhalten. Der Dienst erstellt vor dem Schemawechsel eine konsistente SQLite-Sicherung mit dem Namen `studio-before-v5-*.sqlite3`.

- Bestehende Chat-, Ordner-, Projekt-, Kapitel-, Dokument- und Bild-IDs bleiben gültig. Die bisherige Zuordnung eines Chats wird per ID übernommen. Titelähnlichkeit führt zu keiner Zusammenführung.
- Ein sichtbarer Altbestand ohne Chat erhält einen Chat unter seinem bisherigen Ordner. Gelöschte und archivierte Bestände behalten ihren Status. Der Papierkorb unterscheidet frühere Chat- und Inhaltslöschungen weiterhin.
- Ein Kapitel wird über seine gespeicherte Nummer innerhalb des aktiven Story-Kontexts gefunden. Eindeutige alte Kapitel mit einem Titel wie „Kapitel 3“ können beim ersten Zugriff als nummeriertes Kapitel übernommen werden. Bei mehreren möglichen Zielen erhält der Chat eine Auswahl.
- Neue Chatinhalte bekommen bei Bedarf einen internen Kontext. Ein bewusst als neu bezeichneter Roman im selben Chat erhält einen eigenen Kontext. Der aktive Kontext kann über **Inhalte** gewechselt werden.
- Dokumente, Versionen, Story-Bibel, Prüfläufe, Bildreferenzen und Originalstandorte bleiben gespeichert. Die Migration wird über die Schemaversion einmalig und transaktional ausgeführt.

Nach der Migration werden die bisherigen Beziehungen stichprobenartig gegenüber der Sicherung geprüft. Schreibende Tests laufen im vorhandenen aktiven Chat „The Missing Sundays“. „Das letzte Licht“ wird in seinem vorhandenen Archiv- oder Papierkorbstatus geprüft. Ein Testbestand deckt das Wiederherstellen und Löschen ab.
