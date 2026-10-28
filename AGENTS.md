# Personal Music Library — contributor guidance

## Project purpose and safety

For user-specific music-library context retained across project chats, read
`data/user-context.md` when present. This private, Git-ignored note contains
dated user reports, not verified device state; keep its contents out of commits.

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

### Dekko in a workspace with multiple repositories

- Pass an explicit absolute `root` on every Dekko MCP call. For this repo use
  `C:\Users\polla\Documents\ChatGPT\personal-music-library`; for the sibling use
  `C:\Users\polla\Documents\ChatGPT\spotify song playlist migrator`.
  Resolve the checkout's actual absolute path if the workspace moves.
- Roots are independent indexes. Query each affected repo separately; the shared
  parent directory does not combine their maps. Never assume a previous call
  changes the default root: an omitted `root` uses the server's configured cwd.
- Start with `map_status(root=...)`; use `refresh_map(root=...)` if stale or
  missing. Reuse a fresh map until relevant source changes; avoid repeated rebuilds.
- For unfamiliar work, use a compact `summary` once, then focused `search_code`
  or `outline` queries. Once a symbol is known, prefer file-qualified symbols
  and a budgeted `get_context_pack` or `workset` over broad reads and repeated
  searches. Read the actual source and relevant tests before editing.
- Before relying on caller/callee impact, use `check_ambiguous` and spot-check
  affected ambiguous calls in source. Include tests with `get_callers` when
  needed. A zero result is a navigation lead, not proof of no impact; verify
  with targeted `rg`. Cross-repo impact requires separate queries in both roots.
- Prefer the working Dekko MCP tools here. The standalone CLI failed during the
  2026-09-30 workspace test with `uv trampoline failed to canonicalize script
  path`, while MCP refresh/search/impact calls worked. If MCP is unavailable,
  use targeted `rg` and source/test inspection rather than repeatedly retrying
  the broken CLI. Reassess the CLI if its installation changes.

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

The sibling repository `..\spotify song playlist migrator` is a
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

## Shared GitHub Project tracking

For work performed for repository owner `mrdc1790`, use the existing
[Personal Development Project](https://github.com/users/mrdc1790/projects/1)
when tracking adds value. This is a private planning workspace; outside
contributors are not expected to have access.

- Track substantial features, bugs, work spanning repositories, multi-session
  work, and meaningful blockers or follow-ups. Skip typo fixes, tiny cleanups,
  and routine questions unless the owner asks to track them. Do not import an
  entire backlog or create tasks just because an older repository exists.
- At the start of worthwhile work, check the Project and relevant repository
  issues for an existing item. Reuse it instead of creating duplicates. If
  needed, add the repository issue or pull request, or create a private draft
  with the repository name and a concrete outcome.
- Maintain Status (Todo, In Progress, Done), Area (Music, Health, Website,
  Other), and Priority (High, Medium, Low) when supported by the task. Do not
  invent priorities, deadlines, requirements, or completion claims.
- Update the item when work starts, materially changes, becomes blocked, or
  finishes. Describe blockers in the item body; use the available Status
  options. Mark Done only after the intended outcome and relevant checks are
  complete, and link the commit, pull request, or other verification.
- Keep detailed implementation plans in repository documentation and link
  them from the item. Preserve separate repository ownership and runtime
  boundaries. Never copy credentials, personal data, or private chat contents
  into issues or Project items; public issues and pull requests remain public
  even when tracked in a private Project.
- Use available GitHub tools, or the authenticated `gh project` CLI when the
  connector does not support Projects. If access is unavailable, continue the
  authorized repository work and report the pending tracking update. Do not
  claim synchronization succeeded, create another Project, change visibility,
  or broaden credentials without the owner's authorization.
- In the final work summary, briefly state the Project update, or explain why
  tracking was unnecessary or unavailable. These instructions guide agents
  during work; they do not create a background synchronization service.
