# Human-Writing-Qualitätspipeline

Eine gemeinsame Komponente prüft und korrigiert Schreibergebnisse auf Deutsch und Englisch:
`libexec/creative_studio_quality.py`. Sie hat keine Kenntnis von einzelnen Themen, Namen oder Texten.
Die Regeln stammen aus dem Human-Writing-Skill und aus der Textart.

```
Generate (Aufrufer) → Audit → Verify → Auto-Fix → Recheck → Finalize
```

Die Pipeline schreibt nie neu. Sie korrigiert bestätigte Befunde mit exakten, validierten Span-Änderungen,
lässt gute Abschnitte unberührt und beendet sich nach höchstens zwei Korrekturdurchläufen.

## Wer sie aufruft

| Workflow | Aufruf |
| --- | --- |
| Inhaltsaufträge (Steckbrief, Beschreibung, Website-Text, Dokumentation, Dialog …) | Schritt `review` des `chat_task`, Profil aus dem Inhaltstyp |
| Einmalige Geschichten im Chat | Schritt `review`, Profil `story` |
| Vorhandene Texte | `POST /api/documents/<id>/quality` mit `mode` `audit` oder `fix` |

`quality_run()` im Server ist der eine Einstiegspunkt. Die Story-Produktion und die recherchierte Artikelproduktion
besitzen eigene, ältere Prüfstufen für Kanon, Kontinuität und Belege. Sie nutzen denselben Skill und denselben Patch-Validator
(`creative_studio_correction`), aber noch nicht diese Pipeline. Normale Unterhaltungen laufen nie durch sie.

## Ablauf

1. **Audit.** Vier Quellen, immer zusammen, in Fenstern von wenigen Absätzen:
   - die deterministischen Regeln des Skills (`hw_rules`): Floskeln, Werbesprache, Füllwörter, Wiederholungen,
   - mechanisch beweisbare Reparaturen (`fiction_audit.local_quality`) und die deutsche Orthografie (`editorial_orthography`),
   - ein **Korrekturlauf**: Das Modell gibt die Passage mit berichtigten objektiven Fehlern zurück. Jede wortweise Änderung wird
     ein verankerter Befund mit exakter Ersetzung. Benachbarte Änderungen bilden eine Reparatur. Eine Fassung, die mehr als
     umgeschrieben statt korrigiert ist, wird verworfen (`proofread_rewrote_too_much`),
   - ein **Sprachaudit** mit Satz-für-Satz-Checkliste (Rechtschreibung, Kongruenz, Zeit, Artikel und Kasus, Zeichensetzung,
     wörtliche Übersetzungen, Anglizismen) für alles, was keine einfache Ersetzung hat. Die Selbsteinschätzung „optional“ gilt
     nicht für Grammatik- und Zeichensetzungsmeldungen mit exakter Ersetzung: Darüber entscheidet die Verifikation.
2. **Verify.** Regeltreffer gelten durch ihre Regel als bestätigt. Alles andere wird unabhängig geprüft:
   - Befunde mit exakter Ersetzung durch einen **blinden Vergleich**: Das Modell sieht den Satz vorher und nachher als A und B,
     in wechselnder Reihenfolge, und nennt A, B, „beide“ oder „keine“. Bestätigt ist nur die eindeutige Wahl der neuen Fassung.
     Höchstens 24 Vergleiche je Prüfung, der Rest wird als `verification_budget` ausgewiesen.
   - Befunde ohne Ersetzung in zwei Runden: eine prüft, ob der Fehler echt ist, eine verteidigt das Original. Beide müssen bestätigen.
3. **Fix.** Nur bestätigte Befunde, die ein Profil automatisch korrigiert. Exakte Ersetzungen aus Korrekturlauf und Audit werden
   direkt angewendet. Für die übrigen liefert das Modell den ganzen Satz als exakte Änderung. Mechanische Reparaturen gelten ohne Modell.
4. **Recheck.** Die korrigierte Fassung wird erneut geprüft und nur übernommen, wenn sie
   Struktur, Zitate, Zahlen und Namen erhalten hat, die Längenvorgabe einhält, keine beschädigten Satznähte hat,
   mindestens einen bestätigten Befund behebt und keinen neuen erzeugt.
5. **Finalize.** Die Endfassung wird als neue Dokumentversion gespeichert. Die Vorversion bleibt erreichbar.

### Laufzeit

Alle Rollen nutzen einen Router-Alias und einen Schreibmodus. So bleibt der rund 4000 Token lange Systemprompt zwischengespeichert:
Der erste Aufruf je Sprache dauert auf der Testhardware etwa 50 s, jeder weitere 2 bis 5 s. Ein kurzer Text braucht damit
etwa 10 s (ohne Befunde, Prompt im Cache) bis 100 s (mit Korrekturen und Nachprüfung).

## Sprachen

`de-DE` und `en-US` sind Standard. Eine ausdrücklich genannte Variante (`de-AT`, `de-CH`, `en-GB`, `en-CA`, `en-AU`)
wird dem Audit mitgegeben, damit regionale Schreibweisen nicht als Fehler gelten. Eine unbekannte Variante fällt auf den Standard zurück.
Eine nicht unterstützte Sprache bricht mit `quality_language_unsupported` ab.

## Textarten

Das Profil entscheidet, was als Fehler zählt und wie streng Änderungen sind.

Objektive Fehler (Rechtschreibung, Grammatik, Zeichensetzung, mechanische Wiederholung) werden in jedem Profil korrigiert, sobald der
Verifizierer sie bestätigt. Das Profil bestimmt zusätzlich, welche Regeltreffer des Skills automatisch angewendet werden,
ob Idiomatik und Anglizismen korrigiert werden und wie streng der Änderungsvertrag ist.

