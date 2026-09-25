# Operating guide

## Choose the workflow

| Goal | Use |
|---|---|
| Learn safely with synthetic data | `Try offline demo.cmd` or `python library_demo.py` |
| Browse completed real sources | `Preview saved music.cmd` |
| Start a read-only capture | `Start audit.cmd` or `python audit.py --client-id YOUR_CLIENT_ID` |
| Resume an interrupted capture | `Resume this audit.cmd` in its run folder or `python audit.py --resume 'C:\path\to\run'` |
| Build a historical catalog | `python library.py import 'C:\path\to\snapshot.json'` |
| Alter Spotify memberships | Read [Migration](MIGRATION.md); catalog commands never do this |

Keep source snapshots, run status, errors, and failed coverage. They explain what the data does and does not cover.

## Scan and resume

Create a Spotify Developer app, set redirect URI `http://127.0.0.1:8765/callback`, and use the public Client ID—no Client Secret is needed. Copy `.env.example` to `.env` and replace the placeholder, or set `SPOTIFY_CLIENT_ID` in the process environment. The ignored `.env` file is read locally and only that one setting is accepted.

```powershell
python audit.py
```

Data defaults to `%USERPROFILE%\MusicLibraryData`; explicit `--output` or `PERSONAL_MUSIC_LIBRARY_DATA` takes precedence. Each new audit creates a dated folder. The resumable scanner commits captured rows and progress together. Ctrl+C and rate-limit pauses preserve committed pages; resume the same folder instead of creating a new audit.

```powershell
python audit.py --resume 'C:\path\to\run'
python audit.py --resume 'C:\path\to\run' --status
```

`RUN STATUS.txt` and `run.log.jsonl` are readable mirrors. A changed or unreadable source remains coverage evidence, not an empty playlist. A run is a set of timed source observations, not an atomic account-wide snapshot. After a completed audit, produce the large legacy export required by the catalog importer:

```powershell
python audit.py --resume 'C:\path\to\completed-run' --export-json
```

On resume, unchanged completed playlists reuse captured rows; an unchanged interrupted playlist continues from its committed offset; a changed playlist is recaptured by itself. Liked Songs has no equivalent playlist snapshot token, so its saved prefix is revalidated using identity, URI, `added_at`, local flag, and total. A mismatch resets Liked Songs only. Do not edit checkpoint files: the run database is authoritative. A process lock and persisted per-client-ID cooldown prevent conflicting resumes; nothing wakes or continues automatically after the scanner exits.

## Catalog, queries, and exports

```powershell
python library.py import 'C:\path\to\snapshot.json' --label 'First scan'
python library.py snapshots
python library.py playlists
python library.py find 'song or artist text'
python library.py query intersection PLAYLIST_A_ID PLAYLIST_B_ID
python library.py query union PLAYLIST_A_ID PLAYLIST_B_ID
python library.py query difference PLAYLIST_A_ID PLAYLIST_B_ID
python library.py export exports/first-export
python library.py compare 1 2
python view_catalog.py
```

Use `liked` for Liked Songs. Search returns every observed placement; set operations use distinct available observed identities and do not make playback order. Unavailable coverage stops a query rather than appearing empty. Export destinations must be new; consult `manifest.json` before interpreting an empty CSV. The static viewer is read-only and can take longer with large histories.

## Preview and folders

The preview reads completed audit rows directly and is intentionally bounded; it is a useful trial, not a full-account claim.

```powershell
python preview_audit.py --run 'C:\path\to\run' --open
python preview_audit.py --run 'C:\path\to\run' --playlist PLAYLIST_A --playlist PLAYLIST_B --open
```

Defaults select up to eight complete sources and 10,000 placements, preferring nonempty playlists between 50 and 1,500 placements. No selected source is truncated and called complete. Explicit overrides allow at most 50 sources and 50,000 placements. Set membership is the observed Spotify ID or local URI—not a recording-level equivalence.

Spotify's Web API does not provide its folder tree. The optional read-only Spotifast rootlist adapter preserves nesting, empty folders, ordering, and provenance when available, but needs small live validation:

```powershell
python folder_tree.py --run 'C:\path\to\run'
```

## Backup and recovery

Protect three things separately: catalog metadata/history, migration plans/journals, and actual audio files. The catalog ZIP only protects the first.

```powershell
python library.py backup backups/catalog-2026-09-25.zip
python library.py restore backups/catalog-2026-09-25.zip data/restored-catalog.sqlite
python library.py --db data/restored-catalog.sqlite snapshots
```

The ZIP contains a consistent SQLite copy and checksum. It is not encrypted and contains music metadata, but not audio or migration journals. Restore refuses overwrites; verify a restored copy before relying on a backup. No cloud upload or scheduler is configured.

A checksum detects corruption, not authorship. Keep raw audit folders and migration journals alongside versioned catalog archives, and use a private destination only after validating a restore under a new filename. Synchronizing a live SQLite file can propagate mistakes; a closed, verified archive is the safer first online-backup unit. A catalog restore never reverts Spotify.

## Safe responses

| Situation | Response |
|---|---|
| Rate limit/server failure | Preserve the run and resume later; never infer empty coverage |
| Missing source | Inspect coverage/errors; unread sources are unknown |
| Different location required | Set `PERSONAL_MUSIC_LIBRARY_DATA`, use `--output`, or use `--db`; do not move an active database |
| Client membership/count disagreement | Record time, account, market, filters, and surface; compare fresh API observations within their scope and retain device/local unknowns; see [Evidence and data model](EVIDENCE_AND_MODEL.md) |

### Interpreting Liked Songs and Local Files

A displayed Liked Songs total, API saved-track rows, playlist placements, and desktop Local Files are different measurements. Check run completion and exported coverage before comparing. Do not add/subtract the Local Files count to force agreement. Local references can occur in captured playlists, but the scan does not enumerate every file on disk or confirm phone downloads. No files or Spotify caches should be deleted to investigate a count gap. See the [reconciliation protocol](HISTORICAL_OBSERVATIONS.md#reconciliation-protocol) and [planned acceptance criteria](ROADMAP.md#reconciliation-acceptance-criteria-planned).
| Need to alter Spotify | Use the explicit [Migration](MIGRATION.md) review path |
