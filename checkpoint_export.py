"""Export a saved resumable-audit checkpoint without resuming or modifying it."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def snapshot(database):
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("BEGIN")
        saved = db.execute("SELECT data FROM run_state WHERE id=1").fetchone()
        state = json.loads(saved[0]) if saved else {}
        if state.get("version") != 1 or not state.get("account_id"):
            raise ValueError("Expected an identified version 1 audit checkpoint.")

        manifest = {meta["id"]: meta for meta in state["manifest"]}
        if len(manifest) != len(state["manifest"]) or "liked" in manifest:
            raise ValueError("Invalid checkpoint playlist list.")
        sources = state["sources"]
        if sources.keys() - manifest.keys() - {"liked"}:
            raise ValueError("Checkpoint source is absent from the playlist list.")
        selected = state.get("selected_playlists")
        counts = Counter()
        rows = []
        for source, position, raw in db.execute(
            "SELECT source,position,data FROM occurrences ORDER BY source,position"
        ):
            row = json.loads(raw)
            if (source not in sources or position != counts[source]
                    or row["source"] != source or row["position"] != position):
                raise ValueError("Checkpoint occurrence source or position does not match.")
            counts[source] += 1
            rows.append(row)

        coverage = {}
        playlists = []
        for key in [*manifest, "liked"]:
            source = sources.get(key, {})
            status = source.get("status", "not_requested" if key == "liked" and selected else "pending")
            count = counts[key]
            total = source.get("total")
            complete = status == "complete"
            if (source.get("count", 0) != count
                    or (complete and (type(total) is not int or total != count))):
                raise ValueError("Checkpoint rows do not match saved source coverage.")
            coverage[key] = dict(
                status=status, provider_total=total,
                completed_at=source.get("completed_at"),
                validated_at=source.get("validated_at"), error=source.get("error"),
            )
            if key != "liked":
                playlists.append(dict(metadata=source.get("metadata") or manifest[key], exported=complete))

    result = dict(
        created_at=state["created_at"], account_id=state["account_id"], status=state["status"],
        liked_exported=coverage["liked"]["status"] == "complete", playlists=playlists,
        occurrences=rows, checkpoint=dict(
            saved_at=state.get("updated_at"), discovery_complete=state["discovery_complete"],
            discovery_total=state.get("discovery_total"), last_error=state.get("last_error"),
            sources=coverage,
        ),
    )
    if selected:
        result["selected_playlists"] = selected
    return result
