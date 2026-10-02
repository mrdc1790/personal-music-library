# Roadmap: catalog first, music hub later

## Direction

The longer-term vision is a personal-use-first music hub for power users and playlist creators: fast organization, larger local collections, overlap and duplicate awareness, owned audio, richer metadata, cross-provider references, DJ workflows, discovery, and eventually sharing or AI-assisted filters. It is valuable even if it never becomes a distributed streaming service.

The grounded architecture is a local catalog that observes provider metadata and owned-audio sources. A wrapper can link to provider content where APIs allow, but licensing, playback, social features, provider capabilities, and commercialization require separate current validation.

## Current priority

Retain SQLite for the local operational catalog. The [storage decision and alternatives](STORAGE_DECISION.md) explain the fit, query-performance work, optional analytics path, and criteria for reconsidering a server database. No cloud service or second database engine is currently required.

Finish useful read-only coverage, import it, and make playlist size, overlap, duplicate occurrences, and local collection visibility practical. Spotify's 10,000-item playlist limit remains a service constraint. The future response is a larger local collection with reviewed, bounded provider outputs—not a claim to bypass the limit.

## Next work

1. Validate a real resumable scan and catalog import at useful coverage.
2. Improve full-library ingestion, browsing, playlist-size views, overlap, and duplicate review.
3. Extend the implemented read-only local inventory and filename-candidate reports with richer file evidence, including files never placed in Spotify playlists, and reconcile desktop/phone inventories with Spotify local references. Retain missing roots, read errors, and unknown phone coverage.
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

#### Follow intervals, assertions, and exploration views

The full “Spotify Library Tracker Design” source was rechecked on 2026-09-30. Preserve structured captures directly in the catalog; formatted TXT, names lists, and an optional workbook are generated compatibility/report outputs, not a required TXT-to-regex ingestion pipeline. Historical TXT imports must validate record structure, declared count, artist IDs, and provenance while retaining malformed/incomplete evidence separately.

Future artist reports should include capture/rank history, initial-baseline status, observed refollow count, first/last confirmed presence, primary/all-credit liked counts, distinct owned/accessibly captured playlist counts, placements, unmatched local credits, earliest/latest library evidence, enrichment status, and data-quality flags. Optional provider follower/popularity/genre fields remain nullable and source-dated, not required rankings. Retain genre alias rules and any parent-genre derivation separately from raw tags; revise mappings explicitly instead of silently collapsing meaningful subgenres. External artist-ID matching precedes genre enrichment, with ambiguous matches kept for review.

For optional workbook output, use filterable artist tables, separate artist–playlist relationship rows, links, frozen headers, and status/coverage formatting. Treat provider text as text rather than spreadsheet formulas. Export from saved evidence without network calls; workbook support requires a separately approved dependency. Refresh policies need explicit source timestamps and expiry rules rather than adopting the chat's suggested cache durations as validated defaults. Follow capture completion and derived transition updates must commit consistently, while failed capture evidence remains retained. Proposed `spotify_tracker.py` commands in the chat are not implemented commands.

The “Artist History Design” discussion was reviewed on 2026-09-30. Its main requirements are already captured above; retain these additional details without depending on the chat:

- **Synthetic interval example:** complete captures contain artist C on June 1, omit C on July 1, and contain C again on August 1. Report an observed unfollow transition in `(June 1, July 1]` and refollow in `(July 1, August 1]`, not exact action dates. This assumes comparable captures for the same account; an incomplete July capture establishes neither transition. The initial capture establishes a baseline, not when following began.
- **Separate evidence layers:** store captured facts, derived summaries/intervals, and dated user assertions separately. A recollection such as “I discovered this artist around 2015” is an attributed assertion; an observed save timestamp or earliest captured placement must not overwrite it or become a discovery date. Derived results should retain input snapshot IDs and derivation rules.
- **Durable decisions:** reviewed local-text-to-artist mappings and manual genre include/exclude choices must survive enrichment refreshes. Retain decision provenance and allow explicit revision; provider updates do not silently undo a user decision. Preserve raw tags and unresolved name collisions alongside the chosen view.
- **Exploration views:** consider genre/subgenre filters for followed artists with few captured saved tracks, recently observed follows with little captured music, library artists absent from a complete follow capture, and rankings by distinct observed identities or playlist breadth. Label first-credit metrics as credit ordering, not proof that a song is fundamentally one artist's release. Distinguish playlist breadth, Liked Songs membership, placements, and eventually reviewed recording counts. Zero means zero within named coverage; incomplete library capture cannot establish that an artist has no music anywhere in the account.
- **One evidence model, several outputs:** follow observations, genre evidence, reviewed artist mappings, and derived metrics should become versioned entities/relationships in the local SQLite catalog as each feature is implemented. CSV, optional workbooks, HTML dashboards, and future UI are views over that evidence, not independently maintained sources of truth. This does not add a graph database or implement these tables now; follow the [storage decision](STORAGE_DECISION.md) and preserve existing snapshots through tested schema upgrades.

