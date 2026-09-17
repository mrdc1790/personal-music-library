# What you can do today

Updated September 17, 2026. The conversations have been consolidated into one project and roadmap. The complete music hub described in them has not been built.

## Browse your music

Double-click `View music catalog.cmd` to search songs and browse playlist placements in an imported catalog. Until a real scan is successfully imported, this opens synthetic demo music. Running the audit and importing it into the catalog are currently separate steps; the README explains the import.

There is no all-library overlap map yet. Union, intersection, and difference already work as commands. A useful next interface would show playlist sizes, rank the playlists sharing the most songs with a selected playlist, and let you click a shared count to inspect those songs. For hundreds of playlists, this is a more readable starting design than displaying every song as a connected dot.

## Three distinct problems

| Problem | What is implemented | What remains |
|---|---|---|
| Repeated entries | Export repeated observed identities and their positions; preserve original duplicates | Reviewed deduplication workflow and recording-level matching across different releases |
| Relinking / shadow releases | Preserve original/returned IDs when supplied; guarded migration tools with offline tests | Reliable account evidence, candidate review, live validation; automatic repair is blocked without adequate evidence |
| Local tracks | Preserve the metadata and Spotify local references returned in playlists | Inventory actual folders, match files, detect missing/ambiguous matches, verify playback on each device |

Two identical observed IDs and two releases of the same recording are different matching problems. Spotify's automatic relinking is also different from deciding that a reissued album should replace an older album in every playlist. [Spotify describes relinking as substituting an available instance for a market-unavailable track](https://developer.spotify.com/documentation/web-api/concepts/track-relinking). Its [Development Mode guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide) removes `linked_from`, which limits evidence about original stored IDs.

[Spotify's playlist documentation](https://developer.spotify.com/documentation/web-api/concepts/playlists) describes local references as metadata-based URIs and states that the Web API cannot add local files. A reference is not an audio file or proof that the phone has it.

## Symfonium's role

[Symfonium](https://www.symfonium.app/) is an Android player for accessible audio from supported local, cloud, network, and media-server providers. It does not consume this SQLite catalog directly or turn a Spotify track ID into playable audio.

Proposed connection: catalog entry -> verified local file/provider item -> exported playlist -> Symfonium. Matching and export are still planned. [Symfonium supports M3U/PLS import for supported file providers](https://docs.symfonium.app/wiki/providers/import-sync-media-providers-playlists/); path matching and duplicate handling would need validation with a small real collection.

It is worth a small trial if the immediate goal is better listening to existing MP3/FLAC files on Android. A server is optional for that test. It does not solve the problem of streaming Spotify-only songs in one oversized playlist.

## The 10k limit

Treat Spotify's 10,000-entry playlist limit as a constraint on Spotify output. [Soundiiz documents this operational limit](https://support.soundiiz.com/hc/en-us/articles/10006072755730-Spotify-Playlist-Limit-10-000-Songs-per-Playlist). The local catalog has no intentional equivalent cap, but performance at this user's full library scale is not yet measured.

The proposed approach is to organize one large local collection and maintain smaller Spotify playlists as outputs. For example, a 24,000-entry collection could produce three 8,000-entry parts. This does not make them one 24,000-entry playlist inside Spotify or promise seamless shuffle across parts. Splitting/publishing is not implemented. Local references would require separate handling because the Web API cannot add them.

Deduplication might recover some space, but no capacity saving is known until real data is captured and candidates are reviewed. Owning the audio enables a separate playback path; simply exporting its metadata does not.

## First live audit finding

The September 17 attempt ended with `status: incomplete`, zero occurrences, zero playlists, and HTTP 502 reading `/v1/me/tracks`. This is a failed export, not a measurement of the library. No empty real catalog was imported.

The read-only client now retries HTTP 500/502/503/504 with waits of 2, 4, 8, and 16 seconds, then reports a server error if it still fails. Access denials are not retried as server errors. Three regression tests cover recovery, exhaustion, and access denial; all 37 tests pass. This improves resilience but cannot guarantee the remote service will recover.

Next step: rerun `Start audit.cmd`, complete sign-in, and check the report's status and errors before importing the new snapshot. Preserve the failed run for diagnosis.
