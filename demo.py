"""Generate a synthetic, unapproved audit and plan without connecting to Spotify."""
from datetime import datetime, timezone
from pathlib import Path
import secrets

import audit
import migrate


def main():
    folder = Path("backups") / ("demo-" + secrets.token_hex(4))
    folder.mkdir(parents=True)
    playlist = "P" * 22
    rows = []
    for source, ids in ((playlist, [audit.OLD, audit.NEW, audit.OLD]), ("liked", [audit.OLD, audit.NEW])):
        for position, track_id in enumerate(ids):
            rows.append(audit.occurrence(source, "SYNTHETIC DEMO", position, dict(item=dict(
                id=track_id, uri=migrate.track_uri(track_id), name="2 Busy (synthetic metadata)",
                is_playable=True))))
    snapshot = dict(created_at=datetime.now(timezone.utc).isoformat(), account_id="SYNTHETIC-NOT-A-REAL-ACCOUNT",
        client_id="0" * 32, api_mode="extended", status="completed synthetic example",
        occurrences=rows, errors=[], playlists=[dict(exported=True, metadata=dict(id=playlist,
            name="SYNTHETIC DEMO", snapshot_id="0", owner=dict(id="SYNTHETIC-NOT-A-REAL-ACCOUNT")))])
    audit.export_report(folder, snapshot)
    mappings = migrate.read(Path(__file__).with_name("mappings.example.json"))
    migrate.save(folder / "review-plan.json", migrate.make_plan(snapshot, mappings))
    print("Synthetic example only; not your account. Report:", (folder / "report.html").resolve())


if __name__ == "__main__":
    main()
