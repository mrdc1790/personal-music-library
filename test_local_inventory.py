"""Synthetic temporary audio/catalog evidence only; no personal data or network."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import library
import local_inventory as local


class LocalInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'audio'
        self.root.mkdir()
        self.db_path = self.base / 'catalog.sqlite'

    def audio(self, relative='Song.wav', seconds=1):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(8000)
            stream.writeframes(b'\0\0' * 8000 * seconds)
        return path

    def snapshot(self, exported=True, status='completed', title='Song', duration=1000):
        rows = [dict(source='p', position=position, is_local=True,
                     returned_uri='spotify:local:Artist:Album:Song:1',
                     title=title, artists=['Synthetic artist'], duration_ms=duration)
                for position in range(2)]
        with closing(library.connect(self.db_path, write=True)) as db:
            return library.import_snapshot(db, dict(account_id='synthetic', status=status,
                liked_exported=exported, playlists=[dict(metadata=dict(id='p', name='Fixture'),
                                                       exported=exported)], occurrences=rows), 'Fixture')

    def compare(self, scan, **kwargs):
        sid = self.snapshot(**kwargs)
        before = self.db_path.read_bytes()
        with closing(library.connect(self.db_path)) as db:
            result = local.reconcile(db, sid, scan)
        self.assertEqual(before, self.db_path.read_bytes())
        return result

    def test_paths_overlap_and_byte_duplicates_are_separate_counts(self):
        first = self.audio()
        second = self.audio('copy/Song.wav')
        before = first.read_bytes()
        scan = local.inventory([self.root, second.parent])
        self.assertEqual(scan['status'], 'complete')
        self.assertEqual(len(scan['entries']), 3)
        self.assertEqual(scan['distinct_paths'], 2)
        self.assertEqual(scan['byte_duplicates'][0]['paths'], sorted([str(first), str(second)]))
        result = self.compare(scan)
        self.assertEqual(result['local_occurrences'], 2)
        self.assertEqual(result['distinct_local_uris'], 1)
        self.assertEqual([r['position'] for r in result['references']], [0, 1])
        self.assertTrue(all(r['status'] == 'ambiguous' for r in result['references']))
        self.assertEqual(len(result['references'][0]['candidates']), 2)
        self.assertEqual(first.read_bytes(), before)

    def test_single_candidate_is_not_exact_identity(self):
        self.audio()
        result = self.compare(local.inventory([self.root]))
        self.assertEqual(result['references'][0]['status'], 'likely')
        self.assertEqual(result['references'][0]['candidates'][0]['evidence'], 'filename_title')

    def test_missing_root_and_failed_source_never_mean_empty(self):
        scan = local.inventory([self.root, self.base / 'missing'])
        self.assertEqual(scan['status'], 'incomplete')
        self.assertEqual(scan['roots'][1]['errors'][0]['error'], 'FileNotFoundError')
        result = self.compare(scan, exported=False, status='partial')
        self.assertEqual(len(result['references']), 2)
        self.assertTrue(all(r['status'] == 'incomplete' for r in result['references']))
        self.assertFalse(result['spotify_coverage_complete'])

    def test_empty_complete_root_differs_from_partial_catalog(self):
        scan = local.inventory([self.root])
        result = self.compare(scan)
        self.assertEqual(result['references'][0]['status'], 'unmatched')
        result = self.compare(scan, exported=False, status='partial')
        self.assertEqual(result['references'][0]['status'], 'incomplete')

    def test_duration_conflict_and_file_only_evidence(self):
        self.audio(seconds=5)
        result = self.compare(local.inventory([self.root]))
        self.assertEqual(result['references'][0]['status'], 'unmatched')
        self.assertEqual(result['references'][0]['contradictions'][0]['reason'], 'duration_differs')
        self.assertEqual(result['files_without_observed_candidate'][0]['status'], 'unmatched')
        result = self.compare(local.inventory([self.root]), status='partial')
        self.assertEqual(result['files_without_observed_candidate'][0]['status'], 'incomplete')

    def test_read_failure_keeps_path_and_marks_coverage(self):
        path = self.audio()
        original = Path.open

        def denied(target, *args, **kwargs):
            if target == path and args and args[0] == 'rb':
                raise PermissionError('synthetic failure')
            return original(target, *args, **kwargs)

        with patch.object(Path, 'open', denied):
            scan = local.inventory([self.root])
        self.assertEqual(scan['entries'][0]['path'], str(path))
        self.assertIsNone(scan['entries'][0]['sha256'])
        self.assertEqual(scan['status'], 'incomplete')
        self.assertEqual(self.compare(scan)['references'][0]['status'], 'incomplete')

    def test_directory_failure_and_changed_file_are_incomplete(self):
        self.audio()
        with patch.object(local.os, 'scandir', side_effect=PermissionError('fixture')):
            scan = local.inventory([self.root])
        self.assertEqual(scan['roots'][0]['status'], 'incomplete')
        original = Path.stat

        def changed(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if kwargs.get('follow_symlinks', True) and path.suffix == '.wav':
                from types import SimpleNamespace
                return SimpleNamespace(st_size=info.st_size + 1, st_mtime_ns=info.st_mtime_ns)
            return info

        with patch.object(Path, 'stat', changed):
            scan = local.inventory([self.root])
        self.assertEqual(scan['entries'][0]['status'], 'incomplete')

    def test_cli_reports_without_overwriting_and_requires_catalog(self):
        self.audio()
        output = self.base / 'report.json'
        with patch('builtins.print'):
            self.assertEqual(local.main([str(self.root), '--output', str(output)]), 0)
        self.assertEqual(json.loads(output.read_text())['distinct_paths'], 1)
        before = output.read_bytes()
        with self.assertRaises(FileExistsError):
            local.main([str(self.root), '--output', str(output)])
        self.assertEqual(before, output.read_bytes())
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            local.main([str(self.root), '--snapshot', '1'])


if __name__ == '__main__':
    unittest.main()
