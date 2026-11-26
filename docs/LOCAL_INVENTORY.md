# Local file inventory and reconciliation

This offline workflow reads explicitly selected audio folders and optionally an
existing catalog snapshot. It writes a separate JSON report and can also save
scan history in a dedicated SQLite database. It does not modify audio, the
catalog, Spotify, or device settings. No network or dependencies are required.

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

The inventory preserves available ID3v2.3/v2.4 DJ and release tags on MP3s,
including BPM, initial key, genre, and available date fields. WAV observations
include duration, sample rate, channels, and bit depth. The comparison shows
these values with their candidate or confirmed file paths. Scan again to capture
the new fields in an older inventory. See [metadata coverage](METADATA.md#local-files-and-dj-metadata)
for field semantics and the separate audio-analysis pilot.

## Show file locations in a saved playlist comparison

Spotify's `spotify:local:` reference contains song metadata. The filesystem
path comes from a separate inventory of the folders you choose. To keep that
evidence in SQLite and show it in a comparison, use:

```powershell
$inventoryDb = Join-Path $env:USERPROFILE 'MusicLibraryData\inventories\local-files.sqlite'
python local_inventory.py 'C:\Music' --inventory-db $inventoryDb
python preview_audit.py --run 'C:\path\to\saved-run' --inventory-db $inventoryDb --open
```

The preview command generates a new offline preview from the saved audit.
Click a local track to see the dated candidate paths and coverage. Use
`--inventory-scan ID` to pick an earlier SQLite scan, or `--inventory PATH`
to use an existing JSON report. With no inventory selected, the details show
that file locations were not checked. The SQLite store keeps each scan
separately, including incomplete scans and paths that may have since moved.
Only paths relevant to local references in the preview are included in its
HTML. Treat the SQLite store, JSON and enriched HTML as private.

## Confirm a file and recognize it after a move

After checking a candidate yourself, copy the full `spotify:local:` URI from
the preview and give the inventory the exact file path.

```powershell
$uri = 'spotify:local:Example+Artist:Example+Album:Example+Song:203'
python local_inventory.py --inventory-db $inventoryDb --confirm $uri 'C:\Music\01 - Example Song.mp3'
```

Confirmation checks the file's current SHA-256 against the saved scan. Use
`--inventory-scan ID` if you reviewed an older scan. Regenerate the preview
with the same database to see the confirmation. Future scans show every path
with those exact bytes, even after a rename or move. When the bytes are absent
from the selected scan, the preview still shows that a prior review exists.
Changing tags, transcoding, or otherwise changing the bytes requires review
again. A new explicit confirmation replaces the active link for that exact URI.
Use `--clear-confirmation $uri` with the same database to withdraw it. The store
keeps the review history and the scan and path used at confirmation time.

The extension filter includes MP3, M4A, AAC, WAV, FLAC, OGG, Opus, AIFF, and WMA.
This is an inventory filter, not a claim that Spotify supports these formats or
that their contents are valid audio. Each entry keeps its absolute path, root
index, size, modification time, SHA-256 of readable bytes, and filename stem.
The scanner reads basic MP3 title, artist, and album tags from ID3v1 and
untransformed ID3v2.3/v2.4 text frames. It reads WAV duration where supported.
Other formats can still match by filename. Unsupported or malformed metadata
leaves the readable file's hash intact. Audio fingerprints are future work.
Run a new inventory to collect tags for files in older scans.

Roots and their errors remain in the report, including missing roots and failed
directory/file reads. Links and Windows reparse points are skipped and make
coverage incomplete. Files that change during reading lose their trusted hash
and make coverage incomplete. Root traversal is sorted. Overlapping or repeated
roots retain separate observations; `distinct_paths` counts unique paths.
Byte-duplicate groups retain every distinct path with equal SHA-256; repeated
observations of one path are not additional physical file copies.

Reconciliation retains every Spotify local occurrence, source, zero-based
position, URI, title, artist text, and duration. Repeated references remain
separate rows. A candidate needs an exact title after Unicode and case
normalization, from either a title tag or the filename stem. A numbered filename
can match via its title tag. Conflicting title, artist, album, or duration evidence
is shown separately. Artist and album are compared when present on both sides,
and duration has a two-second tolerance when available on both sides.

- `confirmed`: the scan observed bytes that you explicitly linked to this URI.
- `likely`: one tag or filename candidate that needs review.
- `ambiguous`: multiple distinct candidate paths, even if their bytes match.
- `unmatched`: no candidate within completely scanned roots and an exported
  reference source; it is not a claim that audio is absent elsewhere.
- `incomplete`: no usable title/object or insufficient inventory/source coverage
  to interpret the lack of a candidate.

Positive candidates remain visible during partial coverage, with
`comparison_complete` and `source_exported` recorded separately. Metadata
conflicts retain their path and reason. Files without observed candidates are
reported separately, with incomplete status when the catalog snapshot or root
scan is partial. Export flags, snapshot status, source counts, inventory times,
and snapshot time remain explicit. A complete endpoint capture does not prove
desktop Local Files, phone, saved local songs, transfer, or playback coverage.
There is no automatic replacement, cleanup, or deletion workflow.

## Folder counts versus Local Files versus playlist counts

For a reviewed set of local references, the catalog can
[preview an M3U](OWNED_AUDIO_PROJECTION.md) using saved file confirmations.
Each draft keeps the source positions and repeats, and leaves unresolved paths
out of the proposed M3U text.

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
byte groups, basic MP3 tags, optional WAV duration, and tag or filename candidates
against captured local playlist references. It does not yet count every non-audio file or produce
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
- Extend source-dated tag and audio properties and add reviewed file-to-recording links,
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
