# Roadmap: catalog first, music hub later

## Direction

The longer-term vision is a personal-use-first music hub for power users and playlist creators: fast organization, larger local collections, overlap and duplicate awareness, owned audio, richer metadata, cross-provider references, DJ workflows, discovery, and eventually sharing or AI-assisted filters. It is valuable even if it never becomes a distributed streaming service.

The user clarified on October 27, 2026 that an ultimate goal across these tools
is DJing with a deeply organized, tagged library, probably in rekordbox. Use the
[DJ library workflow](DJ_LIBRARY_WORKFLOW.md) to guide version identity, useful
tagging, saved musical filters, and preservation of preparation work. Rekordbox
is the leading delivery target; keep the underlying catalog portable.

The grounded architecture is a local catalog that observes provider metadata and owned-audio sources. A wrapper can link to provider content where APIs allow, but licensing, playback, social features, provider capabilities, and commercialization require separate current validation.

The personal database is the engine for later exploration: build durable metadata and relationships for tracks/recordings, releases, artists, ordered memberships, owned audio, and personal decisions; enrich them through selected independent sources. Playlist algebra, musical profiles, DJ suggestions, and artist/album placement questions then query saved local evidence with zero provider calls. Collection and enrichment refresh run separately, and results show their evidence dates and coverage. Rich metadata is a planned extension of the working catalog, not merely a temporary Spotify response cache.

## Current priority

Retain SQLite for the local operational catalog. The [storage decision and alternatives](STORAGE_DECISION.md) explain the fit, query-performance work, optional analytics path, and criteria for reconsidering a server database. No cloud service or second database engine is currently required.

Build out the personal SQLite catalog first. Start with saved evidence and
make playlist capacity, coverage, overlap, duplicate occurrences, and local
collection visibility practical. Continue manual New Music Friday curation
with Spotify folder playback across numbered playlist volumes. Each volume
has Spotify's 10,000-song limit. The catalog can preserve the larger logical
collection and its history. [Playlist curation guide](PLAYLIST_CURATION.md).

## Catalog and browser migrator coordination

Follow the [authoritative integration roadmap](CATALOG_MIGRATOR_ROADMAP.md) for
the separate repair track. The catalog owns discovery, history, and evidence.
The browser remains the preferred future interface for reviewed Spotify repairs.
Resume the planned bridge when a concrete repair case demonstrates value in a
manual trial. Folder curation and catalog delivery can proceed independently.

## Next work

