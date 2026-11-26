from contextlib import closing
from pathlib import Path
import json
import tempfile
import unittest

import checkpoint_export
import library
import playlist_capacity
from resumable_audit import Run


def row(source, position, uri=None, *, local=False):
    return dict(source=source, position=position, returned_uri=uri, is_local=local, missing=uri is None)


class CapacityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = library.connect(self.folder / "catalog.sqlite", write=True)
        self.addCleanup(self.db.close)

    def make_run(self):
        run = Run(self.folder / "run", "synthetic-client")
        manifest = [dict(id=key, name=key) for key in ("finished", "paused", "failed", "pending")]
        return run, manifest

    def test_checkpoint_round_trip_retains_saved_prefix_and_unknown_coverage(self):
        run, manifest = self.make_run()
        with closing(run):
            run.state.update(
                account_id="synthetic", status="paused", manifest=manifest, discovery_complete=False,
                last_error="synthetic cutoff", sources={
                    "finished": dict(status="complete", count=4, total=4, completed_at="2026-01-02T00:00:00Z"),
                    "paused": dict(status="capturing", count=1, total=4),
                    "failed": dict(status="failed", count=0, error="synthetic failure"),
                },
            )
            uri = "spotify:track:example"
            occurrences = [
                row("finished", 0, uri), row("finished", 1, uri),
                row("finished", 2, "spotify:local::::35", local=True), row("finished", 3),
                row("paused", 0, uri),
            ]
            run.db.executemany(
                "INSERT INTO occurrences VALUES (?,?,?,?,?)",
                [(item["source"], item["position"], None, None, json.dumps(item)) for item in occurrences],
            )
            run.save()
        database = run.folder / "library.sqlite"
        original = database.read_bytes()
        snapshot = checkpoint_export.snapshot(database)
        self.assertEqual(database.read_bytes(), original)
        self.assertEqual(snapshot["occurrences"], occurrences)
        self.assertNotIn("client_id", snapshot)

        sid = library.import_snapshot(self.db, json.loads(json.dumps(snapshot)), "saved checkpoint")
        report = playlist_capacity.report(self.db, sid)
        sources = {item["source"]: item for item in report["sources"]}
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(report["checkpoint_error"], "synthetic cutoff")
        self.assertEqual(sources["finished"]["remaining_slots"], 9996)
        self.assertEqual(sources["finished"]["captured_at"], "2026-01-02T00:00:00Z")
        self.assertEqual(sources["paused"]["placements"], 1)
        self.assertEqual(sources["paused"]["provider_total"], 4)
        self.assertIsNone(sources["paused"]["remaining_slots"])
        self.assertEqual(sources["failed"]["source_error"], "synthetic failure")
        self.assertEqual(sources["pending"]["source_status"], "pending")
        self.assertFalse(sources["liked"]["source_complete"])

    def test_checkpoint_refuses_a_complete_source_with_missing_rows(self):
        run, manifest = self.make_run()
        with closing(run):
            run.state.update(account_id="synthetic", manifest=manifest, sources={
                "finished": dict(status="complete", count=1, total=1),
            })
            run.save()
        with self.assertRaisesRegex(ValueError, "saved source coverage"):
            checkpoint_export.snapshot(run.folder / "library.sqlite")

    def test_growth_requires_dated_complete_reconciled_counts(self):
        def capture(date, count, provider_count):
            return library.import_snapshot(self.db, dict(
                account_id="synthetic", created_at=date, status="partial", liked_exported=True,
                playlists=[
                    dict(exported=True, metadata=dict(id="p", tracks=dict(total=count))),
                    dict(exported=True, metadata=dict(id="mismatch", items=dict(total=provider_count))),
                    dict(exported=True, metadata=dict(id="unknown", tracks=dict(total=0), items=dict(total=2))),
                ],
                occurrences=[row("p", i, "spotify:track:example") for i in range(count)],
            ), date)

        first = capture("2026-01-01T00:00:00Z", 1, 0)
        later = capture("2026-01-02T00:00:00Z", 3, 1)
        report = playlist_capacity.report(self.db, later, first)
        sources = {item["source"]: item for item in report["sources"]}
        self.assertEqual(sources["p"]["net_placement_change"], 2)
        self.assertEqual(sources["mismatch"]["capacity_status"], "count_mismatch")
        self.assertIsNone(sources["mismatch"]["net_placement_change"])
        self.assertEqual(sources["unknown"]["capacity_status"], "provider_total_unknown")
        self.assertEqual(sources["liked"]["capacity_status"], "not_applicable")
        backwards = playlist_capacity.report(self.db, first, later)
        self.assertTrue(all(item["net_placement_change"] is None for item in backwards["sources"]))

    def test_near_capacity_counts_every_placement(self):
        count = playlist_capacity.PLAYLIST_LIMIT - 1
        sid = library.import_snapshot(self.db, dict(
            account_id="synthetic", status="partial", liked_exported=False,
            playlists=[dict(exported=True, metadata=dict(id="p", items=dict(total=count)))],
            occurrences=[row("p", i, "spotify:track:example") for i in range(count)],
        ), "near capacity")
        source = playlist_capacity.report(self.db, sid)["sources"][0]
        self.assertEqual(source["placements"], count)
        self.assertEqual(source["remaining_slots"], 1)


if __name__ == "__main__":
    unittest.main()
