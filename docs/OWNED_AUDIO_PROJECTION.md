# Preview a playlist of owned audio

Inventory a small audio folder and [confirm the right files](LOCAL_INVENTORY.md)
for their exact Spotify local URIs. Generate a private manifest for one saved
playlist or [logical collection](OPERATING_GUIDE.md#group-split-playlists).

```powershell
python owned_audio_projection.py --playlist PLAYLIST_ID --snapshot 3 --inventory-db 'C:\private\inventory.sqlite' --output 'C:\private\audio-draft.json'
python owned_audio_projection.py --collection dance --inventory-db 'C:\private\inventory.sqlite' --output 'C:\private\volumes-draft.json'
```

The manifest lists every observed placement in order, including duplicates,
unconfirmed paths, and Spotify catalog tracks. It shows missing and partial
playlist coverage and the inventory scan date and status. The `m3u_preview`
field includes only confirmed bytes seen in the selected inventory. If multiple
paths contain those bytes, the manifest uses the originally reviewed path if
it still appears. Otherwise it leaves the placement unresolved.

The manifest is a preview with local paths as observed, without a device or
server mapping. Verify the files and path format on the intended target before
using the draft. The command does not open audio, connect to a player, copy files,
or edit Spotify or rekordbox.
