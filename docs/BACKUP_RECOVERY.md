# Backup & recovery

`./setup.sh backup` -> timestamped archive in
`~/.local/state/localllma-setup/backups/` (router/webui/writing configs,
systemd user units, Pi settings/auth/MCP/models-store).
`./setup.sh restore [file]` validates JSON and models.ini, then redeploys and
reloads units. Without an argument the newest archive is used.

Model weights (37.1 GB) are not in the archive: keep your own copy of
`~/models/gguf` or refetch with `--download-models` (pinned revisions,
checksums, resumable). CUDA runtime libs are covered by
`packages/cuda-libs.sha256` when restoring from a library backup.

`./setup.sh uninstall` saves managed configs into
`~/.local/state/localllma-setup/uninstall.*` first; models and user data stay
unless `--remove-models`. Doc refreshes back up once into
`~/.local/state/localllma-setup/doc-backup/`.

Session data (Pi sessions, WebUI chats via Import/Export) belongs to normal
user backups - the setup never deletes them.

## Pi harness rollback

Use `./setup.sh backup --pi-only` to save Pi configuration files and the
managed launcher links. Setup also creates a pre-switch backup for an
existing installation. Run `./setup.sh restore --pi-only /path/to/backup.tar.gz`
to restore an earlier release link. The corresponding release directory
must still be present. Run `./setup.sh uninstall --pi-only` to return to
the launcher saved before the managed install. This leaves project sessions
and checkpoints in the local Pi state directory.
