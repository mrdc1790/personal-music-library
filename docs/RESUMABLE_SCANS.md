# Resumable scans and project status

Updated September 22, 2026. The default `Start audit.cmd` / `python audit.py` now uses the resumable scanner. Legacy recovered databases cannot be resumed because they lack its durable progress records. Keep them as partial historical evidence.

## Start, pause, resume

- Fresh run: double-click `Start audit.cmd`. Sign in with the same Spotify account. This creates a new dated folder under `%USERPROFILE%\MusicLibraryData\backups` (or your explicit `--output`).
- Pause: press Ctrl+C in the scan terminal. A rate limit pauses automatically on the first HTTP 429. Committed pages remain on disk; an interrupted page is rolled back.
- Resume: open that SAME run folder and double-click `Resume this audit.cmd`. Sign in again; tokens are never saved. A cooldown blocks sign-in/scanning until its expiry. Nothing automatically wakes up or runs in the background after the scanner exits.
- Inspect: open `RUN STATUS.txt`. It shows the last failure, request, cooldown expiry in your local timezone, source names/statuses/counts, and resume instructions. `run.log.jsonl` preserves timestamped request successes, HTTP failures/retries, and checkpoint events without access tokens or OAuth URLs.
- Do not use Start audit to resume: it deliberately creates a new run. Completed runs are protected from CLI resumption; start a new run for a new historical scan.

Equivalent commands:

```powershell
python audit.py --resume 'C:\path\to\the-run-folder'
python audit.py --resume 'C:\path\to\the-run-folder' --status
```

`library.sqlite` contains rows and the authoritative run state in the same database. JSON status files and the text log are readable mirrors, regenerated on reopening. Never edit checkpoint files by hand. A process lock prevents two scanners from writing the same run, and is released by Windows if a process crashes. App cooldowns also persist outside the run folder, keyed by public Client ID, to prevent accidentally restarting into the same cooldown.

## What is re-read?

Playlists are captured first. On resume, each discovered playlist gets a metadata/snapshot-ID check. Unchanged completed playlists reuse their rows. An unchanged interrupted playlist continues from its committed page offset. A changed playlist discards only that source's stale rows and starts that source again. The version is checked again after reading its final page. Permission failures are shown as failed coverage, never as empty playlists.

The playlist discovery list is checkpointed too. It is the list discovered for this run, not continuous monitoring of newly created/deleted playlists. Start a fresh run for a new discovery sweep. The export is a collection of per-source observations at recorded times, not an atomic account-wide snapshot.

Liked Songs has no playlist snapshot ID. On resume, all previously saved liked entries are re-read and compared by returned/original identity, URI, added_at, and local flag, with the total checked as well. A matching prefix allows continuing at the old offset; a mismatch resets Liked Songs only. Revalidation itself can be paused by a rate limit, but its prefix checks restart on the next session so old validation is not treated as current. This costs requests and cannot guarantee progress if Spotify consistently denies enough requests to validate the prefix. Freeze edits to Liked Songs during capture; even full prefix validation cannot make an unversioned, changing collection atomic. Metadata-only edits are not treated as identity shifts.

## Storage and exports

SQLite is the default durable output. No full JSON or giant HTML is generated on every pause. For compatibility with the existing catalog importer, request an explicit JSON/report export after a successful scan:

```powershell
python audit.py --resume 'C:\path\to\completed-run' --export-json
```

This can be large. The catalog importer still loads the JSON in memory, so improving full-scale ingestion remains necessary. `run-state.json` and `status-summary.json` are progress files, not complete music snapshots. A captured page or partial source must never be called a completed source. The legacy programmatic `audit.scan` and `migrate.py scan` remain legacy nonresumable paths; use the standard audit launcher for durable resume.

## Consolidated status

| Question | Current reality |
|---|---|
| Liked Songs discrepancies next? | Yes. Finish sufficient captured coverage, then compare actual entries and local-file evidence. Counts alone cannot identify missing songs. |
| Rate limit / pause / resume? | Durable per-page SQLite checkpoints, automatic pause on 429, saved expiry, and a same-folder resume launcher. No need to restart every playlist. Likes require full saved-prefix revalidation, which still costs requests. |
| New run versus resumed run? | Resume continues one run with validation. Start audit creates a separate fresh dated run. No automatic cross-run diff or account-wide atomic snapshot. |
| Difference between runs? | After importing two snapshots, the catalog compare command compares placements, ordering and coverage. A failed/unread source remains unknown. Resume is recovery, not a historical diff. |
| Visualization/database? | Read-only searchable table and snapshot/playlist filters; durable audit database and status log. Large-scale catalog ingestion/viewer improvements and an overlap map remain planned. |
| Smarter Playlists? | CLI union/intersection/difference work. Saved recipes and visual rule editing are planned. |
| DJ / central media hub? | Metadata/identity/history foundation. Audio matching, analysis (BPM/key), cue points, DJ exports, and player integration remain planned. Duration is already stored; raw album/release fields are preserved when supplied. |
| Spotify 10k limit? | Remains a Spotify output constraint. Larger local collections and bounded output playlists are the proposed route; splitting/publishing is not implemented. |
| Local songs? | Preserve API-returned playlist references and duration. Audio-folder inventory, matching, missing-file/device checks, and explaining past disappearance still require work. |
| Storage / cloud backups? | Real run data defaults outside OneDrive in `%USERPROFILE%\MusicLibraryData`. Full JSON exports are optional; no Google Drive upload, retention automation, or deduplicated raw storage is configured. |

58 tests passed September 22, including recovery after interruption, snapshot changes, unchanged playlist reuse, same-count liked shifts, failed-prefix handling, cooldown guards and concurrent-writer exclusion. These are offline tests, not proof of successful full-library live coverage.

Windows data paths now use the physical profile MusicLibraryData folder because packaged desktop apps can redirect AppData into a private cache. Older AppData backups remain untouched. Explicit `--output` and `PERSONAL_MUSIC_LIBRARY_DATA` overrides still take priority.
