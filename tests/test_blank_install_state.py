"""Regression tests for the clean first-install boundary."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".super-coder" / "scripts"))
sys.path.insert(0, str(ROOT / ".super-coder" / "render"))

import flat
import install
import run


class BlankInstallStateTests(unittest.TestCase):
    @staticmethod
    def create_render_schema(con):
        con.executescript(
            """
            CREATE TABLE documents (
                feature_id INTEGER, kind TEXT, seq INTEGER, title TEXT,
                body TEXT, render_path TEXT, frozen INTEGER
            );
            CREATE TABLE roadmap (
                feature_id INTEGER, title TEXT, roadmap_status TEXT,
                summary TEXT, owning_shell INTEGER, sort_order INTEGER
            );
            CREATE TABLE shells (shell_id INTEGER, shortname TEXT);
            CREATE TABLE flags (
                flag_id INTEGER, feature_id INTEGER, display_name TEXT,
                description TEXT, resolved INTEGER, is_deleted INTEGER
            );
            CREATE TABLE skills (
                name TEXT, description TEXT, category TEXT, command TEXT,
                content TEXT, is_deleted INTEGER
            );
            """
        )

    def test_strip_removes_memory_and_map_state_but_not_sibling_config(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            engine = repo / ".super-coder"
            targets = [
                repo / ".sc-state" / "content.sql",
                repo / ".sc-state" / "map_content.sql",
                repo / ".sc-state" / "map.db",
                repo / ".sc-state" / "map.db-wal",
                repo / ".sc-state" / "map.db-shm",
                engine / "snapshot" / "content.sql",
                engine / "assets" / "seed" / "super-coder-founding-spec.md",
            ]
            keep = repo / ".sc-state" / "engine.ref"
            for path in [*targets, keep]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("state")

            removed = install.strip_instance_content(repo, engine)

            self.assertEqual(set(removed), set(targets))
            self.assertEqual([path.exists() for path in targets],
                             [False] * len(targets))
            self.assertEqual(keep.read_text(), "state")

    def test_blank_instance_requires_both_users_and_shells_to_be_empty(self):
        with sqlite3.connect(":memory:") as con:
            con.executescript(
                """
                CREATE TABLE users (user_id INTEGER);
                CREATE TABLE shells (shell_id INTEGER);
                """
            )
            self.assertTrue(run.is_blank_instance(con))

            con.execute("INSERT INTO users VALUES (1)")
            self.assertFalse(run.is_blank_instance(con))

            con.execute("DELETE FROM users")
            con.execute("INSERT INTO shells VALUES (1)")
            self.assertFalse(run.is_blank_instance(con))

            con.execute("INSERT INTO users VALUES (1)")
            self.assertFalse(run.is_blank_instance(con))

    def test_flat_render_prunes_rows_absent_from_clean_database(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stale = [
                root / "specs_sc" / "legacy-spec.md",
                root / "docs_sc" / "legacy-sprint.md",
                root / "skills_sc" / "retired-skill.md",
            ]
            keep = root / "docs" / "project-owned.md"
            for path in [*stale, keep]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("legacy")

            with sqlite3.connect(":memory:") as con:
                con.row_factory = sqlite3.Row
                self.create_render_schema(con)
                summary = flat.render_visibility(con, root=root)

            self.assertEqual(set(summary["removed"]), set(stale))
            self.assertEqual([path.exists() for path in stale], [False, False, False])
            self.assertEqual(keep.read_text(), "legacy")
            self.assertEqual(
                (root / "roadmap_sc.md").read_text(),
                "---\n"
                "rendered_by: super-coder\n"
                "source: db\n"
                "edit: changes here are overwritten — author via the shell or localhost GUI\n"
                "---\n\n"
                "# Roadmap\n\n"
                "> Rendered from the DB. Status is a planning horizon; a feature's "
                "open flags are its blockers.\n",
            )
            self.assertTrue((root / "skills_sc" / "README.md").is_file())

    def test_flat_render_preserves_current_rows_while_pruning_stale_siblings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            current_spec = root / "specs_sc" / "nested" / "current.md"
            current_skill = root / "skills_sc" / "active.md"
            stale = [
                root / "specs_sc" / "nested" / "legacy.md",
                root / "skills_sc" / "retired.md",
            ]
            keep = root / "docs" / "project-owned.md"
            for path in [current_spec, current_skill, *stale, keep]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("old")

            with sqlite3.connect(":memory:") as con:
                con.row_factory = sqlite3.Row
                self.create_render_schema(con)
                con.execute(
                    "INSERT INTO roadmap VALUES (1, 'Current feature', "
                    "'in_progress', 'Current summary', NULL, 0)"
                )
                con.execute(
                    "INSERT INTO documents VALUES "
                    "(1, 'spec', 1, 'Current spec', '# Current body', "
                    "'specs_sc/nested/current.md', 0)"
                )
                con.execute(
                    "INSERT INTO skills VALUES "
                    "('active', 'Active description', 'test', NULL, "
                    "'Active instructions', 0)"
                )
                summary = flat.render_visibility(con, root=root)

            self.assertEqual(set(summary["removed"]), set(stale))
            self.assertEqual([path.exists() for path in stale], [False, False])
            self.assertIn("# Current body", current_spec.read_text())
            self.assertIn("Active instructions", current_skill.read_text())
            self.assertIn("Current feature", (root / "roadmap_sc.md").read_text())
            self.assertEqual(keep.read_text(), "old")


if __name__ == "__main__":
    unittest.main()
