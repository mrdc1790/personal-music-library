"""Review possible recording relationships using only saved catalog evidence."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import unicodedata

import library
import recording_review
from storage_paths import data_root
import track_metadata


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def isrc(value):
    return (value or '').strip().replace('-', '').upper()


def placement(row, exported):
    raw = json.loads(row['raw_json'])
    evidence = track_metadata.observed(raw)
    album = evidence['album']
    track = evidence['track']
    names = json.loads(row['artists'])
    ids = raw.get('artist_ids') or [artist.get('id') for artist in evidence['artists']]
    return dict(source=row['source'], playlist_name=row['playlist_name'], position=row['position'],
                source_exported=bool(exported[row['source']]), title=row['title'], artists=names,
                primary_artist_id=ids[0] if ids else None, album=row['album'] or album.get('name'),
                release_id=album.get('id'), release_date=album.get('release_date'),
                release_date_precision=album.get('release_date_precision'),
                duration_ms=row['duration_ms'], explicit=raw.get('explicit', track.get('explicit')),
                isrc=row['isrc'], returned_uri=row['returned_uri'], original_id=row['original_id'],
                playable=bool(row['playable']) if row['playable'] in (0, 1) else None)


def compare_pair(source, candidate, *, shared_identity=False):
    support, conflicts, unknown = [], [], []
    for key in ('isrc', 'title', 'primary_artist_id', 'explicit'):
        left, right = source[key], candidate[key]
        if key == 'isrc':
            left, right = isrc(left), isrc(right)
        if key == 'title':
            left, right = normalized(left), normalized(right)
        if left is None or right is None or left == '' or right == '':
            unknown.append(key)
        elif left == right:
            support.append(key)
        else:
            conflicts.append(key)
    source_names, candidate_names = source['artists'], candidate['artists']
    if source_names and candidate_names and normalized(source_names[0]) and normalized(candidate_names[0]):
        if normalized(source_names[0]) == normalized(candidate_names[0]):
            support.append('primary_artist_name')
        else:
            conflicts.append('primary_artist_name')
    else:
        unknown.append('primary_artist_name')
    durations = (source['duration_ms'], candidate['duration_ms'])
    if all(type(value) is int and value > 0 for value in durations):
        gap = abs(durations[0] - durations[1])
        (support if gap <= 3000 else conflicts).append('duration_ms')
    else:
        gap = None
        unknown.append('duration_ms')
    if not shared_identity and 'isrc' not in support:
        signals = set(support)
        if not {'title', 'duration_ms'} <= signals or not {'primary_artist_id', 'primary_artist_name'} & signals:
            return None
    return dict(support=support, conflicts=conflicts, unknown=unknown, duration_difference_ms=gap)


def report(db, source_snapshot, snapshot, key, limit=50):
    if not 1 <= limit <= 200:
        raise ValueError('Candidate limit must be between 1 and 200.')
    source_rows = library.lookup_identity(db, source_snapshot, key)
    if not source_rows:
        raise ValueError('The source track key is absent from the selected source snapshot.')
    coverage = {}
    for sid in {source_snapshot, snapshot}:
        sources = dict(db.execute('SELECT source,exported FROM playlists WHERE snapshot_id=?', (sid,)))
        coverage[sid] = sources
    source = [placement(row, coverage[source_snapshot]) for row in source_rows]
    titles = {normalized(row['title']) for row in source} - {''}
    codes = {isrc(row['isrc']) for row in source} - {''}
    possible = set()
    for candidate, title, code in db.execute(
            "SELECT track_key,title,isrc FROM items WHERE snapshot_id=? AND missing=0 AND is_local=0 "
            "AND track_key LIKE 'spotify:track:%' AND track_key!=?", (snapshot, key)):
        if normalized(title) in titles or isrc(code) in codes:
            possible.add(candidate)

    # Compare unique metadata observations so repeated placements do not inflate evidence.
    identity_fields = ('title', 'artists', 'primary_artist_id', 'isrc', 'duration_ms', 'explicit')
    source_versions = {json.dumps([row[field] for field in identity_fields]): row for row in source}
    results = []
    for candidate in sorted(possible):
        rows = [placement(row, coverage[snapshot]) for row in library.lookup_identity(db, snapshot, candidate)]
        versions = {json.dumps([row[field] for field in identity_fields]): row for row in rows}
        matches = []
        for before in source_versions.values():
            for after in versions.values():
                match = compare_pair(before, after)
                if match:
                    matches.append(dict(match, source_placement=[before['source'], before['position']],
                                        candidate_placement=[after['source'], after['position']]))
        if not matches:
            continue
        strong = any('isrc' in match['support'] for match in matches)
        contradictory = any(match['conflicts'] for match in matches)
        results.append(dict(track_key=candidate, placements=rows, comparisons=matches,
                            status='conflicting_evidence' if contradictory else 'isrc_candidate' if strong else 'metadata_candidate'))
    rank = {'isrc_candidate': 0, 'metadata_candidate': 1, 'conflicting_evidence': 2}
    results.sort(key=lambda candidate: (rank[candidate['status']], candidate['track_key']))

    snapshots = {sid: dict(db.execute('SELECT id,created_at,status FROM snapshots WHERE id=?', (sid,)).fetchone(),
                           exported_sources=sum(sources.values()), known_sources=len(sources))
                 for sid, sources in coverage.items()}
    return dict(source_key=key, source_snapshot=snapshots[source_snapshot], search_snapshot=snapshots[snapshot],
                reviews=recording_review.reviews(db, key),
                source_placements=source, candidates=results[:limit], total_candidates=len(results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('track_key', help='Exact observed Spotify track URI or local reference')
    parser.add_argument('--db', type=Path, default=data_root() / 'catalog.sqlite')
    parser.add_argument('--snapshot', type=int, help='Snapshot in which to look for candidates')
    parser.add_argument('--source-snapshot', type=int, help='Snapshot containing the input track; defaults to --snapshot')
    parser.add_argument('--output', type=Path, required=True, help='New private JSON report')
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    try:
        with closing(library.connect(args.db)) as db:
            db.execute('BEGIN')
            target = library.snapshot_id(db, args.snapshot)
            source = library.snapshot_id(db, args.source_snapshot) if args.source_snapshot is not None else target
            result = report(db, source, target, args.track_key, args.limit)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(f'Saved {len(result["candidates"])} of {result["total_candidates"]} candidate(s).')


if __name__ == '__main__':
    main()
