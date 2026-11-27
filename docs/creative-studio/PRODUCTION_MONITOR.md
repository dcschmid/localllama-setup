# Produktionsansicht und Live-Aktivität

Die Produktionsansicht steht im selben Story-Chat wie der Auftrag. Sie zeigt ausschließlich gespeicherte Backend-Zustände und beobachtete Live-Signale. Es gibt keine geschätzten Prozentwerte, keine Animation als Fortschrittsersatz und keine vom Modell erzeugten Protokolleinträge.

## Der Fehlerfall „Donner über Thunderforge“

Der Job `71410090…` steht in der Datenbank auf **`failed`**, Schritt `reviewed`, Kapitel 2, Fehler `story_length_failed`. Die frühere Karte leitete ihre Überschrift „Kapitel 2 wird verbessert“ allein aus dem Schrittnamen `reviewed` ab, zeigte also Arbeit an, obwohl der Job beendet war. Die Karte bildet den Zustand jetzt nur noch aus dem gespeicherten Jobstatus. Der Schrittname ändert ihn nie.

Aus dem gespeicherten Kapiteltext berechnet die Ansicht für diesen Job: 827 von mindestens 900 Wörtern (Obergrenze 1.200), 73 Wörter fehlen, vier automatische Erweiterungsversuche wurden verworfen, letzter Checkpoint ist Kapitel 1 mit 1.053 Wörtern und Bild.

## Zustände

`monitor.state` kommt aus `libexec/creative_studio_monitor.py` und folgt der Zustandsmaschine der Jobtabelle:

| Zustand | Quelle |
| --- | --- |
| Wird vorbereitet | `queued`, oder `running` ohne gespeicherte Schrittereignisse |
| Läuft | `running`, Backend-Schritt ohne offene Modellanfrage |
| Wartet auf Modell | `running`, Schreib- oder Planungsschritt mit offener Modellanfrage |
| Wird überprüft | `running` in einem Audit- oder Validierungsschritt (`auditing`, `rewrite_audit`, `text_finalize`, `image_archive`, `manuscript`, `final_validation`, Planungsprüfung) |
| Wird automatisch korrigiert | `running` im Schritt `reviewed` (Korrektur bestätigter Befunde, Szenenerweiterung) |
| Wird erneut versucht | `running` mit gespeichertem `retry` und ohne Fehler (höchstens zwei automatische Versuche) |
| Pausiert | `paused` durch den Nutzer, die Kapitelfreigabe, die Bildfreigabe oder einen auto-korrigierbaren Sprachbefund |
| Benutzerentscheidung erforderlich | `paused` mit bestätigtem, nicht selbstständig lösbarem Konflikt (`pause_reason=blocker`) |
| Fehlgeschlagen | `failed` |
| Abgeschlossen | `completed`, alle Exportdateien geprüft |
| Unvollständig | `completed`, aber geprüfte Exportdatei fehlt |
| Verbindung unterbrochen | nur im Browser: Abrufe schlagen fehl. Der Jobzustand bleibt der zuletzt bekannte |

Eine unterbrochene Browser-Verbindung bricht nie einen Job ab. Der Worker läuft in der Studio-Prozessinstanz weiter und setzt nach einem Neustart am gespeicherten Schritt an. Nach einem Browser-Neustart liest die Ansicht Zustand, Kapitel, Bilder und den persistenten Verlauf aus dem Backend und verbindet sich neu.

## Heartbeat, Fortschritt und Stalled-Erkennung

`libexec/creative_studio_activity.py` führt im Speicher des Studio-Prozesses ein Register der tatsächlich beobachteten Signale:

- **Heartbeat**: Ein Monitor-Thread bestätigt alle 2 Sekunden, dass der Produktions-Worker-Thread lebt und diesen Job ausführt. Der Heartbeat beweist die Erreichbarkeit des Workers, nicht den Fortschritt des Modells.
- **Fortschritt**: letzter gespeicherter Zwischenstand, gesendete oder beantwortete Modellanfrage, oder ein Token-Zähler des Modell-Slots, der sich bewegt hat.
- **Modellanfrage**: `production_model` meldet Start, Modell, Rolle, Promptgröße und Zeitlimit. Der Monitor liest alle 4 Sekunden `/slots?model=<alias>` des llama.cpp-Routers. `is_processing` mit `n_decoded = 0` ist Prefill, `n_decoded > 0` Generierung, ein bewegter Zähler ist Fortschritt. Nach der Antwort bleiben Token (`usage.completion_tokens`), Zeichenzahl, Dauer und Ergebnis (`ok`, `timeout`, `error`) erhalten.

