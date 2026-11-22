# llama.cpp on the Framework Laptop 16

1. Open **llama.cpp** in the KDE application menu. The starter launches the user service and opens [Llama Chat](http://127.0.0.1:8080).
2. Pick the model at the bottom of the chat. **research** is for everyday work, documents, web search, and deep research. **coding-cyber-tiel-35b** opens Cyber-Tiel. **creative-writing** is for stories and dialogue. The model loads on first access.
3. For text documents, choose **+** and **Add files**. Reopen a conversation from the chat history, or use **Import/Export** in the settings menu.
4. Open **MCP Servers** via the MCP entry in the sidebar. It lists **Websearch & Deep Research**, **Context7**, **GitHub**, and **Skill-Sammlung (read-only)**. [Open MCP Servers](http://127.0.0.1:8080/#/mcp-servers)
5. Select **research** in the chat and, if needed, the desired MCP server under **+ → Tools**. Example task `Suche mit search_web nach der offiziellen Python-Dokumentation zu Decimal. Gib die URL aus dem Tool-Ergebnis an.` Confirm a single call with **Allow once**. For Deep Research, choose **deep-research**, start the job with `deep_research`, then poll it with `deep_research_status` and the job ID. The profile uses the same Gemma file with a shorter thinking budget for the synthesis.
6. You can have the skill collection read with `read_text_file`. Example `Lies das Human-Writing-SKILL.md aus unserer lokalen Skill-Sammlung und nenne die Regel für Überarbeitungsschritte.` The writing profiles load their Human-Writing rules automatically while writing.

In a reopened chat, select an existing profile if needed. The KDE starter always uses `http://127.0.0.1:8080`. Use this address to reach the same chats, MCP entries, and approvals.

## Writing with StyleTune

In a new chat, pick **creative-writing**, **human-writing**, **human-rewrite**, or **human-audit** at the bottom. These profiles use the same StyleTune file and load the Human-Writing skill automatically. **creative-writing** fits stories or scenes. **human-writing** fits blog posts, reviews, and devlogs. **human-rewrite** edits existing text. **human-audit** returns findings.

Put the task on the first line and the source text or style samples below it. Optional tags at the start explicitly control language, mode, or genre.

- `[en] [fiction] Write a Riff Racers paddock scene from Cleo's point of view.`
- `[de] [editorial] Schreibe einen Blogartikel aus diesen drei Beobachtungen.`
- `[de] [rewrite] Überarbeite den folgenden Abschnitt. Lass Zitate und Links exakt stehen.`
- `[en] [audit] Audit the prose below for vague claims and repetition.`
- `[de] [voice] Kalibriere meinen Stil anhand dieser drei Textproben.`
- `[website-audit] Prüfe diese HTML-Auszüge oder diesen Auditbericht.`
- `[website-rewrite] Erstelle Ersatzvorschläge für die freigegebenen Textstellen.`

Regular writing and checking of pasted text run offline. For an actual retrieval, start with `[web]`, „Recherchiere im Web" or „Verwende ausdrücklich unseren Websearch MCP". Enable the existing Websearch tool under **+ → Tools → Websearch & Deep Research** if needed. The command for the additional text-linter check with a saved file is in [SETUP.md](SETUP.md#human-writing-in-the-webui).

### Fact sheets from sources

1. Create a fact sheet in the **research** profile. Example task `Sammle nur Belege zur Fragestellung. Liste pro Fakt eine ID, die genaue Aussage, den Quellenausschnitt und die URL. Markiere Widersprüche und fehlende Belege. Schreibe noch keinen Artikel.` For devlogs and other internal topics, you can paste confirmed notes, test results, or text excerpts yourself as the fact sheet.
2. Switch to **human-writing**. Paste the fact sheet under `[fakten] [de] Schreibe aus F1, F2 usw. Setze zu jeder Tatsachenbehauptung die passende F-ID. Wenn die Belege kurz sind, darf der Text kürzer ausfallen.` Repeat `[fakten]` for follow-up tasks bound to sources.
3. Review the draft in a separate **research** chat. Give the model the fact sheet and the draft. Ask for unbacked claims, shifts in meaning, and observations the author only inferred. Have **human-rewrite** trim the flagged passages on purpose. For important claims, check the original source.

### Stories with a word target

Split a story with a 1,200-word target into four scenes of about 300 words each. Give StyleTune the next plot step, the previous scene, and the desired character voices per request. Then count the words in the assembled text. If a section comes up short, add a concrete plot step at that spot.

## Local coding

Both commands start **Coding Long 256K** with Cyber-Tiel. The context window covers 262,144 tokens and the output target is 8,192 tokens. In Claude, `/context` shows the usage, `/status` the local server, and `/autocompact` the configured window value. [Measurement and rollback](PERFORMANCE_OPTIMIZATION.md)

```bash
claude-local
codex-local
```

Long attachments can be spread across multiple inputs. Keep follow-up questions in the same conversation. On unload, the router loses the stored prompt state.

Research and inference can be controlled individually:

```bash
systemctl --user status llama-cpp.service llama-cpp-research.service llama-cpp-mcp.service
systemctl --user stop llama-cpp.service
```

Starting again from the application menu brings the interface back. Details are in [SETUP.md](SETUP.md) and [MODEL_BENCHMARKS.md](MODEL_BENCHMARKS.md).
