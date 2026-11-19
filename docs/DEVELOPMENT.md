# Development & maintenance

- Validate changes: `bash -n` + `shellcheck` + `bash tests/unit.sh` +
  `python3 .github/links.py`; CI mirrors the same gates (GitHub Actions,
  `ci.yml`). CUDA/Fedora integration lanes stay local: GPU results must come
  from the real laptop, so CI never fakes them and never downloads GGUFs.
- Release bumps: edit the pinned versions in `setup.sh`
  (`release`, `pi_version`), manifest rows (`packages/models.tsv`,
  `artifacts.tsv`, lockfiles), then `./setup.sh` twice (gate + install) and
  `./setup.sh test`. Models only move through manifest edits, never silently.
- Adding a knob: measure first (benchmarks/), document tested vs experimental
  vs rejected in PERFORMANCE.md; experimental stays opt-in.
- New managed files: add to install + uninstall + backup paths together, or
  drift and leftovers appear.
- Docs: English pages here, installed German record in docs/*.md stays the
  measurement history; both refresh into `~/.config/llama.cpp` with backups.
- Pi internals come from the official docs (docs.pi.dev); only the wiring
  (auth/settings/MCP templates) is owned here. Skills live in the external
  collection repo; changes belong there, not here.
