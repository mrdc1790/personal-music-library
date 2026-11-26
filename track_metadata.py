"""Read track, release, credit, and placement metadata already saved in an audit."""

import json


TRACK_FIELDS = ('id', 'uri', 'name', 'duration_ms', 'disc_number', 'track_number',
                'explicit', 'popularity', 'is_playable', 'restrictions', 'external_ids', 'external_urls')
ALBUM_FIELDS = ('id', 'uri', 'name', 'album_type', 'total_tracks', 'release_date',
                'release_date_precision', 'label', 'genres', 'external_ids', 'external_urls')
CREDIT_FIELDS = ('id', 'uri', 'name', 'genres', 'external_urls')


def present(value):
    return value is not None and value != '' and value != [] and value != {}


def fields(data, keys):
    return {key: data[key] for key in keys if present(data.get(key))}


def credits(data):
    return [credit for artist in data.get('artists') or []
            if (credit := fields(artist, CREDIT_FIELDS))]


def observed(row):
    entry = row.get('raw') or {}
    track = (entry.get('item') if 'item' in entry else entry.get('track')) or {}
    album = track.get('album') or {}
    return dict(track=fields(track, TRACK_FIELDS), album=fields(album, ALBUM_FIELDS),
                artists=credits(track), album_artists=credits(album),
                added_at=row.get('added_at') or entry.get('added_at'))


def report(db, snapshot, placements=False):
    """Count observed placements with fields and optionally include their evidence."""
    count = 0
    coverage = dict.fromkeys(('album', 'release_date', 'date_added', 'artist_id', 'artist_genres',
                              'album_genres', 'album_label', 'duration', 'isrc', 'popularity',
                              'explicit', 'track_number', 'disc_number'), 0)
    status, captured_at = db.execute(
        'SELECT status, created_at FROM snapshots WHERE id=?', (snapshot,)).fetchone()
    known_sources, exported_sources = db.execute(
        'SELECT count(*), coalesce(sum(exported), 0) FROM playlists WHERE snapshot_id=?', (snapshot,)).fetchone()
    result = dict(snapshot=snapshot, status=status, captured_at=captured_at,
                  known_sources=known_sources, exported_sources=exported_sources, field_placements=coverage)
    if placements:
        result['placements'] = []
    for source, position, key, raw in db.execute(
            'SELECT source, position, track_key, raw_json FROM items WHERE snapshot_id=? ORDER BY source, position',
            (snapshot,)):
        row = json.loads(raw)
        evidence = observed(row)
        album, track, artists = (evidence[k] for k in ('album', 'track', 'artists'))
        count += 1
        values = dict(album=album.get('name'), release_date=album.get('release_date'),
                      date_added=evidence['added_at'], artist_id=any(row.get('artist_ids') or []) or
                      any(artist.get('id') for artist in artists) or None,
                      artist_genres=[artist['genres'] for artist in artists if artist.get('genres')],
                      album_genres=album.get('genres'), album_label=album.get('label'),
                      duration=row.get('duration_ms'), isrc=row.get('isrc'), popularity=track.get('popularity'),
                      explicit=row.get('explicit', track.get('explicit')), track_number=track.get('track_number'),
                      disc_number=track.get('disc_number'))
        for field, value in values.items():
            coverage[field] += present(value)
        if placements:
            result['placements'].append(dict(source=source, position=position, track_key=key,
                                             title=row.get('title'), artist_names=row.get('artists') or [],
                                             duration_ms=row.get('duration_ms'), isrc=row.get('isrc'),
                                             local=bool(row.get('is_local')), **evidence))
    result['observed_placements'] = count
    return result
