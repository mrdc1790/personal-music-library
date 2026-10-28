# DJ library workflow and rekordbox delivery (planned)

Direction clarified on **October 27, 2026**: the shared long-term goal is to DJ
with a deeply organized, tagged, trustworthy music library, probably through
rekordbox. Rekordbox is the leading target, not a verified installed version,
license, controller, or player configuration. Keep the catalog portable.

This is a design and acceptance plan. Audio analysis, tag writing, rekordbox
adapters, saved musical filters, and DJ readiness tracking are not implemented.
The existing catalog captures metadata and inventories selected audio roots;
filename candidates do not confirm recording matches.

## Responsibilities

| Layer | Responsibility |
|---|---|
| Selected audio files | Playable assets with origin, exact version, file identity, and observed locations; keep originals and backup evidence |
| Personal Music Library | Durable identities, source observations, personal decisions, enrichment provenance, saved recipes, and future readiness/export history |
| Rekordbox | Intended preparation/performance surface for reviewed beatgrids, cues, loops, playlists, and target-device preparation; import supported observations back into the catalog later |
| Spotify Playlist Migrator | Review and execute explicitly approved Spotify instance replacements; it does not transfer audio, cues, or DJ preparation |
| Optional Obsidian | Research, taxonomy explanations, listening notes, and project navigation through Markdown; no required runtime role |

The catalog's normalized labels and personal decisions are the portable master
view. Preserve rekordbox edits as attributed observations and reconcile conflicts
per field; do not blindly replace them from an older catalog export. The audio
files remain the assets, and rekordbox preparation needs its own backup.

Spotify membership capture, a Spotify migration, local-audio preparation, and a
rekordbox handoff are independent workflows. A Spotify ID replacement does not
prove that an audio file or its cues should change. Follow the separate
[catalog/migrator roadmap](CATALOG_MIGRATOR_ROADMAP.md) for that bridge; DJ pilots
need not wait for it or a complete Spotify collection.

## Design for the preparation workflow

1. **Intake and identify.** Inventory explicitly selected audio read-only. Keep
   origin, availability, format, duration, file paths, and version descriptions.
   Distinguish originals, extended/radio edits, remixes, live versions, and
   clean/explicit versions. Titles, artist names, and equal durations are only
   candidate evidence. Audio acquisition remains a separately scoped action.
2. **Analyze once and retain corrections.** Import chosen DJ analysis or run a
   separately selected analyzer on authorized audio. Record file/recording match,
   tool and model version, settings, time, confidence where supplied, and errors.
   Missing/failed results stay unknown. A background queue should resume and
   reuse valid work; ordinary searches use the saved database without provider
   calls. User corrections survive later imports and reanalysis.
3. **Tag for decisions.** Start with a small vocabulary that helps choose the
   next track. Expand it after use rather than require exhaustive tagging before
   a track can enter the library. Preserve raw provider/model labels alongside
   normalized and user-reviewed values.
4. **Build reusable crates.** Save visible AND/OR/NOT rules over selected sources,
   tags, tempo, key compatibility, readiness, and personal preferences. Show
   inclusion reasons and missing/conflicted feature counts. Save rules separately
   from ordered results; preserve deliberate repeats unless the chosen recipe
   explicitly deduplicates at a named identity level.
5. **Prepare and audition.** In the chosen DJ software, review beatgrids, cues,
   phrase boundaries, vocal clashes, and actual transitions. Tempo/key similarity
   narrows candidates; it does not establish a good mix. Retain section-specific
   evidence when one track-wide BPM, key, or energy label is inadequate.
6. **Deliver and learn.** Preview the exact output and unresolved items, test on
   the chosen application/device profile, and retain export versions and review
   results. Later import supported preparation/history observations explicitly.
   Set notes or play history alone do not prove audience response or track quality.

## Useful fields and independent meanings

| Area | Suggested evidence or personal labels |
|---|---|
| Identity | Exact mix/edit, reviewed recording link, preferred playable file, origin, observed path, and unresolved alternatives |
| Musical measurements | BPM with half/double-time and variable-tempo handling; tonic/mode and notation; segment evidence where available |
| Style | Broad genre plus multiple meaningful subgenres; artist/release tags remain distinct from track labels |
| Mood and intensity | Separate mood descriptors and an explicitly defined personal energy scale; tool scales are not automatically comparable |
| Performance use | Vocal/instrumental characteristics, intro/outro notes, warmup/peak/reset/closing roles, and reviewed transition notes |
| Personal preference | Enjoyment/favorites and familiarity, separate from energy, genre, or readiness |
| Preparation | Analysis status, review decisions, cue/grid observations, and dated validation for the selected target |

For illustration, a recipe might select `(melodic OR atmospheric) AND 135-145
BPM AND instrumental`, then rank by a declared energy preference. These are
synthetic labels, not findings about the user's collection. Define handling of
unknown fields and show excluded/unresolved counts instead of claiming complete
classification. Start with deterministic filters; an optional language interface
can later produce a visible recipe without receiving Spotify records.

Track file identity separately from recording identity and playlist occurrences.
Moving a file does not create a new recording. Editing file tags changes a byte
hash without necessarily changing audio; preserve that history. Do not transfer
cues between different edits, delete copies, reorganize folders, rewrite tags, or
transcode originals as a side effect of matching or enrichment. Keep paths stable
after preparation and make any future relocation an explicit reviewed operation.

