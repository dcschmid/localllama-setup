# Creative Studio – Wiederaufnahme der Manuskriptproduktion

## Diagnose des Jobs auf Port 8700

Untersucht wurde der reguläre Produktionsjob `709797541f074049bf109d99b2de10b6` für „The Weight of Three Keys“. Der frühere, getrennte Abnahmelauf mit derselben Geschichte hat eine andere Job-ID und einen anderen Checkpoint.

| Schritt | Nachweis zum Zeitpunkt der Unterbrechung |
| --- | --- |
| 1. Story-Planung | Freigegebene Version 1 liegt im Job-Payload. Der Job wurde am 25. November um 07:59:28 CET angelegt. |
| 2. Story-Bibel | Bestandteil des geladenen Plan-Payloads. Die Szenenvorbereitung und die Kontinuitätsprüfung verwendeten den aus Plan und Bibel vorbereiteten Kontext. |
| 3. Kapitelplan | Acht nummerierte Einträge. Der Job stand bei Kapitel 1, „Das Erbe im Schrank“. |
| 4. Kapitel erzeugen | Der Checkpoint enthält die Szenenplanung und zwei Schreibaufrufe. Die gespeicherten Szenen hatten 660 und 517 Wörter. |
| 5. Kapitel speichern | Version 2 war seit 08:08:21 CET mit 1.177 Wörtern als Entwurf gespeichert. |
| 6. Human Writing Audit | Fertiger Prüfbericht mit Human Writing 1.2.0 und Prüfschema 2. Die vier lokalen Stilhinweise waren redaktionell. |
| 7. Kontinuitätsprüfung | Der Prüfbericht enthält einen unbestätigten Kontinuitätshinweis. Er war als Hinweis klassifiziert. Kein bestätigter Blocker blieb übrig. |
| 8. Automatische Überarbeitung | Der Quality Gate ging zur Illustration weiter. Der Checkpoint enthält keinen Rewrite-Pass. |
| 9. Neuen Text prüfen | Es gab keine Rewrite-Fassung zur Nachprüfung. Der gespeicherte Text und sein Prüfbericht hatten dieselbe Version. |
| 10. Kapiteltext finalisieren | Der alte Ablauf schrieb den Kapitelabschluss erst nach dem Bild. Zum Zeitpunkt der Störung war das Kapitel noch als Entwurf gespeichert. |
| 11. Illustration anfordern | Zwei vorbereitende LLM-Aufrufe endeten um 08:15:51 und 08:18:02 CET. Danach stand der Code `production_image_evidence` im Job. Es gab weder einen gespeicherten Bildprompt noch einen Bildauftrag. |
| 12. Bild speichern | Keine Job-ID beim Bilddienst, kein Bild-Archivbeleg. |
| 13. Kapitel abschließen | Es gab keinen Kapitelabschluss im Produktionsjob. |
| 14. Kapitel 2 starten | Kapitel 2 hatte keinen Schreib-Checkpoint. |

Die gespeicherte Ausnahme `production_image_evidence` hat in diesem Pfad genau einen Auslöser. Das Schreibmodell musste einen Auszug wörtlich wiedergeben. Die Antwort scheiterte an der Prüfung auf eine exakte zusammenhängende Stelle im Kapitel. Die verworfene Modellausgabe wurde damals nicht gespeichert, daher lässt sich ihr Wortlaut nicht nachträglich rekonstruieren. Im `llama-cpp`-Journal endeten beide Modellaufrufe ohne Trunkierung. `gpu_log` enthält jeweils den passenden Acquire- und Release-Eintrag. Der Studio-Datensatz und das Journal des Bilddiensts liefern für diesen Job keinen Bild-POST. Frühere abgebrochene Aufrufe während der Neustarts erklären den finalen Fehlercode nicht.

Die Oberfläche bezeichnete den Sammelzustand `illustrating` pauschal als „Kapitelillustration wird erstellt“. In diesem Zustand lagen auch Szenenauswahl und Prompt-Erstellung vor der ersten Anfrage an den Bilddienst.

## Reparatur

- `libexec/creative_studio_production.py` speichert nach bestandener Redaktion den finalisierten Textstand samt Zusammenfassung. Die Illustration folgt als eigener Arbeitsabschnitt. Alte Checkpoints werden beim nächsten Retry aus der gespeicherten Textversion weitergeführt.
- Der Worker reicht dem Planungsmodell nummerierte Textpassagen aus der gespeicherten Fassung. Die strukturierte Antwort wählt eine Fassung per ID. Den exakten Textbeleg übernimmt und überprüft der Worker selbst.
- Die Bildphasen und ihre Ausnahmen sind getrennt sichtbar. SQLite-, Netzwerk- und Formatfehler erhalten einen technischen Fehlercode. Ausgewählte vorübergehende Fehler können pro erfolgreichem Checkpoint höchstens zweimal automatisch wiederholt werden. Gültige Archiv- und Auftrags-IDs bleiben bei einer Wiederaufnahme erhalten.
- Fehlerhafte strukturierte Rewrite-Antworten zählen als Versuch. Nach zwei Versuchen führt der geprüfte alte Text die Produktion weiter, sofern kein bestätigter Blocker verbleibt.
- `production.ts` und `studio-ui.ts` zeigen die tatsächliche Aufgabe oder Fehlerphase. Eine aufklappbare Detailansicht enthält den Code und, sofern vorhanden, die HTTP- oder SQLite-Diagnose.

