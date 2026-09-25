# Historical observations and unresolved evidence

These are dated observations retained for investigation. They are not a claim of current account state, a complete inventory, or permission to change Spotify.

## September 19, 2026: Liked Songs and Local Files counts

| Surface | Reported count | Difference from API total |
|---|---:|---:|
| Audit Liked Songs API total | [private count] | 0 |
| Spotifast desktop | [private count] | 0 |
| Spotify desktop Liked Songs | [private count] | [private count] |
| Spotify phone Liked Songs | [private count] | [private count] |
| Spotify web Liked Songs | [private count] | [private count] |
| Desktop Local Files | [private count] | Separate collection; do not subtract it |

The belief that all [private count] local songs were downloaded on the phone was not independently verified. Desktop minus API was [private count], not [private count]; web minus desktop was 10; desktop minus phone was 568. Equal totals can still contain different items. These gaps do not identify missing songs or justify deletion, unliking, cache clearing, deduplication, or relinking.

The earlier partial backup `[private backup ID]/library.sqlite` had local references in 44 playlist sources and none in its Liked Songs rows. That proves only that the playlist scan captured some Spotify-returned local references. It does not count unique files, prove audio exists, establish phone playback, or explain the client disagreement.

## September 19, 2026: interrupted audit and recovery

An unchanged placement total was traced to failed playlist reads and long HTTP 429 rate limits, not deduplication. The historical recovery copy passed SQLite `quick_check` and contained [private count] placements across hundreds of exported playlists; Liked Songs was not exported. It is incomplete audit evidence, not a complete catalog or importable `snapshot.json`.

This incident motivated the durable scanner: completed pages are committed, exhausted rate limits stop the run while preserving partial evidence, failures are visible, and incomplete coverage is never presented as an empty source. Historical paths and free-space figures are intentionally omitted because storage defaults have since moved to `%USERPROFILE%\MusicLibraryData`.

## September 22–24, 2026: bounded trial and client disagreement

The initial preview used eight completed playlists and [private count] placements from a run with a small completed subset of known sources. Liked Songs was excluded. The preview is therefore a bounded sample, not a representative account-wide survey; absence from it proves nothing about Spotify.

For track `[private track ID]`, desktop reported expected playlist membership while phone reported neither playlist nor Liked Songs membership after playback from a known playlist. The long migrator **Build preview** was read-only discovery: it showed affected locations but did not add, remove, like, or unlike anything. The cause remains unresolved.

## Reconciliation protocol

1. Complete and validate authoritative API coverage while preserving unread sources as unknown.
2. Count placements, distinct observed identities, local references, and missing objects separately for every source.
3. Inventory specifically chosen audio roots read-only: path, size, metadata, duration, errors, and optional hashes.
4. Match references to files with exact, likely, ambiguous, unmatched, and incomplete-root outcomes.
5. Obtain comparable client lists or file inventories where available, recording account, capture time, filters, and coverage.
6. Show actual item differences before proposing any repair.

Spotify local-file metadata, byte hashes, and audio fingerprints answer different questions. None reconstructs an undocumented client matching algorithm.
