import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch
from io import BytesIO
from urllib.error import HTTPError

from audit import OLD, NEW, Spotify, SpotifyRateLimit, SpotifyServerError, DiskRows, occurrence, pages, migration_plan, export_report, stable_playlist, scan


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
    def test_long_rate_limit_stops_without_another_request(self):
        api = Spotify('example', {'access_token': 'test', 'expires_in': 3600})
        error = HTTPError('https://api.spotify.com/v1/me/tracks', 429, 'Limited', {'Retry-After': '24000'}, None)
        with patch('audit.urlopen', side_effect=error) as request, patch('audit.time.sleep') as sleep:
            with self.assertRaises(SpotifyRateLimit):
                api.get('me/tracks')
            self.assertEqual(request.call_count, 1)
            sleep.assert_not_called()

    def test_playlist_rate_limit_stops_whole_scan_and_preserves_checkpoint(self):
        api = FakeAPI({'me': {'id': 'me'},
            'me/tracks?limit=50&market=from_token': {'items': [{'track': {'id': OLD}}], 'total': 1},
            'me/playlists?limit=50': {'items': [{'id': 'p', 'name': 'P'}, {'id': 'never', 'name': 'Never'}], 'total': 2},
            'playlists/p': SpotifyRateLimit('retry in 24000 seconds')})
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'run'
            with self.assertRaises(SpotifyRateLimit):
                scan(api, folder)
            saved = json.loads((folder / 'snapshot.json').read_text())
            self.assertEqual(len(saved['occurrences']), 1)
            self.assertEqual(saved['status'], 'incomplete')
            self.assertIn('24000', saved['errors'][0])

    def test_smaller_page_fallback_keeps_offset_and_every_entry(self):
        api = FakeAPI({'one?limit=50': {'items': [1], 'total': 3, 'next': 'one?limit=50&offset=1'},
            'one?limit=50&offset=1': SpotifyServerError('502'),
            'one?limit=10&offset=1': {'items': [2], 'total': 3, 'next': 'one?limit=10&offset=2'},
            'one?limit=10&offset=2': {'items': [3], 'total': 3}})
        self.assertEqual(pages(api, 'one?limit=50'), [1, 2, 3])

    def test_smaller_page_failure_stops_and_access_denial_does_not_fallback(self):
        with self.assertRaises(SpotifyServerError):
            pages(FakeAPI({'one?limit=50': SpotifyServerError('502'),
                          'one?limit=10': SpotifyServerError('502')}), 'one?limit=50')
        with self.assertRaisesRegex(RuntimeError, '403'):
            pages(FakeAPI({'one?limit=50': RuntimeError('403')}), 'one?limit=50')

    def test_liked_server_failure_continues_playlists_without_false_coverage(self):
        api = FakeAPI({'me': {'id': 'me'},
            'me/tracks?limit=50&market=from_token': {'items': [{'track': {'id': OLD}}], 'total': 2,
                'next': 'me/tracks?limit=50&offset=1'},
            'me/tracks?limit=50&offset=1': SpotifyServerError('502'),
            'me/tracks?limit=10&offset=1': SpotifyServerError('502'),
            'me/playlists?limit=50': {'items': [{'id': 'p', 'name': 'P'}], 'total': 1},
            'playlists/p': {'id': 'p', 'snapshot_id': 'same'},
            'playlists/p/items?limit=50&market=from_token': {'items': [{'track': {'id': NEW}}], 'total': 1},
            f'tracks/{OLD}?market=from_token': {'id': OLD},
            f'tracks/{NEW}?market=from_token': {'id': NEW}})
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'run'
            result = scan(api, folder)
            self.assertEqual(result['status'], 'partial')
            self.assertFalse(result['liked_exported'])
            self.assertTrue(result['playlists'][0]['exported'])
            self.assertEqual([r['source'] for r in result['occurrences']], ['p'])
            self.assertFalse(json.loads((folder / 'snapshot.json').read_text())['liked_exported'])

    def test_disk_export_memory_does_not_scale_with_raw_library(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            tracemalloc.start()
            try:
                rows = DiskRows(folder / 'library.sqlite')
                rows.extend(occurrence('p', 'Playlist', i, {'track': {
                    'id': 'test', 'name': str(i), 'extra': 'x' * 12000}}) for i in range(2000))
                snapshot = dict(status='test', occurrences=rows, errors=[])
                export_report(folder, snapshot)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(len(rows), 2000)
            self.assertGreater((folder / 'snapshot.json').stat().st_size, 24000000)
            self.assertLess(peak, 8 * 1024 * 1024)
            self.assertEqual(sum(1 for _ in rows), 2000)

    def test_disk_source_rolls_back_failed_pagination(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = DiskRows(Path(directory) / 'library.sqlite')
            rows.extend([occurrence('saved', 'Saved', 0, {'track': {'id': 'one'}})])
            def broken():
                yield occurrence('failed', 'Failed', 0, {'track': {'id': 'two'}})
                raise RuntimeError('incomplete pagination')
            with self.assertRaisesRegex(RuntimeError, 'incomplete pagination'):
                rows.extend(broken())
            self.assertEqual([r['source'] for r in rows], ['saved'])

    def test_disk_json_preserves_duplicates_null_and_local_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rows = DiskRows(folder / 'library.sqlite')
            entries = [{'track': {'id': OLD}}, {'track': {'id': OLD}},
                       {'track': None}, {'is_local': True, 'track': {'uri': 'spotify:local:a'}}]
            expected = [occurrence('p', 'P', i, e) for i, e in enumerate(entries)]
            rows.extend(expected)
            export_report(folder, dict(status='test', occurrences=rows, errors=[]))
            self.assertEqual(json.loads((folder / 'snapshot.json').read_text())['occurrences'], expected)

    def test_server_error_retries_same_read_then_succeeds(self):
        api = Spotify('example', {'access_token': 'test', 'expires_in': 3600})
        error = HTTPError('https://api.spotify.com/v1/me/tracks', 502, 'Bad Gateway', {}, None)
        with patch('audit.urlopen', side_effect=[error, BytesIO(b'{"items": [], "total": 0}')]) as request, patch('audit.time.sleep') as sleep, patch('builtins.print') as output:
            self.assertEqual(api.get('me/tracks')['total'], 0)
            self.assertEqual(request.call_count, 2)
            self.assertEqual(request.call_args_list[0].args[0].full_url, request.call_args_list[1].args[0].full_url)
            self.assertEqual(request.call_args_list[1].args[0].get_method(), 'GET')
            sleep.assert_called_once_with(2)
            messages = ' '.join(str(c.args[0]) for c in output.call_args_list)
            self.assertIn('offset 0', messages)
            self.assertIn('retry 1/4', messages)
            self.assertIn('Read succeeded', messages)

    def test_server_errors_stop_after_bounded_retries(self):
        api = Spotify('example', {'access_token': 'test', 'expires_in': 3600})
        error = HTTPError('https://api.spotify.com/v1/me/tracks', 503, 'Unavailable', {}, None)
        with patch('audit.urlopen', side_effect=error) as request, patch('audit.time.sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'after retries'):
                api.get('me/tracks')
            self.assertEqual(request.call_count, 5)
            self.assertEqual([c.args[0] for c in sleep.call_args_list], [2, 4, 8, 16])

    def test_access_denial_is_not_retried_as_server_error(self):
        api = Spotify('example', {'access_token': 'test', 'expires_in': 3600})
        error = HTTPError('https://api.spotify.com/v1/me/tracks', 403, 'Forbidden', {}, None)
        with patch('audit.urlopen', side_effect=error) as request, patch('audit.time.sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
                api.get('me/tracks')
            self.assertEqual(request.call_count, 1)
            sleep.assert_not_called()

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
