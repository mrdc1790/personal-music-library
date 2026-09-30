"""Read-only local audio inventory and candidate reconciliation; no Spotify access."""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import wave

import library
from storage_paths import data_root


AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus', '.aiff', '.aif', '.wma'}


def utc():
    return datetime.now(timezone.utc).isoformat()


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
                        digest = hashlib.sha256()
                        with path.open('rb') as stream:
                            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                                digest.update(chunk)
                        entry['sha256'] = digest.hexdigest()
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


def reconcile(db, sid, scan):
    """Filename candidates are observations, never identity or playback proofs."""
    sid = library.snapshot_id(db, sid)
    snapshot = db.execute('SELECT status,created_at FROM snapshots WHERE id=?', (sid,)).fetchone()
    coverage = library.sources(db, sid)
    source_coverage = {s['source']: bool(s['exported']) for s in coverage}
    spotify_complete = snapshot['status'].startswith('completed') and all(source_coverage.values())
    files = defaultdict(list)
    for entry in scan['entries']:
        files[entry['filename_title'].casefold()].append(entry)
    results = []
    observed = set()
    for row in library.rows(db, sid):
        if not row['is_local']:
            continue
        candidates = {}
        contradictions = []
        for entry in files.get((row['title'] or '').casefold(), []):
            if row['missing'] or entry['status'] != 'complete':
                continue
            duration = entry['duration_ms']
            if duration is not None and row['duration_ms'] is not None:
                if abs(duration - row['duration_ms']) > 2000:
                    contradictions.append(dict(path=entry['path'], reason='duration_differs'))
                    continue
            candidates[entry['path']] = dict(path=entry['path'], evidence='filename_title',
                                             duration_ms=duration)
        observed.update(candidates)
        complete = scan['status'] == 'complete' and source_coverage[row['source']]
        if row['missing'] or not row['title']:
            status = 'incomplete'
        elif len(candidates) > 1:
            status = 'ambiguous'
        elif candidates:
            status = 'likely'
        else:
            status = 'unmatched' if complete else 'incomplete'
        results.append(dict(source=row['source'], position=row['position'],
                            returned_uri=row['returned_uri'], title=row['title'],
                            artists=json.loads(row['artists']), duration_ms=row['duration_ms'],
                            source_exported=source_coverage[row['source']],
                            comparison_complete=complete, status=status,
                            candidates=list(candidates.values()), contradictions=contradictions))
    return dict(snapshot_id=sid, snapshot_created_at=snapshot['created_at'],
                snapshot_status=snapshot['status'], spotify_coverage=coverage,
                spotify_coverage_complete=spotify_complete, local_occurrences=len(results),
                distinct_local_uris=len({r['returned_uri'] for r in results if r['returned_uri']}),
                references=results,
                files_without_observed_candidate=[dict(path=path, status=(
                    'unmatched' if spotify_complete and scan['status'] == 'complete' else 'incomplete'))
                    for path in sorted({e['path'] for e in scan['entries']} - observed)],
                limitations='Filename candidates do not prove recording identity. Hashes compare file bytes only. '
                             'Coverage applies to chosen roots and captured API sources, never device playback.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='+', type=Path)
    parser.add_argument('--db', type=Path, help='Optional existing catalog, opened read-only')
    parser.add_argument('--snapshot', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.snapshot is not None and args.db is None:
        parser.error('--snapshot requires --db')
    report = inventory(args.roots)
    if args.db is not None:
        with closing(library.connect(args.db)) as db:
            report['reconciliation'] = reconcile(db, args.snapshot, report)
    output = args.output or data_root() / 'inventories' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve earlier reports and refuse to overwrite any source file or catalog.
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print('Local inventory report saved.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
