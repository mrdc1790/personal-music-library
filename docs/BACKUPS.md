# Backup and recovery

## What needs backing up?

There are three different things:

1. **Your catalog:** snapshots, titles, identities, playlist memberships, positions, metadata, history.
2. **Repair evidence:** migration plans and operation journals describing any Spotify writes.
3. **Your audio:** the actual MP3/FLAC/etc. files. A catalog cannot recreate them.

The implemented ZIP backup covers item 1. Keep original audit folders and repair journals separately. Audio backup is not implemented or performed by this tool.

## Make a consistent catalog backup

```powershell
python library.py backup backups/catalog-2026-09-16.zip
```

Use a new dated filename each time. The command uses SQLite's backup API, checks database integrity, and writes a ZIP containing:

- `catalog.sqlite`: consistent catalog copy including raw imported snapshots.
- `manifest.json`: format version, creation time, and SHA-256 checksum of the database.

The archive is **not encrypted**. It may reveal your music preferences, playlist names, account ID, and local reference metadata. OAuth tokens are not part of the audit snapshots produced by this project. There are no audio files inside this ZIP.

## Restore before relying on it

```powershell
python library.py restore backups/catalog-2026-09-16.zip data/restored-catalog.sqlite
python library.py --db data/restored-catalog.sqlite snapshots
python library.py --db data/restored-catalog.sqlite playlists
```

Restore refuses to overwrite an existing file, validates the checksum, checks the schema, and runs SQLite's integrity check. It reads only the known archive members, not arbitrary archive paths.

A checksum detects corruption; it is not a signature proving who created the archive. Restore archives you trust. Keep the original catalog untouched while checking the restored one. Using a restored local catalog does not revert Spotify itself.

The offline demo already exercised this complete round trip with synthetic data.

## Online backup: proposed next step, not configured

The project currently lives under OneDrive Documents. That means existing OneDrive settings may already sync project files. Sync status has not been checked, and no new upload, sharing setting, cloud account, or schedule was configured.

For an initial online copy:

1. Generate a new versioned ZIP after importing a good scan.
2. Put that closed archive in your chosen private backup destination, or keep it in a folder you have verified is already syncing.
3. Confirm the upload completed using that provider's interface.
4. Retrieve a copy and restore it under a new filename using the commands above.
5. Keep earlier archives. Do not automatically replace the only known-good copy.

Versioned archives are preferable to relying solely on a live SQLite file being synchronized while it changes. Synchronization can propagate a mistaken deletion. Keep another independent copy, including a copy of your music files, according to your storage capacity and preferred retention policy.

No hosted PostgreSQL instance or always-on server is needed for the current single-user catalog. Hosting becomes a separate decision if you later want several devices to edit one shared library. A backup destination is not the same thing as a hosted application.

## Suggested manual routine

After a scan/import you consider complete: keep the raw audit folder, produce the catalog ZIP, verify a restore, and copy the archive to the selected backup destination. This is a suggested manual routine, not a scheduled automation.

For the All Leaks audio collection, separately decide which directories hold authoritative files and where their audio backup lives. Do not assume Spotify playlist downloads can serve as a recoverable audio archive. No music folders were searched, moved, retagged or deleted during this work.

## If something goes wrong

- **Catalog damaged:** restore a known-good ZIP to a new file; inspect it before changing the working catalog.
- **Cloud copy missing:** the local command cannot verify provider sync; check the destination and retained versions.
- **CSV missing data:** reopen the scan report and manifest coverage flags. Re-export from the correct snapshot, not an incomplete later one.
- **Spotify repair interrupted:** preserve the operation journal and follow `MIGRATION.md`. A catalog restore alone does not repair account state.
- **Audio file missing:** a metadata snapshot may help identify it, but recovery requires an audio backup or another lawful copy.