`health.level` unterscheidet:

| Stufe | Bedeutung |
| --- | --- |
| `ok` | Fortschritt innerhalb der Schwelle, oder das Modell meldet bewegte Token |
| `waiting` | Der Worker bearbeitet zuerst einen anderen Auftrag |
| `quiet` | Länger als die Schwelle kein bestätigter Fortschritt. Die Ansicht schreibt: „Seit längerer Zeit kein neuer Fortschritt bestätigt. Der Prozessstatus wird überprüft.“ |
| `stalled` | Geprüft: Das Modell hat nach der Stalled-Schwelle keine neuen Token geliefert, oder der Slot ist für die offene Anfrage leer |
| `worker_down` | Der Worker-Thread läuft nicht, oder sein Heartbeat blieb länger als 20 Sekunden aus |

Ein langer Prefill wird nie als `stalled` gemeldet. Er endet am Modell-Zeitlimit (600 Sekunden je Anfrage, Artikel 1.800), das den bestehenden Retry mit höchstens zwei Wiederholungen auslöst. Ein Zeitlimit zeigt die Ansicht als „Die Modellanfrage hat das Zeitlimit überschritten“. Der Fehlerzustand bleibt `failed`, der gespeicherte Stand bleibt erhalten.

Die Schwellen in Sekunden sind je Schritt konfigurierbar (`quiet` / `stalled`, Standard Schreiben 480 / 2.400, Prüfung 600 / 2.400, Bild 900 / 3.600):

```bash
CREATIVE_STUDIO_ACTIVITY='{"writing": {"quiet": 900, "stalled": 3600}}' llama-creative-studio serve
```

## Ereignisse und Übertragung

- `GET /api/production/jobs/<id>` liefert das Job-Objekt mit dem neuen Feld `monitor`.
- `GET /api/production/jobs/<id>/events` ist ein Server-Sent-Events-Strom. Er sendet `job` (vollständiger Datensatz, sobald sich etwas ändert), `heartbeat` (Server-Zeit, Health, Modellstatus, etwa alle 2 Sekunden) und `end` bei einem abgeschlossenen, abgebrochenen oder unvollständigen Job. Fenster von 10 Minuten, der Browser verbindet sich selbst neu.
- Ohne frischen Strom fragt der Browser wie zuvor alle 1,8 Sekunden ab. Der Strom ersetzt das Polling nur solange er liefert.

Der **Aktivitätsverlauf** besteht aus den persistenten Schrittereignissen `result.events` des Jobs (Zeitpunkt, Schritt-ID `<Kapitel>:<Schritt>`, Status, Dauer, Versuche, Wortzahl und Korrekturen) sowie dem Start des Auftrags. Bei Fehlern steht die technische Referenz `<Job-ID 8>/<Ereignis>/<Fehlercode>` dabei. Ältere Jobs haben weniger Details, nie erfundene.

## Wortzahl und Verlängerung

`monitor.length` wird aus dem gespeicherten Kapiteltext der aktuellen Version berechnet (aktuelle Wortzahl, Mindest- und Höchstzahl, fehlende oder überzählige Wörter, Anzahl der Erweiterungsversuche und ihre Ursachen). Gibt es keinen gespeicherten Text, bleibt das Feld leer, und die Ansicht zeigt keine Zahlen.

Die automatische Verlängerung (`chapter_expansion`) schreibt eine zusätzliche Szene an einem vorhandenen Anschlusspunkt. Jeder verworfene Versuch speichert jetzt seine Ursache (`anchor`, `empty`, `placeholder`, `aside`, `repetition`, `range`) und den Zeitpunkt. Der nächste Versuch bekommt diese Ursache im Prompt genannt. Die Grenze von zwei Versuchen je Durchlauf bleibt. Danach nennt die Ansicht die konkreten Ursachen, den letzten Checkpoint und die möglichen Aktionen.