Die SQLite-Sicherung wurde vor der Reparatur verifiziert. Das Schema bleibt auf Version 6. Die produktive Story und ihr Job wurden für die Regressionstests nicht als beschreibbare Vorlage verwendet.

## Nachweise

- Der isolierte Realtest „The Bell at Heron Landing“ hat mit `creative-writing` Kapitel 1 erzeugt. Ein absichtlich eingefügter Satzzeichenfehler prüfte den Reparaturpfad. Human Writing 1.2.0 erkannte ihn, ein lokaler Patch korrigierte ihn und eine erneute Modellprüfung akzeptierte die Korrektur. Die gespeicherte Fassung 4 hatte 332 Wörter.
- Bei der isolierten Bildvorbereitung wurde außerdem eine Modellantwort mit einem gültigen Szenenindex und einem 416 Zeichen langen Alternativtext beobachtet. Der frühere Grenzwert von 400 Zeichen verhinderte das Speichern eines ansonsten verwendbaren Prompts. Die Reparatur begrenzt Metadaten und kann leere Werte aus der belegten Passage oder dem Kapiteltitel ableiten.
- Der erste Bild-POST des isolierten Tests erreichte den Bilddienst. Dessen GPU-Prüfung lehnte den Start ab, obwohl der schlafende llama.cpp-Prozess nur noch 162 MiB hielt. Der alte Studio-Koordinator akzeptierte fremde Prozesse unter 1.024 MiB, der Bilddienst akzeptierte beim Modellstart keinen fremden Compute-Prozess. Der reparierte Koordinator prüft denselben Zustand. Ausschließlich für den zuletzt von Studio freigegebenen Schreibauftrag und dessen vom Router als schlafend gemeldete Instanz kann er das vorhandene Entladen des Routers aufrufen. Anschließend prüft er die GPU erneut. Der Bilddienst, der Router und ihre Profile wurden nicht neu gestartet oder installiert.
- Der isolierte Job erreichte nach dem Öffnen derselben Datenbank ein archiviertes 768×768-PNG aus Z-Image-Turbo und anschließend den Schreib-Checkpoint von Kapitel 2. Genau ein Bildjob war erfolgreich. Der erste, eindeutig fehlgeschlagene Auftrag blieb in der Historie. Die Illustration zeigt Nell, Korb und Glocke am Fährsteg. Das vor dem Test aktive Bildprofil MOSS wurde vor der Wiederaufnahme der regulären Geschichte wieder geladen.
- Die produktive Bereitstellung um 08:37 CET prüfte den Healthcheck und die Datenbankintegrität. Der ursprüngliche Job war vor dem kontrollierten Retry unverändert. Firefox überprüfte im echten Chat die Fehlerphase, verständliche Ursache und den technischen Code.
- 35 Python-Tests in fünf Suiten, zwei Firefox-Regressionsläufe sowie TypeScript und Astro-Build bestanden. Die Regressionen umfassen ungültige Szenen-IDs, die begrenzten Wiederholungen, einen fehlgeschlagenen Queue-Commit, die Wiederverwendung eines vorhandenen Bildauftrags und den Schutz aktiver bzw. fremder GPU-Prozesse. Semgrep meldete die zwei bereits bekannten Treffer in der Chat-Sortierung und in der Backup-Wiederherstellung.
- Um 08:43 CET erreichte der unveränderte Produktionsjob im regulären Studio Kapitel 2. Kapitel 1 wurde auf Basis von Version 2 und dem vorhandenen Audit abgeschlossen. Der einzige Bildauftrag archivierte ein 768×768-PNG aus MOSS. Kapiteltext, Versionshistorie, Audit, Plan und Chat stimmten mit der Sicherung überein. Die Bilddatei war über die reguläre Studio-API abrufbar. Bei der Sichtprüfung wirkt neben den vorgesehenen drei Schlüsseln ein weiterer dunkler Gegenstand wie ein zusätzlicher Schlüssel. Die Bildserie hat eine separate redaktionelle Freigabe.
- Der isolierte Test und der reguläre Job haben den Übergang von Kapitel 1 zu Kapitel 2 real durchlaufen. Die restlichen Kapitel wurden durch diesen Übergangstest nicht als abgeschlossen verifiziert.
