"""Build a dry-run M3U manifest from reviewed files and saved track placements."""

import argparse
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path, PureWindowsPath
import sqlite3

import library
import local_inventory
import logical_playlists
from storage_paths import data_root


def reviewed_path(hashes, confirmation):
    if confirmation is None:
        return 'unconfirmed', None, []
    paths = sorted(hashes.get(confirmation['sha256'], {}))
    if not paths:
        return 'confirmed_bytes_not_observed', None, paths
    if len(paths) == 1:
        path = paths[0]
    else:
        preferred = os.path.normcase(confirmation['path'])
        reviewed = [path for path in paths if os.path.normcase(path) == preferred]
        if len(reviewed) != 1:
            return 'ambiguous_paths', None, paths
        path = reviewed[0]
    if (not (Path(path).is_absolute() or PureWindowsPath(path).is_absolute())
            or any(character in path for character in '\r\n\x00')):
        return 'unsupported_path', None, paths
    return 'ready_in_saved_inventory', path, paths


def report(db, sid, inventory, playlist=None, collection=None):
    if (playlist is None) == (collection is None):
        raise ValueError('Select one playlist or one logical collection.')
    _, hashes, confirmations = local_inventory.inventory_index(inventory)
    at, account = db.execute('SELECT created_at,account_id FROM snapshots WHERE id=?', (sid,)).fetchone()
    sources = {row['source']: row for row in library.sources(db, sid)}
    if collection is not None:
        group = logical_playlists.definitions(db, account).get(collection)
        if group is None:
            raise ValueError('The logical collection was not found in this catalog.')
    else:
        source = sources.get(playlist)
        if source is None:
            raise ValueError('The playlist was not found in this snapshot.')
        group = dict(collection_id=None, name=source['name'], members=[playlist], active_playlist=None)
    selection = logical_playlists.describe(group, sources)
    placements, paths = [], []
    counts = Counter()
    for member in selection['members']:
        for key, source, position, title, local, basis in db.execute(
                'SELECT track_key,source,position,title,is_local,identity_basis FROM items '
                'WHERE snapshot_id=? AND source=? ORDER BY position', (sid, member['playlist_id'])):
            if local and basis != 'unidentified':
                confirmation = confirmations.get(key)
                status, path, observed = reviewed_path(hashes, confirmation)
            else:
                confirmation, path, observed = None, None, []
                status = 'unidentified' if basis == 'unidentified' else 'spotify_catalog_track'
            counts[status] += 1
            placements.append(dict(source=source, position=position, track_key=key, title=title,
                                   status=status, path=path, reviewed_at=confirmation['confirmed_at'] if confirmation else None,
                                   observed_paths=observed))
            if path is not None:
                paths.append(path)
    return dict(format_version=1, snapshot_id=sid, snapshot_captured_at=at, selection=selection,
                inventory_scan_id=inventory.get('scan_id'), inventory_finished_at=inventory.get('finished_at'),
                inventory_status=inventory.get('status'), counts=dict(counts), placements=placements,
                m3u_preview='\n'.join(['#EXTM3U', *paths, '']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=data_root() / 'catalog.sqlite')
    parser.add_argument('--snapshot', type=int)
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument('--playlist', help='Exact saved playlist ID')
    selected.add_argument('--collection', help='Configured logical collection ID')
    parser.add_argument('--inventory-db', type=Path, required=True)
    parser.add_argument('--inventory-scan', type=int)
    parser.add_argument('--output', type=Path, required=True, help='New private JSON manifest with draft paths')
    args = parser.parse_args()
    try:
        inventory = local_inventory.load_inventory(args.inventory_db, args.inventory_scan)
        with closing(library.connect(args.db)) as db:
            db.execute('BEGIN')
            sid = library.snapshot_id(db, args.snapshot)
            result = report(db, sid, inventory, args.playlist, args.collection)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'{error}\n')
    print(f'Saved dry run for {len(result["placements"])} observed placement(s).')


if __name__ == '__main__':
    main()
