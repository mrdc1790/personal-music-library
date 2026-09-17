# Worked examples

All names, IDs and dates here are synthetic. These examples do not describe your real Spotify account.

## What is in the example?

| Source ID | First snapshot, in order |
|---|---|
| `Chill` | Moonrise, Harbor, Moonrise |
| `Festival` | Moonrise, Night Drive |
| `AllLeaks` | Warehouse Edit (a local-track reference) |
| `liked` | Moonrise, Harbor |

Eight occurrences, four observed identities, four sources. Moonrise appears twice in Chill, once in Festival, and once in Liked Songs.

The second snapshot removes only the second Moonrise from Chill. Everything else stays the same. These files are checked in under `examples/` so the examples remain reproducible.

## Simplest route

Double-click `Try offline demo.cmd`, or run:

```powershell
python library_demo.py
```

Expected output:

```text
OFFLINE DEMO - synthetic music, not your Spotify account
Chill AND Festival: Moonrise
Chill NOT Festival: Harbor
Snapshot change: removed one duplicate Moonrise from Chill.
CSV files, database, and tested backup/restore: <a new folder under backups>
```

Open `csv/songs_with_playlists.csv` inside the printed folder to see the reverse membership list. Open `csv/duplicate_occurrences.csv` to see Moonrise twice in Chill. `catalog-backup.zip` and `restored-catalog.sqlite` demonstrate a completed local restore.

## Step through it yourself

Run from the project directory. Use this dedicated example database, not your real catalog:

```powershell
python library.py --db data/example.sqlite import examples/snapshot-before.json --label 'Example before'
python library.py --db data/example.sqlite import examples/snapshot-after.json --label 'Example after'
python library.py --db data/example.sqlite snapshots
```

In a new example database, the IDs are 1 and 2. Re-importing the same files does not add duplicates.

### Where is Moonrise?

```powershell
python library.py --db data/example.sqlite find Moonrise --snapshot 1
```

Four results: Chill at positions 0 and 2, Festival at position 0, and liked at position 0. Positions are zero-based: position 0 means the first song.

### What is shared by two playlists?

```powershell
python library.py --db data/example.sqlite query intersection Chill Festival --snapshot 1
```

One result: Moonrise. Its duplicate in Chill does not create a second set result.

### Combine the playlists, once per identity

```powershell
python library.py --db data/example.sqlite query union Chill Festival --snapshot 1
```

Three results: Moonrise, Harbor, Night Drive. Results are sorted by identity key, not a promised playback sequence. Creating a Spotify playlist from these results is not implemented.

### What is in Chill but not Festival?

```powershell
python library.py --db data/example.sqlite query difference Chill Festival --snapshot 1
```

One result: Harbor. Reversing the inputs returns Night Drive.

### What changed?

```powershell
python library.py --db data/example.sqlite compare 1 2
```

Chill shows one removed occurrence of the URI ending in 22 `A` characters and `sequence_changed: true`. The other sources are unchanged. This correctly records the removal of one duplicate, rather than saying Moonrise disappeared entirely.

### Export readable tables

```powershell
python library.py --db data/example.sqlite export exports/example-before --snapshot 1
```

The output folder must not already exist. Use another name when repeating this step.

| Track | Sources | Occurrences |
|---|---:|---:|
| Moonrise | 3 | 4 |
| Harbor | 2 | 2 |
| Night Drive | 1 | 1 |
| Warehouse Edit | 1 | 1 |

“Sources” includes Liked Songs. `manifest.json` maps the safe, ID-derived per-playlist filenames to their original names and IDs. The local Warehouse Edit artist remains an unmatched name rather than being merged with the Spotify artist of the same name.

### Make and restore a backup

```powershell
python library.py --db data/example.sqlite backup backups/example.zip
python library.py restore backups/example.zip data/example-restored.sqlite
python library.py --db data/example-restored.sqlite snapshots
```

The restored catalog contains both snapshots. These commands do not upload anything.

## What these examples deliberately do not claim

- A local reference does not prove an MP3 exists on disk or is playable on your phone.
- A track found in three playlists may still be absent from an inaccessible fourth playlist.
- Two Spotify IDs with the same title are still separate identities here.
- Stored dates are observed metadata; the catalog does not manufacture original artist-follow dates.
- A synthetic test is not a successful live Spotify migration.
