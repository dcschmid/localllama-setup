# Story-Produktion im Creative Studio

Wähle im Chat **Geschichte / Roman** und öffne **Geschichte planen**. Beschreibe die Idee, wähle Sprache und Kapitelzahl und passe bei Bedarf den Wortbereich an. Die Planung erscheint im Chat. Sie enthält Handlung, Story-Bibel, Visual Bible und Kapitelübersicht. Über **Plan bearbeiten** legst du eine neue Version an. Im Chat kannst du auch mit „Story-Planung überarbeiten: …“ eine geänderte Planung vorschlagen lassen.

**Planung freigeben** legt die Grundlage für **Gemeinsam schreiben** oder **Geschichte vollständig erstellen** fest. Im ersten Modus hält das Studio nach jedem Kapitel zur Freigabe an. Im zweiten produziert es alle Kapitel und Illustrationen ohne einzelne Kapitelbestätigungen. Beide Modi halten bei belegten, ungelösten Konflikten an. Bei einer Planänderung prüft das Studio bestehende Kapitel und verlangt eine Bestätigung der Auswirkungen. Belegte Beobachtungen aus den fertiggestellten Kapiteln sind in der erweiterten Story-Bibel mit ihren Textstellen verfügbar.

Im Chat steht der laufende Schritt. Du kannst pausieren, fortsetzen, abbrechen oder einen fehlgeschlagenen Schritt wiederholen. Ein bereits laufender Einzelaufruf kann noch auslaufen. Er unterbricht keinen anderen Dienst. Nach einem Studio-Neustart setzt der Job an seinem gespeicherten Schritt an. Dokumentversionen und bereits abgeschlossene Bilder sind über ihre IDs zugeordnet.

Öffne das Manuskript über den Produktionsauftrag. Sobald die Textprüfung und Sichtprüfung abgeschlossen sind, stehen Markdown, MDX und ein ZIP mit beiden Fassungen und den PNG-Dateien bereit. Das ZIP enthält relative Bildpfade. Für ein Astro-Projekt kannst du die MDX-Datei und ihren Ordner `images` gemeinsam übernehmen. [Astro MDX-Dokumentation](https://v5.docs.astro.build/en/guides/integrations-guide/mdx/)

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

Ohne Datei verwenden die Rollen die verfügbaren Schreibaliase `creative-writing`, `story` oder `human-writing`. Die Produktionsdiagnose unter `/api/production/<Projekt-ID>/report` enthält den tatsächlich verwendeten Alias, die Modell-ID, GGUF-Variante, Quantisierung, Router- und Samplingparameter sowie die Version und Prüfsummen der geladenen Human-Writing-Regeln. Der Router rendert den Prompt und tokenisiert ihn vor der Generierung. Chapter-Batches verwenden relevante Bibeldaten und kurze Zusammenfassungen. [llama.cpp Server-API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

Das Studio wartet, solange ein Inferenzslot belegt ist oder der Bilddienst rendert. Für Bildjobs gelten die GPU-Prüfungen der vorhandenen Warteschlange. Der Produktionsjob entlädt keine Modelle und ändert keine llama.cpp-Profile. Ein Alias mit langer Leerlauffrist kann die Bildgenerierung verzögern.

## Abnahme der Bilder

Das Studio speichert für jedes Motiv eine Textstelle, den Prompt, den Seed, die zugehörige Dokumentversion und die Bild-ID. Der lokale Dienst validiert PNG-Daten und Abmessungen. Die Modelle in der getesteten Konfiguration akzeptieren Text. Sobald alle Motive vorliegen, zeigt das Studio sie gemeinsam zur Sichtprüfung. Über **Neue Fassung für das Manuskript** kannst du einzelne Motive korrigieren und neu erzeugen. Vorhandene Fassungen bleiben im Bildarchiv. Wiederkehrende Figurenmerkmale, Kleidung und Farbpalette stehen in der Visual Bible. Ein Seed stabilisiert das Sampling einer konkreten Anfrage und garantiert keine wiedererkennbare Figur über verschiedene Motive hinweg.

Aktualisierte Image-Service-Builds nehmen einen `Idempotency-Key` an. Bei älteren Builds versucht das Studio, eine unterbrochene Einreichung anhand der gespeicherten Anfrage und des Seeds wiederzufinden. Bei einer mehrdeutigen Antwort hält es den Produktionsjob an. Es sendet die Anfrage in diesem Fall nicht blind erneut.

## Prüfung

- `python3 tests/creative-studio-production.py` prüft die Produktionszustände mit ersetzten Modell- und Bildantworten.
- `python3 tests/creative-studio-production.py --serve-fixture 18702` startet eine isolierte HTTP-Fixture. `CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:18702 node tests/creative-studio-production.mjs` prüft sie mit Firefox.
- `python3 tests/creative-studio-real-production.py --url http://127.0.0.1:18700 --output output/story-production-acceptance` verfolgt einen bereits angelegten echten Abnahmelauf. Die Ergebnisse und der aktuelle Status liegen in dessen Ausgabeverzeichnis.
- `python3 benchmarks/story-production-models.py --help` zeigt die Eingaben für den Deutsch-/Englisch-Vergleich. Der Vergleich liest die vorhandenen Beispiele aus SQLite und schreibt eigene Ergebnisdateien.