## Rekordbox exchange and preservation

The official [rekordbox 7.2.14 manual](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)
documents My Tag and combined track filtering (printed pages 30-32), XML library
import (page 19), tag reload (page 26), and library backup/XML export (page 246).
It also describes adding My Tag text to Comments. These documented features do
not establish a lossless round trip for our data or a specific user's setup.

Before an adapter, create a versioned field-mapping and ownership table:

- Map portable catalog genre/subgenre, mood, energy, and set-role fields to an
  intentionally small rekordbox view. Evaluate My Tag, Genre, Comments, Rating,
  and Color separately; do not use one field for several incompatible meanings.
- Test which values actually survive the selected import/export route. Do not
  assume My Tag categories, intelligent-playlist rules, beatgrids, cues, loops,
  ratings, colors, or analysis locks are exported or restored by every format.
  An M3U provides paths/order, not a complete preparation backup.
- Treat Comments as user content. Any future encoded-tag projection needs a
  declared format, collision policy, and preservation of existing text. Showing
  My Tag text in Comments does not prove that Comments reconstructs My Tag.
- Capture catalog, file-tag, and rekordbox values independently. Preview conflicts
  and proposed changes field by field. A tag reload can replace edited library
  information; do not silently reload tags or overwrite manually corrected BPM,
  key, grids, cues, or locks.
- Prefer explicit documented exchange files and reviewed imports initially.
  Do not edit rekordbox's live private database. Keep output manifests with
  schema/producer versions, source evidence, file mappings, order, repeats,
  missing fields, omitted items, and known losses. Retrying an output must not
  duplicate crates or erase later edits without a declared reconciliation policy.

Rekordbox version, mode/plan, playback route, player/controller model, firmware,
and supported file formats are acceptance inputs, not project-wide assumptions.
A laptop/controller preparation and a USB/player delivery require separate checks.
Keep audio backups, catalog backups, and rekordbox library/preparation backups
distinct. An XML export or catalog ZIP must not be advertised as backing up all
three. Keep personal exports and results under the existing `storage_paths.py`
data root or an explicitly selected location, outside Git and default OneDrive
Documents storage.

## Small delivery sequence and acceptance

1. **Manual pilot:** choose a small, diverse authorized local sample, provisionally
   20-30 tracks, agree on useful labels, and inspect a chosen rekordbox export.
   Include a remix/edit pair, repeated placements, and uncertain/missing fields.
   This can progress independently while Spotify coverage or quota is unresolved.
2. **Read-only importer:** implement one chosen exchange format with synthetic
   fixtures and temporary databases. Preserve raw input, exact paths/identities,
   duplicates, unknown fields, and conflicting human corrections. Import makes
   no provider calls and changes neither audio nor rekordbox.
3. **Local recipes and dry-run output:** build one useful musical filter and a
   manifest for a disposable test crate. Report unsupported fields and unresolved
   file mappings before any separately reviewed import or file-tag write.
4. **Validate round trip and playback:** use backups and disposable files/crates
   to compare before/after values, cue/grid retention, order/repeats, path handling,
   reruns, and target playback. Add one analyzer only after evaluating its actual
   accuracy, license, installation cost, and permissions for the intended inputs.

Do not require every optional label before declaring a track usable. Define a
target-specific readiness checklist: correct reviewed asset/version, readable
file, supported format, accepted analysis uncertainty, required preparation, and
dated audition/export verification. Report separate states such as inventoried,
analyzed, reviewed, and verified on the target. Success is faster reliable track selection
and preserved preparation, not a high count of automatically generated tags.

## Optional Obsidian and repository workflow

Obsidian can directly edit the same Markdown files tracked by Git. Its
[vaults are ordinary folders](https://help.obsidian.md/data-storage); there is no
required API integration. Keep shared architecture, roadmaps, and tagging rules
in their authoritative repo documents using normal relative Markdown links that
also work on GitHub. Obsidian should not create a second copy of these plans.

For a cross-project overview, an optional private vault outside both repositories
can link to their GitHub docs and contain listening notes, research, and set
ideas. That is navigation, not synchronization or permission for the apps to
read the vault. Alternatively, open a selected documentation folder as a vault
and edit those files in place. A docs-only vault will not include root READMEs;
links outside its scope still need the usual editor or repository browser.

Each vault has its own scope. A single view over two sibling repositories needs
a deliberate folder/link design; do not automatically open the whole shared
parent, copy both trees, or add junction/symlink synchronization. No vault,
plugin, sync service, or Git automation is installed by this plan.

Both repositories ignore `.obsidian/` settings directories so optional local
workspace/plugin state stays out of commits. This does not hide ordinary notes,
and Git ignore rules do not restrict Obsidian visibility, plugins, or a sync
service. Keep personal notes outside the shared repos and keep credentials,
private context, audio, databases, captures, and generated exports outside a
shared vault. Use one chosen sync strategy only if cross-device notes are needed.

Bases can later organize selected note properties, but neither Bases nor a
one-note-per-track export is the catalog engine. Any future note export should
be explicit, curated, and one-way initially, with stable catalog references;
editing a note must not silently update SQLite, file tags, rekordbox, or Spotify.

## Linked scope

Both repositories' plans were checked. The companion migrator documentation
points here because this goal shapes their shared direction; its execution
scope and safety rules remain unchanged. No runtime dependency, schema change,
analysis run, account action, or rekordbox import is part of this docs update.
