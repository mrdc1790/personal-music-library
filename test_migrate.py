from copy import deepcopy
from pathlib import Path
import random
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

import audit
import migrate as m


OLD, NEW = audit.OLD, audit.NEW
OTHER = "A" * 22
P = "P" * 22
CLIENT = "c" * 32
U, V, W = [m.track_uri(x) for x in (OLD, NEW, OTHER)]


def fixture(sequence=None, liked=None, mode="extended"):
    sequence = sequence if sequence is not None else [U, W, U, V]
    liked = liked if liked is not None else [U, V]
    rows = []
    for source, uris in ((P, sequence), ("liked", liked)):
        for i, uri in enumerate(uris):
            rows.append(audit.occurrence(source, source, i,
                {"item": {"id": uri.split(":")[-1], "uri": uri, "name": "Example", "is_playable": True}}))
    return dict(account_id="me", client_id=CLIENT, api_mode=mode, status="completed export",
        occurrences=rows, errors=[], playlists=[dict(exported=True,
            metadata=dict(id=P, name="Example", owner=dict(id="me"), snapshot_id="0"))])


def make(sequence=None, liked=None, mode="extended"):
    return m.make_plan(fixture(sequence, liked, mode), [dict(old_id=OLD, new_id=NEW, evidence="test", approved=True)])


