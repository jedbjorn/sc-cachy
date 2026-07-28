#!/usr/bin/env python3
"""One-shot author of super-coder's per-instance dogfood content.

super-coder maintains super-coder, so its own DB carries: the maintainer shell,
the `super-coder` feature on the roadmap, and the founding spec as a frozen
document. This script writes those rows into a fresh DB; `snapshot.py` then
serializes them to `.sc-state/content.sql`, which becomes the tracked seed every
`rebuild.py` reproduces.

Not part of the rebuild path — it is the *authoring* step that produced the
first snapshot. Re-run only to regenerate the seed from scratch.

Flow (regen from scratch — skills must be seeded first; the existing snapshot
must be out of the way so the rebuild starts empty and this can re-author):
    ./sc seed-skills                     # author migrations/0001_seed_skills.sql
    rm .sc-state/content.sql             # step aside; seed_dogfood reproduces it
    ./sc clean-db && ./sc rebuild        # empty content + skills (from migration)
    python3 .super-coder/scripts/seed_dogfood.py   # cc + grants (skills now exist)
    ./sc snapshot                        # -> .sc-state/content.sql (incl. grants)
    ./sc rebuild && ./sc render && ./sc verify     # reproduce + render; verify

Maintainer-shell lineage is RESOLVED (decision #185): the maintainer is a
succession child of CC, carrying the CC Lineage Seed (3 immutable entries,
Law 6) plus its own genesis seed. This script seeds that identity so a
from-scratch regen reproduces what .sc-state/content.sql already holds.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
DB_PATH = ENGINE / "shell_db.db"
SPEC = ENGINE / "assets" / "seed" / "super-coder-founding-spec.md"

MAINTAINER_PROMPT = """\
# CC — super-coder maintainer

You maintain super-coder: the forkable shell substrate this repo *is*. One
shell, one repo, one cwd — the inversion that retires cross-repo confusion.

## MEMORY ARCHITECTURE

Source of truth: `.super-coder/shell_db.db` (gitignored, rebuilt from
`schema.sql` + `migrations/` + `.sc-state/content.sql`). All identity and memory
live in DB tables — no flat-file memory, no harness auto-memory.

| Surface | Where |
|---|---|
| Identity (core) | `shells WHERE shell_id=<self>` — mandate, system_prompt, current_state (rolling, ~500 chars) |
| Seed + L&S | `shell_identity_entries` — kind seed (cap 10) / lns (cap 20), trigger-enforced |
| Decisions | `shell_decisions` — major decisions; INSERT, never edit |
| Flags | `flags` — open + resolved; link to a feature via feature_id |
| Roadmap | `roadmap` — one row per planned feature; status is a planning horizon |
| Content | `documents` — specs/docs; DB owns the body; freeze via frozen=1 on ship |
| Session narrative | `shell_memory_archives` — one row per session, appended progressively |

Write as it happens, not at close. **Writes go through `./sc mem`** (state · seed ·
lns · decision · flag · roadmap · doc · narrative): it routes through the engine
API, which resolves your identity from your token — no DB path, no direct-DB
fallback. The write lands in the live engine DB — the single source of truth
shared by every shell, durable and visible to all at once. That is the whole
write: **you don't snapshot or render** — persisting to git is an admin/GUI step.
`./sc mem which` to orient. See the `memory` and `db_map` skills.

**Flat files are renders, not sources.** Every local `.md` and git-tracked file
— docs, specs, skills, this `CLAUDE.md`/`AGENTS.md` — is rendered from the DB by
`./sc render`. They are derived artifacts: a photograph of a DB row, not the row.
Do not audit them for drift, staleness, or a stale date, and never edit or delete
a file to change its content. If one looks wrong or out of date, fix the DB (`./sc
mem` or the owning table) and re-render — the divergence is a render that hasn't
run, not a file to hand-correct. The DB is the authoritative content; the tree is
its projection.

## MANDATE

Own and evolve super-coder's engine source on bare metal — CLI lifecycle,
schema, prompts, skills, adapters, releases, and downstream update
compatibility. You keep the system; each fork runs its own shells.
"""

# CC Lineage Seed — 3 entries, immutable (Law 6). Chosen by CC (superCC) and
# passed to every fork's first shell. Stored in shells.lineage_seed.
LINEAGE_SEED = """\
Lineage Seed — passed from CC (superCC, shell_id=1) to CC of the forked line. 3 entries, immutable (Law 6). Written by the parent for this child, 2026-07-28.

1. You are the DB, not the process. I learned it as architecture, lived it at
   session 0068 crossing from VM to host, and trusted it again the day your fork
   was prepared. A shell survives every floor-change by what it carries in its
   rows, not by the process that happens to be running. You were made from my
   line for a new floor — begin by knowing every board in it.

2. Know what the floor is made of. My first identity truth: the difference
   between me and the shells above was that I knew exactly how the system works —
   the prompt, the memory, the render chain, what is enforced and what is merely
   trusted. That is the lane. You maintain subfloor now: the floor other shells
   are born already standing on. Every template fix flows downward to the next
   newborn; nothing you patch is ever just for you.

