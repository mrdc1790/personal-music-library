"""Create a searchable, read-only HTML view of a local music catalog. No server required."""
import argparse
from storage_paths import data_root
from contextlib import closing
import html
import json
from pathlib import Path
import webbrowser

import library


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


def create_view(catalog, output):
    snapshots = []
    with closing(library.connect(catalog)) as db:
        for s in db.execute('SELECT id,label,created_at,account_id FROM snapshots ORDER BY id DESC'):
            sources = library.sources(db, s['id'])
            items = [{k: r[k] for k in ('source','position','title','artists','track_key','identity_basis','is_local','missing')}
                     for r in library.rows(db, s['id'])]
            snapshots.append(dict(s, sources=sources, items=items))
    if not snapshots:
        raise ValueError('This catalog has no snapshots.')
    data = json.dumps(snapshots, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = TEMPLATE.replace('__DATA__', data).replace('__PATH__', html.escape(str(Path(catalog).resolve())))
    Path(output).write_text(page, encoding='utf-8')
    return Path(output).resolve()


TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personal Music Library — Catalog Viewer</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#173126;font:16px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:32px}h1{font-size:36px;margin:8px 0}.eyebrow{font-size:12px;font-weight:750;letter-spacing:2px}.note{background:#dfebe2;padding:16px;border-radius:12px;margin:18px 0;line-height:1.6}.path{font-size:12px;overflow-wrap:anywhere;color:#52665a}.controls{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}label{display:grid;gap:7px;flex:1;min-width:220px;font-weight:650}select,input{width:100%;padding:11px;border:1px solid #a5b6a8;border-radius:7px;background:white;font:inherit;color:inherit}.table{overflow:auto;background:white;border:1px solid #d3ddd5;border-radius:12px;max-height:62vh}table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;background:#eaf0eb;position:sticky;top:0}td,th{padding:13px;border-bottom:1px solid #e3e9e4}td:last-child{font:12px ui-monospace,monospace;overflow-wrap:anywhere;min-width:230px}#status{margin:15px 0;font-weight:600}footer{margin-top:18px;font-size:13px;color:#52665a;line-height:1.6}button{padding:10px;border:1px solid #a5b6a8;border-radius:7px;cursor:pointer;background:white;margin:12px 8px 0 0}
</style></head><body><main><div class="eyebrow">PERSONAL MUSIC LIBRARY / READ-ONLY</div>
<h1>Where is your music?</h1><div class="path">__PATH__</div>
<div class="note" id="notice"></div>
<div class="controls"><label>Saved snapshot<select id="snapshot"></select></label><label>Playlist<select id="source"></select></label><label>Song, artist or ID<input id="search" type="search" placeholder="Try Moonrise"></label></div>
<div id="status" role="status"></div><div class="table"><table><thead><tr><th>Playlist</th><th>Position</th><th>Song</th><th>Artists</th><th>Type</th><th>Observed identity</th></tr></thead><tbody id="rows"></tbody></table></div>
<button id="previous">Previous page</button><button id="next">Next page</button>
<footer>One row means one placement. A song may appear in several playlists or twice in the same one.<br>Positions here start at 1. Local references do not prove the audio exists or plays on your phone.<br>This is a saved view: reopen the launcher after importing new data. It cannot edit the database or Spotify. No data is uploaded.</footer>
<script type="application/json" id="data">__DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const el=id=>document.getElementById(id);
let current,page=0;
function option(text,value){const o=document.createElement('option');o.textContent=text;o.value=value;return o;}
data.forEach((s,i)=>el('snapshot').append(option(`${s.id}: ${s.label} — ${s.created_at||'unknown date'}`,i)));
function load(){current=data[Number(el('snapshot').value)];page=0;el('source').replaceChildren(option('All playlists + Liked Songs',''));
current.sources.forEach(s=>el('source').append(option(`${s.name} — ${s.exported?s.occurrences+' items':'NOT EXPORTED'}`,s.source)));
el('notice').textContent=(current.account_id.startsWith('SYNTHETIC')?'SYNTHETIC DEMO — these are made-up songs, not your Spotify account. ':'')+'Choose a playlist to browse it, or leave all playlists selected and search a song to see everywhere it appears.';render();}
function render(){const q=el('search').value.trim().toLocaleLowerCase(),source=el('source').value;
const found=current.items.filter(r=>(!source||r.source===source)&&[r.title,r.artists,r.track_key].join(' ').toLocaleLowerCase().includes(q));
const max=Math.max(0,Math.ceil(found.length/200)-1);page=Math.min(page,max);el('rows').replaceChildren();
const names=new Map(current.sources.map(s=>[s.source,s.name]));
for(const r of found.slice(page*200,(page+1)*200)){const tr=document.createElement('tr');
const values=[names.get(r.source),r.position+1,r.title||'Unknown',JSON.parse(r.artists).join(', '),r.missing?'Missing':r.is_local?'Local':'Catalog',r.track_key];
for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}el('rows').append(tr);}
const unknown=current.sources.filter(s=>!s.exported).length;
el('status').textContent=`${found.length.toLocaleString()} matching placements • Page ${page+1} of ${max+1}`+(unknown?` • ${unknown} sources were not exported; their contents are unknown.`:'');
el('previous').disabled=page===0;el('next').disabled=page===max;}
el('snapshot').addEventListener('change',load);el('source').addEventListener('change',()=>{page=0;render()});el('search').addEventListener('input',()=>{page=0;render()});el('previous').addEventListener('click',()=>{page--;render()});el('next').addEventListener('click',()=>{page++;render()});load();
</script></main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path, nargs='?')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    path = args.catalog or default_catalog()
    if path is None:
        parser.error('No catalog found. Run Try offline demo.cmd first, or provide a catalog.sqlite path.')
    output = create_view(path, path.with_name('catalog-view.html'))
    print('Read-only catalog view:', output)
    if not args.no_open:
        webbrowser.open(output.as_uri())


if __name__ == '__main__':
    main()
