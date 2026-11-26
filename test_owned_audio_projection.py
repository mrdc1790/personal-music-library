"""Verify the dry-run M3U keeps source order and excludes unreviewed paths."""

from contextlib import closing, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import library
from library_demo import sample_snapshots
import local_inventory
import logical_playlists
import owned_audio_projection


class OwnedAudioProjectionTests(unittest.TestCase):
    def test_projection_keeps_positions_and_repeated_confirmed_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / 'Audio'
            audio.mkdir()
            reviewed = audio / 'Reviewed.mp3'
            reviewed.write_bytes(b'synthetic bytes for the reviewed file')
            copy = audio / 'Copy.mp3'
            copy.write_bytes(reviewed.read_bytes())
            inventory_db = root / 'inventory.sqlite'
            local_inventory.save_inventory(inventory_db, local_inventory.inventory([audio]))
            snapshot, _ = sample_snapshots()
            local = next(row for row in snapshot['occurrences'] if row['is_local'])
            snapshot['occurrences'].append(dict(local, source='Festival', position=2))
            snapshot['occurrences'].append(dict(local, position=1, returned_uri='spotify:local:Demo:Other:Track:180'))
            snapshot['playlists'][1]['exported'] = False
            local_inventory.review_file(inventory_db, local['returned_uri'], reviewed)
            db_path = root / 'catalog.sqlite'
            with closing(library.connect(db_path, write=True)) as db:
                sid = library.import_snapshot(db, snapshot, 'Partial volumes')
                logical_playlists.save(db, 'volumes', 'Volume selection', ['Festival', 'AllLeaks'])
            out = root / 'draft.json'
            args = ['owned_audio_projection.py', '--db', str(db_path), '--snapshot', str(sid), '--collection', 'volumes',
                    '--inventory-db', str(inventory_db), '--output', str(out)]
            with patch('sys.argv', args), redirect_stdout(StringIO()):
                owned_audio_projection.main()
            report = json.loads(out.read_text(encoding='utf-8'))
            self.assertFalse(report['selection']['complete'])
            self.assertEqual(report['m3u_preview'].splitlines(), ['#EXTM3U', str(reviewed), str(reviewed)])
            self.assertEqual([(row['source'], row['position']) for row in report['placements']],
                             [('Festival', 0), ('Festival', 1), ('Festival', 2), ('AllLeaks', 0), ('AllLeaks', 1)])
            self.assertEqual(report['counts'], dict(spotify_catalog_track=2, ready_in_saved_inventory=2, unconfirmed=1))

            moved = audio / 'Moved.mp3'
            reviewed.rename(moved)
            local_inventory.save_inventory(inventory_db, local_inventory.inventory([audio]))
            with closing(library.connect(db_path)) as db:
                result = owned_audio_projection.report(db, sid, local_inventory.load_inventory(inventory_db), playlist='AllLeaks')
            self.assertEqual(result['placements'][0]['status'], 'ambiguous_paths')
            self.assertEqual(result['m3u_preview'], '#EXTM3U\n')
            self.assertEqual(set(result['placements'][0]['observed_paths']), {str(copy), str(moved)})

    def test_path_missing_or_incompatible_with_m3u_stays_unresolved(self):
        confirmation = dict(sha256='hash', path='somewhere')
        self.assertEqual(owned_audio_projection.reviewed_path({}, confirmation)[0], 'confirmed_bytes_not_observed')
        for path in ('relative.mp3', '/music/bad\npath.mp3'):
            result = owned_audio_projection.reviewed_path({'hash': {path: {}}}, confirmation)
            self.assertEqual(result[0:2], ('unsupported_path', None))
