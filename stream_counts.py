"""Import dated stream totals and private listening events into the local catalog."""

from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import PurePosixPath
import re
import zipfile


TRACK_URI = re.compile(r"spotify:track:[a-zA-Z0-9]{22}")
AUDIO_HISTORY = re.compile(r"Streaming_History_Audio_.*\.json", re.IGNORECASE)
SCHEMAS = {
    "listening_events": """CREATE TABLE IF NOT EXISTS listening_events (
        service TEXT NOT NULL, event_id TEXT NOT NULL, track_key TEXT NOT NULL,
        ended_at TEXT NOT NULL, played_ms INTEGER NOT NULL,
        PRIMARY KEY(service, event_id))""",
    "worldwide_streams": """CREATE TABLE IF NOT EXISTS worldwide_streams (
        service TEXT NOT NULL, track_key TEXT NOT NULL, as_of TEXT NOT NULL,
        streams INTEGER NOT NULL, source TEXT NOT NULL,
        PRIMARY KEY(service, track_key, as_of))""",
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode("utf-8")).hexdigest()


def utc_timestamp(value):
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is not None and "T" in value:
            return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (TypeError, ValueError, OverflowError):
        pass
    raise ValueError("Expected an ISO timestamp with a time zone.")


def nonnegative_integer(value):
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value):
        value = int(value)
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError("Expected a nonnegative integer within SQLite's integer range.")
    return value


def import_spotify_history(db, archive):
    """Merge the audio-track rows from a Spotify Extended Streaming History ZIP."""
    observed = Counter()
    rows_seen = inserted = 0
    with zipfile.ZipFile(archive) as source:
        files = [file for file in source.infolist()
                 if AUDIO_HISTORY.fullmatch(PurePosixPath(file.filename).name)]
        if not files:
            raise ValueError("ZIP has no Spotify Extended Streaming History audio files. Request Extended Streaming History for track URIs.")
        if len({file.filename for file in files}) != len(files):
            raise ValueError("ZIP contains duplicate audio history filenames.")

        def events(file):
            nonlocal rows_seen
            with source.open(file) as stream:
                rows = json.load(stream)
            if not isinstance(rows, list):
                raise ValueError("Expected a list of play events in each Spotify audio history file.")
            for index, row in enumerate(rows, 1):
                try:
                    track = row["spotify_track_uri"]
                    if track is None:
                        continue  # Podcasts, audiobooks and other rows without a track URI.
                    if not TRACK_URI.fullmatch(track):
                        raise ValueError("Expected a Spotify track URI.")
                    ended_at, played_ms = utc_timestamp(row["ts"]), nonnegative_integer(row["ms_played"])
                    signature = fingerprint([track, ended_at, played_ms, row.get("platform"), row.get("offline_timestamp")])
                except (TypeError, ValueError, KeyError) as error:
                    raise ValueError(f"Invalid Spotify audio history event at row {index}.") from error
                rows_seen += 1
                # The archive exposes no stable event ID. Preserve repeated rows in an
                # export while making overlapping exports idempotent up to multiplicity.
                observed[signature] += 1
                yield ("spotify", f"{signature}:{observed[signature]}", track, ended_at, played_ms)

        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(SCHEMAS["listening_events"])
            for file in files:
                inserted += db.executemany("INSERT OR IGNORE INTO listening_events VALUES (?,?,?,?,?)", events(file)).rowcount
            if not rows_seen:
                raise ValueError("No Spotify audio events with track URIs were found.")
    return dict(track_events_in_archive=rows_seen, new_events=inserted)


def csv_records(path, columns):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not set(columns) <= set(reader.fieldnames):
            raise ValueError("Required CSV columns: " + ", ".join(columns))
        for row in reader:
            if None in row or any(row[column] is None for column in columns):
                raise ValueError(f"Malformed CSV at line {reader.line_num}.")
            yield reader.line_num, [row[column].strip() for column in columns]


