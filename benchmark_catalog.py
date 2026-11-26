"""Measure catalog imports and queries using only synthetic snapshots."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import tempfile
from time import perf_counter
import tracemalloc

import library
import song_stats


def snapshot(identities, repeats, later):
    playlists = []
    items = []
    # Keep each playlist within its own capacity while growing total history.
    for start in range(0, repeats, 10000):
        source = f'volume-{start // 10000:03}'
        playlists.append(dict(exported=True, metadata=dict(id=source, name=source)))
    playlists.append(dict(exported=False, metadata=dict(id='unread', name='Unread playlist')))
    for index in range(identities + repeats):
        repeated = index >= identities
        source = playlists[(index - identities) // 10000]['metadata']['id'] if repeated else 'liked'
        position = (index - identities) % 10000 if repeated else index
        identity = (index + int(later and index == identities)) % identities
        local = identity % 1000 == 999
        track_id = f'{identity:022}'
        uri = f'spotify:local:Demo:Library:Track+{identity}:180' if local else f'spotify:track:{track_id}'
        items.append(dict(source=source, position=position, title=f'Synthetic track {identity:07}',
                          artists=['Synthetic artist'], returned_id=None if local else track_id,
                          returned_uri=uri, is_local=local, duration_ms=180000))
    return dict(account_id='SYNTHETIC-BENCHMARK', created_at=f'2026-01-0{2 if later else 1}T00:00:00Z',
                status='partial', liked_exported=True, playlists=playlists, occurrences=items)


def measure(operation, trace):
    if trace:
        tracemalloc.start()
    start = perf_counter()
    try:
        result = operation()
        seconds = perf_counter() - start
        peak = round(tracemalloc.get_traced_memory()[1] / (1024 * 1024), 2) if trace else None
    finally:
        if trace:
            tracemalloc.stop()
    return result, dict(seconds=round(seconds, 4), python_peak_mib=peak)


def run(identities, repeats, trace):
    output = dict(identities=identities, placements_per_snapshot=identities + repeats, snapshots=2)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'benchmark.sqlite'
        with closing(library.connect(path, write=True)) as db:
            before, output['import_first'] = measure(
                lambda: library.import_snapshot(db, snapshot(identities, repeats, False), 'First'), trace)
            after, output['import_second'] = measure(
                lambda: library.import_snapshot(db, snapshot(identities, repeats, True), 'Second'), trace)
        key = 'spotify:track:' + f'{1:022}'
        exact_lookup = getattr(library, 'lookup_identity', None)
        output['exact_lookup_implementation'] = 'indexed' if exact_lookup else 'substring baseline'
        with closing(library.connect(path)) as db:
            for name, operation in {
                'exact_lookup': lambda: (exact_lookup or library.lookup)(db, after, key),
                'text_search': lambda: library.lookup(db, after, 'Synthetic track 0000001'),
                'intersection': lambda: library.set_query(db, after, 'intersection', ['volume-000', 'volume-001']),
                'compare': lambda: library.compare(db, before, after),
                'song_stats': lambda: song_stats.report(db, after, None, limit=10),
            }.items():
                result, output[name] = measure(operation, trace)
                if name == 'exact_lookup':
                    assert result and all(row['track_key'] == key for row in result)
                elif name == 'compare':
                    assert sum(row['status'] == 'changed' for row in result) == 1
                else:
                    assert result is not None
                del result
        output['sqlite_file_mib'] = round(path.stat().st_size / (1024 * 1024), 2)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identities', type=int, default=100_000)
    parser.add_argument('--repeats', type=int, default=90_000, help='Repeated placements per snapshot (at least 10001)')
    parser.add_argument('--trace-memory', action='store_true', help='Measure Python allocation peaks and instrumented time')
    args = parser.parse_args()
    if args.identities < 2 or args.repeats < 10001:
        parser.error('Use at least two identities and 10001 repeated placements.')
    print(json.dumps(run(args.identities, args.repeats, args.trace_memory), indent=2))


if __name__ == '__main__':
    main()
