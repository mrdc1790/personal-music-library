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
5. Add [artist history and enrichment](#artist-history-and-enrichment-planned): followed-artist snapshots, source-dated genre evidence, and manual overrides without inventing history.
6. Build recording/source relationships for ordinary single/album/deluxe/compilation duplicates as well as shadow releases, market relinks, and local/cloud candidates. Keep genuine versions distinct. Apply the same taxonomy to playlists and Liked Songs before expanding automatic resolution.

### Reconciliation acceptance criteria (planned)

- Capture comparable, timestamped API, desktop, web, Spotifast, and phone observations with account, market, filters, app/version, and coverage; retain old-device observations as history rather than current totals.
- Show endpoint total versus fetched/exported/imported rows, exact identities, local references, missing objects, and failures separately. Never label a bounded preview or complete endpoint traversal as complete device coverage.
- Produce item-level A-only/B-only/shared/unknown comparisons before assigning causes. With only a displayed count, report the gap as unresolved; do not manufacture a missing-song list.
- Inventory all selected audio roots read-only with per-file path, size, metadata, duration, read errors, optional byte hash, and later optional fingerprint. Distinguish file presence, Spotify discovery, playlist membership, download indication, and verified playback per device.
- Review exact/likely/ambiguous/unmatched reference-to-file and file-to-recording candidates; preserve many occurrences pointing to one file and multiple files pointing to one recording.
- Add synthetic regression cases for equal counts with different members, partial pages, unavailable items, local-only files, repeated local URIs, copied/transcoded files, and single/album IDs with no relink evidence in both playlists and Liked Songs. Cover remix/clean/live false matches and pre-existing replacement occurrences.
- Keep candidate grouping, preferred-version migration, occurrence deduplication, and local-file cleanup as separate decisions. A migration must not silently collapse playlist duplicates.

### Artist history and enrichment (planned)

Retain this as an extension of the catalog, reusing capture, coverage, and offline reporting infrastructure. The current `artist_playlist_summary.csv` already distinguishes primary-credit placements, all-credit placements, and distinct observed track identities per source, with unmatched name-only artists kept separate. Follow history, external genre enrichment, persistent artist mappings, and the richer dashboard below are not implemented.

- **Follow observations:** preserve each capture's artist IDs, returned API rank, account, capture time, and completion evidence. Track initial import, first/last seen, last confirmed followed, and observed follow/unfollow/refollow transitions. Detection times and intervals are not original follow dates; API rank is not chronology. Transitions entirely between captures are unknowable.
- **Complete comparisons:** record transitions only between validated complete followed-artist captures for the same account. A partial or failed capture cannot mark absent artists as unfollowed or replace the last complete baseline. Retain its failure evidence separately.
- **Library statistics:** distinguish primary versus all credited artists, distinct observed track identities versus placements, distinct owned versus other accessible playlists, and Liked Songs membership. Every metric must name its snapshot and coverage. Earliest/latest captured save or playlist-add timestamps provide library evidence, not a discovery or follow date. Recording-level counts require separately reviewed identity groups.
- **Genre provenance:** retain raw tags, provider, retrieval time, matched artist identity, match evidence, normalized labels, and manual include/exclude overrides. Overrides are explicit user choices rather than extra weighted votes. Preserve meaningful subgenres and original labels. Any scoring weights are provisional heuristics, not calibrated probabilities; artist genres do not automatically establish track genres, mood, BPM, or key.
- **Identity review:** maintain reviewable mappings for local artist text and external artist identifiers, retaining ambiguous and unmatched candidates. Equal names alone must not merge artists. Keep unresolved local references visible; this does not substitute for filesystem inventory.
- **Report views:** consider Artists, Follow Changes, Artist–Playlist Relationships, Genre Evidence, Unmatched Local References, Run History, and a Data Dictionary. A dashboard can highlight missing genres, newly observed artists, and followed artists with no tracks in the captured sources. CSV/HTML views can precede an optional workbook; exporting must not require Spotify calls.
- **Independent refresh:** separate follow capture, playlist/library capture, enrichment, and report generation. Reuse captures only under their existing validation rules; cache enrichment with source timestamps and refresh policy. Revalidate provider fields and endpoints before implementation and retain unavailable metadata as unknown rather than zero.
- **Historical imports:** existing dated artist exports could seed earlier observations after validating artist identities, capture provenance, account, and completeness. Filenames alone do not establish capture times or follow dates. Incomplete exports cannot establish unfollows.

Start with complete follow snapshots and an artist report joined to existing catalog observations, then add reviewed mappings, genre enrichment, and richer presentation. Before shipping, cover partial captures, initial imports, observed refollows, duplicate artist names, featured credits, repeated placements, incomplete playlist coverage, manual exclusions, and uncertain historical imports with synthetic tests.

These requirements preserve the useful design from the earlier “Spotify Library Tracker Design” discussion without depending on that chat remaining available. They do not change the current priority order or authorize artist-follow changes. Cross-repository scope was checked: this read-only catalog feature needs no companion change in the separate playlist migrator.

### Followed-artist release inbox (planned)

Preserve the useful design from the “RiffRadar Spotify investigate” discussion here so the chat can be deleted. This is a future catalog extension after the current coverage and identity work, not implemented automation.

- **Collection and views:** maintain a durable Followed Artist Releases collection; New Music Friday is a weekly release-date view, with an explicit timezone and week boundary. Keep provider release date and its precision separate from first detection time. Late discoveries and backfills remain visible rather than falling out of history.
- **Capture evidence:** a future daily read-only scan should record the followed-artist snapshot, account/market, artist and release IDs, ordered track listings, capture/detection times, and per-artist pagination, failures, and coverage. Failed or partial scans cannot establish no new releases. Initial catalog import needs an explicit baseline/backfill policy.
- **Identity and filters:** preserve raw releases and track occurrences before applying reviewed recording groups or presentation deduplication. Single/album overlap, reuploads, deluxe editions, remixes, live versions, compilations, featured credits, and incorrect artist attribution need explicit rules and uncertain candidates. New provider IDs do not automatically mean new recordings; matching recordings must not erase release history.
- **Separate outputs:** release detection, catalog storage, local recipe views, and Spotify publishing are separate stages. A future publisher requires explicit authorization, a preview, retry-safe addition tracking, readback verification, and a visible playlist-capacity policy. Retain the full local history even when a bounded Spotify view rotates; never silently purge existing playlist entries or deduplicate user occurrences.
- **Validation before implementation:** recheck current endpoint capabilities, scopes, rate limits, and market/date behavior. Use synthetic cases for incomplete artist pages, failed scans, repeated detection, delayed availability, imprecise dates, reuploads, version ambiguity, and capacity exhaustion before any account-backed trial.

See [release-discovery research leads](REFERENCE_PROJECTS.md#release-discovery-research-leads). Third-party playlists can be observed as sources with their own provenance and coverage; they cannot prove exhaustive release detection. Cross-repository impact was checked against the separate playlist migrator's context and safety guidance: this plan belongs to the catalog and requires no migrator edit, shared runtime, OAuth change, or migration behavior change.

## Planned interfaces

- A Smarter Playlists-style local recipe UI: choose a snapshot, connect sources and set operations, preview, then save a reusable recipe. Scheduling and publishing come later.
- Dry-run M3U/server-playlist reports after local audio is actually matched. Symfonium, Navidrome, and Jellyfin can be owned-audio endpoints; they do not turn streaming metadata into audio.
- BPM, key, energy, genre, mood, and DJ export only where evidence or analysis supplies it.
- Provider adapters for Spotify, local/server, and potential Apple Music, YouTube, or SoundCloud references, each with a capability matrix.

## Not current CLI scope

No audio downloading or redistribution; universal queue, offline playback, or Connect replacement; automatic account writes; guaranteed cross-service link conversion; hosted multi-device database; or business/legal/provider-policy conclusions based only on design notes.

The roadmap preserves the broader idea without presenting aspiration as delivered functionality.
