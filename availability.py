"""Report Spotify track availability and recovery leads from saved evidence."""

from collections import defaultdict
from html import escape
import json
import re
from urllib.parse import quote, urlencode


SECTIONS = {
    "recover": "SoundCloud recovery leads",
    "check_local": "Check local copies and Spotify search",
    "local_candidate": "Review local file candidates",
    "spotify_candidate": "Review playable Spotify alternatives",
    "relinked": "Spotify supplied a playable relink",
    "review": "Review restrictions or conflicting evidence",
    "unknown": "Availability unknown",
}


def normalized(value):
    return " ".join(value.casefold().split())


def local_files(inventory):
    files = defaultdict(dict)
    if inventory is None:
        return files, "not checked"
    if (not isinstance(inventory, dict) or inventory.get("version") != 1
            or not isinstance(inventory.get("entries"), list)
            or not isinstance(inventory.get("roots"), list) or not inventory["roots"]):
        raise ValueError("Expected a report from local_inventory.py with at least one root.")
    for entry in inventory["entries"]:
        if entry["status"] == "complete":
            files[normalized(entry["filename_title"])][entry["path"]] = entry.get("duration_ms")
    complete = inventory.get("status") == "complete" and all(
        root.get("status") == "complete" for root in inventory["roots"])
    return files, "complete" if complete else "incomplete"


def similar_duration(left, right):
    return left is None or right is None or abs(left - right) <= 2000


def report(db, sid, inventory=None):
    files, local_coverage = local_files(inventory)
    snapshot = dict(db.execute(
        "SELECT id,created_at,status FROM snapshots WHERE id=?", (sid,)).fetchone())
    sources = {r["source"]: dict(r, local=0, non_track=0, no_signal=0, observed=0) for r in db.execute(
        "SELECT source,name,exported FROM playlists WHERE snapshot_id=? ORDER BY source", (sid,))}
    playable_ids, playable_isrcs, relinks = set(), defaultdict(set), defaultdict(set)
    review = []
    groups = {status: [] for status in SECTIONS}
    rows = db.execute("SELECT * FROM items WHERE snapshot_id=? ORDER BY source,position", (sid,))
    for row in rows:
        source = sources[row["source"]]
        source["observed"] += 1
        uri = row["returned_uri"] or ""
        if row["is_local"] or uri.startswith("spotify:local:"):
            source["local"] += 1
            continue
        item = json.loads(row["raw_json"])
        raw = item.get("raw") or {}
        track = (raw.get("item") if "item" in raw else raw.get("track")) or {}
        if track.get("type") not in (None, "track") or (uri and not uri.startswith("spotify:track:")):
            source["non_track"] += 1
            continue
        restrictions = track.get("restrictions") or {}
        restriction = restrictions.get("reason") or ("unspecified" if restrictions else None)
        returned, original = row["returned_id"], row["original_id"]
        relinked = original and returned and original != returned
        playable = row["playable"] if row["playable"] in (0, 1) else None
        if not row["missing"] and playable is None and not restriction and not relinked:
            source["no_signal"] += 1
            continue

        artists = [name for name in json.loads(row["artists"]) if name]
        title = row["title"] or ""
        signature = (normalized(title), tuple(normalized(name) for name in artists))
        explicit = item.get("explicit")
        isrc = (row["isrc"] or "").strip().upper()
        observed_playable = not row["missing"] and playable == 1 and not restriction
        if observed_playable:
            if returned:
                playable_ids.add(returned)
                if isrc and title and artists:
                    playable_isrcs[isrc, signature].add((returned, explicit, row["duration_ms"]))
            if not relinked:
                continue

        evidence = dict(source=row["source"], position=row["position"], returned_id=returned,
                        original_id=original, title=title, artists=artists, album=row["album"],
                        playable=playable, restriction=restriction, candidates=[], local_paths=[])
        if row["missing"]:
            groups["unknown"].append(evidence)
        elif observed_playable:
            relinks[original].add(returned)
            groups["relinked"].append(evidence)
        elif restriction and (restriction != "market" or playable == 1):
            groups["review"].append(evidence)
        elif playable == 0 or restriction == "market":
            review.append((evidence, isrc, signature, explicit, row["duration_ms"]))
        else:
            groups["unknown"].append(evidence)

    for entry, isrc, signature, explicit, duration in review:
        returned = entry["returned_id"]
        alternatives = {key: "Spotify relink" for key in relinks.get(returned, {}) if key != returned}
        for track_id, other_explicit, other_duration in playable_isrcs.get((isrc, signature), ()):
            if (track_id != returned and track_id != entry["original_id"]
                    and (explicit is None or other_explicit is None or explicit == other_explicit)
                    and similar_duration(duration, other_duration)):
                alternatives.setdefault(track_id, "Matching ISRC, title and artists")
        entry["candidates"] = sorted(alternatives.items())
        if returned in playable_ids:
            entry["mixed_playability"] = True
            groups["review"].append(entry)
        elif alternatives:
            groups["spotify_candidate"].append(entry)
        elif not entry["title"] or not entry["artists"]:
            groups["review"].append(entry)
        else:
            title, artists = entry["title"], entry["artists"]
            names = {normalized(title), normalized(f"{artists[0]} - {title}"),
                     normalized(f"{', '.join(artists)} - {title}")}
            entry["local_paths"] = sorted({path for name in names for path, length in files.get(name, {}).items()
                                           if similar_duration(duration, length)})
            if entry["local_paths"]:
                groups["local_candidate"].append(entry)
            elif local_coverage == "complete":
                groups["recover"].append(entry)
            else:
                groups["check_local"].append(entry)

    return dict(snapshot=snapshot, sources=sources, groups=groups, local_coverage=local_coverage,
                inventory_at=inventory.get("finished_at") if inventory else None,
                inventory_roots=inventory["roots"] if inventory else [])


