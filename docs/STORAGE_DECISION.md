# Storage decision: SQLite for the local catalog

Reviewed on 2026-09-30 against the “Compare database options” discussion and current source. Decision: retain SQLite as the primary local catalog and resumable-capture store. Alternatives have been considered at the architecture level; this is not a benchmark of every engine or a claim that future workloads have already been tested.

## Why it fits

The current workload is one account's local historical metadata: snapshots, sources, ordered occurrences, memberships, and coverage evidence. Relational constraints and transactions fit those relationships. Python's standard-library `sqlite3` keeps installation simple without a database service. A larger track count alone is not a reason to replace the engine; measure actual history size, latency, memory use, and write contention.

`library.py` currently has schema version 1, foreign-key enforcement, an indexed item lookup, transactional imports, read-only query connections, and consistent backup/restore with checksums and integrity checks. The operational scan database and historical catalog are separate formats; they are not interchangeable. Raw JSON remains source evidence/interchange, CSV remains a report format, and migration journals remain separate evidence. A SQLite commit cannot make Spotify writes transactional.

SQLite's [deployment guidance](https://www.sqlite.org/whentouse.html) supports device-local application storage and notes one writer per database at a time. Remote clients can still use an application API with SQLite local to that server. Multiple jobs can serialize short writes; mobile access, hosting, or multiple users alone do not mandate an engine change. They do require explicit authentication, isolation, availability, and sync design, which this project does not currently implement.

## Alternatives and their place

| Approach | Decision for this project | Revisit when |
|---|---|---|
| SQLite | Selected operational catalog; retain relational evidence and occurrence ordering | Measured contention, deployment, or dataset requirements exceed the local design |
| PostgreSQL | Leading candidate for a future shared server database, not a current dependency | Concurrent writes cannot practically queue, several app servers need shared state, or central administration/isolation is required |
| MySQL/MariaDB | Viable server alternatives; no current project requirement favors them over the local engine | Deployment or team requirements favor their ecosystem; compare then rather than assuming inferiority |
| Supabase | Hosted PostgreSQL/service option, not a separate database model | Authorized cloud deployment needs its API/auth/operations features; review privacy, cost, access, and backup responsibilities |
| DuckDB | Optional downstream analytics engine, not a planned replacement for catalog state | Large listening-history or analytical exports justify it through measured queries |
| JSON files | Retain raw snapshots and versioned interchange; not the only membership/history query store | New source adapters need faithful raw evidence |
| CSV / Parquet | CSV exists for inspection/export; Parquet could support analytical datasets | Typed columnar exports materially help larger analytics and an approved dependency is justified |
| MongoDB | Document storage is possible, but incoming Spotify JSON alone does not justify it | A distinct document-centric workload outweighs occurrence joins, constraints, and server operations |
| Redis | Potential cache, not the authoritative historical catalog | A measured cache need appears; define invalidation and persistence requirements separately |
| IndexedDB | Potential browser cache/offline state, not the current historical catalog | A browser client needs structured persistence; define export, eviction, recovery, and sync explicitly |
| LMDB / RocksDB | Embedded key/value alternatives, with no present advantage established | A measured key/value workload warrants rebuilding relational indexes and integrity logic |

[DuckDB's documentation](https://duckdb.org/docs/stable/connect/concurrency) describes an analytical concurrency model; do not simplify that into “it cannot do transactions.” [PostgreSQL's concurrency documentation](https://www.postgresql.org/docs/current/mvcc.html) is a starting point for a server evaluation. No alternative service or package was installed or configured by this review.

## Cross-project storage status — October 27, 2026

The October 22 browser recovery implementation did not extend or populate this
Python database, change its schema, or optimize its query paths. The October 27
refresh updates plans/docs only. Keep these stores and their guarantees distinct:

| Store | Implemented role | Boundary |
|---|---|---|
| Per-run capture SQLite | Committed source rows and resumable capture state | Operational run format; not interchangeable with the historical catalog |
| Historical catalog SQLite | Imported immutable snapshot history and local queries | Existing schema/query implementation; useful real coverage and scale validation remain work |
| Browser IndexedDB | Persisted ordered URI/version/page checkpoints and selected-input draft | Recoverable preview cache; site data can be evicted or cleared; never execution authority |
| Browser session storage / memory | Explicit fallback when IndexedDB is unavailable | Weaker recovery, reported in the UI; not a durable backup |
| Browser local storage | Client-scoped cooldown state and existing browser auth configuration | Separate from preview contents and from Python storage; changing origin does not transfer it |
| Migration journals | Existing guarded Python executor journal | Browser equivalent and catalog journal interchange are not implemented |

The [catalog delivery order](ROADMAP.md#next-work) starts with saved evidence,
historical import, and playlist capacity reporting. Measure report and
exact-instance query cost before expanding browsing. The current
lookup/set/compare paths materialize snapshot rows despite the existing
exact-instance index. Use the historical catalog for these queries and keep
browser recovery and any later repair handoff separate.

## Work before changing engines

- Benchmark synthetic histories with at least 100,000 observed identities,
  more placements than identities, local references, repeated snapshots, and
  incomplete coverage. Measure import cost, query/report latency, and peak
  memory. Push filtering/joins into SQL and measure the results before
  considering a change of database engine.
- Keep the evidence model explicit: recordings, releases, provider instances, owned files, occurrences, and candidate/review decisions remain separate. A relationship graph can be represented with relational tables; the term “graph” does not itself require a graph database. Changing engines cannot fix identity or incomplete-coverage mistakes.
- Add schema migrations only when needed, with version checks, a verified backup, preservation of older evidence, and synthetic upgrade/restore tests. A PostgreSQL move would need explicit type, constraint, SQL, ID, transaction, and backup conversion checks; it is not an automatic file conversion.
- Keep active databases on supported local storage through `storage_paths.py`. Use consistent verified archives for transfer/backup, not simultaneous edits to a cloud-synced or network-shared live file. [WAL](https://www.sqlite.org/wal.html) may improve reader/writer coexistence but still has one writer and extra files/checkpoint considerations; it is not enabled by this decision or a multi-machine sync mechanism.

The browser migrator was checked: its preview checkpoints and cooldown storage are recovery state, not a historical catalog. Its October 22, 2026 update adds IndexedDB preview persistence, with explicit session/memory fallback and fresh version checks on resume. This does not require this catalog to be complete or add SQLite to the browser. A future durable mutation journal or versioned catalog interface still needs a separate design and tests; neither app opens the other's database. The chat can be deleted without losing these choices or reconsideration criteria.
