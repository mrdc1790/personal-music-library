from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import genre_enrichment as genres
import library
import preview_audit


ISRC = 'USABC2600001'
RECORDING = '59adae3e-8445-4d88-9675-d45369aa6ac2'
FETCHED = '2026-11-26T12:34:56+00:00'


def track(**changes):
    return dict({'title': 'Song', 'artists': ['Artist'], 'duration_ms': 192000, 'isrc': ISRC}, **changes)


def recording(**changes):
    return dict({
        'id': RECORDING, 'title': 'Song', 'length': 193000, 'artist-credit': [{'name': 'Artist'}],
        'genres': [{'name': 'trip hop'}, {'name': 'downtempo'}],
    }, **changes)


class GenreEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'genre.sqlite'

    def test_match_requires_same_version_and_preserves_unknowns(self):
        ref = genres.reference(track(title='  SONG ', isrc='US-ABC-26-00001'))
        tags = recording()['genres']
        self.assertEqual(genres.observation(ref, lambda entity, _: (
            FETCHED, [recording()] if entity == 'isrc' else tags)), dict(
            status='matched', fetched_at=FETCHED, recording_id=RECORDING, genres=['downtempo', 'trip hop']))
        for rows, status in [
            ([], 'unmatched'),
            ([recording(), recording(title='Remix')], 'ambiguous'),
            ([recording(title='Song - remix')], 'mismatch'),
            ([recording(length=196000)], 'mismatch'),
            ([recording(**{'artist-credit': [{'name': 'Different'}]})], 'mismatch'),
            ([recording()], 'no_genres'),
        ]:
            with self.subTest(status=status, rows=rows):
                resolved = genres.observation(ref, lambda entity, _: (FETCHED, rows if entity == 'isrc' else []))
                self.assertEqual(resolved['status'], status)
                self.assertFalse(resolved.get('genres'))
        self.assertEqual(genres.observation(ref, lambda *_: None)['status'], 'pending')
        self.assertIsNone(genres.reference(track(is_local=True)))
        self.assertIsNone(genres.reference(track(isrc='bad')))

    def test_bounded_resumable_cache_and_no_catalog_mutation(self):
        first = genres.reference(track())
        second = genres.reference(track(isrc='USABC2600002'))
        fetch = Mock(side_effect=[[recording()], ValueError('temporary failure'), recording()['genres'], []])
        with closing(genres.connect(self.cache, write=True)) as db, patch.object(genres.time, 'sleep'):
            result = genres.enrich(db, [first, second, first], 1, fetch)
            self.assertEqual(result['requests'], 1)
            self.assertEqual(result['coverage']['pending'], 1)
            self.assertEqual(result['coverage']['genre_pending'], 1)
            with self.assertRaisesRegex(ValueError, 'temporary failure'):
                genres.enrich(db, [first, second], 1, fetch)
            self.assertEqual(genres.enrich(db, [first, second], 2, fetch)['coverage'],
                             {'matched': 1, 'unmatched': 1})
        with closing(genres.connect(self.cache)) as db:
            self.assertEqual(genres.enrich(db, [first, second], 0, fetch)['requests'], 0)
        self.assertEqual([call.args for call in fetch.call_args_list],
                         [('isrc', ISRC), ('recording', RECORDING), ('recording', RECORDING), ('isrc', second[0])])
        catalog = self.root / 'catalog.sqlite'
        with closing(library.connect(catalog, write=True)):
            pass
        original = catalog.read_bytes()
        with self.assertRaisesRegex(ValueError, 'separate cache'):
            genres.connect(catalog, write=True)
        self.assertEqual(catalog.read_bytes(), original)

    def test_request_sends_only_isrc_and_handles_provider_failures(self):
        with patch.object(genres, 'urlopen', return_value=BytesIO(json.dumps({
            'recordings': [recording()],
        }).encode())) as open_url:
            self.assertEqual(genres.lookup('isrc', ISRC), [recording()])
            request = open_url.call_args.args[0]
            self.assertIn('/isrc/' + ISRC + '?', request.full_url)
            self.assertIn('inc=artist-credits', request.full_url)
            self.assertIn('PersonalMusicLibrary', request.get_header('User-agent'))
        with patch.object(genres, 'urlopen', return_value=BytesIO(json.dumps(recording()).encode())) as open_url:
            self.assertEqual(genres.lookup('recording', RECORDING), recording()['genres'])
            self.assertIn('inc=genres', open_url.call_args.args[0].full_url)
        for code in (404, 503):
            with self.subTest(code=code), patch.object(genres, 'urlopen', side_effect=HTTPError(
                    'https://musicbrainz.org', code, '', {'Retry-After': '30'}, None)):
                if code == 404:
                    self.assertEqual(genres.lookup('isrc', ISRC), [])
                else:
                    with self.assertRaisesRegex(ValueError, '503.*Retry-After'):
                        genres.lookup('isrc', ISRC)

    def test_read_only_preview_keeps_musicbrainz_genre_distinct(self):
        audit = self.root / 'library.sqlite'
        with closing(sqlite3.connect(audit)) as db, db:
            db.executescript('CREATE TABLE run_state(id INTEGER, data TEXT);'
                             'CREATE TABLE occurrences(source TEXT, position INTEGER, data TEXT);')
            state = dict(created_at=FETCHED, status='running', discovery_complete=True, manifest=[{'id': 'mix'}],
                         sources={'mix': dict(status='complete', count=1, total=1)})
            db.execute('INSERT INTO run_state VALUES(1,?)', (json.dumps(state),))
            row = track(source='mix', position=0, returned_id='spotify-id')
            db.execute('INSERT INTO occurrences VALUES (?, ?, ?)', ('mix', 0, json.dumps(row)))
        with closing(genres.connect(self.cache, write=True)) as db, db:
            db.executemany('INSERT INTO responses VALUES (?, ?, ?, ?)', [
                ('isrc', ISRC, FETCHED, json.dumps([recording()])),
                ('recording', RECORDING, FETCHED, json.dumps(recording()['genres'])),
            ])
        with closing(genres.connect(self.cache)) as cache:
            data = preview_audit.load_trial(audit, ['mix'], genre_cache=cache)
        item, = data['items']
        self.assertFalse(item.get('genre'))
        self.assertEqual(item['recording_genre']['genres'], ['downtempo', 'trip hop'])
        html = preview_audit.render(data, self.root / 'comparison.html').read_text(encoding='utf-8')
        self.assertIn('Genre (MusicBrainz recording)', html)
        self.assertIn(RECORDING, html)

    def test_catalog_pass_only_reads_exported_sources_in_selected_snapshot(self):
        with closing(library.connect(self.root / 'catalog.sqlite', write=True)) as db, db:
            db.executemany('INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?)', [
                (1, 'first', 'Capture', 'me', FETCHED, 'partial', '{}'),
                (2, 'second', 'Other capture', 'me', FETCHED, 'complete', '{}'),
            ])
            for snapshot, source, exported, isrc in [
                (1, 'complete', 1, ISRC), (1, 'partial', 0, 'USABC2600002'),
                (2, 'complete', 1, 'USABC2600003'),
            ]:
                db.execute('INSERT INTO playlists VALUES (?, ?, ?, ?, ?)', (snapshot, source, source, exported, '{}'))
                db.execute('INSERT INTO items (snapshot_id, source, position, track_key, identity_basis, is_local, '
                           'missing, raw_json) VALUES (?, ?, 0, ?, ?, 0, 0, ?)',
                           (snapshot, source, isrc, 'returned_uri_only', json.dumps(track(isrc=isrc))))
            self.assertEqual(list(genres.snapshot_references(db, 1, set())), [genres.reference(track())])
            with self.assertRaisesRegex(ValueError, 'fully exported'):
                genres.snapshot_references(db, 1, {'complete', 'partial'})
