# Data dictionary and identity rules

This describes the implemented catalog, not the larger planned recording graph.

## Terms

| Term | Definition |
|---|---|
| Snapshot | One imported audit scan, with its raw JSON and coverage status |
| Source | A Spotify playlist ID, or the reserved ID `liked` for Liked Songs |
| Occurrence / placement | One item at one zero-based position within a source |
| Track key | The identity available to this scan, selected using the rules below |
| Recording | An underlying performance/recording, potentially released more than once; canonical grouping is planned |
| Returned ID | ID Spotify returned, potentially affected by relinking |
| Original ID evidence | The old ID explicitly exposed through relinking metadata; absence remains unknown |
| Local reference | Metadata describing a local track, not a file path or an audio copy |
| Primary artist | The first artist in the returned credits |
| All credits | Every distinct artist ID credited on the item; name-only local credits stay separate |
| Client membership observation | A timestamped client/API claim about membership; evidence, not a replacement for a stored occurrence |

## Implemented tables

| Table/view | Key | Purpose |
|---|---|---|
| `catalog_meta` | key | Schema version; currently 1 |
| `snapshots` | integer id; unique SHA-256 | Label, account, source time, status, complete raw JSON |
| `playlists` | snapshot_id + source | Name, successful-export flag, raw playlist metadata; includes Liked Songs |
| `items` | snapshot_id + source + position | Every occurrence with queryable metadata and complete raw occurrence JSON |
| `membership` (view) | snapshot_id + track_key + source | Occurrence count per identity/source, excluding explicit missing objects |

Foreign keys link occurrences to their source/snapshot. Import is transactional. Invalid or non-contiguous positions roll back the entire new snapshot. Exact duplicate snapshots are not imported twice. Each catalog is restricted to one account; synthetic examples use a different account identity.

`items` exposes title, artist names, returned/original identity, local/missing/playable flags, album, duration, ISRC, and added timestamp. Raw JSON retains artist IDs, release dates, explicit status, attribution, and other fields even when a dedicated table column does not exist. CSV generation extracts several of these fields from that raw JSON.

A distinct `artists` or `canonical_recordings` table is not implemented yet. Artist reports are derived from preserved credits. This avoids pretending that the larger proposed schema already exists.

## Identity selection

Selection happens in this order:

1. An explicitly missing object gets a unique unknown key for its snapshot/source/position.
2. A local item uses its preserved local URI when present; otherwise it gets an unknown key.
3. Explicit `original_id` evidence produces a Spotify track URI for that original.
4. Otherwise use the returned URI, or returned ID if the URI is absent.
5. If no identity is available, use an unknown key.

Every row carries `identity_basis`: `original_id_evidence`, `returned_uri_only`, `returned_id_only`, `local_metadata_reference`, or `unidentified`.

**A returned-only key is an observation, not proof of stored identity.** Two different releases are never automatically merged by title or ISRC. A local URI is not globally unique audio identity: two files can share metadata. Unknown keys are excluded from set results and make exact sequence comparisons uncertain.

Spotify documents local references and their metadata-based form in its [playlist concepts](https://developer.spotify.com/documentation/web-api/concepts/playlists). That documentation does not establish a full client fingerprint algorithm or per-device playback state.

## Planned cross-client observations

The current catalog stores snapshots, not client UI claims. Before using those
claims in automation, add an append-only observation record for occurrence URI
and position, requested/effective URI, timestamp, platform/version, market, UI
surface, result and evidence. Client absence is conflicting/unknown evidence;
only a fresh authoritative scan may authorize removal.

## Query behavior

`find` searches title, artist text, returned/original ID and track key, case-insensitively. It returns every matching occurrence, including duplicates.

`query` compares distinct available identities within the selected snapshot. At least two distinct, successfully exported source IDs are required. Union/intersection/difference do not produce playback order; results are sorted by identity key. No canonical-recording query mode exists yet.

`compare` compares source sequences, names and occurrence counts. It preserves duplicate-count changes. It flags absent/unread sources as unknown coverage rather than claiming deletion. Unknown identities prevent exact comparison for that source. It does not yet classify moves separately from other sequence changes or report every metadata-only change.

The catalog currently loads selected snapshot rows into memory for several operations. It has not been benchmarked on your full library. A later performance pass can add narrower SQL queries, caching and incremental scanning based on measured needs.

## Counts

- Source count counts distinct playlists plus Liked Songs, if present.
- Occurrence count includes every placement, including repeats.
- Artist primary placements count first credits.
- Artist all-credit placements count each credited artist once per occurrence.
- Artist distinct observed tracks deduplicate track keys within a source.
- Name-only artist keys are labeled `unmatched-name:` and are not joined to Spotify artist IDs.

Example: a song twice in Chill and once in Festival has three occurrences and two sources. Its collaborator gets three all-credit placements but zero primary placements if always second in the credits.

## Dates and coverage

`created_at` is the scan time supplied by the audit. `added_at` is the item timestamp returned by Spotify when present. Neither is an artist-follow timestamp.

“Latest” means most recently imported snapshot ID. Out-of-order historical imports do not automatically sort by scan date; select an explicit snapshot ID when needed.

The existing audit checks playlist snapshot stability but does not obtain an atomic snapshot of the whole account. Liked Songs lack equivalent version checks. An incomplete scan may contain useful data without establishing full coverage. Raw status and errors remain available in `snapshots.raw_json`.

The `exported` flag for Liked Songs is inferred from the current audit's completion states. Other formats and arbitrary CSV exports are not supported inputs. There is no silent generic importer.

## CSV details

UTF-8 with BOM; zero-based positions; arrays serialized as JSON text; missing values blank. Potential formula prefixes are escaped with an apostrophe for spreadsheet use. Exact originals remain in SQLite/JSON.

`tracks.csv` chooses a representative occurrence's metadata for each key within one snapshot. If returned metadata differs across occurrences, consult `playlist_items.csv` or raw JSON. It is not a deduplicated recording catalog.

Per-playlist filenames use a truncated SHA-256 of the source ID, keeping unsafe/duplicate playlist names out of paths. The manifest contains the name↔ID↔filename mapping and coverage flags. Failed exports can yield empty CSVs; always read the coverage flag before interpreting emptiness.

## Planned data extensions

Separate canonical recording/source mappings; reviewed local files and fingerprints; folder hierarchy and placement; followed-artist snapshots and detected events; genre evidence/manual overrides; collection rules and projection plans. These should be added with schema migrations and explicit provenance. Do not manually add columns to a working database and assume the CLI understands them.
