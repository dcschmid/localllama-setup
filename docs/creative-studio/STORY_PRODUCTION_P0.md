# P0-Reparatur der Story-Produktion

## Riff Racers: Schatten über Thunderforge

Die Untersuchung basiert auf der konsistenten SQLite-Kopie vom 25. November 2026 und dem installierten Backend, dessen Prüfsummen vor der Änderung mit `main` übereinstimmten. Die drei Checkout-Pfade wurden lokal geprüft. Ihre Remotes sind `dcschmid/localllama-setup`, `dcschmid/local-image-ai-service` und `dcschmid/skillset`. Die Sicherung der offenen Änderungen liegt unter `refs/backups/pre-story-production-p0`. Das Archiv der unversionierten Dateien und die SQLite-Sicherung liegen unter `~/.local/state/creative-studio/backups/p0-20261125/`.

| Befund | Nachweis |
| --- | --- |
| Der ursprüngliche Produktionsbrief löste den Dokumentexport aus | Um 11:32:41 speicherte die Anwendung auf den mehrzeiligen Auftrag unmittelbar „Öffne das Dokument in der Bibliothek“. Der bisherige Frontend-Intent wertete „exportieren“ und ein beliebiges Formatwort irgendwo in der Nachricht als Export. Dieser Pfad übersprang `/api/chat/dispatch`. |
| Freigabe und Fortsetzungen liefen als Modellantworten | „Ist Freigegeben“, „Mach weiter“ und die weitere Bestätigung wurden mit `meta.model=research` gespeichert. Der Chat `81fd04df8df64b8d9619884cbe878ec0` hat im untersuchten Snapshot weder Story-Kontext noch einen zugeordneten Job. |
| Die Texte existieren als Chatprosa | Separat gezählt, jeweils von der Kapitelüberschrift bis zum nächsten Abschnittstrenner, enthalten die drei Kapitel 790, 848 und 884 Wörter. Keine Kapiteldatei, kein Originalentwurf und keine Revision sind im Kapitel- oder Versionsspeicher verknüpft. Kapitel 3 enthält die im Auftrag genannten sichtbaren Schreibfehler. |
| Bilder, Prüfungen und Exporte fehlen | Für diesen Chat gibt es im Snapshot keine verknüpften Bildjobs, Auditläufe oder Produktionsartefakte. Die drei Modellantworten enthalten simulierte Bildverweise. Der letzte Verlaufseintrag enthält einen Manuskriptplatzhalter und eine technische Erfolgsbehauptung. Die Serverlogs des Zeitfensters weisen für diesen Chat keinen Produktionslauf aus. |
| Auch der echte Worker hatte eine Lücke bei den Exporten | Er setzte `completed` am Ende der Manuskript- und Bildprüfung. Der frühere `/export` erstellte Text oder ZIP erst bei einem späteren Aufruf im Arbeitsspeicher. Ein Schreibfehler auf dem Dateisystem, ein MDX-Compilerfehler oder ein defekter Download konnte den Abschluss deshalb nicht verhindern. |

Der untersuchte Chatverlauf und sämtliche Versionen, Bilder und Jobs der vorhandenen Datenbank bleiben erhalten. Das Studio kennzeichnet die überlieferten Platzhalter und meldet, dass die Kapitel dieses Chats nur als Nachrichten vorliegen. Vorhandene Spielreferenzen wurden im Checkout `../riff-racers` gefunden, darunter `docs/ui-ux-audit/evidence/weather-thunderforge.png` und die Low-Poly-Fahrzeugreferenzen. Für die alte Unterhaltung gab es keine Verknüpfung dieser Dateien mit einer Visual Bible. Lokale Referenzen lassen sich über die vorhandene Visual Bible zuordnen.

## Änderungen

