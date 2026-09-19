from contextlib import closing
from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import library as lib
from library_demo import sample_snapshots


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = lib.connect(self.folder / "catalog.sqlite", write=True)
        self.addCleanup(self.db.close)
        self.before, self.after = sample_snapshots()
        self.a = lib.import_snapshot(self.db, self.before, "first")

    def test_import_idempotent_and_history_not_overwritten(self):
        self.assertEqual(lib.import_snapshot(self.db, self.before, "same"), self.a)
        b = lib.import_snapshot(self.db, self.after, "second")
        self.assertEqual(len(lib.rows(self.db, self.a)), 8)
        self.assertEqual(len(lib.rows(self.db, b)), 7)

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

    def test_compare_counts_duplicate_removal(self):
        b = lib.import_snapshot(self.db, self.after, "second")
        change = next(r for r in lib.compare(self.db, self.a, b) if r["source"] == "Chill")
        self.assertEqual(change["removed_occurrences"], {"spotify:track:" + "A" * 22: 1})
        self.assertTrue(change["sequence_changed"])

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
