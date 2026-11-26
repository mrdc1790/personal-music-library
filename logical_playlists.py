"""Account-scoped playlist groups built from saved Spotify playlist IDs."""

import re


SCHEMA = """
CREATE TABLE IF NOT EXISTS logical_collections (
 collection_id TEXT PRIMARY KEY, name TEXT NOT NULL, account_id TEXT NOT NULL, active_playlist TEXT);
CREATE TABLE IF NOT EXISTS logical_members (
 collection_id TEXT NOT NULL REFERENCES logical_collections(collection_id) ON DELETE CASCADE,
 position INTEGER NOT NULL, playlist_id TEXT NOT NULL,
 PRIMARY KEY(collection_id,position), UNIQUE(collection_id,playlist_id));
"""


def save(db, collection_id, name, members, active=None):
    if (not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', collection_id) or not name.strip()
            or not members or len(set(members)) != len(members) or 'liked' in members):
        raise ValueError('Supply a collection ID, a name, and distinct Spotify playlist IDs in order.')
    if active is not None and active not in members:
        raise ValueError('The active volume must be a member of this collection.')
    with db:
        db.execute('BEGIN IMMEDIATE')
        accounts = db.execute('SELECT DISTINCT account_id FROM snapshots').fetchall()
        if len(accounts) != 1:
            raise ValueError('Import playlist evidence for one account before saving a collection.')
        for playlist in members:
            if not db.execute('SELECT 1 FROM playlists WHERE source=? LIMIT 1', (playlist,)).fetchone():
                raise ValueError('Every playlist must be known to the catalog. Import its capture first.')
        db.execute('INSERT INTO logical_collections VALUES (?,?,?,?) ON CONFLICT(collection_id) DO UPDATE SET '
                   'name=excluded.name, account_id=excluded.account_id, active_playlist=excluded.active_playlist',
                   (collection_id, name.strip(), accounts[0][0], active))
        db.execute('DELETE FROM logical_members WHERE collection_id=?', (collection_id,))
        db.executemany('INSERT INTO logical_members VALUES (?,?,?)',
                       ((collection_id, position, playlist) for position, playlist in enumerate(members)))
    return dict(collection_id=collection_id, members=len(members))


def definitions(db, account):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='logical_collections'").fetchone():
        return {}
    groups = {}
    for row in db.execute('SELECT c.collection_id,c.name,c.active_playlist,m.playlist_id '
                          'FROM logical_collections c JOIN logical_members m USING(collection_id) '
                          'WHERE c.account_id=? ORDER BY c.name,c.collection_id,m.position', (account,)):
        key, name, active, playlist = row
        group = groups.setdefault(key, dict(collection_id=key, name=name, active_playlist=active, members=[]))
        group['members'].append(playlist)
    return groups


def describe(group, sources):
    members = []
    for playlist in group['members']:
        source = sources.get(playlist)
        members.append(dict(playlist_id=playlist, name=source['name'] if source else None,
                            coverage=('complete' if source['exported'] else 'partial') if source else 'absent',
                            placements=source['occurrences'] if source else None))
    return dict(group, members=members, complete=all(member['coverage'] == 'complete' for member in members),
                observed_placements=sum(member['placements'] or 0 for member in members))


def reports(db, sid, groups, sources):
    names = {source['source']: source for source in sources}
    result = []
    for group in groups.values():
        report = describe(group, names)
        known = [member['playlist_id'] for member in report['members'] if member['coverage'] != 'absent']
        placeholders = ','.join('?' for _ in known)
        if known:
            report['observed_identities'] = db.execute(
                f"SELECT COUNT(DISTINCT track_key) FROM items WHERE snapshot_id=? AND source IN ({placeholders}) "
                "AND identity_basis!='unidentified'", (sid, *known)).fetchone()[0]
        else:
            report['observed_identities'] = 0
        result.append(report)
    return result
