# Human Writing im Creative Studio

Die [modulare Schreibpipeline](WRITING_PIPELINE.md) beschreibt die aktuelle Auswahl aus Human Writing, Story Writing und Article Writing sowie die automatische Korrektur für generierte Entwürfe.

Im geöffneten Dokument startet **Text prüfen** den Audit. **Text verbessern** erstellt einen Vorschlag für das Dokument oder eine markierte Passage. Im Vergleich stehen Original und Vorschlag mit hervorgehobenen Änderungen und redaktionellen Begründungen. Bei stabiler Absatzstruktur lassen sich einzelne Änderungen zur Übernahme auswählen.

**Überarbeitung übernehmen** speichert eine neue Version. **Vorschlag verwerfen** schließt den Vorschlag. Unter **Versionen** lassen sich Fassungen öffnen, vergleichen und als neue Version wiederherstellen. Der **Prüfverlauf** enthält Prüfberichte und den Status bisheriger Vorschläge. **Human Writing aktiv** öffnet die Nachweise der letzten Skill-Nutzung am Dokument.

Der normale Chat nutzt denselben Ablauf. „Bitte prüfe unsere Geschichte mit meinem Human Writing Skill und schlage eine natürlichere Fassung vor“ startet Prüfung und Überarbeitung für das geöffnete oder zugeordnete Dokument. Für Aufträge zu einem einzelnen Absatz wird der gewünschte Text im Editor markiert.

## Ursache und technische Einbindung

Der bisherige Editor bot einen isolierten Linter-Aufruf und einen separaten Modellaufruf für markierten Text. Der Linter-Bericht hatte weder eine redaktionelle Analyse noch einen Verlauf. Die Überarbeitung ersetzte zunächst den Entwurf im Browser. Zum Speichern war eine zweite Aktion nötig. Die Versionsverwaltung konnte nur einzelne alte Fassungen anzeigen. Aus dem normalen Chat gab es keinen Weg zu diesem Ablauf.

Das Studio verwendet weiterhin den Skill aus `~/dev/github/skillset/skills/human-writing`. Die drei Schreibprofile zeigen auf Gemma 4 12B StyleTune. `config/writing/render.py` kompiliert die vorhandenen Referenzen für das llama.cpp-Chat-Template. Vor der Generierung prüft das Studio mit `/apply-template`, ob Profil, Modus, Sprachreferenz und erwartete Regeltexte in der gerenderten Anfrage vorhanden sind. Das Backend speichert Skill-Version, Alias und Hashes der verwendeten Referenzen als Nachweis.

- **Texterstellung** verwendet `creative-writing` im Modus `generate`. Der Schreibauftrag enthält die gewünschte Sprache, das Genre und den Ton. Vorhandene Figuren-, Handlungs- und Kontinuitätsnotizen, Story-Bibel, Voice Profile und eine zugehörige Fassung aus dem Projekt ergänzen den Kontext.
- **Audit** führt `scripts/lint_text.py` aus und zeigt seine Funde separat von den redaktionellen Einschätzungen aus `human-audit`. **Story Quality Review** vertieft auf Wunsch Dramaturgie, Figuren, Perspektive und Schluss. Das Backend prüft Modellzitate am Original. Wenn nur ein gültiger Absatzbezug vorliegt, zeigt es einen tatsächlichen Ausschnitt aus diesem Absatz und kennzeichnet ihn entsprechend.
- **Überarbeitung** verwendet `human-rewrite` einschließlich `fidelity-rules.md`. Das Backend prüft unter anderem Sprache, angeforderte Wortzahl, Zahlen und geschützte Markdown-Inhalte und versucht bei Abweichungen höchstens einen zweiten Modelllauf. Die Beurteilung von Handlung, Feinheiten und Figurenstimmen bleibt Teil der redaktionellen Prüfung und der Freigabe.
- **Persistenz** verwendet eine additive SQLite-Migration und die bestehende Dokumentversionierung. Ein Vorschlag bezieht sich auf eine konkrete Ausgangsversion. Bei zwischenzeitlicher Änderung verlangt die Anwendung einen neuen Vorschlag. Die Übernahme speichert Dokument und Versionsstatus gemeinsam.

Für die Modellprüfung einer sehr langen Fassung kann ein Kapitel oder ein Textausschnitt markiert werden. Ab 20.000 Textbytes pro Passage liefert der Audit weiterhin die lokalen Linter-Funde, begrenzt aber die Modellprüfung auf eine kürzere Auswahl. Versionshistorien aus älteren Installationen enthalten unter Umständen nur den Text der damaligen Fassung.

