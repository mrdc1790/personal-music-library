"""Read-only Spotifast rootlist adapter; never accesses tokens or Spotify."""
from contextlib import closing
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote_plus

from storage_paths import data_root


def normalize(document):
    """Accept Spotifast SessionState/CachedRootlist or an explicit raw URI envelope."""
    if not isinstance(document, dict):
        raise ValueError('Expected a JSON object containing an account-scoped rootlist.')
    root = document.get('rootlist', document)
    if not isinstance(root, dict) or not isinstance(root.get('account_id'), str) or not root['account_id']:
        raise ValueError('No account-scoped rootlist found. Refresh folders in current Spotifast and quit normally to save session.json.')
    entries = root.get('entries')
    if entries is None and isinstance(root.get('uris'), list):
        entries = []
        for uri in root['uris']:
            if not isinstance(uri, str):
                raise ValueError('Rootlist URIs must be strings.')
            if uri.startswith('spotify:start-group:'):
                ident, _, name = uri[len('spotify:start-group:'):].partition(':')
                entries.append({'FolderStart': {'id': ident, 'name': unquote_plus(name)}})
            elif uri.startswith('spotify:end-group:'):
                entries.append('FolderEnd')
            elif uri.startswith('spotify:playlist:'):
                entries.append({'Playlist': uri})
            else:
                raise ValueError('Unsupported rootlist URI; refusing to silently drop an entry.')
    if not isinstance(entries, list):
        raise ValueError('Expected rootlist.entries or rootlist.uris list.')
    nodes, stack, counts, folder_ids = [], [], {}, set()
    for entry in entries:
        if entry == 'FolderEnd':
            if not stack:
                raise ValueError('Unmatched folder end; hierarchy not imported.')
            stack.pop()
            continue
        parent = stack[-1] if stack else None
        node = dict(node_id=len(nodes), parent_id=parent, sibling_order=counts.get(parent, 0))
        counts[parent] = node['sibling_order'] + 1
        if isinstance(entry, dict) and set(entry) == {'FolderStart'}:
            folder = entry['FolderStart']
            if not isinstance(folder, dict) or not isinstance(folder.get('id'), str) or not folder['id'] or not isinstance(folder.get('name'), str):
                raise ValueError('Invalid folder metadata.')
            if folder['id'] in folder_ids:
                raise ValueError('Duplicate folder ID; hierarchy not imported.')
            folder_ids.add(folder['id'])
            node.update(kind='folder', provider_id=folder['id'], name=folder['name'])
            stack.append(node['node_id'])
        elif isinstance(entry, dict) and set(entry) == {'Playlist'}:
            uri = entry['Playlist']
            if not isinstance(uri, str) or not re.fullmatch(r'spotify:playlist:[A-Za-z0-9]{22}', uri):
                raise ValueError('Invalid playlist URI.')
            node.update(kind='playlist', provider_id=uri.rsplit(':', 1)[1], name=None)
        else:
            raise ValueError('Unsupported rootlist entry; hierarchy not imported.')
        nodes.append(node)
    if stack:
        raise ValueError('Unclosed folder; possible truncated rootlist. Nothing imported.')
    return root['account_id'], nodes


SCHEMA = '''
CREATE TABLE IF NOT EXISTS hierarchy_snapshots (
 id INTEGER PRIMARY KEY, account_id TEXT NOT NULL, checksum TEXT NOT NULL,
 imported_at TEXT NOT NULL, source_file TEXT NOT NULL, file_modified_at TEXT NOT NULL,
 provenance TEXT NOT NULL, source_payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hierarchy_nodes (
 snapshot_id INTEGER NOT NULL REFERENCES hierarchy_snapshots(id), node_id INTEGER NOT NULL,
 parent_id INTEGER, sibling_order INTEGER NOT NULL, kind TEXT NOT NULL,
 provider_id TEXT NOT NULL, name TEXT, PRIMARY KEY(snapshot_id,node_id));
'''


def import_tree(source, target, account):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError('Source and database must differ.')
    raw = source.read_bytes()
    found, nodes = normalize(json.loads(raw))
    if found != account:
        raise ValueError('Folder account does not match the requested audit account.')
    # Retain only the hierarchy, never the rest of session.json (history/UI state).
    checksum = hashlib.sha256(json.dumps(nodes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target)) as db, db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and 'hierarchy_snapshots' not in tables:
            raise ValueError('Use a separate hierarchy database, not an audit/catalog database.')
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript(SCHEMA)
        latest = db.execute('SELECT id,checksum FROM hierarchy_snapshots WHERE account_id=? ORDER BY id DESC LIMIT 1', (account,)).fetchone()
        if latest and latest[1] == checksum:
            return latest[0], len(nodes)
        root = json.loads(raw).get('rootlist', json.loads(raw))
        evidence = {k: root[k] for k in ('account_id', 'entries', 'uris') if k in root}
        sid = db.execute('INSERT INTO hierarchy_snapshots(account_id,checksum,imported_at,source_file,file_modified_at,provenance,source_payload) VALUES(?,?,?,?,?,?,?)',
                   (account, checksum, datetime.now(timezone.utc).isoformat(), str(source),
                    datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
                    'Spotifast rootlist import; upstream capture time and completeness unverified',
                    json.dumps(evidence, ensure_ascii=False))).lastrowid
        db.executemany('INSERT OR IGNORE INTO hierarchy_nodes VALUES(?,?,?,?,?,?,?)',
                      [(sid, n['node_id'], n['parent_id'], n['sibling_order'], n['kind'], n['provider_id'], n['name']) for n in nodes])
    return sid, len(nodes)


def latest_tree(target, account):
    target = Path(target)
    if not target.exists():
        return None
    with closing(sqlite3.connect(target.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM hierarchy_snapshots WHERE account_id=? ORDER BY id DESC LIMIT 1', (account,)).fetchone()
        if row is None:
            return None
        return dict(row, nodes=[dict(n) for n in db.execute('SELECT * FROM hierarchy_nodes WHERE snapshot_id=? ORDER BY node_id', (row['id'],))])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('session', type=Path, nargs='?', help='Spotifast session.json; auto-detect on Windows when omitted')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--account', help='Must equal the account_id in your audit run-state.json')
    group.add_argument('--run', type=Path, help='Get the expected account from this audit folder')
    group.add_argument('--latest-run', action='store_true', help='Use the newest audit in the default backup folder')
    p.add_argument('--database', type=Path, default=data_root() / 'hierarchy.sqlite')
    args = p.parse_args()
    try:
        account = args.account
        if args.latest_run:
            candidates = list((data_root() / 'backups').glob('*/library.sqlite'))
            if not candidates:
                raise ValueError('No saved audit found. Supply --run or --account explicitly.')
            args.run = max(candidates, key=lambda path: path.stat().st_mtime).parent
        if args.run:
            with closing(sqlite3.connect((args.run / 'library.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
                account = json.loads(db.execute('SELECT data FROM run_state WHERE id=1').fetchone()[0]).get('account_id')
            if not account:
                raise ValueError('Audit has not verified an account yet.')
        session = args.session
        if session is None:
            base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'paolino'
            candidates = [base / app / 'data/session.json' for app in ('spotifast', 'fastpotify')]
            session = next((path for path in candidates if path.exists()), None)
            if session is None:
                raise ValueError('No Spotifast session.json found. Supply its path explicitly.')
        sid, count = import_tree(session, args.database, account)
        print(f'Saved hierarchy snapshot {sid}: {count} folder/playlist nodes. No Spotify requests made.')
        print(args.database)
    except (ValueError, OSError, sqlite3.Error) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