These requirements preserve the useful design from the earlier “Spotify Library Tracker Design” and “Artist History Design” discussions without depending on those chats remaining available. They do not change the current priority order or authorize artist-follow changes. Cross-repository scope was checked: this read-only catalog feature needs no companion change in the separate playlist migrator.

### Recording resolver and release-family discovery (planned)

The “Clarify Spotify Duplicates” discussion has largely already been incorporated into [the identity taxonomy](EVIDENCE_AND_MODEL.md#duplicate-and-identity-taxonomy), [reference-tool research](REFERENCE_PROJECTS.md), and [migration guidance](MIGRATION.md). Its remaining discovery requirement belongs here: begin with one confusing saved track and recover candidate old releases, sibling releases, neighboring tracks, and their captured playlist/Liked Songs placements. These are planned capabilities, not a working `resolve-track` command.

1. Start with a captured provider ID/URI and historical raw metadata. Report its observed release, artists, ISRC, duration, version markers, original/returned identity evidence, snapshot, and coverage. If the old release is unavailable now, keep the historical observations; do not reconstruct missing neighbors from the current album's positions alone.
2. Produce read-only candidate reports from ISRC with artist/duration/version checks, then release-family comparisons, then weaker title/artist/duration candidates. Add external recording IDs and owned-audio fingerprints later. Preserve supporting and contradictory evidence, missing fields, and ambiguous or unmatched tracks. Heuristic labels are not calibrated probability percentages.
3. Compare release track lists beyond disc/track ordinal position. Standard-to-deluxe, resequenced, missing-track, and bonus-track cases need partial candidate mappings with explicit unmatched entries. This does not relax either executor's current album/identity gates.
4. Record relationship classification and reviewed same-recording/keep-separate decisions without deleting provider instances or rewriting historical occurrences. A preferred album/instance is a separate user policy from recording equivalence. Support both literal-instance placement queries and, eventually, reviewed recording-level placement queries.
5. Only a separately reviewed mapping may enter migration planning and explicit execution. Detection, canonical grouping, preferred-instance selection, occurrence deduplication, and migration remain separate actions. Retain unknown coverage and pre-existing destination placements.

Acceptance examples should be synthetic: one saved old track whose album is no longer readable; an old/current album pair; a standard/deluxe pair with unmatched bonus tracks; same ISRC with contradictory version evidence; single/album candidates without exposed relinking; and duplicate placements plus existing destinations. Revalidate available provider metadata before building the resolver; exposed relinking is optional evidence, and a missing field is not proof of no relationship.

Cross-repository scope: this catalog owns historical evidence and the planned detector/resolver. The browser migrator remains independently runnable for reviewed track/album inputs, including selected Liked Songs membership. It is not currently a frontend to `migrate.py`; shared plan import or a unified executor would require a separately designed, versioned interface and tests, not cross-repo imports. The Python engine retains its own execution restrictions and durable journal; browser preview checkpoints are not an equivalent journal.

The linked Google Doc's “Spotify catalog identity and reconciliation — current specification” tab was reviewed on 2026-09-30 and already preserves the shared taxonomy and safety requirements. Repository guides own commands and implementation status. Older chat claims that the browser handles playlists only, that Spotify Dedup matches only identical IDs, or that failure leaves the whole account unchanged are superseded by current documentation. The chat can be deleted without losing this project-relevant design.

### Followed-artist release inbox (planned)

Preserve the useful design from the “RiffRadar Spotify investigate” discussion here so the chat can be deleted. This is a future catalog extension after the current coverage and identity work, not implemented automation.

- **Collection and views:** maintain a durable Followed Artist Releases collection; New Music Friday is a weekly release-date view, with an explicit timezone and week boundary. Keep provider release date and its precision separate from first detection time. Late discoveries and backfills remain visible rather than falling out of history.
- **Capture evidence:** a future daily read-only scan should record the followed-artist snapshot, account/market, artist and release IDs, ordered track listings, capture/detection times, and per-artist pagination, failures, and coverage. Failed or partial scans cannot establish no new releases. Initial catalog import needs an explicit baseline/backfill policy.
- **Identity and filters:** preserve raw releases and track occurrences before applying reviewed recording groups or presentation deduplication. Single/album overlap, reuploads, deluxe editions, remixes, live versions, compilations, featured credits, and incorrect artist attribution need explicit rules and uncertain candidates. New provider IDs do not automatically mean new recordings; matching recordings must not erase release history.
- **Separate outputs:** release detection, catalog storage, local recipe views, and Spotify publishing are separate stages. A future publisher requires explicit authorization, a preview, retry-safe addition tracking, readback verification, and a visible playlist-capacity policy. Retain the full local history even when a bounded Spotify view rotates; never silently purge existing playlist entries or deduplicate user occurrences.
- **Validation before implementation:** recheck current endpoint capabilities, scopes, rate limits, and market/date behavior. Use synthetic cases for incomplete artist pages, failed scans, repeated detection, delayed availability, imprecise dates, reuploads, version ambiguity, and capacity exhaustion before any account-backed trial.

See [release-discovery research leads](REFERENCE_PROJECTS.md#release-discovery-research-leads). Third-party playlists can be observed as sources with their own provenance and coverage; they cannot prove exhaustive release detection. Cross-repository impact was checked against the separate playlist migrator's context and safety guidance: this plan belongs to the catalog and requires no migrator edit, shared runtime, OAuth change, or migration behavior change.

## Planned interfaces

### Discovery bridge and personal library (planned)

The “Local Spotify Library Brainstorming (origin of codex project)” discussion was reviewed on 2026-09-30. Its central direction is retained: Spotify can remain a discovery/social service while the local SQLite catalog preserves independent evidence, organization, and owned-audio relationships. Build useful catalog and resolver capabilities before deciding whether a custom player/UI is necessary.

- **Discovery/import queue:** a captured like, playlist addition, or followed-artist release may produce a reviewable desired-library entry. Distinguish not yet inventoried, no candidate within completed roots, ambiguous match, reviewed match, desired acquisition, and verified import. Keep source IDs, snapshot/coverage, version preference, candidate evidence, user decision, and resulting file provenance. A queue entry is not proof of file absence everywhere or authorization to download. Dismissing or unliking an entry must not delete owned audio.
- **Personal evidence:** consider ratings, favorites, user tags, discovery recollections, concert/festival associations, and listening/play/skip events as separately sourced and dated entities. Keep service likes distinct from local favorites; play counts must name their event sources and coverage. Unknown skip history is not “never skipped,” and a user-entered mood or discovery date must remain an assertion. Derived smart filters need these fields implemented and populated before claiming results.
- **Additional source adapters:** saved albums and SoundCloud metadata/history are future capture candidates, not current collector coverage. Any existing external SoundCloud download pipeline remains independently managed; this catalog does not run it. Import chosen existing files with raw metadata and provenance, including unmatched releases; automatic tagging, moving, transcoding, artwork/lyrics enrichment, and cleanup require separate scope and review.
- **Choose outputs by requirements:** before deployment or custom UI work, compare Navidrome/Symfonium, Jellyfin, Plexamp, Roon, Feishin, Finamp, Flacbox, and a custom client against required devices, actual playlist capacity, duplicate/order behavior, folder projections, offline use, metadata, accessibility, multi-user access, backup, and cost. These are evaluation candidates from the chat, not current compatibility endorsements. Test a small owned-audio projection and consult current provider documentation before selecting one. NAS/server hosting and automatic multi-device indexing are not implemented or guaranteed.

The catalog does not reproduce Spotify's proprietary recommendations, social backend, universal playback, or streamed audio. Larger local collections still face each selected player's/server's practical constraints; “unlimited” is not a validated capacity promise. The [integration design](INTEGRATION_DESIGN.md) records bounded Spotify outputs and owned-audio transfer acceptance. Cross-repository scope was checked: this vision belongs to the catalog roadmap and requires no companion change to the browser migrator. No download, account write, server installation, or recurring sync was configured. The chat's project-relevant vision is preserved without relying on it remaining available.

- A Smarter Playlists-style local recipe UI: choose a snapshot, connect sources and set operations, preview, then save a reusable recipe. Scheduling and publishing come later.
- Dry-run M3U/server-playlist reports after local audio is actually matched. Symfonium, Navidrome, and Jellyfin can be owned-audio endpoints; they do not turn streaming metadata into audio.
- BPM, key, energy, genre, mood, and DJ export only where evidence or analysis supplies it.
- Provider adapters for Spotify, local/server, and potential Apple Music, YouTube, or SoundCloud references, each with a capability matrix.

## Not current CLI scope

No audio downloading or redistribution; universal queue, offline playback, or Connect replacement; automatic account writes; guaranteed cross-service link conversion; hosted multi-device database; or business/legal/provider-policy conclusions based only on design notes.

The roadmap preserves the broader idea without presenting aspiration as delivered functionality.
