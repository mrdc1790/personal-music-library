"""Read-only Spotify library audit. Python 3.11+, no third-party packages.

No Spotify library mutation endpoints or write scopes are used.
Tokens live only in process memory. JSON/SQLite exports contain library data.
"""
import argparse
from contextlib import closing
import base64
import hashlib
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
import webbrowser
from datetime import datetime, timezone

API = "https://api.spotify.com/v1/"
REDIRECT = "http://127.0.0.1:8765/callback"
SCOPES = "user-library-read playlist-read-private playlist-read-collaborative"
OLD = "623tFk37Yd1PBpo926WiLu"
NEW = "6Q0c6AP55HK2tGqYFSPTxq"


def token_request(fields):
    req = Request("https://accounts.spotify.com/api/token",
                  data=urlencode(fields).encode(), method="POST")
    try:
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Spotify sign-in failed (HTTP {error.code}). Check the Client ID and redirect URI.") from None


def authorize(client_id, scopes=SCOPES):
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # OAuth codes must never enter access logs.

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid = (parsed.path == "/callback" and
                     secrets.compare_digest(params.get("state", [""])[0], state))
            if not valid:
                self.send_error(400, "Invalid sign-in response")
                return
            result.update({key: values[0] for key, values in params.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"Sign-in response received. Return to the audit window. You may close this tab.")

    params = dict(client_id=client_id, response_type="code", redirect_uri=REDIRECT,
                  scope=scopes, state=state, code_challenge_method="S256", code_challenge=challenge)
    with HTTPServer(("127.0.0.1", 8765), Callback) as server:
        server.timeout = 1
        url = "https://accounts.spotify.com/authorize?" + urlencode(params)
        print("Review Spotify access in your browser. Requested scopes: " + scopes, flush=True)
        print("If the browser does not open, open this sign-in link:\n" + url, flush=True)
        webbrowser.open(url)
        deadline = time.monotonic() + 600
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if "code" not in result:
        raise RuntimeError("Sign-in was declined or timed out.")
    return token_request(dict(grant_type="authorization_code", code=result["code"],
                              redirect_uri=REDIRECT, client_id=client_id, code_verifier=verifier))


class Spotify:
    def __init__(self, client_id, tokens):
        self.client_id = client_id
        self.tokens = tokens
        self.expires = time.monotonic() + tokens.get("expires_in", 3600) - 60

    def get(self, path):
        url = path if path.startswith("https://") else API + path.lstrip("/")
        if not url.startswith(API):
            raise RuntimeError("Refusing an unexpected pagination destination.")
        for attempt in range(5):
            if time.monotonic() >= self.expires:
                refreshed = token_request(dict(grant_type="refresh_token",
                    refresh_token=self.tokens["refresh_token"], client_id=self.client_id))
                self.tokens.update(refreshed)
                self.expires = time.monotonic() + refreshed.get("expires_in", 3600) - 60
            req = Request(url, headers={"Authorization": "Bearer " + self.tokens["access_token"]})
            try:
                with urlopen(req, timeout=45) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code in (500, 502, 503, 504):
                    if attempt < 4:
                        delay = 2 ** (attempt + 1)
                        print(f"Spotify server error HTTP {error.code}; retrying this read in {delay} seconds.", flush=True)
                        time.sleep(delay)
                        continue
                    raise RuntimeError(f"Spotify server error HTTP {error.code} reading {urlsplit(url).path} "
                                       "after retries. Try the audit again later; this does not mean your library is empty.") from None
                if error.code == 429 and attempt < 4:
                    delay = max(1, int(error.headers.get("Retry-After", "5")))
                    if delay > 60:
                        raise RuntimeError(f"Spotify rate limit: retry in {delay} seconds. Partial backup retained.") from None
                    print(f"Spotify rate limit; waiting {delay} seconds.", flush=True)
                    time.sleep(delay)
                    continue
                if error.code == 401 and attempt == 0 and "refresh_token" in self.tokens:
                    self.expires = 0
                    continue
                raise RuntimeError(f"Spotify HTTP {error.code} reading {urlsplit(url).path}. "
                                   "Check app access, Premium status, and permissions.") from None
        raise RuntimeError("Spotify request retry limit reached.")


def iter_pages(api, path):
    seen, count = set(), 0
    expected = None
    while path:
        if path in seen:
            raise RuntimeError("Pagination repeated a page; scan is incomplete.")
        seen.add(path)
        page = api.get(path)
        if not isinstance(page.get("items"), list):
            raise RuntimeError("Spotify omitted the items array; cannot call this a complete export.")
        if expected is None:
            expected = page.get("total")
        elif page.get("total") != expected:
            raise RuntimeError("Library changed during pagination. Run a fresh scan.")
        for item in page["items"]:
            count += 1
            yield item
        path = page.get("next")
    if expected is not None and count != expected:
        raise RuntimeError("Export count differs from Spotify's total. Run a fresh scan.")


def pages(api, path):
    return list(iter_pages(api, path))


class DiskRows(list):
    """Replayable JSON list backed by SQLite, with at most one decoded row in RAM.

    list inheritance lets json.dump stream this collection using its list encoder.
    Never use json.dumps on it: that would assemble the entire output in memory.
    """
    def __init__(self, path):
        self.path = Path(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS occurrences (source TEXT, position INTEGER, returned_id TEXT, original_id TEXT, data TEXT, PRIMARY KEY(source,position))")
            db.execute("CREATE INDEX IF NOT EXISTS returned_lookup ON occurrences(returned_id)")
            db.execute("CREATE INDEX IF NOT EXISTS original_lookup ON occurrences(original_id)")

    def __len__(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]

    def __iter__(self):
        with closing(sqlite3.connect(self.path)) as db:
            for (data,) in db.execute("SELECT data FROM occurrences ORDER BY rowid"):
                yield json.loads(data)

    def extend(self, rows):
        # Commit a complete source only. A pagination failure rolls it back.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("INSERT INTO occurrences VALUES (?,?,?,?,?)", (
                (r["source"], r["position"], r["returned_id"], r["original_id"],
                 json.dumps(r, ensure_ascii=False)) for r in rows))


