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


def create_view(catalog, output, hierarchy=None):
    output = Path(output)
    for source in (catalog, hierarchy):
        if source is not None and (output.resolve() == Path(source).resolve() or
                                  (output.exists() and Path(source).exists() and output.samefile(source))):
            raise ValueError('Choose an HTML output separate from the catalog and hierarchy files.')
    snapshots = []
    with closing(library.connect(catalog)) as db:
        db.execute('BEGIN')
        for s in db.execute('SELECT id,label,created_at,account_id,status FROM snapshots ORDER BY id DESC'):
            sources = library.sources(db, s['id'])
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
                                  folders=folders, tree_imported_at=tree['imported_at'] if tree else None))
    if not snapshots:
        raise ValueError('This catalog has no snapshots.')
    data = json.dumps(snapshots, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    replacements = {
        '__DATA__': data,
        '__PATH__': html.escape(str(Path(catalog).resolve())),
    }
    page = re.sub(r'__DATA__|__PATH__', lambda match: replacements[match.group()], TEMPLATE)
    output.write_text(page, encoding='utf-8')
    return output.resolve()


TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personal Music Library — Catalog Viewer</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#173126;font:16px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:32px}h1{font-size:36px;margin:8px 0}.eyebrow{font-size:12px;font-weight:750;letter-spacing:2px}.note{background:#dfebe2;padding:16px;border-radius:12px;margin:18px 0;line-height:1.6}.path{font-size:12px;overflow-wrap:anywhere;color:#52665a}.controls{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}label{display:grid;gap:7px;flex:1;min-width:220px;font-weight:650}select,input{width:100%;padding:11px;border:1px solid #a5b6a8;border-radius:7px;background:white;font:inherit;color:inherit}.table{overflow:auto;background:white;border:1px solid #d3ddd5;border-radius:12px;max-height:62vh}table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;background:#eaf0eb;position:sticky;top:0}td,th{padding:13px;border-bottom:1px solid #e3e9e4}td:last-child{font:12px ui-monospace,monospace;overflow-wrap:anywhere;min-width:230px}#status{margin:15px 0;font-weight:600}footer{margin-top:18px;font-size:13px;color:#52665a;line-height:1.6}button{padding:10px;border:1px solid #a5b6a8;border-radius:7px;cursor:pointer;background:white;margin:12px 8px 0 0}
button.link{border:0;background:transparent;color:#126244;text-decoration:underline;padding:0;margin:0;text-align:left;font:inherit}
#details button.link,#status button.link{margin:4px 12px 4px 0}#details li{line-height:1.55}
#details dl{display:grid;grid-template-columns:max-content 1fr;gap:5px 14px}#details dt{font-weight:700}#details dd{margin:0}
#details ul{max-height:16rem;overflow:auto}
</style></head><body><main><div class="eyebrow">PERSONAL MUSIC LIBRARY / READ-ONLY</div>
<h1>Where is your music?</h1><div class="path">__PATH__</div>
<div class="note" id="notice"></div>
<div class="controls"><label>Saved snapshot<select id="snapshot"></select></label><label>Folder<select id="folder"></select></label><label>Playlist<select id="source"></select></label><label>Search songs, artists, albums or IDs<input id="search" type="search"></label></div>
<section id="details" class="note" hidden aria-live="polite"></section>
<div id="status" role="status"></div><div class="table"><table><thead><tr><th>Playlist</th><th>Position</th><th>Song</th><th>Artists</th><th>Type</th><th>Observed identity</th></tr></thead><tbody id="rows"></tbody></table></div>
<button id="previous">Previous page</button><button id="next">Next page</button>
<footer>One row means one placement. A song may appear in several playlists or twice in the same one.<br>Positions here start at 1. Local references do not prove the audio exists or plays on your phone.<br>This is a saved view: reopen the launcher after importing new data. It cannot edit the database or Spotify. No data is uploaded.</footer>
<script type="application/json" id="data">__DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const el=id=>document.getElementById(id);
let current, names, page = 0, selectedKey = '';
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
function load(key = '') {
    current = data[Number(el('snapshot').value)];
    names = new Map(current.sources.map(source => [source.source, source]));
    selectedKey = key;
    page = 0;
    el('details').hidden = true;
    el('folder').replaceChildren(option('All folders', ''));
    current.folders.forEach(folder => el('folder').append(option(folderLabel(folder.path), folder.id)));
    el('folder').disabled = !current.folders.length;
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
function searchCatalog(value) {
    selectedKey = '';
    el('folder').value = '';
    resetSources();
    el('search').value = value;
    page = 0;
    render();
}
function render() {
    const query = el('search').value.trim().toLocaleLowerCase(), source = el('source').value;
    const allowed = new Set(folderSources().map(item => item.source));
    const found = current.items.filter(row => allowed.has(row.source) && (!source || row.source === source) &&
        (!selectedKey || row.track_key === selectedKey) && (!query ||
            [row.title, row.artists, row.track_key, row.metadata.album, row.metadata.album_id,
                row.metadata.album_artist, row.metadata.isrc].join(' ').toLocaleLowerCase().includes(query)));
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
el('search').oninput = () => { selectedKey = ''; page = 0; render(); };
el('previous').onclick = () => { page--; render(); };
el('next').onclick = () => { page++; render(); };
load(requested >= 0 ? route.get('key') ?? '' : '');
</script></main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path, nargs='?')
    parser.add_argument('--hierarchy', type=Path, default=data_root() / 'hierarchy.sqlite')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    path = args.catalog or default_catalog()
    if path is None:
        parser.error('No catalog found. Run Try offline demo.cmd first, or provide a catalog.sqlite path.')
    if not path.is_file():
        parser.error(f'Catalog file not found: {path}')
    try:
        output = create_view(path, path.with_name('catalog-view.html'), args.hierarchy)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.error(f'Could not create the catalog view: {error}')
    print('Read-only catalog view:', output)
    if not args.no_open:
        webbrowser.open(output.as_uri())


if __name__ == '__main__':
    main()
