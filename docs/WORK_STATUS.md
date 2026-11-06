# Work status

## November 6, 2026 — duplicate counts in snapshot comparisons

Offline snapshot comparisons show the remaining count for each observed track
key that lost placements. The catalog reports these counts for sources with
complete coverage and identified rows in both captures. The reference review
records the Spotify Dedup behavior observed in the hosted build and how it
differs from the public source. [Operating guide](OPERATING_GUIDE.md#catalog-queries-and-exports) · [Spotify Dedup review](REFERENCE_PROJECTS.md#spotify-dedup)

Validation covered 77 offline tests, including retained playlist copies,
removed Liked Songs membership, and unknown coverage. A synthetic CLI run
also verified the count reported by `library.py compare`.

## November 5, 2026 — playlist curation and catalog priorities

An initial owner-reported check found native folder shuffle working on mobile
and desktop. The [curation guide](PLAYLIST_CURATION.md) records the numbered
volume workflow and a pilot for nesting, local tracks, and larger collections.
Playback across deep trees and very large folders still needs device testing.

The personal SQLite catalog is the primary development track. The first milestone
is a capacity report grounded in saved evidence. The browser migrator stays
available for specific repairs, with the file bridge and automatic publishing
lower in the delivery order. This is a documentation update in both repositories.

Validation passed 77 catalog tests, 65 migrator tests, and a synthetic SQLite
import and reopen at [190,000 placements](PLAYLIST_CURATION.md#how-the-limits-apply).

## Continue here

1. Use the [offline preview](OPERATING_GUIDE.md#preview-and-folders) to select
   completed sources from a saved run and check coverage. Verify a supported
   export/import or add an offline export path for interrupted captures.
2. Deliver the [capacity baseline](ROADMAP.md#next-work) from the historical
   catalog, then measure query cost and expand coverage.
3. Try one category with two direct sibling volumes in Spotify while the
   database work proceeds. When there is a concrete repair case, use the
   [shared integration roadmap](CATALOG_MIGRATOR_ROADMAP.md) for that work.

## October 27, 2026 — DJ goal alignment and publication

The [DJ library workflow](DJ_LIBRARY_WORKFLOW.md) now records the shared goal:
a deeply organized, tagged library for DJing, probably through rekordbox.
README, roadmap, library-intelligence, integration, and shared coordination docs
link to its tagging, exact-version identity, preparation-preservation, and pilot
acceptance requirements. The sibling migrator's README, plan, context, and work
status retain its separate Spotify execution role and link to this design.

A small authorized local-audio pilot can progress independently of full Spotify
coverage or the bridge. Rekordbox adapters, analysis, tag writing, musical
recipes, and readiness tracking remain planned. Optional Obsidian use edits the
same Markdown or keeps private research separately; both repositories ignore
local `.obsidian/` settings. No vault or plugin was installed.

This follow-up changes documentation and ignore rules only. Publishing it does
not populate a database, import into rekordbox, or change Spotify. The earlier
preservation record below remains historical context.

Publication checks: 11 catalog tests and 65 sibling migrator tests passed;
added local/cross-repository links and anchors and Git whitespace checks passed.

## Preserved work

The local changes were uncommitted while main was one commit behind origin/main.
The missing upstream integration roadmap was incorporated before publishing the
local work. No evidence established why earlier work had been left uncommitted.

- Dated shadow-album navigation observation and private-context contributor guidance.
- Database-first library intelligence design, enrichment provenance, continuing
  refresh, multi-playlist exploration, DJ candidates, and artist/album placement.
- Capture SQLite versus historical catalog SQLite versus browser recovery storage.
- Versioned discovery handoff requirements retaining source coverage, negative
  observations, occurrence order, duplicates, identity uncertainty, and freshness.

This pass changes documentation only in this repository. Personal context,
credentials, captures, generated reports, and databases remain outside commits.

## Validation and linked impact

`python -m unittest test_library.py`: 11 tests passed on October 27.
The sibling migrator's `npm test`: 65/65 passed, covering persistent recovery and
failure gates with offline fixtures. No authenticated scan, database population,
Spotify mutation, or deployment was performed. The previously recorded October 22
browser smoke test was synthetic and was not rerun in this preservation pass.

Both repositories were reviewed. The migrator recovery is independent of catalog
completion; no catalog runtime/schema change or shared runtime is required.
