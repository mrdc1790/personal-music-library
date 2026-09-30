# Integration design: folders and smart collections

Both areas are planned extensions to the local catalog. They must preserve provenance and remain useful even when Spotify, local audio, or a future provider cannot support the requested output.

## Folder structure adapter

Spotify's Web API capture preserves playlist contents but not folder nodes, nesting, empty folders, or desktop sibling order. API playlist-list order must not be described as a folder tree.

`folder_tree.py` is an offline-tested, read-only adapter for an account-scoped Spotifast rootlist cache. It can retain raw hierarchy payload, nested and empty folders, stable IDs where supplied, parent relationships, sibling order, and separate hierarchy snapshots. It joins playlist structure to audit data by Spotify playlist ID—not display name. The current limitation is important: no live account tree or direct rootlist fetch has yet been validated.

Keep structure coverage separate from playlist-content coverage. A rootlist playlist with unreadable contents remains visible in its folder with contents marked unknown. Malformed or incomplete rootlist structure must retain raw ordered evidence and a warning rather than being silently repaired into a trustworthy tree. Rootlist support does not expose hidden original IDs, bypass rate limits, remove the 10,000-item limit, or establish local-file playback.

## Smart collections and recipes

The current CLI supports local union, intersection, and difference. A future recipe interface should make those steps visible and reproducible:

1. Select one saved snapshot and show its coverage.
2. Select source playlists or Liked Songs by friendly name and stable ID.
3. Connect simple rules: in either, in both, or in A but not B.
4. Preview result count, entries, and inclusion explanation.
5. Save either the recipe (rules) or a result (entries from a particular run); do not confuse the two.

The expected synthetic examples are `Chill AND Festival → Moonrise` and `Chill NOT Festival → Harbor`. A recipe run must not mutate its sources. It must preserve snapshot ID, recipe version, parameters, coverage, output-order rule, and any shuffle seed so the result can be explained and reproduced.

Later operations—sorting, limits, artist spacing, explicit deduplication, scheduling, refresh against a newer snapshot, and Spotify publishing—need their own visible rules and review boundaries. Mathematical set operations do not define listening order. A large local result may later be projected to bounded service playlists, but splitting or publishing is not implemented.

## Owned audio and DJ endpoints

Local inventory is a first-class source adapter, separate from Spotify playlists, Liked Songs, and rootlist folders. It must include selected files never referenced by Spotify. Model file-on-device, Spotify local metadata reference, provider track instance, and candidate recording as separate entities. A phone inventory must carry its own capture time and coverage; a desktop match or download icon is not proof of phone file presence or playback. Keep unresolved local/cloud matches visible rather than excluding them from a music-hub view.

Recipe deduplication must declare its identity level: exact URI, reviewed recording group, or file identity. Single-versus-album candidates belong to recording-level review even when neither release is a shadow and no relink field exists. Cross-playlist overlap remains intentional unless a separate reviewed recipe says otherwise.

Only after files are inventoried and matched should the project generate a dry-run M3U or music-server playlist report. Verify path mapping, ordering, duplicates, and unresolved entries on a small sample before bulk output. Symfonium, Navidrome, Jellyfin, and DJ software are potential endpoints for owned audio; they do not convert Spotify metadata into audio or establish universal playback.

## Large collections and bounded provider outputs (planned)

A local collection can exceed a provider playlist's capacity. Represent the collection independently, then create separately reviewed output projections; do not claim to bypass Spotify's limit. Each projection should retain collection/recipe version, source snapshots and coverage, identity level, ordering, part boundaries, destination IDs, and a manifest mapping every output occurrence to its source. Preserve duplicate occurrences unless the user explicitly chooses a deduplicating recipe.

Preview capacity and unmatched/unavailable entries before publishing. Splitting must be deterministic under a declared order, with a policy for future additions, changed part boundaries, renamed outputs, and pre-existing destination contents. Never silently drop old entries to make room or overwrite unrelated destination items. Future incremental sync needs idempotent action tracking, fresh reads, verification, and a conflict/recovery policy. Synthetic acceptance should cover boundary sizes, repeated tracks across parts, partial writes, concurrent destination edits, and reruns. No publisher or automatic collection splitting is implemented.

## Symfonium transfer acceptance (planned)

Keep the catalog as historical evidence and Symfonium as a possible playback client for matched owned audio. A transfer is a projection with losses, not a lossless Spotify-account migration.

