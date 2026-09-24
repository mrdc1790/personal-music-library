from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import folder_tree
import preview_audit

P = 'A' * 22
Q = 'B' * 22


class FolderTests(unittest.TestCase):
    def tree(self):
        return {'rootlist': {'account_id': 'me', 'entries': [
            {'FolderStart': {'id': 'outer', 'name': 'Dance'}},
            {'FolderStart': {'id': 'empty', 'name': 'Empty'}}, 'FolderEnd',
            {'Playlist': 'spotify:playlist:' + P}, 'FolderEnd',
            {'Playlist': 'spotify:playlist:' + Q}]}}

    def test_nested_order_empty_folders(self):
        account, nodes = folder_tree.normalize(self.tree())
        self.assertEqual(account, 'me')
        self.assertEqual([n['parent_id'] for n in nodes], [None, 0, 0, None])
        self.assertEqual([n['sibling_order'] for n in nodes], [0, 0, 1, 1])

    def test_rejects_unbalanced_or_unknown(self):
        for entries in [['FolderEnd'], [{'FolderStart': {'id': 'x', 'name': 'X'}}], [{'Unexpected': 1}]]:
            with self.assertRaises(ValueError):
                folder_tree.normalize({'account_id': 'me', 'entries': entries})

    def test_uri_decode(self):
        _, nodes = folder_tree.normalize({'account_id': 'me', 'uris': [
            'spotify:start-group:1:Bass+%26+beats', 'spotify:playlist:' + P, 'spotify:end-group:1']})
        self.assertEqual(nodes[0]['name'], 'Bass & beats')

    def test_import_idempotence_account_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'session.json', Path(tmp) / 'tree.sqlite'
            data = self.tree()
            data['unrelated_session_field'] = 'DO_NOT_RETAIN'
            source.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                folder_tree.import_tree(source, target, 'other')
            self.assertFalse(target.exists())
            first = folder_tree.import_tree(source, target, 'me')
            self.assertEqual(first, folder_tree.import_tree(source, target, 'me'))
            data['rootlist']['entries'][0]['FolderStart']['name'] = 'Changed'
            source.write_text(json.dumps(data))
            self.assertNotEqual(first, folder_tree.import_tree(source, target, 'me'))
            self.assertEqual(folder_tree.latest_tree(target, 'me')['nodes'][0]['name'], 'Changed')
            self.assertIsNone(folder_tree.latest_tree(target, 'other'))
            data['rootlist']['entries'][0]['FolderStart']['name'] = 'Dance'
            source.write_text(json.dumps(data))
            restored = folder_tree.import_tree(source, target, 'me')
            self.assertGreater(restored[0], first[0])
            self.assertEqual(folder_tree.latest_tree(target, 'me')['nodes'][0]['name'], 'Dance')
            self.assertNotIn(b'DO_NOT_RETAIN', target.read_bytes())


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'library.sqlite'
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript('CREATE TABLE run_state(id INTEGER, data TEXT); CREATE TABLE occurrences(source TEXT, position INTEGER, data TEXT);')
            state = dict(created_at='today', status='paused', account_id='me', discovery_complete=True,
                manifest=[{'id': P}, {'id': Q}], sources={
                P: dict(status='complete', count=2, total=2, metadata={'name': 'Music'}),
                Q: dict(status='capturing', count=1, total=3, metadata={'name': 'Partial'})})
            db.execute('INSERT INTO run_state VALUES(1,?)', (json.dumps(state),))
            for key, pos in [(P, 0), (P, 1), (Q, 0)]:
                row = dict(source=key, position=pos, returned_uri='spotify:track:' + P,
                           title='</script><script>alert(1)</script>', artists=['Example'])
                db.execute('INSERT INTO occurrences VALUES(?,?,?)', (key, pos, json.dumps(row)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_subset_preserves_duplicate_positions_and_escapes_html(self):
        data = preview_audit.load_trial(self.path)
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(len(data['playlists']), 1)
        self.assertEqual(data['known_sources'], 3)
        out = preview_audit.render(data, Path(self.tmp.name) / 'trial.html')
        self.assertNotIn('</script><script>alert(1)</script>', out.read_text(encoding='utf-8'))

    def test_reject_partial_and_over_budget(self):
        for kwargs in [dict(selected=[Q]), dict(selected=[P], max_rows=1), dict(max_rows=0)]:
            with self.assertRaises(ValueError):
                preview_audit.load_trial(self.path, **kwargs)

    def test_bad_coverage_rejected(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM occurrences WHERE source=? AND position=1', (P,))
        with self.assertRaises(ValueError):
            preview_audit.load_trial(self.path)


if __name__ == '__main__':
    unittest.main()
