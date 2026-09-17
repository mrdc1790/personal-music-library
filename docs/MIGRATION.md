# Spotify Shadow Track Migration

A local Python tool for backing up Spotify library data, reviewing track replacements, and executing journaled migrations where Spotify exposes sufficient identity evidence. Python 3.11+; no third-party packages or Client Secret required.

Implemented: `scan`, `plan`, `apply`, `resume`, and `rollback`. Writes require individually approved mappings and `--execute`. Without `--execute`, apply/resume/rollback inspect local files and print a summary.

**Live status:** No account scan or migration has been performed. Tests use a simulated Spotify API. A real Developer app and user sign-in are required for live validation. Development Mode scans are useful backups but are blocked from execution because the API hides original IDs.

## Review of the shared proposal

The snapshot, reverse occurrence index, reviewed mappings, and add-before-remove workflow are sound. Four details need correcting:

1. **Original IDs may be unavailable.** Spotify's [February 2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide) removes `linked_from` in Development Mode. A returned ID is not proof of the stored ID. Empty relink findings cannot establish a clean library. Raw entries and original/returned IDs are kept separately.
2. **Snapshots do not provide a transaction.** [Playlist insertion](https://developer.spotify.com/documentation/web-api/reference/add-items-to-playlist) supports positions but no compare-and-swap snapshot parameter. Reads and mutations can race. Pause all playlist edits during a run. The engine detects changes it can observe and stops, but cannot prevent every concurrent edit.
3. **Do not assume positional deletion.** The current [remove endpoint](https://developer.spotify.com/documentation/web-api/reference/remove-items-playlist) documents URI objects and a snapshot, but no per-occurrence positions. Forward migration inserts one replacement at each old occurrence, from the end backward, verifies intermediate sequences, then removes the old URI across its occurrences. Mapping chains and cycles are rejected.
4. **Rollback is not an inverse ID swap.** That would destroy pre-existing replacement occurrences. Recovery uses original sequences and saved membership. Playlist rollback uses [replace plus batched insertion](https://developer.spotify.com/documentation/web-api/reference/reorder-or-replace-playlists-items), resetting all affected playlist item dates and attribution. Local/missing entries block affected playlists; unavailable originals may still fail to re-add.

New routes are `/playlists/{id}/items`, `/me/library`, and `/me/library/contains`. ISRC metadata is available again following March's changes; it is evidence, not automatic approval. [July's changes](https://developer.spotify.com/documentation/web-api/references/changes/july-2026) describe account-wide Development Mode quotas. Read requests use bounded retries; writes never retry automatically.

Only an app that actually has **Extended Quota Mode** can use `--api-mode extended` for execution in this version. This option records the app's real capability; it does not grant it or restore fields on a Development Mode app. Old exports without an app identity require a fresh scan. Hidden-ID recovery from other exports/browser data remains manual. Fuzzy catalog search is not implemented.

## Offline example

```powershell
python demo.py
python -m unittest -v
```

The example creates a synthetic HTML report, JSON snapshot, SQLite database, and unapproved review plan under `backups/demo-*`. It includes two old occurrences plus an already-present replacement. It never connects to Spotify.

## Connect and scan

Use an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard). Set the redirect URI to exactly:

```text
http://127.0.0.1:8765/callback
```

Use the public **Client ID**, never the Client Secret. Spotify login and consent happen in the browser. Tokens stay in memory. Access depends on Spotify's current account/app eligibility, including the app owner's Premium requirement.

```powershell
python migrate.py scan --client-id YOUR_CLIENT_ID
```

For an app already granted Extended Quota Mode:

```powershell
python migrate.py scan --client-id YOUR_CLIENT_ID --api-mode extended
```

The original `Start audit.cmd` and `python audit.py` remain read-only entry points. The new command records the app mode for subsequent plans. Every scan gets a separate folder. It attempts every listed playlist and records failures, including inaccessible followed playlists. Partial scans block executable plans; there is no silent exclusion switch.

Each scan folder contains:

- `report.html`: findings and coverage notes.
- `snapshot.json`: account/app identity, playlist snapshots, raw entries, positions and duplicates.
- `library.sqlite`: indexed occurrences plus snapshot metadata.
- `migration-plan.json`: audit proposals, not executable approvals.

Backups are inside this OneDrive project by default and may sync under normal settings. Set `--output` to another folder if desired. Liked Songs have no snapshot token; pause edits during scanning. No API export can recover fields Spotify hides.

## Review and plan

Copy `mappings.example.json` to `mappings.json`. Confirm old/new recordings, artist identities, versions, explicit status, duration, and ISRC where available. The included **2 Busy** mapping is a supplied hypothesis, not a verified account fact. `approved` starts as `false`.

```powershell
python migrate.py plan --snapshot backups/YOUR_SCAN/snapshot.json --mappings mappings.json --output review-plan.json
```

Read `locations`, `playlists.before`, `playlists.after`, `liked_before`, `blocked`, and `limitations`. Positions are zero-based. All observed old occurrences are included; individual occurrences cannot be silently excluded. Metadata matches never approve themselves. Review each mapping, set its `approved` field to `true`, and regenerate with a new filename:

```powershell
python migrate.py plan --snapshot backups/YOUR_SCAN/snapshot.json --mappings mappings.json --output approved-plan.json
python migrate.py apply --plan approved-plan.json --journal backups/run-1.json
```

The last command is a dry run. Blocked plans remain blocked even if approved. Keep the original snapshot alongside the plan and journal. Executable plans must be generated by the planner; do not hand-edit their sequences.

## Execute

After reviewing the concrete plan:

```powershell
python migrate.py apply --plan approved-plan.json --journal backups/run-1.json --execute
```

This sign-in requests library/playlist modification scopes. Preflight checks the same account/app, playable exact replacement IDs, full playlist sequences and snapshots, and saved membership for every old/new URI. Each mutation is journaled before sending and verified afterward. Playlists are processed before Liked Songs. New likes are saved and verified before old likes are removed; already-saved replacements remain saved.

The journal is flushed to disk before requests and includes its plan and verified history. A lock prevents simultaneous use of the same journal. Other journals and Spotify clients are not locked, so do not run them concurrently. Keep journals private; add account files outside `backups/` to ignore rules before committing.

## Interruptions and rollback

```powershell
python migrate.py resume --journal backups/run-1.json
python migrate.py resume --journal backups/run-1.json --execute
```

Resume checks all tracked resources for later edits. A pending request whose exact result is observed can be recognized without repeating it. A definite HTTP rejection leaves the operation uncommitted. An ambiguous request whose result cannot be established stops for manual reconciliation; there is no force-retry switch. Preserve the journal and inspect the account. If a killed process left a `.lock` file, establish that it is no longer running before removing that specific stale lock.

Rollback can start after a completed or verified partial run, but not with an unresolved write:

```powershell
python migrate.py rollback --journal backups/run-1.json --accept-metadata-reset
python migrate.py rollback --journal backups/run-1.json --accept-metadata-reset --execute
```

Rollback restores original sequences, duplicate counts, and tracked saved membership, preserving replacement likes that predated migration. It refuses later observed edits. It rebuilds affected playlists in chunks of at most 100 items and cannot restore dates/attribution or guarantee unavailable originals can be re-added. A failed rollback retains progress; use `resume` to continue. This is recovery machinery, not an atomic undo guarantee.

## Verification and scope

Tests cover duplicate ordering, pre-existing targets, randomized sequences, large rollback batches, lost responses, ambiguous failures, account/app mismatches, approval/identity gates, local/null entries, scan pagination, and later edits. Live OAuth, endpoint compatibility, relinking and rollback need a small account-backed validation before broad use.

The shared conversation's desktop slowness, wrapper UI, Symfonium integration, and union/intersection queries are separate work. No Spotify cache or local music files were changed.

Official documentation reviewed September 11, 2026. Shared conversation (private source omitted).
