"""A bounded, offline explorer of completed sources in an audit SQLite database."""
from contextlib import closing
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import webbrowser

import folder_tree
import library
import local_inventory
from storage_paths import data_root


def load_trial(database, selected=None, max_playlists=8, max_rows=10000, hierarchy=None, inventory=None):
    if not 1 <= max_playlists <= 50 or not 1 <= max_rows <= 50000:
        raise ValueError('Trial limits: 1–50 playlists and 1–50,000 placements.')
    files = local_inventory.inventory_index(inventory) if inventory is not None else None
    if inventory is not None:
        inventory_summary = dict(scan_id=inventory.get('scan_id'), finished_at=inventory.get('finished_at'),
                                 complete=inventory.get('status') == 'complete' and all(
                                     root.get('status') == 'complete' for root in inventory['roots']))
    else:
        inventory_summary = None
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')  # Consistent local read, even if another process resumes the audit.
        saved = db.execute('SELECT data FROM run_state WHERE id=1').fetchone()
        if not saved:
            raise ValueError('Expected a resumable audit database.')
        state = json.loads(saved[0])
        sources = state['sources']
        complete = {k: v for k, v in sources.items() if v.get('status') == 'complete'}
        if selected:
            if len(set(selected)) != len(selected) or len(selected) > max_playlists:
                raise ValueError('Select distinct playlists within the trial limit.')
            if any(k not in complete for k in selected):
                raise ValueError('Only fully captured sources can be selected. Incomplete is not empty.')
            keys = selected
        else:
            # A useful mix of nonempty playlists without choosing the largest account collections.
            candidates = sorted(complete, key=lambda k: (not (50 <= complete[k]['count'] <= 1500), k))
            keys, used = [], 0
            for k in candidates:
                count = complete[k]['count']
                if count and used + count <= max_rows and len(keys) < max_playlists:
                    keys.append(k)
                    used += count
        if not keys:
            raise ValueError('No completed playlists fit the trial. No Spotify request was made.')
        if sum(complete[k]['count'] for k in keys) > max_rows:
            raise ValueError('Selected sources exceed the row budget; choose fewer playlists.')
        playlists, items = [], []
        for k in keys:
            source = complete[k]
            rows = db.execute('SELECT position,data FROM occurrences WHERE source=? ORDER BY position', (k,))
            count = 0
            for position, raw in rows:
                if position != count or len(items) >= max_rows:
                    raise ValueError('Invalid positions or row limit exceeded; no partial source is presented as complete.')
                row = json.loads(raw)
                identity, basis = library.identity(row, state['created_at'])
                item = dict(source=k, position=position + 1, key=identity, basis=basis,
                    title=row.get('title') or 'Unknown', artists=', '.join(row.get('artists') or []),
                    duration_ms=row.get('duration_ms'), local=bool(row.get('is_local')), missing=bool(row.get('missing')))
                if files is not None and item['local']:
                    title = None if item['missing'] else row.get('title')
                    candidates, conflicts, confirmation = local_inventory.file_candidates(
                        files, title, item['duration_ms'], uri=row.get('returned_uri'),
                        artists=row.get('artists') or [])
                    if confirmation:
                        confirmation = dict(confirmed_at=confirmation['confirmed_at'], paths=confirmation['paths'])
                    item['local_files'] = dict(candidates=candidates, conflicts=conflicts,
                                               confirmation=confirmation,
                                               usable_title=bool(title))
                items.append(item)
                count += 1
            if count != source['count'] or count != source['total']:
                raise ValueError('Source coverage/count mismatch; trial refused.')
            playlists.append(dict(id=k, name=source.get('metadata', {}).get('name') or ('Liked Songs' if k == 'liked' else k),
                count=count, captured_at=source.get('completed_at'), validated_at=source.get('validated_at')))
        known_sources = len(state['manifest']) + int(not state.get('selected_playlists'))
        return dict(account=state.get('account_id'), run=str(Path(database).resolve().parent),
                    run_status=state['status'], saved_at=state.get('updated_at'),
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    completed_sources=len(complete), known_sources=known_sources,
                    discovery_complete=state['discovery_complete'], playlists=playlists, items=items,
                    inventory=inventory_summary,
                    playlist_names={p['id']: p.get('name', p['id']) for p in state['manifest']},
                    hierarchy=folder_tree.latest_tree(hierarchy, state.get('account_id')) if hierarchy else None)


