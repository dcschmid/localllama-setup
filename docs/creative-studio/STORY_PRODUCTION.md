# Story-Produktion im Creative Studio

Eine natürliche Anweisung wie „Erstelle eine deutschsprachige Geschichte mit dem Titel Donner über Thunderforge. 3 Kapitel mit jeweils 900–1.200 Wörtern …“ startet standardmäßig `auto_production`. Das Studio erfasst Titel, Sprache, Kapitelzahl und Wortbereich, lädt das bestätigte Ordnerwissen samt Referenzen und erstellt intern Story-Bibel, Zeitlinie und Kapitelplanung. Es prüft die Planung, korrigiert belegte Fehler in höchstens zwei Durchläufen und speichert den konsistenten Plan als freigegebene Version. Derselbe persistente Produktionsjob schreibt anschließend die Kapitel, prüft und korrigiert sie, erzeugt Bilder und validiert die Exporte. Die Freigabe beruht in diesem Modus auf dem ursprünglichen Produktionsauftrag.

Mit „Zeige mir zuerst die Planung“ fordert der Nutzer eine vorherige Freigabe an. Das Studio plant und prüft intern, hält mit einem versionierten Entwurf an und beginnt nach Zustimmung automatisch die vollständige Produktion. Die eigenständige Schaltfläche **Geschichte planen** erzeugt weiterhin einen Plan zur Durchsicht. Über **Plan bearbeiten** entsteht eine neue Version. Im Chat kannst du auch mit „Story-Planung überarbeiten …“ einen persistenten Änderungsvorschlag erzeugen.

**Planung freigeben** legt bei eigenständigen Planungen die Grundlage für **Gemeinsam schreiben** oder **Geschichte vollständig erstellen** fest. Im ersten Modus hält das Studio nach jedem Kapitel zur Freigabe an. Im zweiten produziert es alle Kapitel und Illustrationen ohne einzelne Kapitelbestätigungen. Belegte, sicher korrigierbare Textfehler durchlaufen höchstens zwei automatische Überarbeitungen mit erneuter Prüfung. Offene Kanonkonflikte pausieren den Job. Bestätigte Ordnerfakten werden durch die Produktion nicht geändert. Bei einer Planänderung prüft das Studio bestehende Kapitel und verlangt eine Bestätigung der Auswirkungen. Belegte Beobachtungen aus den fertiggestellten Kapiteln sind in der erweiterten Story-Bibel mit ihren Textstellen verfügbar.

Der Zustand ergibt sich aus der gespeicherten Planversion und dem letzten Auftrag. `/api/production/<Projekt-ID>` nennt ihn als `stage`: `NO_PLAN`, `PLANNING`, `PLAN_READY`, `PLAN_APPROVED`, `PRODUCTION_RUNNING`, `PRODUCTION_PAUSED`, `PRODUCTION_FAILED`, `PRODUCTION_INCOMPLETE` oder `PRODUCTION_COMPLETED`. Eine Modellantwort ändert ihn nicht. Im Chat steht der laufende Schritt. Du kannst pausieren, fortsetzen, abbrechen oder einen fehlgeschlagenen Schritt wiederholen. Ein bereits laufender Einzelaufruf kann noch auslaufen. Er unterbricht keinen anderen Dienst. Nach einem Studio-Neustart setzt der Job an seinem gespeicherten Schritt an. Dokumentversionen und bereits abgeschlossene Bilder sind über ihre IDs zugeordnet.

