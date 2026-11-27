"""Save and rerun a local playlist set query as a versioned JSON recipe."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

import library
from storage_paths import data_root


OPERATIONS = ('union', 'intersection', 'difference')


def validate(recipe):
    if (not isinstance(recipe, dict) or set(recipe) != {'version', 'name', 'operation', 'sources'}
            or type(recipe['version']) is not int or recipe['version'] != 1
            or not isinstance(recipe['name'], str) or not recipe['name'].strip()
            or recipe['operation'] not in OPERATIONS or not isinstance(recipe['sources'], list)
            or not all(isinstance(source, str) and source.strip() for source in recipe['sources'])
            or len(set(recipe['sources'])) != len(recipe['sources']) or len(recipe['sources']) < 2):
        raise ValueError('Expected a version 1 playlist recipe with a name, operation, and distinct source IDs.')


def run(db, sid, recipe):
    validate(recipe)
    captured_at, status = db.execute('SELECT created_at,status FROM snapshots WHERE id=?', (sid,)).fetchone()
    matches = library.set_query(db, sid, recipe['operation'], recipe['sources'])
    return dict(recipe=recipe, snapshot_id=sid, captured_at=captured_at, snapshot_status=status,
                source_members=library.query_sources(db, sid, recipe['sources']),
                coverage='complete exports for all selected sources', order='observed identity key ascending',
                matching_identities=len(matches), tracks=matches)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=data_root() / 'catalog.sqlite')
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('save', help='Write a new reusable recipe file')
    save.add_argument('output', type=Path)
    save.add_argument('name')
    save.add_argument('operation', choices=OPERATIONS)
    save.add_argument('sources', nargs='+')
    preview = commands.add_parser('preview', help='Run a recipe on saved evidence and write a new result file')
    preview.add_argument('recipe', type=Path)
    preview.add_argument('output', type=Path)
    preview.add_argument('--snapshot', type=int)
    args = parser.parse_args()
    try:
        if args.command == 'save':
            document = dict(version=1, name=args.name.strip(), operation=args.operation, sources=args.sources)
            validate(document)
        else:
            recipe = json.loads(args.recipe.read_text(encoding='utf-8-sig'))
            with closing(library.connect(args.db)) as db:
                db.execute('BEGIN')
                document = run(db, library.snapshot_id(db, args.snapshot), recipe)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'{error}\n')
    print('Saved recipe.' if args.command == 'save' else f'Saved preview for {document["matching_identities"]} identities.')


if __name__ == '__main__':
    main()
