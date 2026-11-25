# Designprüfung für Local Creative Studio

Die Empfehlung ist **A · Minimal Creative Assistant** als Startansicht. Ein wieder geöffnetes Projekt kann die einklappbare Projektübersicht aus B verwenden, sobald ein Dokument im Chat bearbeitet wird. Diese Platzierung hält den Einstieg frei und gibt laufender Arbeit einen festen Kontext.

## Varianten öffnen

Im Repository starten und im Browser öffnen.

```sh
python3 -m http.server 4370 --bind 127.0.0.1 --directory docs/creative-studio/prototypes
```

| Entwurf | Einstieg | Projektarbeit |
| --- | --- | --- |
| [A · Minimal Creative Assistant](http://127.0.0.1:4370/?design=a) | Ein Chatbereich auf warmer Papierfarbe, Terrakotta für Aktionen, vier Vorschläge als Zeilen mit feinen Trennlinien | Projekte über die Seitenleiste. Der Editor erscheint beim Öffnen eines Entwurfs. |
| [B · Creative Workspace](http://127.0.0.1:4370/?design=b) | Chat mit Olivpalette und „Weiterarbeiten“ am rechten Rand. Auf Mobilgeräten folgt die Projektliste auf das Eingabefeld. | Zuletzt bearbeitete Projekte mit Typ, Arbeitsstand und Zeitpunkt. Im Editor lässt sich die Projektübersicht aufklappen. |

Beide Entwürfe nutzen Noto Serif mit Georgia als Ersatz für Überschriften und Lesetext. Noto Sans mit einer Systemschrift als Ersatz hält Bedienelemente kompakt. Beide Farbmodi funktionieren mit denselben Komponenten.

Im Prototyp öffnet „Die letzte Fähre“ eine Beispielunterhaltung mit Entwurf. „Deep Research starten“ füllt einen Beispielauftrag aus. Nach dem Senden lassen sich die simulierte Pause, Quellen und offene Fragen ausprobieren. Die Demo-Datei aus dem Editor enthält den aktuellen Demo-Text. Die produktive Umsetzung von Design A läuft auf Port 8700 mit den lokalen Diensten. [Studio und Browserprüfung](../README.md)

## Befunde aus dem Bestand

Die in der Anfrage erwähnten Anhänge waren im Arbeitskontext nicht verfügbar. Firefox-Aufnahmen des laufenden Studios ersetzen sie. Die Aufnahmen zeigen Beispielnamen für Unterhaltungen und neutrale Jobbeschreibungen.

| Befund | Beobachtung und Beleg |
| --- | --- |
| Zu viele Entscheidungen beim Einstieg | Neun gleichrangige Ziele im Kopf, zwei Modellwahlen und ein zusätzlicher Profilinspektor stehen beim leeren Chat über dem eigentlichen Auftrag. Die feste Dreispaltenstruktur hält die Mitte dunkel und leer. [Startansicht im Code](../../../packages/creative-studio/web/src/pages/index.astro) · [Chat im Code](../../../packages/creative-studio/web/src/lib/chat.ts) |
| Später Datenabruf überschreibt Recherche | In Firefox öffnet „Stories“ einen Projektabruf. Währenddessen zu „Recherche“ wechseln. Nach dem Auflösen des absichtlich verzögerten Abrufs bleibt „Recherche“ aktiv, während „Stories & Romane“ und die Kapitelanleitung erscheinen. Beide Ansichten schreiben in dieselben DOM-Container. [Navigation](../../../packages/creative-studio/web/src/pages/index.astro) · [Story-Ansicht](../../../packages/creative-studio/web/src/lib/stories.ts) |
| Galerie leer trotz gespeicherter Bilder | Die API liefert eine Liste, die UI liest `images` aus einem Objekt und zeigt „leer“. Die 60 Bilder der ersten Seite waren über den Studio-Dateipfad abrufbar. Der Bilddienst lieferte 106 eindeutige Einträge über zwei Seiten. Der Studio-Proxy liefert bei weiteren Seiten und bei einem Detailaufruf wieder die erste Liste. Die UI hätte zudem bei korrekter Antwort auf 18 Einträge gekürzt. [Bildansicht](../../../packages/creative-studio/web/src/lib/images.ts) · [Proxy](../../../libexec/llama-creative-studio) |
| Vorhandene Dokumente fehlen im Export | Der Dialog filtert seine Dokumentauswahl nach `body`. Der genutzte Projekt-Endpunkt liefert Titel, Typ, Status, Version und Zeitstempel. Der Text liegt am Dokument-Endpunkt. [Exportansicht](../../../packages/creative-studio/web/src/lib/publish.ts) · [Projekt-Endpunkt](../../../libexec/llama-creative-studio) |
| Spielideen können im falschen Projekt landen | Beim Öffnen des Game Lab wird das erste Game-Projekt als Ziel vorbelegt. Die Oberfläche listet Namen in der Seitenleiste ohne Projektwahl. [Game Lab](../../../packages/creative-studio/web/src/lib/sections.ts) |

## Browserprüfung

Firefox 159.0 mit Playwright 1.65.1. Beide Entwürfe wurden bei 1440, 834, 390 und 320 CSS-Pixeln Breite in Hell und Dunkel geprüft. Die Aufnahmen zeigen die [Ausgangslage im Chat](../../../output/playwright/creative-studio/bestand-chat.png), die [leere Galerie](../../../output/playwright/creative-studio/bestand-bilder.png) und den [überschriebenen Recherchebereich](../../../output/playwright/creative-studio/bestand-navigation.png).

| Ansicht | A | B |
| --- | --- | --- |
| Desktop | [Hell](../../../output/playwright/creative-studio/a-desktop-light.png) · [Dunkel](../../../output/playwright/creative-studio/a-desktop-dark.png) | [Hell](../../../output/playwright/creative-studio/b-desktop-light.png) · [Dunkel](../../../output/playwright/creative-studio/b-desktop-dark.png) |
| Tablet | [Hell](../../../output/playwright/creative-studio/a-tablet-light.png) · [Dunkel](../../../output/playwright/creative-studio/a-tablet-dark.png) | [Hell](../../../output/playwright/creative-studio/b-tablet-light.png) · [Dunkel](../../../output/playwright/creative-studio/b-tablet-dark.png) |
| Mobil | [Hell](../../../output/playwright/creative-studio/a-mobil-light.png) · [Dunkel](../../../output/playwright/creative-studio/a-mobil-dark.png) | [Hell](../../../output/playwright/creative-studio/b-mobil-light.png) · [Dunkel](../../../output/playwright/creative-studio/b-mobil-dark.png) |
| Kontexteditor | [Desktop](../../../output/playwright/creative-studio/a-editor-desktop-light.png) | [Desktop](../../../output/playwright/creative-studio/b-editor-desktop-light.png) · [Mobil](../../../output/playwright/creative-studio/b-editor-mobil-light.png) |

Geprüft wurden Startansicht, vier Vorschläge, horizontaler Überlauf, Sprunglink, Tastaturbedienung der mobilen Navigation mit Fokus-Rückgabe, Recherchevorschau, Chat zum Entwurf, Markdown-Vorschau, Demoversion, Rückgängig, Demo-MDX-Download und Wechsel des Farbmodus. axe-core 4.14.0 meldete im geprüften Umfang keine automatisiert erkannten A- oder AA-Verstöße. Die Prüfung mit den echten Diensten fand an der produktiven Umsetzung mit temporärem Datenbestand statt. [Studio und Browserprüfung](../README.md)

Der vorhandene [API-Vertragstest](../../../tests/creative-studio.py) bestand alle 13 Prüfungen mit einer temporären Datenbank. Der Bildkatalog war über einen lesenden Proxy erreichbar. Modell- und Bildgenerierung gehören nicht zu diesem Vertragstest.

Die visuelle Prüfung bewertet A mit 92 und B mit 90 von 100 Punkten. Die Bewertungen sind heuristisch und beziehen sich auf die gerenderten Prototypen.

| Kriterium | A | B | Beobachtung |
| --- | ---: | ---: | --- |
| Eigenständigkeit | 18/20 | 18/20 | Warme Papierpalette, kleine Stiftmarke und klare typografische Stimme |
| Typografie | 14/15 | 14/15 | Serifentitel und ruhige Lesetypografie, Systemfallback bei fehlenden Noto-Schriften |
| Raum und Rhythmus | 14/15 | 13/15 | A bündelt Eingabe und Vorschläge. B teilt die Aufmerksamkeit mit der Projektspalte. |
| Passung zum Auftrag | 15/15 | 14/15 | A priorisiert freie Eingabe. B macht das Wiederaufnehmen eines Projekts sichtbarer. |
| Komponenten | 9/10 | 9/10 | Gemeinsame Bedienelemente, Dialoge und konsistente Symbole |
| Inhalt | 9/10 | 9/10 | Konkrete Beispielprojekte und deutlich markierte Beispielantworten |
| Responsive Verhalten | 5/5 | 5/5 | Reflow bis 320 CSS-Pixel, Editor als eigenständige Ansicht auf kleinen Displays |
| Bedienbarkeit | 8/10 | 8/10 | Automatisierte Prüfung und gezielte Tastaturprobe, Screenreader-Prüfung offen |

Zum Wiederholen der Prüfung erwartet das Skript `playwright` mit Firefox und `axe-core` im Node-Modulpfad. Diese Laufzeit dient ausschließlich der Prüfung.

```sh
node docs/creative-studio/prototypes/verify.mjs
```

