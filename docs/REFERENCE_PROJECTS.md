# Reference projects: identity, coverage, and release discovery

Reviewed on 2026-09-25. This is a source review, not an account-backed compatibility test. The linked branches and deployed site can differ and can change. Neither tool was run against the account.

## Spotify Dedup

The [current site](https://spotify-dedup.com/) describes playlist and Liked Songs duplicate review using IDs and title/artist/duration similarity, configurable matching, oldest/newest retention, and cross-playlist review. The older [repository README](https://github.com/JMPerez/spotify-dedup) emphasizes identical URIs, so that description alone is incomplete.

The inspected [deduplicator source](https://github.com/JMPerez/spotify-dedup/blob/master/dedup/deduplicator.ts) checks identical IDs or case-insensitive title plus first artist with duration difference below 2,000 ms. It skips null tracks and null IDs, including typical local objects. Both playlist and saved-track paths exist. Thus ordinary single/album IDs can be candidates without relink evidence; this is heuristic matching, not proof of identical recordings. The inspected source is not proof that every deployed advanced option uses that exact algorithm.

It removes duplicates rather than lifting every source occurrence to a preferred ID. Its API view and skipped objects cannot inventory local files or resolve desktop/phone count discrepancies. Similarity can confuse versions; a no-duplicates result does not prove complete coverage or a shadow-free library.

## Spotify Song Relinker

[AfterForever667/spotify_songs_relink](https://github.com/AfterForever667/spotify_songs_relink) is the specific project named in the planning document. Its [Python source](https://github.com/AfterForever667/spotify_songs_relink/blob/main/spotify_songs_relink.py), labeled version 2.1.0, processes Liked Songs or one owned playlist. It uses exposed relink information or searches for a playable replacement for an unavailable item. Ordinary playable single/album duplicates without a relink are not generally detected by this logic.

Its per-page dictionary collapses repeated IDs and excludes missing IDs; the audit log therefore is not a full occurrence/local-file inventory. Unavailable-item search accepts a playable matching title after an artist-qualified search, without verifying ISRC/duration equivalence. Playlist writes append a replacement and remove all old occurrences, with no intervening readback verification; liked-track writes similarly add then remove. This does not satisfy our position, multiplicity, or verified-add guarantees. Its Excel report cannot explain device-count discrepancies. API capability/endpoint compatibility still needs separate validation; a returned ID is not a universal canonical recording ID.

## Release-discovery research leads

Reviewed on 2026-09-30 to preserve the project-relevant ideas from the “RiffRadar Spotify investigate” chat. This is public documentation research, not an account-backed test or a decision to connect a service.

- **[RiffRadar](https://riffradar.org/):** the earlier chat described followed-artist/discography playlist generation and daily refresh. The current page returned only “Checking service status” to the reader, so cadence, pricing, availability, and release completeness remain unverified. Keep it as a research lead for discovery and smart-playlist design, not a confirmed exhaustive release collector.
- **[SpotifyDiscoveryBot](https://github.com/Selbi182/SpotifyDiscoveryBot):** its README describes scheduled followed-artist crawling, configurable album/single/EP/remix/live/compilation/re-release groups, and filtering of reuploads and artist misattribution. These are useful design questions, not proof of recording equivalence or current API compatibility. Its circular playlist fitting removes old entries at the documented 10,000-track limit; optional AutoPurge also removes entries. That behavior does not satisfy this catalog's durable-history requirement. Review implementation, license, identity heuristics, and account-write behavior before reuse or execution.
- **[Tracknack](https://tracknack.com/spotify-new-releases):** the provider advertises artist/label release monitoring and automatic playlist delivery, plus producer/credit discovery. Its page says the free plan runs weekly and covers up to 30 artists or labels; daily/hourly scheduling is paid. Claims of catching every release are vendor claims, not verified coverage guarantees. Recheck plans and large-library limits before considering a trial.

These tools address release detection or playlist delivery, not the catalog's snapshots, local-file inventory, recording review, or the separate migrator's verified replacement workflow. Preserve detection and release evidence locally; a changing third-party playlist is not the source of truth. The [planned release inbox](ROADMAP.md#followed-artist-release-inbox-planned) separates durable observations from weekly views and any future authorized Spotify writes. No service was installed, connected, or run, and deleting the source chat will not remove these requirements or research links.

## Requirements for our projects

| Question | Required treatment |
|---|---|
| Same recording on single and album? | Candidate relation in playlists and likes, even without a shadow/relink; review genuine-version differences |
| Local files included? | Preserve API local references AND separately inventory chosen file roots/device evidence; never infer one from the other |
| Totals disagree? | Preserve endpoint/client counts and coverage, then compare actual items; leave count-only gaps unresolved |
| Replace or deduplicate? | Separate reviewed actions; migration preserves duplicate placements and existing destination occurrences |
| Missing or hidden data? | Unknown coverage, not a clean bill of health or permission to delete |

Spotify documents [local playlist objects](https://developer.spotify.com/documentation/web-api/concepts/playlists) as metadata references and [market relinking](https://developer.spotify.com/documentation/web-api/concepts/track-relinking) as availability-dependent instance resolution. Neither establishes complete local-device inventory or every recording-equivalence relationship. Apply the [taxonomy](EVIDENCE_AND_MODEL.md#duplicate-and-identity-taxonomy) and [reconciliation acceptance criteria](ROADMAP.md#reconciliation-acceptance-criteria-planned).
