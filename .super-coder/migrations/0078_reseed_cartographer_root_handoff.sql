-- 0078 — cartographer canonical-root persistence handoff.
--
-- Map config and semantic extractors are deliberately read from the shared
-- main checkout, not a shell worktree. Correct the cartographer skill so it
-- authors those paths through $SC_ROOT and hands their commit to admin.
-- Surgical REPLACEs preserve the skill row id and every existing grant.

BEGIN;

UPDATE skills
SET content = REPLACE(
  content,
  '2. **Author `.sc-state/map.config.json`** — authored content (tracked,
   per-fork, survives `sc update`; lives in `.sc-state/`, outside the
   gitignored engine dir). All keys optional; each merges over `map_repo.py`
   defaults:',
  '2. **Author `$SC_ROOT/.sc-state/map.config.json`** — canonical-root content
   (tracked, per-fork, survives `sc update`; lives in `.sc-state/`, outside the
   gitignored engine dir). The mapper deliberately reads the shared main
   checkout, not your shell worktree, so use `$SC_ROOT` explicitly and do not
   copy this file into the worktree. All keys optional; each merges over
   `map_repo.py` defaults:'
)
WHERE name = 'cartographer';

UPDATE skills
SET content = REPLACE(
  content,
  '6. **Commit** the config + hooks (`git` skill) -> `sc mem state "…"` ->
   `sc mem oriented` (sets `bootstrapped=1` — the write is live in the
   shared DB; it does NOT snapshot).',
  '6. **Hand off persistence.** Hook wiring is per-clone runtime state, not a
   commit. The config lives in the canonical main checkout, which only admin
   may commit: use the `messaging` skill to send admin the exact authored path
   (`.sc-state/map.config.json`) and your verification result. Do not branch or
   commit the main checkout from the cartographer shell. Then `sc mem state
   "…"` -> `sc mem oriented` (sets `bootstrapped=1` — the write is live in the
   shared DB; it does NOT snapshot).'
)
WHERE name = 'cartographer';

UPDATE skills
SET content = REPLACE(
  content,
  '7. Commit.',
  '7. Hand the exact changed canonical-root paths and verification result to admin
   for commit, as in first-boot step 6.'
)
WHERE name = 'cartographer';

UPDATE skills
SET content = REPLACE(
  content,
  '2. **Copy the matching reference** from the engine''s
   `.super-coder/templates/map_extractors/` into `.sc-state/map_extractors/`:',
  '2. **Copy the matching reference** from the engine''s
   `.super-coder/templates/map_extractors/` into
   `$SC_ROOT/.sc-state/map_extractors/`:'
)
WHERE name = 'cartographer';

UPDATE skills
SET content = REPLACE(
  content,
  '4. **Commit** `.sc-state/map_extractors/`. (Snapshotting the authored layer =
   the admin/GUI step above — not yours to run.)',
  '4. **Hand off persistence** to admin via the `messaging` skill, naming each
   changed `.sc-state/map_extractors/` path and the verification result. These
   canonical-root files are normal tracked files; snapshotting the authored DB
   layer remains the separate admin/GUI step above.'
)
WHERE name = 'cartographer';

COMMIT;
