"""Run saved set recipes against current and historical synthetic data."""

from contextlib import closing, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import library
from library_demo import sample_snapshots
import logical_playlists
import playlist_recipe


class PlaylistRecipeTests(unittest.TestCase):
    def test_saved_recipe_and_preview_keep_order_and_refuse_partial_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path, recipe_path, output = (root / name for name in ('catalog.sqlite', 'recipe.json', 'preview.json'))
            before, after = sample_snapshots()
            with closing(library.connect(db_path, write=True)) as db:
                baseline = library.import_snapshot(db, before, 'Complete')
                after['playlists'][0]['exported'] = False
                incomplete = library.import_snapshot(db, after, 'Partial')
                logical_playlists.save(db, 'two', 'Two volumes', ['Chill', 'Festival'])
            with patch('sys.argv', ['playlist_recipe.py', 'save', str(recipe_path), 'Not festival', 'difference',
                                    'collection:two', 'Festival']), redirect_stdout(StringIO()):
                playlist_recipe.main()
            argv = ['playlist_recipe.py', '--db', str(db_path), 'preview', str(recipe_path), str(output),
                    '--snapshot', str(baseline)]
            with patch('sys.argv', argv), redirect_stdout(StringIO()):
                playlist_recipe.main()
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['recipe']['sources'], ['collection:two', 'Festival'])
            self.assertEqual(result['source_members']['collection:two'], ['Chill', 'Festival'])
            self.assertEqual(result['snapshot_id'], baseline)
            self.assertEqual([track['title'] for track in result['tracks']], ['Harbor'])
            with closing(library.connect(db_path)) as db:
                with self.assertRaisesRegex(ValueError, 'not exported'):
                    playlist_recipe.run(db, incomplete, result['recipe'])
                with self.assertRaisesRegex(ValueError, 'version 1'):
                    playlist_recipe.run(db, baseline, dict(result['recipe'], version=True))
