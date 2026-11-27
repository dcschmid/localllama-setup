# Inhaltsaufträge: Text, Bild und Datei in einer Anfrage

Ein Auftrag wie

> Erstelle einen deutschsprachigen Strecken-Steckbrief für Thunderforge aus Riff Racers mit ungefähr 250 Wörtern.
> Verwende ausschließlich das bestätigte Wissen aus diesem Ordner. … Prüfe und korrigiere den Text automatisch.
> Erstelle dazu ein passendes Bild im Low-Poly Concept Art Stil, 16:9.
> Zeige mir beides direkt im Chat und stelle den Steckbrief als Markdown-Datei zum Herunterladen bereit.

ist eine **Texterstellung**. Die Prüfung, das Bild und die Datei sind Folgeschritte. Früher meldete das
Studio hier „Für diese Textprüfung liegt im Chat noch kein geschriebener Text vor“, weil „Text“ und „Prüfe“
zusammen den Prüfpfad auslösten und „Erstelle“ nie gewichtet wurde.

## Wie die Hauptaufgabe bestimmt wird

`libexec/creative_studio_content.py` liest die Anfrage Satz für Satz, nicht nach einzelnen Schlüsselwörtern.

- Eine **Erstellungsklausel** beginnt mit einem Schreibverb („Erstelle“, „Schreibe“, „Verfasse“, „Kannst du … schreiben“)
  und nennt ein neues Textergebnis (Steckbrief, Beschreibung, Zusammenfassung, Mail, Gedicht …).
- Steht die Prüfung **nach** einer Erstellungsklausel, ist sie die Qualitätsstufe dieses Auftrags.
- Eine Prüfung bleibt Hauptaufgabe, wenn sie **zuerst** kommt oder kein neuer Text verlangt wird
  („Prüfe diesen Text“, „Schreibe den Text neu“, „Verbessere diesen Text“).
- Geschichten, Artikel, Recherche, Planung, Spielideen und reine Bildwünsche behalten ihre Routen.
  Ein ausdrücklich gewählter Modus (Chat, Bild, Recherche, Spiel) wird nicht überstimmt.

Aus der Anfrage entsteht dieser Vertrag (`analyze`), der im Auftrag unter `plan.writing.content` gespeichert wird:

```json
{
  "primary_intent": "create_content", "content_type": "track_profile", "content_label": "Strecken-Steckbrief",
  "language": "de-DE", "target_words": 250, "word_range": [225, 275],
  "subject": "Thunderforge", "context_name": "Riff Racers",
  "use_folder_knowledge": true, "knowledge_only": true,
  "review_after_creation": true, "auto_correct": true,
  "generate_image": true, "image_aspect_ratio": "16:9", "image_profile": "Low-Poly Concept Art",
  "export_formats": ["md"], "export_unsupported": []
}
```

Der Schreibauftrag (`plan.writing.instruction`) enthält nur die Schreibvorgaben. Bild-, Datei- und Prüfsätze laufen als eigene Schritte.

## Ablauf

Ein einziger `chat_task` führt ohne weitere Eingabe alle Schritte aus. Es gibt keine Story-Planung, keine Freigabe und keine Recherche.

| Schritt | Was passiert |
| --- | --- |
| `writing` | Ordnerwissen laden (nach Thema gerankt: die 6 relevantesten Einträge plus bestätigte Einträge, nie Ideen oder das Visual Profile), Text schreiben, Sprache, Länge und Thema messen |
| `document` | Erster Entwurf wird als Dokument gespeichert (Version 1) |
| `review` | Human-Writing-Audit. Gefundene Befunde werden höchstens zweimal korrigiert und nur gespeichert, wenn die Befunde messbar weniger werden. Die korrigierte Fassung ist Version 2. Verbleibende Hinweise werden angezeigt |
| `export` | Markdown-Datei wird aus der gespeicherten Endfassung geschrieben, zurückgelesen und gegen Größe und SHA-256 geprüft |
| `image` | Bild über den lokalen Bilddienst |

Jeder Schritt wird persistiert. Nach einem Neustart setzt der Auftrag am unterbrochenen Schritt fort.

### Ordnerwissen

`use_folder_knowledge` und `knowledge_only` stammen aus Formulierungen wie „aus diesem Ordner“ und „ausschließlich“.
Der Schreibauftrag verbietet dann neue Namen, Zahlen, Regeln, Orte und Ereignisse. Fehlt Ordnerwissen,
bricht der Auftrag **vor** dem ersten Modellaufruf mit `content_knowledge_missing` ab. Bild, Prüfung und Export werden dann übersprungen.

„Bestätigtes Ordnerwissen“ meint hier wie im restlichen Studio den Block aus Kanon (`confirmed`) und Referenzen (`reference`).
Ideen werden nie eingespeist. Die Karte im Chat zeigt unter „Verwendetes Ordnerwissen“, welche Einträge mit welchem Status benutzt wurden.

### Länge

Kleine Schreibmodelle verfehlen eine Wortzahl um einen festen Faktor und kopieren einen Entwurf, den sie überarbeiten sollen.
Deshalb gibt der Auftrag die Länge als Absatzplan vor. Verfehlt ein Entwurf den Bereich, wird **frisch** geschrieben, mit einem um
den gemessenen Faktor korrigierten Ziel (höchstens vier Versuche).

### Bild

Benennt die Anfrage einen Studio-Stil („Low-Poly Concept Art“, „Graphic Novel“, …) oder hat der Ordner ein Visual Profile,
nutzt das Bild dieselben Vorlagen, Modelle und Rezepte wie Story-Illustrationen. Das Profil des Ordners liefert Palette und Standardstil,
die Vorlage `riff-racers-low-poly` wird für Ordner „Riff Racers“ gewählt. Der Composer reduziert den Text auf einen kurzen Szenen-Digest.
Jeder andere Stil wird als kurzer Szenen-Prompt mit „no text, no lettering“ gesendet. Ein in der Oberfläche gewähltes Modell hat Vorrang.

### Datei

`GET /api/chat/tasks/<id>/files/<name>` liefert die Datei nur, solange ihre Bytes noch dem Beleg entsprechen. Unterstützt ist `md`.
Andere genannte Formate (`mdx`, `pdf`, `docx`, `txt`) erscheinen unter `export_unsupported`, und die Karte weist darauf hin.

## Tests

`python3 tests/creative-studio-content.py` prüft den Vertrag, die Routing-Matrix und den kompletten Ablauf mit nachgebildeten
Schreib- und Bilddiensten, einschließlich Fehlerfällen (kein Wissen, wirkungslose Korrektur, manipulierte Datei).