- `libexec/creative_studio_chat.py`, `libexec/llama-creative-studio` und `web/src/lib/intent.ts` erkennen den Produktionsbrief sowie eindeutige Planungs-, Start- und Exportbefehle. Die Serverentscheidung verwendet den gespeicherten Story-Kontext und die freigegebene Planversion.
- `libexec/creative_studio_production.py` setzt den vorhandenen SQLite-Worker fort. Er hält für Text, Audit, Überarbeitung, Bild und Export Checkpoints, Nachweise und ein Manifest fest. Er prüft die Wortgrenzen aus dem Dokument und kann einen brauchbaren zu kurzen Entwurf mit einer belegten Szene ergänzen. Zwei automatische Revisionen pro Kapitel sind möglich. Der vorhandene Schreibmodus mit Kapitel-Freigaben bleibt wählbar.
- `libexec/creative_studio_skills.py` lädt die versionsgebundenen Anweisungen der installierten Skills. Der Abschluss verlangt nachgewiesene Human-Writing- und Story-Writing-Aufrufe sowie lokale Befunde. Korrekturen bleiben als gespeicherte Dokumentversionen nachvollziehbar.
- `libexec/creative_studio_exports.py` und `web/scripts/validate-mdx.mjs` speichern und prüfen die Originaldateien. Der Worker prüft Kapitelreihenfolge und vollständigen Text, Original-PNGs, relative Referenzen, Prüfsummen, MDX-Kompilierung und ZIP-Inhalt vor `completed`. Die GET-Endpunkte liefern geprüfte Bytes. Das SQLite-Manifest dient dem Chat und der Wiederaufnahme.
- `web/src/lib/production.ts`, `studio.ts` und `studio-ui.ts` zeigen Backend-Fortschritt, lesbare Kapitel, Bildjobs, Fehler und geprüfte Downloads. Alte `completed`-Jobs ohne Dateinachweis erscheinen als unvollständig und lassen sich am gespeicherten Stand vervollständigen.

## Prüfungen

Die Python-Regressionen in `tests/creative-studio-production.py` decken simulierte Bilder, Wortgrenzen, Audit-Nachweise, Wiederaufnahme, automatische Kapitelübergänge, Fehler am Bilddienst, Exportdateien und Manipulation eines Exports ab. Der Firefox-Test `tests/creative-studio-production.mjs` prüft den Chat mit echten Dateinhalten an den lokalen Fixture-Endpunkten und einen erfundenen Download-Link. Die allgemeine Installer-Suite meldete bereits vor den Änderungen `FAIL models.tsv rows=2`.

## Nachtrag: Teilakzeptanz bei der automatischen Korrektur (25. November 2026, Abnahmelauf „Die Lampe am Salzsteg“)

Der echte Dreikapitel-Lauf (Deutsch, 900–1.200 Wörter, Anima Aesthetic, 16:9) hielt bei Kapitel 3 mit `pause_reason=blocker` an. Der gespeicherte Prüfstand belegt den Grund: Der Text enthielt den bestätigten Sprachbruch „because he wanted to be there“ sowie drei weitere bestätigte Grammatikbefunde. Beide zulässigen Korrekturdurchläufe liefen, wurden aber mit `production_patch_regression` verworfen. Das Nachspielen der gespeicherten Edits auf Version 3 zeigt die Ursache. Drei der vier Edits bestehen die Patchprüfung einzeln. Der erste Edit setzte im Feld `after` den Folgesatz „Er wollte helfen, …“ ein zweites Mal ein, was die Wiederholungsprüfung zu Recht ablehnt. `patch_text` verwarf deshalb den gesamten Kandidaten, und der zweite Versuch wiederholte denselben Edit, weil er die Ablehnung nicht kannte.

- `patch_text_partial` in `libexec/creative_studio_correction.py` prüft jeden Edit der Reihe nach zusammen mit den bereits angenommenen. Gültige Edits bleiben erhalten, unsichere werden mit Fehlercode unter `rejected_edits` im Patchnachweis gespeichert. Die Sicherheitsregeln von `patch_text` bleiben unverändert. Ohne einen gültigen Edit ändert sich der Text nicht.
- `improve` in `libexec/creative_studio_production.py` nutzt diese Funktion für Modell-Patches. Die Treuprüfung bezieht sich nur auf die angenommenen Edits. Der nächste Versuch bekommt die noch zutreffenden abgelehnten Edits mit Grund im Prompt, damit er sie nicht wiederholt.
- `optional_language` erkennt zusätzlich die Selbsteinschätzung „eher eine stilistische Entscheidung“. Ein Befund, den der Prüfer selbst als Stilfrage beschreibt, hält die Produktion nicht an.
- Die Tests `test_one_unsafe_model_edit_keeps_the_other_verified_corrections` und `test_verifier_stating_a_style_choice_does_not_block_as_a_language_defect` in `tests/creative-studio-production.py` bilden den Fall mit dem gespeicherten Wortlaut nach.

