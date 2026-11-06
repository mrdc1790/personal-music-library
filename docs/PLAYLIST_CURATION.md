# New Music Friday and Spotify playlist folders

On November 5, 2026, the owner reported that folder shuffle worked on mobile and
desktop. Keep the weekly New Music Friday selection manual. For a
growing category, keep the existing playlist and its link as the first volume.
Add a second volume for new selections and place both playlists directly inside
the same Spotify folder. Start playback from the folder to listen across volumes.

```text
Dubstep
  Dubstep 01 (existing playlist)
  Dubstep 02 (current additions)
```

## What Spotify documents

- Spotify supports nested folders for organization. Its folder guide describes
  sequential play and shuffle across playlists in a folder on desktop and
  mobile. A June 2026 community report describes desktop including descendants
  while mobile played only playlists directly in the folder. Treat recursive
  playback as a per-client test. [Folder setup](https://support.spotify.com/us/article/playlist-folders/),
  [folder playback guide and discussion](https://community.spotify.com/forum/en/discussion/7411628/playlist-folders-are-now-available-on-mobile-here-s-how-to-organize-your-playlists).
- The Play Queue shows upcoming tracks and separates manual additions from
  tracks supplied by the playback source. Queue visibility and the folder's
  shuffle pool are separate measurements. Published guidance leaves aggregate
  folder size, maximum playback depth, and full shuffle coverage unspecified.
  A folder holding 100 full playlists would represent 1,000,000 placements.
  Playback at that scale is unverified. [Play Queue guide](https://community.spotify.com/forum/en/kb/articles/807-how-does-the-play-queue-work),
  [folder playback guide](https://community.spotify.com/forum/en/discussion/7411628/playlist-folders-are-now-available-on-mobile-here-s-how-to-organize-your-playlists).
- Spotify lists whole-folder playback as unsupported over Spotify Connect.
  Select an individual volume for Connect. Test local tracks on each device
  with its own files and sync state. Use the native client to add local tracks
  and organize folders. [Folder playback FAQ](https://community.spotify.com/forum/en/discussion/7411628/playlist-folders-are-now-available-on-mobile-here-s-how-to-organize-your-playlists),
  [local files support](https://support.spotify.com/us/article/local-files/),
  [Spotify playlist API](https://developer.spotify.com/documentation/web-api/concepts/playlists).

## How the limits apply

| Scope | Meaning |
|---|---|
| Ordinary Spotify playlist | 10,000 songs per playlist. Each volume has its own capacity. [Spotify save-limit FAQ](https://community.spotify.com/forum/en/kb/articles/792-is-there-a-save-limit-on-spotify) |
| Spotify saved library | Spotify documents unlimited saved items. Track Liked Songs coverage separately from placements and device-local availability. [Spotify save-limit FAQ](https://community.spotify.com/forum/en/kb/articles/792-is-there-a-save-limit-on-spotify) |
| Offline HTML trial | The default budget is 10,000 placements total across up to eight completed sources. Explicit overrides allow up to 50,000 placements total and up to 50 sources. Two 8,000-item playlists take 16,000 placements. [Preview commands](OPERATING_GUIDE.md#preview-and-folders) |
| Historical SQLite catalog | Plan separate storage and query benchmarks for 100,000 observed identities, more placements than identities, and repeated snapshots. [Catalog roadmap](ROADMAP.md#next-work) |

A placement is one position in one source. Preserve repeats within and across
playlists, including local references and unavailable rows. When reporting
space, use placement counts with dated coverage. Treat an incomplete or
conflicting count as unknown headroom.

A November 5 synthetic SQLite import and reopen retained 190,000 placements
across 100,100 observed identities. It included 100,000 saved tracks, nine full
playlist volumes, local references, and repeats. Use separate benchmarks for
browsing and repeated snapshots. Playback needs device testing.

## One-category playback pilot

1. Use one existing category near capacity. Keep the existing volume and use
   a second, smaller sibling for new selections. Confirm tracks unique to each
   volume play from the folder on the phone and desktop. Check ordered play
   and regular shuffle separately. Turn off Autoplay during the check so
   recommendations stay out of the results.
2. Test depth with a small parent folder containing one direct playlist and a
   subfolder containing a distinct playlist. Use recognizable tracks, test
   from the parent and leaf on each device, then add another level only if
   useful. If the parent skips descendants, open the leaf folder for playback.
   Keep the volumes of any category you want to shuffle together as direct
   siblings.
3. Try a combined collection over 10,000 placements using existing volumes.
   Record device/app version, folder depth, combined placements, volumes
   heard, start time, and whether playback continues or resumes. Test local
   and streamed tracks separately. Use a small fixture to verify which
   branches participate and larger sessions to observe practical reliability.

## Catalog support

The first deliverable is a read-only capacity report from saved observations.
It should help choose an active volume, flag playlists near the cap, and show
where more evidence is needed. Later, map volumes by stable playlist ID into
one logical collection per category and preview rollover destinations. Keep
the original playlist memberships, order, and duplicate occurrences.

Native folder playback makes automatic splitting and publishing optional.
Measure the work of manual rollover before adding a writer. Keep the separate
migrator focused on reviewed track and release repairs. The database and manual
folder workflow can progress independently of that repair integration.
[Delivery order](ROADMAP.md#next-work),
[collection design](INTEGRATION_DESIGN.md#large-collections-and-bounded-provider-outputs-planned).
