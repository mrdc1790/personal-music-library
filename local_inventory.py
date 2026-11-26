"""Local audio inventory, candidate reconciliation, and reviewed file links."""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import unicodedata
from urllib.parse import unquote_plus
import wave

import audio_tags
import library
from storage_paths import data_root


AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus', '.aiff', '.aif', '.wma'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def hash_stream(stream):
    return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(roots):
    """Keep overlapping-root observations; never follow symlinks or junctions."""
    report = dict(version=1, started_at=utc(), roots=[], entries=[])
    for root_index, supplied in enumerate(roots):
        root = Path(os.path.abspath(Path(supplied).expanduser()))
        coverage = dict(root_index=root_index, path=str(root), status='complete',
                        errors=[], skipped=[], observed_files=0)
        report['roots'].append(coverage)

        def error(path, exc):
            coverage['status'] = 'incomplete'
            coverage['errors'].append(dict(path=str(path), error=type(exc).__name__))

        def visit(path):
            try:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    coverage['status'] = 'incomplete'
                    coverage['skipped'].append(dict(path=str(path), reason='link_or_reparse_point'))
                    return
                if stat.S_ISDIR(info.st_mode):
                    with os.scandir(path) as children:
                        names = sorted(child.name for child in children)
                    for name in names:
                        visit(path / name)
                elif stat.S_ISREG(info.st_mode) and path.suffix.casefold() in AUDIO_EXTENSIONS:
                    entry = dict(root_index=root_index, path=str(path), size_bytes=info.st_size,
                                 mtime_ns=info.st_mtime_ns, filename_title=path.stem,
                                 status='complete', sha256=None, duration_ms=None)
                    report['entries'].append(entry)
                    coverage['observed_files'] += 1
                    try:
                        with path.open('rb') as stream:
                            entry['sha256'] = hash_stream(stream)
                            if path.suffix.casefold() == '.mp3':
                                stream.seek(0)
                                try:
                                    entry['tags'] = audio_tags.mp3_tags(stream)
                                except ValueError as exc:
                                    entry['metadata_error'] = str(exc) if not isinstance(exc, UnicodeError) else 'Invalid ID3 text'
                        if path.suffix.casefold() == '.wav':
                            try:
                                with wave.open(str(path), 'rb') as audio:
                                    entry['duration_ms'] = round(audio.getnframes() * 1000 / audio.getframerate())
                            except (OSError, EOFError, wave.Error, ZeroDivisionError) as exc:
                                entry['metadata_error'] = type(exc).__name__
                        after = path.stat()
                        if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                            raise OSError('File changed during read')
                    except OSError as exc:
                        entry['status'] = 'incomplete'
                        entry['sha256'] = None
                        error(path, exc)
            except OSError as exc:
                error(path, exc)

        try:
            if not stat.S_ISDIR(root.lstat().st_mode):
                raise NotADirectoryError(str(root))
            visit(root)
        except OSError as exc:
            error(root, exc)
    report['status'] = 'complete' if report['roots'] and all(
        r['status'] == 'complete' for r in report['roots']) else 'incomplete'
    hashes = defaultdict(set)
    for entry in report['entries']:
        if entry['sha256']:
            hashes[entry['sha256']].add(entry['path'])
    report['byte_duplicates'] = [dict(sha256=digest, paths=sorted(paths))
                                 for digest, paths in sorted(hashes.items()) if len(paths) > 1]
    report['distinct_paths'] = len({e['path'] for e in report['entries']})
    report['finished_at'] = utc()
    return report


