# Library intelligence: changes, playlist relationships, and DJ exploration

Planning and public documentation reviewed on **October 6, 2026**. This records
the user's ideas for the personal library after dependable capture and caching:
compare one or many playlists, describe their musical characteristics, find
related playlists and DJ transitions, and suggest placements for an artist's
remaining album tracks or future releases. BPM is the intended tempo field.
Examples below are proposed questions, not findings about the user's music.

**Implementation alignment — October 27, 2026:** the recent runtime work delivered
durable preview recovery in the separate browser migrator. It did not populate
this catalog, change its schema/query implementation, or deliver enrichment,
continuing refresh, recording matching, DJ profiles, or recommendations. The
database-first architecture below remains the plan. Next validate useful real
capture/import coverage and measured queries; the
[discovery handoff](INTEGRATION_DESIGN.md#catalog-to-migrator-discovery-handoff-planned)
can then reuse exact-instance evidence without waiting for richer musical
metadata. The [roadmap](ROADMAP.md#next-work) tracks this sequence. This alignment
does not refresh the external-provider research dated above.

## The personal database is the query engine

The user's clarification is central: build a durable, richly enriched personal
music database, then answer library questions from that database. Spotify and
other services supply observations to it. Their APIs are used by collection and
enrichment jobs; an ordinary playlist comparison, musical profile, DJ suggestion,
or artist/album placement query runs entirely against committed local evidence.
It should work offline and make **zero Spotify or enrichment-provider calls**.

The intended flow is:

1. Capture selected provider memberships/releases and owned-audio evidence.
2. Match identities, supplement metadata through chosen external sources or
   local analysis, and store the evidence with its source and date.
3. Maintain indexes and derived views in the personal SQLite database.
4. Answer questions from those saved entities, relationships, and views.
5. Independently refresh changed memberships or missing/expired enrichment, then
   rebuild affected local results. A later query can use the updated evidence.

This is a long-lived catalog, beyond a temporary API-response cache. Model rich
metadata at the entity it describes and join it locally:

| Entity or relationship | Intended saved evidence |
|---|---|
| Track instance and reviewed recording | Provider/external IDs, titles, duration, version identity, credits, recording relationships, and matched BPM/key/genre/mood observations |
| Album/release | Stable release IDs, edition, release date/precision, ordered track list, credits, source tags, and release-family relationships |
| Artist | Stable IDs, aliases, reviewed external mappings, credits, genre evidence, and captured follow/release history |
| Playlist and likes membership | Source IDs, versions, ordered occurrences, repeated placements, save/add observations, coverage, and change history |
| Owned audio and DJ evidence | Inventoried file identities, recording matches, analysis/tool versions, beatgrids/cues where available, and reviewed corrections |
| Personal choices and derived views | User tags, ratings, preferred versions, placement rules, recipes, musical profiles, suggestions, and their input versions |

These are planned extensions, not fields already populated by the current schema.
Different sources can contribute different fields to the same reviewed entity;
their raw values, entity level, conflicting evidence, and user decisions remain
available. An album tag is not silently promoted to a track fact. Independent
external metadata and owned-audio analysis retain their own provenance rather
than being labeled Spotify metadata just because a Spotify instance is linked.

For example, "Which of my playlists could transition from these Future Bass
playlists?" would join saved memberships to saved track features and compare
local results. "Where do I usually place this artist, and which remaining album
tracks fit?" would join saved artist credits, release tracks, placements, and
rules. Once that evidence is populated, neither question needs a new provider
request. Result freshness comes from the last committed refresh, with its time
and coverage shown.

Missing or stale fields are visible query results, not a reason to silently call
a service during the question. A query may record a local enrichment need; only
a separately enabled refresh job or explicit refresh performs the network work.
Source storage/use permissions still apply to retained data, but they are a
separate constraint from whether the query technically needs an API call.

## Feasibility and current status

These features are technically achievable in stages with SQLite, source adapters,
and explainable rules. Neither an AI model nor another database engine is needed
for the first useful version. Technical feasibility does not establish permission
to analyze a provider's data; see the provider constraints below.

| Request | Available foundation | Remaining work or dependency |
|---|---|---|
| Union, intersection, and differences across playlists and likes | `library.py:set_query` accepts two or more distinct, exported sources in one saved snapshot | One-source exploration, richer membership/occurrence views, symmetric difference, at-least-N rules, saved recipes, and a convenient UI |
| Notice additions, removals, and edits | Durable scan checkpoints, immutable catalog imports, and `library.py:compare` already retain occurrence-count and sequence differences | Continuing refresh across runs, fresh discovery, event history, scheduling, and a data-quality dashboard |
| Find where an artist or album appears | Reverse lookup, artist/source CSV summaries, and raw album/artist IDs are retained | Indexed album/artist queries, complete release track lists, reviewed identity mappings, and placement recommendations |
| Describe a Future Bass playlist's genre, BPM, and key | Captured memberships can be joined to future enrichment | Track metadata, source permissions, missing-data reporting, and reproducible playlist profiles |
| Find similar playlists and candidate DJ transitions | Exact membership comparisons provide a starting point | Permitted musical metadata, similarity rules, track-level transition candidates, and manual DJ review |
| Suggest destinations for future releases | Artist placements and the planned followed-artist release inbox provide inputs | Release capture, user placement rules, explainable recommendations, feedback, and stale-evidence handling |

Current set results are distinct observed identities, sorted by identity key;
they are not an ordered listening playlist. Stored occurrences retain duplicates
and positions. The current HTML preview compares two playlists; the CLI can select
more. Recording-level equivalence, autonomous maintenance, enrichment, and these
recommendation features are not implemented or validated on the user's library.

## Continuing refresh and self-audit

Build on the existing scanner rather than introduce another hidden collector.
Resuming a run currently checks playlist versions and revalidates saved Liked
Songs prefixes. It is not a continuing sync system: completed discovery is kept
within that run, and resuming it does not discover newly added playlists.

- **Fresh discovery:** each refresh cycle needs a newly validated account-scoped
  playlist manifest, including new and inaccessible sources. Keep playlist
  visibility separate from ownership and edit permission. A failed manifest
  cannot establish that a playlist was deleted or unfollowed.
- **Playlist reuse:** retain complete items with their provider snapshot token;
  validate the current token before reuse. Recapture changed sources with version
  checks before and after pagination. This reduces item reads, but validation
  still contacts Spotify. Retry a changing source within a bounded policy and
  continue unrelated sources; persist unresolved coverage if it keeps changing.
- **Liked Songs:** there is no equivalent playlist snapshot token in the current
  design. Equal counts, a matching first page, or a cached prefix alone cannot
  prove unchanged membership. Plan validated full traversals, drift checks, and
  explicit capture intervals; do not promise an atomic account snapshot or a
  shortcut that misses older removals. Keep a failed observation out of the
  last complete comparison baseline.
- **Observed changes:** compare complete, comparable sources for the same account
  and capability context. Preserve added/removed occurrence counts, sequence
  changes, and name changes. The initial capture is a baseline, not a report that
  every song was just added. Keep provider `added_at`, first detection time, and
  the interval between captures separate. Events between captures can be missed.
- **Health and recovery:** show last attempt, last complete capture, validation
  time, endpoint totals versus fetched/imported rows, changed versions, failures,
  stale sources, missing identities, and enrichment coverage. Retain failed runs
  and older good evidence without presenting the latter as current. Make import
  and event creation retry-safe and transactional; do not emit the same event
  again after a resume. Health checks flag problems rather than silently repair
  identities, delete evidence, or change Spotify.
- **Independent queues:** distinguish provider capture, catalog import,
  enrichment, derived-report rebuilding, and optional notifications. Local
  queries, profiles, suggestions, and reports need no provider requests. Only
  separately enabled capture/enrichment refresh jobs contact providers. Cache
  lifetimes must be explicit and measured, with provider-specific pacing,
  `Retry-After`, and shared Spotify quota considered. No polling interval or
  instant notification guarantee is selected here.

Scheduled catalog maintenance remains planned. A scheduler needs its own setup
and credentials lifecycle; recording this roadmap does not configure a recurring
job or authorize account writes. The existing [operating guide](OPERATING_GUIDE.md)
remains the source for implemented scan/import commands.

## One or many playlists: understandable comparisons

Offer a source selector with stable IDs, names, snapshot and coverage, followed by
one-source membership, union, intersection, A minus all selected B sources,
symmetric difference, or tracks in at least N of M sources. Liked Songs is an
explicit source, not an assumed filter. Resolve duplicate playlist names through
IDs; group selectors and folder paths require separately captured hierarchy.

At-least-N counts distinct selected sources, not repeated placements. For more
than two sources, define symmetric difference as an odd membership count and
offer "exactly one source" as a separate rule; they are different questions.

For every result, show which sources contain the track, counts and positions of
its occurrences, and the reason for inclusion. Keep exact observed identity as
the default; reviewed recording-group queries are a later explicit mode.
Incomplete sources block definitive absence/difference answers. An exploratory
subset may be shown with unknown coverage, but is not a complete set result.

Save a query recipe separately from its result. Retain source snapshot IDs,
identity level, rules, version, output order, and any shuffle seed. Updating a
recipe against new evidence creates a new result. Mathematical set membership
does not authorize deduplication or define listening order; an occurrence-preserving
projection needs an explicit order/multiplicity policy.

Proposed questions include "What is shared across these five playlists?", "What
is in either playlist but not my likes?", and "Which songs appear in at least
three of these playlists?" A future conversational parser can turn the user's
request into a visible query specification; it must resolve ambiguous source
names and unsupported fields before claiming an answer. Keep Spotify payloads
out of AI models under the policy described below.

## Musical profiles, similarity, and DJ transitions

On appropriately permitted evidence, a playlist profile can report genre/tag
distribution, BPM median and ranges, key/mode distribution, duration, and optional
user-defined mood or energy. Show usable, missing, conflicted, and unmatched
metadata counts per field. Name the source, capture/enrichment dates, identity
mode, and weighting: distinct tracks and repeated placements answer different
questions. Small or biased enriched subsets do not describe the whole playlist.

Genre evidence must distinguish artist, release, recording, and individual track
tags. An artist tag or the playlist name "Future Bass" does not label every track.
Retain raw subgenres and explicit user overrides. BPM needs half/double-time
ambiguity and variable-tempo handling; key needs tonic, mode, original notation,
and a versioned display conversion. Do not average numeric key codes. Energy
scores from different tools are not automatically comparable or Spotify-equivalent.

Start similarity with visible membership overlap, such as Jaccard
`shared / union`, and directional containment `shared / source size`. Add musical
profile comparisons only for adequately covered fields. Expose component scores,
unknown fields, user-selected weights, and the evidence behind each suggestion.
Empty or incompletely captured sources need explicit handling. A single combined
score is a ranking heuristic, not a calibrated probability or proof of genre.

For DJ use, separate "these playlists resemble each other" from "these two tracks
could transition well". Return directional source-track to destination-track
candidates with tempo difference, optional half/double-time interpretation,
key/mode compatibility rule, and energy direction where evidenced. Show assumed
pitch adjustment and key-lock behavior. Later, owned-audio beatgrids, phrase/cue
information, and listening notes can support better candidates. Playlist-wide
averages cannot guarantee a mix; BPM/key suggestions still need listening and
manual review. Spotify metadata or membership is not playable DJ audio.

## Artist, album, and future-release placement

Answer literal placements first: which selected playlists contain this artist,
album instance, or track, with primary/all-credit modes, distinct-track counts,
occurrence counts, dates, and named coverage. Album identity comes from a stable
ID, not its display title. "Tracks not yet placed" requires a complete captured
album track list; it cannot be inferred from tracks already in the library.

Then suggest destinations using observed artist/album placements, permitted
track profiles, and explicit user rules. For example, "Suggest the remaining
tracks from this album for playlists already containing its tracks" is a
reviewable shortlist, not a rule to add every song. Preserve reasons and counter
evidence: featured artists, mixed-genre albums, remixes, live/clean versions,
existing placements, stale captures, and unmatched releases. Reviewed
recording-group membership is optional and must not merge versions automatically.

Join the [release inbox](ROADMAP.md#followed-artist-release-inbox-planned) to these
placement suggestions. Keep release date/precision, first detection, and release
versus recording identity separate. User acceptance, dismissal, and explicit
artist-to-playlist rules become dated local decisions that survive refreshes;
these can improve deterministic rules without training a model on Spotify data.
Any future publisher remains a separate authorized, previewed, freshly validated
workflow with action tracking and readback verification.

## Metadata sources and provider constraints

The following is a public documentation review, not an account-backed capability
test, service connection, or vendor recommendation. Recheck access, terms,
attribution, storage permissions, quotas, cost, and actual coverage before adding
an adapter. An external API is optional; manual labels and existing DJ metadata
can provide an initial useful dataset.

| Source | Useful evidence | Limits and proposed role |
|---|---|---|
| Spotify | Track/artist/release identity and captured placements; historical genres/features if lawfully available | Artist `genres` is currently marked deprecated. Audio Features, Audio Analysis, Recommendations, and Related Artists access was restricted for affected/new apps in 2024. Do not require these fields or infer access from a documentation example. ([Artist reference](https://developer.spotify.com/documentation/web-api/reference/get-an-artist), [access changes](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api)) |
| MusicBrainz | External artist/recording/release IDs, ISRC lookup, and community genres/tags via `inc=genres` or `inc=tags` | Match entities before importing tags; missing tags and multiple ISRC candidates remain unresolved. Public reads require correct application identification and at most one call per second. This is an identity/tag source, not a promised BPM/key service. ([API](https://musicbrainz.org/doc/MusicBrainz_API), [rate limits](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting)) |
| Last.fm | Track and artist top tags, potentially useful for genre/mood labels | The documented top-tag methods use an API key without requiring user authentication. Retain tag counts and entity level; name/MBID matching and autocorrection need review. Tags are community labels, not measured acoustic features. ([Track tags](https://www.last.fm/api/show/track.getTopTags), [artist tags](https://www.last.fm/api/show/artist.getTopTags)) |
| Owned audio, file tags, user labels, and DJ analysis/imports | BPM, key, beatgrids, user genre/mood, and later other measured features | Analyze explicitly selected owned/authorized audio or import a chosen export with provenance. Mixxx documents BPM and key analysis and manual correction; a compatible catalog import adapter is still needed. Different mixes/edits and incomplete analysis can disagree. No analyzer installation or Python dependency is approved by this planning task. ([Beat detection](https://manual.mixxx.org/2.5/en/chapters/preferences/beat_detection), [key detection](https://manual.mixxx.org/2.5/en/chapters/preferences/key_detection)) |

Spotify's current [Developer Policy](https://developer.spotify.com/policy), section
III.13, broadly prohibits analyzing Spotify Content or the service; III.14 also
prohibits training or otherwise ingesting Spotify Content into ML/AI models.
Consequently Spotify-derived musical profiling/recommendation has an unresolved
provider-permission constraint even if computed locally without AI. Do not assume
offline caching or adding external tags removes it. Implement analysis first on
owned audio and other sources whose permissions support the use; validate the
specific Spotify-backed use before enabling it. A conversational request parser
must not send Spotify records to a model as a workaround.

Current Spotify capability also affects collection scope: the [February 2026
changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026)
restricts other playlists' returned contents and changes endpoints/fields. Keep
inaccessible third-party sources unknown rather than empty. The [quota
documentation](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
describes Development Mode quota shared across one developer's apps, distinct
from rolling rate limits. The catalog and migrator can compete for that quota.

## Evidence model and implementation order

Keep raw imported snapshots intact. Extend SQLite through backward-compatible,
tested schema upgrades as features land, rather than modify schema in this docs
change. Proposed evidence layers are:

1. Captures and per-source coverage/validation history, plus derived observed
   change events referencing their before/after captures.
2. Reviewed external entity mappings and enrichment observations: entity level,
   provider/external ID, raw value, units/notation, request identity, timestamps,
   match evidence, tool/version, availability/error, and refresh policy.
3. Separate durable user decisions: mappings, genre include/exclude choices,
   corrected BPM/key, placement rules, and recommendation feedback.
4. Versioned recipes, profiles, and recommendations that reference input
   snapshots, enrichment versions, overrides, rules, and coverage. Rebuild only
   affected derived views when inputs change; do not rewrite historical results.

Persist enrichment only within each source's allowed storage rules. Share a
matched entity's cached metadata across queries without repeating network reads.
Keep a successful empty response distinct from unmatched identity, failed
request, and unavailable field. An expired cached value may remain visible with
its age and status, but cannot become fresh evidence or silently erase an
override. Use existing `storage_paths.py` locations, outside OneDrive Documents,
and keep personal data and credentials out of Git.

Delivery order after useful real capture/import validation:

1. Continuing read-only refresh, reliable per-source comparisons, and health
   reporting; retain all existing identity/coverage gates.
2. Source selection, N-way membership views, explicit album/artist queries, and
   saved query recipes. These need no acoustic metadata.
3. Reviewed entity matching and one small permitted enrichment/import pilot,
   including manual genre/BPM/key evidence and conflict reporting.
4. Field-covered playlist profiles and explainable similarity/transition
   candidates on permitted sources.
5. Album-completion and future-release destination suggestions, user feedback,
   and only later a conversational interface or separately authorized publishing.

Acceptance tests should use temporary databases and synthetic examples: three or
more sources with repeats and unknown rows; equal-count membership replacements;
new playlists after an earlier completed discovery; mid-scan edits and failed
likes; retry-safe change events; duplicate artist/album names; incomplete release
lists; ambiguous external matches; stale/empty/failed enrichment; surviving user
overrides; 70/140 BPM ambiguity; key notation conflicts; missing profile fields;
mixed albums/featured credits; and existing destination occurrences. Verify
local queries succeed with providers offline and an adapter that rejects any
network request, including when enrichment is missing or stale. Verify
provider-derived data stays out of model inputs. Benchmark real query and refresh
costs before selecting cadence or claiming speed or recommendation quality.

Cross-repository impact was checked against the sibling browser migrator's
current source, preview-cache behavior, Liked Songs handling, and safety docs.
These planned read-only catalog views require no migrator edit. Keep the projects
independently runnable with separate storage and OAuth; any later plan handoff
must use an explicitly versioned interface with fresh migration validation.
