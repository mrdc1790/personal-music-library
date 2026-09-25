"""Snapshot-backed Spotify migrations. Standard library only; Python 3.11+."""
import argparse
from storage_paths import data_root
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import audit
from spotify_config import spotify_client_id

WRITE_SCOPES = audit.SCOPES + " user-library-modify playlist-modify-private playlist-modify-public"
ID = re.compile(r"[A-Za-z0-9]{22}\Z")
URI = re.compile(r"spotify:(track|episode):[A-Za-z0-9]{22}\Z")


class RejectedWrite(RuntimeError):
    """Spotify explicitly rejected a mutation without applying it."""


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    """Flush journal before sending mutations; replace within the same directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + secrets.token_hex(4) + ".tmp")
    with temp.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def track_uri(track_id):
    require(isinstance(track_id, str) and ID.fullmatch(track_id), "Invalid Spotify track ID.")
    return "spotify:track:" + track_id


def stored_uri(row, mode):
    require(not row.get("missing") and not row.get("is_local"),
            "Affected playlists containing missing or local items need manual recovery planning.")
    if row.get("original_id"):
        return track_uri(row["original_id"])
    require(mode == "extended", "Original IDs are hidden/unknown in Development Mode; writes are blocked.")
    uri = row.get("returned_uri")
    require(isinstance(uri, str) and URI.fullmatch(uri), "Missing or unsupported item URI.")
    return uri


def make_plan(snapshot, mappings):
    """Mappings remain proposals until their approved field is explicitly true."""
    require(snapshot.get("account_id"), "Snapshot lacks account identity.")
    require(snapshot.get("client_id"), "Run a fresh scan with migrate.py to record the app identity.")
    require(not snapshot.get("errors") and snapshot.get("status", "").startswith("completed"),
            "A complete audit is required; resolve failed reads before planning writes.")
    mode = snapshot.get("api_mode", "development")
    proposals = deepcopy(mappings)
    replacements = {}
    for m in proposals:
        old, new = track_uri(m["old_id"]), track_uri(m["new_id"])
        require(old != new and old not in replacements, "Duplicate or self mapping.")
        require(bool(m.get("evidence")), "Every mapping needs evidence for review.")
        replacements[old] = new
        m.setdefault("approved", False)
    require(replacements, "Supply at least one mapping.")
    require(not (set(replacements) & set(replacements.values())), "Mapping chains/cycles are not supported; split into separate scans.")
    blocked = []
    if mode != "extended":
        blocked.append("Development Mode hides linked_from. Plan is for review only; do not relabel the app as Extended Mode.")
    resources = {}
    rows_by_source = {}
    for row in snapshot["occurrences"]:
        rows_by_source.setdefault(row["source"], []).append(row)
    metadata = {p["metadata"]["id"]: p for p in snapshot["playlists"]}
    locations = []
    for source, rows in rows_by_source.items():
        rows.sort(key=lambda r: r["position"])
        affected = [r for r in rows if "spotify:track:" + (r.get("original_id") or r.get("returned_id") or "") in replacements]
        if not affected:
            continue
        locations.extend(dict(source=source, name=r["source_name"], position=r["position"],
                              old_id=r.get("original_id") or r.get("returned_id")) for r in affected)
        if source == "liked":
            continue
        try:
            require([r["position"] for r in rows] == list(range(len(rows))), "Playlist positions are incomplete.")
            p = metadata[source]
            meta = p["metadata"]
            owner = meta.get("owner") or {}
            require(p["exported"] and (owner.get("id") == snapshot["account_id"] or meta.get("collaborative") is True),
                    "Playlist is not confirmed owned/collaborative.")
            require(meta.get("snapshot_id"), "Playlist lacks a snapshot ID.")
            before = [stored_uri(r, mode) for r in rows]
            resources[source] = dict(name=meta.get("name", source), before=before,
                after=[replacements.get(u, u) for u in before], snapshot_id=meta["snapshot_id"])
        except (RuntimeError, KeyError) as error:
            blocked.append(f"{source}: {error}")
    liked_rows = rows_by_source.get("liked", [])
    liked = {}
    for uri in sorted(set(replacements) | set(replacements.values())):
        # With hidden IDs, this is only an observed proposal, never an executable state.
        liked[uri] = any((r.get("original_id") or r.get("returned_id")) == uri.split(":")[-1] for r in liked_rows)
    require(locations, "No observed occurrences of the supplied old IDs; inspect the audit for hidden IDs.")
    return dict(version=1, account_id=snapshot["account_id"], client_id=snapshot["client_id"],
        api_mode=mode, snapshot_hash=digest(snapshot), mappings=proposals, locations=locations,
        playlists=resources, liked_before=liked, blocked=blocked,
        limitations=["No atomic transaction or guaranteed exclusion of concurrent edits.",
            "Replaced items lose original added dates/attribution; Liked Songs dates cannot be restored.",
            "Rollback rebuilds affected playlists, resetting all item dates/attribution; unavailable originals may not be re-addable."])


def operation(resource, method, body, before, after):
    return dict(resource=resource, method=method, body=body, before=deepcopy(before), after=deepcopy(after))


def compile_operations(plan):
    require(plan.get("version") == 1 and plan.get("api_mode") == "extended" and not plan.get("blocked"),
            "Plan has identity/coverage blockers. Review the audit; writes are disabled.")
    require(all(m.get("approved") is True for m in plan["mappings"]), "Each mapping must be reviewed and approved in the mappings file.")
    replacements = {track_uri(m["old_id"]): track_uri(m["new_id"]) for m in plan["mappings"]}
    ops = []
    for source, p in plan["playlists"].items():
        current = p["before"][:]
        for i in range(len(current) - 1, -1, -1):
            if current[i] in replacements:
                uri = replacements[current[i]]
                after = current[:i] + [uri] + current[i:]
                ops.append(operation(source, "POST", dict(uris=[uri], position=i), current, after))
                current = after
        removed = sorted(set(current) & set(replacements))
        for start in range(0, len(removed), 100):
            batch = removed[start:start + 100]
            after = [u for u in current if u not in batch]
            ops.append(operation(source, "DELETE", dict(items=[dict(uri=u) for u in batch]), current, after))
            current = after
        require(current == p["after"], "Internal sequence mismatch.")
    current = deepcopy(plan["liked_before"])
    for old, new in replacements.items():
        if not current[old]:
            continue
        if not current[new]:
            after = dict(current, **{new: True})
            ops.append(operation("liked", "PUT", dict(uri=new), current, after))
            current = after
    for old in replacements:
        if current[old]:
            after = dict(current, **{old: False})
            ops.append(operation("liked", "DELETE", dict(uri=old), current, after))
            current = after
    require(ops, "Plan contains no changes.")
    return ops


class Writer(audit.Spotify):
    def mutate(self, method, path, body):
        # A read refreshes expiring tokens. Mutations are deliberately never retried here.
        self.get("me")
        require(path.startswith("playlists/") or path.startswith("me/library?"), "Unexpected write endpoint.")
        request = Request(audit.API + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + self.tokens["access_token"], "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=45) as response:
                data = response.read()
                return json.loads(data) if data else {}
        except HTTPError as error:
            if error.code in (400, 401, 403, 404, 429):
                raise RejectedWrite(f"Write rejected (HTTP {error.code}). Fix access/input or wait for the rate limit before resuming.") from None
            raise RuntimeError(f"Write HTTP {error.code}; journal retained. No automatic retry.") from None


def observe(api, resource, plan):
    if resource == "liked":
        uris = sorted(plan["liked_before"])
        state = {}
        for i in range(0, len(uris), 40):
            batch = uris[i:i + 40]
            values = api.get("me/library/contains?" + urlencode(dict(uris=",".join(batch))))
            require(isinstance(values, list) and len(values) == len(batch) and all(type(v) is bool for v in values),
                    "Invalid library contains response.")
            state.update(zip(batch, values))
        return state, None
    meta, entries = audit.stable_playlist(api, resource)
    rows = [audit.occurrence(resource, meta.get("name", resource), i, entry) for i, entry in enumerate(entries)]
    return [stored_uri(r, plan["api_mode"]) for r in rows], meta["snapshot_id"]


def verify_account(api, plan):
    me = api.get("me")
    require(me.get("account_id", me.get("id")) == plan["account_id"], "Signed in to a different account.")
    require(api.client_id == plan["client_id"], "Use the same Spotify app as the snapshot.")


def preflight(api, plan):
    verify_account(api, plan)
    for m in plan["mappings"]:
        track = api.get(f"tracks/{m['new_id']}?market=from_token")
        require(track.get("id") == m["new_id"] and track.get("is_playable") is True and not track.get("linked_from"),
                "Replacement is not confirmed playable as the exact requested ID.")
    for resource, p in plan["playlists"].items():
        state, version = observe(api, resource, plan)
        require(state == p["before"] and version == p["snapshot_id"], f"{resource}: playlist changed since scan.")
    state, _ = observe(api, "liked", plan)
    require(state == plan["liked_before"], "Liked Songs differ from the plan (or Spotify aliases the IDs).")


def start_journal(api, plan, path):
    ops = compile_operations(plan)
    require(not Path(path).exists(), "Journal already exists. Use resume or a new journal path.")
    preflight(api, plan)
    journal = dict(version=1, plan=deepcopy(plan), plan_hash=digest(plan), operations=ops,
        cursor=0, pending=None, status="running", direction="apply", history=[],
        versions={r: p["snapshot_id"] for r, p in plan["playlists"].items()},
        current={**{r: p["before"] for r, p in plan["playlists"].items()}, "liked": plan["liked_before"]})
    save(path, journal)
    return journal


def run(api, journal, path):
    plan = journal["plan"]
    require(digest(plan) == journal["plan_hash"], "Journal plan was modified.")
    require(journal["status"] != "rolled_back", "This run was already rolled back.")
    verify_account(api, plan)
    # Check all resources, including previously finished playlists, on every resume.
    for resource, expected in journal["current"].items():
        if journal.get("pending") and resource == journal["pending"]["resource"]:
            continue
        actual, version = observe(api, resource, plan)
        require(actual == expected and (resource == "liked" or version == journal["versions"][resource]),
                f"{resource}: changed outside the journal; stop for manual reconciliation.")
    while journal["cursor"] < len(journal["operations"]):
        op = journal["operations"][journal["cursor"]]
        resource = op["resource"]
        actual, version = observe(api, resource, plan)
        if journal.get("pending"):
            # A timeout may have succeeded. Never blindly resend a pending mutation.
            require(actual == op["after"], "Pending write cannot be confirmed. Do not retry blindly; inspect the journal and account.")
            response_version = journal["pending"].get("response_snapshot")
            require(not response_version or response_version == version, "Playlist changed after the pending response.")
        else:
            require(actual == op["before"] and (resource == "liked" or version == journal["versions"][resource]),
                    f"{resource}: changed before write; stopped.")
            journal["pending"] = dict(resource=resource, cursor=journal["cursor"], before_snapshot=version)
            save(path, journal)
            body = deepcopy(op["body"])
            if resource == "liked":
                endpoint = "me/library?" + urlencode(dict(uris=body["uri"]))
                body = None
            else:
                endpoint = f"playlists/{resource}/items"
                if op["method"] == "DELETE":
                    body["snapshot_id"] = version
            try:
                response = api.mutate(op["method"], endpoint, body)
            except RejectedWrite:
                journal["pending"] = None
                save(path, journal)
                raise
            if resource != "liked":
                require(response.get("snapshot_id"), "Write response omitted snapshot ID; inspect before resuming.")
                journal["pending"]["response_snapshot"] = response["snapshot_id"]
            save(path, journal)
            actual, version = observe(api, resource, plan)
            require(actual == op["after"], "Write verification failed; journal retained for recovery.")
            require(resource == "liked" or version == response["snapshot_id"], "Concurrent playlist edit detected after write.")
        journal["history"].append(dict(direction=journal["direction"], operation=op,
            snapshot_id=version, verified_at=datetime.now(timezone.utc).isoformat()))
        journal["current"][resource] = actual
        if resource != "liked":
            journal["versions"][resource] = version
        journal["pending"] = None
        journal["cursor"] += 1
        save(path, journal)
    for resource, expected in journal["current"].items():
        actual, version = observe(api, resource, plan)
        require(actual == expected and (resource == "liked" or version == journal["versions"][resource]),
                f"{resource}: final verification failed.")
    journal["status"] = "completed" if journal["direction"] == "apply" else "rolled_back"
    save(path, journal)


def prepare_rollback(journal):
    require(not journal.get("pending"), "Reconcile the pending write before rollback; resume can recognize a completed write.")
    require(journal["direction"] == "apply", "Rollback already started; use resume.")
    ops = []
    plan = journal["plan"]
    for resource, p in plan["playlists"].items():
        current, original = journal["current"][resource], p["before"]
        if current == original:
            continue
        after = original[:100]
        ops.append(operation(resource, "PUT", dict(uris=after), current, after))
        current = after
        for i in range(100, len(original), 100):
            batch = original[i:i + 100]
            after = current + batch
            ops.append(operation(resource, "POST", dict(uris=batch, position=len(current)), current, after))
            current = after
    current = deepcopy(journal["current"]["liked"])
    # Restore originals first; preserve replacements that were already saved.
    for wanted, method in ((True, "PUT"), (False, "DELETE")):
        for uri, value in plan["liked_before"].items():
            if value is wanted and current[uri] != value:
                after = dict(current, **{uri: value})
                ops.append(operation("liked", method, dict(uri=uri), current, after))
                current = after
    journal.update(operations=ops, cursor=0, direction="rollback", status="running")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Read-only JSON/SQLite snapshot and HTML audit")
    scan.add_argument("--client-id", help="Overrides SPOTIFY_CLIENT_ID from the environment or .env")
    scan.add_argument("--api-mode", choices=["development", "extended"], default="development",
                      help="Actual Spotify app quota mode; extended is not a workaround for hidden IDs")
    scan.add_argument("--output", type=Path, default=data_root() / "backups")
    plan = sub.add_parser("plan", help="Offline review plan from a snapshot and mapping file")
    plan.add_argument("--snapshot", type=Path, required=True)
    plan.add_argument("--mappings", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    for command in ("apply", "resume", "rollback"):
        p = sub.add_parser(command)
        p.add_argument("--journal", type=Path, required=True)
        p.add_argument("--execute", action="store_true", help="Allow account writes after reviewing the plan")
        if command == "apply":
            p.add_argument("--plan", type=Path, required=True)
        if command == "rollback":
            p.add_argument("--accept-metadata-reset", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "scan":
            client_id = spotify_client_id(args.client_id)
            api = audit.Spotify(client_id, audit.authorize(client_id))
            folder = args.output / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3))
            result = audit.scan(api, folder, args.api_mode)
            print("Report:", folder.resolve() / "report.html")
            return 2 if result["errors"] else 0
        if args.command == "plan":
            require(not args.output.exists(), "Choose a new output filename to preserve prior plans.")
            result = make_plan(read(args.snapshot), read(args.mappings))
            save(args.output, result)
            print(f"Plan: {args.output.resolve()}\nOccurrences: {len(result['locations'])}\nBlockers: {result['blocked']}")
            return 2 if result["blocked"] else 0
        plan = read(args.plan) if args.command == "apply" else read(args.journal)["plan"]
        if args.command == "apply":
            ops = compile_operations(plan)
        else:
            journal = read(args.journal)
            if args.command == "rollback":
                require(args.accept_metadata_reset, "Rollback rewrites affected playlists and resets all item dates/attribution. Use --accept-metadata-reset after review.")
                prepare_rollback(journal)
            ops = journal["operations"][journal["cursor"]:]
        print(f"Account: {plan['account_id']} | {len(ops)} remaining writes | limitations: " + "; ".join(plan["limitations"]))
        if not args.execute:
            print("Dry run only. No login or Spotify writes. Add --execute after review.")
            return 0
        # Prevent concurrent writers using this journal; stale locks require investigation.
        lock = args.journal.with_suffix(args.journal.suffix + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("x") as stream:
            stream.write(str(os.getpid()))
        try:
            api = Writer(plan["client_id"], audit.authorize(plan["client_id"], WRITE_SCOPES))
            if args.command == "apply":
                journal = start_journal(api, plan, args.journal)
            elif args.command == "rollback":
                save(args.journal, journal)
            run(api, journal, args.journal)
            print(journal["status"])
        finally:
            lock.unlink()
        return 0
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print("Stopped:", error)
        print("Any write journal is retained. Inspect it before attempting recovery.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
