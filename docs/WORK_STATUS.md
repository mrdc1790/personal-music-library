# Work status

## November 26, 2026 — selected playlist capture and comparison

Pass a link, URI, or ID per `--playlist` to capture those playlists in a
resumable run. The run exports an importable snapshot, preserving Spotify's
local references, duplicate placements, and source coverage. Generate an
offline preview to compare in either direction, find shared tracks, or view
the union. This also works on a bounded selection from a full audit.
[Operating guide](OPERATING_GUIDE.md#capture-just-the-playlists-you-choose).

## November 26, 2026 — unavailable track and recovery report

`library.py availability` produces a private HTML report from an imported
capture. It lists unavailable placements, playable Spotify alternatives and
relinks, and local filename candidates when supplied with an inventory. The
report includes manual Spotify and SoundCloud searches for recovery leads.
See the [operating guide](OPERATING_GUIDE.md#unavailable-tracks-and-recovery).

Verified with 92 offline tests and a report from an existing catalog snapshot.
The catalog was opened read-only. A fresh Spotify capture and a personal local
inventory were outside this run.

## November 16, 2026 — offline checkpoint export and playlist capacity

`library.py export-checkpoint` exports committed rows and coverage from a
resumable audit without making Spotify requests. `library.py capacity` reports
historical playlist counts and estimated remaining slots, with an optional
comparison to an older capture. See the [operating guide](OPERATING_GUIDE.md#playlist-capacity).

Verified the bounded preview and exported a saved interrupted run into a
temporary copy of the historical catalog. The private baseline report contains
estimates and net changes where the evidence supports them. The original catalog
and checkpoint were unchanged. All 85 offline tests passed. No live Spotify
capture or account mutation was performed. The browser migrator's fresh
capacity preflight remains separate.

## November 16, 2026 — song scores and stream totals

[Song stats](OPERATING_GUIDE.md#song-stats) ranks observed songs by distinct
playlists and folder categories. It reports personal plays and dated worldwide
streams for Spotify and across imported services. The [worked example](EXAMPLES.md#rank-songs-and-import-stream-counts)
shows the scoring and stream fields. The [evidence model](EVIDENCE_AND_MODEL.md#evidence-behind-song-stats)
explains source coverage and the dates behind the join.

Validation covered 81 offline tests and a synthetic CLI run through the stream
importers, backup, restore, and reporting. A local report verified playlist
scoring against a saved partial audit. The implementation is complete. Refresh
the playlist and folder capture, import Extended Streaming History and available
dated worldwide totals, then check coverage on a small sample for a current
report.

## November 16, 2026 — original capacity handoff

**Initial task.** Use `Preview saved music.cmd` to check coverage in an existing
capture. The deliverable is a dated playlist capacity report from saved
evidence. If the existing capture is interrupted and cannot be imported, build
an offline checkpoint export first. The report should show playlist size,
coverage, and remaining slots where the recorded counts support an estimate.
This can start with the data already on disk.
[Implementation sequence and acceptance criteria](ROADMAP.md#next-work).

| Question | Current state |
|---|---|
| What happens at a rate limit? | The audit pauses and keeps committed pages in SQLite. The cooldown is saved. Resume the same run after it expires. The program requires a manual resume. |
| Does resume restart the scan? | Unchanged playlists reuse saved rows and continue at the last committed offset where applicable. Changed playlists are recaptured individually. Liked Songs requires rereading and validating the saved prefix, which uses requests. A mismatch restarts Liked Songs. Use a new audit for a separate dated capture. |
| Where do errors and progress go? | `RUN STATUS.txt` shows source progress, the latest failure, cooldown expiry, and resume instructions. `run.log.jsonl` keeps timestamped request, retry, failure, and checkpoint events. See the [operating guide](OPERATING_GUIDE.md#scan-and-resume). |
| Is there a diff between runs? | Import two captures and run `library.py compare` with their snapshot IDs. It reports placement and order changes, including how many copies remain when a track loses placements. Unread sources remain unknown. Comparison is a separate offline step. See the [comparison guide](OPERATING_GUIDE.md#catalog-queries-and-exports). |
| How do we investigate Liked Songs discrepancies? | Compare actual entries across the API, desktop, web, and phone where lists are available. Keep count-only evidence and device-specific gaps explicit. Use the read-only audio inventory for selected local folders. See [historical observations](HISTORICAL_OBSERVATIONS.md) and [local inventory](LOCAL_INVENTORY.md). |
| What can I visualize? | The read-only viewer supports search and playlist/snapshot selection. The bounded preview can browse completed sources from a saved run. Full-scale import and browsing, capacity, broader overlap views, and duplicate review remain work items. See [preview and folders](OPERATING_GUIDE.md#preview-and-folders). |
| How does Smarter Playlists fit? | Union, intersection, and difference work for covered sources. Saved recipes and a visual rule editor are planned. See [integration design](INTEGRATION_DESIGN.md). |
| How does this help with DJing or a central hub? | The catalog retains duration and supplied source metadata. Local filename and optional WAV duration can help surface file candidates. Verified recording matches, BPM/key analysis, cues, rekordbox exports, and player integration are roadmap work. See the [DJ workflow](DJ_LIBRARY_WORKFLOW.md). |
| What can we do about Spotify's 10k limit? | Keep the larger collection in the catalog and curate numbered Spotify playlists within a folder. The per-playlist limit still applies. Automatic splitting and publishing are planned. See [playlist curation](PLAYLIST_CURATION.md). |

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

1. Measure [catalog query and import cost](ROADMAP.md#next-work) and expand
   saved coverage when a fresh read-only capture is appropriate.
2. Try one category with two direct sibling volumes in Spotify while the
   database work proceeds. When there is a concrete repair case, use the
   [shared integration roadmap](CATALOG_MIGRATOR_ROADMAP.md) for that work.

## Current publication status

The checkpoint export, capacity report, selected playlist capture, and
availability report are part of the catalog. Refreshing inputs for the
[song-stats report](OPERATING_GUIDE.md#song-stats) remains a separate task.
[Current milestone status](CATALOG_MIGRATOR_ROADMAP.md#catalog-delivery-status).

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
