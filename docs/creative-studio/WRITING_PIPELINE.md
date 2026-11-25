# Modulare Schreibpipeline im Creative Studio

## Ausgangslage und Git

Das Studio-Checkout unter `~/dev/github/localllma-setup` zeigt auf `dcschmid/localllama-setup`. Sein Arbeitsbaum enthielt bereits die neue Chat-, Editor- und Story-Produktion sowie weitere gestagte und ungestagte Arbeiten. Das Skillset unter `~/dev/github/skillset` zeigt auf `dcschmid/skillset`. Es enthielt Human Writing 1.2.0 mit einer Langform-Fiction-Referenz, CLI und Tests. Der Image-Service unter `~/dev/github/local-image-ai-service` zeigt auf `dcschmid/local-image-ai-service` und wurde über seine vorhandene API verwendet.

Beide Repositories haben einen lokalen Branch `editorial-pipeline`. Der jeweils erste Snapshot-Commit enthält den vorgefundenen Stand der betroffenen Dateien. Darauf folgen die Implementierungs- und Prüfcommits. Die ursprünglichen Git-Indizes blieben bytegleich. Es gab keinen Push und keine destruktive Migration. Der Live-Test läuft mit einer separaten SQLite-Datenbank und eigenem Konfigurationsordner. Die Ausgangsdiffs liegen unter `/tmp/editorial-baseline.3TaiDW`. Die vorherige generierte Router-Vorlage liegt als Kopie im Verzeichnis des Live-Tests.

| Repository | Arbeitscommit | Basis-Snapshot |
| --- | --- | --- |
| Skillset | `c871610` | `321aa93` |
| Studio | `9e861fb` | `15dad1b` |

## Skills und Integrationspunkte

| Skill | Version | Verantwortung |
| --- | --- | --- |
| `human-writing` | 1.3.0 | Sprachqualität in Deutsch und Englisch, Voice Calibration und Fidelity. Bestehende Website-, Projekt- und Langform-Werkzeuge bleiben erreichbar. |
| `story-writing` | 1.0.0 | Handlungsbogen, Figuren, Story-Bibel, Kapitel, Kontinuität, Dialog und redaktionelle Beurteilung. |
| `article-writing` | 1.0.0 | Artikelplanung, Quellenarbeit, fachliche und journalistische Prüfung sowie Publishing. |

Die beiden Fachskills haben eigene Metadaten, Referenzen und Tests. Sie bleiben in beliebigen Agenten einsetzbar. Die gemeinsamen Sprachregeln liegen in Human Writing.

- `libexec/creative_studio_chat.py` und `creative_studio_plan.py` wählen anhand des Auftrags den bestehenden Ablauf. „Schreibe eine Mystery-Geschichte mit acht Kapiteln“ startet eine freigabepflichtige Planung. Ein recherchierter Artikel bleibt ein Artikelauftrag, auch wenn das Thema „die Geschichte von …“ lautet.
- `libexec/creative_studio_skills.py` wählt Skill und Referenzen nach Artefakt, Phase und Sprache. Sprachprüfungen laden Human Writing. Kontinuitätsprüfungen laden Story Writing. Faktenprüfungen laden Article Writing. Generierung und Überarbeitung kombinieren jeweils die Fachregeln mit Human Writing.
- `config/writing/render.py`, `routing.jinja` und `libexec/llama-creative-studio` erhalten das Router-Template für bestehende Aufrufer. Das Studio prüft die Systemsektion des gerenderten Prompts, ergänzt fehlende Regeln und erfasst nur belegte Regeltexte mit Version und SHA-256. Die Produktionsaufrufe verwenden die tatsächliche Router-Tokenisierung und das Ausgabelimit des Alias.
- `libexec/creative_studio_production.py` bewahrt Story-Plan, Kapitel- und Bildjobs. Neue Planentwürfe erfassen die Zielgruppe und strukturierte Gegenstandsmerkmale. Kapitelbilder verwenden standardmäßig `1024x576`. Der vorhandene Bilddienst verarbeitet Modell, Preset und Stil aus der freigegebenen Planung.
- `libexec/creative_studio_article.py` und der Studio-Job führen Artikelplanung, Quellenaufnahme, Texterstellung, Sprachprüfung, Faktenprüfung und Publishing-Prüfung aus. Deep Research liefert gespeicherte Quellenauszüge. Ein manuelles Dossier kann eine Markdown-Quellenverlinkung mit dem darauffolgenden Blockzitat enthalten. Das Studio übernimmt den tatsächlichen Seitenauszug aus dem MCP-Feld `chunk`. Treffer-Snippets und Dossier-Zusammenfassungen zählen als Recherchehinweise.
- `packages/creative-studio/web/src/lib/production.ts` und `studio.ts` zeigen Fortschritt und Korrekturanzahl im Chat. Geladene Skill-Versionen und belegte Fundstellen stehen unter **Prüfdetails**.
- `tests/creative-studio-writing.py`, `creative-studio-production.py` und `creative-studio-real-articles.py` prüfen Routing, Persistenz, Korrekturen, Faktenbelege und Export. Die ursprünglichen Browser-Tests und Skill-CLIs sind weiterhin nutzbar.

