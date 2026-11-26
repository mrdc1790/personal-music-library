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

For a two-playlist comparison you can try without signing in, see the
[worked examples](EXAMPLES.md#what-is-shared-by-two-playlists), including
[a union with a local track](EXAMPLES.md#compare-two-playlists-with-a-local-track).

Pass a playlist link, `spotify:playlist:` URI, or playlist ID with each
`--playlist`. Sign in with the catalog's Spotify app as usual. The audit reads
the selected playlists directly and skips playlist discovery and Liked Songs.
It prints the path to the importable `snapshot.json` when the run finishes.

```powershell
python audit.py --playlist 'PLAYLIST_A_LINK' --playlist 'PLAYLIST_B_LINK'
python library.py import 'C:\path\to\run\snapshot.json' --label 'Two-playlist capture'
```

You can compare completed playlists in the [offline preview](#preview-and-folders)
before importing the snapshot. The **Operation** menu includes both directions
of difference, intersection, and union. The same menu works when previewing
selected completed playlists from a full audit. Regenerate saved HTML files to
pick up changes to the preview.

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

For an initial report, import an audit snapshot using the commands above.
For a current baseline, make a new read-only scan and import it under a new
label. Keep older imports for comparison. Refresh the [folder capture](#preview-and-folders)
from the same account near the scan date, then import any listening history and
worldwide totals you have. You can run the ranking after the snapshot import
while the other inputs are still pending.

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

Use `--snapshot ID` to choose the membership capture (the latest import is the
default). The report uses the latest matching folder import, the full locally
imported listening history, and the latest dated count per track and service.
Each input therefore has its own date. Save a dated JSON report with `--output`
when you want to keep the exact combination of inputs. The parent directory must exist.

Sort by `playlist`, `personal-spotify`, `personal`, `worldwide-spotify`, or
`worldwide`. The two cross-service sorts use the totals from imported services.
Tracks with missing counts for the selected sort follow tracks with known
counts. The default limit is 50 and `matching_songs` is the count before that
limit. Reports cover identified music tracks and local references observed in
exported sources from the selected snapshot. A song that appears only in an
imported listening file needs an observed catalog placement to appear here.

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

Click any column header to sort the table. Click again to reverse the order.
Length sorts by duration with unknown
lengths at the end. Trial playlists sorts by the number of distinct playlists in
the preview that contain the song, including playlists outside the current A/B
selection.

Use the funnel beside any header to sort in either direction or filter that
column. **Value** lets you search the available values and choose which to keep.
To keep only a few, uncheck **Select all matching values** with an empty search,
then search for and check the values you want. **Condition** supports Contains,
Does not contain, and Equals on text columns. For **Length** and **Trial playlists**,
it offers equals, does not equal, and strict and inclusive comparisons. Enter a
length like `3:30` or `210` in whole seconds. Length conditions use the displayed
rounded seconds. Use **Value** to select unknown lengths. Choose **Apply** to save the
filter, **Cancel** to discard edits, or **Clear** to remove the column's filter.
Active funnels are highlighted. Column filters combine with each other, the
playlist operation, and the main search before pagination. **Clear all filters**
clears the search and every column filter, then returns to page one with the
same playlists, operation, and sort order. Regenerate older HTML from the saved
run with the command above to get the new controls offline.

Click a song to see metadata and each **Date added**. Release dates use the
provider's available precision. Use `--inventory-db` or `--inventory` to attach
local file evidence. The comparison's BPM and Key columns use confirmed file
tags from a saved SQLite inventory. Candidate tags stay under their file paths.
See [metadata coverage and exports](METADATA.md) for fields and planned analysis.

## Browse the saved catalog

```powershell
python view_catalog.py "$env:USERPROFILE\MusicLibraryData\catalog.sqlite"
python preview_audit.py --run 'C:\path\to\run' --catalog "$env:USERPROFILE\MusicLibraryData\catalog.sqlite" --catalog-view "$env:USERPROFILE\MusicLibraryData\catalog-view.html" --open
```

In the explorer, select a snapshot, then search by song, artist, album, or ID.
Click a song to see every observed placement for its exact identity in that
snapshot, including duplicates and Liked Songs where captured. Click a playlist
in the song details to browse its saved rows. The explorer starts with the
snapshot with the most exported playlists. Choose a different snapshot to see
its history. Once a folder tree is available, select a folder to include its
subfolders or browse by the playlist breadcrumbs.
**Clear all filters** returns to page one of the selected snapshot and clears
the folder, playlist, logical playlist, search, exact song identity, and rating filters. Regenerate an
older catalog view with the command above to get the button.

`--catalog` adds a separate **Saved catalog placements** section to the
comparison without changing the A/B results. It defaults to the same account's
snapshot with the most exported playlists. Use `--catalog-snapshot` to choose
another snapshot for that account. The section reports coverage and never
treats missing or partial sources as empty. `--catalog-view` links directly to
the selected song and snapshot in the generated explorer.

The default budget covers up to eight complete sources and 10,000 placements in
total, with automatic selection favoring playlists of 50 to 1,500 placements.
Each occurrence counts, so two 8,000-item playlists need the 16,000-row budget
shown above. Override the preview budget with `--max-rows` (up to 50,000) and
`--max-playlists` (up to 50 sources). The preview rejects selections outside its
budget and sources with incomplete or inconsistent counts. These settings govern
only the local HTML preview. Set membership uses the observed Spotify ID or local
URI. See the [capacity and playback guide](PLAYLIST_CURATION.md#how-the-limits-apply)
for the independent Spotify limits and catalog scale goals.

### How duplicates appear

The results table counts playlist placements. An exact track repeated at two
positions in one playlist has two rows. If it appears in two playlists, the
song details list both placements with their source and position. **Show only
this identity** filters to the selected saved key. The song details count
placements across the selected snapshot, even when the table is filtered.

For Spotify catalog tracks, the key uses the original track ID when the
snapshot has that evidence and otherwise uses the returned URI or ID. Local
tracks use their Spotify local URI, a reference based on file metadata.
Unidentified rows stay visible individually. A local file and a Spotify
catalog release of the same song have different keys, as can two Spotify
releases of the same recording. A title or album search can show both.

Set queries such as `intersection` return one result per identified key and
count which selected sources contain it. Snapshot comparisons can report
changes in the number of placements. The explorer and these reports read saved
evidence, so a placement count covers only what was captured.

Online cleaners can use broader matching. Spotify Dedup, for example, offers
strict ID matching and fuzzy matching on title, artist, and similar duration.
It can flag distinct IDs as possible duplicates and remove selected entries
from Spotify after review. Similar metadata can also match distinct versions.
The catalog explorer does not change Spotify. [Spotify Dedup](https://spotify-dedup.com/)

### Rate songs

Open a song's details and choose a rating from 1 to 5 or **Unrated** to clear
it. Filter for a particular rating or **Unrated**, and sort by highest or lowest
with unrated rows last. All placements of the same observed identity share one
rating across snapshots. Different Spotify IDs and local references keep their
own ratings. Placements without an identity cannot be rated.

Download the changes from the explorer before closing it, then apply the file
to the same local catalog and reopen the explorer. Rating drafts are held in
the open page. An import rejects a conflicting edit and keeps the entire batch
unapplied. Catalog backups include saved ratings.

```powershell
python library.py import-ratings "$env:USERPROFILE\Downloads\catalog-rating-changes.json"
python view_catalog.py
```

Use `python library.py --db 'C:\path\to\catalog.sqlite' import-ratings ...`
when the explorer was generated from a different catalog path.

### Group split playlists

Use `python library.py playlists` to find the saved IDs. Save a collection by
passing its members in order. Run the same command with the same collection ID
to revise its name, members, or active volume. Each member must appear in at
least one imported snapshot. The current grouping applies to each saved
snapshot, so playlist renames and moves preserve membership.

```powershell
python library.py save-collection dance 'Dance A–Z' ID_A_TO_L ID_M_TO_Z --active ID_M_TO_Z
python library.py collections --snapshot 2
python library.py query intersection collection:dance liked --snapshot 2
python library.py song-stats --snapshot 2 --sort collection
```

Choose **Logical playlist** in the catalog explorer to see the ordered members,
observed placements, and distinct identified tracks. Every placement keeps its
original playlist and position. Incomplete or absent members are visible and
their group totals are partial. CLI set queries require complete exports for
every member of the selected groups. Song stats counts each configured group
once per identity using its exported members and reports the member coverage.
The original per-playlist scoring and capacity reports still use individual
Spotify playlists. Catalog backups include the local group definitions.

### Import playlist folders

The read-only Spotifast rootlist adapter preserves nesting, empty folders,
ordering, and provenance. Refresh playlists and folders in a Spotifast build
that saves the account-scoped rootlist, then quit normally before importing.
The importer can also take an explicit saved rootlist JSON as its first argument.
For a portable ZIP installation, look for the session under the
`spotifast-data` directory next to the executable and pass its path explicitly.
See [Spotifast's file locations](https://spotifast.rocks/settings-and-files/).

```powershell
python folder_tree.py --run 'C:\path\to\run'
```

Regenerate both views after import so they can display the newly saved tree.
The tree and track snapshots have independent coverage and dates. If the
importer reports that the session has no account-scoped rootlist, the views can
still browse the flat saved playlists. The last known session on November 26,
2026 had no importable tree.

Use the Spotify client for [playing and shuffling native folders](PLAYLIST_CURATION.md).
The catalog's folder view displays saved organization evidence.

## Backup and recovery

Protect three things separately: catalog metadata/history, migration plans/journals, and actual audio files. The catalog ZIP only protects the first.

```powershell
python library.py backup backups/catalog-2026-09-25.zip
python library.py restore backups/catalog-2026-09-25.zip data/restored-catalog.sqlite
python library.py --db data/restored-catalog.sqlite snapshots
```

The ZIP contains an unencrypted, checksummed copy of the catalog SQLite file,
including imported listening events and stream totals. Keep hierarchy snapshots
privately alongside it as a separate database. Spotify audio, music files, and
migration journals have separate storage. Restore refuses overwrites. Verify a
restored copy before relying on a backup.

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
