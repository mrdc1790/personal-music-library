from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import patch
import audit
from resumable_audit import Run, check_cooldown, run_lock, cooldown_path

class API:
    client_id = 'a' * 32
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
    def get(self, path):
        self.calls.append(path)
        value = self.responses[path]
        if isinstance(value, list):
            value = value.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

def entry(id):
    return {'track': {'id': id, 'uri': 'spotify:track:' + id}, 'added_at': id}

def page(items, next=None, total=None):
    return {'items': items, 'next': next, 'total': len(items) if total is None else total}

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'run'
        self.run = Run(self.folder, API.client_id)
        self.addCleanup(lambda: self.run.close())
    def base(self):
        return {'me': {'id': 'account'},
                'me/playlists?limit=50': page([{'id': 'p', 'name': 'P'}]),
                'playlists/p': {'id': 'p', 'name': 'P', 'snapshot_id': 'v1'},
                'me/tracks?limit=50&market=from_token': page([])}
    def reopen(self):
        self.run.close()
        self.run = Run(self.folder)
    def test_resume_incomplete_playlist_same_version_skips_saved_page(self):
        r = self.base()
        first = 'playlists/p/items?limit=50&market=from_token'
        later = 'playlists/p/items?limit=50&offset=1'
        r[first] = page([entry('one')], later, 2)
        r[later] = audit.SpotifyRateLimit('test cooldown', 1)
        with self.assertRaises(audit.SpotifyRateLimit):
            self.run.execute(API(r))
        self.assertEqual(len(self.run.rows), 1)
        self.reopen()
        self.run.state['cooldown_until'] = 0
        r[later] = page([entry('two')], total=2)
        api = API(r)
        self.run.execute(api)
        self.assertNotIn(first, api.calls)
        self.assertEqual([x['returned_id'] for x in self.run.rows], ['one', 'two'])
        self.assertTrue(self.run.state['status'].startswith('completed'))
    def test_changed_playlist_discards_stale_checkpoint(self):
        self.test_resume_incomplete_playlist_same_version_skips_saved_page()
        self.reopen()
        r = self.base()
        r['playlists/p'] = {'id': 'p', 'snapshot_id': 'v2'}
        r['playlists/p/items?limit=50&market=from_token'] = page([entry('replacement')])
        self.run.execute(API(r))
        self.assertEqual([x['returned_id'] for x in self.run.rows], ['replacement'])
    def test_completed_playlist_only_fetches_metadata(self):
        r = self.base()
        r['playlists/p/items?limit=50&market=from_token'] = page([entry('one')])
        self.run.execute(API(r))
        self.reopen()
        api = API(self.base())
        self.run.execute(api)
        self.assertEqual(api.calls.count('playlists/p'), 1)
        self.assertEqual(len(self.run.rows), 1)
    def test_likes_same_total_shift_is_detected(self):
        r = self.base()
        r['playlists/p/items?limit=50&market=from_token'] = page([])
        r['me/tracks?limit=50&market=from_token'] = page([entry('old')], 'likes-next', 2)
        r['likes-next'] = audit.SpotifyRateLimit('pause', 1)
        with self.assertRaises(audit.SpotifyRateLimit):
            self.run.execute(API(r))
        self.reopen()
        self.run.state['cooldown_until'] = 0
        r['me/tracks?limit=50&market=from_token'] = page([entry('new'), entry('last')])
        api = API(r)
        self.run.execute(api)
        self.assertNotIn('likes-next', api.calls)
        self.assertEqual([x['returned_id'] for x in self.run.rows], ['new', 'last'])
    def test_unchanged_liked_prefix_continues(self):
        r = self.base()
        r['playlists/p/items?limit=50&market=from_token'] = page([])
        r['me/tracks?limit=50&market=from_token'] = page([entry('first')], 'likes-next', 2)
        r['likes-next'] = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run.execute(API(r))
        self.reopen()
        r['likes-next'] = page([entry('second')], total=2)
        self.run.execute(API(r))
        self.assertEqual([x['returned_id'] for x in self.run.rows], ['first', 'second'])
    def test_uncommitted_page_rows_are_rolled_back(self):
        r = self.base()
        r['playlists/p/items?limit=50&market=from_token'] = page([entry('first'), entry('second')])
        original = audit.occurrence
        def interrupt(source, name, position, item):
            if position == 1:
                raise KeyboardInterrupt()
            return original(source, name, position, item)
        with patch('audit.occurrence', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run.execute(API(r))
        self.reopen()
        self.assertEqual(len(self.run.rows), 0)
        self.assertEqual(self.run.state['sources']['p']['count'], 0)
    def test_account_and_cooldown_guards(self):
        self.run.state['cooldown_until'] = time.time() + 100
        api = API({})
        with self.assertRaisesRegex(RuntimeError, 'Cooldown'):
            self.run.execute(api)
        self.assertEqual(api.calls, [])
        self.run.state.update(cooldown_until=0, account_id='other')
        with self.assertRaisesRegex(RuntimeError, 'Account mismatch'):
            self.run.execute(API(self.base()))
        self.assertEqual(len(self.run.rows), 0)
    def test_app_cooldown_blocks_new_runs(self):
        with patch('resumable_audit.data_root', return_value=Path(self.temp.name)):
            cooldown_path(API.client_id).write_text(json.dumps({'retry_at': time.time() + 100}))
            with self.assertRaisesRegex(RuntimeError, 'cooldown active'):
                check_cooldown(API.client_id)
    def test_process_lock_prevents_duplicate_writer(self):
        with run_lock(self.folder):
            with self.assertRaises((RuntimeError, BlockingIOError)):
                with run_lock(self.folder):
                    self.fail('two writers acquired the same run')
    def test_log_has_request_and_cooldown_but_no_token(self):
        r=self.base()
        r['playlists/p']=audit.SpotifyRateLimit('HTTP 429 at playlists/p', 100)
        with self.assertRaises(audit.SpotifyRateLimit):
            self.run.execute(API(r))
        text=(self.folder/'RUN STATUS.txt').read_text(encoding='utf-8')
        self.assertIn('Do not resume before',text)
        self.assertIn('HTTP 429', text)
        self.assertIn('pending | P',text)
        self.assertIn('request_failed',(self.folder/'run.log.jsonl').read_text())