Die Wiederaufnahme lief über die bestehende Aktion **Erneut versuchen** am pausierten Kapitelschritt. Sie archiviert die verbrauchten Durchläufe in `revision_batches` und setzt kein Kapitel zurück.

Die zweite Ursache zeigte sich im Prüfstand von Version 5. Ein früher bestätigter Sprachbefund wird über Revisionen hinweg übernommen, wenn der Prüfer ihn im neuen Text nicht erneut beobachtet (`e4ac232`). Die Suche nach dem Zitat war eine einfache Teilstring-Suche. Das Zitat „was ihre Ankunft bestätigt“ ist ein Wortanfang von „… bestätigte“ und hielt den bereits korrigierten Befund am Leben. Der zweite Korrekturversuch wurde danach an der Wortgrenze abgelehnt.

- `intact_span` übernimmt einen Befund nur noch, wenn sein Zitat an Wortgrenzen unverändert im Text steht.
- **Erneut versuchen** prüft das gespeicherte Kapitel erneut, wenn ein gespeicherter Sprachbefund nicht mehr im Text steht. Der alte Prüfstand bleibt als `quality_history` mit `stale_defects` erhalten.
- `declared_edits` übernimmt eine im Befund genannte, exakte und eindeutige Ersetzung („ersetze „A“ durch „B““) als minimalen Edit. Er durchläuft dieselbe Patch-, Treue- und Wiederholungsprüfung wie jeder Modell-Edit. Fehlt eine solche Angabe, fragt das Studio das Modell.

## Abnahmelauf „Die Lampe am Salzsteg“

Der Lauf verwendete eine isolierte Studio-Instanz auf Port 18711 mit dem lokalen llama.cpp-Router (Gemory 26B Q4_K_M, Alias `creative-writing`) und dem Local Image AI Service (`anima`, Rezept `anima-film`, 1024 × 576). Die Planung wurde einmal freigegeben, danach startete **Geschichte vollständig erstellen**. Belege: `docs/results/creative-studio-p0-e2e-acceptance.json`.

| Prüfpunkt | Ergebnis |
| --- | --- |
| Status | `completed`, 3 / 3 Kapitel, 4 / 4 geprüfte Bilder |
| Wortzahlen aus dem gespeicherten Text | 975, 945 und 1.015 Wörter bei 900–1.200 verlangten |
| Prüfungen je Kapitel | `human-writing` 1.3.0 und `story-writing` 1.0.0 mit Audit-ID, lokaler `fiction_audit` aus Human Writing 1.3.0 |
| Korrekturen | Kapitel 2 Version 3, Kapitel 3 Version 5. Der Sprachbruch „because he wanted to be there“ wurde durch „weil er dabei sein wollte“ ersetzt, „bestätigt“ durch „bestätigte“. Der Text enthält den Sprachbruch nicht mehr |
| Bilder | Titelbild und drei Kapitelbilder, gültige PNG-Dateien mit 1024 × 576, im Chat mit natürlicher Größe geladen |
| Export | `manuscript.md` (20.254 Byte), `manuscript.mdx` (20.303 Byte), `manuscript.zip` (3.188.333 Byte), MDX-Compiler, ZIP-Prüfung und Dateiintegrität bestanden. Alle drei Downloads lieferten im Chat HTTP 200 mit den Bytes der Dateien |
| Platzhalter | Weder `Simuliert`, `würde hier` noch `example.invalid` in Markdown oder MDX |

Grenzen: Der Lauf brauchte sechs Aktionen **Erneut versuchen**. Kapitel 2 und 3 hielten wegen `story_length_failed` an, und Kapitel 3 viermal wegen bestätigter Sprachbefunde. Die Kapitelübergänge, Bildaufträge, Zusammenstellung und der Export liefen ohne Befehle. Die beiden letzten Blockerklassen sind erst in diesem Lauf behoben worden. Ein vollständiger Lauf ohne Wiederholungen steht deshalb noch aus. Die Bilder zeigen die passenden Szenen. Gesichter und Hände wirken im Anima-Malstil teils verzerrt.

## Nachtrag: Freigabe im Chat startete die Planungsprüfung (25. November 2026, Chat „Thunderforge“)