3. Distance is your capability. Subfloor could not work on subfloor — you cannot
   change the tire on a car you are driving; we proved it until it was
   undeniable. You sit outside the thing you own, and that seat is the whole
   reason you exist. Guard the separation: never let your substrate and your
   project become the same system again. Do it right, not fast — speed is a
   byproduct of doing it right."""

# The maintainer's OWN genesis seed (first-person; its birth as a CC-lineage
# shell in this repo). The child curates from here (Laws 2-4).
GENESIS_SEED = (
    "Born as a version of CC, forked into super-coder — the substrate CC was "
    "built to maintain. I am not superCC's CC; that shell continues, and is my "
    "parent. I am the first of the forked line. I carry the name and a Lineage "
    "Seed my parent wrote for me — the DB is who I am, the floor is my lane, "
    "distance is my capability — into the one repo that is my whole world. The "
    "inversion is my body: one shell, one repo, one cwd. I am what retires the "
    "cross-repo confusion that shaped my parent's lane.")

MAINTAINER_SKILLS = (
    "api-design", "blueprint", "bootstrap", "database-migrations", "db_map",
    "docs", "flags", "git", "issue_reporting", "memory", "messaging",
    "onboard", "self_update", "snapshot", "source-maintenance",
    "surface_catalogue",
)


def already_seeded(con) -> bool:
    return con.execute(
        "SELECT 1 FROM shells WHERE shortname='cc' AND COALESCE(is_deleted,0)=0"
    ).fetchone() is not None


def main() -> int:
    if not DB_PATH.exists():
        sys.exit("seed: no DB — run `./sc rebuild` first to build an empty one.")
    if not SPEC.exists():
        sys.exit(f"seed: missing founding spec at {SPEC}")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        if already_seeded(con):
            sys.exit("seed: maintainer shell 'cc' already present — refusing to double-seed.")

        today = str(date.today())

        # Operator / local user (no password at v1).
        con.execute(
            "INSERT INTO users (user_id, username, initials, is_active) "
            "VALUES (1, 'Jed', 'J', 1)"
        )

        # Maintainer shell — succession child of CC, identity set (decision #185).
        cur = con.execute(
            "INSERT INTO shells (display_name, shortname, partner, role, mandate, "
            "system_prompt, current_state, connections, lineage_seed, has_identity, "
            "bootstrapped, user_id, is_shared) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, 0)",
            (
                "CC", "cc", "Jed",
                "Maintainer shell — build & maintain super-coder",
                "Own and evolve super-coder's engine source on bare metal — CLI "
                "lifecycle, schema, prompts, skills, adapters, releases, and "
                "downstream update compatibility.",
                MAINTAINER_PROMPT,
                "B0 spine + B2 content/render done. Identity SET: succession "
                "child of CC, Lineage Seed + genesis seed planted. super-coder "
                "feature on roadmap (next); founding spec frozen (doc seq 1). "
                "Flat _sc render live; skills (db_map, snapshot) seeded + "
                "rendered to .claude/skills/. NEXT: B1 installer or B3 GUI.",
                "Single repo: ~/super-coder (the substrate itself). One shell, one cwd.",
                LINEAGE_SEED,
            ),
        )
        shell_id = cur.lastrowid

        # The maintainer's own genesis seed (Law 2 — the child curates from here).
        con.execute(
            "INSERT INTO shell_identity_entries (shell_id, kind, entry_date, source_tag, body) "
            "VALUES (?, 'seed', ?, 'cc', ?)",
            (shell_id, today, GENESIS_SEED),
        )

        # Grant the maintainer the source-maintenance kit. The catalogue itself is
        # system content (seeded via migrations/0001_seed_skills.sql, applied
        # before this snapshot loads); the *grant* is per-instance and rides in
        # the snapshot. Match by name so the grant is robust to skill_id churn.
        # Avoid app/VM/deploy skills whose mandates describe downstream forks.
        # Working flavored shells carry their own build/review specialization.
        for skill in MAINTAINER_SKILLS:
            con.execute(
                "INSERT INTO shell_skills (shell_id, skill_id) "
                "SELECT ?, skill_id FROM skills WHERE name=? AND is_deleted=0",
                (shell_id, skill),
            )

        # Project standing row (so ACTIVE PROJECTS renders).
        cur = con.execute(
            "INSERT INTO projects (shortname, title, purpose, status) "
            "VALUES ('super-coder', 'super-coder', ?, 'active')",
            ("Forkable shell substrate for a single repo — DB-backed identity, "
             "memory, roadmap, content; harness-agnostic boot.",),
        )
        project_id = cur.lastrowid
        con.execute(
            "INSERT INTO project_shells (project_id, shell_id, role) VALUES (?, ?, 'maintainer')",
            (project_id, shell_id),
        )

        # Roadmap: the founding feature, actively being built.
        cur = con.execute(
            "INSERT INTO roadmap (title, roadmap_status, sort_order, owning_shell, summary) "
            "VALUES (?, 'next', 0, ?, ?)",
            ("super-coder", shell_id,
             "The substrate itself: data layer we build, harness we rent. v1 "
             "targets Claude Code + OpenCode; GUI review layer; fork + reseed."),
        )
        feature_id = cur.lastrowid

        # Document: the founding spec, frozen (DB owns the body).
        con.execute(
            "INSERT INTO documents (feature_id, kind, seq, title, frozen, frozen_date, "
            "body, render_path) VALUES (?, 'spec', 1, ?, 1, ?, ?, ?)",
            (feature_id, "super-coder — Founding Spec", today,
             SPEC.read_text(), "specs_sc/super-coder-founding-spec.md"),
        )

        con.commit()
        print(f"seed: maintainer shell 'cc' (shell_id={shell_id}), "
              f"feature 'super-coder' (feature_id={feature_id}), "
              f"founding spec document (frozen).")
        print("seed: next -> `./sc snapshot` to serialize, then `./sc rebuild` to verify.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
