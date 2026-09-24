# Small real-data trial and Spotify folders

Updated September 24, 2026.

## First action: look at your results

Double-click **Preview saved music.cmd** in the project folder. It creates and opens `%USERPROFILE%\MusicLibraryData\previews\trial.html` using the latest resumable audit database. It does not sign in, contact Spotify, or start/resume the audit. Each refresh replaces only this derived preview file; source databases are read-only.

The initial real trial generated for this account uses 8 completed playlists and [private count] placements from the September 22 run. That run had a small completed subset of known sources (580 playlists plus Liked Songs). The rest of the account is not represented by the trial. Liked Songs is not included in this trial. A song absent here is not necessarily absent from Spotify.

1. Choose **Playlist A** to browse.
2. Click an **Overlap with A** count to inspect songs shared with that playlist.
3. Choose **In both**, **In A, absent from B**, or **In either** for two-source set operations.
4. Search title, artist, or identity.
5. Click a song to see all its positions across the selected trial playlists. Duplicate placements are retained, although the main table groups identical observed identities.

Set membership means the same observed Spotify ID or local URI. It does not merge different releases of the same recording. Unidentified entries remain visible in ordinary browsing but are excluded from set operations. Local references do not establish that an audio file exists on disk or on a phone.

Defaults limit the trial to 8 complete sources and 10,000 placements. Sources are selected deterministically with preference for nonempty playlists of 50–1,500 placements; selection is a sample, not a representative statistical survey. No playlist is truncated and then labeled complete. At most 50 sources / 50,000 placements are permitted by explicit overrides.

```powershell
python preview_audit.py --run '%USERPROFILE%\MusicLibraryData\backups\20260922-230518-468551' --open
# Choose two completed playlists by ID (repeat --playlist):
python preview_audit.py --run 'C:\path\to\run' --playlist PLAYLIST_ID_A --playlist PLAYLIST_ID_B --open
```

The preview reads one consistent SQLite transaction, checks contiguous positions and source counts, and includes capture/validation timestamps in its data. It reads selected rows directly without generating a huge library JSON or importing all account history. This is the useful small trial before a full scan; it is not a new limited online scanner mode. Keep the HTML private: it contains your music metadata.

## Do nested playlists currently get captured?

The Web API audit can capture accessible playlists that happen to sit inside folders. It does **not** capture their folder membership, parent folders, empty folders, or folder ordering. The order of songs within each captured playlist is retained.

There is now a second, offline adapter: **folder_tree.py** imports Spotifast's saved account rootlist and retains:

- Folder IDs and names, including duplicate names and empty folders.
- Parent-child nesting and sibling order.
- Playlist references by ID, including repeated references and references absent from the track scan.
- Account, import time, source filename/file modification time, original hierarchy payload, and separate historical structure snapshots.

The output is `%USERPROFILE%\MusicLibraryData\hierarchy.sqlite`. It is deliberately separate from the track audit and catalog. The preview joins it by account and playlist ID. You can add or refresh hierarchy without rereading playlist tracks or starting a fresh audit. Uncaptured playlist contents remain explicitly outside the trial; an empty folder remains a folder.

**Actual account limitation:** the installed older Fastpotify `session.json` inspected here contains no rootlist. Its collapsed-folder preferences are not sufficient evidence to reconstruct your hierarchy. The adapter is implemented and tested on source-compatible fixtures, but your actual nested tree has NOT been captured or visually checked against Spotify yet.

## Capture your actual tree through Spotifast

Current Spotifast documents an account-scoped `rootlist` in `session.json`. Use a current release, sign into your account, let its folders load, then quit normally so its session is saved. This project does not install/upgrade Spotifast, extract its credentials, or establish a librespot session for you.

After that, double-click **Import Spotify folders.cmd**. It uses the latest default audit to verify your account, imports the folder tree, and refreshes the trial on success.

Equivalent commands from the project folder:

