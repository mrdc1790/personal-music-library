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
from storage_paths import data_root


def load_trial(database, selected=None, max_playlists=8, max_rows=10000, hierarchy=None):
    if not 1 <= max_playlists <= 50 or not 1 <= max_rows <= 50000:
        raise ValueError('Trial limits: 1–50 playlists and 1–50,000 placements.')
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
                items.append(dict(source=k, position=position + 1, key=identity, basis=basis,
                    title=row.get('title') or 'Unknown', artists=', '.join(row.get('artists') or []),
                    duration_ms=row.get('duration_ms'), local=bool(row.get('is_local')), missing=bool(row.get('missing'))))
                count += 1
            if count != source['count'] or count != source['total']:
                raise ValueError('Source coverage/count mismatch; trial refused.')
            playlists.append(dict(id=k, name=source.get('metadata', {}).get('name') or ('Liked Songs' if k == 'liked' else k),
                count=count, captured_at=source.get('completed_at'), validated_at=source.get('validated_at')))
        return dict(account=state.get('account_id'), run=str(Path(database).resolve().parent),
                    run_status=state['status'], saved_at=state.get('updated_at'),
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    completed_sources=len(complete), known_sources=len(state['manifest']) + 1,
                    discovery_complete=state['discovery_complete'], playlists=playlists, items=items,
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
</style><main><small>PERSONAL MUSIC LIBRARY · OFFLINE / READ ONLY</small><h1>Explore a little. Learn a lot.</h1>
<div id="coverage" class="banner"></div><div class="controls">
<label>Playlist A<select id="a"></select></label><label>Operation<select id="op"><option value="single">Browse A</option><option value="intersection">In both A and B</option><option value="difference">In A, absent from B</option><option value="union">In either A or B</option></select></label>
<label>Playlist B<select id="b"></select></label><label>Search title / artist / ID<input id="search" type="search"></label></div>
<div class="grid"><section><h2>Playlist folders</h2><div id="folder-note" class="muted"></div><div id="tree"></div><h2>Overlap with A</h2><div id="overlap"></div></section>
<section id="details"><h2>Where is this song?</h2><p>Click a song below to see its placements across the trial playlists.</p><small>Identity means the same observed Spotify ID or local URI. Different releases are not automatically merged.</small></section></div>
<div id="status" role="status"></div><div class="scroll"><table><thead><tr><th>Song</th><th>Artist</th><th>Length</th><th>Type</th><th>Trial playlists</th></tr></thead><tbody id="rows"></tbody></table></div>
<button id="prev">Previous</button> <button id="next">Next</button>
<footer id="foot"></footer></main><script id="data" type="application/json">__DATA__</script><script>
'use strict'; const d=JSON.parse(document.getElementById('data').textContent),el=id=>document.getElementById(id);let page=0;
const names=new Map(d.playlists.map(p=>[p.id,p.name])),songs=new Map(),sets=new Map(d.playlists.map(p=>[p.id,new Set()]));
for(const r of d.items){if(!songs.has(r.key))songs.set(r.key,{...r,placements:[]});songs.get(r.key).placements.push(r);if(r.basis!=='unidentified')sets.get(r.source).add(r.key);}
function option(text,value){const o=document.createElement('option');o.textContent=text;o.value=value;return o;}
for(const p of d.playlists){for(const id of ['a','b'])el(id).append(option(`${p.name} (${p.count.toLocaleString()} placements)`,p.id));}if(d.playlists.length>1)el('b').selectedIndex=1;
el('coverage').textContent=`REAL SAVED DATA — small trial: ${d.playlists.length} playlists, ${d.items.length.toLocaleString()} placements. The saved run has ${d.completed_sources}/${d.known_sources} known sources complete. This is a subset, not your entire library. No new Spotify requests. Liked Songs ${names.has('liked')?'is included.':'is NOT included.'}`;
el('foot').textContent=`Saved audit state: ${d.run_status} at ${d.saved_at}. This label is historical; it does not prove a process is running. Source: ${d.run}. Local entries are Spotify metadata references, not an inventory or backup of your audio files. Missing/unidentified items are excluded from set operations. Data stays in this file; no uploads or external scripts.`;
function showSong(song){const box=el('details');box.replaceChildren();const h=document.createElement('h2');h.textContent=song.title+' — '+song.artists;box.append(h);const id=document.createElement('p');id.textContent=song.key;box.append(id);for(const r of song.placements){const p=document.createElement('p');p.textContent=`${names.get(r.source)} · position ${r.position}`;box.append(p);}const note=document.createElement('small');note.textContent='Membership shown only in selected trial sources. Absence here says nothing about the rest of your account.';box.append(note);}
function render(){const a=el('a').value,b=el('b').value,op=el('op').value,A=sets.get(a),B=sets.get(b),q=el('search').value.toLocaleLowerCase();let found=[...songs.values()].filter(s=>{const present=s.placements.some(r=>r.source===a);return op==='single'?present:op==='intersection'?A.has(s.key)&&B.has(s.key):op==='difference'?A.has(s.key)&&!B.has(s.key):A.has(s.key)||B.has(s.key);}).filter(s=>[s.title,s.artists,s.key].join(' ').toLocaleLowerCase().includes(q));
page=Math.min(page,Math.max(0,Math.ceil(found.length/100)-1));el('rows').replaceChildren();for(const s of found.slice(page*100,page*100+100)){const tr=document.createElement('tr'),td=document.createElement('td'),btn=document.createElement('button');btn.className='link';btn.textContent=s.title;btn.onclick=()=>showSong(s);td.append(btn);tr.append(td);const sec=Math.round((s.duration_ms||0)/1000);for(const v of [s.artists,s.duration_ms==null?'Unknown':Math.floor(sec/60)+':'+String(sec%60).padStart(2,'0'),s.missing?'Missing':s.local?'Local reference':'Spotify',new Set(s.placements.map(r=>r.source)).size]){const c=document.createElement('td');c.textContent=v;tr.append(c);}el('rows').append(tr);}el('status').textContent=`${found.length.toLocaleString()} observed identities · page ${page+1} · duplicates grouped; click a song for every position`;el('prev').disabled=page===0;el('next').disabled=(page+1)*100>=found.length;
el('overlap').replaceChildren();const overlaps=d.playlists.filter(p=>p.id!==a).map(p=>({...p,shared:[...A].filter(k=>sets.get(p.id).has(k)).length})).sort((x,y)=>y.shared-x.shared);for(const p of overlaps){const row=document.createElement('p'),btn=document.createElement('button');btn.className='link';btn.textContent=`${p.name}: ${p.shared} shared`;btn.onclick=()=>{el('b').value=p.id;el('op').value='intersection';page=0;render();};row.append(btn);el('overlap').append(row);}}
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
    p.add_argument('--output', type=Path, default=data_root() / 'previews' / 'trial.html')
    p.add_argument('--open', action='store_true')
    args = p.parse_args()
    try:
        run = args.run
        if run is None:
            candidates = list((data_root() / 'backups').glob('*/library.sqlite'))
            if not candidates:
                raise ValueError('No saved audit found. Specify --run with a resumable audit folder.')
            run = max(candidates, key=lambda path: path.stat().st_mtime).parent
        data = load_trial(run / 'library.sqlite', args.playlist, args.max_playlists, args.max_rows, args.hierarchy)
        output = render(data, args.output)
        print(f"Real-data trial: {len(data['playlists'])} sources, {len(data['items']):,} placements. No Spotify requests.")
        print(output)
        if args.open:
            webbrowser.open(output.as_uri())
    except (ValueError, OSError, sqlite3.Error) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
