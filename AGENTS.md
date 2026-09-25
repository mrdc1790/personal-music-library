# Personal Music Library — contributor guidance

## Project purpose and safety

This is a local, evidence-preserving catalog for Spotify playlist metadata and
related audit/migration workflows. Treat source snapshots, scan status, failed
coverage, duplicate occurrences, and historical records as evidence: do not
silently discard, deduplicate, or reinterpret them.

- Default to read-only workflows. Do not add an account-changing Spotify action
  or run a migration unless the task explicitly asks for it.
- Never treat a failed, partial, unreadable, or unexported source as empty.
- Preserve duplicate playlist occurrences and source ordering where the data
  model supports them.
- Keep credentials, access tokens, personal snapshots, SQLite databases, and
  generated reports out of commits and tool output.
- Keep storage defaults outside OneDrive Documents; use the existing
  `storage_paths.py` helpers rather than inventing new data locations.

## Navigation and impact analysis

Use Dekko for unfamiliar-codebase navigation, dependency tracing, symbol
discovery, caller/callee analysis, change-impact analysis, and identifying
relevant tests.

- Prefer focused queries such as summary, search, outline, context, diff,
  affected, and workset before broad repository reads.
- Do not use Dekko for a trivial change when the relevant implementation is
  already known.
- Treat its map as navigation help, not implementation truth: read the actual
  source before changing it.
- If Dekko is unavailable, unindexed, or stale, use targeted `rg` searches and
  direct source/test inspection; regenerate the map when the installed Dekko
  workflow supports it.
- For low- or zero-caller results that matter to correctness, sanity-check with
  Dekko when available and verify against the source.

## Source formatting

Keep source files human-readable.

- Never minify source files.
- Use 4 spaces for Python indentation; never introduce literal tabs.
- Use normal blank lines between top-level functions, classes, and logical
  sections.
- Prefer separate `const`/`let`-style declarations in non-Python examples and
  separate Python assignments when names represent different concepts.
- Do not chain unrelated declarations with commas.
- Prefer readability over minimizing line count; keep one statement per line
  where practical and do not compress functions onto one line.
- Preserve existing conventions and keep edits formatter-friendly.

## Implementation and verification

- Keep the standard-library-first design unless a dependency is clearly
  justified and explicitly approved by the task.
- Make schema, export, and parser changes backward-compatible where possible;
  existing catalogs and snapshots may be valuable personal history.
- Update or add focused `unittest` coverage with behavior changes. Use temporary
  directories/databases in tests; do not rely on personal data or network access.
- Run the smallest relevant test file first (for example,
  `python -m unittest test_library.py`), then the broader relevant suite when
  the change crosses modules.
- Clearly distinguish test fixtures and demo data from real user data in code,
  output, and documentation.

## Working-tree discipline

- Inspect the working tree before edits and preserve unrelated user changes.
- Keep diffs narrow; avoid opportunistic rewrites.
- Do not modify generated backups, personal scan outputs, or sample mappings
  unless the task specifically calls for them.

## Cross-repository coordination

The sibling repository at
`..\spotify song playlist migrator` is a
separate application with related Spotify migration and reconciliation
workflows. Its behavior is not automatically shared with this catalog.

- Before changing shared Spotify assumptions—read/write boundaries, saved-track
  handling, duplicate occurrences, partial coverage, reconciliation, OAuth
  scopes, or migration safety—inspect the sibling repository for affected
  code, tests, and user documentation.
- For unfamiliar cross-repository impact, use targeted Dekko queries in the
  migrator (which has a `.dekko` map) and targeted `rg` searches in both
  repositories. Read the matching source before deciding whether a companion
  change is needed.
- Keep each repository independently runnable and testable. Do not create a
  runtime dependency, shared relative path, or cross-repo import without an
  explicit task requirement.
- Make a companion edit only when a behavior, safety promise, interface, or
  documentation claim would otherwise become inconsistent. State that linked
  impact in the change summary and run the relevant tests in every changed
  repository.
- When no sibling change is required, record that the cross-repository impact
  was checked; do not broaden a focused task merely for symmetry.
