# Pi prompt templates (slash commands)

Ship from `config/prompts/*.md`, installed to `~/.pi/agent/prompts/`
(existing user copies are never overwritten). Templates are short pointers:
they reference the central skill collection and project rules, they never
duplicate rulebooks. No name clashes with native Pi commands.

| Command | Purpose | Skill anchors |
| --- | --- | --- |
| `/finish` | wrap-up: open tasks -> tests -> new errors -> git diff -> security -> docs -> acceptance -> known limits; no push/deploy | testing-qa, ultimate-code-review |
| `/review` | read-only diff review, findings by severity with file:line, new vs existing errors | ultimate-code-review, ultimate-code-quality-refactoring |
| `/fix-ci` | reproduce first, smallest fix, retest; after 2 same failures re-evaluate cause, no repeat loops | ultimate-testing-qa |
| `/finish-docs` | docs drift vs code, CHANGELOG short entry German+English, no tokens/session data | human-writing, documentation |

Usage in Pi: type the command name in the chat prompt (`/finish`). They are
deliberately terse so a 35B-A3B model keeps the whole workflow in one pass.
