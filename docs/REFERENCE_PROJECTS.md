# Reference projects: duplicate detection, relinking, and coverage

Reviewed on 2026-09-25. This is a source review, not an account-backed compatibility test. The linked branches and deployed site can differ and can change. Neither tool was run against the account.

## Spotify Dedup

The [current site](https://spotify-dedup.com/) describes playlist and Liked Songs duplicate review using IDs and title/artist/duration similarity, configurable matching, oldest/newest retention, and cross-playlist review. The older [repository README](https://github.com/JMPerez/spotify-dedup) emphasizes identical URIs, so that description alone is incomplete.

The inspected [deduplicator source](https://github.com/JMPerez/spotify-dedup/blob/master/dedup/deduplicator.ts) checks identical IDs or case-insensitive title plus first artist with duration difference below 2,000 ms. It skips null tracks and null IDs, including typical local objects. Both playlist and saved-track paths exist. Thus ordinary single/album IDs can be candidates without relink evidence; this is heuristic matching, not proof of identical recordings. The inspected source is not proof that every deployed advanced option uses that exact algorithm.

It removes duplicates rather than lifting every source occurrence to a preferred ID. Its API view and skipped objects cannot inventory local files or resolve desktop/phone count discrepancies. Similarity can confuse versions; a no-duplicates result does not prove complete coverage or a shadow-free library.

## Spotify Song Relinker

[AfterForever667/spotify_songs_relink](https://github.com/AfterForever667/spotify_songs_relink) is the specific project named in the planning document. Its [Python source](https://github.com/AfterForever667/spotify_songs_relink/blob/main/spotify_songs_relink.py), labeled version 2.1.0, processes Liked Songs or one owned playlist. It uses exposed relink information or searches for a playable replacement for an unavailable item. Ordinary playable single/album duplicates without a relink are not generally detected by this logic.

Its per-page dictionary collapses repeated IDs and excludes missing IDs; the audit log therefore is not a full occurrence/local-file inventory. Unavailable-item search accepts a playable matching title after an artist-qualified search, without verifying ISRC/duration equivalence. Playlist writes append a replacement and remove all old occurrences, with no intervening readback verification; liked-track writes similarly add then remove. This does not satisfy our position, multiplicity, or verified-add guarantees. Its Excel report cannot explain device-count discrepancies. API capability/endpoint compatibility still needs separate validation; a returned ID is not a universal canonical recording ID.

## Requirements for our projects

| Question | Required treatment |
|---|---|
| Same recording on single and album? | Candidate relation in playlists and likes, even without a shadow/relink; review genuine-version differences |
| Local files included? | Preserve API local references AND separately inventory chosen file roots/device evidence; never infer one from the other |
| Totals disagree? | Preserve endpoint/client counts and coverage, then compare actual items; leave count-only gaps unresolved |
| Replace or deduplicate? | Separate reviewed actions; migration preserves duplicate placements and existing destination occurrences |
| Missing or hidden data? | Unknown coverage, not a clean bill of health or permission to delete |

Spotify documents [local playlist objects](https://developer.spotify.com/documentation/web-api/concepts/playlists) as metadata references and [market relinking](https://developer.spotify.com/documentation/web-api/concepts/track-relinking) as availability-dependent instance resolution. Neither establishes complete local-device inventory or every recording-equivalence relationship. Apply the [taxonomy](EVIDENCE_AND_MODEL.md#duplicate-and-identity-taxonomy) and [reconciliation acceptance criteria](ROADMAP.md#reconciliation-acceptance-criteria-planned).
