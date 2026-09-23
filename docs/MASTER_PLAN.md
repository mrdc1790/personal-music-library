# Master project brief

**September 22 implementation update:** [Durable resumable scanning](RESUMABLE_SCANS.md) now checkpoints pages, validates source versions, and enforces saved cooldowns. Liked Songs prefix validation is intentionally more expensive; see the consolidated status table for current boundaries.

Updated September 17, 2026. This document consolidates the shared conversations; it is a requirements record, not a claim that every idea is implemented.

## Purpose

Build a durable, searchable personal music catalog. Start with useful Spotify metadata exports and local queries. Use that foundation later for shadow-release repair, local-file auditing, artist history, richer organization, and selected playback/export integrations.

The umbrella product is **Personal Music Library**. Its GitHub repository was renamed to [personal-music-library](https://github.com/mrdc1790/personal-music-library) on September 17, 2026. The local folder remains `spotify-shadow-track-migration`, so existing paths and launchers still work. No account or chat was renamed.

## Why this matters to you

Your conversations describe tens of thousands of liked songs, many large playlists, nested organization, thousands of local tracks in **All Leaks**, and an interest in DJ workflows. Those are user-reported scale estimates, not measurements from a scan performed here.

The recurring frustration is losing reliable knowledge of your collection: which release you saved, where it appears, whether its audio still exists, and what changes over time. The first release should make those questions easier before adding another full player.

## Conversation reading ledger

All seven pages below were read through the browser on September 16, 2026. The five nested links were read after explicit user approval. User statements are requirements/context; previous assistant proposals and numeric examples are not validated account facts.

| Conversation | Contribution | Decision |
|---|---|---|
| Spotify local song fingerprinting (private source omitted) | All Leaks, surviving playlist references, missing files, device-specific availability, metadata versus fingerprints | Preserve local references now; implement a separate inventory/matching workflow later |
| Spotify Playlist Export (private source omitted) | CSVs, reverse membership, set operations, local database, folders, Symfonium, overall consolidation | This is the starting user workflow |
| Spotify Shadow Track Migration (private source omitted) | Pretty Lights rereleases, K.A.A.N. 2 Busy, preserve every placement and like | Keep reviewed repair as a separate, guarded module |
| Spotify Library Tracker Design (private source omitted) | Follow/unfollow observations, artist statistics, genre provenance, manual overrides, workbook ideas | Keep it: it adds substantial requirements and is not a duplicate of export work |
| Designing Music Hub App (private source omitted) | Personal-use-first hub, optional commercial future, music inbox, provider identities, playlists, social, AI, DJ, playback | Umbrella vision and long-term backlog; not the scope of the current CLI |
| Spotify 10k Playlist Limit (private source omitted) | Very large collections, smaller service projections, frustration with limits and support | Store larger collections locally later; do not promise a Spotify limit bypass or seamless playback |
| Spotify Shadow Track Migration — second share (private source omitted) | Same main shadow-release question and answer, different suggested follow-ups | Substantially overlapping content; retain source links, do not delete originals |

The original shared answer (private source omitted) was read earlier and motivated the initial migration tool. No further unrelated links were followed and no chats were reorganized.

## Decisions for this implementation

The Spotify alt app idea Google Doc (private source omitted) was read on September 17, 2026. It reinforces the combined metadata catalog, local audio, playlist overlap, DJ enrichment, discovery, and multi-provider vision. Its embedded prior assistant answer is a proposal, not validated implementation or proof of feasibility. In particular, a local database does not supply Spotify audio, remove Spotify's playlist limit, reproduce Spotify Connect, or guarantee unlimited performance. The owned-audio player route depends on actually having the files and matching them correctly.

Latest user priority: the 10k Spotify playlist limit is the main remaining pain point. After a successful real import, prioritize playlist size/overlap/duplicate visibility and a design for one large local collection with multiple bounded Spotify outputs. The existing milestone numbers group work; they do not require finishing artist enrichment before addressing this priority. See [current capabilities and practical boundaries](CURRENT_CAPABILITIES.md).

The additional Designing Music Hub App assessment (private source omitted) was read on September 18, 2026. It supports separating library management from playback, recording identity from provider releases, and provider capabilities from the core catalog. Its proposed first-session experience (automatic duplicate resolution, folders, release discovery, and AI filters) is aspirational, not the current implementation. Its business pricing, legal claims, and provider capability table are not adopted as validated facts. Keep SQLite for the present personal catalog; the assessment's PostgreSQL suggestion does not itself justify migrating. Historical discovery reasons and listening events can only be shown when actually captured. The immediate product priority remains a successful scan followed by clear playlist size, overlap, and duplicate visibility.

Additional design reference: the user supplied [Smarter Playlists](https://smarterplaylists.playlistmachinery.com/#editor) on September 17, 2026 and likes its workflow. Its public landing page describes connected components for mixing, filtering, sorting, and scheduling playlists. Only the public page was inspected; its signed-in editor and live Spotify behavior were not tested. [The smart-playlist design](SMART_PLAYLISTS.md) translates this inspiration into a proposed local workflow with explicit implementation boundaries.

1. SQLite is the local working catalog; immutable raw scan JSON remains provenance.
2. Each scan remains distinguishable. Importing a new scan never replaces prior snapshots.
3. An occurrence is a row with a position. Duplicates and source order are preserved.
4. Recording identity and provider identity are different. The current release queries observed identities only; canonical recording matching is not yet built.
5. Unknown data stays unknown. An unread playlist is not empty; a missing original ID is not inferred.
6. The catalog module performs no network requests or Spotify mutations.
7. Cloud backup starts with portable, versioned archives. No hosted service or multi-device writable database is required now.
8. Audio files need a separate inventory and backup. A metadata catalog is not an audio archive.
9. Plain-English status and a runnable example come before architectural detail.

## Prioritized milestones

### 1. Useful local catalog — implemented, live import still needed

Deliverables: snapshot import/history; song-to-playlist lookup; union/intersection/difference; CSVs; artist placement counts; duplicate reports; occurrence/order comparison; checksummed backup/restore; offline example.

Acceptance: a real scan imports, an identifiable song shows its actual observed memberships, a sample overlap is correct, and an archive restores. Only the synthetic version of this acceptance check has been completed.

### 2. All Leaks inventory — planned

Inventory explicitly chosen music folders, preserving scan root, file path, size, modification time, metadata, duration, and optional file hash. Keep each scan's coverage and errors. Compare playlist local references with this inventory.

Suggested result categories: exact metadata candidate, likely candidate, ambiguous, unmatched within scanned roots, and scan incomplete. Avoid labels such as “definitely playable” based on metadata alone.

A SHA-256 file hash means byte identity; an audio fingerprint is a different signal. Neither reconstructs Spotify's undocumented internal client matching. Do not upload audio or rewrite tags by default. Phone playback requires separate device observations.

### 3. Artist history and metadata — planned, not redundant

Add complete followed-artist snapshots and observed follow/unfollow/refollow transitions. Keep API rank without pretending it is chronological. Define first-seen and detection intervals rather than inventing original follow dates.

Preserve primary-credit versus all-credit counts, distinct songs versus placements, owned versus accessible playlist counts, and unmatched local artists.

Genre data should retain source, fetched date, artist-match confidence, raw value, normalized value, and manual include/exclude decisions. Manual choices are overrides. The earlier proposed numeric weights are experimental design suggestions, not validated confidence probabilities. MusicBrainz/Last.fm enrichment and an XLSX dashboard are not implemented.

### 4. Recording identity and shadow repair — partial implementation

Maintain explicit reviewed relationships among releases/recordings/providers. Consider ISRC, artist IDs, duration, explicit status, title/version and source evidence. Never merge a live recording, remix, clean edit or remaster merely because the title resembles another.

Existing migration commands are tested offline, but the example IDs and actual account behavior still need validation. Current Development Mode limitations block automatic execution. Large/near-full playlist capacity, unavailable-original recovery, and concurrent edits need account-backed investigation before broad repairs.

### 5. Collections and folder organization — planned

September 23: [Spotifast/librespot rootlist adapter investigation](SPOTIFAST_ADAPTER.md) identifies a documented read-only route for folder structure and ordering outside the Web API. Keep the existing catalog and add structure as a separately sourced snapshot; validate a small real folder-tree export before claiming support. No adapter is implemented yet.

Preserve manually captured nested folder hierarchy, sibling order and source provenance. Later create local static or rule-based collections that can exceed a service's limit. Project these into multiple service playlists only with a reviewed synchronization plan.

Folder names are not a reliable unique identity; use stable local IDs and parent IDs. This version has no folder import or editing command, and CSV exports do not claim to contain a folder tree.

For rule-based collections, prioritize the [Smarter Playlists-inspired recipe interface](SMART_PLAYLISTS.md): select a snapshot, connect sources and set operations, inspect the result, and save a reusable recipe. Start with local previews; scheduling and publishing to Spotify are later, separate capabilities.

### 6. Symfonium and owned audio — planned

Match catalog entries to actual accessible audio paths/provider IDs. Generate a dry-run M3U or server playlist report, listing unresolved entries explicitly. Verify ordering, duplicate handling and path mapping on a small playlist before bulk import.

[Symfonium's documentation](https://docs.symfonium.app/wiki/providers/import-sync-media-providers-playlists/) describes provider/file playlist import and synchronization. It does not turn Spotify metadata into audio. Retain hierarchy and provenance in the catalog even when an output format cannot express them.

### 7. Broader music hub — vision, not delivered

Keep these requirements in the backlog rather than silently dropping them:

| Area | Requested ideas / future work |
|---|---|
| Library UI | Fast desktop organization, Saved In lookup/sorting, nested folders, ratings/tags |
| Provider adapters | Spotify, Apple Music, YouTube/SoundCloud, local/server sources; per-provider capability matrix |
| Sharing/inbox | Resolve friends' links, temporary/imported collections, cross-service destinations |
| Discovery | New Music Friday, followed-artist releases, forgotten library, relationship exploration |
| Automation | Rules, reviewed background sync, scheduled snapshots and change reports |
| Search/AI | Natural-language filters, playlist refinement, explainable suggestions |
| Audio/DJ | BPM/key/energy, mood/genre evidence, cues/beatgrids, Rekordbox/Serato/export workflows |
| Playback | Queue, offline, supported devices; no promise of universal Connect or mixed-service streaming |
| Social | Friends, collaboration, activity and sharing where provider access allows |
| Product/business | Personal usefulness first; competition, costs, provider terms and distribution reviewed separately |

The earlier hub conversation's pricing, legal interpretations and feasibility estimates have not been adopted as current facts. Any commercialization or streaming integration needs its own current provider/API/policy review. This project does not establish permission to stream or redistribute music.

## Corrections and boundaries worth preserving

- A first scan cannot recover a history that was never captured.
- API-returned metadata cannot prove hidden original IDs or device playback state.
- Exact-ID set operations and recording-level set operations answer different questions.
- Metadata resemblance produces candidate matches, not certainty that a local file is the right recording.
- A local database can hold larger collections; it cannot change a remote service's limits.
- Rollback preserves some structure but cannot promise original Spotify timestamps/attribution.
- Synchronization can replicate deletion; retain independent versioned backups and test restoration.

## How future work should be explained

Start with the question the feature answers. Show one example with an expected result. Label it **working**, **implemented but untested live**, **blocked**, or **planned**. Define new terms when introduced. Ask for only the next necessary input. Do not hand the user the whole backlog as today's to-do list.

The next practical step is simply trying the offline demo, then importing one real read-only scan when account setup is available.
