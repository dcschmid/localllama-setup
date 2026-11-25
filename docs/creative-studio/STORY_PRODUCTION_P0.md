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