## Automatische Korrekturen

Die Story-Produktion speichert zuerst den Entwurf. Sprachprüfung und Story-Prüfung protokollieren exakte Textstellen. Ein möglicher Handlungswiderspruch benötigt zusätzlich die widersprechende Plan- oder Kanonstelle und eine zweite Prüfung. Rein redaktionelle Vorschläge und unbestätigte Funde bleiben im Prüfverlauf. Festgestellte Rechtschreib-, Grammatik- und Kontinuitätsfehler sind Kandidaten für eine lokale Korrektur. Eine Änderung an einer geschützten Mengenangabe in einer Story braucht einen exakten Beleg im freigegebenen Kanon.

`libexec/creative_studio_correction.py` prüft Hash, Ausgangsversion im Job, Textspanne, Überlappungen und Satzgrenzen. Es schützt Metadaten, Code, Markdown-Elemente, Zitate, Zahlen und bekannte Namen. Es weist neue mechanisch erkennbare Duplikate zurück. Modell-Patches für Stories erhalten außerdem eine Prüfung auf unbeabsichtigte Änderungen an Handlung und Perspektive. Die Pipeline prüft die Kandidaten erneut und übernimmt eine bessere Fassung in einer Transaktion. Pro Dokumentversion versucht sie höchstens zwei automatische Korrekturdurchläufe. Das ursprüngliche Kapitel bleibt im Versionsverlauf. Ein manuell bearbeitetes oder freigegebenes Kapitel überschreibt der Job nicht. Ein ungelöster bestätigter Story-Blocker pausiert vor der Illustration.

Artikelstellen werden nur sprachlich verändert. Eine belegte Behauptung benötigt eine exakte Artikelstelle, einen verfügbaren Quellenauszug und eine zweite Bewertung, ob die Quelle die Aussage tatsächlich trägt. Persönliche Erfahrung ist an das vom Autor bereitgestellte Material gebunden. Fehlt der Beleg, bleibt der Artikel als Entwurf markiert und die Stelle erscheint im Prüfbefund. Die Publishing-Prüfung kontrolliert Abschluss von Frontmatter und Codeblöcken und parst Python-Beispiele mit `ast`. Markdown- und MDX-Export bewahren vorhandenes Frontmatter, relative Links und Bildpfade. Bei eingebetteten Studio-Bildern bündelt der Export die PNGs und passt nur die zugehörigen Bildverweise an.

## Lokale Modelle und Abnahme

Der Router hat `creative-writing` mit `Gemory-26B-A4B-Q4_K_M.gguf` und `research` beziehungsweise `deep-research` mit `Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf` gemeldet. Die Rollen lassen sich in `story-model-roles.json` hinterlegen. Die Abnahme besitzt eine eigene Datei. Der gemeldete Kontext betrug 262.144 Token bei einem Slot, das Ausgabelimit 8.192 Token. Bei der echten englischen Planung lagen drei gemessene Eingaben bei 3.097, 4.200 und 4.451 Token. Der Image-Service meldete sich als bereit und führte `1024x576` im Formatkatalog.

