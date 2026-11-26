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

### Browser migrator versus this database

The separate browser migrator's IndexedDB recovery does not populate or open
this catalog. Continue using the capture/export/import commands below for local
history; there is no implemented catalog-to-browser export/import command yet.
Browser preview recovery can be used independently. The
[integration plan](INTEGRATION_DESIGN.md#catalog-to-migrator-discovery-handoff-planned)
defines the future handoff, and the [roadmap](ROADMAP.md#next-work) records pending
capture/scale validation. The October 22 recovery pass and October 27 docs update
did not perform a new personal capture or catalog import.

For the browser tool, use its own README for localhost ports and OAuth. Its
default is 5173; a Windows port reservation prevented that bind on October 22,
when 18080 worked as an alternative. That dated observation does not change this
Python application's `http://127.0.0.1:8765/callback` redirect or establish today's
port availability. Neither application's recovery data is an audio backup.

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

For an interrupted run, use the offline preview below to inspect completed
sources, or export the committed checkpoint without contacting Spotify:

```powershell
python library.py export-checkpoint 'C:\path\to\run' 'C:\private\saved-checkpoint.json'
python library.py import 'C:\private\saved-checkpoint.json' --label 'Saved checkpoint'
```

Use a new destination outside the repository. The export reads the resumable
run's SQLite database in one read transaction. It includes committed prefixes,
source status and errors, completion and validation times when recorded, and
playlist discovery coverage. An incomplete source stays unexported for queries
that require complete coverage. This is an importable observation, not a new
capture or a resume file. `--resume --export-json` still attempts an
authenticated resume on an unfinished run.

On resume, unchanged completed playlists reuse captured rows; an unchanged interrupted playlist continues from its committed offset; a changed playlist is recaptured by itself. Liked Songs has no equivalent playlist snapshot token, so its saved prefix is revalidated using identity, URI, `added_at`, local flag, and total. A mismatch resets Liked Songs only. Do not edit checkpoint files: the run database is authoritative. A process lock and persisted per-client-ID cooldown prevent conflicting resumes; nothing wakes or continues automatically after the scanner exits.

### Capture just the playlists you choose

Pass a playlist link, `spotify:playlist:` URI, or playlist ID with each
`--playlist`. Sign in with the catalog's Spotify app as usual. The audit reads
the selected playlists directly and skips playlist discovery and Liked Songs.
It prints the path to the importable `snapshot.json` when the run finishes.

```powershell
python audit.py --playlist 'PLAYLIST_A_LINK' --playlist 'PLAYLIST_B_LINK'
python library.py import 'C:\path\to\run\snapshot.json' --label 'Two-playlist capture'
```

You can compare completed playlists in the [offline preview](#preview-and-folders)
before importing the snapshot.

```powershell
python preview_audit.py --run 'C:\path\to\run' --open
```

Local entries returned by Spotify retain their local URIs and playlist
positions. If Spotify denies access to a playlist, the run records that source
as unreadable. Use `--resume` with the printed run folder to retry an
interrupted or partial capture. The selection is saved in the run.

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

For a before-and-after cleanup review, import both captures and run
`python library.py compare BEFORE_ID AFTER_ID`. For each comparable source,
`removed_occurrences` shows how many placements were lost per observed track
key. Look up that key in `remaining_occurrences_for_removed_keys` for the
count after the change. If a playlist went from three copies to one, the maps
show two removed and one remaining. A remaining count of zero means that the
key disappeared from that source, even if it remains elsewhere. Both maps
require complete coverage and identified rows in both captures. The counts
describe the change between captures. Identifying a specific surviving row
or attributing the change to a cleanup requires additional evidence.

## Unavailable tracks and recovery

```powershell
python library.py availability
python library.py availability --snapshot 1
python library.py availability --snapshot 1 --inventory 'C:\private\inventory.json'
```

The report opens as a local HTML file. It uses the latest imported snapshot by
default and keeps every captured Liked Songs and playlist position, including
duplicates. Open **Source coverage** to see which captures were incomplete and
how many placements had no availability signal. Spotify may return a null
object or omit relink details. The report keeps these gaps visible. Local
Spotify references need their own [inventory and device checks](LOCAL_INVENTORY.md).

The report shows playable relinks and alternatives observed in the same capture.
The latter require matching ISRC, title and artists, with compatible duration
and explicit flags where supplied. Review the exact version before using the
[Spotify Playlist Migrator](https://github.com/mrdc1790/spotify-shadow-release-migrator)
for a replacement. Account restrictions and conflicting signals get a review row.

An unplayable or market-restricted track with no observed Spotify alternative
can be a **SoundCloud recovery lead** after a complete inventory of the chosen
folders finds no compatible filename. A missing or incomplete inventory puts it
under **Check local copies and Spotify search**. Both sections link to manual
Spotify and SoundCloud searches. Use a [local inventory report](LOCAL_INVENTORY.md)
to check title or `Artist - Title` filenames. Different filenames and unscanned
locations can hide copies. A Spotify flag records availability at capture time
for that account and market. The service might make the track playable again.

The report runs offline and saves to the `availability` folder under your Music
Library data directory by default. Use `--output` to choose a new file.

## Playlist capacity

```powershell
python library.py capacity --output 'C:\private\capacity.json'
python library.py capacity --snapshot 2 --before 1 --output 'C:\private\capacity-change.json'
```

The report counts every captured placement, including repeats, local files
and unavailable rows. It estimates remaining slots against the documented
ordinary-playlist limit of 10,000 only for completed sources whose provider
total agrees with the captured count. Unknown headroom stays null with a reason.
The report lists known estimates from lowest to highest and labels Liked Songs
separately. It includes the evidence timestamp and its basis; older exports may
have only a run-level timestamp. With `--before`, it reports net placement changes
for the same playlist when both captures qualify and their evidence times are
strictly ordered. The report describes saved evidence; check current Spotify
state before relying on spare capacity for a repair.

## Song stats

```powershell
python library.py song-stats --term 'song or artist text'
python library.py song-stats --folder-depth 2 --limit 100
python library.py import-spotify-history 'C:\path\to\extended-spotify-history.zip'
python library.py import-personal-plays 'C:\path\to\other-service-plays.csv'
python library.py import-worldwide-streams 'C:\path\to\worldwide-streams.csv'
python library.py song-stats --sort personal-spotify --output 'C:\private\song-stats.json'
```

- **Playlist score** adds one point per distinct playlist in the selected
  catalog snapshot plus one per distinct known folder category. Three playlists
  under Electronic score 4. Three playlists across three known categories
  score 6. The default category is the outermost folder. Set `--folder-depth 2`
  to distinguish Electronic / House and Electronic / Bass. Repeat copies in a
  playlist count once. Liked Songs can supply a song to the report and adds
  no points. The report names the snapshot and coverage. If a playlist is at
  the root, lacks a folder match, or has conflicting category assignments, it
  contributes its base point. Folder assignments come from the latest imported
  tree for the snapshot's account, which can have a different date.
- **Personal plays** use your Spotify [Extended Streaming History](https://support.spotify.com/us/article/understanding-your-data/)
  audio-track events and optional reviewed events from other services. The
  report shows personal Spotify plays and the sum across imported services.
  Both count events with at least 30 seconds played. Per-service details also
  show event counts, listening milliseconds, and dates. `null` means no
  matching data. Zero means an observed count of zero. The standard Spotify
  account export lacks Spotify track URIs, so use the Extended Streaming History
  ZIP from the same account as the catalog. Spotify rows are matched by exact
  track URI. Reimport merges overlapping events using their timestamp, track,
  duration, platform, offline timestamp, and occurrence count within the ZIP.
- **Worldwide streams** use the latest dated, imported totals for each service.
  The worldwide Spotify field comes from the Spotify row. The total across
  imported services may span different reporting dates and definitions. Check
  the per-service detail for counts, dates, and sources. Spotify’s [Web API track data](https://developer.spotify.com/documentation/web-api/reference/get-track)
  lacks raw stream totals. Use a source that provides worldwide all-time
  track totals, such as an authorized [Spotify for Artists export](https://support.spotify.com/us/artists/article/exporting-data/)
  or a distributor report for the same recording. Supply one row per service
  and track per date. Exclude combined platforms, chart ranks, popularity
  scores, views, release totals, and date-limited figures.

Non-Spotify personal events CSV uses
`service,event_id,track_key,ended_at,played_ms`. Use the playback service slug
(e.g. `apple-music`), a stable event ID from that service's history, the
reviewed Spotify track URI of the same recording, a timestamp with its time zone,
and the actual time played in milliseconds. Use one event feed per playback
service to avoid counting a play twice.

Worldwide streams CSV uses `service,track_key,as_of,streams,source`. Use an
exact Spotify track URI, a `YYYY-MM-DD` date, the integer count, and a source
description. Both CSV imports require a reviewed recording match. Same-title
tracks and different versions retain their own rows.

All imports are offline. Listening events and dated stream totals are stored in
the catalog and included in its backups. The Spotify archive itself and fields
such as IP address are excluded. Store the database, reports, and backups in
private storage.

## Preview and folders

The preview reads completed audit rows directly and is intentionally bounded; it is a useful trial, not a full-account claim.

```powershell
python preview_audit.py --run 'C:\path\to\run' --open
python preview_audit.py --run 'C:\path\to\run' --playlist PLAYLIST_A --playlist PLAYLIST_B --max-rows 16000 --open
```

The default budget covers up to eight complete sources and 10,000 placements in
total, with automatic selection favoring playlists of 50 to 1,500 placements.
Each occurrence counts, so two 8,000-item playlists need the 16,000-row budget
shown above. Override the preview budget with `--max-rows` (up to 50,000) and
`--max-playlists` (up to 50 sources). The preview rejects selections outside its
budget and sources with incomplete or inconsistent counts. These settings govern
only the local HTML preview. Set membership uses the observed Spotify ID or local
URI. See the [capacity and playback guide](PLAYLIST_CURATION.md#how-the-limits-apply)
for the independent Spotify limits and catalog scale goals.

Spotify's Web API does not provide its folder tree. The optional read-only Spotifast rootlist adapter preserves nesting, empty folders, ordering, and provenance when available, but needs small live validation:

```powershell
python folder_tree.py --run 'C:\path\to\run'
```

Use the Spotify client for [playing and shuffling native folders](PLAYLIST_CURATION.md).
The catalog's folder view displays saved organization evidence.

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