## Aktionen

| Zustand | Aktionen |
| --- | --- |
| läuft, wartet, überprüft, korrigiert, erneuter Versuch | Pausieren, Details anzeigen. Kein Retry-Knopf |
| pausiert | Fortsetzen (bzw. Kapitel freigeben, Bilder prüfen), Details anzeigen, Abbrechen |
| fehlgeschlagen | Fehlgeschlagenen Schritt erneut ausführen, Gespeicherten Text öffnen, Details anzeigen, Abbrechen |
| Entscheidung erforderlich | Konkreten Konflikt bearbeiten, danach Fortsetzen, Details anzeigen |
| abgeschlossen | Manuskript öffnen, Bilder ansehen, Markdown, MDX, ZIP herunterladen |

Ein Knopf wird nach dem Klick je Job und Aktion gesperrt. Die Server-Zustandsprüfung (`production_transition_invalid`) verhindert zusätzlich doppelte Übergänge. Ein zweiter Klick erzeugt weder einen zweiten Job noch eine Fehlermeldung.

## Barrierefreiheit

Zustände haben Text und Symbol, nie nur Farbe. Fortschritt ist als `<progress>` mit Namen und Wert ausgezeichnet. Kapitel, Verlauf und technische Details sind `<details>` und per Tastatur bedienbar. Der Fokus bleibt bei Aktualisierungen erhalten (Knöpfe und `<summary>`). Der Live-Bereich `#announcement` meldet nur Zustandswechsel (Pause, Wiederholung, Fehler, Abschluss, Entscheidung), Kapitelwechsel, bestätigte Stillstandsstufen und den Verbindungsverlust. Tokenzahlen und Zeitangaben werden nie angesagt. Die Ansicht enthält keine Animationen, `prefers-reduced-motion` ist damit erfüllt.

## Prüfung

```bash
python3 tests/creative-studio-monitor.py            # Zustände, Heartbeat, Stalled, Wortzahlen, echter Job (read-only Kopie)
python3 tests/creative-studio-production.py --serve-fixture 18702
CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:18702 node tests/creative-studio-monitor.mjs   # Firefox, Szenarien, Layout, axe
```

Den echten Job prüft derselbe Browsertest auf einer privaten Kopie der Live-Datenbank. `python3 tests/creative-studio-monitor.py --serve-real 18731` kopiert `studio.sqlite3` und die Kapitelbilder des Jobs in ein Temporärverzeichnis, bricht dort fremde aktive Jobs ab und richtet alle Upstream-Dienste auf einen geschlossenen Port. Danach `CREATIVE_STUDIO_REAL_URL=http://127.0.0.1:18731 CREATIVE_STUDIO_REAL_SESSION=<Chat-ID> node tests/creative-studio-monitor.mjs`. Die Live-Datenbank wird nur gelesen.

## Einschränkungen

- Das Register der Live-Signale liegt im Speicher des Studio-Prozesses. Nach einem Neustart fehlt der Heartbeat bis zum nächsten Schritt, gespeicherter Stand und Verlauf bleiben.
- Die Modellanfrage ist nicht gestreamt. Token-Zähler und Prefill/Generierung stammen aus `/slots` des Routers. Meldet er keine Slots, schreibt die Ansicht „Der Modellfortschritt ist nicht einsehbar“ und erklärt die Anfrage nicht für hängend, bis das Zeitlimit greift.
- Der Heartbeat bestätigt den Worker-Thread. Ein blockierter Thread innerhalb eines Aufrufs zeigt sich nur über das Zeitlimit.
- Bildaufträge laufen im Bilddienst. Die Ansicht zeigt deren gespeicherten Zustand, keine Bildtoken.
- Screenreader-Verhalten ist durch DOM-Semantik, Live-Bereich und axe-core (WCAG 2.2 A/AA) geprüft, nicht mit einem echten Screenreader (Orca, NVDA) gehört. Das bleibt eine manuelle Abnahme.
- Die Browsertests `creative-studio-workflow`, `-visual` und `-planning` schlagen auch auf dem unveränderten Stand fehl. Das hat mit dieser Änderung nichts zu tun.
