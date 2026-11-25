# Creative Studio – Story-Planung im Chat

Die bisherige Absichtserkennung wählte die Kapitelredaktion, sobald ein Prüf- oder Überarbeitungsverb und eine Kapitelnummer zusammentrafen. Der Abgleich mit dem vorhandenen Kapiteltext kam erst danach. Eine Anfrage über die Handlung von Kapitel 4 konnte deshalb bei der Textredaktion landen, obwohl im Chat bereits eine vollständige Planung vorlag.

## Umsetzung

- `libexec/creative_studio_chat.py` unterscheidet Arbeitsabsicht und Ziel der Anfrage. Die Auswahl berücksichtigt Planungsdaten, Kapiteltext, den aktiven Story-Kontext und ausdrückliche Textziele wie Grammatik oder geschriebene Fassungen.
- `libexec/llama-creative-studio` löst den aktuellen Chat und die gemeinte Kapitelnummer vor der Werkzeugwahl auf. Freie Antworten können den normalen Chatpfad verwenden. Bei einer ausdrücklich angefragten Textprüfung für ein geplantes Kapitel bietet der Chat an, das Kapitel zu schreiben.
- `libexec/creative_studio_production.py` prüft Planung, Story-Bibel und Kapitelübersicht gemeinsam über die konfigurierbare Rolle `planning-audit`. Ohne eigenen Eintrag erbt die Rolle `audit` und bevorzugt in der Standardkonfiguration das lokale Research-Profil. Befunde im Prüfbericht brauchen ein wörtliches Zitat, eine Begründung und eine Korrektur. Liegt die Planung nur im Chat, lässt sie sich dort prüfen und ausdrücklich als Entwurf übernehmen.
- Entwürfe besitzen eigene Versionen. Die Freigabe berücksichtigt die gespeicherten Textversionen und erfordert eine Bestätigung vorhandener Auswirkungen. Ein laufender oder pausierter Manuskriptjob behält seine freigegebene Planversion. Eine explizite Übernahme beim Fortsetzen ist für freigegebene Änderungen an unverfassten Kapiteln nach dem aktuellen Checkpoint möglich. Änderungen an begonnener Handlung oder übergreifender Planung erfordern einen eigenen Abgleich mit dem Manuskript.
- `production.ts`, `studio.ts` und `studio-ui.ts` zeigen Ergebnisse, Belege, Planstatus und Entwürfe im bestehenden Chat und Planungsdialog an. Die vorhandenen Tabellen und IDs werden weiterverwendet.

## Verifikation

- Python-Suiten für Chat, Produktionsjob, Planvalidierung, Story und Organizer.
- Firefox und HTTP für die Fälle A bis F, Entwurfsübernahme aus einem reinen Chat und die Rückkehr zum allgemeinen Chat. Die Modellantworten in dieser Suite sind reproduzierbare Fixtures. Die vorhandene Firefox-Suite deckt zusätzlich Manuskriptansicht, Kapitelbild und ZIP-Export ab.
- TypeScript und Astro-Build. Semgrep prüfte sechs Quelldateien. Die beiden Treffer lagen in bestehenden Funktionen. Die Sortierrichtung der Chats stammt aus zwei festen Werten. Der zweite Treffer betrifft das Wiederherstellen von TAR-Backups und liegt außerhalb des Planungswegs.

- Alle 30 Python-Tests in den fünf Suiten bestanden. Die Firefox-Suite zur Planung bestand alle Fälle A bis F. Die separate Firefox-Produktionssuite bestand ebenfalls.
- Der reguläre Dienst wurde am 25. November 2026 gegen 07:18 CET neu gestartet. Port 8700 lieferte den neuen Web-Build und einen erfolgreichen Healthcheck. Die Datenbank blieb auf Schema 6 und bestand den Integritätstest. Die Zeilenzahlen aller geprüften Inhaltstabellen und Jobtabellen stimmten vor und nach dem Neustart überein.

## The Weight of Three Keys

Der vorgegebene Prüfauftrag wurde per HTTP im vorhandenen Abnahmechat übergeben. Der Auftrag enthält die acht Kapitelpläne der bestehenden Planversion. Die Redaktion des Manuskripts bleibt pausiert. Der Abgleich mit dem vorherigen SQLite-Backup bestätigt dieselben Kapitel, Bilder, gespeicherten Planversionen und denselben Manuskript-Checkpoint.

Beim Abschluss der Softwaretests belegte ein separater 256K-Kontextbenchmark den Modellslot. Der gespeicherte Audit wartet und wird durch den Studio-Worker ohne zusätzlichen HTTP-Port weitergeführt. `output/story-production-acceptance/planning-audit.json` enthält den aktuellen Stand. Konkrete Modellbefunde und eine daraus abgeleitete Entwurfsfassung stehen bis zum Abschluss der Inferenz aus.
