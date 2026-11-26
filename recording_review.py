"""Store explicit pairwise recording decisions without changing captured identities."""

from datetime import datetime, timezone


DECISIONS = ('same-recording', 'keep-separate', 'clear')
SCHEMA = """
CREATE TABLE IF NOT EXISTS recording_reviews (
 id INTEGER PRIMARY KEY, left_key TEXT NOT NULL, right_key TEXT NOT NULL,
 decision TEXT NOT NULL CHECK (decision IN ('same-recording','keep-separate','clear')),
 reason TEXT NOT NULL, reviewed_at TEXT NOT NULL, CHECK (left_key < right_key));
CREATE INDEX IF NOT EXISTS recording_review_pair ON recording_reviews(left_key,right_key,id);
"""


def save(db, left, right, decision, reason):
    if (left == right or not all(key.startswith(('spotify:track:', 'spotify:local:')) for key in (left, right))
            or decision not in DECISIONS or not reason.strip()):
        raise ValueError('Choose two distinct observed track keys, a review decision, and a reason.')
    left, right = sorted((left, right))
    with db:
        db.execute('BEGIN IMMEDIATE')
        for key in (left, right):
            if not db.execute('SELECT 1 FROM items WHERE snapshot_id IN (SELECT id FROM snapshots) AND track_key=? '
                              "AND identity_basis!='unidentified' LIMIT 1", (key,)).fetchone():
                raise ValueError('Both reviewed identities must be present in the catalog.')
        previous = db.execute('SELECT id,decision,reason FROM recording_reviews WHERE left_key=? AND right_key=? '
                              'ORDER BY id DESC LIMIT 1', (left, right)).fetchone()
        if previous is not None and previous['decision'] == decision and previous['reason'] == reason.strip():
            return dict(review_id=previous['id'], added=False)
        if decision == 'clear' and (previous is None or previous['decision'] == 'clear'):
            raise ValueError('This pair has no active recording review to clear.')
        identifier = db.execute('INSERT INTO recording_reviews(left_key,right_key,decision,reason,reviewed_at) '
                                'VALUES (?,?,?,?,?)', (left, right, decision, reason.strip(),
                                                       datetime.now(timezone.utc).isoformat())).lastrowid
    return dict(review_id=identifier, added=True)


def reviews(db, key=None, history=False):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='recording_reviews'").fetchone():
        return []
    conditions, params = [], ()
    if not history:
        conditions.extend(("decision!='clear'", 'id IN (SELECT MAX(id) FROM recording_reviews GROUP BY left_key,right_key)'))
    if key is not None:
        conditions.append('(left_key=? OR right_key=?)')
        params = (key, key)
    where = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
    return [dict(row) for row in db.execute('SELECT * FROM recording_reviews' + where + ' ORDER BY id', params)]
