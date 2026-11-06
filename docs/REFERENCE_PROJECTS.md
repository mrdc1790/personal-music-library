# Reference projects: identity, coverage, and release discovery

Public source and deployed assets were inspected without a Spotify account session. The tools' behavior can change between builds.

## Spotify Dedup

The hosted build inspected on November 5, 2026 defaults to keeping the oldest
addition in each within-source group. It compares Spotify `added_at` timestamps
and uses position when the timestamps tie or either is missing. It groups matching IDs
first, then compares the survivors by case-insensitive title and first artist.
Adjacent durations within two seconds can form a group, so a chain can span
more than two seconds. Strict ID matching, tolerance, and keep-newest settings
are configurable. Different release IDs can match even without relink evidence.
The separate Across Playlists mode lets users choose where to retain a song,
including Liked Songs as a source.
[Site FAQ](https://spotify-dedup.com/) · [Deployed matcher](https://spotify-dedup.com/_next/static/chunks/06j28pnnypgk8.js) · [Deployed defaults](https://spotify-dedup.com/_next/static/chunks/35oj_1u_uq8g5.js)

The [public repository matcher](https://github.com/JMPerez/spotify-dedup/blob/5742217f733f9f0191c0be6f3cdc80bec57ae0de/dedup/deduplicator.ts)
keeps the first match it encounters and skips null IDs. The deployed matcher
uses timestamps and skips missing track objects. In its within-source path,
ID-less rows also fail to enter fuzzy matching. These rules provide candidate
groups, with possible false matches and incomplete local/device coverage.

The deployed scan filters to owned, nonempty playlists, reuses its first
Liked Songs page, and fetches up to five additional pages concurrently per
source. It matches locally and batches playlist removals by position and likes
by ID. The public repository's snapshot cache for clean playlists is an older
implementation detail. A playlist fetch failure can advance the deployed scan's
progress, so a completed progress bar alone does not establish coverage.
[Deployed scan](https://spotify-dedup.com/_next/static/chunks/2y8dhnmqi11di.js) · [Deployed pager and deletion](https://spotify-dedup.com/_next/static/chunks/06j28pnnypgk8.js) · [Public snapshot cache](https://github.com/JMPerez/spotify-dedup/blob/5742217f733f9f0191c0be6f3cdc80bec57ae0de/dedup/playlistCache.ts)

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
