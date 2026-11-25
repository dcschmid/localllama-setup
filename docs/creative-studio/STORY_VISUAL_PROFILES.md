# Story Visual Profiles im Creative Studio

## Bedienung

Im Story-Chat öffnet **Bildstil** das Profil dieser Geschichte. Wähle eine Vorlage, ein vom lokalen Modell unterstütztes Format und bei Bedarf **Visuelle Konsistenz**. Unter **Erweitert** stehen das Modell, die Guided Recipe, die Lizenz und die eigenen Stilvorgaben. Dort lässt sich ein vorhandenes Profil aus einer anderen Geschichte kopieren. Im Chat ändern „Verwende ab jetzt Graphic Novel für diese Geschichte“ und „Ich möchte ab jetzt alle Illustrationen im Painterly Storybook Stil“ das gespeicherte Profil. „Zeige mir diese Szene als Low-Poly-Render“ gilt für den einzelnen Auftrag.

„Erstelle ein passendes Bild für Kapitel 3“ bezieht sich auf den zugeordneten Kapiteltext. „Mach die Szene etwas heller“ nutzt das letzte Bild im aktuellen Story-Chat als Ausgangspunkt. In der Bildvorschau stehen Bilddetails, Download, erneute Generierung, Variante, Einsatz als Titelbild und das Einfügen ins Dokument. Das Archiv in **Bibliothek → Bilder** hält die erzeugten Fassungen und ihre IDs vor.

| Profil | Bevorzugtes lokales Modell | Standardrezept |
|---|---|---|
| Anima Aesthetic | Anima Aesthetic 1.1 · `anima` | `anima-film`, je nach Aufgabe `anima-portrait`, `anima-landscape` oder `anima-fantasy` |
| Painterly Storybook | Anima Aesthetic 1.1 · `anima` | `anima-storybook` |
| Graphic Novel | MOSS Image · `moss` | `moss-comic`, optional `anima-manga` mit Anima |
| Soft Cinematic Anime | Anima Aesthetic 1.1 · `anima` | `anima-film` mit eigener Stilvorgabe |
| Low-Poly Concept Art | MOSS Image · `moss` | `lowpoly-retro`, je nach Aufgabe u. a. `lowpoly-character`, `lowpoly-vehicle`, `lowpoly-track-overview` oder `lowpoly-world` |
| High-Poly Stylized | Z-Image · `z-image` | Freie lokale Compose-Vorlage |
| Riff Racers – Game Art · Low-Poly | MOSS Image · `moss` | `lowpoly-retro` mit Riff-Racers-Stilvorgabe und den passenden Aufgabenrezepten |
| Riff Racers – Game Art · High-Poly | Z-Image · `z-image` | Freie lokale Compose-Vorlage mit Riff-Racers-Stilvorgabe |

Der überprüfte Katalog bietet für `anima`, `moss` und `z-image` 16:9 mit 1024 × 576, 1:1 mit 1024 × 1024, 4:3 mit 1024 × 768, 3:4 mit 768 × 1024 und 9:16 mit 576 × 1024 Pixeln. Für 3:2 und 2:3 bietet er bei Anima und MOSS 1152 × 768 und 768 × 1152, bei Z-Image 960 × 640 und 640 × 960. Die Auswahl im Studio stammt aus dem laufenden Katalog. Sie setzt ein installiertes Modell, ein zugeordnetes Rezept und eine tatsächlich angebotene Größe mit dem gewählten Verhältnis voraus. Fehlt die Kombination, zeigt das Studio den Fehler an.

