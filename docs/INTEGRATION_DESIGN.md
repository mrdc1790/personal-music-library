# Integration design: folders and smart collections

Both areas are planned extensions to the local catalog. They must preserve provenance and remain useful even when Spotify, local audio, or a future provider cannot support the requested output.

## Folder structure adapter

Spotify's Web API capture preserves playlist contents but not folder nodes, nesting, empty folders, or desktop sibling order. API playlist-list order must not be described as a folder tree.

`folder_tree.py` is an offline-tested, read-only adapter for an account-scoped Spotifast rootlist cache. It can retain raw hierarchy payload, nested and empty folders, stable IDs where supplied, parent relationships, sibling order, and separate hierarchy snapshots. It joins playlist structure to audit data by Spotify playlist ID—not display name. The current limitation is important: no live account tree or direct rootlist fetch has yet been validated.

Keep structure coverage separate from playlist-content coverage. A rootlist playlist with unreadable contents remains visible in its folder with contents marked unknown. Malformed or incomplete rootlist structure must retain raw ordered evidence and a warning rather than being silently repaired into a trustworthy tree. Rootlist support does not expose hidden original IDs, bypass rate limits, remove the 10,000-item limit, or establish local-file playback.

## Smart collections and recipes

The current CLI supports local union, intersection, and difference. A future recipe interface should make those steps visible and reproducible:

1. Select one saved snapshot and show its coverage.
2. Select source playlists or Liked Songs by friendly name and stable ID.
3. Connect simple rules: in either, in both, or in A but not B.
4. Preview result count, entries, and inclusion explanation.
5. Save either the recipe (rules) or a result (entries from a particular run); do not confuse the two.

The expected synthetic examples are `Chill AND Festival → Moonrise` and `Chill NOT Festival → Harbor`. A recipe run must not mutate its sources. It must preserve snapshot ID, recipe version, parameters, coverage, output-order rule, and any shuffle seed so the result can be explained and reproduced.

Later operations—sorting, limits, artist spacing, explicit deduplication, scheduling, refresh against a newer snapshot, and Spotify publishing—need their own visible rules and review boundaries. Mathematical set operations do not define listening order. A large local result may later be projected to bounded service playlists, but splitting or publishing is not implemented.

## Owned audio and DJ endpoints

Only after files are inventoried and matched should the project generate a dry-run M3U or music-server playlist report. Verify path mapping, ordering, duplicates, and unresolved entries on a small sample before bulk output. Symfonium, Navidrome, Jellyfin, and DJ software are potential endpoints for owned audio; they do not convert Spotify metadata into audio or establish universal playback.
