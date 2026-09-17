"""One-command, fully offline example of the personal music catalog."""
import argparse
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import secrets

import audit
import library


def sample_snapshots():
    def entry(source, pos, letter, title, local=False):
        uri = "spotify:local:Demo+Artist::Warehouse+Edit:180" if local else "spotify:track:" + letter * 22
        return audit.occurrence(source, source, pos, dict(added_at="2026-09-01T12:00:00Z", item=dict(
            id=None if local else letter * 22, uri=uri, name=title, is_local=local, duration_ms=180000,
            artists=[dict(id=None if local else "D" * 22, name="Demo Artist")],
            album=dict(id="E" * 22, name="Synthetic examples", release_date="2026-01-01"))))
    first = dict(account_id="SYNTHETIC-DEMO", client_id="0" * 32, api_mode="development",
        created_at="2026-09-01T12:00:00Z", status="completed synthetic example", errors=[],
        playlists=[dict(exported=True, metadata=dict(id=source, name=source, snapshot_id="demo-1"))
                   for source in ("Chill", "Festival", "AllLeaks")], occurrences=[])
    for source, tracks in (("Chill", [("A", "Moonrise"), ("B", "Harbor"), ("A", "Moonrise")]),
                           ("Festival", [("A", "Moonrise"), ("C", "Night Drive")]),
                           ("liked", [("A", "Moonrise"), ("B", "Harbor")])):
        first["occurrences"].extend(entry(source, i, letter, title) for i, (letter, title) in enumerate(tracks))
    first["occurrences"].append(entry("AllLeaks", 0, "L", "Warehouse Edit", True))
    second = deepcopy(first)
    second["created_at"] = "2026-09-16T12:00:00Z"
    second["occurrences"] = [r for r in second["occurrences"] if not (r["source"] == "Chill" and r["position"] == 2)]
    return first, second


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    folder = args.output or Path("backups") / ("catalog-demo-" + secrets.token_hex(4))
    folder.mkdir(parents=True, exist_ok=False)
    first, second = sample_snapshots()
    audit.write_json(folder / "snapshot-before.json", first)
    audit.write_json(folder / "snapshot-after.json", second)
    with closing(library.connect(folder / "catalog.sqlite", write=True)) as db:
        a = library.import_snapshot(db, first, "Demo before")
        b = library.import_snapshot(db, second, "Demo after")
        shared = library.set_query(db, a, "intersection", ["Chill", "Festival"])
        unique = library.set_query(db, a, "difference", ["Chill", "Festival"])
        library.export(db, a, folder / "csv")
        library.backup(db, folder / "catalog-backup.zip")
        changes = library.compare(db, a, b)
    library.restore(folder / "catalog-backup.zip", folder / "restored-catalog.sqlite")
    print("OFFLINE DEMO - synthetic music, not your Spotify account")
    print("Chill AND Festival:", ", ".join(r["title"] for r in shared))
    print("Chill NOT Festival:", ", ".join(r["title"] for r in unique))
    print("Snapshot change: removed one duplicate Moonrise from Chill.")
    print("CSV files, database, and tested backup/restore:", folder.resolve())
    audit.write_json(folder / "comparison.json", changes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
