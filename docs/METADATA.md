# Track, artist, album, and local audio metadata

The catalog keeps a dated copy of each audit occurrence and its returned API
entry. Audit responses can supply track URI and IDs, title, credited names and
IDs, ISRC, duration, disc and track numbers, explicit status, popularity,
playability, and the album or single identity, title, type, release date and
precision, and album credits. Availability varies by source and app. A number
such as a local reference's popularity of zero can be a provider placeholder.
Date added comes from the playlist or saved-track placement. Release date
describes the observed edition. Preserve year-only and month-only dates as given.

## Inspect what was captured

```powershell
python library.py snapshots
python library.py metadata --snapshot SNAPSHOT_ID
python library.py metadata --snapshot SNAPSHOT_ID --output 'C:\private\metadata.json'
```

The default is the latest imported snapshot. Choose an older snapshot explicitly
when a newer two-playlist test has a smaller scope. Counts measure observed
placements with populated fields. They include duplicate placements and may
include local placeholders. Failed or unexported sources have unknown coverage.
The optional private export includes per-placement track fields, album fields,
ordered artist and album artist credits, source, zero-based position, observed
track key, and date added. Existing captures work without reimporting or
contacting Spotify. Keep exports with your private catalog data.

The [offline comparison](OPERATING_GUIDE.md#preview-and-folders) exposes Album,
Album artist, Release date, ISRC, genre, and confirmed file-tag BPM and Key.
The table uses a representative captured row for grouped Spotify metadata.
Click a title to see observed metadata and each placement's added date. Unknown
fields are called out in the details. An album or artist genre is source
metadata and may describe something broader than the track. The
[catalog explorer](OPERATING_GUIDE.md#browse-the-saved-catalog) links exact
identities to saved playlists and can browse folder paths after import.

## Local files and DJ metadata

[Local inventory](LOCAL_INVENTORY.md) records available embedded MP3 tags,
including BPM, initial key, genre, release and recording dates, album artist,
composer, disc and track number, ISRC, and publisher. WAV reads can record
duration, sample rate, channel count, and bit depth. Tags reflect what the file
declares. The comparison displays them under each saved candidate or confirmed
file path. Spotify playlist placement evidence retains its own source and
timestamps. Run a new inventory scan to discover tags from files scanned before
these fields were supported.

## MusicBrainz recording genres

Genre enrichment is a separate command. Import a finished audit's snapshot
first, or use an already imported targeted capture. A partial snapshot can be
used for its fully exported sources. The full audit can continue while the
genre pass runs.

```powershell
python library.py snapshots
python genre_enrichment.py --snapshot SNAPSHOT_ID --playlist PLAYLIST_ID
python genre_enrichment.py --snapshot SNAPSHOT_ID --playlist PLAYLIST_ID --fetch --limit 20
python preview_audit.py --run 'C:\path\to\run' --playlist PLAYLIST_ID --genre-cache --output 'C:\private\genre-preview.html' --open
```

The first genre command reports coverage offline. Omit `--playlist` to use
all fully exported sources in the chosen snapshot. With `--fetch`, only a
public ISRC and, after a match, a MusicBrainz recording ID are sent to
MusicBrainz. The match requires one recording for the ISRC, agreement on title
and primary credit, and duration within three seconds. Alternate spellings,
credits, versions, or durations can make a lookup inconclusive. Ambiguous,
unmatched, pending, and matched-without-tags outcomes remain visible.

Each successful response is saved in a separate SQLite cache under the local
data directory. The request limit counts ISRC and recording requests. Repeat the
same command to continue after a limit or provider failure. Successful responses
and empty results are reused for 90 days before they become eligible for refresh.
Offline HTML displays the last saved observation, its fetch date, and its
MusicBrainz recording link when available. Recording tags have their own column
alongside observed album or artist genre. The preview generates the report
without provider requests. The [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
documents lookup fields and its [request limits](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting).

## Next metadata passes

1. Evaluate a read-only, small owned-audio pilot for untagged BPM, musical key,
   waveform summaries, and additional formats. Save results in the local
   inventory or a sidecar keyed by SHA-256 with tool version and date. Keep
   imported tags, audio estimates, and reviewed values as independent
   observations. Check half-time/double-time tempo, remixes, conflicting tags,
   corrupt files, and moved copies before expanding the scan.
2. Extend the recording-genre pass with cached artist and release enrichment using stable provider IDs,
   source dates, field coverage, and reviewed cross-provider matches. Evaluate
   artist genres, release labels and credits, artwork references, and edition
   relationships where permitted. Keep artist, release, recording, and placement
   fields distinct.
3. Evaluate a [rekordbox pilot](DJ_LIBRARY_WORKFLOW.md) for reading DJ tags and
   preparation. Full waveform and beat-grid analysis, tag writing, artist and
   album enrichment requests, and full-library refresh remain separate work.

Spotify's [track reference](https://developer.spotify.com/documentation/web-api/reference/get-track)
documents release-date precision and simplified credits. Spotify
[restricted Audio Features and Audio Analysis](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api)
for affected apps. The current audit and metadata report use fields already
returned by the track capture and do not depend on these endpoints.
