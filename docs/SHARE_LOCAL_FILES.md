# Sharing local music for Spotify playlists

This is a practical handoff guide for sending someone MP3s that can appear beside Spotify tracks in their playlists. It is not a catalog import, an audio backup, or a guarantee that a particular device has received or can play a file.

## Before sending the instructions

- Send the recipient a folder containing the audio files and, if applicable, a Spotify playlist that already contains the local-track references.
- Ask them to keep the folder in a permanent local location, such as `C:\Music`. They should not delete or move it after adding it to Spotify; moving it can break Spotify's local-file reference on that computer.
- This process gives the recipient their own local copy of the audio. It does not upload the files to Spotify or make them available to other Spotify users.

## Set up local files on the computer

In the Spotify desktop app:

1. Open **Settings**, find **Library**, and turn on **Show Local Files**.
2. Add or select the folder that contains the MP3s.
3. Open **Your Library → Local Files** to confirm the songs appear.
4. Add the songs to Spotify playlists as usual. If the sender already added matching local tracks to a shared playlist, such as *Secret Dreams*, they may already appear there after Spotify recognizes the files.

Spotify's settings labels and available file types can vary by app version and platform. If the folder or tracks do not appear, confirm the files are still in the selected folder and restart the desktop app before changing anything else.

## Download the playlist on a phone

For the best chance of syncing local tracks to a phone:

1. Keep the phone and computer on the same Wi-Fi network.
2. Leave Spotify open on both devices and sign in to the same Spotify account.
3. On Windows, set the computer's active Wi-Fi or Ethernet network profile to **Private**: **Settings → Network & Internet → Wi-Fi/Ethernet → [your network] → Network profile type → Private**.
4. On the phone, open the playlist containing the local tracks and download that playlist.

Spotify should then transfer the local files needed by that downloaded playlist to the phone. If it does not, keep both devices awake with Spotify open on the same network and retry the playlist download. Do not treat a missing phone track as evidence that the source file was deleted or that another device lacks it.

Once transferred, local songs can be interlaced with regular Spotify tracks in the same playlist. They remain dependent on the local files and device sync; they are not ordinary Spotify catalog tracks.

## Copy/paste message for a friend

> Download the folder I sent you and put it somewhere permanent on your computer, like `C:\Music`—please do not move or delete it afterward. In the Spotify desktop app, go to **Settings → Library**, turn on **Show Local Files**, and add/select that folder. The songs should appear in **Your Library → Local Files**. You can add them to playlists like normal; they may already show in the playlist I sent you if Spotify matches them. To get them on your phone, keep Spotify open on both your computer and phone, use the same Spotify account, and put both devices on the same Wi-Fi. On Windows, make sure the computer's network profile is **Private**, not Public. Then open the playlist on your phone and download it. Spotify should sync the local MP3s, so they can sit alongside regular Spotify songs in the same playlist.

## Catalog boundary

This project currently records only local references Spotify returns in scanned playlists. It does not scan the supplied folder, copy audio, configure Spotify, or verify phone transfer/playback. Record any desktop or phone result as a timestamped device observation rather than treating it as complete coverage.
