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
