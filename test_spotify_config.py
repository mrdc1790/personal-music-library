import tempfile
import unittest
from pathlib import Path

from spotify_config import dotenv_client_id, spotify_client_id


VALID = "0123456789abcdef0123456789abcdef"


class SpotifyConfigTests(unittest.TestCase):
    def test_cli_value_has_highest_precedence(self):
        other = "abcdef0123456789abcdef0123456789"
        self.assertEqual(spotify_client_id(VALID, {"SPOTIFY_CLIENT_ID": other}), VALID)

    def test_environment_precedes_dotenv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("SPOTIFY_CLIENT_ID=" + VALID, encoding="utf-8")
            other = "abcdef0123456789abcdef0123456789"
            self.assertEqual(spotify_client_id(None, {"SPOTIFY_CLIENT_ID": other}, path), other)

    def test_reads_quoted_value_without_loading_other_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text(
                "IGNORED=value\nSPOTIFY_CLIENT_ID='" + VALID + "'\nSPOTIFY_CLIENT_SECRET=ignored\n",
                encoding="utf-8",
            )
            self.assertEqual(dotenv_client_id(path), VALID)

    def test_missing_or_invalid_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            with self.assertRaisesRegex(RuntimeError, "Set SPOTIFY_CLIENT_ID"):
                spotify_client_id(None, {}, path)
            path.write_text("SPOTIFY_CLIENT_ID=not-an-id", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "32 hexadecimal"):
                spotify_client_id(None, {}, path)


if __name__ == "__main__":
    unittest.main()