def render(data, output):
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(TEMPLATE.replace('__DATA__', payload), encoding='utf-8')
    return output.resolve()


TEMPLATE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your music — small trial</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f5f2;color:#18392c;font:16px system-ui}main{max-width:1400px;margin:auto;padding:28px}h1{font-size:36px;margin:8px 0}h2{font-size:20px}.banner,section{background:white;border:1px solid #d4dfd7;border-radius:12px;padding:18px;margin:16px 0}.banner{background:#e0efe6;line-height:1.6}.controls{display:flex;gap:14px;flex-wrap:wrap}label{display:grid;gap:6px;flex:1;min-width:190px}input,select,button{font:inherit;padding:9px;border:1px solid #a3b7aa;border-radius:6px;background:white;color:inherit}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:10px;border-bottom:1px solid #e5ece7}th{background:#eff5f0;position:sticky;top:0}.scroll{max-height:52vh;overflow:auto}small,.muted{color:#526b5e}.grid{display:grid;grid-template-columns:1fr 2fr;gap:18px}#tree{max-height:260px;overflow:auto}summary{cursor:pointer}#details{overflow-wrap:anywhere}#status{margin:16px 0;font-weight:650}button.link{border:0;padding:0;text-align:left;color:#126244;text-decoration:underline}footer{font-size:13px;line-height:1.6;margin-top:24px}@media(max-width:800px){.grid{display:block}main{padding:16px}}
th .sort-column{background:transparent;border:0;padding:0;text-align:left;font-weight:inherit}
.column-heading{display:flex;align-items:center;justify-content:space-between;gap:6px}
.filter-column{background:transparent;padding:3px 6px;border-color:transparent}
.filter-column[aria-pressed="true"]{background:#d1eadb;border-color:#4e8067;color:#164735}
.filter-column::before{content:"";display:block;width:14px;height:14px;background:currentColor;clip-path:polygon(0 12%,100% 12%,63% 55%,63% 93%,37% 78%,37% 55%)}
dialog{width:min(420px,calc(100% - 32px));max-height:calc(100% - 32px);padding:20px;border:1px solid #a3b7aa;border-radius:12px;color:inherit}
dialog::backdrop{background:#18392c55}dialog h2{margin-top:0}
.filter-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
#filter-apply{background:#126244;color:white;border-color:#126244}
dialog label{margin-top:10px;min-width:0}dialog label:has(input[type="checkbox"]){display:flex;align-items:baseline;gap:8px;margin:0;padding:4px}
.filter-values{max-height:21vh;overflow:auto;border:1px solid #e5ece7;overflow-wrap:anywhere}
</style><main><small>PERSONAL MUSIC LIBRARY · OFFLINE / READ ONLY</small><h1>Explore a little. Learn a lot.</h1>
<div id="coverage" class="banner"></div><div class="controls">
<label>Playlist A<select id="a"></select></label><label>Operation<select id="op"><option value="single">Browse A</option><option value="intersection">In both A and B</option><option value="difference">In A, absent from B</option><option value="reverse-difference">In B, absent from A</option><option value="union">In either A or B</option></select></label>
<label>Playlist B<select id="b"></select></label><label>Search title / artist / ID<input id="search" type="search"></label></div>
<div class="grid"><section><h2>Playlist folders</h2><div id="folder-note" class="muted"></div><div id="tree"></div><h2>Overlap with A</h2><div id="overlap"></div></section>
<section id="details"><h2>Where is this song?</h2><p>Click a song below to see its placements across the trial playlists.</p><small>Identity means the same observed Spotify ID or local URI. Different releases are not automatically merged.</small></section></div>
<div id="status" role="status"></div><div class="scroll"><table><thead><tr id="headings"></tr></thead><tbody id="rows"></tbody></table></div>
<button id="prev">Previous</button> <button id="next">Next</button>
<dialog id="column-filter" aria-labelledby="filter-title"><h2 id="filter-title"></h2>
<div class="filter-actions"><button id="sort-ascending" type="button">↑ Ascending</button><button id="sort-descending" type="button">↓ Descending</button></div>
<label>Filter by<select id="filter-mode"><option value="values">Value</option><option value="condition">Condition</option></select></label>
<div id="filter-by-value">
<label>Search values<input id="filter-search" type="search"></label>
<label><input id="filter-select-all" type="checkbox"> Select all matching values</label>
<div id="filter-values" class="filter-values"></div><small id="filter-value-count" role="status"></small>
</div>
<div id="filter-by-condition" hidden><label>Condition<select id="filter-operator"><option value="contains">Contains</option><option value="excludes">Does not contain</option><option value="equals">Equals</option></select></label>
<label>Text<input id="filter-text" type="text"></label></div>
<div class="filter-actions"><button id="filter-apply" type="button">Apply</button><button id="filter-cancel" type="button">Cancel</button><button id="filter-clear" type="button">Clear</button></div>
</dialog>
<footer id="foot"></footer></main><script id="data" type="application/json">__DATA__</script><script>
'use strict'; const d=JSON.parse(document.getElementById('data').textContent),el=id=>document.getElementById(id);let page=0;
const names=new Map(d.playlists.map(p=>[p.id,p.name])),songs=new Map(),sets=new Map(d.playlists.map(p=>[p.id,new Set()]));
for(const r of d.items){if(!songs.has(r.key))songs.set(r.key,{...r,placements:[]});songs.get(r.key).placements.push(r);if(r.basis!=='unidentified')sets.get(r.source).add(r.key);}
function option(text,value){const o=document.createElement('option');o.textContent=text;o.value=value;return o;}
for(const p of d.playlists){for(const id of ['a','b'])el(id).append(option(`${p.name} (${p.count.toLocaleString()} placements)`,p.id));}if(d.playlists.length>1)el('b').selectedIndex=1;
el('coverage').textContent=`REAL SAVED DATA — small trial: ${d.playlists.length} playlists, ${d.items.length.toLocaleString()} placements. The saved run has ${d.completed_sources}/${d.known_sources} known sources complete. This is a subset, not your entire library. No new Spotify requests. Liked Songs ${names.has('liked')?'is included.':'is NOT included.'}`;
el('foot').textContent=`Saved audit state: ${d.run_status} at ${d.saved_at}. This label is historical; it does not prove a process is running. Source: ${d.run}. Local entries are Spotify metadata references, not an inventory or backup of your audio files. Missing/unidentified items are excluded from set operations. Data stays in this file; no uploads or external scripts.`;
function addText(box, tag, text) {
    const node = document.createElement(tag);
    node.textContent = text;
    box.append(node);
}
function showLocalFiles(box, song) {
    addText(box, 'h3', 'Local file locations');
    if (!d.inventory) {
        addText(box, 'p', 'File locations were not checked. Spotify provides a local reference for this track.');
        return;
    }
    const {finished_at, scan_id, complete} = d.inventory;
    const scan = scan_id == null ? 'Inventory' : 'Inventory scan ' + scan_id;
    addText(box, 'p', scan + (finished_at ? ' saved ' + finished_at : '') +
        (complete ? ' · selected roots scanned' : ' · incomplete folder coverage'));
    const paths = new Map();
    const conflicts = new Map();
    const conflictLabels = {
        tag_title_differs: 'tag title differs',
        tag_artist_differs: 'tag artist differs',
        tag_album_differs: 'tag album differs',
        duration_differs: 'duration differs',
    };
    let confirmation = null;
    let usableTitle = false;
    for (const placement of song.placements) {
        const evidence = placement.local_files;
        if (!evidence) continue;
        usableTitle ||= evidence.usable_title;
        confirmation ||= evidence.confirmation;
        for (const candidate of evidence.candidates) {
            if (!paths.has(candidate.path) || candidate.evidence === 'audio_tags') {
                paths.set(candidate.path, candidate.evidence);
            }
        }
        for (const conflict of evidence.conflicts) {
            const reason = conflictLabels[conflict.reason];
            conflicts.set(conflict.path + ' · ' + reason, conflict.path);
        }
    }
    if (confirmation) {
        if (confirmation.paths.length) {
            addText(box, 'p', 'Confirmed file bytes · reviewed ' + confirmation.confirmed_at);
            const list = document.createElement('ul');
            for (const path of confirmation.paths) {
                addText(list, 'li', path);
                paths.delete(path);
            }
            box.append(list);
        } else {
            addText(box, 'p', 'A file was confirmed earlier. Its bytes were not observed in this inventory.');
        }
    }
    if (paths.size) {
        addText(box, 'p', paths.size === 1 ? 'One candidate' : paths.size + ' possible paths');
        const list = document.createElement('ul');
        for (const [path, basis] of paths) {
            addText(list, 'li', path + (basis === 'audio_tags' ? ' · audio tags' : ' · filename'));
        }
        box.append(list);
        addText(box, 'small', 'Candidates reflect the saved scan and need review.');
    } else if (!confirmation?.paths.length && !usableTitle) {
        addText(box, 'p', 'The saved reference has no usable title to compare.');
    } else if (!confirmation?.paths.length) {
        addText(box, 'p', complete ? 'No candidate in the scanned folders.' :
            'No candidate observed. Some folders or files could not be checked.');
    }
    if (conflicts.size) {
        addText(box, 'p', 'Metadata differences in at least one placement');
        const list = document.createElement('ul');
        for (const detail of conflicts.keys()) addText(list, 'li', detail);
        box.append(list);
    }
}
function showSong(song) {
    const box = el('details');
    box.replaceChildren();
    addText(box, 'h2', song.title + ' — ' + song.artists);
    addText(box, 'p', song.key);
    for (const r of song.placements) {
        addText(box, 'p', names.get(r.source) + ' · position ' + r.position);
    }
    addText(box, 'small', 'Membership shown only in selected trial sources.');
    if (song.local) showLocalFiles(box, song);
}
function matchesOperation(op, song, a, A, B) {
    if (op === 'single') return song.placements.some(row => row.source === a);
    const inA = A.has(song.key), inB = B.has(song.key);
    switch (op) {
        case 'intersection': return inA && inB;
        case 'difference': return inA && !inB;
        case 'reverse-difference': return inB && !inA;
        case 'union': return inA || inB;
        default: return false;
    }
}
function durationLabel(ms) {
    if (ms == null) return 'Unknown';
    const seconds = Math.round(ms / 1000);
    return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
}

for (const song of songs.values()) {
    song.type = song.missing ? 'Missing' : song.local ? 'Local reference' : 'Spotify';
    song.playlistCount = new Set(song.placements.map(row => row.source)).size;
}

const columns = [
    {label: 'Song', value: song => song.title},
    {label: 'Artist', value: song => song.artists},
    {label: 'Length', value: song => durationLabel(song.duration_ms), number: song => song.duration_ms},
    {label: 'Type', value: song => song.type},
    {label: 'Trial playlists', value: song => String(song.playlistCount), number: song => song.playlistCount},
];
const collator = new Intl.Collator(undefined, {sensitivity: 'base', numeric: true});
const filters = new Map();
let sortColumn = null;
let sortDirection = 1;
let filterColumn;
let filterValues;
let chosenValues;

function resetResults() {
    page = 0;
    el('rows').closest('.scroll').scrollTop = 0;
    render();
}

function sortBy(column, direction) {
    sortColumn = column;
    sortDirection = direction;
    for (const field of columns) {
        if (field === column) {
            field.heading.setAttribute('aria-sort', direction === 1 ? 'ascending' : 'descending');
            field.indicator.textContent = direction === 1 ? '↑' : '↓';
        } else {
            field.heading.removeAttribute('aria-sort');
            field.indicator.textContent = '↕';
        }
    }
    resetResults();
}

for (const column of columns) {
    const heading = document.createElement('th');
    heading.scope = 'col';
    const controls = document.createElement('div');
    controls.className = 'column-heading';
    const sort = document.createElement('button');
    sort.type = 'button';
    sort.className = 'sort-column';
    sort.textContent = column.label + ' ';
    const indicator = document.createElement('span');
    indicator.setAttribute('aria-hidden', 'true');
    indicator.textContent = '↕';
    sort.append(indicator);
    sort.onclick = () => sortBy(column, sortColumn === column ? -sortDirection : 1);

    const filter = document.createElement('button');
    filter.type = 'button';
    filter.className = 'filter-column';
    filter.setAttribute('aria-label', 'Filter ' + column.label);
    filter.setAttribute('aria-haspopup', 'dialog');
    filter.setAttribute('aria-pressed', 'false');
    filter.onclick = () => openFilter(column);
    controls.append(sort, filter);
    heading.append(controls);
    el('headings').append(heading);
    Object.assign(column, {heading, indicator, filter});
}

function baseResults() {
    const a = el('a').value, b = el('b').value, op = el('op').value;
    const query = el('search').value.toLocaleLowerCase();
    return [...songs.values()].filter(song =>
        matchesOperation(op, song, a, sets.get(a), sets.get(b)) &&
        [song.title, song.artists, song.key].join(' ').toLocaleLowerCase().includes(query));
}

function openFilter(column) {
    filterColumn = column;
    const saved = filters.get(column);
    const values = new Set(baseResults().map(column.value));
    // Keep previous selections available when the playlist operation or search changes.
    if (saved?.mode === 'values') {
        for (const value of saved.values) values.add(value);
    }
    filterValues = [...values].sort(collator.compare);
    chosenValues = new Set(saved?.mode === 'values' ? saved.values : filterValues);
    el('filter-title').textContent = 'Filter ' + column.label;
    el('filter-search').value = '';
    el('filter-mode').value = saved?.mode ?? 'values';
    el('filter-operator').value = saved?.operator ?? 'contains';
    el('filter-text').value = saved?.text ?? '';
    updateFilterMode();
    el('column-filter').showModal();
}

function matchingValues() {
    const query = el('filter-search').value.toLocaleLowerCase();
    return filterValues.filter(value => (value || '(Blank)').toLocaleLowerCase().includes(query));
}

function updateSelectAll(matches) {
    const checked = matches.filter(value => chosenValues.has(value)).length;
    const selectAll = el('filter-select-all');
    selectAll.checked = matches.length > 0 && checked === matches.length;
    selectAll.indeterminate = checked > 0 && checked < matches.length;
    selectAll.disabled = matches.length === 0;
}

function renderFilterValues() {
    const matches = matchingValues();
    const list = el('filter-values');
    const limit = 200;
    list.replaceChildren();
    list.scrollTop = 0;
    for (const value of matches.slice(0, limit)) {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = chosenValues.has(value);
        checkbox.onchange = () => {
            if (checkbox.checked) chosenValues.add(value);
            else chosenValues.delete(value);
            updateSelectAll(matches);
        };
        label.append(checkbox, value || '(Blank)');
        list.append(label);
    }
    el('filter-value-count').textContent = matches.length > limit ?
        `Showing first ${limit} of ${matches.length.toLocaleString()} values. Search to narrow the list.` :
        `${matches.length.toLocaleString()} matching values`;
    updateSelectAll(matches);
}

function updateFilterMode() {
    const byValue = el('filter-mode').value === 'values';
    el('filter-by-value').hidden = !byValue;
    el('filter-by-condition').hidden = byValue;
    if (byValue) renderFilterValues();
}

function saveFilter(filter) {
    if (filter) filters.set(filterColumn, filter);
    else filters.delete(filterColumn);
    filterColumn.filter.setAttribute('aria-pressed', String(Boolean(filter)));
    el('column-filter').close();
    resetResults();
}

el('filter-mode').onchange = updateFilterMode;
el('filter-search').oninput = renderFilterValues;
el('filter-select-all').onchange = event => {
    for (const value of matchingValues()) {
        if (event.target.checked) chosenValues.add(value);
        else chosenValues.delete(value);
    }
    renderFilterValues();
};
el('filter-apply').onclick = () => {
    const mode = el('filter-mode').value;
    if (mode === 'values') {
        saveFilter(chosenValues.size === filterValues.length ? null : {mode, values: chosenValues});
    } else {
        const operator = el('filter-operator').value;
        const text = el('filter-text').value.trim();
        saveFilter(text || operator === 'equals' ? {mode, operator, text} : null);
    }
};
el('filter-clear').onclick = () => saveFilter(null);
el('filter-cancel').onclick = () => el('column-filter').close();
for (const [button, direction] of [['sort-ascending', 1], ['sort-descending', -1]]) {
    el(button).onclick = () => {
        el('column-filter').close();
        sortBy(filterColumn, direction);
    };
}

function matchesFilter(value, filter) {
    if (filter.mode === 'values') return filter.values.has(value);
    const text = filter.text.toLocaleLowerCase();
    const candidate = value.toLocaleLowerCase();
    if (filter.operator === 'equals') return candidate === text;
    if (filter.operator === 'excludes') return !candidate.includes(text);
    return candidate.includes(text);
}

function compareSongs(left, right) {
    if (!sortColumn.number) {
        return sortDirection * collator.compare(sortColumn.value(left), sortColumn.value(right));
    }
    const a = sortColumn.number(left), b = sortColumn.number(right);
    if (a == null) return b == null ? 0 : 1;
    if (b == null) return -1;
    return sortDirection * (a - b);
}

function render() {
    const activeFilters = [...filters];
    const found = baseResults().filter(song =>
        activeFilters.every(([column, filter]) => matchesFilter(column.value(song), filter)));
    if (sortColumn) found.sort(compareSongs);
    page = Math.min(page, Math.max(0, Math.ceil(found.length / 100) - 1));
    el('rows').replaceChildren();
    for (const song of found.slice(page * 100, page * 100 + 100)) {
        const row = document.createElement('tr');
        const title = document.createElement('td');
        const button = document.createElement('button');
        button.className = 'link';
        button.textContent = song.title;
        button.onclick = () => showSong(song);
        title.append(button);
        row.append(title);
        for (const column of columns.slice(1)) addText(row, 'td', column.value(song));
        el('rows').append(row);
    }
    el('status').textContent = `${found.length.toLocaleString()} observed identities · page ${page + 1} · duplicates grouped; click a song for every position`;
    el('prev').disabled = page === 0;
    el('next').disabled = (page + 1) * 100 >= found.length;
    const a = el('a').value;
    const keys = [...sets.get(a)];
    const overlaps = d.playlists.filter(p => p.id !== a)
        .map(p => ({...p, shared: keys.filter(key => sets.get(p.id).has(key)).length}))
        .sort((left, right) => right.shared - left.shared);
    el('overlap').replaceChildren();
    for (const playlist of overlaps) {
        const row = document.createElement('p');
        const button = document.createElement('button');
        button.className = 'link';
        button.textContent = `${playlist.name}: ${playlist.shared} shared`;
        button.onclick = () => {
            el('b').value = playlist.id;
            el('op').value = 'intersection';
            resetResults();
        };
        row.append(button);
        el('overlap').append(row);
    }
}
if(!d.hierarchy){el('folder-note').textContent='Folder hierarchy NOT captured yet. A flat playlist list does not preserve folders.';}else{el('folder-note').textContent=`Imported ${d.hierarchy.imported_at}. Cached tree; upstream capture time/completeness unverified. Folder capture is separate from track coverage.`;const parents=new Map([[null,el('tree')]]);for(const n of d.hierarchy.nodes){const parent=parents.get(n.parent_id);if(n.kind==='folder'){const det=document.createElement('details'),sum=document.createElement('summary');sum.textContent=n.name||'(unnamed folder)';det.append(sum);parent.append(det);parents.set(n.node_id,det);}else{const row=document.createElement('p');if(names.has(n.provider_id)){const btn=document.createElement('button');btn.className='link';btn.textContent=names.get(n.provider_id);btn.onclick=()=>{el('a').value=n.provider_id;el('op').value='single';page=0;render();};row.append(btn);}else row.textContent=(d.playlist_names[n.provider_id]||n.provider_id)+' — outside trial';parent.append(row);}}}
for(const id of ['a','b','op','search'])el(id).addEventListener(id==='search'?'input':'change',()=>{page=0;render();});el('prev').onclick=()=>{page--;render();};el('next').onclick=()=>{page++;render();};render();
</script></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, help='Existing audit folder; defaults to newest resumable run')
    p.add_argument('--playlist', action='append', help='Select a completed source ID; repeat for comparison')
    p.add_argument('--max-playlists', type=int, default=8)
    p.add_argument('--max-rows', type=int, default=10000)
    p.add_argument('--hierarchy', type=Path, default=data_root() / 'hierarchy.sqlite')
    inventory_source = p.add_mutually_exclusive_group()
    inventory_source.add_argument('--inventory', type=Path, help='Saved local inventory JSON')
    inventory_source.add_argument('--inventory-db', type=Path, help='Saved local inventory SQLite database')
    p.add_argument('--inventory-scan', type=int, help='Scan ID in --inventory-db; defaults to newest saved scan')
    p.add_argument('--output', type=Path, default=data_root() / 'previews' / 'trial.html')
    p.add_argument('--open', action='store_true')
    args = p.parse_args()
    if args.inventory_scan is not None and args.inventory_db is None:
        p.error('--inventory-scan requires --inventory-db')
    try:
        run = args.run
        if run is None:
            candidates = list((data_root() / 'backups').glob('*/library.sqlite'))
            if not candidates:
                raise ValueError('No saved audit found. Specify --run with a resumable audit folder.')
            run = max(candidates, key=lambda path: path.stat().st_mtime).parent
        audit_db = run / 'library.sqlite'
        inputs = (audit_db, args.hierarchy, args.inventory_db, args.inventory)
        if any(path is not None and (
               path.resolve() == args.output.resolve() or
               (path.exists() and args.output.exists() and path.samefile(args.output)))
               for path in inputs):
            raise ValueError('Choose an HTML output separate from the saved evidence files.')
        inventory = None
        if args.inventory_db is not None:
            inventory = local_inventory.load_inventory(args.inventory_db, args.inventory_scan)
        elif args.inventory is not None:
            inventory = json.loads(args.inventory.read_text(encoding='utf-8-sig'))
            if isinstance(inventory, dict):
                inventory.pop('confirmations', None)
        data = load_trial(audit_db, args.playlist, args.max_playlists, args.max_rows,
                          args.hierarchy, inventory=inventory)
        output = render(data, args.output)
        print(f"Real-data trial: {len(data['playlists'])} sources, {len(data['items']):,} placements. No Spotify requests.")
        print(output)
        if args.open:
            webbrowser.open(output.as_uri())
    except (ValueError, OSError, sqlite3.Error) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