class FakeSpotify:
    client_id = CLIENT

    def __init__(self, plan):
        self.playlists = {p: x["before"][:] for p, x in plan["playlists"].items()}
        self.versions = {p: int(x["snapshot_id"]) for p, x in plan["playlists"].items()}
        self.liked = deepcopy(plan["liked_before"])
        self.calls = []
        self.fail_after = None
        self.fail_before = False
        self.account = "me"
        self.playable = True

    def get(self, path):
        if path == "me":
            return dict(id=self.account)
        if path.startswith("tracks/"):
            return dict(id=path.split("/")[1].split("?")[0], is_playable=self.playable)
        if path.startswith("me/library/contains?"):
            uris = parse_qs(urlsplit(path).query)["uris"][0].split(",")
            return [self.liked[u] for u in uris]
        p = path.split("/")[1]
        if "/items?" in path:
            return dict(items=[{"item": {"id": u.split(":")[-1], "uri": u}} for u in self.playlists[p]],
                        total=len(self.playlists[p]), next=None)
        return dict(id=p, name="Example", snapshot_id=str(self.versions[p]))

    def mutate(self, method, path, body):
        self.calls.append((method, path, deepcopy(body)))
        if self.fail_before:
            raise OSError("Network failed before response")
        if path.startswith("me/library?"):
            uri = parse_qs(urlsplit(path).query)["uris"][0]
            self.liked[uri] = method == "PUT"
            result = {}
        else:
            p = path.split("/")[1]
            current = self.playlists[p]
            if method == "POST":
                pos = body["position"]
                current[pos:pos] = body["uris"]
            elif method == "DELETE":
                removed = {x["uri"] for x in body["items"]}
                self.playlists[p] = [u for u in current if u not in removed]
            else:
                self.playlists[p] = body["uris"][:]
            self.versions[p] += 1
            result = dict(snapshot_id=str(self.versions[p]))
        if len(self.calls) == self.fail_after:
            raise OSError("Server committed, response lost")
        return result


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "journal.json"

    def execute(self, plan):
        api = FakeSpotify(plan)
        journal = m.start_journal(api, plan, self.path)
        m.run(api, journal, self.path)
        return api, journal

    def test_duplicate_positions_and_preexisting_target_roundtrip(self):
        plan = make()
        api, journal = self.execute(plan)
        self.assertEqual(api.playlists[P], [V, W, V, V])
        self.assertEqual(api.liked, {U: False, V: True})
        self.assertEqual(journal["status"], "completed")
        self.assertEqual([c[2]["position"] for c in api.calls if c[0] == "POST"], [2, 0])
        m.prepare_rollback(journal)
        m.run(api, journal, self.path)
        self.assertEqual(api.playlists[P], plan["playlists"][P]["before"])
        self.assertEqual(api.liked, plan["liked_before"])
        self.assertEqual(journal["status"], "rolled_back")

    def test_liked_adds_before_removing_and_rollback_removes_new_only(self):
        api, journal = self.execute(make(liked=[U]))
        liked_calls = [(method, parse_qs(urlsplit(path).query)["uris"][0])
                       for method, path, body in api.calls if path.startswith("me/library")]
        self.assertEqual(liked_calls, [("PUT", V), ("DELETE", U)])
        m.prepare_rollback(journal)
        m.run(api, journal, self.path)
        self.assertEqual(api.liked, {U: True, V: False})

    def test_randomized_sequences_preserve_every_occurrence(self):
        rng = random.Random(42)
        for _ in range(100):
            seq = [rng.choice([U, V, W]) for _ in range(rng.randrange(1, 120))] + [U]
            plan = make(seq)
            current = seq[:]
            for op in m.compile_operations(plan):
                if op["resource"] != P:
                    continue
                self.assertEqual(current, op["before"])
                if op["method"] == "POST":
                    current[op["body"]["position"]:op["body"]["position"]] = op["body"]["uris"]
                else:
                    removed = {x["uri"] for x in op["body"]["items"]}
                    current = [u for u in current if u not in removed]
                self.assertEqual(current, op["after"])
            self.assertEqual(current, [V if u == U else u for u in seq])

    def test_development_mode_blocks_even_with_approved_mapping(self):
        plan = make(mode="development")
        self.assertTrue(plan["blocked"])
        with self.assertRaisesRegex(RuntimeError, "blockers"):
            m.compile_operations(plan)

    def test_unapproved_mapping_and_incomplete_scan_block(self):
        plan = make()
        plan["mappings"][0]["approved"] = False
        with self.assertRaisesRegex(RuntimeError, "approved"):
            m.compile_operations(plan)
        snapshot = fixture()
        snapshot["errors"] = ["denied playlist"]
        with self.assertRaisesRegex(RuntimeError, "complete audit"):
            m.make_plan(snapshot, plan["mappings"])

    def test_null_and_local_items_block_entire_affected_playlist(self):
        for field in ("missing", "is_local"):
            snapshot = fixture()
            snapshot["occurrences"][1][field] = True
            plan = m.make_plan(snapshot, make()["mappings"])
            self.assertTrue(plan["blocked"])

    def test_conflicting_mapping_chains_rejected(self):
        mappings = make()["mappings"] + [dict(old_id=NEW, new_id=OTHER, evidence="test")]
        with self.assertRaisesRegex(RuntimeError, "chains"):
            m.make_plan(fixture(), mappings)

    def test_wrong_account_app_and_unplayable_target_stop_before_writes(self):
        for field, value in (("account", "other"), ("client_id", "wrong"), ("playable", False)):
            plan = make()
            api = FakeSpotify(plan)
            setattr(api, field, value)
            with self.assertRaises(RuntimeError):
                m.start_journal(api, plan, self.path)
            self.assertEqual(api.calls, [])

    def test_snapshot_change_even_same_sequence_blocks(self):
        plan = make()
        api = FakeSpotify(plan)
        api.versions[P] += 1
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            m.start_journal(api, plan, self.path)
        self.assertEqual(api.calls, [])

    def test_lost_response_resume_does_not_duplicate_insertion(self):
        plan = make()
        api = FakeSpotify(plan)
        api.fail_after = 1
        journal = m.start_journal(api, plan, self.path)
        with self.assertRaises(OSError):
            m.run(api, journal, self.path)
        saved = m.read(self.path)
        self.assertIsNotNone(saved["pending"])
        m.run(api, saved, self.path)
        self.assertEqual(api.playlists[P], plan["playlists"][P]["after"])
        self.assertEqual(len([x for x in api.calls if x[0] == "POST"]), 2)

    def test_uncertain_write_never_blindly_retried(self):
        plan = make()
        api = FakeSpotify(plan)
        api.fail_before = True
        journal = m.start_journal(api, plan, self.path)
        with self.assertRaises(OSError):
            m.run(api, journal, self.path)
        with self.assertRaisesRegex(RuntimeError, "Pending write"):
            m.run(api, m.read(self.path), self.path)
        self.assertEqual(len(api.calls), 1)
        with self.assertRaisesRegex(RuntimeError, "pending write"):
            m.prepare_rollback(m.read(self.path))

    def test_rollback_large_playlist_uses_100_item_batches(self):
        original = [U] + [W] * 200 + [V]
        api, journal = self.execute(make(original))
        m.prepare_rollback(journal)
        self.assertEqual([len(op["body"]["uris"]) for op in journal["operations"] if op["resource"] == P], [100, 100, 2])
        m.run(api, journal, self.path)
        self.assertEqual(api.playlists[P], original)

    def test_later_edit_blocks_rollback(self):
        api, journal = self.execute(make())
        api.playlists[P].append(W)
        api.versions[P] += 1
        calls = len(api.calls)
        m.prepare_rollback(journal)
        with self.assertRaisesRegex(RuntimeError, "outside the journal"):
            m.run(api, journal, self.path)
        self.assertEqual(len(api.calls), calls)

    def test_noop_resume_of_completed_run_makes_no_writes(self):
        api, journal = self.execute(make())
        calls = len(api.calls)
        m.run(api, journal, self.path)
        self.assertEqual(len(api.calls), calls)

    def test_rejected_request_retains_verified_partial_state_for_rollback(self):
        plan = make()
        api = FakeSpotify(plan)
        original_mutate = api.mutate
        count = 0

        def reject_second(method, path, body):
            nonlocal count
            count += 1
            if count == 2:
                raise m.RejectedWrite("HTTP 429")
            return original_mutate(method, path, body)

        api.mutate = reject_second
        journal = m.start_journal(api, plan, self.path)
        with self.assertRaises(m.RejectedWrite):
            m.run(api, journal, self.path)
        saved = m.read(self.path)
        self.assertIsNone(saved["pending"])
        self.assertEqual(saved["cursor"], 1)
        m.prepare_rollback(saved)
        m.run(api, saved, self.path)
        self.assertEqual(api.playlists[P], plan["playlists"][P]["before"])

    def test_multiple_old_ids_can_share_replacement(self):
        snapshot = fixture([U, W, V, U], [U, W])
        mappings = make()["mappings"] + [dict(old_id=OTHER, new_id=NEW, approved=True, evidence="test")]
        plan = m.make_plan(snapshot, mappings)
        api, journal = self.execute(plan)
        self.assertEqual(api.playlists[P], [V] * 4)
        self.assertEqual(api.liked, {U: False, W: False, V: True})
        m.prepare_rollback(journal)
        m.run(api, journal, self.path)
        self.assertEqual(api.playlists[P], [U, W, V, U])
        self.assertEqual(api.liked, plan["liked_before"])


if __name__ == "__main__":
    unittest.main()
