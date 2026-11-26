"""Offline music catalog: import audit snapshots, query memberships, export and back up.

This module has no network or Spotify mutation code. It stores observed identities;
matching a URI is not a claim that two releases represent the same recording.
"""
import argparse
from storage_paths import data_root
from collections import Counter, defaultdict
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

import availability
import checkpoint_export
import playlist_capacity
import song_stats
import track_metadata
import stream_counts

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots (
 id INTEGER PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
 account_id TEXT NOT NULL, created_at TEXT, status TEXT NOT NULL, raw_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS playlists (
 snapshot_id INTEGER NOT NULL REFERENCES snapshots(id), source TEXT NOT NULL,
 name TEXT NOT NULL, exported INTEGER NOT NULL, metadata_json TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,source));
CREATE TABLE IF NOT EXISTS items (
 snapshot_id INTEGER NOT NULL, source TEXT NOT NULL, position INTEGER NOT NULL,
 track_key TEXT NOT NULL, identity_basis TEXT NOT NULL, title TEXT, artists TEXT,
 returned_uri TEXT, returned_id TEXT, original_id TEXT, is_local INTEGER NOT NULL,
 missing INTEGER NOT NULL, playable INTEGER, album TEXT, duration_ms INTEGER,
 isrc TEXT, added_at TEXT, raw_json TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,source,position),
 FOREIGN KEY(snapshot_id,source) REFERENCES playlists(snapshot_id,source));
CREATE INDEX IF NOT EXISTS item_lookup ON items(snapshot_id,track_key);
CREATE TABLE IF NOT EXISTS song_ratings (
 track_key TEXT PRIMARY KEY, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5));
CREATE VIEW IF NOT EXISTS membership AS
 SELECT snapshot_id,track_key,source,COUNT(*) AS occurrence_count
 FROM items WHERE missing=0 GROUP BY snapshot_id,track_key,source;
