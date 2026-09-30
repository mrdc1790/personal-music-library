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
