import os
from pathlib import Path
import unittest
from unittest.mock import patch
from storage_paths import data_root

class StorageTests(unittest.TestCase):
    def test_default_and_override(self):
        home = Path.home()
        with patch.dict(os.environ, {"LOCALAPPDATA": str(home / "AppData/Local")}, clear=True):
            self.assertEqual(data_root(), home / "AppData/Local/PersonalMusicLibrary")
        with patch.dict(os.environ, {"PERSONAL_MUSIC_LIBRARY_DATA": "chosen-data"}):
            self.assertEqual(data_root(), Path("chosen-data").resolve())
