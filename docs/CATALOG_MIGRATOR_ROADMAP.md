# Catalog and browser migrator integration roadmap

Updated: 2026-10-19. This is the authoritative cross-repository integration sequence.
It is a design, not an implemented bridge or authorization to change Spotify.

## Decision and ownership

Align documentation first, validate the manual workflow next, and build a small
file-based bridge only when the trial demonstrates useful savings.

- **Personal Music Library:** discovery, capture provenance, coverage, historical
  snapshots, reviewed identity evidence, and long-term outcome history.
- **[Spotify Playlist Migrator](https://github.com/mrdc1790/spotify-shadow-release-migrator):**
  preferred future interface for reviewed execution against current Spotify state.
- **Current Python migration engine:** remains available under its existing
  restrictions, approval gates, offline-test status, and journal/rollback rules.
  The browser is not its frontend. Do not remove or relax those restrictions.
  Decide whether to retire its execution path only after the browser workflow
  proves the required capability and recovery coverage.

Keep each repository independently runnable. No shared credentials, runtime
storage, cross-repository imports, or combined application are needed for the
first bridge. There is currently no proposal/result exchange between them.

## Ordered work and acceptance

1. **Align documentation — completed by this documentation update.**
   Both READMEs link here and distinguish current behavior from intended
   ownership. The catalog's existing migration commands remain documented.
2. **Validate a manual end-to-end workflow — next, not yet completed.**
   Obtain useful resumable capture coverage and import a supported snapshot into
   the historical catalog; operational scan and historical catalog databases are
   different formats. Respect cooldowns and retain partial coverage as unknown.
   Identify a candidate from saved evidence, manually enter source/destination
   into the browser, review the preview, and retain the outcome.
   Start with synthetic/offline checks. Any live mutation requires explicit
   authorization, initially on a disposable playlist. Record manual friction,
   coverage, request counts, pages, retries, cooldown time, lookup latency,
   imported rows, and memory. Do not promise full-library speed from a small demo.
3. **Specify a versioned proposal contract — planned.**
   Document a synthetic file and validation rules before implementation:
   schema version, proposal ID, account reference, capture/snapshot ID and time,
   source versions and coverage, proposed track mappings, evidence/reason and
   review status, every observed source occurrence/position, pre-existing
   destination occurrences, and requested/returned/original identity evidence
   where available. Retain unknown identity explicitly. Exclude credentials.
   Define rejection or review handling for unsupported versions, account
   mismatch, malformed/partial data, stale evidence, and ambiguous mappings.
   A saved review decision is provenance, not transferable execution consent.
4. **Implement explicit read-only proposal export/import — planned.**
   Catalog exports; browser imports into a review screen labeled with capture
   age and coverage. Import performs no Spotify writes. Validate the contract
   with synthetic duplicate occurrences, existing destinations, unavailable
   identities, partial coverage, stale data, and account/version mismatch.
   Historical locations are hints, not a complete current execution target list.
   Initially use the browser's existing fresh discovery and confirmation gates;
   require a newly reviewed preview and explicit confirmation.
5. **Return execution evidence — planned.**
   Browser exports actual outcomes; catalog imports them as append-only history.
   Preserve proposal/mapping IDs, attempted actions, verification outcomes,
   affected collections, timestamps, and available pre/post version evidence.
   Distinguish proposed, attempted, verified, failed, and unknown outcomes,
   including partial writes. A browser session checkpoint is not a durable
   mutation journal. Test a synthetic round trip, interrupted runs, duplicate
   result imports, and contradictory or incomplete outcomes. Do not present
   history import as rollback or proof of device synchronization.
6. **Consider incremental preview and engine consolidation — later.**
   Only after measuring the basic workflow, design coverage-aware reuse:
   refresh the editable-playlist manifest, check fresh versions for previously
   covered playlists, and read changed/new/unread sources. Unchanged complete
   negatives matter as well as positive matches. Recheck selected Liked Songs
   separately; historical absence cannot establish current absence.
   Retain fresh execution preflight and replacement verification.
   Use the existing exact-identity index for narrow SQL lookups before making
   scale promises. Compare the two executors' capabilities and recovery
   guarantees before deciding whether to deprecate Python execution.
   A local API or shared runtime is a separate future decision.

## Invariants

- Preserve duplicate source occurrences plus pre-existing destination occurrences.
  Migration, recording grouping, preferred-release selection, and deduplication
  are separate decisions.
- Unreadable, partial, stale, or conflicting evidence is not an empty collection,
  a removal signal, or permission to proceed.
- Imported captures cannot bypass current coverage, identity, confirmation,
  add-before-remove, or verification gates. Each engine retains its own rules.
- Metadata similarity and album positions do not prove identical recordings.
  Keep remixes, live versions, clean/explicit editions, edits, and remasters
  distinct unless deliberately reviewed as substitutions.
- Spotify has no cross-playlist transaction. Record partial outcomes honestly;
  neither a handoff nor an HTTP success guarantees rollback or final correctness.
- Full endpoint traversal is endpoint-scoped evidence, not a filesystem inventory,
  phone-download verification, or universal client reconciliation.
- Development apps owned by one developer share quota; separate Client IDs
  are not an independent quota workaround. No guaranteed scan-time improvement
  or concurrency increase is assumed.

## Related plans

The [catalog roadmap](ROADMAP.md) owns the broader catalog, resolver, local-file,
and music-hub priorities. This integration track does not move those features
ahead of useful coverage and browsing.

The browser's [October 2 performance/design note](https://github.com/mrdc1790/spotify-shadow-release-migrator/blob/main/UPDATED_PLAN.md)
retains its benchmark corrections and technical research. Its implementation
sequence is superseded by this roadmap; historical links are not live validation.
The [Python migration guide](MIGRATION.md) remains authoritative for that engine's
current commands and restrictions.
