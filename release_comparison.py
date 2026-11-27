"""Compare tracks observed on two saved releases without matching by ordinal."""

import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

import library
import recording_candidates
from storage_paths import data_root


def positive_integer(value):
    return value if type(value) is int and value > 0 else None


def release(db, snapshot, release_id):
    if not re.fullmatch(r'[A-Za-z0-9]{22}', release_id):
        raise ValueError('Use an exact 22-character saved Spotify release ID.')
    snapshot_data = dict(db.execute('SELECT id,created_at,status FROM snapshots WHERE id=?', (snapshot,)).fetchone())
    coverage = dict(db.execute('SELECT source,exported FROM playlists WHERE snapshot_id=?', (snapshot,)))
    members, totals, names = {}, set(), set()
    for row in db.execute("SELECT i.*,p.name AS playlist_name FROM items i JOIN playlists p USING(snapshot_id,source) "
                          "WHERE i.snapshot_id=? AND i.identity_basis!='unidentified' AND i.is_local=0 "
                          "AND i.track_key LIKE 'spotify:track:%' ORDER BY i.source,i.position", (snapshot,)):
        raw = json.loads(row['raw_json']).get('raw') or {}
        track = (raw.get('item') if 'item' in raw else raw.get('track')) or {}
        album = track.get('album') or {}
        if album.get('id') != release_id:
            continue
        key, disc, number = row['track_key'], positive_integer(track.get('disc_number')), positive_integer(track.get('track_number'))
        group = members.setdefault((key, disc, number), dict(track_key=key, disc=disc, track=number, placements=[]))
        group['placements'].append(recording_candidates.placement(row, coverage))
        if total := positive_integer(album.get('total_tracks')):
            totals.add(total)
        name = album.get('name')
        if isinstance(name, str) and name:
            names.add(name)
    if not members:
        raise ValueError('A selected release has no observed track placements in its snapshot.')
    tracks = sorted(members.values(), key=lambda row: (row['disc'] is None, row['disc'] or 0,
                                                       row['track'] is None, row['track'] or 0, row['track_key']))
    return dict(release_id=release_id, observed_names=sorted(names), snapshot=snapshot_data,
                known_sources=len(coverage), exported_sources=sum(coverage.values()),
                reported_track_totals=sorted(totals), observed_track_entries=len(tracks), tracks=tracks)


def metadata_pairs(left, right, shared_key):
    fields = ('title', 'artists', 'primary_artist_id', 'isrc', 'duration_ms', 'explicit')
    left_versions, right_versions = (
        {json.dumps([row[field] for field in fields]): row for row in track['placements']}.values()
        for track in (left, right))
    matches = {}
    for before in left_versions:
        for after in right_versions:
            if match := recording_candidates.compare_pair(before, after, shared_identity=shared_key):
                matches[json.dumps(match)] = match
    return list(matches.values())


def compare(db, left_snapshot, left_id, right_snapshot, right_id):
    first, second = (release(db, sid, key) for sid, key in ((left_snapshot, left_id), (right_snapshot, right_id)))
    pairs = []
    for left, a in enumerate(first['tracks']):
        for right, b in enumerate(second['tracks']):
            shared_key = a['track_key'] == b['track_key']
            evidence = metadata_pairs(a, b, shared_key)
            if shared_key or evidence:
                pairs.append(dict(left=left, right=right, shared_observed_key=shared_key, evidence=evidence,
                                  conflicting_metadata=any(pair['conflicts'] for pair in evidence)))
    a_options = Counter(pair['left'] for pair in pairs if not pair['conflicting_metadata'])
    b_options = Counter(pair['right'] for pair in pairs if not pair['conflicting_metadata'])
    for pair in pairs:
        pair['status'] = ('conflicting_metadata' if pair['conflicting_metadata'] else
                          'one_to_one_candidate' if a_options[pair['left']] == b_options[pair['right']] == 1 else
                          'multiple_candidates')
    for side, record, options in (('left', first, a_options), ('right', second, b_options)):
        observed = Counter(pair[side] for pair in pairs)
        for index, track in enumerate(record['tracks']):
            track['compatible_candidates'] = options[index]
            track['observed_candidates'] = observed[index]
    return dict(format_version=1, left=first, right=second, pairs=pairs,
                left_without_compatible_candidate=[i for i in range(len(first['tracks'])) if not a_options[i]],
                right_without_compatible_candidate=[i for i in range(len(second['tracks'])) if not b_options[i]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left_release')
    parser.add_argument('right_release')
    parser.add_argument('--db', type=Path, default=data_root() / 'catalog.sqlite')
    parser.add_argument('--left-snapshot', type=int)
    parser.add_argument('--right-snapshot', type=int)
    parser.add_argument('--output', type=Path, required=True, help='New private JSON report')
    args = parser.parse_args()
    try:
        with closing(library.connect(args.db)) as db:
            db.execute('BEGIN')
            result = compare(db, library.snapshot_id(db, args.left_snapshot), args.left_release,
                             library.snapshot_id(db, args.right_snapshot), args.right_release)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(f'Saved evidence for {len(result["pairs"])} release-track pair(s).')


if __name__ == '__main__':
    main()
