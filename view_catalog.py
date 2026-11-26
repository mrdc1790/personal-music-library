"""Create a searchable, read-only HTML view of a local music catalog. No server required."""
import argparse
from storage_paths import data_root
from contextlib import closing
import html
import json
from pathlib import Path
import re
import sqlite3
import webbrowser

import folder_tree
import library
import logical_playlists
import track_metadata


def default_catalog():
    root = Path(__file__).resolve().parent
    external = data_root() / 'catalog.sqlite'
    if external.exists():
        return external
    real = root / 'data/catalog.sqlite'
    if real.exists():
        return real
    candidates = list((root / 'backups').glob('catalog-demo-*/catalog.sqlite'))
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def create_view(catalog, output, hierarchy=None, snapshot=None):
    output = Path(output)
    for source in (catalog, hierarchy):
        if source is not None and (output.resolve() == Path(source).resolve() or
                                  (output.exists() and Path(source).exists() and output.samefile(source))):
            raise ValueError('Choose an HTML output separate from the catalog and hierarchy files.')
    snapshots = []
    with closing(library.connect(catalog)) as db:
        db.execute('BEGIN')
        ratings = library.song_ratings(db)
        query = 'SELECT id,label,created_at,account_id,status FROM snapshots'
        parameters = ()
        if snapshot is not None:
            query += ' WHERE id=?'
            parameters = (library.snapshot_id(db, snapshot),)
        for s in db.execute(query + ' ORDER BY id DESC', parameters):
            sources = library.sources(db, s['id'])
            groups = logical_playlists.definitions(db, s['account_id'])
            sources_by_id = {source['source']: source for source in sources}
            collections = [logical_playlists.describe(group, sources_by_id) for group in groups.values()]
            tree = folder_tree.latest_tree(hierarchy, s['account_id']) if hierarchy else None
            folders, paths, membership = folder_tree.folder_paths(tree)
            for source in sources:
                source['paths'] = paths.get(source['source'], [])
                source['folders'] = sorted(membership.get(source['source'], ()))
            items = []
            for row in db.execute('SELECT source,position,title,artists,track_key,identity_basis,is_local,missing,raw_json '
                                  'FROM items WHERE snapshot_id=? ORDER BY source,position', (s['id'],)):
                item = dict(row)
                item['artists'] = ', '.join(json.loads(item['artists']))
                item['metadata'] = track_metadata.card(json.loads(item.pop('raw_json')))
                items.append(item)
            snapshots.append(dict(s, sources=sources, items=items,
                                  collections=collections,
                                  folders=folders, tree_imported_at=tree['imported_at'] if tree else None))
    if not snapshots:
        raise ValueError('This catalog has no snapshots.')
    data = json.dumps(snapshots, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    replacements = {
        '__DATA__': data,
        '__RATINGS__': json.dumps(list(ratings.items()), ensure_ascii=True).replace('<', '\\u003c'),
        '__PATH__': html.escape(str(Path(catalog).resolve())),
    }
    page = re.sub(r'__DATA__|__RATINGS__|__PATH__', lambda match: replacements[match.group()], TEMPLATE)
    output.write_text(page, encoding='utf-8')
    return output.resolve()


TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personal Music Library — Catalog Viewer</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#173126;font:16px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:32px}h1{font-size:36px;margin:8px 0}.eyebrow{font-size:12px;font-weight:750;letter-spacing:2px}.note{background:#dfebe2;padding:16px;border-radius:12px;margin:18px 0;line-height:1.6}.path{font-size:12px;overflow-wrap:anywhere;color:#52665a}.controls{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}label{display:grid;gap:7px;flex:1;min-width:220px;font-weight:650}select,input{width:100%;padding:11px;border:1px solid #a5b6a8;border-radius:7px;background:white;font:inherit;color:inherit}.table{overflow:auto;background:white;border:1px solid #d3ddd5;border-radius:12px;max-height:62vh}table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;background:#eaf0eb;position:sticky;top:0}td,th{padding:13px;border-bottom:1px solid #e3e9e4}td:last-child{font:12px ui-monospace,monospace;overflow-wrap:anywhere;min-width:230px}#status{margin:15px 0;font-weight:600}footer{margin-top:18px;font-size:13px;color:#52665a;line-height:1.6}button{padding:10px;border:1px solid #a5b6a8;border-radius:7px;cursor:pointer;background:white;margin:12px 8px 0 0}
button.link{border:0;background:transparent;color:#126244;text-decoration:underline;padding:0;margin:0;text-align:left;font:inherit}
.controls #clear-filters{align-self:flex-end;margin:0;font:inherit;color:inherit}
.controls [hidden]{display:none}
#details button.link,#status button.link{margin:4px 12px 4px 0}#details li{line-height:1.55}
#details dl{display:grid;grid-template-columns:max-content 1fr;gap:5px 14px}#details dt{font-weight:700}#details dd{margin:0}
#details ul{max-height:16rem;overflow:auto}#details label{max-width:200px}
</style></head><body><main><div class="eyebrow">PERSONAL MUSIC LIBRARY / READ-ONLY</div>
<h1>Where is your music?</h1><div class="path">__PATH__</div>
<div class="note" id="notice"></div>
<div class="controls"><label>Saved snapshot<select id="snapshot"></select></label><label>Folder<select id="folder"></select></label><label>Playlist<select id="source"></select></label><label>Search songs, artists, albums or IDs<input id="search" type="search"></label>
<label id="collection-control" hidden>Logical playlist<select id="collection"></select></label>
<label>Rating<select id="rating-filter"><option value="">Any rating</option><option value="unrated">Unrated</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label>
<label>Order<select id="rating-order"><option value="">Source order</option><option value="highest">Highest rating first</option><option value="lowest">Lowest rating first</option></select></label>
<button id="clear-filters" type="button">Clear all filters</button></div>
<section id="collection-details" class="note" hidden></section>
<section id="details" class="note" hidden aria-live="polite"></section>
<div id="rating-changes" hidden><button id="download-ratings" type="button">Download rating changes</button><span id="rating-status" role="status"></span></div>
<div id="status" role="status"></div><div class="table"><table><thead><tr><th>Playlist</th><th>Position</th><th>Song</th><th>Artists</th><th>Type</th><th>Rating</th><th>Observed identity</th></tr></thead><tbody id="rows"></tbody></table></div>
<button id="previous">Previous page</button><button id="next">Next page</button>
<footer>One row means one placement. A song may appear in several playlists or twice in the same one.<br>Positions here start at 1. Local presence and playback require separate evidence.<br>Reopen the launcher after importing new data or applying rating changes. No data is uploaded.</footer>
<script type="application/json" id="data">__DATA__</script>
<script type="application/json" id="ratings">__RATINGS__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const el=id=>document.getElementById(id);
const ratings = new Map(JSON.parse(el('ratings').textContent));
const ratingChanges = new Map();
const ratingFor = key => ratingChanges.has(key) ? ratingChanges.get(key) : (ratings.get(key) ?? null);
let current, names, page = 0, selectedKey = '';
let collection = null;
const route = new URLSearchParams(location.hash.slice(1));
function option(text, value) {
    const node = document.createElement('option');
    node.textContent = text;
    node.value = value;
    return node;
}
function append(parent, tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    parent.append(node);
    return node;
}
function action(parent, label, handler) {
    const button = append(parent, 'button', label);
    button.type = 'button';
    button.className = 'link';
    button.onclick = handler;
    return button;
}
function folderLabel(path) {
    return path.join(' / ') || 'Root';
}
function playlistLabel(source) {
    const folders = source.paths.map(folderLabel).join(' · ');
    return folders ? folders + ' / ' + source.name : source.name;
}
function folderSources() {
    if (el('folder').value === '') return current.sources;
    const folder = Number(el('folder').value);
    return current.sources.filter(source => source.folders.includes(folder));
}
function resetSources() {
    el('source').replaceChildren(option('All sources in this view', ''));
    for (const source of folderSources()) {
        const coverage = source.exported ? source.occurrences + ' items' : 'unknown coverage';
        el('source').append(option(playlistLabel(source) + ' — ' + coverage, source.source));
    }
}
function showCollection(key = '') {
    collection = current.collections.find(group => group.collection_id === key) ?? null;
    el('collection').value = collection?.collection_id ?? '';
    el('folder').disabled = Boolean(collection) || !current.folders.length;
    el('source').disabled = Boolean(collection);
    const details = el('collection-details');
    details.hidden = !collection;
    details.replaceChildren();
    if (!collection) return;
    el('folder').value = '';
    resetSources();
    const members = new Set(collection.members.map(member => member.playlist_id));
    const identities = new Set();
    for (const row of current.items) {
        if (members.has(row.source) && row.identity_basis !== 'unidentified') identities.add(row.track_key);
    }
    append(details, 'h2', collection.name);
    append(details, 'p', `${collection.observed_placements.toLocaleString()} observed placements · ` +
        `${identities.size.toLocaleString()} observed identities · ${collection.complete ? 'Complete members' : 'Partial coverage'}`);
    const list = document.createElement('ol');
    for (const member of collection.members) {
        const item = append(list, 'li', '');
        if (member.coverage === 'absent') item.append(`${member.playlist_id} · absent from this capture`);
        else {
            action(item, member.name, () => browsePlaylist(member.playlist_id));
            item.append(` · ${member.placements.toLocaleString()} observed placements · ${member.coverage}`);
        }
        if (member.playlist_id === collection.active_playlist) item.append(' · Active volume');
    }
    details.append(list);
}
function load(key = '') {
    current = data[Number(el('snapshot').value)];
    names = new Map(current.sources.map(source => [source.source, source]));
    selectedKey = key;
    page = 0;
    el('details').hidden = true;
    el('folder').replaceChildren(option('All folders', ''));
    current.folders.forEach(folder => el('folder').append(option(folderLabel(folder.path), folder.id)));
    el('collection-control').hidden = !current.collections.length;
    el('collection').replaceChildren(option('All playlists', ''), ...current.collections.map(
        group => option(group.name, group.collection_id)));
    showCollection();
    resetSources();
    const tree = current.tree_imported_at
        ? ' Folder paths come from the cached import dated ' + current.tree_imported_at + '.'
        : ' No folder tree is available for this account.';
    el('notice').textContent = (current.account_id.startsWith('SYNTHETIC') ? 'SYNTHETIC DEMO. ' : '') +
        'Capture status: ' + current.status + '.' + tree;
    render();
    if (key) {
        const row = current.items.find(item => item.track_key === key && item.identity_basis !== 'unidentified');
        if (row) showSong(row);
    }
}
function browsePlaylist(source) {
    selectedKey = '';
    el('search').value = '';
    el('folder').value = '';
    showCollection();
    resetSources();
    el('source').value = source;
    page = 0;
    render();
}
function showSong(row) {
    const details = el('details');
    details.hidden = false;
    details.replaceChildren();
    append(details, 'h2', (row.title || 'Unknown') + ' — ' + row.artists);
    append(details, 'p', row.track_key);
    const placements = row.identity_basis === 'unidentified' ? [row] :
        current.items.filter(item => item.track_key === row.track_key);
    if (row.identity_basis !== 'unidentified') {
        const label = append(details, 'label', 'Your rating');
        const rating = document.createElement('select');
        rating.append(option('Unrated', ''), ...[1, 2, 3, 4, 5].map(value => option(`${value}/5`, value)));
        rating.value = ratingFor(row.track_key) ?? '';
        rating.onchange = () => {
            const next = rating.value ? Number(rating.value) : null;
            if (next === (ratings.get(row.track_key) ?? null)) ratingChanges.delete(row.track_key);
            else ratingChanges.set(row.track_key, next);
            el('rating-changes').hidden = !ratingChanges.size;
            el('rating-status').textContent = `${ratingChanges.size} unsaved rating change(s)`;
            render();
        };
        label.append(rating);
    }
    const fields = [['album', 'Album'], ['album_artist', 'Album artist'], ['release_date', 'Release date'],
        ['isrc', 'ISRC'], ['genre', 'Genre (album or artist)'], ['track_number', 'Track number'],
        ['disc_number', 'Disc number']];
    const metadata = document.createElement('dl');
    for (const [field, label] of fields) {
        const values = [...new Set(placements.map(item => item.metadata[field]).filter(value => value != null))];
        append(metadata, 'dt', label);
        append(metadata, 'dd', values.join(' · ') || 'Unavailable in this snapshot');
    }
    details.append(metadata);
    if (row.identity_basis !== 'unidentified') {
        action(details, 'Show only this identity', () => {
            selectedKey = row.track_key;
            el('search').value = '';
            el('folder').value = '';
            resetSources();
            page = 0;
            render();
        });
    }
    if (row.metadata.album_id || row.metadata.album) {
        action(details, 'Find this album', () => searchCatalog(row.metadata.album_id || row.metadata.album));
    }
    if (row.artists) action(details, 'Find these artist credits', () => searchCatalog(row.artists));
    append(details, 'h3', `${placements.length} observed placement(s) in snapshot ${current.id}`);
    if (row.identity_basis === 'unidentified') append(details, 'p', 'This placement has no usable identity.');
    const list = document.createElement('ul');
    for (const item of placements) {
        const source = names.get(item.source);
        const entry = append(list, 'li', '');
        action(entry, playlistLabel(source), () => browsePlaylist(source.source));
        entry.append(' · position ' + (item.position + 1) +
            (item.metadata.added_at ? ' · Added ' + item.metadata.added_at : '') +
            (source.exported ? '' : ' · partial source'));
    }
    details.append(list);
    details.scrollIntoView({block: 'nearest'});
}
function searchCatalog(value = '') {
    selectedKey = '';
    el('folder').value = '';
    showCollection();
    resetSources();
    el('search').value = value;
    page = 0;
    render();
}
function render() {
    const query = el('search').value.trim().toLocaleLowerCase(), source = el('source').value;
    const ratingFilter = el('rating-filter').value, ratingOrder = el('rating-order').value;
    const members = collection && new Map(collection.members.map((member, position) => [member.playlist_id, position]));
    const allowed = members || new Set(folderSources().map(item => item.source));
    const found = current.items.filter(row => allowed.has(row.source) && (!source || row.source === source) &&
        (!ratingFilter || (ratingFilter === 'unrated' ? ratingFor(row.track_key) === null :
            ratingFor(row.track_key) === Number(ratingFilter))) &&
        (!selectedKey || row.track_key === selectedKey) && (!query ||
            [row.title, row.artists, row.track_key, row.metadata.album, row.metadata.album_id,
                row.metadata.album_artist, row.metadata.isrc].join(' ').toLocaleLowerCase().includes(query)));
    const rank = key => {
        const rating = ratingFor(key);
        return rating === null ? 6 : (ratingOrder === 'highest' ? -rating : rating);
    };
    if (ratingOrder || members) found.sort((a, b) =>
        (ratingOrder ? rank(a.track_key) - rank(b.track_key) : 0) ||
        (members ? members.get(a.source) - members.get(b.source) : 0));
    const last = Math.max(0, Math.ceil(found.length / 200) - 1);
    page = Math.min(page, last);
    el('rows').replaceChildren();
    for (const item of found.slice(page * 200, (page + 1) * 200)) {
        const row = document.createElement('tr');
        const source = names.get(item.source);
        action(append(row, 'td', ''), playlistLabel(source), () => browsePlaylist(source.source));
        append(row, 'td', item.position + 1);
        action(append(row, 'td', ''), item.title || 'Unknown', () => showSong(item));
        append(row, 'td', item.artists);
        append(row, 'td', item.missing ? 'Missing' : item.is_local ? 'Local' : 'Catalog');
        const rating = ratingFor(item.track_key);
        append(row, 'td', rating === null ? '—' : `${rating}/5`);
        append(row, 'td', item.track_key);
        el('rows').append(row);
    }
    const unknown = current.sources.filter(item => !item.exported).length;
    const status = el('status');
    status.textContent = `${found.length.toLocaleString()} matching placements · Page ${page + 1} of ${last + 1}`;
    if (unknown) status.append(` · ${unknown} known sources have unknown coverage.`);
    if (selectedKey) action(status, 'Clear exact identity filter', () => {
        selectedKey = '';
        page = 0;
        render();
    });
    el('previous').disabled = page === 0;
    el('next').disabled = page === last;
}
data.forEach((snapshot, i) => el('snapshot').append(option(
    `${snapshot.id}: ${snapshot.label} — ${snapshot.created_at || 'unknown date'}`, i)));
const requested = data.findIndex(snapshot => String(snapshot.id) === route.get('snapshot'));
const broadest = data.reduce((best, snapshot, i) => {
    const count = s => s.sources.filter(source => source.exported && source.source !== 'liked').length;
    return count(snapshot) > count(data[best]) ? i : best;
}, 0);
el('snapshot').selectedIndex = requested >= 0 ? requested : broadest;
el('snapshot').onchange = () => load();
el('folder').onchange = () => { resetSources(); page = 0; render(); };
el('source').onchange = () => { selectedKey = ''; page = 0; render(); };
el('collection').onchange = () => {
    showCollection(el('collection').value);
    selectedKey = '';
    page = 0;
    render();
};
el('search').oninput = () => { selectedKey = ''; page = 0; render(); };
for (const id of ['rating-filter', 'rating-order']) el(id).onchange = () => { page = 0; render(); };
el('clear-filters').onclick = () => {
    el('rows').closest('.table').scrollTop = 0;
    el('rating-filter').value = '';
    el('rating-order').value = '';
    searchCatalog();
};
el('download-ratings').onclick = () => {
    const changes = Array.from(ratingChanges, ([track_key, rating]) => ({
        track_key, before: ratings.get(track_key) ?? null, rating,
    }));
    const payload = {format: 'personal-music-library-ratings-1', account: current.account_id, changes};
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'catalog-rating-changes.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    el('rating-status').textContent = 'Apply this file locally with library.py import-ratings.';
};
el('previous').onclick = () => { page--; render(); };
el('next').onclick = () => { page++; render(); };
load(requested >= 0 ? route.get('key') ?? '' : '');
</script></main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path, nargs='?')
    parser.add_argument('--hierarchy', type=Path, default=data_root() / 'hierarchy.sqlite')
    parser.add_argument('--snapshot', type=int, help='Generate a smaller explorer for just this snapshot')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    path = args.catalog or default_catalog()
    if path is None:
        parser.error('No catalog found. Run Try offline demo.cmd first, or provide a catalog.sqlite path.')
    if not path.is_file():
        parser.error(f'Catalog file not found: {path}')
    try:
        name = 'catalog-view.html' if args.snapshot is None else f'catalog-view-{args.snapshot}.html'
        output = create_view(path, path.with_name(name), args.hierarchy, args.snapshot)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.error(f'Could not create the catalog view: {error}')
    print('Read-only catalog view:', output)
    if not args.no_open:
        webbrowser.open(output.as_uri())


if __name__ == '__main__':
    main()
