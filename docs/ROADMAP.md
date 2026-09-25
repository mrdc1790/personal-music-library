# Roadmap: catalog first, music hub later

## Direction

The longer-term vision is a personal-use-first music hub for power users and playlist creators: fast organization, larger local collections, overlap and duplicate awareness, owned audio, richer metadata, cross-provider references, DJ workflows, discovery, and eventually sharing or AI-assisted filters. It is valuable even if it never becomes a distributed streaming service.

The grounded architecture is a local catalog that observes provider metadata and owned-audio sources. A wrapper can link to provider content where APIs allow, but licensing, playback, social features, provider capabilities, and commercialization require separate current validation.

## Current priority

Finish useful read-only coverage, import it, and make playlist size, overlap, duplicate occurrences, and local collection visibility practical. Spotify's 10,000-item playlist limit remains a service constraint. The future response is a larger local collection with reviewed, bounded provider outputs—not a claim to bypass the limit.

## Next work

1. Validate a real resumable scan and catalog import at useful coverage.
2. Improve full-library ingestion, browsing, playlist-size views, overlap, and duplicate review.
3. Inventory user-chosen local-audio roots, including files never placed in Spotify playlists, and reconcile desktop/phone inventories with Spotify local references. Retain missing roots, read errors, and unknown phone coverage.
4. Validate one small live Spotifast folder-tree import.
5. Add followed-artist snapshots, source-dated genre evidence, and manual overrides without inventing history.
6. Build recording/source relationships for ordinary single/album/deluxe/compilation duplicates as well as shadow releases, market relinks, and local/cloud candidates. Keep genuine versions distinct. Apply the same taxonomy to playlists and Liked Songs before expanding automatic resolution.

### Reconciliation acceptance criteria (planned)

- Capture comparable, timestamped API, desktop, web, Spotifast, and phone observations with account, market, filters, app/version, and coverage; retain old-device observations as history rather than current totals.
- Show endpoint total versus fetched/exported/imported rows, exact identities, local references, missing objects, and failures separately. Never label a bounded preview or complete endpoint traversal as complete device coverage.
- Produce item-level A-only/B-only/shared/unknown comparisons before assigning causes. With only a displayed count, report the gap as unresolved; do not manufacture a missing-song list.
- Inventory all selected audio roots read-only with per-file path, size, metadata, duration, read errors, optional byte hash, and later optional fingerprint. Distinguish file presence, Spotify discovery, playlist membership, download indication, and verified playback per device.
- Review exact/likely/ambiguous/unmatched reference-to-file and file-to-recording candidates; preserve many occurrences pointing to one file and multiple files pointing to one recording.
- Add synthetic regression cases for equal counts with different members, partial pages, unavailable items, local-only files, repeated local URIs, copied/transcoded files, and single/album IDs with no relink evidence in both playlists and Liked Songs. Cover remix/clean/live false matches and pre-existing replacement occurrences.
- Keep candidate grouping, preferred-version migration, occurrence deduplication, and local-file cleanup as separate decisions. A migration must not silently collapse playlist duplicates.

## Planned interfaces

- A Smarter Playlists-style local recipe UI: choose a snapshot, connect sources and set operations, preview, then save a reusable recipe. Scheduling and publishing come later.
- Dry-run M3U/server-playlist reports after local audio is actually matched. Symfonium, Navidrome, and Jellyfin can be owned-audio endpoints; they do not turn streaming metadata into audio.
- BPM, key, energy, genre, mood, and DJ export only where evidence or analysis supplies it.
- Provider adapters for Spotify, local/server, and potential Apple Music, YouTube, or SoundCloud references, each with a capability matrix.

## Not current CLI scope

No audio downloading or redistribution; universal queue, offline playback, or Connect replacement; automatic account writes; guaranteed cross-service link conversion; hosted multi-device database; or business/legal/provider-policy conclusions based only on design notes.

The roadmap preserves the broader idea without presenting aspiration as delivered functionality.
