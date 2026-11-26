# Review recording candidates from saved evidence

Run the offline report from one imported catalog. Supply an exact observed
Spotify track identity or local URI. Pick a source snapshot if the older track
only appears in history. The search snapshot supplies candidate Spotify tracks.

```powershell
python recording_candidates.py 'spotify:track:OBSERVED_TRACK_ID' --source-snapshot 1 --snapshot 3 --output 'C:\private\recording-review.json'
python recording_candidates.py 'spotify:local:Artist:Album:Title:180' --snapshot 3 --output 'C:\private\local-track-review.json'
```

The report shows the original and returned identity evidence available in the
capture, historical release fields, and known or unknown playability. It lists
every observed placement for the source and each candidate, with its original
position, snapshot and source coverage. Repeat placements are retained. Identical
metadata observations are compared once.

Matching ISRCs are one source of evidence. The fallback requires agreement on
title, primary credit, and duration within three seconds. The comparison keeps
version wording, and marks contradictory titles, artist IDs, explicit flags,
ISRCs or durations when they are supplied. Missing fields remain visible.
Even an ISRC candidate needs review before any substitution. A local URI
identifies a saved reference. Confirm the actual audio version separately.

The search is limited to captured catalog tracks. It makes zero provider
requests and does not authorize or execute a migration. An empty result means
there was no candidate within the saved search evidence. Capture more sources
or investigate a release separately if important evidence is missing.