| Profil | Beispiele | Zusätzlich automatisch | Idiomatik | Vertrag |
| --- | --- | --- | --- | --- |
| `story` | Geschichte, Kapitel, Gedicht | Füllfloskeln | nein, Stimme und Fragmente bleiben | allgemein |
| `dialogue` | Dialog, Spieltext, Quest | nichts | nein, Umgangssprache und Dialekt sind gewollt | allgemein |
| `article`, `essay` | Artikel, Musikartikel, Dossier, Essay | KI-Floskeln (Essay auch Übergangsfloskeln) | ja | streng: jede Behauptung, Zahl und jeder Name bleibt |
| `technical` | Dokumentation, README, Tutorial | KI-Floskeln | nein, Terminologie bleibt | streng, Befehle, Versionen und Bezeichner bleiben |
| `blog` | Blogbeitrag, Devlog | KI-Floskeln, Übergangsfloskeln | ja, persönliche Stimme bleibt | allgemein |
| `marketing` | Website, Produkttext, Ankündigung | KI-Floskeln, Übergangsfloskeln | ja, leere Superlative werden konkret | allgemein |
| `general` | alles andere | KI-Floskeln, Übergangsfloskeln | ja | allgemein |

"Allgemein" ist der eigene Vertrag der Pipeline, "streng" der Patch-Vertrag des Studios (siehe unten).

## Format- und Faktentreue

Gesperrt für jede Korrektur: Markdown-Struktur, Codeblöcke und Inline-Code, Links und Bildpfade, Frontmatter, Zitate, Zahlen
und Datumsangaben, die vom Aufrufer benannten Begriffe (zum Beispiel das Thema eines Auftrags).
In Sachtexten und technischen Texten gilt zusätzlich der strenge Patch-Vertrag. In allgemeinen Texten unterscheidet der
eigene Vertrag Namen von deutschen Substantiven, erlaubt Beugungsformen und lehnt geänderte Zahlen, erfundene Namen,
überlange Ersetzungen und überlappende Änderungen ab.

Ein Satz wird nur als Ganzes ersetzt oder gelöscht. Teilsatz-Änderungen, die ein Fragment, ein kleingeschriebenes Satzende
oder ein doppeltes Leerzeichen hinterlassen würden, lehnt die Nahtprüfung ab.

## Nachweis

Jeder Lauf liefert ein Receipt (`result.quality` im Auftrag, Antwort von `/quality`). Es nennt:

- Pipeline-Version, Sprachvariante, Profil,
- geladene Skills mit Version und SHA-256 der Regeldateien, SHA-256 des Regelskripts,
- ob das Sprachaudit abgeschlossen wurde, welche Modelle antworteten, wie viele Aufrufe, und jede Einschränkung (`limits`),
- jeden Befund mit Quelle, Kategorie, Status und Begründung, auch den Grund, warum er nicht angewendet wurde,
- je Durchlauf die angewendeten und abgelehnten Änderungen mit Fehlercode, ob das Ergebnis akzeptiert wurde und das Recheck-Ergebnis,
- SHA-256 der Vor- und der Endfassung. Die Versionsnotiz des Dokuments trägt die ersten 12 Zeichen.

„Korrigiert“ und „offen“ werden an der Endfassung gemessen: Ein Befund gilt nur dann als korrigiert, wenn seine Textstelle
verschwunden ist, und bleibt offen, solange sie im Text steht, auch wenn der Recheck ihn nicht erneut meldet.
Fällt das Modell aus, meldet das Receipt `audit.completed: false` mit dem Grund. Es wird kein Audit behauptet.

## Grenzen

- Die Pipeline findet nur, was die Regeln des Skills und das lokale Modell erkennen. Das Modell übersieht Fehler,
  und zwei Läufe über denselben Text können verschiedene Befunde liefern. Ein Lauf ohne Befund beweist keinen fehlerfreien Text.
- Gemessen mit dem lokalen 26B-Modell (RTX 5070, 8 GB): Eine reine Fehlerliste als JSON fand etwa 3 von 8 eingebauten Fehlern,
  der Korrekturlauf etwa 7 von 8. Der blinde Vergleich entschied 13 von 14 Fällen richtig (alle 8 echten Fehler bestätigt,
  5 von 6 korrekten Sätzen belassen; der Fehltreffer, eine Großschreibung in einem Eigennamen, wird vom Namensschutz abgefangen).
  Das sind kleine Stichproben, keine Garantie.
- Faktische Richtigkeit prüft sie nicht. Das tut die Belegprüfung der Artikelproduktion.
- Stilentscheidungen (Rhythmus, Satzbau-Muster) werden gemeldet, aber nicht automatisch geändert.

## Tests

`python3 tests/creative-studio-quality.py` deckt zwölf voneinander unabhängige Texte ab (Deutsch und Englisch: Beschreibung,
Literatur, Artikel, Devlog, Technik, Website mit Markdown, Fachbegriffe und Zitate, ein bereits guter Text, ein Text mit
mehreren Fehlern) sowie die Negativfälle: verfälschte Zahl, Version und Code, geschützter Name, beschädigte Links und
Codeblöcke, bewusste Stilmittel, erfundene Befunde, Modellausfall, Müll vom Modell, Durchlaufgrenze und Endlosschleife.
Das Modell ist dabei geskriptet. Alles andere (Regeln, Verankerung, Patch-Validator, Schutz, Nahtprüfung, Receipt) läuft echt.
`tests/creative-studio-content.py` prüft den Ablauf im Server, einschließlich einer englischen Anfrage in einem
fremden Ordner, einer Geschichte und der Prüfung eines vorhandenen Dokuments.
