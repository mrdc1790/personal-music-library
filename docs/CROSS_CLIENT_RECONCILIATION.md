# Cross-client Spotify reconciliation

The `[private track ID]` incident demonstrated that desktop and phone can
show incompatible playlist/Liked Songs membership. The long playlist-migrator
**Build preview** run was discovery only; it did not execute an account write.

Treat client UI state as append-only evidence, not a source of destructive
truth. Capture stored occurrence URI and position, requested/effective URI,
time, platform/app version, market, UI surface, `present`/`absent`/`unknown`
result, and raw evidence. A client-side absence is conflicting evidence; only a
fresh authoritative library/playlist read may establish a removal.

This complements, rather than replaces, the recording/release/catalog-instance
identity model. A playable client object can differ from the stored occurrence,
and playback does not prove matching membership identity.
