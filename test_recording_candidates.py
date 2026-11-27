"""Exercise candidate evidence without making any network requests."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import library
import recording_candidates
import recording_review
import release_comparison


ISRC = 'USABC2600001'


def observed(source, position, key, title='Original', code=None, explicit=False, local=False, length=180000):
    uri = 'spotify:local:Demo:Album:Original:180' if local else 'spotify:track:' + key * 22
    credit = dict(name='Demo Artist', id=None if local else 'D' * 22)
    album = dict(id=('R' if key == 'A' else 'S') * 22, name='Demo Album')
    return dict(source=source, position=position, returned_uri=uri, title=title, artists=[credit['name']],
                is_local=local, isrc=code, explicit=explicit, duration_ms=length,
                raw=dict(item=dict(uri=uri, artists=[credit], album=album)))


def capture(day, *rows, partial=()):
    return dict(account_id='SYNTHETIC-CANDIDATES', created_at=f'2026-09-{day:02}T00:00:00Z',
                status='partial' if partial else 'completed', liked_exported=False, occurrences=list(rows),
                playlists=[dict(metadata=dict(id=source, name=source), exported=source not in partial)
                           for source in sorted({row['source'] for row in rows})])


def album_member(row, release_id, ordinal, total):
    track = row['raw']['item']
    track.update(disc_number=1, track_number=ordinal)
    track['album'].update(id=release_id, total_tracks=total)
    return row


class RecordingCandidateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'catalog.sqlite'
        self.db = library.connect(self.path, write=True)
        self.addCleanup(self.db.close)

    def test_same_isrc_and_version_conflicts_with_distinct_source_placements(self):
        before = library.import_snapshot(self.db, capture(1, observed('old', 0, 'A', code=ISRC)), 'Earlier')
        after = library.import_snapshot(self.db, capture(
            2, observed('left', 0, 'B', code=ISRC), observed('left', 1, 'B', code=ISRC),
            observed('right', 0, 'B', code=ISRC),
            observed('right', 1, 'C', title='Original - Live', code=ISRC, explicit=True, length=187000),
            observed('right', 2, 'D', title='Incompatible duration', code=None, length=185000),
            partial=('right',),
        ), 'Later')
        key = 'spotify:track:' + 'A' * 22
        result = recording_candidates.report(self.db, before, after, key)
        self.assertEqual(result['total_candidates'], 2)
        same, conflicting = result['candidates']
        self.assertEqual(result['search_snapshot']['exported_sources'], 1)
        self.assertEqual(result['source_placements'][0]['release_id'], 'R' * 22)
        self.assertEqual(same['status'], 'isrc_candidate')
        self.assertEqual(len(same['comparisons']), 1)
        self.assertEqual([(row['source'], row['position'], row['source_exported']) for row in same['placements']],
                         [('left', 0, True), ('left', 1, True), ('right', 0, False)])
        self.assertEqual(conflicting['status'], 'conflicting_evidence')
        self.assertEqual(conflicting['comparisons'][0]['conflicts'], ['title', 'explicit', 'duration_ms'])

    def test_local_reference_cli_keeps_missing_id_and_unknown_playability(self):
        local = observed('volume', 0, 'L', local=True)
        local['is_playable'] = None
        replacement = observed('volume', 1, 'B', code=ISRC)
        replacement['is_playable'] = None
        sid = library.import_snapshot(self.db, capture(1, local, replacement), 'Saved evidence')
        report = self.path.with_name('candidates.json')
        argv = ['recording_candidates.py', local['returned_uri'], '--db', str(self.path), '--snapshot', str(sid),
                '--output', str(report)]
        with patch('sys.argv', argv), redirect_stdout(StringIO()):
            recording_candidates.main()
        data = json.loads(report.read_text(encoding='utf-8'))
        row, = data['candidates']
        self.assertEqual(row['status'], 'metadata_candidate')
        self.assertIn('isrc', row['comparisons'][0]['unknown'])
        self.assertIsNone(row['placements'][0]['playable'])
        self.assertTrue(data['source_key'].startswith('spotify:local:'))
        with self.assertRaisesRegex(ValueError, 'absent'):
            recording_candidates.report(self.db, sid, sid, 'Absent key')

    def test_pair_review_is_direction_independent_and_retains_revisions(self):
        source = observed('volume', 0, 'A', code=ISRC)
        candidate = observed('volume', 1, 'B', code=ISRC)
        sid = library.import_snapshot(self.db, capture(1, source, candidate), 'Review evidence')
        left, right = source['returned_uri'], candidate['returned_uri']
        args = ['library.py', '--db', str(self.path), 'review-recording', right, left,
                '--decision', 'keep-separate', '--reason', 'Verified different audio versions']
        with patch('sys.argv', args), redirect_stdout(StringIO()):
            self.assertEqual(library.main(), 0)
        review, = recording_candidates.report(self.db, sid, sid, left)['reviews']
        self.assertEqual(review['decision'], 'keep-separate')
        self.assertEqual((review['left_key'], review['right_key']), (left, right))
        self.assertFalse(recording_review.save(self.db, left, right, 'keep-separate', review['reason'])['added'])
        recording_review.save(self.db, left, right, 'same-recording', 'New evidence changed the decision')
        recording_review.save(self.db, right, left, 'clear', 'Needs another listening check')
        self.assertEqual(recording_review.reviews(self.db, left), [])
        self.assertEqual([row['decision'] for row in recording_review.reviews(self.db, right, history=True)],
                         ['keep-separate', 'same-recording', 'clear'])
        self.assertEqual(len(library.rows(self.db, sid)), 2)
        with self.assertRaisesRegex(ValueError, 'must be present'):
            recording_review.save(self.db, left, 'spotify:track:' + 'X' * 22, 'same-recording', 'Test')

    def test_release_comparison_uses_metadata_over_ordinals_and_keeps_a_bonus_track(self):
        old, deluxe = 'R' * 22, 'S' * 22
        earlier = capture(1,
                          album_member(observed('old', 0, 'A', code=ISRC), old, 1, 2),
                          album_member(observed('old', 1, 'A', code=ISRC), old, 1, 2),
                          album_member(observed('old', 2, 'Q', title='Interlude'), old, 2, 2))
        later = capture(2,
                        album_member(observed('new', 0, 'Q', title='Interlude'), deluxe, 1, 5),
                        album_member(observed('new', 1, 'B', code=ISRC), deluxe, 2, 5),
                        album_member(observed('new', 2, 'C', title='Bonus'), deluxe, 3, 5),
                        album_member(observed('new', 3, 'D', code=ISRC, explicit=True), deluxe, 4, 5),
                        partial=('new',))
        before = library.import_snapshot(self.db, earlier, 'Standard')
        after = library.import_snapshot(self.db, later, 'Deluxe partial')
        output = self.path.with_name('release-comparison.json')
        args = ['release_comparison.py', old, deluxe, '--db', str(self.path), '--left-snapshot', str(before),
                '--right-snapshot', str(after), '--output', str(output)]
        with patch('sys.argv', args), redirect_stdout(StringIO()):
            release_comparison.main()
        result = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(result['left']['observed_track_entries'], 2)
        self.assertEqual(len(result['left']['tracks'][0]['placements']), 2)
        self.assertEqual(result['right']['reported_track_totals'], [5])
        self.assertEqual(result['right']['exported_sources'], 0)
        self.assertEqual(result['right_without_compatible_candidate'], [2, 3])
        self.assertEqual([(p['left'], p['right'], p['status']) for p in result['pairs']],
                         [(0, 1, 'one_to_one_candidate'), (0, 3, 'conflicting_metadata'), (1, 0, 'one_to_one_candidate')])
        self.assertTrue(result['pairs'][-1]['shared_observed_key'])
