import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import folder_tree
import library
import song_stats
import stream_counts


TRACK_A, TRACK_B, TRACK_C, TRACK_D = ("spotify:track:" + char * 22 for char in "ABCD")
PLAYLIST_IDS = [char * 22 for char in "123456"]


class SongStatsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "catalog.sqlite"
        self.db = library.connect(self.path, write=True)
        self.addCleanup(self.db.close)
        playlists = [dict(metadata=dict(id=source, name="Volume"), exported=i < 5)
                     for i, source in enumerate(PLAYLIST_IDS)]
        rows = []
        for source, tracks in zip(PLAYLIST_IDS + ["liked"], [
                [TRACK_A, TRACK_A], [TRACK_A, TRACK_B], [TRACK_A, TRACK_B], [TRACK_B],
                [TRACK_D], [TRACK_B], [TRACK_C, TRACK_A]]):
            for position, key in enumerate(tracks):
                rows.append(dict(source=source, position=position, returned_uri=key,
                                 title="Alternate title" if key == TRACK_A and source == PLAYLIST_IDS[1] else key[-1]))
        rows.append(dict(source=PLAYLIST_IDS[4], position=1, missing=True))
        rows.append(dict(source=PLAYLIST_IDS[4], position=2, returned_uri="spotify:episode:" + "E" * 22))
        snapshot = dict(account_id="sample", status="partial", liked_exported=True,
                        playlists=playlists, occurrences=rows)
        self.sid = library.import_snapshot(self.db, snapshot, "Sample")
        folders = self.root / "tree.json"
        folders.write_text(json.dumps(dict(account_id="sample", uris=[
            "spotify:start-group:house:Electronic", "spotify:start-group:dance:Dance",
            "spotify:playlist:" + PLAYLIST_IDS[0], "spotify:playlist:" + PLAYLIST_IDS[1], "spotify:end-group:dance",
            "spotify:start-group:bass:Bass", "spotify:playlist:" + PLAYLIST_IDS[2], "spotify:end-group:bass",
            "spotify:end-group:house", "spotify:start-group:rock:Rock", "spotify:playlist:" + PLAYLIST_IDS[3],
            "spotify:end-group:rock", "spotify:playlist:" + PLAYLIST_IDS[4],
        ])), encoding="utf-8")
        self.hierarchy = self.root / "hierarchy.sqlite"
        folder_tree.import_tree(folders, self.hierarchy, "sample")

    def archive(self, entries):
        path = self.root / "history.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, rows in entries.items():
                archive.writestr(name, json.dumps(rows))
        return path

    def csv(self, name, body):
        path = self.root / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_scores_with_folder_breadth_and_partial_coverage(self):
        rank = song_stats.report(self.db, self.sid, self.hierarchy)
        self.assertEqual(rank["playlist_coverage"], dict(exported=5, known=6, exported_with_known_folder=4))
        self.assertEqual([(r["track_key"], r["observed_playlist_count"], r["playlist_score"]) for r in rank["songs"]],
                         [(TRACK_B, 3, 5), (TRACK_A, 3, 4), (TRACK_D, 1, 1), (TRACK_C, 0, 0)])
        self.assertIsNone(rank["songs"][0]["personal_spotify_plays_30s"])
        self.assertIsNone(rank["songs"][0]["worldwide_imported_streams"])
        deeper = song_stats.report(self.db, self.sid, self.hierarchy, folder_depth=2, term="Alternate title")
        self.assertEqual(deeper["songs"][0]["playlist_score"], 5)
        self.assertEqual(deeper["songs"][0]["playlist_ids"], PLAYLIST_IDS[:3])
        flat = song_stats.report(self.db, self.sid, self.root / "missing.sqlite")
        self.assertIsNone(flat["hierarchy"])
        self.assertEqual(flat["songs"][0]["playlist_score"], 3)

    def test_conflicting_folders_do_not_add_a_bonus(self):
        tree = folder_tree.latest_tree(self.hierarchy, "sample")
        conflicting = dict(tree["nodes"][-1], provider_id=PLAYLIST_IDS[0])
        tree["nodes"].append(conflicting)
        self.assertNotIn(PLAYLIST_IDS[0], song_stats.playlist_folders(tree, 1))
        self.assertIsNone(folder_tree.latest_tree(self.hierarchy, "other"))

    def test_spotify_and_cross_service_plays_and_totals_stay_separate(self):
        event = dict(spotify_track_uri=TRACK_A, ts="2024-03-01T03:00:00Z", ms_played=30000,
                     ip_addr="private")
        short = dict(event, spotify_track_uri=TRACK_B, ms_played=29999)
        path = self.archive({"my_data/Streaming_History_Audio_0.json": [event, event, short, dict(event, spotify_track_uri=None)],
                             "my_data/Streaming_History_Video_0.json": [event]})
        self.assertEqual(stream_counts.import_spotify_history(self.db, path)["new_events"], 3)
        self.assertEqual(stream_counts.import_spotify_history(self.db, path)["new_events"], 0)
        overlap = self.archive({"Streaming_History_Audio_1.json": [event, dict(event, ts="2024-03-02T03:00:00Z")]})
        self.assertEqual(stream_counts.import_spotify_history(self.db, overlap)["new_events"], 1)
        personal = self.csv("plays.csv", "service,event_id,track_key,ended_at,played_ms\n"
                            f"apple-music,apple-1,{TRACK_A},2024-03-01T04:00:00+01:00,31000\n")
        self.assertEqual(stream_counts.import_personal_plays(self.db, personal)["new_events"], 1)
        self.assertEqual(stream_counts.import_personal_plays(self.db, personal)["new_events"], 0)
        totals = self.csv("totals.csv", "service,track_key,as_of,streams,source\n"
                          f"spotify,{TRACK_A},2026-10-01,200,Artist dashboard\n"
                          f"spotify,{TRACK_A},2026-11-01,300,Artist dashboard\n"
                          f"apple-music,{TRACK_A},2026-10-15,50,Distributor\n")
        self.assertEqual(stream_counts.import_worldwide_streams(self.db, totals)["new_observations"], 3)
        self.assertEqual(stream_counts.import_worldwide_streams(self.db, totals)["new_observations"], 0)
        rank = song_stats.report(self.db, self.sid, self.hierarchy, sort="personal")
        a, b, *_ = rank["songs"]
        self.assertEqual((a["personal_spotify_plays_30s"], a["personal_imported_plays_30s"]), (3, 4))
        self.assertEqual((a["worldwide_spotify_streams"], a["worldwide_imported_streams"]), (300, 350))
        self.assertEqual((b["personal_spotify_plays_30s"], b["worldwide_imported_streams"]), (0, None))
        self.assertEqual(b["personal_by_service"][0]["played_ms"], 29999)
        self.assertEqual(rank["personal_history_coverage"][0]["first_event_at"], "2024-03-01T03:00:00.000000+00:00")
        self.assertEqual(len(a["worldwide_by_service"]), 2)
        self.assertNotIn("private", " ".join(self.db.iterdump()))

    def test_invalid_import_rolls_back_and_basic_archive_gets_clear_error(self):
        event = dict(spotify_track_uri=TRACK_A, ts="2024-03-01T03:00:00Z", ms_played=30000)
        path = self.archive({"Streaming_History_Audio_0.json": [event, dict(event, ms_played=-10)]})
        with self.assertRaisesRegex(ValueError, "row 2"):
            stream_counts.import_spotify_history(self.db, path)
        self.assertEqual(stream_counts.observations(self.db)[0], {})
        basic = self.archive({"StreamingHistory_music_0.json": [dict(trackName="test", msPlayed=100)]})
        with self.assertRaisesRegex(ValueError, "Extended Streaming History"):
            stream_counts.import_spotify_history(self.db, basic)
        conflict = self.csv("conflict.csv", "service,track_key,as_of,streams,source\n"
                            f"spotify,{TRACK_A},2026-10-01,200,Artist dashboard\n"
                            f"spotify,{TRACK_A},2026-10-01,201,Artist dashboard\n")
        with self.assertRaisesRegex(ValueError, "Conflicting service total"):
            stream_counts.import_worldwide_streams(self.db, conflict)
        self.assertEqual(stream_counts.observations(self.db)[1], {})


if __name__ == "__main__":
    unittest.main()
