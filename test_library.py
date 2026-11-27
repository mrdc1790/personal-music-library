from contextlib import closing, redirect_stderr
from copy import deepcopy
import csv
from html import escape
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import library as lib
from library_demo import sample_snapshots
import logical_playlists
import song_stats
import view_catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = lib.connect(self.folder / "catalog.sqlite", write=True)
        self.addCleanup(self.db.close)
        self.before, self.after = sample_snapshots()
        self.a = lib.import_snapshot(self.db, self.before, "first")

    def test_view_keeps_placeholder_like_labels_and_paths_literal(self):
        catalog = self.folder / '__DATA__ & catalog.sqlite'
        output = self.folder / 'view.html'
        label = '__PATH__ <Sample & title>'
        with closing(lib.connect(catalog, write=True)) as db:
            lib.import_snapshot(db, self.before, label)

        html = view_catalog.create_view(catalog, output).read_text(encoding='utf-8')
        payload = re.search(r'<script type="application/json" id="data">(.*?)</script>', html)
        self.assertEqual(json.loads(payload.group(1))[0]['label'], label)
        self.assertIn(escape(str(catalog.resolve())), html)
        self.assertIn('<button id="clear-filters" type="button">Clear all filters</button>', html)
        self.assertIn('<summary>Compare playlists and collections</summary>', html)

    def test_view_reports_missing_catalog_without_creating_it(self):
        catalog = self.folder / 'missing.sqlite'
        stderr = StringIO()
        with patch('sys.argv', ['view_catalog.py', str(catalog), '--no-open']):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                view_catalog.main()
        self.assertEqual(error.exception.code, 2)
        self.assertIn('Catalog file not found', stderr.getvalue())
        self.assertFalse(catalog.exists())
        self.assertFalse((catalog.parent / 'catalog-view.html').exists())

    def test_import_idempotent_and_history_not_overwritten(self):
        self.assertEqual(lib.import_snapshot(self.db, self.before, "same"), self.a)
        b = lib.import_snapshot(self.db, self.after, "second")
        self.assertEqual(len(lib.rows(self.db, self.a)), 8)
        self.assertEqual(len(lib.rows(self.db, b)), 7)

    def test_ratings_apply_edit_clear_and_restore_by_exact_identity(self):
        key = 'spotify:track:' + 'A' * 22
        catalog = self.folder / 'catalog.sqlite'
        changes = dict(format='personal-music-library-ratings-1', account=self.before['account_id'],
                       changes=[dict(track_key=key, before=None, rating=5)])
        payload = self.folder / 'ratings.json'
        payload.write_text(json.dumps(changes), encoding='utf-8')
        with patch('sys.argv', ['library.py', '--db', str(catalog), 'import-ratings', str(payload)]):
            self.assertEqual(lib.main(), 0)
        self.assertEqual(lib.import_ratings(self.db, changes), {'updated_ratings': 0})
        lib.import_snapshot(self.db, self.after, 'second')
        page = view_catalog.create_view(catalog, self.folder / 'view.html').read_text(encoding='utf-8')
        embedded = re.search(r'<script type="application/json" id="ratings">(.*?)</script>', page)
        self.assertEqual(dict(json.loads(embedded.group(1))), {key: 5})
        changes['changes'][0].update(before=5, rating=3)
        lib.import_ratings(self.db, changes)
        archive = self.folder / 'backup.zip'
        lib.backup(self.db, archive)
        restored = self.folder / 'restored.sqlite'
        lib.restore(archive, restored)
        with closing(lib.connect(restored)) as db:
            self.assertEqual(lib.song_ratings(db), {key: 3})
        changes['changes'][0].update(before=3, rating=None)
        lib.import_ratings(self.db, changes)
        self.assertEqual(lib.song_ratings(self.db), {})

    def test_rating_batch_rolls_back_on_stale_or_unknown_evidence(self):
        first, second = ('spotify:track:' + letter * 22 for letter in 'AB')
        changes = dict(format='personal-music-library-ratings-1', account=self.before['account_id'],
                       changes=[dict(track_key=second, before=None, rating=4)])
        lib.import_ratings(self.db, changes)
        for change, message in [(dict(track_key=second, before=None, rating=2), 'changed'),
                                (dict(track_key='unknown', before=None, rating=3), 'unobserved'),
                                (dict(track_key=second, before=4, rating=True), 'Invalid')]:
            changes['changes'] = [dict(track_key=first, before=None, rating=5), change]
            with self.assertRaisesRegex(ValueError, message):
                lib.import_ratings(self.db, changes)
            self.assertEqual(lib.song_ratings(self.db), {second: 4})
        changes['account'] = 'another-account'
        with self.assertRaisesRegex(ValueError, 'different catalog'):
            lib.import_ratings(self.db, changes)
        with self.db:
            self.db.execute('DROP TABLE song_ratings')
        self.assertEqual(lib.song_ratings(self.db), {})

    def test_metadata_report_uses_existing_raw_observations(self):
        import track_metadata

        baseline = track_metadata.report(self.db, self.a, placements=True)
        row = lib.rows(self.db, self.a)[0]
        original = json.loads(row["raw_json"])
        original["raw"] = {"item": {
            "explicit": False, "popularity": 0,
            "artists": [{"name": "First", "id": "artist-id"}, {"name": "Second"}],
            "album": {"name": "Album", "release_date": "2020-04", "release_date_precision": "month"},
        }}
        with self.db:
            self.db.execute("UPDATE items SET raw_json=? WHERE snapshot_id=? AND source=? AND position=?",
                            (json.dumps(original), self.a, row["source"], row["position"]))
        report = track_metadata.report(self.db, self.a, placements=True)
        self.assertEqual(report["observed_placements"], 8)
        self.assertGreater(report["field_placements"]["release_date"], 0)
        expected_popularity = baseline["field_placements"]["popularity"] + (
            "popularity" not in baseline["placements"][0]["track"])
        self.assertEqual(report["field_placements"]["popularity"], expected_popularity)
        self.assertEqual(report["field_placements"]["artist_genres"], 0)
        placement = report["placements"][0]
        self.assertEqual(placement["album"]["release_date_precision"], "month")
        self.assertEqual([artist["name"] for artist in placement["artists"]], ["First", "Second"])
        self.assertFalse(placement["track"]["explicit"])
        self.assertNotIn("placements", track_metadata.report(self.db, self.a))

    def test_partial_scan_with_failed_likes_is_unknown_not_empty(self):
        partial = deepcopy(self.before)
        partial['status'] = 'partial'
        partial['liked_exported'] = False
        partial['occurrences'] = [r for r in partial['occurrences'] if r['source'] != 'liked']
        sid = lib.import_snapshot(self.db, partial, 'failed likes')
        coverage = {p['source']: p['exported'] for p in lib.sources(self.db, sid)}
        self.assertEqual(coverage['liked'], 0)
        with self.assertRaisesRegex(ValueError, 'not exported'):
            lib.set_query(self.db, sid, 'intersection', ['liked', 'Chill'])

    def test_set_operations_and_reverse_lookup_retain_duplicate_evidence(self):
        shared = lib.set_query(self.db, self.a, "intersection", ["Chill", "Festival"])
        self.assertEqual([r["title"] for r in shared], ["Moonrise"])
        union = lib.set_query(self.db, self.a, "union", ["Chill", "Festival"])
        self.assertEqual(len(union), 3)
        diff = lib.set_query(self.db, self.a, "difference", ["Chill", "Festival"])
        self.assertEqual([r["title"] for r in diff], ["Harbor"])
        self.assertEqual(len(lib.lookup(self.db, self.a, "Moonrise")), 4)

    def test_exact_identity_lookup_and_single_snapshot_explorer(self):
        key = 'spotify:track:' + 'A' * 22
        full = lib.lookup(self.db, self.a, key)
        self.assertEqual(lib.lookup_identity(self.db, self.a, key), full)
        self.assertEqual([(row['source'], row['position']) for row in full],
                         [('Chill', 0), ('Chill', 2), ('Festival', 0), ('liked', 0)])
        self.assertEqual(lib.lookup_identity(self.db, self.a, key[:-1]), [])
        lib.import_snapshot(self.db, self.after, 'second')
        catalog = self.folder / 'catalog.sqlite'
        output = self.folder / 'view.html'
        page = view_catalog.create_view(catalog, output, snapshot=self.a).read_text(encoding='utf-8')
        payload = re.search(r'<script type="application/json" id="data">(.*?)</script>', page)
        self.assertEqual([snapshot['id'] for snapshot in json.loads(payload.group(1))], [self.a])

    def test_logical_collection_keeps_order_duplicates_renames_and_coverage(self):
        logical_playlists.save(self.db, 'split', 'Split playlist', ['Festival', 'Chill'], active='Chill')
        groups = logical_playlists.definitions(self.db, self.before['account_id'])
        self.assertEqual(logical_playlists.definitions(self.db, 'other-account'), {})
        group, = logical_playlists.reports(self.db, self.a, groups, lib.sources(self.db, self.a))
        self.assertEqual([member['playlist_id'] for member in group['members']], ['Festival', 'Chill'])
        self.assertEqual(group['active_playlist'], 'Chill')
        self.assertEqual((group['observed_placements'], group['observed_identities']), (5, 3))
        self.assertTrue(group['complete'])
        self.assertEqual([row['title'] for row in lib.set_query(self.db, self.a, 'intersection',
                                                               ['collection:split', 'liked'])], ['Moonrise', 'Harbor'])
        rankings = song_stats.report(self.db, self.a, None, sort='collection')
        moonrise = next(row for row in rankings['songs'] if row['title'] == 'Moonrise')
        self.assertEqual((moonrise['observed_playlist_count'], moonrise['observed_collection_count']), (2, 1))

        changed = deepcopy(self.after)
        changed['playlists'][0]['metadata']['name'] = 'New volume name'
        changed['playlists'][1]['exported'] = False
        later = lib.import_snapshot(self.db, changed, 'renamed, partial')
        group, = logical_playlists.reports(self.db, later, groups, lib.sources(self.db, later))
        self.assertEqual([member['coverage'] for member in group['members']], ['partial', 'complete'])
        self.assertEqual(group['members'][1]['name'], 'New volume name')
        self.assertFalse(group['complete'])
        with self.assertRaisesRegex(ValueError, 'not exported'):
            lib.set_query(self.db, later, 'difference', ['collection:split', 'liked'])

        changed['playlists'].pop(1)
        changed['occurrences'] = [row for row in changed['occurrences'] if row['source'] != 'Festival']
        missing = lib.import_snapshot(self.db, changed, 'missing member')
        group, = logical_playlists.reports(self.db, missing, groups, lib.sources(self.db, missing))
        self.assertEqual(group['members'][0]['coverage'], 'absent')
        self.assertIsNone(group['members'][0]['placements'])
        with self.assertRaisesRegex(ValueError, 'known to the catalog'):
            logical_playlists.save(self.db, 'split', 'Changed', ['Uncaptured'])
        self.assertEqual(logical_playlists.definitions(self.db, self.before['account_id']), groups)

    def test_unknown_playlist_is_not_treated_as_empty(self):
        snapshot = deepcopy(self.after)
        snapshot["playlists"][0]["exported"] = False
        snapshot["occurrences"] = [r for r in snapshot["occurrences"] if r["source"] != "Chill"]
        b = lib.import_snapshot(self.db, snapshot, "partial")
        with self.assertRaisesRegex(ValueError, "not exported"):
            lib.set_query(self.db, b, "difference", ["Festival", "Chill"])
        change = next(r for r in lib.compare(self.db, self.a, b) if r["source"] == "Chill")
        self.assertEqual(change["status"], "coverage_changed_or_unknown")
        self.assertNotIn("removed_occurrences", change)
        self.assertNotIn("remaining_occurrences_for_removed_keys", change)

    def test_compare_counts_duplicate_removal(self):
        snapshot = deepcopy(self.after)
        snapshot["occurrences"] = [
            r for r in snapshot["occurrences"] if (r["source"], r["position"]) != ("liked", 1)
        ]
        b = lib.import_snapshot(self.db, snapshot, "second")
        changes = {r["source"]: r for r in lib.compare(self.db, self.a, b)}
        duplicate = "spotify:track:" + "A" * 22
        unliked = "spotify:track:" + "B" * 22
        self.assertEqual(changes["Chill"]["removed_occurrences"], {duplicate: 1})
        self.assertEqual(changes["Chill"]["remaining_occurrences_for_removed_keys"], {duplicate: 1})
        self.assertTrue(changes["Chill"]["sequence_changed"])
        self.assertEqual(changes["liked"]["removed_occurrences"], {unliked: 1})
        self.assertEqual(changes["liked"]["remaining_occurrences_for_removed_keys"], {unliked: 0})

    def test_bad_positions_roll_back_import(self):
        snapshot = deepcopy(self.after)
        snapshot["occurrences"][0]["position"] = 999
        with self.assertRaises(ValueError):
            lib.import_snapshot(self.db, snapshot, "bad")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0], 1)

    def test_unknown_identity_is_not_collapsed_or_used_in_intersection(self):
        snapshot = deepcopy(self.after)
        for r in snapshot["occurrences"]:
            if r["position"] == 0:
                r.update(missing=True, returned_id=None, returned_uri=None)
        b = lib.import_snapshot(self.db, snapshot, "missing")
        self.assertEqual(lib.set_query(self.db, b, "intersection", ["Chill", "Festival"]), [])
        unknown = [r["track_key"] for r in lib.rows(self.db, b) if r["missing"]]
        self.assertEqual(len(unknown), len(set(unknown)))

    def test_partial_database_stores_errors_and_rejects_other_account(self):
        snapshot = deepcopy(self.after)
        snapshot["account_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "separate catalog"):
            lib.import_snapshot(self.db, snapshot, "wrong")

    def test_backup_restore_and_checksum_failure(self):
        target = self.folder / "copy.zip"
        lib.backup(self.db, target)
        restored = self.folder / "restored.sqlite"
        lib.restore(target, restored)
        with closing(lib.connect(restored)) as db:
            self.assertEqual(len(lib.rows(db, self.a)), 8)
        with self.assertRaisesRegex(ValueError, "already exists"):
            lib.restore(target, restored)
        with zipfile.ZipFile(target) as archive:
            manifest = archive.read("manifest.json")
            content = archive.read("catalog.sqlite")
        corrupt = self.folder / "corrupt.zip"
        with zipfile.ZipFile(corrupt, "w") as archive:
            archive.writestr("manifest.json", manifest)
            archive.writestr("catalog.sqlite", content + b"corruption")
        with self.assertRaisesRegex(ValueError, "checksum"):
            lib.restore(corrupt, self.folder / "bad.sqlite")
        self.assertFalse((self.folder / "bad.sqlite").exists())

    def test_csv_formula_safety_duplicate_counts_and_local_artist_separation(self):
        snapshot = deepcopy(self.after)
        snapshot["occurrences"][0]["title"] = '=HYPERLINK("http://example.invalid")'
        b = lib.import_snapshot(self.db, snapshot, "formula")
        out = self.folder / "export"
        lib.export(self.db, b, out)
        with (out / "playlist_items.csv").open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.DictReader(stream))
        self.assertTrue(next(r for r in exported if r["source"] == "Chill")["title"].startswith("'="))
        self.assertTrue(lib.lookup(self.db, b, "HYPERLINK")[0]["title"].startswith("="))
        with (out / "artist_playlist_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
            artists = list(csv.DictReader(stream))
        local = next(r for r in artists if r["source"] == "AllLeaks")
        self.assertTrue(local["artist_key"].startswith("unmatched-name:"))
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(len(manifest["playlist_files"]), 4)

    def test_existing_audit_database_cannot_be_repurposed(self):
        import sqlite3
        path = self.folder / "audit.sqlite"
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE occurrences(id INTEGER)")
            db.commit()
        with self.assertRaisesRegex(ValueError, "another database"):
            lib.connect(path, write=True)


if __name__ == "__main__":
    unittest.main()
