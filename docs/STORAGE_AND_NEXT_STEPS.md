# Storage and current next steps

Updated September 19, 2026.

## What happened in this run

The unchanged placement total was caused by failed playlist reads, including long Spotify 429 rate limits. It was not deduplication: every playlist placement is retained. The old playlist error handler continued after the rate limit, hiding errors behind an unchanged saved count. The updated client propagates long/exhausted rate limits, ends the scan, and preserves the incomplete export. Failed playlist reads now print their error immediately. Do not restart during the requested cooldown (approximately 6.5 hours remaining when inspected); other tools using the same app may contribute to its quota.

The running audit was stopped at the user's request after verifying its process. A consistent SQLite recovery copy passed quick_check:

`%USERPROFILE%\AppData\Local\PersonalMusicLibrary\backups\recovered-partial-20260919-153159\library.sqlite`

It contains [private count] placements and metadata for hundreds of exported playlists. Liked Songs was not exported. This is an incomplete audit database, not a catalog database. Its adjacent scan-metadata.json is only coverage metadata, not an importable snapshot.json. Original backup folders have not been deleted.

## New paths

The user moved Documents out of OneDrive during the scan. Code is now at `%USERPROFILE%\Projects\personal-music-library`. The running process had continued writing to its original OneDrive backup path.

New audit and migrate-scan defaults use `%LOCALAPPDATA%\PersonalMusicLibrary\backups`. The catalog CLI defaults to `%LOCALAPPDATA%\PersonalMusicLibrary\catalog.sqlite`; the viewer checks that location first, then legacy catalog/demo locations. Existing catalogs are not silently moved. Synthetic demo scripts and commands with explicit paths retain those paths.

Override all these defaults with the `PERSONAL_MUSIC_LIBRARY_DATA` environment variable, or use audit `--output` / library `--db` for individual commands. `Start audit.cmd` now passes through arguments. For example:

```powershell
python audit.py --output 'D:\MusicLibraryData\backups'
```

Use an actual available disk; D: is only an example. This changes future output, not a running process. Local C: had approximately 12 GB free during inspection. Writing outside OneDrive avoids cloud syncing but uses the same disk. Full JSON, SQLite, raw metadata repeated at each placement, older scans, and catalog import copies all contribute to size. Keep one verified recovery copy before reviewing redundant backups for deletion. Do not delete a running database or its journal.

Google Drive could hold selected compressed, closed, verified backups after a run. No upload or schedule is configured. Compression/retention and reducing redundant raw data remain needed for this library's scale.

## Reruns, comparison, and the interface

Every audit starts a fresh dated scan; automatic resume/incremental scanning and automatic diffing are not implemented. After importing two snapshots into the same catalog, `library.py compare OLD_ID NEW_ID` compares occurrences/order and coverage. It cannot infer deleted tracks from unread sources.

The viewer is a basic searchable, read-only table with playlist and snapshot selectors. Full-library overlap views and a Smarter Playlists-style visual rule builder are planned. Set operations already work as CLI queries. The catalog importer and static viewer still materialize large datasets in memory and need scale work before a confident full-library walkthrough at this size.

## Metadata and local audio

Each observed placement stores title, artist names/IDs, returned ID/URI, original ID when supplied, ISRC when supplied, duration in milliseconds, explicit/playable/local/missing flags, added_at, added_by, source, and position. The raw API entry is preserved, including album/release-date fields when supplied. Those raw fields are not all exposed as catalog columns or viewer filters. Scan time is recorded separately from date added.

BPM/key are not fetched or calculated. No local audio analysis, fingerprinting, or filesystem inventory has been performed. A Spotify local URI encodes artist, album, title, and duration in seconds, not a unique file ID or file hash. Duration is saved and will be a matching signal; it does not prove recording identity. A surviving URI does not prove any phone has the audio, and a changed tag/length may change a reference. The user's historical disappearance reports remain unresolved.

## Priorities

1. Resolve storage/retention and respect Spotify's cooldown before more scanning.
2. Obtain sufficient Liked Songs coverage, then reconcile API/desktop/web/phone counts using actual entries, not subtraction alone. Preserve inaccessible entries as unknown.
3. Inventory explicitly identified local-audio roots and match candidates, including duration, ambiguity, and missing-file reports.
4. Make catalog ingestion and browsing practical at full-library scale, then add playlist sizes, overlaps, duplicate review, and saved rules.
5. Use the catalog as a foundation for DJ crates and a central music hub. Audio matching, BPM/key analysis, cue grids, DJ export, and Symfonium integration are future work.

A collection above 10,000 entries can be organized locally, but this does not lift Spotify's playlist limit or provide seamless playback across split outputs. Spotify output splitting is still planned. Deduplication may recover some space; it cannot remove the limit.

47 tests pass after the storage/rate-limit update. This does not establish complete live account coverage.