def occurrence(source, name, position, entry):
    track = entry.get("item") if "item" in entry else entry.get("track")
    track = track or {}
    linked = track.get("linked_from") or {}
    # A returned ID is NOT evidence of the originally stored ID when linked_from is missing.
    return dict(source=source, source_name=name, position=position,
                returned_id=track.get("id"), original_id=linked.get("id"),
                returned_uri=track.get("uri"), title=track.get("name"),
                artists=[a.get("name") for a in track.get("artists", [])],
                artist_ids=[a.get("id") for a in track.get("artists", [])],
                isrc=(track.get("external_ids") or {}).get("isrc"),
                duration_ms=track.get("duration_ms"), explicit=track.get("explicit"),
                is_playable=track.get("is_playable"),
                is_local=entry.get("is_local", track.get("is_local", False)),
                missing=not bool(track), added_at=entry.get("added_at"),
                added_by=entry.get("added_by"), raw=entry)


def stable_playlist(api, playlist_id):
    for _ in range(3):
        before = api.get(f"playlists/{playlist_id}")
        rows = pages(api, f"playlists/{playlist_id}/items?limit=50&market=from_token")
        after = api.get(f"playlists/{playlist_id}")
        if before.get("snapshot_id") and before["snapshot_id"] == after.get("snapshot_id"):
            return after, rows
    raise RuntimeError("Playlist kept changing while it was being read. Scan again while no one is editing it.")