"""


def connect(path, write=False):
    path = Path(path).resolve()
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
    else:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    if write:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and "catalog_meta" not in tables:
            db.close()
            raise ValueError("Use a new catalog filename; this is another database (possibly the per-scan audit DB).")
        db.executescript(SCHEMA)
        db.execute("INSERT OR IGNORE INTO catalog_meta VALUES ('schema_version','1')")
        db.commit()
    version = db.execute("SELECT value FROM catalog_meta WHERE key='schema_version'").fetchone()
    if not version or version[0] != "1":
        db.close()
        raise ValueError("Unsupported catalog schema.")
    return db


def identity(row, snapshot_hash):
    if row.get("missing"):
        return f"unknown:{snapshot_hash}:{row['source']}:{row['position']}", "unidentified"
    if row.get("is_local"):
        uri = row.get("returned_uri")
        if uri:
            return uri, "local_metadata_reference"
        return f"unknown:{snapshot_hash}:{row['source']}:{row['position']}", "unidentified"
    if row.get("original_id"):
        return "spotify:track:" + row["original_id"], "original_id_evidence"
    if row.get("returned_uri"):
        return row["returned_uri"], "returned_uri_only"
    if row.get("returned_id"):
        return "spotify:track:" + row["returned_id"], "returned_id_only"
    return f"unknown:{snapshot_hash}:{row['source']}:{row['position']}", "unidentified"


def import_snapshot(db, snapshot, label):
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    checksum = hashlib.sha256(raw.encode()).hexdigest()
    previous = db.execute("SELECT id FROM snapshots WHERE sha256=?", (checksum,)).fetchone()
    if previous:
        return previous[0]
    account = snapshot.get("account_id")
    if not account or not isinstance(snapshot.get("occurrences"), list):
        raise ValueError("Expected an audit snapshot with account_id and occurrences.")
    accounts = {r[0] for r in db.execute("SELECT DISTINCT account_id FROM snapshots")}
    if accounts and accounts != {account}:
        raise ValueError("Use a separate catalog for a different account (including synthetic examples).")
    with db:
        sid = db.execute("INSERT INTO snapshots(sha256,label,account_id,created_at,status,raw_json) VALUES (?,?,?,?,?,?)",
            (checksum, label, account, snapshot.get("created_at"), snapshot.get("status", "unknown"), raw)).lastrowid
        # New audits explicitly report source coverage; older partial scans reached likes first.
        legacy_liked_complete = snapshot.get("status", "") == "partial" or snapshot.get("status", "").startswith("completed")
        liked_complete = snapshot.get("liked_exported", legacy_liked_complete)
        sources = {"liked": ("Liked Songs", int(liked_complete), {})}
        for p in snapshot.get("playlists", []):
            meta = p["metadata"]
            source = meta["id"]
            if source in sources:
                raise ValueError("Duplicate source in snapshot.")
            sources[source] = (meta.get("name", source), int(bool(p.get("exported"))), meta)
        for row in snapshot["occurrences"]:
            if row["source"] not in sources:
                raise ValueError("Occurrence refers to a playlist absent from snapshot metadata.")
        for source, (name, exported, meta) in sources.items():
            db.execute("INSERT INTO playlists VALUES (?,?,?,?,?)", (sid, source, name, exported, json.dumps(meta)))
        positions = defaultdict(list)
        for row in snapshot["occurrences"]:
            source, pos = row["source"], row["position"]
            if type(pos) is not int or pos < 0:
                raise ValueError("Positions must be nonnegative integers.")
            positions[source].append(pos)
            key, basis = identity(row, checksum)
            entry = row.get("raw") or {}
            track = (entry.get("item") if "item" in entry else entry.get("track")) or {}
            album = (track.get("album") or {}).get("name")
            db.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                sid, source, pos, key, basis, row.get("title"), json.dumps(row.get("artists") or [], ensure_ascii=False),
                row.get("returned_uri"), row.get("returned_id"), row.get("original_id"),
                int(bool(row.get("is_local"))), int(bool(row.get("missing"))), row.get("is_playable"),
                album, row.get("duration_ms"), row.get("isrc"), row.get("added_at"), json.dumps(row, ensure_ascii=False)))
        for source, values in positions.items():
            if sorted(values) != list(range(len(values))):
                raise ValueError(f"Non-contiguous positions in {source}; import rolled back.")
    return sid


def snapshot_id(db, sid=None):
    if sid is None:
        row = db.execute("SELECT MAX(id) FROM snapshots").fetchone()
        sid = row[0]
    if not sid or not db.execute("SELECT 1 FROM snapshots WHERE id=?", (sid,)).fetchone():
        raise ValueError("Snapshot not found; import a snapshot first.")
    return sid


def sources(db, sid):
    return [dict(r) for r in db.execute("SELECT p.source,p.name,p.exported,COUNT(i.position) AS occurrences "
        "FROM playlists p LEFT JOIN items i USING(snapshot_id,source) WHERE p.snapshot_id=? "
        "GROUP BY p.source,p.name,p.exported ORDER BY p.source", (sid,))]


def rows(db, sid):
    return [dict(r) for r in db.execute("SELECT * FROM items WHERE snapshot_id=? ORDER BY source,position", (sid,))]


def song_ratings(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='song_ratings'").fetchone():
        return {}
    return dict(db.execute("SELECT track_key,rating FROM song_ratings"))


def import_ratings(db, document):
    if (not isinstance(document, dict) or document.get("format") != "personal-music-library-ratings-1"
            or not isinstance(document.get("account"), str)
            or not isinstance(document.get("changes"), list) or not document["changes"]):
        raise ValueError("Expected a downloaded catalog rating changes file.")
    keys = set()
    with db:
        db.execute("BEGIN IMMEDIATE")
        if {r[0] for r in db.execute("SELECT DISTINCT account_id FROM snapshots")} != {document.get("account")}:
            raise ValueError("Rating changes belong to a different catalog account.")
        ratings = song_ratings(db)
        updated = 0
        for change in document["changes"]:
            if not isinstance(change, dict) or set(change) != {"track_key", "before", "rating"}:
                raise ValueError("Invalid rating change.")
            key, before, rating = change["track_key"], change["before"], change["rating"]
            if not isinstance(key, str) or key in keys or any(
                    value is not None and (type(value) is not int or not 1 <= value <= 5)
                    for value in (before, rating)):
                raise ValueError("Invalid or duplicate rating change.")
            keys.add(key)
            if not db.execute("SELECT 1 FROM items WHERE snapshot_id IN (SELECT id FROM snapshots) "
                              "AND track_key=? AND identity_basis!='unidentified' LIMIT 1", (key,)).fetchone():
                raise ValueError("A rating refers to an unobserved or unidentified track.")
            current = ratings.get(key)
            if current == rating:
                continue
            if current != before:
                raise ValueError("A saved rating changed since this view was generated. Reload the catalog and retry.")
            if rating is None:
                db.execute("DELETE FROM song_ratings WHERE track_key=?", (key,))
            else:
                db.execute("INSERT INTO song_ratings VALUES (?,?) "
                           "ON CONFLICT(track_key) DO UPDATE SET rating=excluded.rating", (key, rating))
            updated += 1
    return dict(updated_ratings=updated)


def lookup(db, sid, term):
    term = term.casefold()
    names = {p["source"]: p["name"] for p in sources(db, sid)}
    return [dict(r, playlist_name=names[r["source"]]) for r in rows(db, sid)
            if term in " ".join(str(r.get(k) or "") for k in
                ("track_key", "title", "artists", "returned_id", "original_id")).casefold()]


def set_query(db, sid, operation, selected):
    if len(selected) < 2 or len(set(selected)) != len(selected):
        raise ValueError("Provide at least two distinct playlist/source IDs.")
    coverage = {p["source"]: p["exported"] for p in sources(db, sid)}
    if any(not coverage.get(source) for source in selected):
        raise ValueError("A requested playlist was not exported or does not exist. Use playlists to inspect coverage.")
    sets, details = {source: set() for source in selected}, {}
    for row in rows(db, sid):
        if row["source"] in sets and row["identity_basis"] != "unidentified":
            sets[row["source"]].add(row["track_key"])
            details.setdefault(row["track_key"], row)
    first, *rest = [sets[s] for s in selected]
    if operation == "union":
        result = first.union(*rest)
    elif operation == "intersection":
        result = first.intersection(*rest)
    elif operation == "difference":
        result = first.difference(*rest)
    else:
        raise ValueError("Unknown set operation.")
    return [dict(track_key=key, title=details[key]["title"], artists=details[key]["artists"],
                 source_count=sum(key in values for values in sets.values())) for key in sorted(result)]


def compare(db, before, after):
    result = []
    left, right = {p["source"]: p for p in sources(db, before)}, {p["source"]: p for p in sources(db, after)}
    a, b = defaultdict(list), defaultdict(list)
    for sid, target in ((before, a), (after, b)):
        for row in rows(db, sid):
            target[row["source"]].append(row)
    for source in sorted(set(left) | set(right)):
        if source not in left or source not in right or not left[source]["exported"] or not right[source]["exported"]:
            result.append(dict(source=source, status="coverage_changed_or_unknown", note="Not evidence of song deletion."))
            continue
        if any(r["identity_basis"] == "unidentified" for r in a[source] + b[source]):
            result.append(dict(source=source, status="unidentified_items", note="Exact identity comparison unavailable."))
            continue
        old, new = [r["track_key"] for r in a[source]], [r["track_key"] for r in b[source]]
        old_counts, new_counts = Counter(old), Counter(new)
        removed = old_counts - new_counts
        result.append(dict(source=source, status="changed" if old != new or left[source]["name"] != right[source]["name"] else "unchanged",
            added_occurrences=dict(new_counts - old_counts), removed_occurrences=dict(removed),
            remaining_occurrences_for_removed_keys={key: new_counts[key] for key in removed},
            sequence_changed=old != new, name_before=left[source]["name"], name_after=right[source]["name"]))
    return result


def csv_value(value):
    value = "" if value is None else str(value)
    # Spreadsheet-facing exports; exact originals remain in SQLite/raw JSON.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def write_csv(path, columns, records):
    with Path(path).open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in columns} for row in records)


def artist_summary(items):
    grouped = {}
    for row in items:
        original = json.loads(row["raw_json"])
        names, ids = original.get("artists") or [], original.get("artist_ids") or []
        seen = set()
        for index, name in enumerate(names):
            artist_id = ids[index] if index < len(ids) else None
            # Never merge text-only local artists into Spotify artists with the same name.
            key = "spotify:artist:" + artist_id if artist_id else "unmatched-name:" + str(name)
            if key in seen:
                continue
            seen.add(key)
            pair = (key, row["source"])
            value = grouped.setdefault(pair, dict(artist_key=key, artist_name=name, source=row["source"],
                placements_all_credits=0, placements_primary=0, tracks=set()))
            value["placements_all_credits"] += 1
            value["placements_primary"] += index == 0
            value["tracks"].add(row["track_key"])
    return [dict(artist_key=v["artist_key"], artist_name=v["artist_name"], source=v["source"],
        placements_all_credits=v["placements_all_credits"], placements_primary=v["placements_primary"],
        distinct_observed_tracks=len(v["tracks"])) for _, v in sorted(grouped.items())]


def export(db, sid, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    items, playlists = rows(db, sid), sources(db, sid)
    by_source = defaultdict(list)
    for row in items:
        by_source[row["source"]].append(row)
        raw = json.loads(row["raw_json"])
        entry = raw.get("raw") or {}
        track = (entry.get("item") if "item" in entry else entry.get("track")) or {}
        album = track.get("album") or {}
        row.update(explicit=raw.get("explicit"), artist_ids=json.dumps(raw.get("artist_ids") or []),
                   album_id=album.get("id"), release_date=album.get("release_date"), added_by=json.dumps(raw.get("added_by")))
    write_csv(destination / "playlists.csv", ["source", "name", "exported", "occurrences"], playlists)
    columns = ["source", "position", "track_key", "identity_basis", "title", "artists", "album", "duration_ms",
               "isrc", "is_local", "missing", "playable", "added_at", "returned_uri", "returned_id", "original_id",
               "artist_ids", "album_id", "release_date", "explicit", "added_by"]
    write_csv(destination / "playlist_items.csv", columns, items)
    names = {p["source"]: p["name"] for p in playlists}
    grouped = defaultdict(list)
    for row in items:
        grouped[row["track_key"]].append(row)
    tracks, memberships = [], []
    for key, occurrences in sorted(grouped.items()):
        source_counts = Counter(r["source"] for r in occurrences)
        tracks.append(dict(occurrences[0], source_count=len(source_counts), occurrence_count=len(occurrences),
                           playlist_names=json.dumps([names[s] for s in sorted(source_counts)], ensure_ascii=False)))
        for source, count in sorted(source_counts.items()):
            memberships.append(dict(track_key=key, source=source, playlist_name=names[source], occurrence_count=count))
    write_csv(destination / "tracks.csv", ["track_key", "title", "artists", "album", "isrc", "identity_basis"], tracks)
    write_csv(destination / "songs_with_playlists.csv", ["track_key", "title", "artists", "source_count", "occurrence_count", "playlist_names"], tracks)
    write_csv(destination / "song_playlist_membership.csv", ["track_key", "source", "playlist_name", "occurrence_count"], memberships)
    write_csv(destination / "artist_playlist_summary.csv", ["artist_key", "artist_name", "source",
        "placements_all_credits", "placements_primary", "distinct_observed_tracks"], artist_summary(items))
    write_csv(destination / "duplicate_occurrences.csv", ["track_key", "source", "playlist_name", "occurrence_count"],
              [r for r in memberships if r["occurrence_count"] > 1 and not r["track_key"].startswith("unknown:")])
    per_playlist = destination / "playlists"
    per_playlist.mkdir()
    file_map = []
    for p in playlists:
        filename = hashlib.sha256(p["source"].encode()).hexdigest()[:20] + ".csv"
        write_csv(per_playlist / filename, columns, by_source[p["source"]])
        file_map.append(dict(source=p["source"], name=p["name"], file="playlists/" + filename, exported=p["exported"]))
    metadata = dict(db.execute("SELECT id,label,account_id,created_at,status,sha256 FROM snapshots WHERE id=?", (sid,)).fetchone())
    (destination / "manifest.json").write_text(json.dumps(dict(snapshot=metadata, playlist_files=file_map,
        notes=["Observed identity only, not canonical recordings.", "Positions are zero-based; duplicates retained.",
               "Dangerous CSV formula prefixes are escaped with an apostrophe; SQLite preserves exact text.",
               "An unexported playlist is unknown, not empty."]), indent=2), encoding="utf-8")


def backup(db, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "catalog.sqlite"
        with closing(sqlite3.connect(copy)) as target:
            db.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed.")
        content = copy.read_bytes()
        manifest = dict(format=1, created_at=datetime.now(timezone.utc).isoformat(),
                        sha256=hashlib.sha256(content).hexdigest(),
                        includes="Catalog, raw snapshots, song ratings, and imported listening events and stream totals")
        with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("catalog.sqlite", content)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))


def restore(archive_path, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Restore destination already exists; choose a new filename.")
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        content = archive.read("catalog.sqlite")
    if manifest.get("format") != 1 or hashlib.sha256(content).hexdigest() != manifest.get("sha256"):
        raise ValueError("Backup checksum or format is invalid.")
    with tempfile.TemporaryDirectory() as folder:
        check = Path(folder) / "check.sqlite"
        check.write_bytes(content)
        with closing(connect(check)) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Restored database integrity check failed.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=data_root() / "catalog.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="Add an audit snapshot without replacing history")
    imp.add_argument("snapshot", type=Path)
    imp.add_argument("--label", default="Imported audit")
    checkpoint = sub.add_parser("export-checkpoint", help="Export saved audit evidence without resuming Spotify")
    checkpoint.add_argument("run", type=Path, help="Folder containing the resumable audit's library.sqlite")
    checkpoint.add_argument("output", type=Path, help="New private snapshot JSON file")
    capacity = sub.add_parser("capacity", help="Save historical playlist capacity estimates")
    capacity.add_argument("--snapshot", type=int)
    capacity.add_argument("--before", type=int, help="Older snapshot to compare")
    capacity.add_argument("--output", type=Path, required=True, help="New private JSON report")
    unavailable = sub.add_parser("availability", help="Report unavailable Spotify tracks and recovery leads")
    unavailable.add_argument("--snapshot", type=int, help="Use this capture instead of the latest one")
    unavailable.add_argument("--inventory", type=Path, help="Existing local_inventory.py JSON report")
    unavailable.add_argument("--output", type=Path, help="New private HTML report")
    metadata = sub.add_parser("metadata", help="Count or export track, artist, and release observations")
    metadata.add_argument("--snapshot", type=int)
    metadata.add_argument("--output", type=Path, help="New private JSON file with per-placement metadata")
    sub.add_parser("snapshots")
    for command in ("playlists", "find", "query", "export", "song-stats"):
        p = sub.add_parser(command)
        p.add_argument("--snapshot", type=int)
        if command == "find":
            p.add_argument("term")
        elif command == "query":
            p.add_argument("operation", choices=["union", "intersection", "difference"])
            p.add_argument("sources", nargs="+")
        elif command == "export":
            p.add_argument("output", type=Path)
        elif command == "song-stats":
            p.add_argument("--hierarchy", type=Path, default=data_root() / "hierarchy.sqlite")
            p.add_argument("--folder-depth", type=int, default=1)
            p.add_argument("--term", default="", help="Filter by song, artist, or exact track key")
            p.add_argument("--sort", choices=song_stats.SORT_FIELDS, default="playlist")
            p.add_argument("--limit", type=int, default=50)
            p.add_argument("--output", type=Path, help="Save a private JSON report to a new file")
    stream_imports = {
        "import-spotify-history": (stream_counts.import_spotify_history, "Import a Spotify Extended Streaming History ZIP"),
        "import-personal-plays": (stream_counts.import_personal_plays, "Import a reviewed non-Spotify personal plays CSV"),
        "import-worldwide-streams": (stream_counts.import_worldwide_streams, "Import dated, worldwide all-time stream totals from CSV"),
    }
    for command, (_, help_text) in stream_imports.items():
        sub.add_parser(command, help=help_text).add_argument("input", type=Path)
    sub.add_parser("import-ratings", help="Apply changes downloaded from the catalog view").add_argument("input", type=Path)
    diff = sub.add_parser("compare")
    diff.add_argument("before", type=int)
    diff.add_argument("after", type=int)
    back = sub.add_parser("backup")
    back.add_argument("output", type=Path)
    recover = sub.add_parser("restore")
    recover.add_argument("archive", type=Path)
    recover.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "export-checkpoint":
            result = checkpoint_export.snapshot(args.run / "library.sqlite")
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False)
            print("Offline checkpoint exported.")
            return 0
        if args.command == "restore":
            restore(args.archive, args.output)
            print("Restored catalog to", args.output)
            return 0
        if args.command == "import-ratings" and not args.db.is_file():
            raise ValueError("Import an audit snapshot before applying rating changes.")
        write = args.command in ("import", "import-ratings") or args.command in stream_imports
        with closing(connect(args.db, write=write)) as db:
            if args.command == "import":
                result = dict(snapshot_id=import_snapshot(db, json.loads(args.snapshot.read_text(encoding="utf-8-sig")), args.label))
            elif args.command == "import-ratings":
                result = import_ratings(db, json.loads(args.input.read_text(encoding="utf-8-sig")))
            elif args.command in stream_imports:
                importer, _ = stream_imports[args.command]
                result = importer(db, args.input)
            elif args.command == "snapshots":
                result = [dict(r) for r in db.execute("SELECT id,label,created_at,status FROM snapshots ORDER BY id")]
            elif args.command == "compare":
                result = compare(db, snapshot_id(db, args.before), snapshot_id(db, args.after))
            elif args.command == "backup":
                backup(db, args.output)
                result = dict(backup=str(args.output), uploaded=False)
            else:
                if args.command in ("song-stats", "capacity", "availability", "metadata"):
                    db.execute("BEGIN")
                sid = snapshot_id(db, args.snapshot)
                if args.command == "playlists":
                    result = sources(db, sid)
                elif args.command == "find":
                    result = lookup(db, sid, args.term)
                    result = [{k: r[k] for k in ("source", "playlist_name", "position", "track_key", "title", "artists", "identity_basis")} for r in result]
                elif args.command == "query":
                    result = set_query(db, sid, args.operation, args.sources)
                elif args.command == "metadata":
                    result = track_metadata.report(db, sid, placements=args.output is not None)
                    if args.output is not None:
                        with args.output.open("x", encoding="utf-8") as stream:
                            json.dump(result, stream, ensure_ascii=False, indent=2)
                        del result["placements"]
                        result["report"] = str(args.output.resolve())
                elif args.command == "capacity":
                    before = snapshot_id(db, args.before) if args.before is not None else None
                    result = playlist_capacity.report(db, sid, before)
                    with args.output.open("x", encoding="utf-8") as stream:
                        json.dump(result, stream, ensure_ascii=False, indent=2)
                    result = dict(report_written=True)
                elif args.command == "availability":
                    inventory = json.loads(args.inventory.read_text(encoding="utf-8-sig")) if args.inventory else None
                    report = availability.report(db, sid, inventory)
                    output = args.output
                    if output is None:
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                        output = data_root() / "availability" / f"{stamp}.html"
                        output.parent.mkdir(parents=True, exist_ok=True)
                    with output.open("x", encoding="utf-8") as stream:
                        availability.write_html(stream, report)
                    result = dict(report=str(output.resolve()), snapshot=sid,
                                  placements={status: len(rows) for status, rows in report["groups"].items()})
                elif args.command == "song-stats":
                    result = song_stats.report(db, sid, args.hierarchy, args.folder_depth, args.term, args.sort, args.limit)
                    if args.output:
                        with args.output.open("x", encoding="utf-8") as stream:
                            json.dump(result, stream, ensure_ascii=False, indent=2)
                        result = dict(report=str(args.output), songs=len(result["songs"]))
                else:
                    export(db, sid, args.output)
                    result = dict(export=str(args.output))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, csv.Error, zipfile.BadZipFile) as error:
        print("Stopped:", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
