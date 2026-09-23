"""Durable read-only audit. Source checkpoints and rows commit together in SQLite."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import audit
from storage_paths import data_root


def utc():
    return datetime.now(timezone.utc).isoformat()


def signature(entry):
    track = (entry.get('item') if 'item' in entry else entry.get('track')) or {}
    return [track.get('id'), track.get('uri'), (track.get('linked_from') or {}).get('id'),
            entry.get('added_at'), entry.get('is_local', track.get('is_local', False))]


@contextmanager
def run_lock(folder):
    handle = (folder / 'run.lock').open('a+b')
    try:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError('This run is already open in another process.') from None
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        handle.close()  # OS releases the lock, including after a crash.


class Run:
    def __init__(self, folder, client_id=None):
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.rows = audit.DiskRows(self.folder / 'library.sqlite')
        self.db = sqlite3.connect(self.rows.path)
        self.db.execute('CREATE TABLE IF NOT EXISTS run_state (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, data TEXT)')
        saved = self.db.execute('SELECT data FROM run_state WHERE id=1').fetchone()
        if saved:
            self.state = json.loads(saved[0])
            if self.state.get('version') != 1:
                raise RuntimeError('Unsupported run checkpoint version.')
        else:
            if not client_id or len(self.rows):
                raise RuntimeError('Not a resumable run. Legacy backups remain untouched; create a new run.')
            self.state = dict(version=1, client_id=client_id, created_at=utc(), status='ready',
                              sources={}, manifest=[], discovery_complete=False, discovery_next='me/playlists?limit=50',
                              discovery_total=None, discovery_seen=[], cooldown_until=0, account_id=None)
            self.save()
        self.write_status()

    def close(self):
        self.db.close()

    def save(self):
        self.state['updated_at'] = utc()
        self.db.execute('INSERT OR REPLACE INTO run_state VALUES(1,?)', (json.dumps(self.state),))
        self.db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('snapshot', json.dumps(self.snapshot(False))))
        self.db.commit()

    def snapshot(self, include_rows=True):
        s = self.state
        result = dict(created_at=s['created_at'], status=s['status'], account_id=s.get('account_id'),
                      client_id=s['client_id'], api_mode='development', errors=[], track_checks={},
                      liked_exported=s['sources'].get('liked', {}).get('status') == 'complete', playlists=[])
        for meta in s['manifest']:
            source = s['sources'].get(meta['id'], {})
            result['playlists'].append(dict(metadata=source.get('metadata', meta), exported=source.get('status') == 'complete'))
            if source.get('error'):
                result['errors'].append(meta.get('name', meta['id']) + ': ' + source['error'])
        if s.get('last_error') and s['status'] != 'completed API export; hidden original IDs remain unknown':
            result['errors'].append(s['last_error'])
        if include_rows:
            result['occurrences'] = self.rows
        return result

    def event(self, kind, **fields):
        record = dict(time=utc(), event=kind, **fields)
        with (self.folder / 'run.log.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def write_status(self):
        audit.write_json(self.folder / 'run-state.json', self.state)
        s = self.state
        lines = ['Personal Music Library — resumable audit', 'Status: ' + s['status'],
                 'Updated: ' + s.get('updated_at', ''), 'Folder: ' + str(self.folder),
                 'Current request: ' + s.get('current_request', 'none'),
                 'Last failure: ' + (s.get('last_error') or 'none')]
        if s.get('cooldown_until', 0) > time.time():
            lines.append('Do not resume before: ' + datetime.fromtimestamp(s['cooldown_until'], timezone.utc).astimezone().isoformat())
        lines += ['Resume: double-click Resume this audit.cmd in this folder.',
                  'No automatic retry after exit. Close/reopen or Ctrl+C preserves committed pages.',
                  'Counts are placements, not unique recordings. Incomplete sources are not complete backups.',
                  'Liked Songs has no version token; prefix revalidation is required on resume.', '', 'Sources:']
        for meta in s['manifest'] + [dict(id='liked', name='Liked Songs')]:
            item = s['sources'].get(meta['id'], {})
            lines.append(f"{item.get('status', 'pending')} | {meta.get('name', meta['id'])} | "
                         f"{item.get('count', 0)}/{item.get('total', '?')} | {item.get('error', '')}")
        audit.write_json(self.folder / 'status-summary.json', dict(
            status=s['status'], completed=sum(x.get('status') == 'complete' for x in s['sources'].values()),
            known_sources=len(s['manifest']) + 1, discovery_complete=s['discovery_complete']))
        (self.folder / 'RUN STATUS.txt').write_text('\n'.join(lines), encoding='utf-8')

    def checkpoint(self, event, **fields):
        self.save()
        self.event(event, **fields)
        self.write_status()

    def clear_source(self, key, meta=None):
        # Clearing old rows and resetting progress are one transaction.
        self.db.execute('DELETE FROM occurrences WHERE source=?', (key,))
        self.state['sources'][key] = dict(status='pending', count=0, total=None, seen=[],
            next=('me/tracks?limit=50&market=from_token' if key == 'liked' else f'playlists/{key}/items?limit=50&market=from_token'),
            metadata=meta or {}, started_at=utc())
        self.checkpoint('source_reset', source=key)

    def request(self, api, path):
        # Log endpoint + pagination only, never Authorization, OAuth URLs, or tokens.
        parsed = urlsplit(path)
        query = parse_qs(parsed.query)
        location = parsed.path + ' ' + urlencode({k: query[k][0] for k in ('offset', 'limit') if k in query})
        self.state['current_request'] = location
        self.save()
        self.event('request', endpoint=location)
        try:
            value = api.get(path)
        except BaseException as error:
            self.event('request_failed', endpoint=location, error=str(error) or type(error).__name__)
            raise
        self.event('request_succeeded', endpoint=location)
        return value

    def discover(self, api):
        s = self.state
        while not s['discovery_complete']:
            path = s['discovery_next']
            if path in s['discovery_seen']:
                raise RuntimeError('Playlist discovery repeated a page; start a fresh run for changed membership.')
            page = self.request(api, path)
            items = page.get('items')
            if not isinstance(items, list):
                raise RuntimeError('Playlist discovery omitted items.')
            if s['discovery_total'] is not None and page.get('total') != s['discovery_total']:
                raise RuntimeError('Playlist list changed during discovery. Start a fresh run; this run is retained.')
            s['discovery_total'] = page.get('total')
            ids = {p['id'] for p in s['manifest']}
            if any(not p.get('id') or p['id'] in ids for p in items) or len({p['id'] for p in items}) != len(items):
                raise RuntimeError('Duplicate/missing playlist ID during discovery; cannot trust this page.')
            s['manifest'].extend(items)
            s['discovery_seen'].append(path)
            s['discovery_next'] = page.get('next')
            s['discovery_complete'] = not s['discovery_next']
            if s['discovery_complete'] and s['discovery_total'] != len(s['manifest']):
                raise RuntimeError('Playlist discovery count mismatch.')
            self.checkpoint('discovery_page', count=len(s['manifest']))

    def collect(self, api, key, name):
        source = self.state['sources'][key]
        while source['next']:
            path = source['next']
            if path in source['seen']:
                raise RuntimeError('Repeated source page; source remains incomplete.')
            try:
                page = self.request(api, path)
            except audit.SpotifyServerError:
                parsed = urlsplit(path); query = parse_qs(parsed.query)
                if int(query.get('limit', ['0'])[0]) <= 10:
                    raise
                query['limit'] = ['10']
                source['next'] = parsed._replace(query=urlencode(query, doseq=True)).geturl()
                self.checkpoint('smaller_page', source=key)
                continue
            items = page.get('items')
            if not isinstance(items, list):
                raise RuntimeError('Missing items; source remains incomplete.')
            if source['total'] is not None and source['total'] != page.get('total'):
                self.clear_source(key, source['metadata'])
                raise RuntimeError('Source total changed; source reset. Resume when edits have stopped.')
            total = page.get('total')
            count = source['count'] + len(items)
            if not isinstance(total, int) or count > total or (not page.get('next') and count != total):
                raise RuntimeError('Page count mismatch; invalid page not committed.')
            for i, entry in enumerate(items, source['count']):
                row = audit.occurrence(key, name, i, entry)
                self.db.execute('INSERT INTO occurrences VALUES(?,?,?,?,?)',
                    (key, i, row['returned_id'], row['original_id'], json.dumps(row, ensure_ascii=False)))
            source.update(count=count, total=total, next=page.get('next'), status='capturing')
            source['seen'].append(path)
            self.checkpoint('page_saved', source=key, count=count, total=total)
            print(f'{name}: {count:,}/{total:,} placements checkpointed.', flush=True)

    def validate_liked_prefix(self, api):
        source = self.state['sources']['liked']
        count = source['count']
        if not count:
            return True
        print(f'Revalidating {count:,} saved Liked Songs entries before resuming...', flush=True)
        path = 'me/tracks?limit=50&market=from_token'
        position = 0
        seen = set()
        while position < count:
            if not path or path in seen:
                return False
            seen.add(path)
            page = self.request(api, path)
            if page.get('total') != source['total'] or not isinstance(page.get('items'), list) or not page['items']:
                return False
            for entry in page['items']:
                if position == count:
                    break
                saved = self.db.execute('SELECT data FROM occurrences WHERE source=? AND position=?', ('liked', position)).fetchone()
                if not saved or signature(json.loads(saved[0])['raw']) != signature(entry):
                    return False
                position += 1
            path = page.get('next')
            self.event('liked_prefix_validated', count=position, total=count)
            print(f'Liked Songs prefix checked: {position:,}/{count:,}', flush=True)
        source['prefix_validated_at'] = utc()
        self.checkpoint('liked_prefix_matches', count=count)
        return True

    def execute(self, api):
        s = self.state
        if s.get('cooldown_until', 0) > time.time():
            raise RuntimeError('Cooldown has not expired. See RUN STATUS.txt; no API request made.')
        if getattr(api, 'client_id', s['client_id']) != s['client_id']:
            raise RuntimeError('Client ID differs from this run.')
        api.audit_event = self.event
        me = self.request(api, 'me')
        account = me.get('account_id', me.get('id'))
        if not account or (s.get('account_id') and s['account_id'] != account):
            raise RuntimeError('Account mismatch; no source data changed.')
        s.update(account_id=account, status='running', last_error=None, cooldown_until=0)
        self.checkpoint('session_started')
        try:
            self.discover(api)
            for meta in s['manifest']:
                key, name = meta['id'], meta.get('name', meta['id'])
                source = s['sources'].get(key, {})
                try:
                    current = self.request(api, f'playlists/{key}')
                    version = current.get('snapshot_id')
                    if not version:
                        raise RuntimeError('No playlist snapshot ID; cannot safely resume this source.')
                    if 'next' not in source or source.get('metadata', {}).get('snapshot_id') != version:
                        self.clear_source(key, current)
                        source = s['sources'][key]
                    source['validated_at'] = utc()
                    source['metadata'] = current
                    if source.get('status') == 'complete':
                        self.checkpoint('playlist_unchanged', source=key)
                        print(f'Unchanged; reusing: {name}', flush=True)
                        continue
                    # An inaccessible source keeps its checkpoint but loses trusted coverage.
                    source.pop('error', None)
                    self.collect(api, key, name)
                    after = self.request(api, f'playlists/{key}')
                    if after.get('snapshot_id') != version:
                        self.clear_source(key, after)
                        raise RuntimeError('Playlist changed during capture; checkpoint reset for next resume.')
                    source.update(status='complete', completed_at=utc(), metadata=after)
                    self.checkpoint('source_complete', source=key)
                except audit.SpotifyRateLimit:
                    raise
                except RuntimeError as error:
                    source = s['sources'].setdefault(key, dict(count=0, metadata=meta))
                    source.update(status='failed', error=str(error))
                    self.checkpoint('source_failed', source=key, error=str(error))
                    print(f'Not exported: {name}: {error}', flush=True)
            if 'liked' not in s['sources']:
                self.clear_source('liked')
            liked = s['sources']['liked']
            if not self.validate_liked_prefix(api):
                self.clear_source('liked')
                liked = s['sources']['liked']
                print('Liked Songs changed: recapturing likes only. Playlist checkpoints retained.', flush=True)
            self.collect(api, 'liked', 'Liked Songs')
            liked.update(status='complete', completed_at=utc())
            failed = any(x.get('status') != 'complete' for x in s['sources'].values())
            s['status'] = 'partial' if failed else 'completed API export; hidden original IDs remain unknown'
            self.checkpoint('session_finished')
        except BaseException as error:
            self.db.rollback()
            # Reload committed state in case an interruption happened mid-page.
            self.state = json.loads(self.db.execute('SELECT data FROM run_state WHERE id=1').fetchone()[0])
            self.state.update(status='paused', last_error=str(error) or type(error).__name__)
            if isinstance(error, audit.SpotifyRateLimit):
                self.state['cooldown_until'] = getattr(error, 'retry_at', time.time() + 60)
            self.checkpoint('session_paused', error=self.state['last_error'])
            raise


def cooldown_path(client_id):
    return data_root() / ('cooldown-' + hashlib.sha256(client_id.encode()).hexdigest()[:16] + '.json')


def check_cooldown(client_id, until=0):
    path = cooldown_path(client_id)
    if path.exists():
        until = max(until, json.loads(path.read_text())['retry_at'])
    if until > time.time():
        expiry = datetime.fromtimestamp(until, timezone.utc).astimezone().isoformat()
        raise RuntimeError('Spotify cooldown active until ' + expiry + '. No sign-in or scan started.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-id')
    parser.add_argument('--output', type=Path, default=data_root() / 'backups')
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--export-json', action='store_true', help='Optional large legacy JSON/report export after scanning')
    args = parser.parse_args(argv)
    run = None
    try:
        if args.resume:
            folder = args.resume.resolve()
            if not (folder / 'library.sqlite').exists():
                raise RuntimeError('Resume folder does not contain a run database.')
            client_id = None
        else:
            client_id = args.client_id or input('Paste your Spotify app Client ID (not Client Secret): ').strip()
            if len(client_id) != 32 or any(c not in '0123456789abcdefABCDEF' for c in client_id):
                raise ValueError('Expected a 32-character hexadecimal Client ID.')
            check_cooldown(client_id)
            folder = args.output.resolve() / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
            folder.mkdir(parents=True, exist_ok=False)
        with run_lock(folder):
            run = Run(folder, client_id)
            launcher = f'@echo off\r\ncd /d "{Path(__file__).resolve().parent}"\r\npython resumable_audit.py --resume "{folder}"\r\npause\r\n'
            (folder / 'Resume this audit.cmd').write_text(launcher, encoding='utf-8')
            print('Run folder:', folder, flush=True)
            print('Status and resume instructions:', folder / 'RUN STATUS.txt', flush=True)
            if args.prepare_only or args.status:
                print((folder / 'RUN STATUS.txt').read_text(encoding='utf-8'))
                return 0
            if run.state['status'].startswith('completed'):
                if args.export_json:
                    audit.export_report(folder, run.snapshot())
                    return 0
                raise RuntimeError('This run is complete. Start a fresh run to preserve its history.')
            check_cooldown(run.state['client_id'], run.state.get('cooldown_until', 0))
            try:
                api = audit.Spotify(run.state['client_id'], audit.authorize(run.state['client_id']))
                run.execute(api)
            except (Exception, KeyboardInterrupt) as error:
                run.db.rollback()
                run.state = json.loads(run.db.execute('SELECT data FROM run_state WHERE id=1').fetchone()[0])
                run.state.update(status='paused', last_error=str(error) or type(error).__name__)
                if isinstance(error, audit.SpotifyRateLimit):
                    run.state['cooldown_until'] = error.retry_at
                run.checkpoint('session_stopped', error=run.state['last_error'])
                raise
            if args.export_json:
                audit.export_report(folder, run.snapshot())
            print('Finished:', run.state['status'], flush=True)
            return 0 if run.state['status'].startswith('completed') else 2
    except (Exception, KeyboardInterrupt) as error:
        print('Paused/stopped:', str(error) or type(error).__name__, flush=True)
        print('Do not start over. Resume the same folder after any cooldown.', flush=True)
        return 1
    finally:
        if run:
            run.close()


if __name__ == '__main__':
    raise SystemExit(main())