Der Katalog und die Primärquellen führen MOSS Image SFT und Z-Image unter Apache-2.0. Anima steht unter der CircleStone-Lizenz. Sie schränkt den Einsatz der Modellgewichte ein und behandelt kommerzielle Nutzung von Ausgaben gesondert. Für kommerzielle Riff-Racers-Inhalte zählen außerdem die Rechte an den verwendeten Referenzmotiven. [MOSS Image SFT](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT) · [Z-Image](https://huggingface.co/Tongyi-MAI/Z-Image) · [Anima-Lizenz](https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md)

## Persistenz und Bildkomposition

Das Profil liegt versioniert in den Metadaten des vorhandenen Story-Kontexts, zu dem Chat, Ordner und Dokumente gehören. Das Studio prüft beim Speichern die erwartete Profilversion. Das Kopieren zwischen Storys übernimmt Stilvorgaben und beschriebene Merkmale. Referenzdateien bleiben an ihren Story-Kontext gebunden. Wenn das ganze Projekt dupliziert wird, ordnet das Studio die kopierten Anhänge ihren neuen IDs zu.

In der Visual Bible stehen Figuren- und Schauplatzmerkmale mit Kapitelintervallen. Das Studio nimmt den jüngsten passenden Stand und wählt Einträge für benannte Elemente der Szene aus. Automatisch erfasste, textbelegte Beobachtungen zu Kleidung, Figuren, Orten und Gegenständen stammen aus früheren, weiterhin gültigen Kapitelfassungen. Die konkrete Textstelle und der passende manuelle Eintrag haben Vorrang bei einem Zustandswechsel. Für Winter, Abendlicht, Nacht, Wald und Industrie setzt der Composer unterschiedliche Farb- und Lichtakzente.

Bildreferenzen können in der Visual Bible hochgeladen oder aus den eigenen Story-Anhängen ausgewählt werden. Wählt der Nutzer **Als Bildvorlage für passende Szenen verwenden**, prüft das Studio `img2img` für das gewählte Modell und übergibt bei einem passenden Eintrag eine Referenz. Die Bildkonditionierung kann die Originalkomposition und Farbverteilung mitprägen. Konsistente Gesichter und exakte 3D-Geometrie lassen sich aus den vorhandenen Bildmodellen allein nicht ableiten.

Bei automatischer Produktion wählt der lokale Textaufruf einen exakt belegten Ausschnitt aus dem fertiggestellten Kapitel. Der Composer kombiniert Ausschnitt, Figuren, Profil, lokales Licht und Bildaufgabe und übergibt den Auftrag über `/studio/api/compose` und `/studio/api/jobs`. Das Studio persistiert die konkrete Anfrage, Profilmetadaten, Seed, Status und ID. Nach dem Neustart verfolgt es bereits angenommene Aufträge anhand der gespeicherten Job-ID. Für eine ausdrücklich abgewiesene GPU-Zuweisung gibt es begrenzte Wiederholungen. Die Textfassung bleibt bei Bildproblemen abrufbar.

Markdown und MDX verweisen relativ auf `images/<ID>.png`. Das ZIP enthält beide Fassungen, die referenzierten Original-PNGs und `images/metadata.json` mit Alt-Text, Format, Seed und Profilbeleg. Für Astro werden die MDX-Datei und ihr Ordner `images` gemeinsam übernommen.

## Technischer Umfang

| Dateien | Änderung |
|---|---|
| `libexec/creative_studio_visual.py` | Vorlagen, Profilpersistenz, Formate, Visual Bible und Composer |
| `libexec/llama-creative-studio` | Profil-API, lokale Compose- und Job-Anbindung, Chat-Routing, Bildvalidierung und ZIP |
| `libexec/creative_studio_chat.py`, `libexec/creative_studio_organizer.py` | Profilinitialisierung und Duplikate mit eigenen Referenzen |
| `libexec/creative_studio_production.py` | Schlüsselszenen, Profilstand, Bildbelege und Exportzuordnung |
| `packages/creative-studio/web/src/lib/{visual,studio,studio-ui,production}.ts` | Einstellungen, Visual Bible, Fehlermeldungen, Chat-Bilder und Bilddetails |
| `tests/creative-studio-{plan,production,visual}.py`, `tests/creative-studio-visual.mjs` | Regression, PNG-Prüfung, Browser und Story-Integration |
| `tests/creative-studio-real-{visuals,production}.py` | Abnahme über echte lokale Dienste und Exportprüfung |

## Lokale Abnahme am 25. November 2026

Zwei isolierte Studio-Instanzen verwendeten den vorhandenen Image-Service auf Loopback und den lokalen llama.cpp-Router. Die Renderings A bis F wurden im Story-Chat bestellt, über das lokale Archiv abgerufen und mit Pillow als PNG mit 1024 × 576 Pixeln geprüft. Szene und Seed blieben für A bis D beziehungsweise für E und F vergleichbar.

| Test | Ergebnis der Sichtprüfung |
|---|---|
| A · Anima Aesthetic | `anima/anima-film`. Horizontale, klare Winterkomposition mit Laterne und warmen Fenstern. Das erste Rendering enthält schwarze Kinobalken und interpretiert die Wetterstation als zwei Häuschen. |
| B · Painterly Storybook | `anima/anima-storybook`. Weiche, sichtbare Pinsel- und Farbflächen. Schnee und warmes Licht greifen die Vorlage auf. Die Figur bleibt auf Distanz undeutlich. |
| C · Graphic Novel | `moss/moss-comic`. Deutliche Umrisse und Schattengrafik. Die nahe Figur mit Laterne ist lesbar, mit komplexerer Treppen- und Gebäudearchitektur. |
| D · Soft Cinematic Anime | `anima/anima-film`. Ruhige, eher dunkle Dämmerung, klare Silhouette im Gegenlicht und schwarze Kinobalken im ersten Rendering. |
| E · Riff Racers Low-Poly | `moss/lowpoly-retro`. Eckige Flächen, kräftiges Rot, sichtbare Reifen und warme industrielle Kulisse. Details am Helm sind gegenüber der Referenz verändert und die Figur wirkt spitzer und stärker stilisiert. |
| F · Riff Racers High-Poly | `z-image` mit Compose-Vorlage. Feinere Reifen- und Bodenmaterialien, stärkere Metallreflexe und erkennbares rot-schwarzes Farbschema. Die Pose und die vergrößerten Räder weichen vom Referenzkart ab. |

Für E und F wurden die lokalen Riff-Racers-Referenzen zu Mika Blaze und dem Hard Rock Kart als Anhänge erfasst und ihre sichtbaren Merkmale in die Visual Bible übertragen. Die beiden Vergleichsaufträge verwendeten diese Textmerkmale. Die Winterserie zeigt Blau, Violett und warmes Fensterlicht. Die Metal-World-Bilder setzen Amber, Graphit und gesättigtes Rot ein. Damit unterscheiden sich die beiden getesteten Farbwelten sichtbar.

Ein eigener Anima-`img2img`-Auftrag mit hochgeladenem Kapitelbild lieferte ein gültiges 16:9-PNG. Die Vorlage prägte den Bildaufbau sichtbar und übertrug ihre schwarzen Balken in das Ergebnis. Beim ersten neuen Textauftrag blieben die Balken sichtbar. Der zweite Test mit dem überarbeiteten Composer und `anima-film` füllte die gesamte 16:9-Fläche. Dieser Render zeigt eine zusätzliche Figur an der Tür. Figurenanzahl, Architektur und Referenztreue bleiben Kandidaten für die Sichtprüfung einzelner Motive.

| Test | Nachweis |
|---|---|
| G · Profilwechsel | Firefox speicherte Graphic Novel mit 4:3 und änderte eine getrennte Geschichte per Chat zu Painterly Storybook. Die jeweils andere Einstellung blieb erhalten. |
| H · Persistenz | Die isolierte Instanz wurde während einer akzeptierten Z-Image-Generierung und später mit einem wartenden Story-Bildauftrag neu gestartet. Die zugehörigen Profile, Nachrichten und abgeschlossenen Bilder waren weiter verfügbar. Der wartende Kapitelbild-Auftrag setzte mit derselben Studio-ID fort. |
| I · Manueller Bildwunsch | Firefox öffnete das echte Anima-Bild aus dem betreffenden Chat mit Modellbeleg, lud das Bild herunter und speicherte es als Titelbild des Testkontexts. |
| J · Automatische Produktion | „Winter Signal“ fertig mit 62 und 86 Wörtern, zwei Kapitelbildern und einem Titelbild. Die Kapitel nutzten `anima-film`, das Titelbild `anima-landscape`. Das Studio übernahm nach einem Neustart den bereits laufenden Titelbildauftrag über dieselbe Dienst-ID. Alle drei Bilder blieben im Chat und im Export zugeordnet. SQLite meldete `ok`. |

In J lief der Text über die lokalen Router-Aliase `creative-writing` und `research`. Ada ist in den drei Bildern am dunklen Haar, roten Mantel und der Laterne wiederzuerkennen. Das Titelbild setzt die Figur in die offene Schneelandschaft. Kapitel 1 illustriert den Weg am Tor, Kapitel 2 die vereiste Tür. Kleidungsdetails und die Architektur variierten leicht. Der ZIP-Export enthält drei PNGs, ihre Metadaten und beide Textformate. Eine isolierte Astro-Seite baute das exportierte MDX und löste alle drei Bildpfade auf.

Insgesamt waren 68 Python-Prüfungen und API-Prüfpunkte erfolgreich. Darunter liegen ein simulierter Acht-Kapitel-Lauf mit neun unterschiedlichen Profilbild-IDs und Tests für fehlerhafte PNGs, alte Textfassungen, GPU-Ablehnung und fehlende Katalogkombinationen. Zwei Firefox-Durchläufe, der Astro-Build, TypeScript und die lokalen Semgrep-Regeln für dynamische Codeausführung und Shell-Aufrufe liefen ohne Beanstandung.

Die lokalen Rendering- und Browserartefakte liegen unter `output/visual-profiles.UN6Lo2/`. Die Bildtests liefen über den vorhandenen Image-Service mit den vorhandenen Modellprofilen. Ein zunächst mit der Standard-URL gelaufener API-Smoke-Test legte ein synthetisches Testprojekt und einen Rechercheauftrag an. Das Testprojekt ist archiviert, der Rechercheauftrag pausiert. Der API-Smoke-Test wurde danach an der getrennten Fixture wiederholt.

```bash
python3 tests/creative-studio-visual.py
python3 tests/creative-studio-production.py
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:18743 node tests/creative-studio-production.mjs
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:18741 node tests/creative-studio-visual.mjs
python3 tests/creative-studio-real-visuals.py --url http://127.0.0.1:18741 --out output/visual-comparison
python3 tests/creative-studio-real-production.py --url http://127.0.0.1:18741 --output output/visual-production --chapters 2 --minimum 45 --maximum 110 --visual-profile anima-aesthetic
```

Die Firefox-Produktionsfixture wird mit `python3 tests/creative-studio-production.py --serve-fixture 18743` gestartet. Die Tests auf Port 18741 setzen eine isolierte Studio-Instanz am tatsächlichen Bilddienst voraus. Der Produktions-Watcher liest die IDs eines angelegten Testlaufs aus `run.json` im Ausgabeverzeichnis. Dort liegen auch die gerenderten Bilder, Profilstände und Auftragsdaten.

Spätere Verbesserungen können mehrere Referenzansichten eines Fahrers und seines Karts prüfen, sofern der lokale Dienst ein solches Verfahren bereitstellt. Ein visueller Abgleich auf Figurenanzahl und auffällige Balken wäre ein eigener Prüfpunkt neben der bereits automatisierten Dateivalidierung.
