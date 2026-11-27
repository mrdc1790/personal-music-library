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

## Save an explicit review

After checking two known identities, save a pairwise `same-recording` or
`keep-separate` decision with a reason. Run `--decision clear` with a reason
to withdraw it. The report shows active decisions involving the source track.

```powershell
python library.py review-recording 'spotify:track:FIRST_ID' 'spotify:track:SECOND_ID' --decision keep-separate --reason 'Verified separate edits'
python library.py recording-reviews --key 'spotify:track:FIRST_ID' --history
```

Reviews are dated, backed up with SQLite, and retain superseded decisions.
They apply to the exact pair. They leave historical identities, counts,
ratings and migrations independent. A canonical group across multiple pairs
would need its own review and rules for conflicting decisions.

## Compare two saved releases

Take the exact album IDs from captured metadata or a saved candidate report.
Use the snapshot containing each edition's placements.

```powershell
python release_comparison.py OLD_RELEASE_ID NEW_RELEASE_ID --left-snapshot 1 --right-snapshot 3 --output 'C:\private\release-comparison.json'
```

The report lists observed tracks in disc and track order. Pairing uses the
observed identity or recording metadata. Ordinals describe positions only. The
report keeps resequenced candidates, competing matches, conflicts, duplicates
in playlist placements, and tracks without a compatible candidate. Pair
indexes are zero-based indexes into the left and right track lists.

The reported album totals are captured metadata. The known track list comes
from saved placements and may omit unobserved album tracks. Prepare a reviewed
replacement separately for any specific pair you choose to use.