def spotify_link(kind, spotify_id, label):
    if spotify_id and re.fullmatch(r"[A-Za-z0-9]{22}", spotify_id):
        return f'<a href="https://open.spotify.com/{kind}/{spotify_id}" rel="noreferrer">{label}</a>'
    return label


def placement_row(entry, placements, sources, search):
    title = escape(entry["title"] or "Unidentified track")
    artists = escape(", ".join(entry["artists"]))
    album = escape(entry["album"] or "")
    links = []
    if entry["original_id"] and entry["original_id"] != entry["returned_id"]:
        links.append(spotify_link("track", entry["original_id"], "Original Spotify ID"))
    if entry["returned_id"]:
        links.append(spotify_link("track", entry["returned_id"], "Returned Spotify track"))
    for track_id, basis in entry["candidates"]:
        links.append(spotify_link("track", track_id, f"Playable Spotify candidate ({basis})"))
    if search and entry["title"] and entry["artists"]:
        query = f'{", ".join(entry["artists"])} {entry["title"]}'
        links.append(f'<a href="https://open.spotify.com/search/{quote(query, safe="")}" '
                     'rel="noreferrer">Search Spotify</a>')
        links.append(f'<a href="https://soundcloud.com/search/sounds?{urlencode({"q": query})}" '
                     'rel="noreferrer">Search SoundCloud</a>')
    if entry["local_paths"]:
        links.extend(escape(path) for path in entry["local_paths"])
    signal = {0: "Unplayable", 1: "Playable", None: "Playability unspecified"}[entry["playable"]]
    if entry.get("mixed_playability"):
        signal += " · same ID also observed playable"
    if entry["restriction"]:
        signal += f' · Spotify restriction ({entry["restriction"]})'
    locations = defaultdict(list)
    for placement in placements:
        locations[placement["source"]].append(str(placement["position"] + 1))
    location_lines = []
    for source_id, positions in locations.items():
        source = sources[source_id]
        coverage = "complete" if source["exported"] else "incomplete"
        name = spotify_link("playlist", source_id, escape(source["name"]))
        location_lines.append(f'{name} · Position {", ".join(positions)} · {coverage}')
    return (f'<tr><td><strong>{title}</strong><br>{artists}<br>{album}</td>'
            f'<td>{"<br>".join(location_lines)}</td>'
            f'<td>{escape(signal)}</td><td>{"<br>".join(links)}</td></tr>\n')


