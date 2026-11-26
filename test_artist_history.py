"""Synthetic tests for followed-artist captures and catalog joins."""

from contextlib import closing, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import artist_history
import library
from library_demo import sample_snapshots


def capture(day, *ids):
    return dict(schema_version=1, captured_at=f'2026-09-{day:02}T00:00:00Z', artists=[
        dict(spotify_id=key, name='Duplicate name', genres=None if i else ['original tag'])
        for i, key in enumerate(ids)])


class ArtistHistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'catalog.sqlite'
        self.db = library.connect(self.path, write=True)
        self.addCleanup(self.db.close)
        audit, _ = sample_snapshots()
        self.account = audit['account_id']
        self.key, self.featured, self.partial_only = (letter * 22 for letter in 'DXY')
        audit['occurrences'][0]['artist_ids'] = [self.key, self.featured, self.featured]
        self.snapshot = library.import_snapshot(self.db, audit, 'Available library evidence')

    def test_partial_captures_preserve_observations_without_false_transitions(self):
        # Insert out of date order to exercise historical recomputation.
        for day, complete, ids in [(5, True, (self.featured, self.key)), (2, False, (self.partial_only,)),
                                   (1, True, (self.key, self.featured)), (3, True, (self.featured,)),
                                   (4, False, (self.key,))]:
            artist_history.import_capture(self.db, capture(day, *ids), self.account, complete)
        result = artist_history.report(self.db, self.snapshot)
        self.assertEqual([row['change'] for row in result['transitions']], ['unfollowed', 'refollowed'])
        self.assertTrue(all(row['spotify_id'] == self.key for row in result['transitions']))
        artists = {row['spotify_id']: row for row in result['artists']}
        self.assertEqual(len(artists), 3)
        self.assertEqual(artists[self.key]['last_capture_rank'], 2)
        self.assertEqual(artists[self.key]['observed_refollows'], 1)
        self.assertEqual(artists[self.key]['observed_liked_tracks'], 2)
        self.assertEqual(artists[self.featured]['observed_primary_placements'], 0)
        self.assertEqual(artists[self.featured]['observed_all_credit_placements'], 1)
        self.assertEqual(artists[self.partial_only]['latest_complete_state'], 'unknown')
        self.assertEqual(len(artist_history.report(self.db, self.snapshot, term=self.key)['artists']), 1)

    def test_import_validates_account_timestamp_and_repeated_evidence(self):
        document = capture(1, self.key)
        source = self.path.with_name('artists.json')
        source.write_text(json.dumps(document), encoding='utf-8')
        arguments = ['library.py', '--db', str(self.path), 'import-followed-artists', str(source),
                     '--account', self.account, '--coverage', 'complete']
        with patch('sys.argv', arguments), redirect_stdout(StringIO()):
            self.assertEqual(library.main(), 0)
        self.assertFalse(artist_history.import_capture(self.db, document, self.account, True)['added'])
        with self.assertRaisesRegex(ValueError, 'different complete'):
            artist_history.import_capture(self.db, capture(1, self.featured), self.account, True)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            artist_history.import_capture(self.db, document, 'different', False)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            artist_history.import_capture(self.db, capture(2, self.key, self.key), self.account, False)
        with self.assertRaisesRegex(ValueError, 'time zone'):
            artist_history.import_capture(self.db, dict(document, captured_at='2026-09-01T00:00:00'), self.account, False)
        backup = self.path.with_name('backup.zip')
        library.backup(self.db, backup)
        restored = self.path.with_name('restored.sqlite')
        library.restore(backup, restored)
        with closing(library.connect(restored)) as db:
            report = artist_history.report(db, self.snapshot)
        self.assertEqual(len(report['follow_captures']), 1)
        self.assertEqual(report['artists'][0]['latest_complete_state'], 'followed')
        self.assertEqual(report['transitions'], [])
