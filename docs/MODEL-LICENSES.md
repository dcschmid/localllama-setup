# Modell-Lizenzen und Herkunft (Stand 2026-11-24)

Revisions-Pins sind die beim Download verwendeten HF-Commits. Kommerzielle
Verwendbarkeit bewertet am 24.11.2026 gegen die HF-Repo-Tags und die
offizielle Google-Gemma-4-Lizenzlinie.

## 1. research-code — HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP

- Datei: `Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf`
  (16.796.015.520 B), Revision `f9093662a2e7ae0503f637088bc96f77a1a70c83`
- Repo-Lizenztag: `license: gemma` (Googles proprietäre „Gemma Terms of
  Use“, nicht Apache)
- Basis: `google/gemma-4-26B-A4B-it`,
  Revision `4d7ae4984b7d…`, Tag `license: apache-2.0`; die offizielle
  Gemma-4-Linie ist laut ai.google.dev/gemma/terms unter Apache 2.0
  veröffentlicht („For Gemma 4 terms, see the Gemma 4 license“).
- **Ungeklärter Prüffall:** Das Quant-Repo trägt `license: gemma`
  (Terms-of-Use-Linie der Gemma-1…3-Ära), obwohl die Gemma-4-Basis Apache
  2.0 trägt. Eine auflösende Erklärung im Repo fehlt.
- Bewertung: Lokaler Betrieb OK. **Kommerzielle
  Produktionsfreigabe: BLOCKED**, bis die Diskrepanz Repo-Tag vs.
  Apache-Basis geklärt ist. Die Gemma Terms of Use erlauben zwar
  kommerzielle Nutzung mit Redistribution-Auflagen, aber die
  Kette google(Apache) → HauhauCS(Terms) ist widersprüchlich dokumentiert.
- Alternativpfad bei Klärungsbedarf: das Basisquant direkt von Google oder
  ein apache-getaggtes Gemma-4-26B-A4B-Quant verwenden.

## 2. story — UltimateIntent/Gemory-26B-A4B-GGUF

- Datei: `Gemory-26B-A4B-Q4_K_M.gguf` (16.796.016.096 B),
  Revision `a8bb79d670874513c76a56f341f6cdba62615744`
- Repo-Lizenztag: `license: apache-2.0`; README verweist auf die offizielle
  Gemma-4-Model-Card und Huihui-Basis als Apache-2.0-Quelle.
- Kette: google/gemma-4 (Apache 2.0) → Fine-Tune (Apache 2.0) → mradermacher-artige
  GGUF-Qants. **Kommerzielle Verwendung: OK** (Apache 2.0, NOTICE/Attribution
  bei Weitergabe beibehalten).
- Sampler-Hinweis der Modellkarte: Q4-Varianten sind sampler-sensitiv;
  BF16 und Q4 shippen bewusst unterschiedliche
  Temperatur-Defaults (Q4 gut bei ~0,2–0,7, BF16 eher 0,8–1).
  Frontend-Overrides möglich; für Story-Rollout gemessen statt geraten.

## 3. article — mradermacher/gemma-4-Ortenzya-…-i1-GGUF

- Datei: `gemma-4-Ortenzya-The-Creative-Wordsmith-31B-it-uncensored-heretic.i1-Q4_K_M.gguf`
  (18.687.064.288 B, ungesplittet, Imatrix), Revision
  `51774f0ee14665c9b18b7bef9b60f6899eb9687e`
- Repo-Lizenztag: `license: apache-2.0`; Basis
  `llmfan46/gemma-4-Ortenzya-The-Creative-Wordsmith-31B-it-uncensored-heretic`
  (`license: apache-2.0`, Revision `5e93f3877d37…`), seinerseits
  Fine-Tune von Gemma 4 (Apache 2.0).
- Kette durchgängig Apache 2.0. **Kommerzielle Verwendung: OK.**
- 31B-dense: langsamer als die 26B-A4B-MoEs; für lange Prosa messen
  (Dekoderrat, RAM-Spitze), nicht auf die leichte Schulter nehmen.

## Quellen

- https://ai.google.dev/gemma/terms (Gemma-4-Hinweis auf Apache-Linie)
- https://huggingface.co/google/gemma-4-26B-A4B-it
- https://huggingface.co/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP
- https://huggingface.co/UltimateIntent/Gemory-26B-A4B-GGUF
- https://huggingface.co/mradermacher/gemma-4-Ortenzya-The-Creative-Wordsmith-31B-it-uncensored-heretic-i1-GGUF

SHA-256 der lokalen Dateien werden nach Download-Ende in
`~/restore/2026-11-24-gemma4-256k-migration/new-models-sha256.txt`
manifestiert und gegen die hier gepinnten Revisionen geprüft.
