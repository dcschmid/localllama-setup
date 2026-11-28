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

1. **Audit.** Drei Quellen, immer zusammen:
   - die deterministischen Regeln des Skills (`hw_rules`): Floskeln, Werbesprache, Füllwörter, Wiederholungen,
   - mechanisch beweisbare Reparaturen (`fiction_audit.local_quality`) und die deutsche Orthografie (`editorial_orthography`),
   - ein Sprachaudit des Modells, in Fenstern, mit einer Satz-für-Satz-Checkliste je Sprache
     (Rechtschreibung, Kongruenz, Zeit, Artikel und Kasus, Zeichensetzung, wörtliche Übersetzungen, Anglizismen).
2. **Verify.** Jeder Modellbefund wird unabhängig geprüft. Regeltreffer gelten durch ihre Regel als bestätigt.
   Optionale Stilhinweise, deliberate Stilmittel, Zitate und Mehrdeutigkeit bleiben unbestätigt.
3. **Fix.** Nur bestätigte Befunde, die ein Profil automatisch korrigiert. Das Modell liefert den ganzen Satz als
   exakte Änderung. Mechanische Reparaturen gelten ohne Modell.
4. **Recheck.** Die korrigierte Fassung wird erneut geprüft und nur übernommen, wenn sie
   Struktur, Zitate, Zahlen und Namen erhalten hat, die Längenvorgabe einhält, keine beschädigten Satznähte hat,
   mindestens einen bestätigten Befund behebt und keinen neuen erzeugt.
5. **Finalize.** Die Endfassung wird als neue Dokumentversion gespeichert. Die Vorversion bleibt erreichbar.

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
- Gemessene Trefferquote des Modellaudits (lokales Modell, je Text dreimal, eingebaute Fehler: Kongruenz, Kasus): Absatzfenster und Ganztext liegen gleichauf. Englischer Tool-Text 1 bis 2 von 2, deutscher Text mit „Alle Gäste bekommt“ 3 von 3, englischer Devlog 0 von 2 (Ganztext einmal 1 von 2), deutsche Geschichte 0 von 1. Etwa jeder zweite bis dritte eingebaute Fehler bleibt unentdeckt. Was gemeldet und bestätigt wird, war in diesen Läufen dagegen zutreffend, und es wurde kein Fakt verändert. Ein Lauf ohne Befund ist keine Garantie.
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
