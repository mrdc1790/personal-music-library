"""Rank observed song identities by playlist reach and report their stream counts."""

from collections import Counter, defaultdict
import json

import folder_tree
import logical_playlists
import stream_counts


SORT_FIELDS = {
    "playlist": "playlist_score",
    "collection": "observed_collection_count",
    "personal": "personal_imported_plays_30s",
    "personal-spotify": "personal_spotify_plays_30s",
    "worldwide": "worldwide_imported_streams",
    "worldwide-spotify": "worldwide_spotify_streams",
}


def playlist_folders(tree, depth):
    folders = {None: ()}
    candidates = defaultdict(set)
    for node in tree["nodes"] if tree else ():
        path = folders[node["parent_id"]]
        if node["kind"] == "folder":
            folders[node["node_id"]] = path + ((node["provider_id"], node["name"]),)
        else:
            candidates[node["provider_id"]].add(path[:depth])
    # A playlist with conflicting category assignments earns only its base point.
    return {source: next(iter(paths)) for source, paths in candidates.items() if len(paths) == 1}


def stream_fields(personal, worldwide):
    return dict(
        personal_spotify_plays_30s=next((p["plays_30s"] for p in personal if p["service"] == "spotify"), None),
        personal_imported_plays_30s=sum(p["plays_30s"] for p in personal) if personal else None,
        personal_by_service=personal,
        worldwide_spotify_streams=next((p["streams"] for p in worldwide if p["service"] == "spotify"), None),
        worldwide_imported_streams=sum(p["streams"] for p in worldwide) if worldwide else None,
        worldwide_by_service=worldwide,
    )


def report(db, snapshot, hierarchy, folder_depth=1, term="", sort="playlist", limit=50):
    if folder_depth < 1 or limit < 1:
        raise ValueError("Folder depth and limit must be positive.")
    metadata = dict(db.execute("SELECT id,created_at,status,account_id FROM snapshots WHERE id=?", (snapshot,)).fetchone())
    account = metadata["account_id"]
    if hierarchy:
        metadata.pop("account_id")
    tree = folder_tree.latest_tree(hierarchy, account) if hierarchy else None
    category_for = playlist_folders(tree, folder_depth)
    playlist_coverage = {row[0]: bool(row[1]) for row in db.execute(
        "SELECT source,exported FROM playlists WHERE snapshot_id=? AND source!='liked'", (snapshot,))}
    groups = logical_playlists.definitions(db, account)
    collections_for = defaultdict(set)
    for group in groups.values():
        for playlist in group['members']:
            collections_for[playlist].add(group['collection_id'])
    personal, worldwide, history_coverage = stream_counts.observations(db)
    tracks = {}
    memberships = defaultdict(set)
    matches = set()
    term = term.casefold()
    for row in db.execute("""SELECT i.track_key,i.title,i.artists,i.source FROM items i
                              JOIN playlists p USING (snapshot_id,source)
                              WHERE i.snapshot_id=? AND p.exported=1 AND i.missing=0
                                AND i.identity_basis!='unidentified'
                                AND (i.track_key LIKE 'spotify:track:%' OR i.track_key LIKE 'spotify:local:%')
                              ORDER BY i.source,i.position""", (snapshot,)):
        key, title, raw_artists, source = row
        if key not in tracks or term and key not in matches:
            artists = json.loads(raw_artists)
            tracks.setdefault(key, dict(track_key=key, title=title, artists=artists))
            if term and term in " ".join([key, title or "", *(name for name in artists if name)]).casefold():
                matches.add(key)
        if source != "liked":
            memberships[key].add(source)

    selected = (tracks[key] for key in matches) if term else tracks.values()
    ranked = []
    for track in selected:
        key = track["track_key"]
        sources = memberships.get(key, ())
        categories = Counter(category_for[source] for source in sources if category_for.get(source))
        if groups or sort == 'collection':
            collections = {group for source in sources for group in collections_for.get(source, ())}
            track.update(observed_collection_count=len(collections), collection_ids=sorted(collections))
        track.update(
            playlist_score=len(sources) + len(categories),
            observed_playlist_count=len(sources),
            playlist_ids=sorted(sources),
            folder_category_count=len(categories),
            folder_categories=[dict(path=[name for _, name in path], folder_ids=[ident for ident, _ in path],
                                    playlist_count=count) for path, count in sorted(categories.items())],
            playlists_without_folder_bonus=len(sources) - sum(categories.values()),
            **stream_fields(personal.get(key, []), worldwide.get(key, [])),
        )
        ranked.append(track)

    field = SORT_FIELDS[sort]
    ranked.sort(key=lambda row: (
        row[field] is None, -(row[field] or 0), -row["playlist_score"], (row["title"] or "").casefold(), row["track_key"]))
    result = dict(
        snapshot=metadata,
        playlist_coverage=dict(exported=sum(playlist_coverage.values()), known=len(playlist_coverage),
                               exported_with_known_folder=sum(exported and bool(category_for.get(source))
                                                              for source, exported in playlist_coverage.items())),
        hierarchy={key: tree[key] for key in ("id", "imported_at", "file_modified_at", "provenance")} if tree else None,
        folder_depth=folder_depth,
        score_formula="One point per observed playlist plus one per distinct known folder category.",
        personal_history_coverage=history_coverage,
        matching_songs=len(ranked),
        songs=ranked[:limit],
    )
    if groups:
        result['collection_coverage'] = [dict(
            collection_id=group['collection_id'], name=group['name'], configured_members=len(group['members']),
            exported_members=sum(playlist_coverage.get(source, False) for source in group['members']),
        ) for group in groups.values()]
    return result
