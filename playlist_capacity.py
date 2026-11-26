"""Historical playlist counts and estimated space from saved evidence."""
from datetime import datetime, timezone
import json


PLAYLIST_LIMIT = 10_000


def provider_total(metadata, source):
    total = source.get("provider_total")
    if type(total) is int and total >= 0:
        return total
    totals = set()
    for key in ("items", "tracks"):
        wrapper = metadata.get(key)
        if isinstance(wrapper, dict):
            value = wrapper.get("total")
            if type(value) is int and value >= 0:
                totals.add(value)
    return totals.pop() if len(totals) == 1 else None


def observations(db, sid):
    saved = db.execute(
        "SELECT created_at,status,json_extract(raw_json,'$.checkpoint') FROM snapshots WHERE id=?",
        (sid,),
    ).fetchone()
    checkpoint = json.loads(saved[2]) if saved[2] else {}
    rows = db.execute("""
        SELECT p.source, p.name, p.exported, p.metadata_json, COUNT(i.position) AS placements
        FROM playlists p LEFT JOIN items i USING(snapshot_id,source)
        WHERE p.snapshot_id=? GROUP BY p.source ORDER BY p.source
        """, (sid,))
    result = []
    for row in rows:
        key = row["source"]
        source = checkpoint.get("sources", {}).get(key, {})
        total = provider_total(json.loads(row["metadata_json"]), source)
        count = row["placements"]
        complete = bool(row["exported"])
        if key == "liked":
            capacity_status = "not_applicable"
        elif not complete:
            capacity_status = "incomplete_capture"
        elif total is None:
            capacity_status = "provider_total_unknown"
        elif total != count:
            capacity_status = "count_mismatch"
        else:
            capacity_status = "estimated"
        captured_at = source.get("completed_at")
        result.append(dict(
            source=key, name=row["name"], kind="liked_songs" if key == "liked" else "playlist",
            placements=count, provider_total=total, source_complete=complete,
            source_status=source.get("status"), captured_at=captured_at,
            validated_at=source.get("validated_at"),
            evidence_at=captured_at or checkpoint.get("saved_at") or saved[0],
            evidence_time_basis=("source_completed" if captured_at else
                                 "checkpoint_saved" if checkpoint.get("saved_at") else "snapshot_created"),
            source_error=source.get("error"),
            capacity_status=capacity_status,
            remaining_slots=max(0, PLAYLIST_LIMIT - count) if capacity_status == "estimated" else None,
        ))
    result.sort(key=lambda row: (
        row["kind"] == "liked_songs", row["remaining_slots"] is None,
        row["remaining_slots"], row["name"].casefold(), row["source"],
    ))
    return dict(snapshot=sid, snapshot_created_at=saved[0], snapshot_status=saved[1],
                checkpoint_saved_at=checkpoint.get("saved_at"),
                checkpoint_error=checkpoint.get("last_error"),
                discovery_complete=checkpoint.get("discovery_complete"), sources=result)


def utc_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def report(db, sid, before=None):
    result = observations(db, sid)
    result["playlist_limit"] = PLAYLIST_LIMIT
    if before is not None:
        prior = observations(db, before)
        old_sources = {row["source"]: row for row in prior["sources"]}
        result["comparison_snapshot"] = before
        for row in result["sources"]:
            old = old_sources.get(row["source"])
            delta = None
            if old and old["remaining_slots"] is not None and row["remaining_slots"] is not None:
                earlier = utc_time(old["evidence_at"])
                later = utc_time(row["evidence_at"])
                if earlier and later and earlier < later:
                    delta = row["placements"] - old["placements"]
            row["net_placement_change"] = delta
    return result