def validate_identity(track, service):
    if not TRACK_URI.fullmatch(track) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", service):
        raise ValueError("Provide an exact Spotify track URI and a lowercase service slug.")


def import_personal_plays(db, path):
    """Merge reviewed non-Spotify events with service-specific stable IDs."""
    inserted = seen = 0
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(SCHEMAS["listening_events"])
        for line, (service, event_id, track, ended_at, ms) in csv_records(
                path, ("service", "event_id", "track_key", "ended_at", "played_ms")):
            try:
                validate_identity(track, service)
                if service == "spotify" or not event_id:
                    raise ValueError("Use the Spotify history importer for Spotify and stable event IDs for other services.")
                values = (track, utc_timestamp(ended_at), nonnegative_integer(ms))
            except ValueError as error:
                raise ValueError(f"Invalid personal play at CSV line {line}. {error}") from error
            key = (service, fingerprint(event_id))
            cursor = db.execute("INSERT OR IGNORE INTO listening_events VALUES (?,?,?,?,?)", key + values)
            if not cursor.rowcount:
                previous = db.execute("SELECT track_key,ended_at,played_ms FROM listening_events "
                                      "WHERE service=? AND event_id=?", key).fetchone()
                if tuple(previous) != values:
                    raise ValueError(f"Conflicting service event ID at CSV line {line}.")
            seen += 1
            inserted += cursor.rowcount
        if not seen:
            raise ValueError("Personal plays CSV contains no events.")
    return dict(events_in_csv=seen, new_events=inserted)


def import_worldwide_streams(db, path):
    """Retain dated all-time track totals from individual services."""
    inserted = seen = 0
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(SCHEMAS["worldwide_streams"])
        for line, (service, track, as_of, streams, source) in csv_records(
                path, ("service", "track_key", "as_of", "streams", "source")):
            try:
                validate_identity(track, service)
                if date.fromisoformat(as_of).isoformat() != as_of or not source:
                    raise ValueError("Provide an as-of date (YYYY-MM-DD) and a source.")
                values = (nonnegative_integer(streams), source)
            except ValueError as error:
                raise ValueError(f"Invalid worldwide stream total at CSV line {line}. {error}") from error
            key = (service, track, as_of)
            cursor = db.execute("INSERT OR IGNORE INTO worldwide_streams VALUES (?,?,?,?,?)", key + values)
            if not cursor.rowcount:
                previous = db.execute("SELECT streams,source FROM worldwide_streams "
                                      "WHERE service=? AND track_key=? AND as_of=?", key).fetchone()
                if tuple(previous) != values:
                    raise ValueError(f"Conflicting service total for the same track and date at CSV line {line}.")
            seen += 1
            inserted += cursor.rowcount
        if not seen:
            raise ValueError("Worldwide streams CSV contains no totals.")
    return dict(totals_in_csv=seen, new_observations=inserted)


def observations(db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    personal = {}
    coverage = []
    worldwide = {}
    if "listening_events" in tables:
        query = """SELECT track_key,service,COUNT(*) AS events,SUM(played_ms >= 30000) AS plays_30s,
                          SUM(played_ms) AS played_ms, MAX(ended_at) AS last_event_at
                   FROM listening_events GROUP BY track_key,service ORDER BY track_key,service"""
        for row in db.execute(query):
            record = dict(row)
            personal.setdefault(record.pop("track_key"), []).append(record)
        coverage = [dict(row) for row in db.execute(
            "SELECT service,MIN(ended_at) AS first_event_at,MAX(ended_at) AS last_event_at "
            "FROM listening_events GROUP BY service ORDER BY service")]
    if "worldwide_streams" in tables:
        query = """SELECT * FROM worldwide_streams AS stream
                   WHERE as_of = (SELECT MAX(as_of) FROM worldwide_streams
                                  WHERE service=stream.service AND track_key=stream.track_key)
                   ORDER BY track_key,service"""
        for row in db.execute(query):
            record = dict(row)
            worldwide.setdefault(record.pop("track_key"), []).append(record)
    return personal, worldwide, coverage
