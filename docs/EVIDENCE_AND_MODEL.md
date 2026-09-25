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

### Duplicate and identity taxonomy

These categories can overlap; label the relationship and evidence instead of calling everything a shadow track.

| Category | What differs or repeats | Treatment |
|---|---|---|
| URL alias | Different share parameters around the same Spotify track ID | Normalize the ID; these URLs are not distinct tracks |
| Exact occurrence duplicate | Same observed URI appears more than once in one playlist | Preserve positions and multiplicity; removal is a separate reviewed deduplication operation |
| Cross-source overlap | Same identity occurs in several playlists and/or Liked Songs | Usually intentional membership, not redundant data to delete |
| Ordinary release duplicate | A single and later album, deluxe, or compilation use different IDs for a candidate same recording | Explicitly in scope for future recording matching in playlists AND Liked Songs; does not require a shadow release or `linked_from` |
| Shadow/re-uploaded catalog instance | Older and newer IDs appear to represent the same recording after catalog replacement | Retain both instances, provenance, and reviewed mapping; do not infer equivalence from navigation |
| Market relinking | Requested/stored and returned/playable objects differ | Keep original and effective identities separately when exposed; missing original identity is unknown |
| Meaningfully different version | Live, remix, remaster, edit, acoustic, rerecording, or clean/explicit variant | Keep distinct unless the user deliberately approves a version substitution; that is not proven duplicate removal |
| Local/cloud candidate match | Local reference or owned file resembles a Spotify recording | Preserve local file ownership/path evidence and cloud identity separately; no automatic replacement |
| Local reference or file duplicate | Repeated local URI, copied bytes, retagged/transcoded file, or similar audio | Count references, file paths, byte hashes, and recording candidates separately; URI equality does not prove identical files |
| Missing/unavailable object | Null item, inaccessible source, unavailable track, or hidden identity | Preserve evidence and coverage; not an empty source or a duplicate |
| Client/count disagreement | Clients report different counts, membership, download, or playback state | Reconciliation issue, not proof of duplicates or deletion |

Same ISRC, title, artist, or duration can support a candidate but cannot alone prove identical audio. Different ISRCs do not automatically rule out a candidate. Candidate grouping must retain confidence, contradictory evidence, and explicit keep-separate decisions. Current exact-ID duplicate/set reports do not implement this recording-level taxonomy.

`items` retains title, artist text, returned/original identity, local/missing/playable flags, album, duration, ISRC, and added timestamp, while raw entries retain other source metadata. Artist reports distinguish first-credit placement counts, all-credit placement counts, distinct observed identities, and unmatched name-only local credits. These are observations, not artist-follow history or canonical artist records.

## Coverage, counts, and local files

An unreadable, partial, or unexported source is never empty. Comparisons distinguish coverage changes from membership changes. Unknown identities remain visible in occurrence browsing but cannot safely participate in set operations.

Name what a count means: sources, occurrences, distinct observed identities, artist credits, local references, or files. A local reference is not a distinct audio file. For future file reconciliation, scan explicit roots read-only and report exact, likely, ambiguous, unmatched, and incomplete results separately. Metadata URI, byte hash, and audio fingerprint are different evidence.

Playlist capture includes local references only when Spotify returns those rows. The desktop **Local Files** collection is not automatically an API playlist or a filesystem inventory. Files absent from captured playlists remain outside that capture. The `liked` source is the saved-track endpoint observation, not a guaranteed reproduction of every client's Liked Songs display. Zero API local rows means zero observed rows, not zero local songs or local likes on devices.

Maintain separate totals for endpoint-reported total, fetched rows, exported/imported rows, distinct observed IDs, local occurrences, distinct local URIs, missing objects, physical files, and reviewed recording groups. Record endpoint, account, market, app/API capability, time window, pagination/completion status, and client filters. Agreement between an API tool and Spotifast does not prove independent coverage; their underlying data paths must be established. A completed API traversal establishes that endpoint's observed coverage, not a universal inventory of device state.

Counts alone cannot identify a difference set. Do not subtract the entire Local Files count from Liked Songs: overlap and inclusion semantics are unverified. Even equal counts can hide different membership. The home computer is the user's preferred reference for intended state, while each device remains a separate observation.

## Client disagreement

Phone, desktop, and web clients can show incompatible membership state even when playback succeeds. Record stored occurrence URI/position, requested/effective URI when known, time, platform/app version, market, UI surface, result (`present`, `absent`, `unknown`), and raw evidence.

“Not shown on phone” is conflicting or unknown evidence, never a removal. Recheck fresh API membership and playlist evidence within their documented scope before a destructive action; API visibility alone cannot settle local-device coverage. A preview is read-only discovery; the catalog migration engine requires a durable write journal.

The known client-disagreement incident is recorded in [Historical observations](HISTORICAL_OBSERVATIONS.md): desktop and phone disagreed, while a long migrator Build preview showed discovery only. Its private track identity is intentionally omitted, and it cannot be attributed as an account write.

## Query and safety rules

`find` returns every placement. `union`, `intersection`, and `difference` compare distinct available observed identities within a snapshot; they do not create a playback sequence or publish anything. `compare` retains unknown coverage. CSV positions are zero-based and arrays are JSON text.

- Do not silently discard duplicates, reorder placements, overwrite snapshots, or turn failed coverage into emptiness.
- Do not claim metadata backs up audio, removes Spotify's playlist cap, or reproduces provider playback.
- Only reviewed migration actions may alter Spotify: add and verify replacements before removing originals.
