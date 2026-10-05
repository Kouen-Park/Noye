# Phase 7 item 5: workspace backup and restore

Desktop Settings → Workspace creates a portable ZIP containing originals, SQLite
conversations/documents/evidence and files under documents. SQLite's backup API
includes committed WAL data. Credentials, preferences, logs, models and Qdrant
storage are excluded. Unsaved editor text is not a saved database record.

Backup briefly excludes database requests and library mutation through a shared
single-process boundary. Active requests, rebuilds, uploads, ingestion or deletion
cause a visible conflict; Noye does not wait indefinitely or take a mixed snapshot.
Files changing externally during copying/final verification cause rejection.
Close other writers before backup; this is not an OS-level filesystem snapshot.

Each archive has versioned metadata, portable source paths, file lengths and SHA-256
checksums. Restore checks all entries, database integrity/relationships/schema and
the missing-source inventory in staging. It rejects path traversal, links, custom
database triggers/views, duplicates, partial archives and newer schema versions.
The format supports at most 20 GiB uncompressed and 100000 entries; desktop download
currently uses a browser Blob, so large-workspace memory behavior needs measurement.
The backup is not encrypted; store it as private workspace data.

Restore publishes into an exclusively created new folder and never overwrites an
existing directory, including an empty one. Originals, saved writing and evidence
remain independent of the active workspace. Missing originals are reported while
saved writing survives. Restored files cannot answer questions until an explicit
rebuild; no model is downloaded and no vectors/credentials are imported. The item 7
desktop integration connects the separate explicit workspace switch.

The protected desktop API uses the existing per-process control capability:
GET /workspace, POST /workspace/backup and POST /workspace/restore. Restores choose
a new sibling directory rather than accepting arbitrary browser-supplied paths.
A closed-workspace CLI restore is also available:
python backend/desktop.py --data-dir NEW_DIRECTORY --restore-backup BACKUP.zip

Validation at the service checkpoint: 758 backend tests passed, 19 skipped; the 15
backup regressions then passed again after exclusive archive creation was hardened.
They exercise committed WAL edits, exact historical evidence, original preservation,
missing originals, legacy migration, invalid archives and snapshot contention.
Frontend: 209 tests passed, including 3 new user-flow cases. No real user workspace,
credential or vector index was modified. Native switch, real native downloads and
large-workspace/low-disk behavior remain for the integration checks.