1. **Establish a catalog baseline from saved evidence.** Verify a supported
   snapshot import or build an offline export of saved checkpoint evidence if
   the available captures are interrupted. Keep incomplete sources, source
   times, and errors visible. Use the current [offline preview](OPERATING_GUIDE.md#preview-and-folders)
   to inspect completed sources now. Resume a live capture separately when
   additional coverage is needed and any cooldown has elapsed.
2. **Deliver a read-only capacity report.** Show each ordinary playlist's
   captured placements, observed provider total where available, evidence
   date, coverage, and estimated remaining slots where the counts agree.
   Include duplicate, local, and unavailable placements in the count. Label
   unknown headroom and distinguish Liked Songs from ordinary playlists.
   Compare dated, complete captures of the same playlist to show net growth.
3. **Scale the local queries.** Measure capture/import cost, report and
   exact-instance lookup latency, and memory with at least 100,000 observed
   identities, repeated placements, local references, and multiple snapshots.
   Measure larger occurrence sets separately. `lookup`, set operations, and
   comparisons still materialize snapshot rows in Python. Add focused indexed
   SQL and paged browsing where measurements justify them.
4. **Organize category volumes.** Record ordered playlist IDs and the active
   volume for each logical collection. Use the report to preview rollover and
   start with manual Spotify folder management. Pilot the [folder-tree adapter](INTEGRATION_DESIGN.md#folder-structure-adapter)
   separately from playback. Review automatic splitting or publishing only
   after measuring the effort of manual rollover.
5. **Expand library coverage and intelligence.** Extend local file inventory
   and device reconciliation, then develop [artist history](#artist-history-and-enrichment-planned),
   reviewed recording relationships, and [library intelligence](LIBRARY_INTELLIGENCE.md)
   in stages. Retain raw occurrences and separate genuine versions. Use
   permitted, source-dated enrichment for musical and DJ views.

The [versioned migrator handoff](CATALOG_MIGRATOR_ROADMAP.md) is a later repair
project. Near-capacity repairs need a fresh headroom check before additions.

A small authorized local-audio/DJ pilot can progress independently of complete
Spotify coverage or the migration bridge: agree on a useful tag vocabulary,
inspect a chosen rekordbox export, then implement one read-only import and a
reviewable dry-run crate. The [pilot acceptance sequence](DJ_LIBRARY_WORKFLOW.md#small-delivery-sequence-and-acceptance)
requires field mapping, correction preservation, round-trip checks, and a chosen
application/device profile before broader writes or playback claims.

### Delivery status and dependencies

| Area | Current status | Next acceptance evidence |
|---|---|---|
| Catalog capture, history, queries, and backups | Existing Python/SQLite implementation | Validate a saved snapshot import or export of saved checkpoint evidence with explicit coverage |
| Playlist capacity and rollover | Capacity report and volume mapping are planned. Native folder playback is available in Spotify clients | Inspect a saved baseline and test one category with direct sibling playlists on both devices |
| Browser preview recovery | IndexedDB checkpoints, resume/stop, counters, and visible fallback implemented in the separate migrator | When a repair is needed, measure an authorized read-only preview with retained coverage and progress |
| Query performance | Exact-instance index exists; general lookup/set/compare paths still materialize snapshot rows | Reproducible measurements and focused SQL-query regression tests before claiming scale gains |
| Catalog discovery bridge | Deferred behind useful catalog coverage and a manual repair trial | Measured value, then versioned evidence export/import, account validation, and fresh discovery |
| Recording resolver and rich library intelligence | Planned extensions | Reviewed identities and permitted metadata with provenance; no silent provider calls during ordinary queries |

The migrator's existing recovery can be used independently for repairs. See
[work status](WORK_STATUS.md) for dated checks and [integration acceptance](CATALOG_MIGRATOR_ROADMAP.md#ordered-work-and-acceptance)
for the deferred bridge.

### Library intelligence and continuing maintenance (planned)

The October 6, 2026 ideas are retained in the [library intelligence design and feasibility review](LIBRARY_INTELLIGENCE.md). Existing N-way CLI set queries, scan comparisons, and artist/source summaries are foundations, not an implemented self-updating recommendation system. Continuing refresh must discover new playlists, keep failed observations out of removal comparisons, revalidate playlist versions, and handle Liked Songs without assuming a version token. Profiles must expose genre/BPM/key coverage; artist/album suggestions need literal placement and complete release evidence first.

The design includes source-dated MusicBrainz/Last.fm tag research and owned-audio/DJ metadata paths. Spotify currently deprecates artist genres and restricts affected apps' Audio Features/Analysis access. Its policy also constrains content analysis and AI ingestion, so Spotify-backed profiling is conditional on validating permission; local computation alone does not settle that. This is planned catalog work, with no scheduler, service connection, dependency installation, or account write configured by this documentation update.

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

The [October 6, 2026 navigation observation](HISTORICAL_OBSERVATIONS.md#october-6-2026-oldshadow-album-navigation-appears-restored) reports that View album now reaches the old/shadow album without an Android app update. Old-release discovery must cover both reachable and unreadable old albums; restored client navigation does not establish API readability, merged identities, or transferred membership. Capture the opened release identity separately from the stored track identity and keep migration optional.

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

The future release inbox can supply candidates for the curator. The current
weekly New Music Friday workflow uses manual selection and native folder
playback across playlist volumes. [Playlist curation guide](PLAYLIST_CURATION.md).

- **Collection and views:** maintain a durable Followed Artist Releases collection and offer a weekly candidate view for New Music Friday with an explicit timezone and week boundary. Keep provider release date and its precision separate from first detection time. Late discoveries and backfills remain visible rather than falling out of history.
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
