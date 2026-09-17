import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit import OLD, NEW, occurrence, pages, migration_plan, export_report, stable_playlist, scan


class FakeAPI:
    def __init__(self, responses):
        self.responses = responses

    def get(self, path):
        result = self.responses[path]
        if isinstance(result, list):
            result = result.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class AuditTests(unittest.TestCase):
    def test_missing_original_id_is_never_invented(self):
        row = occurrence('p', 'P', 0, {'item': {'id': NEW, 'name': 'Song'}})
        self.assertIsNone(row['original_id'])
        plan = migration_plan([row])
        self.assertFalse(plan['apply_enabled'])
        self.assertEqual(plan['mappings'][0]['status'], 'needs_account_evidence')

    def test_duplicate_relinks_keep_each_position(self):
        item = {'item': {'id': NEW, 'linked_from': {'id': OLD}}}
        rows = [occurrence('p', 'P', i, item) for i in (2, 5)]
        plan = migration_plan(rows)
        self.assertEqual([r['position'] for r in plan['mappings'][0]['occurrences']], [2, 5])

    def test_null_local_and_legacy_entries(self):
        missing = occurrence('p', 'P', 0, {'item': None})
        local = occurrence('p', 'P', 1, {'is_local': True, 'track': {'uri': 'spotify:local:a'}})
        self.assertTrue(missing['missing'])
        self.assertTrue(local['is_local'])
        self.assertEqual(local['returned_uri'], 'spotify:local:a')

    def test_pagination_and_count_mismatch(self):
        api = FakeAPI({'one': {'items': [1], 'total': 2, 'next': 'two'},
                       'two': {'items': [2], 'total': 2, 'next': None}})
        self.assertEqual(pages(api, 'one'), [1, 2])
        with self.assertRaises(RuntimeError):
            pages(FakeAPI({'one': {'items': [1], 'total': 2}}), 'one')

    def test_pagination_cycle(self):
        with self.assertRaises(RuntimeError):
            pages(FakeAPI({'one': {'items': [1], 'total': 2, 'next': 'one'}}), 'one')

    def test_changed_playlist_is_read_again(self):
        api = FakeAPI({'playlists/p': [{'snapshot_id': 'a'}, {'snapshot_id': 'b'},
                                       {'snapshot_id': 'b'}, {'snapshot_id': 'b'}],
            'playlists/p/items?limit=50&market=from_token': {'items': [], 'total': 0}})
        meta, rows = stable_playlist(api, 'p')
        self.assertEqual(meta['snapshot_id'], 'b')
        self.assertEqual(rows, [])

    def test_exports_escape_html_and_keep_raw_data(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            row = occurrence('p', '<script>alert(1)</script>', 4,
                             {'item': {'id': OLD, 'name': '<img onerror=bad>'}})
            export_report(folder, dict(status='test', occurrences=[row], errors=[]))
            report = (folder/'report.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>', report)
            self.assertIn('&lt;script&gt;', report)
            with closing(sqlite3.connect(folder/'library.sqlite')) as db:
                saved = db.execute('SELECT data FROM occurrences').fetchone()[0]
                self.assertEqual(json.loads(saved)['position'], 4)
                self.assertEqual(json.loads(saved)['raw'], row['raw'])

    def test_scan_retains_access_denial_as_partial(self):
        responses = {'me': {'id': 'me'},
            'me/tracks?limit=50&market=from_token': {'items': [{'track': {'id': OLD}}], 'total': 1},
            'me/playlists?limit=50': {'items': [{'id': 'p', 'name': 'Denied'}], 'total': 1},
            'playlists/p': RuntimeError('HTTP 403'),
            f'tracks/{OLD}?market=from_token': {'id': OLD},
            f'tracks/{NEW}?market=from_token': {'id': NEW}}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)/'run'
            result = scan(FakeAPI(responses), folder)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(len(result['occurrences']), 1)
            self.assertFalse(result['playlists'][0]['exported'])
            self.assertTrue((folder/'snapshot.json').exists())


if __name__ == '__main__':
    unittest.main()
