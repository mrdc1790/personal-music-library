# Personal Music Library contributor guidance

## Catalog safety

This local catalog preserves Spotify metadata and audit evidence. Read
`data/user-context.md` if present. It is a private, ignored record of user
reports and does not verify device state.

- Default to read-only. Account changes and migrations require an explicit
  request.
- Preserve snapshots, scan status, coverage gaps, source order, duplicate
  occurrences, and history. Failed, partial, unreadable, and unexported
  sources have unknown coverage.
- Keep credentials, tokens, personal snapshots, SQLite databases, and generated
  reports out of commits and tool output. Use `storage_paths.py` for storage
  defaults outside OneDrive Documents.
- Preserve backups, personal scan outputs, and sample mappings unless the task
  calls for changes. Maintain compatibility with existing catalogs, snapshots,
  and exports.

## Python changes

Use four-space indentation and keep the standard-library-first design. New
dependencies require explicit approval. Add focused `unittest` coverage for
behavior changes using temporary storage and synthetic data without network
access. Run the smallest relevant test file first, then broader tests for
changes spanning modules.

See [work status](docs/WORK_STATUS.md) for handoffs. The Spotify Playlist
Migrator is the sibling application.

## Navigation and verification

Use Dekko MCP for unfamiliar code and impact analysis. Resolve the current
checkout's absolute path and pass it as `root` on every call. Check each
repository's map separately with `map_status`. Refresh stale or missing maps
when supported and reuse fresh maps until relevant code changes.

Start with a compact summary and focused searches. Use file-qualified symbols
and bounded context once the target is known. Verify ambiguous calls and
consequential zero-caller results in source, including tests where relevant.
For familiar edits or unavailable indexing, use targeted `rg` and direct
source and test inspection.

Inspect Git status before editing, preserve unrelated changes, and keep diffs
focused. Keep source readable and follow existing formatting conventions.

## Cross-repository changes

Locate the sibling checkout when a task touches shared Spotify rules for
writes, saved tracks, duplicates, coverage, reconciliation, OAuth, or migration
safety. Inspect its source, tests, and docs before deciding on a companion edit.
Keep each repository independently runnable and testable. Shared runtime paths
or imports require an explicit task requirement. Edit both only when behavior,
interfaces, or documented guarantees would otherwise diverge. Report what you
checked and run relevant tests in each changed repository.

## Project tracking

Use the private [Personal Development Project](https://github.com/users/mrdc1790/projects/1)
for substantial work, work spanning repositories, or meaningful blockers.
Skip routine questions and small cleanups. Check the Project and relevant
issues for an existing item before adding one. Keep status, area, and agreed
priority current. Mark Done after verification and link the evidence. Keep
detailed plans in repository docs and private data out of tracking. If access
is unavailable, continue and report the pending update. Summarize tracking
in the final reply.
