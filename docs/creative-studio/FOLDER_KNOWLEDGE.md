# Ordnerwissen (Folder Knowledge / Universe Bible)

Jeder Ordner kann optional dauerhaftes Wissen besitzen: beschriebene Themen,
bestätigte Fakten, Personen, Orte, Organisationen, Weltregeln, Chronologie,
Begriffe, Referenzdokumente, Bildreferenzen, visuelle Vorgaben und kreative
Ideen. Kategorien sind frei; die Liste im Dialog ist eine Auswahl, keine
Menge. Leere Ordner funktionieren exakt wie zuvor.

## Datenmodell

`libexec/creative_studio_knowledge.py` (Migration `knowledge_entries`,
`knowledge_versions`, `knowledge_suggestions` in `studio.sqlite3`). Pro Eintrag:
`id`, `folder_id`, `category`, `title`, `content`, `source`, `status`,
`version`, `created`, `updated`. Status: `confirmed` (bestätigter Kanon),
`reference` (importiert/Referenz, unbestätigt), `idea` (kreative Idee, nie
injiziert), `unresolved` (ungeklärt). Jede Änderung schreibt die Vorgängerversion
nach `knowledge_versions` (Wiederherstellen erhöht die Version neu).
Vorschläge aus Produktion/Chat liegen in `knowledge_suggestions` und werden
ausschließlich durch Nutzeraktion zu Einträgen.

## Vererbung und Konflikte

Kinderordner erben die Einträge aller Eltern (nächste Ebene gewinnt pro
`category + title`). Bestätigte Fakten mit gleichem `category + title` und
unterschiedlichem Inhalt zwischen Ebenen erscheinen in `conflicts`
(Eltern-, dann Kindeintrag) und im Injektionstext als „Konflikt … ungeklärt“;
nichts wird stillschweigend aufgelöst. Ordner ohne gemeinsamen Ast teilen kein
Wissen; das Verschieben eines Chats verschiebt die Wissenszuordnung mit (die
Zuordnung läuft über `sessions.folder_id` bzw. `projects.folder_id`).
Ordnern mit Papierkorb/Purge fallen Wissensdaten cascade mit (`ON DELETE CASCADE`).

## Automatische Verwendung (selektiv, nie als Volltext-Dump)

Injektionspunkte rufen `knowledge.context_for()` auf, das über die Ordnerkette
nach Schlüsselwort-Relevanz (`_terms`), Statuspriorität und Budget
(~10 000 Zeichen) auswählt; Ideen werden nie injiziert:

- Freier Chat (`POST /api/chat`) und Chat-Aufträge (`write_task`-Brief)
- Story-Kontext (`story.context`) und Produktions-Kanon (`payload
  "folder_knowledge"`, eingefroren bei Jobstart → Kapitelwechsel mitten im Job
  wechseln das Wissen nicht)
- Planungsschnappschuss (`planning_source → source["folder_knowledge"]`)
- Guided Writing (`_write_stream`)

Erzeugte Kapitel-Fakten (`status=established`) landen nach Jobabschluss als
Vorschläge im Ordner – nie direkt im Kanon.

## Visuelles Standardprofil

`category="visual-profile"` speichert `{template, ratio, style, palette}` pro
Ordner (Vererbung über die Kette). `knowledge.profile_default()` wendet es nur
auf Profile mit `version == 0` an – ein von Hand gesetztes Story-Profil
(`version > 0`) gewinnt immer; `seed_profile()` sichert den Standard beim
Produktionsstart in das Projekt. Einzelne Chats/Geschichten können den Stil ausdrücklich
überschreiben, ohne andere Geschichten zu ändern.

## API

- `GET /api/folders/<id>/knowledge` – Sicht (`chain/own/inherited/conflicts/
  suggestions/profile/hint`); `?format=markdown|json` → Export in `content`
- `GET /api/folders/hint?session=<id>` – UI-Hinweis (`Weltwissen: … aktiv`),
  sonst `null`
- `POST /api/folders/<id>/knowledge` – `action`: `add|update|status|versions|
  restore|delete|import|accept|keep|reject|profile` (Versionsoptimismus:
  `knowledge_stale` 409)

Frontend: Ordner-Menü → **Ordnerwissen verwalten**
(`packages/creative-studio/web/src/lib/organizer.ts`).

## Tests

`python3 tests/creative-studio-knowledge.py` – 15 Fälle inkl.
Riff-Racers-Umlauf (Thunderforge bleibt nach Import `reference`,
Ideen nie injiziert, Neustart-Persistenz).