Öffne das Manuskript über den Produktionsauftrag. Nach der Prüfung schreibt das Studio `manuscript.md`, `manuscript.mdx`, `manifest.json`, die Original-PNGs unter `images/` und ein ZIP in `~/.local/share/creative-studio/productions`. Erst die vollständige Prüfung einschließlich MDX-Compiler und ZIP macht die Downloads im selben Chat sichtbar. Einzeldateien behalten relative Bildpfade. Im ZIP liegen die passenden Bilddateien bereits neben dem Manuskript. Bei gemeinsamen Aufträgen gibt der Nutzer die Bildserie vor dem Export frei. [Astro MDX-Dokumentation](https://v5.docs.astro.build/en/guides/integrations-guide/mdx/)

Ein vollständiger Produktionsauftrag im Chat darf Anforderungen an Bilder und Export enthalten. Der automatische Modus führt von der internen Planung zur Manuskriptproduktion. Für eigenständig angelegte Planungen steht außerdem die Freigabe im Chat zur Verfügung. Die Freigabe funktioniert im Chat auch in freier Formulierung, etwa „Die Planung ist freigegeben. Erstelle jetzt die Geschichte.“, „Passt so, bitte vollständig schreiben.“, „Ja so ist das gut dann leg los“, „Starte die Manuskriptproduktion.“, „Schreibe jetzt alle drei Kapitel.“, „Generate the full story now.“ oder „I approve the outline. Start writing.“. Das Studio gibt dann genau die zuletzt gespeicherte Planversion dieses Chats frei und startet einen echten Produktionsauftrag. Die Anweisung hat Vorrang vor der Planungsprüfung. Fragen, Bedingungen („wenn“, „aber“, „zuerst“), Verneinungen, einzelne Kapitel („Schreibe Kapitel 2“) und Überarbeitungen („schreibe alle Kapitel neu“) starten nichts. Offene Auswirkungen einer Planänderung verlangen weiterhin die Bestätigung im Plan-Dialog. Im Plan-Dialog gibt **Freigeben und vollständig erstellen** die angezeigte Planversion frei und startet in einem Schritt. „Planung freigeben“ und „Geschichte vollständig erstellen“ sind weiterhin eigenständige Chatbefehle. Wenn Exportdateien eines früheren Jobs fehlen, zeigt das Studio den Auftrag als unvollständig. **Produktion vervollständigen** übernimmt vorhandene Checkpoints der freigegebenen Planversion.

## Modellrollen

Die Anwendung liest `story-model-roles.json` optional aus dem Creative-Studio-Konfigurationsordner. Jede Rolle akzeptiert einen Router-Alias oder eine geordnete Liste von Aliasen. Verfügbare IDs werden zur Laufzeit aus `/v1/models` gelesen. Beispiel für die isolierte Abnahme nach Modellfreigabe:

```json
{
  "plan": ["creative-writing", "story"],
  "write": ["creative-writing", "story"],
  "rewrite": ["creative-writing", "story"],
  "audit": ["research", "creative-writing"]
}
```

Ohne Datei verwendet die Analyse bevorzugt `research`. Die Planung und Texterstellung wählen aus `creative-writing`, `story` und `human-writing`. Die Produktionsdiagnose unter `/api/production/<Projekt-ID>/report` enthält den tatsächlich verwendeten Alias, die Modell-ID, GGUF-Variante, Quantisierung, Router- und Samplingparameter sowie Versionen und Prüfsummen der nachweislich geladenen Regeln aus Human Writing und Story Writing. Der Router rendert den Prompt und tokenisiert ihn vor der Generierung. Chapter-Batches verwenden relevante Bibeldaten und kurze Zusammenfassungen. [llama.cpp Server-API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

Das Studio wartet, solange ein Inferenzslot belegt ist oder der Bilddienst rendert. Die Warteschlange kann einen vom Produktionsjob zuletzt genutzten Router-Worker freigeben, sobald dieser im Schlafzustand ist und keine anderen Router-Modelle aktiv sind. Ein Alias mit langer Leerlauffrist kann die Bildgenerierung verzögern.

## Abnahme der Bilder

Das Studio speichert für jedes Motiv eine Textstelle, den Prompt, den Seed, die zugehörige Dokumentversion, das tatsächlich verwendete Visual Profile und die Bild-ID. Das Standardformat für neue Produktionen ist 16:9. Das Studio prüft die PNG-Struktur, dekomprimierte Bilddaten, Prüfsummen und Abmessungen. Geprüfte Originale liegen zusätzlich in der Studio-Mediathek. Über **Neue Fassung für das Manuskript** kannst du einzelne Motive neu erzeugen. Vorhandene Fassungen bleiben im Bildarchiv. Figuren, Kleidung und Schauplätze kannst du mit Kapitelgrenzen in der Visual Bible erfassen. Ein Seed stabilisiert das Sampling einer konkreten Anfrage. [Visual Profiles und lokale Abnahme](STORY_VISUAL_PROFILES.md)

Aktualisierte Image-Service-Builds nehmen einen `Idempotency-Key` an. Bei älteren Builds versucht das Studio, eine unterbrochene Einreichung anhand der gespeicherten Anfrage und des Seeds wiederzufinden. Bei einer mehrdeutigen Antwort hält es den Produktionsjob an. Es sendet die Anfrage in diesem Fall nicht blind erneut.

## Prüfung

- `python3 tests/creative-studio-production.py` prüft die Produktionszustände mit ersetzten Modell- und Bildantworten.
- `python3 tests/creative-studio-production.py --serve-fixture 18702` startet eine isolierte HTTP-Fixture. `CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:18702 node tests/creative-studio-production.mjs` prüft sie mit Firefox.
- `python3 tests/creative-studio-real-production.py --url http://127.0.0.1:18700 --output output/story-production-acceptance` verfolgt einen bereits angelegten echten Abnahmelauf. Die Ergebnisse und der aktuelle Status liegen in dessen Ausgabeverzeichnis.
- `python3 benchmarks/story-production-models.py --help` zeigt die Eingaben für den Deutsch-/Englisch-Vergleich. Der Vergleich liest die vorhandenen Beispiele aus SQLite und schreibt eigene Ergebnisdateien.

Die [Produktionsansicht](PRODUCTION_MONITOR.md) zeigt Zustand, Heartbeat, Fortschritt, Kapitelstatus, Wortzahlen und den Aktivitätsverlauf aus den gespeicherten Backend-Daten. `python3 tests/creative-studio-monitor.py` und `node tests/creative-studio-monitor.mjs` prüfen sie.

Der [P0-Bericht](STORY_PRODUCTION_P0.md) dokumentiert die Untersuchung von Riff Racers, den lokalen Abnahmelauf und die Nachweise.

Besprochene Planänderungen werden als neue, validierte Planversion mit `pending_approval` in den Vorschlagsdaten gespeichert. Die Daten enthalten die Ausgangsversion, Kapitel- und Bibeländerungen sowie Auswirkungen auf vorhandene Kapitel. Der Plan-Dialog zeigt die neue Version zur Freigabe. Der Chat kann sie mit einer Zustimmung und Startanweisung freigeben und die vollständige Produktion beginnen. Offene Auswirkungen und belegte Restkonflikte werden weiterhin im Plan-Dialog bestätigt.