## Geänderte Dateien

- `libexec/llama-creative-studio` enthält Audit, literarische Prüfung, Vorschläge, Freigabe und Migration.
- `packages/creative-studio/web/src/lib/editor.ts`, `editorial-ui.ts`, `studio.ts`, `studio-ui.ts` und `core.ts` enthalten den gemeinsamen Editor- und Chat-Ablauf. `src/styles/global.css` gestaltet den Vergleich und den Verlauf. `package.json` und `package-lock.json` erfassen die bereits im Frontend verwendbare Diff-Bibliothek als direkte Abhängigkeit.
- `tests/creative-studio-editorial.mjs`, `creative-studio-browser.mjs` und `creative-studio-plan.py` decken die Browser-Abläufe und die Validierung ab.

## Wiederholbarer Test mit „Das letzte Licht“

Die Prüfung nutzt eine SQLite-Sicherung der vorhandenen Studio-Datenbank. Der Test erwartet die gespeicherte englische Fassung in Version 1 und verwendet die verbundenen lokalen llama.cpp- und Bilddienste. Er setzt Firefox, Playwright und axe-core voraus.

```bash
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:8711 \
  CREATIVE_STUDIO_EDITORIAL_PHASE=run node tests/creative-studio-editorial.mjs
# Dieselbe isolierte Anwendung mit unverändertem Datenverzeichnis neu starten.
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:8711 \
  CREATIVE_STUDIO_EDITORIAL_PHASE=reopen node tests/creative-studio-editorial.mjs
```

Die Testphasen speichern die Prüfnachweise in `output/playwright/creative-studio`. Mit `CREATIVE_STUDIO_TEST_OUTPUT` und `CREATIVE_STUDIO_TEST_STATE` lassen sich die Pfade anpassen.

## Ergebnis am 24. November 2026

| Prüfung | Beobachtung in Firefox |
| --- | --- |
| A · Audit | Der vorhandene englische Text umfasst nach dem Skill 333 Wörter. Der lokale Linter markierte keine Funde. Das Modell belegte unter anderem eine erklärende Passage über Elaras Einsamkeit und eine Wiederholung. Es markierte auch gelungene Stellen. Der Text blieb bis auf das Byte gleich. |
| B · Vorschlag | Gemma 4 12B StyleTune lieferte mit dem geladenen Skill 1.0.0 einen Vorschlag mit 324 englischen Wörtern innerhalb der Toleranz von ±10 Prozent. Elara, die *Marella*, das Jahr 1943, Ablauf und Atmosphäre blieben erhalten. Der Vergleich zeigte zwei begründete Änderungen. |
| C · Versionen | Erst die Freigabe speicherte Version 2. Version 1 blieb verfügbar und ließ sich als Version 3 wiederherstellen. Projektbezug, alter Chatverlauf, Bildverknüpfung und PNG blieben unverändert. Das vorhandene Bild ist mit dem Dokument und Projekt verbunden. Das separate Titelbildfeld des Projekts ist leer. |
| D · Chat | Der geforderte Wortlaut startete Audit und Rewrite über dieselben Routen wie der Editor. Verwerfen erzeugte keine weitere Version. |
| E · Neustart | Nach dem Neustart mit demselben Testdatenverzeichnis waren die Fassungen, der Prüfverlauf und das identische PNG wieder verfügbar. |
| Fehler und Teilfreigabe | Der Browser zeigte verständliche Meldungen bei fehlender Absatzauswahl und einem unerreichbaren Router. Die Teilfreigabe speicherte ausschließlich den ausgewählten Absatz. Bei einem Modellfehler blieb das lokale Prüfergebnis verfügbar. |
| Layout und Tastatur | Vergleich auf Desktop, Tablet, Mobil und bei 320 Pixel Breite. Die Startansicht blieb auch in Hell/Dunkel tastaturbedienbar. axe meldete in den geprüften Dialogen keine automatisierten A-/AA-Verstöße und einen manuell zu prüfenden Punkt im Vergleich. Eine vollständige WCAG-Konformität ist damit nicht nachgewiesen. |

Astro-Build, TypeScript und sieben fokussierte Python-Tests liefen erfolgreich. Die produktive Story bleibt in Version 1. Die Vorschläge und Versionswechselfolgen wurden in einer Kopie ausgeführt.