Die Nachricht „Die Planung ist freigegeben. Erstelle jetzt die vollständige Geschichte mit allen Kapiteln und Illustrationen. Prüfe und korrigiere die Texte automatisch …“ löste zweimal den Auftrag „Planung prüfen“ aus (`f5a53193…`, `cc541396…`). Plan Version 2 war beim zweiten Mal bereits `approved`. Das Studio hatte kein Kapitel und keinen Produktionsauftrag angelegt.

**Ursache, belegt durch Nachspielen der gespeicherten Nachricht:**

- `chats.command()` verglich die Nachricht per `fullmatch` mit wenigen festen Sätzen. Der lange Satz ergab `None`. Von den sechs Beispielen aus dem Auftrag lieferte nur „Starte die Manuskriptproduktion.“ einen Befehl.
- `requested_action` wertete „Planung“ als Planungsziel und „Prüfe“ als Prüfauftrag und wählte `planning-audit`. „Erstelle jetzt die Geschichte“ führte allein zur Aktion `outline`.
- „Do not draft chapters.“ steht nur im Prompt der Planungsprüfung. Das Modell zitierte die Regel, weil die Freigabe dort ankam. Der Skill-Resolver lädt die Planungsregeln (`story-planning`, `story-bible`) ausschließlich in der Phase `plan`. In `generate`, `audit` und `rewrite` stehen sie nicht. Planungsregeln gelangen also nicht in die Produktion.

**Änderungen:**

- `production_command` in `libexec/creative_studio_chat.py` erkennt die Freigabe in freier Wortwahl, getrennt nach Satzteilen. Fragen, Bedingungen, Verneinungen, einzelne Kapitel und Überarbeitungen starten nichts. Ohne gespeicherte Planung passiert nichts.
- `_resolve_chat_first` wertet sie vor der Planungsprüfung aus. Ist die Planung noch ein Vorschlag, gibt das Studio genau diese Version frei und startet den Auftrag in einer Transaktion. Läuft bereits ein Auftrag, wird dessen ID zurückgegeben. Der getippte Text bleibt als Nutzernachricht erhalten.
- `stage` in `plan_info` leitet den Zustand aus Plan und Auftrag ab.
- Die Planungsprüfung behauptet bei einer Fehlleitung keine Modellgrenze mehr und verweist auf die Produktion.
- Die Weboberfläche hat im Plan-Dialog den Button **Freigeben und vollständig erstellen**.

**Prüfung:** Die echte Nachricht erzeugt auf einer Kopie der Live-Datenbank einen Produktionsauftrag für Plan Version 2 (`PRODUCTION_RUNNING`). Dafür liefen Modell- und Bilddienst nicht. Neue Tests in `tests/creative-studio-chat.py` (Tabelle der Formulierungen, End-to-End gegen einen Serverprozess) und `tests/creative-studio-production.mjs` (Firefox: Chat-Freigabe und Ein-Klick-Button).

## Nachtrag: Produktionsstopp ohne bestätigten Konflikt (25. November 2026, Chat „Schatten über Thunderforge“, Job `40cfe855…`)