def migration_plan(occurrences):
    evidence = {}
    for row in occurrences:
        old, new = row["original_id"], row["returned_id"]
        if old and new and old != new:
            evidence.setdefault((old, new), []).append(dict(source=row["source"],
                source_name=row["source_name"], position=row["position"]))
    mappings = [dict(old_id=old, new_id=new, evidence="Spotify linked_from", occurrences=locations,
                     status="proposal_only") for (old, new), locations in evidence.items()]
    mappings.append(dict(old_id=OLD, new_id=NEW, evidence="User-supplied shared answer; not independently validated",
        status="needs_account_evidence", observed_locations=[
            dict(source=r["source"], source_name=r["source_name"], position=r["position"],
                 returned_id=r["returned_id"], original_id=r["original_id"])
            for r in occurrences if r["returned_id"] in (OLD, NEW) or r["original_id"] == OLD]))
    return dict(apply_enabled=False, reason="Original stored IDs may be hidden in Development Mode. "
                "Resolve identity and verify account behavior before implementing writes.", mappings=mappings)


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temp.replace(path)


def export_report(folder, snapshot, checkpoint_only=False):
    rows = snapshot["occurrences"]
    with closing(sqlite3.connect(folder / "library.sqlite")) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS occurrences (source TEXT, position INTEGER, returned_id TEXT, original_id TEXT, data TEXT, PRIMARY KEY(source,position))")
        if not isinstance(rows, DiskRows):
            db.execute("DELETE FROM occurrences")
            db.executemany("INSERT INTO occurrences VALUES (?,?,?,?,?)", (
                (r["source"], r["position"], r["returned_id"], r["original_id"], json.dumps(r)) for r in rows))
        db.execute("CREATE INDEX IF NOT EXISTS returned_lookup ON occurrences(returned_id)")
        db.execute("CREATE INDEX IF NOT EXISTS original_lookup ON occurrences(original_id)")
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, data TEXT)")
        db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", ("snapshot", json.dumps({k:v for k,v in snapshot.items() if k != "occurrences"})))
    if checkpoint_only:
        return
    write_json(folder / "snapshot.json", snapshot)
    write_json(folder / "migration-plan.json", migration_plan(rows))
    esc = lambda value: html.escape(str(value if value is not None else "Unknown"))
    errors = "".join(f"<li>{esc(e)}</li>" for e in snapshot["errors"])
    report = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Spotify library audit</title><style>body{{font:17px system-ui;background:#101916;color:#ecf4ef;max-width:1100px;margin:50px auto;padding:24px}}h1{{font-size:42px}}.note{{background:#22342b;padding:20px;border-radius:12px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #446052;overflow-wrap:anywhere}}code{{overflow-wrap:anywhere}}</style>
<p>SPOTIFY SHADOW TRACK MIGRATION / READ-ONLY AUDIT</p><h1>Your library, before any changes.</h1>
<p>{len(rows)} occurrences exported. Scan status: <strong>{esc(snapshot['status'])}</strong>.</p>
<div class="note">No Spotify songs or playlists were changed. Original IDs marked Unknown may be hidden by Spotify's API. An empty issue list does not mean your library has no shadowed songs.</div>
<h2>Items to investigate</h2><p>Positions below start at 1; saved JSON and SQLite positions start at 0. Local files and missing entries stay in the backup.</p>
<table><thead><tr><th>Location</th><th>Position</th><th>Title</th><th>Returned ID</th><th>Original ID evidence</th></tr></thead><tbody>ROW_CONTENT</tbody></table>
<h2>Scan notes</h2><ul>{errors or '<li>No request errors recorded.</li>'}</ul>
<p>API snapshots preserve what Spotify returned, not necessarily the original underlying IDs. Liked Songs have no snapshot token; avoid edits during the scan.</p>
<h2>Next step</h2><p>Review the 2 Busy mapping and confirmed relinks, then use migrate.py plan with a reviewed mappings file. The separate migration command provides apply, resume, and rollback. Development Mode snapshots remain review-only because original IDs can be hidden. This audit never requests write access.</p>
<p>Files alongside this report: snapshot.json (raw data), library.sqlite (searchable backup), migration-plan.json (proposals).</p></html>"""
    head, tail = report.split("ROW_CONTENT", 1)
    temp = folder / "report.html.tmp"
    with temp.open("w", encoding="utf-8") as stream:
        stream.write(head)
        for r in rows:
            if r["missing"] or r["is_playable"] is False or r["original_id"] or r["returned_id"] in (OLD, NEW):
                stream.write(f"<tr><td>{esc(r['source_name'])}</td><td>{r['position']+1}</td>"
                             f"<td>{esc(r['title'])}</td><td>{esc(r['returned_id'])}</td>"
                             f"<td>{esc(r['original_id'])}</td></tr>")
        stream.write(tail)
    temp.replace(folder / "report.html")


def scan(api, folder, api_mode="development"):
    folder.mkdir(parents=True, exist_ok=False)
    snapshot = dict(created_at=datetime.now(timezone.utc).isoformat(), status="incomplete",
                    occurrences=DiskRows(folder / "library.sqlite"), playlists=[], errors=[], track_checks={},
                    api_mode=api_mode, client_id=getattr(api, "client_id", None))
    try:
        me = api.get("me")
        snapshot["account_id"] = me.get("account_id", me.get("id"))
        print("Backing up Liked Songs...", flush=True)
        liked = iter_pages(api, "me/tracks?limit=50&market=from_token")
        snapshot["occurrences"].extend(occurrence("liked", "Liked Songs", i, x) for i, x in enumerate(liked))
        export_report(folder, snapshot, checkpoint_only=True)
        playlists = pages(api, "me/playlists?limit=50")
        for p in playlists:
            print("Reading playlist: " + p.get("name", p["id"]), flush=True)
            try:
                meta, entries = stable_playlist(api, p["id"])
                snapshot["occurrences"].extend(occurrence(p["id"], p.get("name", p["id"]), i, x)
                                               for i, x in enumerate(entries))
                snapshot["playlists"].append(dict(metadata=meta, exported=True))
                del entries
            except RuntimeError as error:
                snapshot["playlists"].append(dict(metadata=p, exported=False))
                snapshot["errors"].append(p.get("name", p["id"]) + ": " + str(error))
            export_report(folder, snapshot, checkpoint_only=True)
            print(f"Saved {len(snapshot['occurrences']):,} placements to disk.", flush=True)
        for track_id in (OLD, NEW):
            try:
                snapshot["track_checks"][track_id] = api.get(f"tracks/{track_id}?market=from_token")
            except RuntimeError as error:
                snapshot["errors"].append(f"Example track {track_id}: {error}")
        snapshot["status"] = "partial" if snapshot["errors"] else "completed API export; hidden original IDs remain unknown"
    except Exception as error:
        snapshot["errors"].append(str(error) or type(error).__name__)
        raise
    finally:
        print("Writing final JSON and HTML exports from the saved database...", flush=True)
        export_report(folder, snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", help="Public Spotify app Client ID; never a Client Secret")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "backups")
    args = parser.parse_args()
    client_id = args.client_id or input("Paste your Spotify app Client ID (not Client Secret): ").strip()
    if len(client_id) != 32 or any(c not in "0123456789abcdefABCDEF" for c in client_id):
        parser.error("Expected a 32-character hexadecimal Client ID.")
    folder = args.output.resolve() / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3))
    try:
        api = Spotify(client_id, authorize(client_id))
        print(f"Saving library backup to {folder}", flush=True)
        result = scan(api, folder)
        print("\n" + result["status"] + "\nReport: " + str(folder / "report.html"), flush=True)
        webbrowser.open((folder / "report.html").as_uri())
        return 0 if not result["errors"] else 2
    except (RuntimeError, OSError, ValueError, MemoryError) as error:
        print("Stopped: " + (str(error) or type(error).__name__))
        print("No Spotify changes were made. Any completed backup stages are in " + str(folder))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