| Prüfung | Ergebnis |
| --- | --- |
| Human Writing DE/EN | Linter-, Website- und Project-Tests bestanden. Langform-Audit fünf Tests bestanden, ein lokaler Manuskript-Fall ohne Fixture übersprungen. |
| Story DE | Regressionstests sichern Satzanschluss, falsches Gegenstandsmerkmal und unplausible Orts-/Zeitfolge ab. Der echte Gemory-Smoke-Test lieferte eine deutsche Szene mit einem Kasusfehler. Gemma lokalisierte die Stelle. Ein kurzer Kategoriename hielt den Befund zunächst offen. Der Regressionstest zeigt, dass eine konkrete Begründung im Korrekturfeld die unabhängige Prüfung auslösen kann. Beim erneuten Live-Aufruf meldete Gemma zu derselben Stelle keinen Befund. Die sprachliche Modellprüfung kann einzelne Fehler übersehen. |
| Story EN | Regressionstests sichern Satzanschluss, fehlerhafte Mengenangaben, Figurenwissen und Objektwechsel ab. Gemory lieferte die englische Smoke-Szene und eine echte Acht-Kapitel-Planung. Die Planprüfung fand strukturelle Widersprüche. Im isolierten Lauf wurden drei Kapitelübergänge und das Ende vor der Freigabe als neue Planversion überarbeitet. Gemma bestätigte separat den Konflikt zwischen vier sichtbaren und drei kanonischen Abzeichen mit einem zweiten Modellaufruf. |
| Artikel A · Sachartikel | Fixture mit gespeichertem Quellenbeleg, erneuter Faktenprüfung und Erhalt des ursprünglichen Entwurfs bestanden. Echter NASA-Auszug über das lokale `read_url` geladen. [NASA Apollo 11](https://www.nasa.gov/mission/apollo-11/) |
| Artikel B · Technik | Fixture mit geschütztem Frontmatter, Bildpfad, Link, Tabelle und Python-Code bestanden. Test mit absichtlich fehlendem Beleg blieb im Entwurfsstatus. Echter Auszug der offiziellen Dokumentation geladen. [Python JSON](https://docs.python.org/3/library/json.html) |
| Artikel C · Devlog | Fixture prüft die Herkunft der gelieferten persönlichen Erfahrung. Der isolierte Live-Job erzeugte 146 englische Wörter mit Gemory und prüfte die Aussagen anhand der Autorennotizen mit Gemma. Der Entwurf überstand einen Studio-Neustart. Markdown- und MDX-Export sowie die MDX-Kompilierung waren erfolgreich. |
| Skill Orchestrator | 35 Checks bestanden. Separate Story- und Article-Tests und die Prüfungen der Skillset-Installationswerkzeuge liefen erfolgreich. |
| Creative Studio | Python-Regressionen, Astro 5.18.2 Build, TypeScript und Firefox-Produktionsablauf mit Fixture-Bildern und ZIP-Download bestanden. Ein eigener Test durchlief acht kurze Fixture-Kapitel und neun Bildzuordnungen. Die technische MDX-Fixture kompilierte. Die unabhängige Gesamt-Baseline `tests/unit.sh` meldete vorher und nachher `models.tsv rows=2`. |
| Semgrep | Drei fokussierte Offline-Regeln für dynamische Ausführung und Shell-Aufrufe auf zwölf geänderten Quelltexten, 0 Treffer. |

## Offene Live-Prüfungen

Der volle englische Manuskriptlauf mit acht Kapiteln à 1.000–1.500 Wörtern und neun neu erzeugten Bildern wurde gestartet. Bereits vor dem isolierten Lauf nutzte ein produktiver Story-Job denselben Router und Bilddienst. Der Router meldete bei einem Ladevorgang HTTP 500. Sein Log nennt fehlenden CUDA-Speicher bei der Reservierung des KV-Caches. Der Testjob wurde vom gespeicherten Checkpoint erneut eingereiht. Für das vollständige Live-Manuskript, seine Wiederöffnung und die neun neuen Testbilder steht die Abnahme aus. Die Live-Artikel A und B haben echte Quellenauszüge geladen. Ihre fertigen Exporte stehen aus.

Den Status der isolierten Datenbank zeigen `/api/production/<Projekt-ID>/report` und `/api/chat/tasks/<Job-ID>`. Die laufenden Nachweise liegen in `/tmp/editorial-live.GjhWq1`. Ein SQLite-Checkpoint und der geprüfte Devlog liegen unter `output/editorial-acceptance.jQl4nK`. Die SQLite-Integritätsprüfung meldete `ok`. Der Story-Watcher erfasst abgelieferte Fassungen. Der Artikel-Watcher prüft die gespeicherten Fassungen und beide Exportformate. Neue automatische Aufträge stellen das Manuskript nach der technischen Bildprüfung zum Export bereit. Die Sichtprüfung ist danach im Chat verfügbar. Gemeinsame Produktion und bereits laufende Aufträge behalten ihren bestätigungspflichtigen Bildschritt. Unterstützte Artikel-Codebeispiele lassen sich auf Syntax prüfen. Der getrennte MDX-Compilercheck lief für die technische Fixture und den echten Devlog. Modellgenerierte Codebeispiele werden im Studio als Text behandelt. Die bestehende Begrenzung auf 150 Kapitel pro Planung gilt weiter.

```sh
python3 tests/creative-studio-writing.py
python3 tests/creative-studio-production.py
npm --prefix packages/creative-studio/web run build
python3 tests/creative-studio-real-production.py --url http://127.0.0.1:18739 --output /tmp/editorial-live.GjhWq1/story
python3 tests/creative-studio-real-articles.py --url http://127.0.0.1:18739 --manifest /tmp/editorial-live.GjhWq1/articles.json --output /tmp/editorial-live.GjhWq1/articles
```
