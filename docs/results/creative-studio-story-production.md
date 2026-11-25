# Implementierungsbericht zur Story-Produktion

Die Änderungen liegen in den lokalen Checkouts von `localllma-setup`, `skillset` und `local-image-ai-service`. Der echte Produktionslauf verwendet ein separates Creative Studio auf Port 18700 und eine eigene SQLite-Datenbank. Die installierten llama.cpp- und Image-Service-Dienste stellen die Inferenz bereit. [Studio-Verwendung und Rollen](../creative-studio/STORY_PRODUCTION.md)

## Umsetzung

| Phase | Ergebnis |
| --- | --- |
| A – Bestandsaufnahme | Bestehende Story-Dokumente, Versionen, Chat-Kontexte, SQLite-Jobs, GPU-Koordination und lokale Bild-API als Grundlage übernommen. |
| B – Human Writing | Version 1.1.0 mit Regeln für Langform, Offline-Prüfung, Belegvalidierung und Regressionstests. |
| C – Planung | Planvorschlag mit strukturierten Figuren-, Zeit-, Orts- und Wissenseinträgen, Visual Bible, Kapitelübersicht, Versionshistorie und Freigabe. Auswirkungen späterer Planänderungen werden an existierenden Texten geprüft. |
| D – Kapitel | Geplante Szenen mit Wortzielen, gespeicherte Entwürfe, sprachliche und redaktionelle Audits, Kontinuitätsprüfung und bis zu zwei gezielte Korrekturversuche. Offene Blocker halten den Job an. |
| E – Bilder | Kapitelzitate als Motivbelege, lokale Bildjobs, wiederverwendbare Seeds, Archivzuordnungen, Bildvarianten und gemeinsame Sichtprüfung. |
| F – Produktion | Automatik und gemeinsame Arbeit mit Fortschritt, Pause, Fortsetzen, Abbruch, Wiederholung und Checkpoints. |
| G – Manuskript | Gesamtprüfung, Lesemodus mit Kapitelnavigation, Markdown, MDX und ZIP mit Bildern. |
| H – Modellprüfung | Gemory Q4_K_M hat den englischen ersten Plan mit der Human-Writing-Version 1.1.0 erzeugt. Gemory und Gemma 4 QAT stehen im Router zur Verfügung. Der Deutsch-/Englisch-Qualitätsvergleich ist noch offen. |

## Human Writing 1.1.0

Der neue Offline-Audit meldet längere Textwiederholungen innerhalb eines Kapitels und im Manuskript, kurze sprachliche Echos, gehäufte rhetorische Kontraste sowie überprüfbare Zeit- und Kleidungshinweise. Er belegt sie mit Kapitel, Zeile, Zeichenbereich und Originalzitat. Absichtliche Leitmotive sind geschützt. Das Modell prüft Handlung, Dialog, Pacing, Figurenwissen und erzählerische Wirkung mit Belegen. Die vorhandenen Befehle für Artikel, Webseiten und Projekte bleiben aufrufbar.

Der Offline-Test auf Kapitel 1 von *The Missing Sundays* ergab neun Befunde. Dazu zählen eine wiederkehrende Beschreibung der Sorgfalt, gehäufte Kontrastformeln, der Zeitsprung am Vormittag und die widersprüchlich beschriebene Kleidung. Die Belege wurden am Originaltext abgeglichen. Ursache und Absicht benötigen den semantischen Review. Getestet wurde auf einem temporären Export der vorhandenen Fassung.

## Technische Abnahme

