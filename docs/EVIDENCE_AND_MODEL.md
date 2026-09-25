# Evidence and data model

## What the catalog represents

The catalog records observations, not a perfect global music-identity graph. A snapshot contains captured sources and coverage. A source is a playlist or `liked`. An occurrence is one item at one zero-based position. Repeated items are separate occurrences because duplicate count and order matter.

| Term | Meaning |
|---|---|
| Observed identity / track key | Spotify or local identity available to a scan; used for exact-ID queries |
| Recording | Underlying performance that may have several releases; canonical matching is planned |
| Local reference | Metadata Spotify returned for a local track; not a file path, audio copy, or playback guarantee |
| Coverage | Successful, failed, changed, and inaccessible source information |
| Client observation | Timestamped phone, desktop, web, or API claim; evidence, not a deletion instruction |

The implementation keeps `snapshots`, `playlists`, and `items`, plus a derived `membership` view. Raw source JSON stays with imported snapshots. Imports are transactional; invalid or non-contiguous positions roll back the new import, and earlier snapshots stay intact. The catalog is restricted to one account; synthetic examples use a separate account identity.

## Identity and duplicates

An observed key uses an explicit missing-object key, local URI, explicit original ID, returned URI/ID, or finally an unknown key. Each item records its identity basis. Two Spotify IDs are not merged just because title, artist, ISRC, or duration looks similar. A recording may appear as a single, album, deluxe, compilation, market-relinked, or later catalog instance; remixes, remasters, live recordings, edits, and clean/explicit versions may be genuinely different.

The future model is a local canonical recording with multiple provider instances and evidence-backed relationships. Until then, exact-ID results and recording-level questions remain distinct.

`items` retains title, artist text, returned/original identity, local/missing/playable flags, album, duration, ISRC, and added timestamp, while raw entries retain other source metadata. Artist reports distinguish first-credit placement counts, all-credit placement counts, distinct observed identities, and unmatched name-only local credits. These are observations, not artist-follow history or canonical artist records.

## Coverage, counts, and local files

An unreadable, partial, or unexported source is never empty. Comparisons distinguish coverage changes from membership changes. Unknown identities remain visible in occurrence browsing but cannot safely participate in set operations.

Name what a count means: sources, occurrences, distinct observed identities, artist credits, local references, or files. A local reference is not a distinct audio file. For future file reconciliation, scan explicit roots read-only and report exact, likely, ambiguous, unmatched, and incomplete results separately. Metadata URI, byte hash, and audio fingerprint are different evidence.

## Client disagreement

Phone, desktop, and web clients can show incompatible membership state even when playback succeeds. Record stored occurrence URI/position, requested/effective URI when known, time, platform/app version, market, UI surface, result (`present`, `absent`, `unknown`), and raw evidence.

“Not shown on phone” is conflicting or unknown evidence, never a removal. Recheck with an authoritative library/playlist scan before a destructive action. A preview is read-only discovery; an actual migration must have a durable write journal.

The known client-disagreement incident is recorded in [Historical observations](HISTORICAL_OBSERVATIONS.md): desktop and phone disagreed, while a long migrator Build preview showed discovery only. Its private track identity is intentionally omitted, and it cannot be attributed as an account write.

## Query and safety rules

`find` returns every placement. `union`, `intersection`, and `difference` compare distinct available observed identities within a snapshot; they do not create a playback sequence or publish anything. `compare` retains unknown coverage. CSV positions are zero-based and arrays are JSON text.

- Do not silently discard duplicates, reorder placements, overwrite snapshots, or turn failed coverage into emptiness.
- Do not claim metadata backs up audio, removes Spotify's playlist cap, or reproduces provider playback.
- Only reviewed migration actions may alter Spotify: add and verify replacements before removing originals.
