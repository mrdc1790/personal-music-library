# Personal Music Library

A local, evidence-preserving catalog for Spotify playlists, Liked Songs, and local-track references. It answers practical questions—where a song appears, where playlists overlap, what changed between captures, and which duplicate occurrences need review—without changing Spotify by default.

It is not a Spotify replacement or audio archive. Spotify metadata does not include Spotify audio, and a local-track reference does not prove that a file exists or plays on a device. The longer-term direction is a personal music hub that bridges streaming metadata, owned audio, organization, and DJ-oriented enrichment; that work remains separate from the working catalog.

## Start small

Double-click **`Try offline demo.cmd`** for a synthetic, self-contained walkthrough. For completed real data, double-click **`Preview saved music.cmd`** for a read-only, bounded explorer. Neither changes Spotify.

## What works today

| Need | Current behavior |
|---|---|
| Capture Spotify metadata | Read-only, resumable audit with durable SQLite checkpoints |
| Browse a small completed capture | Read-only HTML preview with placements, search, and two-playlist set operations |
| Keep history locally | Import snapshots into a separate SQLite catalog; prior snapshots remain intact |
| Find and compare | Search every occurrence; local union, intersection, difference, duplicate, and scan comparison |
| Inspect and protect | CSV exports, static catalog view, checksummed catalog ZIP, and restore verification |
| Preserve folders | Optional read-only Spotifast rootlist import; live validation still needed |
| Repair shadow tracks | Guarded reviewed migration commands; offline-tested only |

Not implemented: local audio-folder inventory/matching, canonical recording matching across Spotify IDs, full-library scale validation, saved smart-playlist recipes, playlist publishing/splitting, player/server integration, or a universal playback/Connect replacement.

## Non-negotiable boundaries

1. An occurrence is evidence: duplicate placements, order, failed coverage, local references, and snapshots are retained.
2. Unknown is not empty: an unreadable playlist or client disagreement is not a removal.
3. Catalog work is offline: only the explicit migration workflow can request a Spotify write, after review and `--execute`.

## Documentation map

| Read this | When you need it |
|---|---|
| [Operating guide](docs/OPERATING_GUIDE.md) | Scan, resume, import, query, preview, export, back up, or inspect folders |
| [Evidence and data model](docs/EVIDENCE_AND_MODEL.md) | Interpret identities, coverage, local tracks, duplicates, or client disagreement |
| [Examples](docs/EXAMPLES.md) | Reproduce the supported offline walkthrough |
| [Migration](docs/MIGRATION.md) | Review or execute a shadow-track migration |
| [Roadmap](docs/ROADMAP.md) | Understand planned work and the broader app vision |
| [Historical observations](docs/HISTORICAL_OBSERVATIONS.md) | Review dated count/recovery evidence without confusing it for current coverage |
| [Integration design](docs/INTEGRATION_DESIGN.md) | Understand the planned folder adapter and smart-collection interface |

Requirements: Windows, Python 3.11+, and no third-party Python packages. A Spotify Developer app is needed only for a scan or migration. Data defaults to `%USERPROFILE%\MusicLibraryData`, outside Documents/OneDrive; use `PERSONAL_MUSIC_LIBRARY_DATA`, `audit.py --output`, or `library.py --db` to choose another location.

The earlier topic-specific notes were consolidated so operations, evidence rules, and planned work each have one current source.

## Related project

[Spotify Playlist Migrator](https://github.com/mrdc1790/spotify-shadow-release-migrator) is a separate browser application for reviewed, explicit playlist and Liked Songs migrations. It shares the same safety principles but has its own codebase, OAuth flow, release cycle, and Git upstream. This repository is the long-lived catalog and evidence layer; neither repository imports code or data from the other at runtime.