| Information | Required treatment |
|---|---|
| Track sequence and repeated occurrences | Compare the imported sequence and multiplicity against the export manifest; do not assume preservation |
| Matched audio | Use verified local/server paths or provider media IDs; report unresolved entries separately |
| Nested/empty folders and sibling order | Preserve the source tree locally; flattened names or tags are an explicit output mapping, not an equivalent tree |
| Playlist names | Retain source IDs and collision-safe output names; equal names do not identify equal playlists |
| Likes/favorites | Choose a playlist or favorite projection explicitly; it is not identical Spotify saved membership |
| Dates, attribution, ownership, covers, descriptions | Retain source evidence locally and declare fields the destination cannot preserve |
| Spotify URIs and raw metadata | Keep in the catalog/manifest; they are not owned-audio playback paths |

The [Symfonium import/sync guide](https://docs.symfonium.app/wiki/providers/import-sync-media-providers-playlists/) reviewed on 2026-09-30 documents server sync modes and M3U/PLS import for supported file providers. Start with a small read-only import and verify actual provider/version behavior. Its “Skip duplicates” option skips playlist imports by matching playlist name; it is not a guarantee about repeated tracks inside a playlist. Online-first and offline-first modes can write or replace server playlists, so sync direction and write authorization must be explicit before using them. Catalog set queries remain the source of playlist algebra; a player's metadata filters are not automatically equivalent membership queries. No player/server was installed or connected by this review.

## Export-plan review and remaining limits

### Earlier audio-download proposal: retained concerns, separate scope

The “Spotify Library Download Plan” discussion was reviewed on 2026-09-30 alongside the artist-tracker chat because the supplied Markdown displayed one URL while linking to the other. It is an older proposal, not an implemented catalog feature or authorization to acquire audio. Audio downloading remains outside current CLI scope.

Retain its useful requirements for any separately scoped owned-audio acquisition/import design: distinguish initial bulk work from continuing metadata refresh; preserve source identity, match evidence, chosen version, file provenance, tags, failures, and review decisions; checkpoint batches without treating failures as absent music; and keep ambiguous remixes/live/clean/edit matches unresolved. A new like can prompt a candidate/import queue, but it must not automatically authorize acquisition or deletion of a local file when the like disappears.

Codec, bitrate, source quality, and playback-device compatibility are separate choices. A higher output bitrate does not establish better source fidelity. Capacity estimates should use actual durations and selected encoding settings, include originals/derivatives and backup headroom, and be validated on a small authorized sample. File tagging, normalization, transcoding, and duplicate cleanup are separate explicit operations; retain originals and transformation provenance when such work is authorized.

The chat's spotDL/yt-dlp commands, matching percentages, “only realistic approach” claim, storage totals, Docker/NAS assumptions, and broad legal conclusions were not verified and are not adopted as project requirements. Any future tool/source evaluation needs current capability, acquisition-rights, provider-term, quality, and recovery review for that specific task. Neither repository acquired audio, installed those tools, configured a scheduler, or changed Spotify by preserving this context.

The “Spotify Playlist Export” discussion was reviewed on 2026-09-30. Its core is already implemented or planned here: SQLite snapshot history, occurrence CSVs, per-playlist CSVs, song-to-playlist reverse indexes, artist/source summaries, exact observed-ID set operations, separate folder evidence, reviewed recording identity, and later owned-audio output. Do not create thousands of authoritative per-song/per-artist files; generate consolidated tables and optional filtered views from the catalog.

Current `playlists.csv` does not include joined folder paths; hierarchy/content export joining remains work. Recording-level algebra, audio fingerprints, reliable moved-file recovery, provider publishing, and general Spotify playlist reconstruction remain planned. Restoring a catalog ZIP restores local evidence only; it does not rebuild Spotify, restore audio, or recover original provider attribution/dates. The separate migration engine's restricted rollback is not a general playlist-restoration feature. Example counts and proposed commands in the chat are illustrations, not measured results or implemented commands.

[Exportify](https://github.com/watsonbox/exportify) and [Spotify's account-data archive](https://support.spotify.com/us/article/understanding-your-data/) are optional archival research leads, not required replacements for the scanner. Any future import must validate actual fields, identities, ordering, account, capture time, and completeness; retain missing fields as unknown and compare source data paths before claiming independent confirmation. Soundiiz and Set Operations for Spotify remain third-party transfer/algebra leads requiring current capability and safety review before use; this review did not validate or authorize their account writes.

The chat explicitly did not read its six linked shared discussions. Their redundancy and unique requirements remain unreviewed; reviewing this parent chat does not establish that those other chats can be deleted. The parent chat's project-relevant design is now preserved here. Cross-repository scope was checked: exports, virtual collections, and owned-audio playback belong to the catalog; the browser migrator's selected-ID repair boundary needs no companion edit. No recurring backup or account-changing automation was configured.
