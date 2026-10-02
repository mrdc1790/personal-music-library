# Local file inventory and reconciliation

This offline workflow reads explicitly selected audio folders and optionally an
existing catalog snapshot. It writes a separate JSON report; it does not modify
audio, the catalog, Spotify, or device settings. No network or dependencies are
required.

```powershell
python local_inventory.py "C:\Music"
python local_inventory.py "C:\Music" "D:\Archive" --db "C:\Users\you\MusicLibraryData\catalog.sqlite" --snapshot 1
```

Without `--snapshot`, reconciliation uses the catalog's latest snapshot. Without
`--db`, the report contains only inventory observations. Reports default to a
timestamped file under `data_root()/inventories`, outside OneDrive Documents.
Use `--output` for an explicit JSON destination. Existing destinations are never
overwritten. Reports contain private paths and captured metadata; keep them out
of commits.

The extension filter includes MP3, M4A, AAC, WAV, FLAC, OGG, Opus, AIFF, and WMA.
This is an inventory filter, not a claim that Spotify supports these formats or
that their contents are valid audio. Each entry keeps its absolute path, root
index, size, modification time, SHA-256 of readable bytes, and filename stem.
WAV duration is read where supported. Tag parsing and audio fingerprints are
not implemented. A WAV metadata parsing error is explicit and does not erase
the readable file's byte evidence.

Roots and their errors remain in the report, including missing roots and failed
directory/file reads. Links and Windows reparse points are skipped and make
coverage incomplete. Files that change during reading lose their trusted hash
and make coverage incomplete. Root traversal is sorted. Overlapping or repeated
roots retain separate observations; `distinct_paths` counts unique paths.
Byte-duplicate groups retain every distinct path with equal SHA-256; repeated
observations of one path are not additional physical file copies.

Reconciliation retains every Spotify local occurrence, source, zero-based
position, URI, title, artist text, and duration. Repeated references remain
separate rows. URI equality never proves file equality. Candidates use only
case-insensitive equality of the filename stem and observed title, with a
two-second duration tolerance when both durations are available. Artist and
album tags are not read or inferred. Filename evidence is weak and may produce
false candidates; artist text is retained for review.

- `likely`: one filename candidate; it is not confirmed recording identity.
- `ambiguous`: multiple distinct candidate paths, even if their bytes match.
- `unmatched`: no candidate within completely scanned roots and an exported
  reference source; it is not a claim that audio is absent elsewhere.
- `incomplete`: no usable title/object or insufficient inventory/source coverage
  to interpret the lack of a candidate.

Positive candidates remain visible during partial coverage, with
`comparison_complete` and `source_exported` recorded separately. Duration
conflicts retain their path and reason. Files without observed candidates are
reported separately, with incomplete status when the catalog snapshot or root
scan is partial. Export flags, snapshot status, source counts, inventory times,
and snapshot time remain explicit. A complete endpoint capture does not prove
desktop Local Files, phone, saved local songs, transfer, or playback coverage.
There is no automatic replacement, cleanup, or deletion workflow.

## Folder counts versus Local Files versus playlist counts

The three-stage folder-audit workflow belongs to this project:
audit selected folders, reconcile separately captured Spotify observations, and
retain the evidence in the library workflow. Personal paths, playlist names,
and exact historical totals stay in private evidence rather than public docs.

Windows folder properties count all files, including artwork and sidecars;
an extension-selected inventory counts candidate audio paths; Spotify Desktop
Local Files counts that client's discovered entries; a playlist count measures
occurrences and may include repeated or cloud items. A difference between those
totals is a numerical gap, not proof of a specific number of missing recordings.
Equal totals also do not establish equal membership. Do not bulk-add the Local
Files view to a playlist merely to equalize its count.

The current scanner implements selected-root traversal, per-file errors, SHA-256
byte groups, optional WAV duration, and weak filename candidates against captured
local playlist references. It does not yet count every non-audio file or produce
an all-file extension histogram, validate audio decoding, read tags/codec/bitrate/
sample rate across formats, or capture the desktop Local Files collection.
An extension is not evidence of Spotify format support. A successful byte read
is not proof of valid or playable audio. No real-folder audit was run by this
documentation review.

Planned acceptance work:

- Produce an all-file extension histogram with an explicit no-extension bucket,
  candidate-audio counts, and traversal coverage. Report repeated root observations
  separately from distinct paths and retain unreadable/skipped entries.
- Retain root-relative paths and folder labels alongside absolute paths and scan
  provenance. Treat folder-derived artist, album, genre, source, or download-batch
  labels as attributed candidates, not authoritative tags or identity. Existing
  folders need no automatic reorganization; genres can be multiple user metadata
  labels without requiring multiple physical copies.
- Capture comparable item-level desktop Local Files and playlist observations
  through a validated export or adapter, retaining account/device, time, filters,
  ordering, duplicates, local/cloud distinction, and completion evidence. A Web
  API playlist scan does not supply the missing desktop collection. Report
  A-only/B-only/shared/unknown under a declared identity basis only when both
  sources support that comparison; count-only observations remain unresolved.
- Add source-dated tag and audio properties, reviewed file-to-recording links,
  provider/source URLs, and path history through backward-compatible SQLite
  schema work. Keep physical files, byte identity, recordings, releases, provider
  instances, and playlist occurrences separate. Metadata equality is candidate
  evidence, not canonical recording identity; playlist relationships must retain
  repeated occurrences. The chat's illustrative tables and SQL are not the
  implemented schema or a working missing-song query.

Whole-file SHA-256 establishes byte equality, not audio equivalence. Retagging
can change the hash without changing the audio; transcoding also changes bytes.
Audio fingerprints or decoded-audio comparisons are separate future evidence
with their own limits. Artist/title/album/duration alone cannot establish the
same recording. Preserve genuine versions and ambiguous matches for review.

Owned files supply the audio bytes; the catalog retains captured facts, history,
and reviewed organization; Spotify and possible players consume separately
validated projections. None is an infallible measurement of another device.
The browser migrator's companion guidance retains this boundary: these count
gaps do not authorize Spotify migration, playlist deduplication, or file cleanup.