def save_inventory(database, scan):
    """Append one dated scan to a dedicated SQLite store."""
    database = Path(database).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        tables = {name for (name,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and ('local_inventory_scans' not in tables
                       or tables - {'local_inventory_scans', 'local_file_reviews'}):
            raise ValueError('Use a separate SQLite file for local inventory, not an audit or catalog.')
        db.execute("""CREATE TABLE IF NOT EXISTS local_inventory_scans (
            id INTEGER PRIMARY KEY, finished_at TEXT NOT NULL, evidence_json TEXT NOT NULL
        )""")
        return db.execute('INSERT INTO local_inventory_scans(finished_at,evidence_json) VALUES (?,?)',
                          (scan['finished_at'], json.dumps(scan, ensure_ascii=False))).lastrowid


def read_scan(db, scan_id):
    if scan_id is None:
        row = db.execute('SELECT id,evidence_json FROM local_inventory_scans ORDER BY id DESC LIMIT 1').fetchone()
    else:
        row = db.execute('SELECT id,evidence_json FROM local_inventory_scans WHERE id=?', (scan_id,)).fetchone()
    if row is None:
        raise ValueError('Local inventory scan not found.')
    return dict(json.loads(row[1]), scan_id=row[0])


def read_confirmations(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='local_file_reviews' AND type='table'").fetchone():
        return {}
    return {uri: dict(sha256=digest, confirmed_at=when, scan_id=scan_id, path=path)
            for uri, digest, when, scan_id, path in db.execute("""
                SELECT uri,sha256,reviewed_at,scan_id,path FROM local_file_reviews
                WHERE id IN (SELECT MAX(id) FROM local_file_reviews GROUP BY uri) AND sha256 IS NOT NULL
            """)}


def load_inventory(database, scan_id=None):
    """Read a saved scan and current confirmations in one consistent transaction."""
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        return dict(read_scan(db, scan_id), confirmations=read_confirmations(db))


def review_file(database, uri, path=None, scan_id=None):
    """Confirm a file observed in a scan, or clear a confirmation while retaining history."""
    parts = uri.split(':')
    if len(parts) != 6 or parts[:2] != ['spotify', 'local'] or not parts[4] or not parts[5].isdecimal():
        raise ValueError('Use the full spotify:local: URI shown in the playlist preview.')
    uri_db = Path(database).resolve().as_uri() + '?mode=rw'
    digest = None
    if path is not None:
        scan = load_inventory(database, scan_id)
        scan_id = scan['scan_id']
        path = Path(os.path.abspath(Path(path).expanduser()))
        observed = {entry['sha256'] for entry in scan['entries']
                    if os.path.normcase(entry['path']) == os.path.normcase(str(path))
                    and entry['status'] == 'complete' and entry.get('sha256')}
        if len(observed) != 1:
            raise ValueError('Choose a readable file with one observed hash in the selected inventory scan.')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Choose a regular audio file from the selected inventory scan.')
        with path.open('rb') as stream:
            digest = hash_stream(stream)
        if digest not in observed:
            raise ValueError('The file bytes changed since the inventory scan. Scan again before confirming.')
    with closing(sqlite3.connect(uri_db, uri=True)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if path is None and uri not in read_confirmations(db):
            raise ValueError('This URI has no active file confirmation.')
        db.execute("""CREATE TABLE IF NOT EXISTS local_file_reviews (
            id INTEGER PRIMARY KEY, uri TEXT NOT NULL, sha256 TEXT, reviewed_at TEXT NOT NULL,
            scan_id INTEGER REFERENCES local_inventory_scans(id), path TEXT
        )""")
        db.execute('INSERT INTO local_file_reviews(uri,sha256,reviewed_at,scan_id,path) VALUES (?,?,?,?,?)',
                   (uri, digest, utc(), scan_id, str(path) if path is not None else None))


def normalized(value):
    return unicodedata.normalize('NFC', value or '').strip().casefold()


def reference_album(uri):
    parts = (uri or '').split(':')
    return unquote_plus(parts[3]) if len(parts) == 6 and parts[:2] == ['spotify', 'local'] else None


def inventory_index(scan):
    if (not isinstance(scan, dict) or scan.get('version') != 1
            or not isinstance(scan.get('entries'), list)
            or not isinstance(scan.get('roots'), list) or not scan['roots']):
        raise ValueError('Expected a local inventory report with at least one scanned root.')
    titles = defaultdict(list)
    hashes = defaultdict(set)
    for entry in scan['entries']:
        if entry['status'] == 'complete':
            names = {normalized(entry['filename_title']), normalized(entry.get('tags', {}).get('title'))}
            for name in names - {''}:
                titles[name].append(entry)
            if entry.get('sha256'):
                hashes[entry['sha256']].add(entry['path'])
    return titles, hashes, scan.get('confirmations', {})


def file_candidates(index, title, duration_ms, *, uri=None, artists=(), album=None):
    titles, hashes, confirmations = index
    candidates = {}
    contradictions = {}
    confirmation = confirmations.get(uri)
    if confirmation:
        confirmation = dict(confirmation, paths=sorted(hashes.get(confirmation['sha256'], ())))
    artist_names = {normalized(artist) for artist in artists} - {''}
    title = normalized(title)
    album = normalized(album or reference_album(uri))
    for entry in titles.get(title, []):
        path = entry['path']
        duration = entry['duration_ms']
        tags = entry.get('tags', {})
        tag_title = normalized(tags.get('title'))
        tag_artist = normalized(tags.get('artist'))
        tag_album = normalized(tags.get('album'))
        reasons = []
        if tag_title and tag_title != title:
            reasons.append('tag_title_differs')
        if tag_artist and artist_names and tag_artist not in artist_names:
            reasons.append('tag_artist_differs')
        if tag_album and album and tag_album != album:
            reasons.append('tag_album_differs')
        if duration is not None and duration_ms is not None and abs(duration - duration_ms) > 2000:
            reasons.append('duration_differs')
        if reasons:
            for reason in reasons:
                contradictions[path, reason] = dict(path=path, reason=reason)
        else:
            evidence = 'audio_tags' if tag_title else 'filename_title'
            candidates[path] = dict(path=path, evidence=evidence, duration_ms=duration)
    return list(candidates.values()), list(contradictions.values()), confirmation


def reconcile(db, sid, scan, confirmations=None):
    """Compare observed metadata and explicitly reviewed byte hashes."""
    sid = library.snapshot_id(db, sid)
    snapshot = db.execute('SELECT status,created_at FROM snapshots WHERE id=?', (sid,)).fetchone()
    coverage = library.sources(db, sid)
    source_coverage = {s['source']: bool(s['exported']) for s in coverage}
    spotify_complete = snapshot['status'].startswith('completed') and all(source_coverage.values())
    files = inventory_index(dict(scan, confirmations=confirmations or {}))
    results = []
    observed = set()
    for row in library.rows(db, sid):
        if not row['is_local']:
            continue
        title = None if row['missing'] else row['title']
        artists = json.loads(row['artists'])
        candidates, contradictions, confirmation = file_candidates(
            files, title, row['duration_ms'], uri=row['returned_uri'], artists=artists, album=row['album'])
        observed.update(candidate['path'] for candidate in candidates)
        complete = scan['status'] == 'complete' and source_coverage[row['source']]
        if confirmation and confirmation['paths']:
            status = 'confirmed'
            observed.update(confirmation['paths'])
        elif row['missing'] or not row['title']:
            status = 'incomplete'
        elif len(candidates) > 1:
            status = 'ambiguous'
        elif candidates:
            status = 'likely'
        else:
            status = 'unmatched' if complete else 'incomplete'
        results.append(dict(source=row['source'], position=row['position'],
                            returned_uri=row['returned_uri'], title=row['title'],
                            artists=artists, duration_ms=row['duration_ms'],
                            source_exported=source_coverage[row['source']],
                            comparison_complete=complete, status=status,
                            candidates=candidates, contradictions=contradictions, confirmation=confirmation))
    return dict(snapshot_id=sid, snapshot_created_at=snapshot['created_at'],
                snapshot_status=snapshot['status'], spotify_coverage=coverage,
                spotify_coverage_complete=spotify_complete, local_occurrences=len(results),
                distinct_local_uris=len({r['returned_uri'] for r in results if r['returned_uri']}),
                references=results,
                files_without_observed_candidate=[dict(path=path, status=(
                    'unmatched' if spotify_complete and scan['status'] == 'complete' else 'incomplete'))
                    for path in sorted({e['path'] for e in scan['entries']} - observed)],
                limitations='Tag and filename candidates require review. Confirmed paths carry an explicit review '
                             'and matching file bytes. '
                             'Coverage applies to chosen roots and captured API sources, never device playback.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='*', type=Path)
    parser.add_argument('--db', type=Path, help='Optional existing catalog, opened read-only')
    parser.add_argument('--snapshot', type=int)
    parser.add_argument('--inventory-db', type=Path, help='SQLite inventory for saving scans and file reviews')
    parser.add_argument('--output', type=Path)
    review = parser.add_mutually_exclusive_group()
    review.add_argument('--confirm', nargs=2, metavar=('LOCAL_URI', 'FILE'), help='Confirm the reviewed URI and file')
    review.add_argument('--clear-confirmation', metavar='LOCAL_URI', help='Clear an active file confirmation')
    parser.add_argument('--inventory-scan', type=int, help='Use this stored scan for --confirm; defaults to latest')
    args = parser.parse_args(argv)
    if args.confirm or args.clear_confirmation:
        if not args.inventory_db or args.roots or args.db or args.snapshot is not None or args.output:
            parser.error('File reviews require --inventory-db and run separately from scanning.')
        if args.inventory_scan is not None and not args.confirm:
            parser.error('--inventory-scan requires --confirm')
        try:
            if args.confirm:
                review_file(args.inventory_db, *args.confirm, scan_id=args.inventory_scan)
            else:
                review_file(args.inventory_db, args.clear_confirmation)
        except (OSError, ValueError, sqlite3.Error) as exc:
            parser.exit(1, f'Could not save file review: {exc}\n')
        print('Local file review saved.')
        return 0
    if not args.roots or args.inventory_scan is not None:
        parser.error('Provide at least one audio root to scan. --inventory-scan applies only to --confirm.')
    if args.snapshot is not None and args.db is None:
        parser.error('--snapshot requires --db')
    report = inventory(args.roots)
    if args.db is not None:
        confirmations = None
        if args.inventory_db is not None and args.inventory_db.exists():
            database_uri = args.inventory_db.resolve().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(database_uri, uri=True)) as evidence:
                confirmations = read_confirmations(evidence)
        with closing(library.connect(args.db)) as db:
            report['reconciliation'] = reconcile(db, args.snapshot, report, confirmations)
    output = args.output or data_root() / 'inventories' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    if args.inventory_db is not None and args.inventory_db.resolve() == output.resolve():
        parser.error('--inventory-db and --output must be different files')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve earlier reports and refuse to overwrite any source file or catalog.
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if args.inventory_db is not None:
        scan_id = save_inventory(args.inventory_db, report)
        print(f'Local inventory report and SQLite scan {scan_id} saved.')
    else:
        print('Local inventory report saved.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