| Prüfung | Ergebnis |
| --- | --- |
| Python-Produktionstests | 6 bestanden. Enthalten sind beide Produktionsmodi, Neustart mit Checkpoint, ungelöster Blocker, Bildvariante und acht Kapitel mit zusammen neun simulierten Bildjobs. |
| Bestehende Studio-Suites | Story 2, Chat 4, Planung 7 und Organizer 7 bestanden. Der API-Smoke-Test lieferte 13 erfolgreiche Prüfungen. |
| Human-Writing-Suites | Bestehende Linter-, Projekt- und Website-Tests bestanden. Drei Langformtests einschließlich des echten lokalen Regressionstexts bestanden mit bereitgestellter Fixture. |
| Image-Service | 20 Tests bestanden, einschließlich wiederholter Einreichung mit derselben ID und Wiederherstellung eines bereits archivierten Bildes. |
| Firefox | Planung, Freigabe, Chat-Illustration, Vergrößerung, Lesemodus und ZIP-Download mit simulierten Modell- und Bildantworten bestanden. |
| Astro | Studio-Build und TypeScript-Check bestanden. Der exportierte Fixture-MDX-Text wurde separat mit Astro 5.18.2 und dessen MDX-Integration gebaut. Beide eingebetteten Bilder wurden aufgelöst. |
| Datenbestand | Schema 5 auf 6 auf einer konsistenten Kopie des aktiven SQLite-Bestands migriert. Integrität und Fremdschlüssel geprüft. IDs, Inhalte, Versionen und Status der 21 Dokumente aus *The Missing Sundays* und *Das letzte Licht* abgeglichen. |
| Echte Dienstvorprüfung | Der Router hat die aktuellen Human-Writing-Referenzen in Deutsch und Englisch nachweislich in die Prompts übernommen. Der Image-Service hat beide geplanten Bildformate mit Z-Image Turbo und festem Seed akzeptiert. Die Endpunkte haben in dieser Probe keinen Text und kein Bild generiert. |
| Semgrep | Die Prüfung der geänderten Python-Pfade meldete einen Treffer an einem vorhandenen Linter-Aufruf. Der Aufruf übergibt ein festes Skript per Argumentliste, ohne Shell. Der Sprachparameter wird aus `en`, `de` und `auto` bestimmt. |

Der API-Smoke-Test verwendete zunächst die installierte Instanz und legte dort eigene Testdaten an. Das Testprojekt wurde in den Papierkorb verschoben und sein noch wartender Bildjob abgebrochen. Der zugehörige Recherchetest endete mit einem Timeout. Der Wiederholungstest in der isolierten Instanz bestand alle 13 Prüfungen.

## Echter Abnahmelauf

Gemory hat den ersten Plan für *The Weight of Three Keys* lokal erzeugt. Er zog die Auflösung zu weit vor. Die redaktionell überarbeitete Fassung trennt Entdeckung, Beweis, öffentliche Korrektur und Nachwirkung und ergänzt Zeitpunkte und Kleidung. Der erste Vorschlag liegt als Version 1 vor. Version 2 wurde für die Abnahme freigegeben.

Der laufende Produktionsauftrag hat acht Kapitel mit jeweils 1.000–1.500 englischen Wörtern und neun Illustrationen zum Ziel. Ein weiterer lokaler Inferenzlauf belegt den gemeinsamen Slot. Der Produktionsauftrag wartet deshalb vor der ersten Szene. Der Dienst und der Abnahmewächter protokollieren den Arbeitsstand unter `output/story-production-acceptance`. Dort liegen außerdem die beiden Planfassungen, die tatsächliche Modellprovenienz und der Offline-Bericht zu *The Missing Sundays*.

Der vollständige Lauf mit echten Kapiteln, Bildmotiven, formaler Sichtprüfung, exportiertem Gesamtmanuskript und dem zweisprachigen Modellvergleich steht noch aus. Die nachfolgende Übersicht im Abnahmeordner aktualisiert sich mit dem laufenden Job.

## Grenzen

Die Plan- und Textprüfung arbeitet mit belegten Modellbefunden und ersetzt keine redaktionelle Abnahme. Bei den verfügbaren Textprofilen prüft der lokale Bilddienst das Dateiformat. Die Übereinstimmung von Motiv und Figur mit der Handlung wird gesammelt zur Sichtprüfung vorgelegt. Die Story-Bibel und abgestimmte Prompts unterstützen eine einheitliche Bildsprache. Die Ähnlichkeit wiederkehrender Figuren lässt sich über unterschiedliche Szenen hinweg nicht garantieren.

Ein älterer Image-Service unterstützt nur die Wiederzuordnung aus der Jobliste. Für idempotente Wiederholung derselben Anfrage muss der aktualisierte Image-Service laufen. Bei unklarer Zuordnung hält der Auftrag an.

Die Installation auf Port 8700 bleibt beim zuvor laufenden Build. Der neue Build und der Abnahmelauf sind auf Port 18700 erreichbar.
