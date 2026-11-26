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

The [offline comparison](OPERATING_GUIDE.md#preview-and-folders) shows Album and
Release date from the representative captured row for a grouped song. Its song
details show each placement's available added date and release metadata.

## Local files and DJ metadata

[Local inventory](LOCAL_INVENTORY.md) records available embedded MP3 tags,
including BPM, initial key, genre, release and recording dates, album artist,
composer, disc and track number, ISRC, and publisher. WAV reads can record
duration, sample rate, channel count, and bit depth. Tags reflect what the file
declares. The comparison displays them under each saved candidate or confirmed
file path. Spotify playlist placement evidence retains its own source and
timestamps. Run a new inventory scan to discover tags from files scanned before
these fields were supported.

## Next metadata passes

1. Evaluate a read-only, small owned-audio pilot for untagged BPM, musical key,
   waveform summaries, and additional formats. Save results in the local
   inventory or a sidecar keyed by SHA-256 with tool version and date. Keep
   imported tags, audio estimates, and reviewed values as independent
   observations. Check half-time/double-time tempo, remixes, conflicting tags,
   corrupt files, and moved copies before expanding the scan.
2. Build opt-in, cached artist and release enrichment with stable provider IDs,
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
