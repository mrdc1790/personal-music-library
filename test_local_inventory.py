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

    def test_sqlite_inventory_preserves_scan_history_and_refuses_catalog(self):
        path = self.audio()
        store = self.base / 'inventory.sqlite'
        output = self.base / 'scan.json'
        with patch('builtins.print'):
            self.assertEqual(local.main([str(self.root), '--inventory-db', str(store),
                                         '--output', str(output)]), 0)
        path.unlink()
        second = local.inventory([self.root, self.base / 'missing'])
        self.assertEqual(local.save_inventory(store, second), 2)
        first = local.load_inventory(store, 1)
        self.assertEqual(first['entries'][0]['path'], str(path))
        self.assertEqual(first['status'], 'complete')
        latest = local.load_inventory(store)
        self.assertEqual(latest['scan_id'], 2)
        self.assertEqual(latest['status'], 'incomplete')
        self.assertTrue(latest['roots'][1]['errors'])
        with self.assertRaisesRegex(ValueError, 'not found'):
            local.load_inventory(store, 3)
        self.snapshot()
        before = self.db_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'separate SQLite'):
            local.save_inventory(self.db_path, second)
        self.assertEqual(before, self.db_path.read_bytes())

    def tagged_mp3(self, name, title='Song', artist='Synthetic artist', album='Album'):
        frames = []
        for code, value in [(b'TIT2', title), (b'TPE1', artist), (b'TALB', album)]:
            payload = b'\x01' + value.encode('utf-16') + b'\0\0'
            frames.append(code + len(payload).to_bytes(4, 'big') + b'\0\0' + payload)
        data = b''.join(frames)
        size = bytes((len(data) >> shift) & 127 for shift in (21, 14, 7, 0))
        path = self.root / name
        path.write_bytes(b'ID3\x03\0\0' + size + data + b'synthetic fixture')
        return path

    def test_audio_tags_find_numbered_file_and_surface_metadata_conflicts(self):
        match = self.tagged_mp3('01 - Song.mp3')
        artist_conflict = self.tagged_mp3('02 - Song.mp3', artist='Other artist')
        album_conflict = self.tagged_mp3('03 - Song.mp3', album='Other album')
        title_conflict = self.tagged_mp3('Song.mp3', title='Other song')
        report = self.compare(local.inventory([self.root]))
        first = report['references'][0]
        self.assertEqual([(c['path'], c['evidence']) for c in first['candidates']],
                         [(str(match), 'audio_tags')])
        self.assertEqual({(c['path'], c['reason']) for c in first['contradictions']},
                         {(str(artist_conflict), 'tag_artist_differs'),
                          (str(album_conflict), 'tag_album_differs'),
                          (str(title_conflict), 'tag_title_differs')})

    def test_malformed_mp3_tags_preserve_hash_and_filename_candidate(self):
        path = self.root / 'Song.mp3'
        path.write_bytes(b'ID3\x04\0\0\0\0\0\x40partial')
        scan = local.inventory([self.root])
        self.assertEqual(scan['entries'][0]['metadata_error'], 'Truncated ID3 tag')
        self.assertTrue(scan['entries'][0]['sha256'])
        row = self.compare(scan)['references'][0]
        self.assertEqual(row['candidates'][0]['evidence'], 'filename_title')

    def test_id3v1_and_v24_text_sizes(self):
        old = self.root / 'legacy.mp3'
        old.write_bytes(b'fixture' + b'TAG' + b'Song'.ljust(30, b'\0') + bytes(95))
        modern = self.root / 'modern.mp3'
        long_title = 'é' * 70
        payload = b'\x03' + long_title.encode('utf-8')
        def size(length):
            return bytes((length >> shift) & 127 for shift in (21, 14, 7, 0))

        frame = b'TIT2' + size(len(payload)) + b'\0\0' + payload
        modern.write_bytes(b'ID3\x04\0\0' + size(len(frame)) + frame)
        tags = {Path(e['path']).name: e['tags'] for e in local.inventory([self.root])['entries']}
        self.assertEqual(tags, {'legacy.mp3': {'title': 'Song'}, 'modern.mp3': {'title': long_title}})

    def test_review_carries_to_moved_bytes_and_can_be_cleared(self):
        uri = 'spotify:local:Artist:Album:Song:1'
        path = self.tagged_mp3('01 - Song.mp3')
        store = self.base / 'review.sqlite'
        scan_id = local.save_inventory(store, local.inventory([self.root]))
        original = path.read_bytes()
        path.write_bytes(b'different')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            local.review_file(store, uri, path, scan_id)
        path.write_bytes(original)
        with patch('builtins.print'):
            self.assertEqual(local.main(['--inventory-db', str(store), '--confirm', uri, str(path),
                                         '--inventory-scan', str(scan_id)]), 0)
        renamed_root = self.base / 'archive'
        renamed_root.mkdir()
        moved = path.rename(renamed_root / 'renamed.mp3')
        missing_scan = local.inventory([self.root, self.base / 'unavailable'])
        local.save_inventory(store, missing_scan)
        sid = self.snapshot()
        with closing(library.connect(self.db_path)) as db:
            saved = local.load_inventory(store)
            row = local.reconcile(db, sid, saved, saved['confirmations'])['references'][0]
            self.assertEqual(row['status'], 'incomplete')
            self.assertEqual(row['confirmation']['paths'], [])
            local.save_inventory(store, local.inventory([renamed_root]))
            saved = local.load_inventory(store)
            row = local.reconcile(db, sid, saved, saved['confirmations'])['references'][0]
            self.assertEqual(row['status'], 'confirmed')
            self.assertEqual(row['confirmation']['paths'], [str(moved)])
            self.assertEqual(row['confirmation']['path'], str(path))
            local.review_file(store, uri)
            self.assertEqual(local.load_inventory(store)['confirmations'], {})


if __name__ == '__main__':
    unittest.main()