```powershell
python folder_tree.py --run '%USERPROFILE%\MusicLibraryData\backups\20260922-230518-468551'
python preview_audit.py --run '%USERPROFILE%\MusicLibraryData\backups\20260922-230518-468551' --open
```

The first command checks the standard Windows Spotifast then legacy Fastpotify session paths. To choose explicitly:

```powershell
python folder_tree.py 'C:\path\to\session.json' --run 'C:\path\to\audit-run'
```

The audit account must match the rootlist account. No token is needed. No network calls are made. Only the rootlist data is retained; unrelated session/history fields are not copied. Missing trees, unknown entry shapes, invalid playlist URIs, duplicate folder IDs, and unbalanced folder markers are rejected instead of silently guessing a tree. Balanced cached data can still be incomplete or old: Spotifast's display parser repairs some malformed raw input upstream, and its cache does not provide a trustworthy rootlist capture timestamp/revision. Accordingly the viewer labels freshness/completeness **unverified**, not a verified complete folder backup. Validate a few known nested branches, an empty folder, and sibling ordering before relying on it.

The importer also accepts an explicit envelope `{ "account_id": "...", "uris": [...] }` for a future raw exporter. It does not fetch that payload itself. Unknown raw URI types fail explicitly; no entries are silently dropped. Direct librespot fetching, revision validation across rootlist pages, and restoring/moving Spotify folders are not implemented.

## Synthetic folder example

The checked-in `examples/spotifast-session.synthetic.json` contains Dance → Bass → playlist, an empty folder, and a root-level playlist. It is not your account.

```powershell
python folder_tree.py examples/spotifast-session.synthetic.json --account SYNTHETIC-FOLDERS --database "$env:TEMP\pml-example-folders.sqlite"
```

Repeated identical imports reuse the latest snapshot. Changed structure adds a new snapshot, including changing back to an older tree. Account matching prevents a synthetic/different account tree from appearing in your real preview. Old snapshots remain in the SQLite file.

## Rate limits and changes between sessions

A 429 pauses the audit, preserving committed pages. The console and `RUN STATUS.txt` show the failure and local cooldown expiry; `run.log.jsonl` retains timestamped requests/errors/checkpoints. There is no notification toast, email, or automatic wakeup. Resume the same run after cooldown using its `Resume this audit.cmd`. Starting a new run creates a new folder and does not bypass the app's saved cooldown.

On resume:

- Changed playlist snapshot ID: recapture that playlist only.
- Unchanged playlist: reuse completed contents or continue its interrupted page sequence.
- Liked Songs: reread the saved prefix and total; a mismatch restarts Liked Songs only. This validation costs requests and may itself be rate-limited. Avoid editing likes during capture. Same-count edits during an unversioned live scan can still escape detection; there is no atomic account snapshot guarantee.
- Newly created/followed playlists: the run's completed discovery list does not automatically expand. A future fresh scan discovers them.
- Folder changes: import a new rootlist separately. Track and folder capture times remain independent.

Resume is recovery, not a historical diff. Comparing two historical song snapshots is available through the catalog after import; it is not automatic on every restart. The full-account JSON importer/viewer still needs scaling improvements. The bounded preview avoids that bottleneck for this trial.

## Where Spotifast fits the larger project

A second provider adapter is useful evidence, especially for folder organization. It does not yet prove access to hidden original relinked IDs, resolve Liked Songs count discrepancies, remove rate limits, or bypass Spotify's 10k playlist constraint. Actual local audio inventory and duration/tag/fingerprint matching remain separate work. This preview supplies the first visual set operations inspired by Smarter Playlists; saved recipes, a node editor, DJ metadata analysis, and player/media-server integration remain future work.

Primary references: [Spotifast settings and files](https://spotifast.rocks/settings-and-files/), [rootlist reader and parser](https://github.com/crmne/spotifast/blob/main/src/player.rs), [serialized rootlist schema](https://github.com/crmne/spotifast/blob/main/src/settings.rs). See [source investigation](SPOTIFAST_ADAPTER.md) for protocol boundaries.
