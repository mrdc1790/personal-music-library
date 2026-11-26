"""Availability reports use synthetic Spotify and filesystem observations."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit
import availability
import library
import local_inventory


def spotify_track(letter, title="Track", **fields):
    track_id = letter * 22
    return dict(dict(id=track_id, uri=f"spotify:track:{track_id}", name=title,
                     artists=[{"name": "Artist"}], duration_ms=120000, explicit=False), **fields)


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.catalog = self.folder / "catalog.sqlite"
        self.db = library.connect(self.catalog, write=True)
        self.addCleanup(self.db.close)

    def capture(self, liked, playlist=()):
        rows = []
        for source, tracks in (("liked", liked), ("playlist", playlist)):
            for index, track in enumerate(tracks):
                # Older captures used the track wrapper for both sources.
                field = "track" if source == "liked" else "item"
                rows.append(audit.occurrence(source, source, index, {field: track}))
        return library.import_snapshot(self.db, dict(account_id="synthetic", status="incomplete",
            created_at="2026-01-02T12:34:56Z", liked_exported=False, occurrences=rows,
            playlists=[dict(metadata=dict(id="playlist", name="Playlist <name>"), exported=True)]), "Test")

    def test_partial_sources_keep_unknown_rows_and_exclude_local_and_episodes(self):
        unavailable = spotify_track("A", is_playable=False)
        restricted = spotify_track("B", restrictions={"reason": "market"})
        explicit = spotify_track("C", is_playable=False, restrictions={"reason": "explicit"})
        local = {"name": "Local", "uri": "spotify:local::Local:120", "is_playable": False}
        episode = spotify_track("E", type="episode", is_playable=False)
        sid = self.capture([unavailable, None, spotify_track("D"), local],
                           [unavailable, unavailable, restricted, explicit, episode])
        report = availability.report(self.db, sid)
        groups = report["groups"]
        self.assertEqual([(r["source"], r["position"]) for r in groups["check_local"]],
                         [("liked", 0), ("playlist", 0), ("playlist", 1), ("playlist", 2)])
        self.assertEqual([r["restriction"] for r in groups["review"]], ["explicit"])
        self.assertEqual([r["position"] for r in groups["unknown"]], [1])
        self.assertFalse(groups["recover"])
        self.assertEqual(report["sources"]["liked"], dict(source="liked", name="Liked Songs", exported=0,
                                                             local=1, non_track=0, no_signal=1, observed=4))
        self.assertEqual(report["sources"]["playlist"]["non_track"], 1)

    def test_playable_relinks_and_recording_candidates_require_positive_evidence(self):
        fields = dict(external_ids={"isrc": "TEST12345"})
        sid = self.capture([spotify_track("A", is_playable=False, **fields),
                            spotify_track("F", "Relinked track", is_playable=False),
                            spotify_track("H", "Conflicting track", is_playable=False)],
                           [spotify_track("B", is_playable=True, **fields),
                            spotify_track("C", is_playable=True, **(fields | {"explicit": True})),
                            spotify_track("D", "Track (Remix)", is_playable=True, **fields),
                            spotify_track("E", **fields),
                            spotify_track("G", "Relinked track", is_playable=True, linked_from={"id": "F" * 22}),
                            spotify_track("H", "Conflicting track", is_playable=True),
                            spotify_track("I", "Unverified relink", linked_from={"id": "J" * 22})])
        groups = availability.report(self.db, sid)["groups"]
        self.assertEqual([r["candidates"] for r in groups["spotify_candidate"]],
                         [[("B" * 22, "Matching ISRC, title and artists")], [("G" * 22, "Spotify relink")]])
        self.assertEqual([r["original_id"] for r in groups["relinked"]], ["F" * 22])
        self.assertEqual([r["original_id"] for r in groups["unknown"]], ["J" * 22])
        self.assertTrue(groups["review"][0]["mixed_playability"])

    def test_only_complete_local_inventory_raises_recovery_leads(self):
        sid = self.capture([spotify_track("A", "Found", is_playable=False),
                            spotify_track("B", "Missing", is_playable=False)])
        music = self.folder / "music"
        music.mkdir()
        audio_file = music / "Artist - Found.mp3"
        audio_file.write_bytes(b"synthetic audio fixture")
        complete = local_inventory.inventory([music])
        groups = availability.report(self.db, sid, complete)["groups"]
        self.assertEqual(groups["local_candidate"][0]["local_paths"], [str(audio_file)])
        self.assertEqual([r["title"] for r in groups["recover"]], ["Missing"])
        incomplete = local_inventory.inventory([music, self.folder / "unreadable"])
        groups = availability.report(self.db, sid, incomplete)["groups"]
        self.assertEqual([r["title"] for r in groups["check_local"]], ["Missing"])
        self.assertFalse(groups["recover"])
        self.assertTrue(groups["local_candidate"])

    def test_cli_writes_a_private_html_report_with_safe_links_and_every_position(self):
        track = spotify_track("A", "<script> & remix", is_playable=False)
        self.capture([track], [track, track])
        output = self.folder / "new.html"
        before = self.catalog.read_bytes()
        argv = ["library.py", "--db", str(self.catalog), "availability", "--output", str(output)]
        with patch("sys.argv", argv), redirect_stdout(StringIO()) as stdout:
            self.assertEqual(library.main(), 0)
            self.assertEqual(json.loads(stdout.getvalue())["placements"]["check_local"], 3)
        page = output.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt; &amp; remix", page)
        self.assertNotIn("<script>", page)
        self.assertEqual(page.count("https://soundcloud.com/search/sounds?q=Artist+%3Cscript%3E+%26+remix"), 1)
        self.assertIn("Playlist &lt;name&gt; · Position 1, 2 · complete", page)
        self.assertIn("Liked Songs · Position 1 · incomplete", page)
        with patch("sys.argv", argv), redirect_stdout(StringIO()):
            self.assertEqual(library.main(), 1)
        self.assertEqual(output.read_text(encoding="utf-8"), page)
        self.assertEqual(self.catalog.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
