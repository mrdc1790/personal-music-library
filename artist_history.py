"""Import followed-artist evidence and compare complete observations offline."""

from collections import defaultdict
import hashlib
import json
import re

from stream_counts import utc_timestamp


SCHEMA = """
CREATE TABLE IF NOT EXISTS artist_follow_captures (
 id INTEGER PRIMARY KEY, account_id TEXT NOT NULL, captured_at TEXT NOT NULL,
 complete INTEGER NOT NULL CHECK(complete IN (0,1)), checksum TEXT NOT NULL UNIQUE, raw_json TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_complete_artist_capture_per_time
 ON artist_follow_captures(account_id,captured_at) WHERE complete=1;
"""


def import_capture(db, document, account, complete):
    if (not isinstance(document, dict) or type(document.get('schema_version')) is not int
            or document['schema_version'] != 1 or not isinstance(document.get('artists'), list)):
        raise ValueError('Expected a version 1 followed-artist JSON capture.')
    if 'account_id' in document and document['account_id'] != account:
        raise ValueError('The capture account does not match the asserted account.')
    captured_at = utc_timestamp(document.get('captured_at'))
    seen = set()
    for artist in document['artists']:
        if not isinstance(artist, dict):
            raise ValueError('Expected an object for each observed artist.')
        identifier, name, genres = (artist.get(field) for field in ('spotify_id', 'name', 'genres'))
        if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9]{22}', identifier)
                or identifier in seen or not isinstance(name, str) or not name.strip()
                or (genres is not None and (not isinstance(genres, list)
                                            or any(not isinstance(genre, str) for genre in genres)))):
            raise ValueError('Invalid or duplicate artist evidence.')
        seen.add(identifier)
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True)
    canonical = json.dumps([account, bool(complete), captured_at, document['artists']],
                           ensure_ascii=False, sort_keys=True)
    checksum = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    with db:
        db.execute('BEGIN IMMEDIATE')
        if {row[0] for row in db.execute('SELECT DISTINCT account_id FROM snapshots')} != {account}:
            raise ValueError('The asserted account does not match this catalog.')
        previous = db.execute('SELECT id FROM artist_follow_captures WHERE checksum=?', (checksum,)).fetchone()
        if previous:
            return dict(capture_id=previous[0], artists=len(seen), added=False)
        if complete and db.execute('SELECT 1 FROM artist_follow_captures '
                                   'WHERE account_id=? AND captured_at=? AND complete=1',
                                   (account, captured_at)).fetchone():
            raise ValueError('A different complete artist capture already exists at that time.')
        capture = db.execute('INSERT INTO artist_follow_captures(account_id,captured_at,complete,checksum,raw_json) '
                             'VALUES (?,?,?,?,?)', (account, captured_at, int(complete), checksum, raw)).lastrowid
    return dict(capture_id=capture, artists=len(seen), added=True)


def follow_history(db, account):
    records, appearances, transitions = [], {}, []
    confirmed = set()
    previously_confirmed = set()
    previous = None
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='artist_follow_captures'").fetchone():
        return records, appearances, transitions, previous
    for capture, at, complete, raw in db.execute(
            'SELECT id,captured_at,complete,raw_json FROM artist_follow_captures WHERE account_id=? '
            'ORDER BY captured_at,complete,id', (account,)):
        artists = json.loads(raw)['artists']
        records.append(dict(capture_id=capture, captured_at=at, complete=bool(complete), observed_artists=len(artists)))
        current = set()
        for rank, artist in enumerate(artists, 1):
            key = artist['spotify_id']
            current.add(key)
            item = appearances.setdefault(key, dict(spotify_id=key, first_observed_at=at,
                                                     last_complete_presence=None, observed_refollows=0))
            item.update(name=artist['name'], raw_genres=artist.get('genres'), last_observed_at=at,
                        last_capture_id=capture, last_capture_rank=rank)
            if complete:
                item['last_complete_presence'] = at
        if complete:
            if previous is not None:
                for key in sorted(current ^ confirmed):
                    if key not in current:
                        kind = 'unfollowed'
                    elif key in previously_confirmed:
                        kind = 'refollowed'
                        appearances[key]['observed_refollows'] += 1
                    else:
                        kind = 'followed'
                    transitions.append(dict(spotify_id=key, change=kind, after=previous, observed_at=at))
            previous = at
            previously_confirmed.update(current)
            confirmed = current
    for key, item in appearances.items():
        item['latest_complete_state'] = ('followed' if key in confirmed else 'unfollowed') if (
            item['last_complete_presence'] is not None) else 'unknown'
    return records, appearances, transitions, previous


def report(db, snapshot, term=''):
    at, account = db.execute('SELECT created_at,account_id FROM snapshots WHERE id=?', (snapshot,)).fetchone()
    records, artists, transitions, complete = follow_history(db, account)
    identifier = term.strip()
    term = identifier.casefold()
    selected = {key for key, artist in artists.items() if not term or term in artist['name'].casefold() or identifier == key}
    sources = {source: bool(exported) for source, exported in db.execute(
        'SELECT source,exported FROM playlists WHERE snapshot_id=?', (snapshot,))}
    placements = defaultdict(lambda: dict(playlists=set(), tracks=set(), liked_tracks=set(), all_credits=0, primary_credits=0))
    observed_rows = db.execute("SELECT source,track_key,raw_json FROM items WHERE snapshot_id=? "
                               "AND missing=0 AND identity_basis!='unidentified'", (snapshot,)) if selected else ()
    for source, track_key, raw in observed_rows:
        evidence = json.loads(raw)
        ids = evidence.get('artist_ids')
        if not ids:
            entry = evidence.get('raw') or {}
            track = (entry.get('item') if 'item' in entry else entry.get('track')) or {}
            ids = [artist.get('id') for artist in track.get('artists') or ()]
        for key in {key for key in ids if isinstance(key, str) and key in selected}:
            details = placements[key]
            details['tracks'].add(track_key)
            details['all_credits'] += 1
            details['primary_credits'] += key == ids[0]
            if source == 'liked':
                details['liked_tracks'].add(track_key)
            else:
                details['playlists'].add(source)
    rows = []
    for key in sorted(selected, key=lambda identity: (artists[identity]['name'].casefold(), identity)):
        detail = placements[key]
        rows.append(dict(artists[key], observed_primary_placements=detail['primary_credits'],
                         observed_all_credit_placements=detail['all_credits'], observed_tracks=len(detail['tracks']),
                         observed_playlist_ids=sorted(detail['playlists']), observed_liked_tracks=len(detail['liked_tracks'])))
    return dict(snapshot=snapshot, snapshot_captured_at=at, exported_sources=sum(sources.values()),
                known_sources=len(sources), liked_exported=sources.get('liked', False),
                follow_captures=records, latest_complete_follow_capture=complete,
                transitions=[row for row in transitions if row['spotify_id'] in selected], artists=rows)
