# Reconciling song counts and local files

Recorded September 19, 2026. These are user-reported observations, not verified equivalent counts taken at one instant.

| Surface | Reported count | Difference from API total |
|---|---:|---:|
| Current audit: Liked Songs API total | [private count] | 0 |
| Spotifast desktop | [private count] | 0 |
| Spotify desktop Liked Songs | [private count] | [private count] |
| Spotify phone Liked Songs | [private count] | [private count] |
| Spotify web Liked Songs | [private count] | [private count] |
| Desktop Local Files | [private count] | Different collection; do not subtract as if equivalent |

The user believes all [private count] local songs are downloaded on the phone; this is not yet independently verified. Older device-count discrepancies were also reported, including a work PC without the local audio files. Treat that as historical context, not current inventory.

## What these counts do and do not establish

The audit prints the API response's `total`, before deduplication or catalog processing. Spotify defines it as the number of items available to return from that endpoint. It is not proof of the complete set shown by every client. The audit preserves duplicates and local/missing entries returned to it; it does not reduce the total to unique recordings.

Desktop minus API is [private count], not [private count]. Web minus desktop is 10; desktop minus phone is 568. These are count gaps, not identified missing-song lists. Equal counts can still contain different songs. Spotifast's matching count does not establish its implementation or prove either dataset complete.

Local-file inclusion, stale client state, filtering, unavailable entries, and release identity differences are hypotheses to investigate, not established causes. No count gap is a reason to delete or unlike songs.

## Local files are a required part of the project

A read-only query of the earlier `[private backup ID]/library.sqlite` partial backup found `is_local` references in 44 playlist sources, and none in that backup's Liked Songs rows. This is evidence that playlist local references are being captured. It is not a complete inventory, a unique-file count, or proof of why the clients disagree.

The playlist scan preserves local references returned by the API, including metadata, URI, source playlist, position, and raw response. This is the relevant scan stage for local songs placed in ordinary playlists such as All Leaks, provided Spotify allows that playlist to be read. It cannot guarantee all [private count] files are represented. A device's Local Files collection is not itself a filesystem inventory obtained by this scan. A local reference does not establish that an audio file exists, is downloaded, or plays on a phone. Nor does membership in All Leaks prove membership in Liked Songs.

## Required reconciliation workflow

1. Finish and validate API coverage; retain unread sources as unknown.
2. Count placements, distinct observed identities, local references, and missing entries separately for Liked Songs and every playlist. Keep raw identities before any recording-level matching.
3. Inventory the user-specified audio folders read-only: paths, size, metadata, duration, errors, and optionally hashes. The folder paths have been requested; the inventory is not yet implemented.
4. Match playlist references to file candidates and report exact evidence, ambiguous matches, and unmatched references. A metadata-based local URI is not a file hash.
5. Obtain comparable desktop/phone lists or file inventories where possible. The API scan alone cannot reconstruct device-only state or a client-only Liked Songs list.
6. Show actual differences before proposing repairs. Track account, capture time, filters, and source coverage with each observation. Do not promise that clearing caches, deduplication, or relinking will reconcile the totals.

Sources: [Spotify playlist local-file behavior](https://developer.spotify.com/documentation/web-api/concepts/playlists), [saved-track response definition](https://developer.spotify.com/documentation/web-api/reference/get-users-saved-tracks), [device Local Files setup](https://support.spotify.com/us/article/local-files/).