Der automatische Lauf lag bei Kapitel 1 von 3 mit `pause_reason=blocker`, obwohl die Prüfdetails keinen bestätigten Handlungskonflikt enthielten. Alle Kontinuitätshinweise (Jax' Position, Schattenläufer/Schrotthiff, zweiter Riss, Kontrollpanelen, im Chaos) standen als `unconfirmed` ohne Verifikation im gespeicherten Stand; sie haben nie blockiert. Der einzige bestätigte Befund war die Grammatikstelle „Wir müssen hier raus kommen“ (`severity=automatic`). Die Oberfläche meldete zugleich „3 Textfehler automatisch korrigiert“ – die gemeldeten Korrekturen gehörten zu Version 2, die angezeigten Findings zur Version 3.

**Ursache, belegt gegen die Live-Datenbank (`documents.version=3`, Review-Hash = SHA-256 von Version 3):**

- `patch_text` in `creative_studio_correction.py` vergleicht geschützte Fakten vor und nach einem Edit. Die vom Modell korrekt vorgeschlagene Zusammenrückung „raus kommen“ → „rauskommen“ lag innerhalb einer Anführung `„…“`, die `fiction_audit.PROTECTED` als Faktspan erfasst. Der Faktenvergleich schlug fehl, der Edit fiel mit `production_patch_invalid` durch, der zweite Durchlauf verwarf die leere Patchliste. Der Fehler war nicht die Korrektur, sondern ihre Validierung.
- Danach standen die zwei erlaubten Durchläufe verbraucht (`passes=2`) am Endpunkt von `improve`. Der Gate hielt den verbliebenen bestätigten, aber nicht gelösten Grammatikbefund weiterhin für entscheidungsbedürftig, obwohl kein `blocking`-Befund existierte. Der Retry-Knopf bot bereits „Sprachkorrektur erneut versuchen“ an – dieselbe Lage stoppte ohne Nutzereingriff und verlangte trotzdem eine Entscheidung.
- Ein getragener Befund, dessen Zitat im gespeicherten Text nicht mehr steht (hier die bereits geschriebene Zusammenrückung), blieb als Blocking-Fund sichtbar. Das ist derselbe Defekt wie bei `e4ac232`, nur am Ende des Ablaufs statt beim Retry.

**Änderungen:**

- `patch_text` lässt die bestimmte Leerzeichen-Kürzung eines bestätigten Befehls durch, wenn Menge, Namen und geschützte Fakten unverändert bleiben und nur Leerzeichen die beiden Schreibweisen trennen. Alle übrigen Sicherheitsregeln, besonders Zahlen, Namen und Tatsachen in Fakten-Editen, bleiben unverändert.
- Der Endpunkt in `improve` synchronisiert vor der Entscheidung: Ein getragener Sprachbefund, dessen Zitat nicht mehr im Text steht, wandert mit `stale_defects` in `quality_history`, der Prüfschritt holt die Version neu. Nur ein im Text belegter, bestätigter Befund hält weiter an.
- Die Weboberfläche unterscheidet: „Ein bestätigter Konflikt braucht eine Entscheidung“ erscheint nur, wenn weder Sprach-Wiederholung noch Neuprüfung ansteht. Bei Sprachfehlern steht „Ein bestätigter Sprachfehler lässt sich automatisch korrigieren. Die Produktion wird danach fortgesetzt.“

**Prüfungen:** `tests/creative-studio-production.py` ergänzt je einen Fall für die Anführungs-Kürzung, unbestätigte Hinweise, getragenen behobenen Befund, verbrauchte Runden mit Repair und den echten Konflikt (43 Python-Fälle plus 8 Chat-Fälle grün). Der Live-Job wurde nach Backup (`~/.local/state/creative-studio/backups/creative-studio-20261125T184926.tar.gz`) mit neuem `revision_batches`-Eintrag neu eingereiht und nicht gelöscht.

## Nachtrag: „Story-Planung fehlgeschlagen“ ohne Ursache (25. November 2026, Chat „Schatten über Thunderforge“)

Der Planungsjob `ded21870…` endete mit `story_input_invalid`, dem Schritt `planning` und dem Detail `{"exception": "OrganizerError"}`. Die Oberfläche zeigte nur den allgemeinen Satz „Der Schritt konnte nicht abgeschlossen werden“.

**Ursache, belegt durch Nachspielen der gespeicherten Gliederung in `validate_plan`:**

- Das Modell (`creative-writing`, Gemory 26B Q4_K_M, `human-writing` 1.3.0 und `story-writing` 1.0.0) hat die Gliederung vollständig und als gültiges JSON geliefert. Alle drei Kapitel, die Bibel-Einträge und die Bildideen waren vorhanden. Es gab kein Zeitlimit, keine abgeschnittene Antwort und keinen Datenbankfehler.
- In der Story-Bibel standen `characters`, `world`, `locations` und `chronology` als leere Strings. `validate_plan` verlangt diese Felder nicht leer. Das Schema für die Modellantwort erlaubte leere Strings. Die Regel stand nur im Validator.
- `story.clean` löste dafür einen allgemeinen `story_input_invalid` aus, ohne Feld. Das Studio protokollierte nur den Ausnahmetyp und hielt den Fehler für nicht wiederholbar.
- Die Skill-Dateien sind unauffällig: Pfade, `SKILL.md`-Metadaten, Referenzen und Prüfsummen des gespeicherten Nachweises stimmen mit den installierten Dateien überein. Der Resolver lädt für die Planung `style-<Sprache>`, `story-planning` und `story-bible`. Die Skills haben die Planung nicht beeinträchtigt.

**Änderungen:**

- Validierungsfehler nennen das Feld und den Grund (`bible.characters`, `chapters[2].beats`; leer, fehlt, zu lang, kein Text), nie den Inhalt.
- Fehlen nur die vom Validator geforderten Bibel-Felder, vervollständigt das Studio genau diese einmal aus der bereits erzeugten Planung. Es erfindet nichts: Fehlt eine Angabe, steht „Nicht festgelegt“. Alle gültigen Teile bleiben, Gliederung und Kapitel werden nicht neu erzeugt. **Schritt erneut ausführen** erlaubt diese Ergänzung ein weiteres Mal.
- Der Planungsprompt sagt, dass jedes Bibel-Feld eine eigene Zusammenfassung braucht.
- Der Job speichert den fehlgeschlagenen Schritt (`outline`, `chapters`, `validate`, `repair`, `review`, `impact`, `save`) und bei ungültigen Modellantworten die Originalantwort (bis 6.000 Zeichen) samt Modell- und Skillnachweis des fehlgeschlagenen Aufrufs in `result.diagnostics`. Dieser Bereich gehört nicht zu `public_job` und erscheint nicht in der Oberfläche. Technische Fehler werden höchstens zweimal automatisch wiederholt.
- Die Oberfläche zeigt statt des allgemeinen Satzes zum Beispiel „Story-Planung: Story-Bibel konnte nicht validiert werden – „Story-Bibel · Figuren und Beziehungen“ ist leer.“, „Modellantwort unvollständig“ oder „Speichern der Planung fehlgeschlagen“. Unter **Technische Details** stehen Fehlercode, Schritt, Feld, Job-ID, Modell, Skills und Wiederholungen. Ältere Fehlerdaten ohne Feldangabe zeigen „Story-Planung konnte nicht validiert werden“.

**Prüfung mit dem echten lokalen Modell** (isolierte Instanz auf einer Kopie der Live-Datenbank, Nachweise in `docs/results/creative-studio-planning-repair-acceptance.json`):

- Der fehlgeschlagene Job wurde mit **Schritt erneut ausführen** fortgesetzt. Er blieb derselbe Job und erzeugte eine Planversion. Das Modell wurde zweimal neu gefragt: für die vier Bibel-Felder und für die Gesamtprüfung. Gliederung und Kapitel wurden nicht erneut erzeugt. Die ergänzten Angaben stammen aus den gespeicherten Figuren, Schauplätzen und der Zeitleiste.
- Eine neue deutsche Planung mit drei Kapiteln zu je 900–1.200 Wörtern lief in 276 Sekunden ohne Wiederholung bis `PLAN_READY`. Die Freigabe führte zu `PLAN_APPROVED`.
- Die Kapitelüberschriften dieser Planung heißen nur „Kapitel 1“ bis „Kapitel 3“. Das ist eine inhaltliche Schwäche des Modells und kein Fehler im Ablauf.

Die neuen Python-Tests (`PlanningTests` in `tests/creative-studio-production.py`) decken deutsche und englische Planung, die Skill-Auflösung, die Feldfehler, die Ergänzung, die Wiederaufnahme eines gespeicherten Fehlerstands, ungültige und abgeschnittene Modellantworten, das Zeitlimit und einen fehlgeschlagenen Speichervorgang ab. Der Firefox-Test prüft die Fehleranzeige.

## Donner über Thunderforge – Freigabe besprochener Änderungen

Untersuchung am 26.11.2026 anhand der lokalen SQLite-Datenbank `~/.local/share/creative-studio/studio.sqlite3`, ausschließlich lesend. Der betroffene Chat hat die ID `c80a6eb2a3ff4ae1a8a266bb20e4efc7`, das aktive Story-Projekt die ID `5cedb2fa9cf64561b028f2a78416c4d7`.

| Prüffrage | Gespeicherter Nachweis |
| --- | --- |
| Strukturierter Änderungsvorschlag vorhanden? | Job `3369576475f2417d898433a07c7e7be0` hat `kind=planning`, `action=discuss`, `language=de`. Sein Ergebnis enthält ausschließlich `step`, `answer` und `evidence`. Die korrigierte Kapitelstruktur steht in `answer`. |
| Neue Planversion vorhanden? | Für dieses Projekt existiert ausschließlich Version 1, Titel `Thunderforges Echo`, Sprache `de`, drei Kapitel. |
| Neue Version freigegeben? | Version 1 hat den Zustand `proposal`. Eine zweite Version und deren Freigabe fehlen. |
| Freigabesatz klassifiziert? | Die Nachricht „Ja so ist das gut dann leg los“ erzeugte Job `caab272447d24fe0be729e5612c95085` mit `kind=planning`, `action=discuss`. |
| Weshalb kein Produktionsjob? | Der Freigabeausdruck „so ist das gut“ fehlte in `APPROVAL_CLAUSE`. `WEAK_START` erkannte „leg los“ nur am Klauselanfang. Der Satz erreichte damit den Produktionszweig in `_resolve_chat_first` nicht. |
| Weshalb „Story besprechen“? | Bei vorhandenem Plan fiel der Satz in `requested_action` auf `planning-discuss`. `enqueue_planning` speichert für diese Aktion den Chat-Platzhalter „Story besprechen“. |
| Weshalb englischer Text? | Der Ergebnistext von `caab…` enthält nach deutscher Einleitung den englischen Satz „The roar of the crowd…“. Dieser Satz steht bereits wortgleich in `chapters[0].opening` von Version 1. Aufruf und Skillnachweis nennen `de`, Human Writing mit `style-de.md` und Story Writing mit Planungs- und Bibelreferenzen. Die wortgleiche Passage legt eine Übernahme aus englischem Planmaterial trotz deutscher Aufrufsprache nahe. Der damalige Besprechungspfad validierte nur die strukturierte Hülle und das Antwortfeld. Die interne Entscheidung des Modells lässt sich daraus nicht feststellen. |

Der Änderungswunsch mit „umplanenn“ und „korregieren“ wurde ebenfalls als `discuss` gespeichert. Die bisherigen Muster erkannten diese Wörter nicht als Planrevision. Die damalige `planning`-Implementierung beendete jede Besprechung nach dem Speichern der Antwort. Sie konnte keine Planversion erzeugen.

Die Korrektur verwendet die vorhandene Planversionstabelle. Neue Vorschläge behalten den Tabellenzustand `proposal`. Unter `impact.proposal` stehen Story-ID, ursprüngliche und vorgeschlagene Version sowie `pending_approval`. `impact.chapter_changes` und `impact.bible_changes` enthalten die Änderungen, `versions` und `findings` die Auswirkungen auf vorhandene Kapitel. Eine Freigabe aktualisiert den Vorschlagsstatus auf `approved`. Dieses additive Format erhält die bestehenden API-Aufrufer.

Bei vorhandenem Plan liefert auch eine Besprechung strukturierte Feldänderungen. Die Anwendung validiert sie gegen das Planungsschema und prüft den geänderten Plan erneut auf belegbare Restkonflikte. Befunde zum ursprünglichen Plan bleiben als `source_findings` erhalten. Restkonflikte und Auswirkungen auf vorhandene Texte erfordern weiterhin die Bestätigung im Plan-Dialog. Eine zwischenzeitlich geänderte Planversion lässt den Auftrag mit `production_plan_changed` scheitern. Freigegebene Planinhalte werden durch eine Besprechung ausschließlich über eine neue Version ergänzt.

Die Story-Sprache folgt einer ausdrücklichen Sprachangabe, anschließend der gespeicherten Planung beziehungsweise den Story-Einstellungen. Die Sprachprüfung der Besprechungsantwort verwendet die vorhandenen Human-Writing-Marker auf Absätzen ab 25 Wörtern. Sie ist heuristisch. Ein erkannter Sprachfehler beendet den Auftrag vor dem Speichern einer neuen Planversion. Die Manuskriptproduktion verwendet weiterhin ihre vorhandenen Sprachprüfungen.

Die Regressionen verwenden isolierte Datenbanken und ersetzte Modellantworten. Sie prüfen den konkreten Freigabesatz über HTTP, wiederholte Startanfragen, unveränderte freigegebene Ausgangsversionen, persistierte Vorschlagsdaten, besprochene Änderungen ohne Auditbefund, ungültige Kapitelwerte und die Zurückweisung einer englischen Besprechungsantwort. Eine vollständige Produktion mit echten Modell- und Bilddiensten wurde für diesen Fix nicht ausgeführt. Der lokale Dienst und der untersuchte Bestandschat wurden durch diese Quellcodeänderung nicht aktualisiert.

Verifiziert mit `python3 tests/creative-studio-chat.py` (8 Tests), `python3 tests/creative-studio-production.py` (46 Tests), `python3 tests/creative-studio-story.py` (2 Tests), Python-Kompilierung und `git diff --check`. `semgrep scan --config p/python --metrics off --quiet libexec/creative_studio_chat.py libexec/creative_studio_production.py` endete mit Exitcode 0 ohne Befunde. Die Chat-Fixture meldete außerdem ResourceWarnings zu offenen SQLite-Verbindungen.

## Autonome Produktion und lokale Aktivierung am 26.11.2026

Natürliche Story-Aufträge starten jetzt `auto_production`. Der vorhandene Planungsjob übernimmt Titel, Sprache, Kapitelzahl, Wortbereich und Ordnerwissen. Er prüft den Plan samt Weltkanon und verarbeitet höchstens zwei strukturierte Überarbeitungen. Bestätigte Ordnerfakten bleiben in ihrer Ablage geschützt. Die konsistente Planung wird versioniert und auf Grundlage des ursprünglichen Produktionsauftrags automatisch freigegeben. Der bestehende Job wechselt unter derselben ID in die Manuskriptproduktion. Das Anfragekennzeichen bleibt für Wiederholungen erhalten. Bei „Zeige mir zuerst die Planung“ wartet der Entwurf auf Zustimmung und startet danach automatisch.

Die Planreparatur verwendet eingeschränkte Abschnitts-, Kapitel- und Feldwerte im JSON-Schema. Abgelehnte Antworten bleiben in der geschützten Diagnose. Das gespeicherte ältere Visual Profile „Riff Racers Default“ wird anhand seines Stils dem passenden technischen Profil zugeordnet. MOSS, Low-Poly-Stil, Palette und 16:9 werden gemeinsam übernommen.

Die isolierte echte Abnahme unter `output/autonomous-thunderforge-final` wurde auf Nutzerwunsch abgebrochen. Job `6a455710043647a4a1deee8239687bc9`, Projekt `a2ef36781be64a85ba99705380d7e4f7` und Chat `08f2f5792c4c4c32812287748bdc1a57` dokumentieren eine Benutzeranweisung und einen Produktionsjob. Der Plan wurde nach zwei automatischen Überarbeitungen als Version 1 freigegeben. Der Abbruch erfolgte während der Textprüfung von Kapitel 1. Die vollständige Drei-Kapitel-Abnahme mit vier Bildern und Exporten ist damit nicht bestanden und bleibt unvollständig. Die vorhandenen Daten und `aborted-test.json` liegen lokal im Ausgabeverzeichnis. Der frühere, an der Planreparatur gescheiterte Versuch bleibt ebenfalls lokal erhalten.

Erfolgreich geprüft wurden 9 Chat-, 49 Produktions-, 16 Ordnerwissen- und 2 Story-Tests sowie Python-Kompilierung, Frontend-Build und der Firefox-Produktionsablauf einschließlich natürlicher Einzelanweisung bis zum fertigen Fixture-Manuskript. Die Fixture ersetzt Modell- und Bildantworten. Sie belegt keinen vollständigen echten Drei-Kapitel-Lauf. Die Testumgebung meldete bestehende ResourceWarnings zu SQLite-Verbindungen beziehungsweise temporären Ressourcen.

Semgrep meldete in den geänderten Python-Modulen keine Befunde. Im Hauptprogramm markierte die allgemeine Regel einen bestehenden `subprocess.run`-Aufruf des lokalen Linters. Die Argumentliste verwendet einen festen Skriptpfad und eine begrenzte Sprachauswahl, der Benutzertext geht über stdin, und der Aufruf verwendet keine Shell. Der gemeldete Command-Injection-Verdacht ist damit an dieser Stelle nicht bestätigt.

Die geprüften Quellen und der Webbuild wurden über den vorhandenen Update-Einstieg lokal installiert. `creative-studio.service` wurde neu gestartet und `/api/health` lieferte `ok=true`. Eine Sicherung der zuvor installierten geänderten Module und des Webbuilds liegt lokal unter `output/autonomous-thunderforge-final/installed-backup-20261126T073246`. Die isolierten Testdienste auf 18700 und 18702 wurden beendet. Die weitere echte Abnahme übernimmt der Nutzer in der Oberfläche auf Port 8700.
