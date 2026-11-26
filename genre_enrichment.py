"""Cache MusicBrainz recording genres for saved catalog evidence."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing, nullcontext
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

import library
from resumable_audit import run_lock
from storage_paths import data_root


CACHE = data_root() / 'musicbrainz' / 'recording-genres.sqlite'
APPLICATION_ID = 0x504D4C47
MAX_AGE = timedelta(days=90)
USER_AGENT = 'PersonalMusicLibrary/0.1 (https://github.com/mrdc1790/personal-music-library)'


def connect(path, write=False):
    path = Path(path).resolve()
    db = sqlite3.connect(path.as_uri() + ('?mode=rwc' if write else '?mode=ro'), uri=True)
    try:
        application = db.execute('PRAGMA application_id').fetchone()[0]
        if write and application == 0 and not db.execute('SELECT 1 FROM sqlite_master').fetchone():
            with db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('CREATE TABLE responses (entity TEXT, identifier TEXT, fetched_at TEXT, payload TEXT, '
                           'PRIMARY KEY (entity, identifier))')
                db.execute(f'PRAGMA application_id={APPLICATION_ID}')
        elif application != APPLICATION_ID:
            raise ValueError('Expected a MusicBrainz genre cache. Choose a separate cache file.')
    except BaseException:
        db.close()
        raise
    return db


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def reference(row):
    """Use the ISRC and descriptive fields from the same observed track payload."""
    if row.get('missing') or row.get('is_local'):
        return None
    isrc = (row.get('isrc') or '').replace('-', '').strip().upper()
    title = normalize(row.get('title'))
    artists = row.get('artists') or []
    primary_artist = normalize(artists[0]) if artists else ''
    duration = row.get('duration_ms')
    if (re.fullmatch(r'[A-Z]{2}[A-Z0-9]{3}[0-9]{7}', isrc) and title and primary_artist
            and isinstance(duration, int) and duration > 0):
        return isrc, title, primary_artist, duration
    return None


def lookup(entity, identifier):
    include = 'artist-credits' if entity == 'isrc' else 'genres'
    request = Request(f'https://musicbrainz.org/ws/2/{entity}/{identifier}?inc={include}&fmt=json',
                      headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return [] if entity == 'isrc' else None
        retry = exc.headers.get('Retry-After')
        wait = f' Retry-After: {retry}.' if retry else ''
        raise ValueError(f'MusicBrainz returned HTTP {exc.code}.{wait} Saved lookups can be reused.') from None
    except (URLError, TimeoutError):
        raise ValueError('MusicBrainz request failed. Saved lookups can be reused.') from None
    if isinstance(payload, dict):
        if entity == 'recording' and payload.get('id') == identifier:
            tags = payload.get('genres')
            if isinstance(tags, list) and all(isinstance(tag, dict) for tag in tags):
                return tags
        recordings = payload.get('recordings')
        if entity == 'isrc' and isinstance(recordings, list) and all(isinstance(row, dict) for row in recordings):
            return recordings
    raise ValueError('Unexpected MusicBrainz response. Saved lookups can be reused.')


def cache_reader(db):
    @lru_cache(maxsize=None)
    def read(entity, identifier):
        row = db.execute('SELECT fetched_at, payload FROM responses WHERE entity=? AND identifier=?',
                         (entity, identifier)).fetchone() if db is not None else None
        return (row[0], json.loads(row[1])) if row else None
    return read


def match(ref, entry):
    if ref is None:
        return dict(status='ineligible')
    if entry is None:
        return dict(status='pending')
    fetched_at, recordings = entry
    result = dict(fetched_at=fetched_at)
    if len(recordings) != 1:
        return dict(result, status='ambiguous' if recordings else 'unmatched')
    recording = recordings[0]
    _, title, artist, duration = ref
    credits = recording.get('artist-credit') or []
    primary = credits[0] if credits else {}
    names = {normalize(primary.get('name')), normalize((primary.get('artist') or {}).get('name'))}
    length = recording.get('length')
    if (normalize(recording.get('title')) != title or artist not in names
            or not isinstance(length, int) or length <= 0 or abs(length - duration) > 3000):
        return dict(result, status='mismatch')
    try:
        recording_id = str(UUID(recording.get('id') or ''))
    except ValueError:
        return dict(result, status='mismatch')
    return dict(result, status='genre_pending', recording_id=recording_id)


def observation(ref, read):
    result = match(ref, read('isrc', ref[0]) if ref else None)
    recording_id = result.get('recording_id')
    entry = read('recording', recording_id) if recording_id else None
    if entry is None:
        return result
    fetched_at, tags = entry
    if tags is None:
        return dict(result, status='recording_unavailable', fetched_at=fetched_at)
    genres = sorted({tag['name'] for tag in tags if tag.get('name')}, key=str.casefold)
    return dict(result, status='matched' if genres else 'no_genres', fetched_at=fetched_at, genres=genres)


def snapshot_references(db, snapshot, selected):
    exported = {row['source'] for row in library.sources(db, snapshot) if row['exported']}
    if selected and set(selected) - exported:
        raise ValueError('Select only fully exported playlists from this snapshot.')
    allowed = selected or exported
    return dict.fromkeys(
        reference(json.loads(raw))
        for source, raw in db.execute(
            'SELECT source, raw_json FROM items WHERE snapshot_id=? ORDER BY source, position', (snapshot,))
        if source in allowed
    )


def enrich(db, references, limit, fetch=lookup):
    cutoff = datetime.now(timezone.utc) - MAX_AGE
    by_isrc = defaultdict(dict)
    for ref in references:
        if ref is not None:
            by_isrc[ref[0]][ref] = None
    read = cache_reader(db)
    updated = {}
    requested = 0
    last = db.execute('SELECT MAX(fetched_at) FROM responses').fetchone()[0] if limit else None

    def read_updated(entity, identifier):
        key = (entity, identifier)
        return updated[key] if key in updated else read(*key)

    def refresh(entity, identifier):
        nonlocal last, requested
        entry = read_updated(entity, identifier)
        if requested == limit or (entry and datetime.fromisoformat(entry[0]) >= cutoff):
            return entry
        if last:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            time.sleep(max(0, 1.05 - elapsed))
        payload = fetch(entity, identifier)
        last = datetime.now(timezone.utc).isoformat()
        with db:
            db.execute('INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?)',
                       (entity, identifier, last, json.dumps(payload, ensure_ascii=False)))
        updated[(entity, identifier)] = (last, payload)
        requested += 1
        return last, payload

    for isrc, refs in by_isrc.items():
        if requested == limit:
            break
        entry = refresh('isrc', isrc)
        for ref in refs:
            recording_id = match(ref, entry).get('recording_id')
            if recording_id:
                refresh('recording', recording_id)
    counts = Counter(observation(ref, read_updated)['status'] for refs in by_isrc.values() for ref in refs)
    return dict(requests=requested, eligible_isrcs=len(by_isrc), eligible_observations=sum(counts.values()),
                coverage=dict(sorted(counts.items())))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=data_root() / 'catalog.sqlite')
    parser.add_argument('--snapshot', required=True, type=int)
    parser.add_argument('--playlist', action='append', help='Exported source ID. Repeat to restrict the pass.')
    parser.add_argument('--cache', type=Path, default=CACHE)
    parser.add_argument('--fetch', action='store_true', help='Send eligible public ISRCs to MusicBrainz.')
    parser.add_argument('--limit', type=int, default=20, help='Maximum new requests per pass (1–100).')
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error('--limit must be from 1 to 100.')
    try:
        with closing(library.connect(args.db)) as db:
            snapshot = library.snapshot_id(db, args.snapshot)
            references = snapshot_references(db, snapshot, set(args.playlist or []))
        cache = args.cache.resolve()
        lock_folder = cache.parent / '.musicbrainz-lock'
        if args.fetch:
            lock_folder.mkdir(parents=True, exist_ok=True)
        lock = run_lock(lock_folder) if args.fetch else nullcontext()
        with lock:
            connection = closing(connect(cache, write=args.fetch)) if args.fetch or cache.exists() else nullcontext()
            with connection as db:
                result = enrich(db, references, args.limit if args.fetch else 0)
        print(json.dumps(dict(snapshot=snapshot, **result), indent=2))
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(1, f'{exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