def write_html(stream, result):
    snapshot, sources, groups = result["snapshot"], result["sources"], result["groups"]
    captured = escape(snapshot["created_at"] or "Unknown")
    inventory_at = escape(result["inventory_at"] or "")
    status = escape(snapshot["status"])
    stream.write(f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spotify availability report</title>
<style>
body {{font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; padding: 0 1rem; max-width: 76rem}}
table {{border-collapse: collapse; width: 100%; margin: .75rem 0 1.25rem; font-size: .9rem}}
th, td {{border-bottom: 1px solid #aaa; padding: .5rem; text-align: left; vertical-align: top; overflow-wrap: anywhere}}
summary {{cursor: pointer; font-weight: 600; padding: .5rem 0}}
</style>
<h1>Spotify availability report</h1>
<p>Snapshot {snapshot['id']} · {captured} · {status}</p>
<p>Local inventory {result['local_coverage']} {inventory_at}</p>
<p>These are observations from the saved capture. Spotify availability can change by market,
account and date. A recovery lead has no playable alternative observed in this capture and no
filename candidate in the supplied complete inventory. Spotify and SoundCloud search links let
you review current options. Local files may have different filenames.</p>
''')
    for key, label in SECTIONS.items():
        entries = groups[key]
        if not entries:
            stream.write(f'<p>{label} (0 placements)</p>\n')
            continue
        tracks = defaultdict(list)
        for entry in entries:
            # Group identical observations while keeping every source and position.
            if entry["returned_id"] or entry["original_id"]:
                track = {name: value for name, value in entry.items() if name not in ("source", "position")}
                tracks[json.dumps(track, ensure_ascii=False)].append(entry)
            else:
                tracks[entry["source"], entry["position"]].append(entry)
        opened = " open" if key in ("recover", "check_local") else ""
        stream.write(f'<details{opened}><summary>{label} ({len(entries):,} placements)</summary>\n'
                     '<table><thead><tr><th>Track</th><th>Saved placement</th><th>Spotify evidence</th>'
                     '<th>Review</th></tr></thead><tbody>\n')
        for placements in tracks.values():
            stream.write(placement_row(placements[0], placements, sources, key in ("recover", "check_local")))
        stream.write('</tbody></table></details>\n')
    stream.write('''<details><summary>Source coverage</summary>
<p>Incomplete sources can include observed placements. The source list covers only the sources
present in this snapshot. Missing objects are listed under Availability unknown. Ordinary rows
without a playability signal are counted below. Local references require a separate device check.</p>
<table><thead><tr><th>Source</th><th>Coverage</th><th>Observed placements</th>
<th>Local references</th><th>Non-track items</th><th>No availability signal</th></tr></thead><tbody>
''')
    for source in sources.values():
        coverage = "complete" if source["exported"] else "incomplete"
        name = spotify_link("playlist", source["source"], escape(source["name"]))
        stream.write(f'<tr><td>{name}</td><td>{coverage}</td>'
                     f'<td>{source["observed"]:,}</td><td>{source["local"]:,}</td>'
                     f'<td>{source["non_track"]:,}</td><td>{source["no_signal"]:,}</td></tr>\n')
    stream.write('</tbody></table></details>\n')
    if result["inventory_roots"]:
        stream.write('<details><summary>Local inventory folders</summary><ul>\n')
        for root in result["inventory_roots"]:
            stream.write(f'<li>{escape(root["path"])} · {escape(root["status"])}</li>\n')
        stream.write('</ul></details>\n')
    stream.write('</html>\n')
