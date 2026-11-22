# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5B: per-game saved scans, stale file safety, folder invalidation."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import archive_scans as scans, download_planner as planner


class SavedScansTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.main = self.root / "archives"
        self.other = self.root / "other"
        self.main.mkdir()
        self.other.mkdir()
        self.snapshot = self.root / "scans.json"
        self.prefs = self.root / "prefs.json"
        for patcher in (
            mock.patch.object(scans, "snapshot_file", return_value=self.snapshot),
            mock.patch.object(planner, "preferences_file", return_value=self.prefs),
            mock.patch.object(planner, "default_library", return_value=self.main)):
            patcher.start()
            self.addCleanup(patcher.stop)
        planner._HASH_MEMO.clear()

    def recipe(self, name, payload):
        return {"id": name, "name": name, "method": "bepinex",
                "packages": [{"id": "loader", "name": "Pinned package",
                              "sha256": hashlib.sha256(payload).hexdigest(),
                              "page": "https://example.org/pinned"}]}

    def make_scan(self, name, folder=None, payload=b"real archive bytes"):
        directory = folder or self.main
        path = directory / "BepInEx-loader.zip"
        path.write_bytes(payload)
        rec = self.recipe(name, payload)
        plan = planner.build_plan(rec, directory)
        self.assertEqual(plan["verified"], 1)
        return plan, path

    def test_scan_results_remain_separate_for_multiple_games_and_restart(self):
        p1, _ = self.make_scan("game-one")
        original = scans.persist(p1)
        p2, _ = self.make_scan("game-two", folder=self.other, payload=b"different")
        planner.set_location("game", str(self.other), "game-two")
        scans.persist(p2)
        loaded = scans.load_saved()
        self.assertEqual(set(loaded), {"game-one", "game-two"})
        self.assertEqual(loaded["game-one"]["folder"], str(self.main))
        self.assertEqual(loaded["game-two"]["folder"], str(self.other))
        self.assertEqual(loaded["game-one"]["scanned_at"], original["scanned_at"])
        self.assertEqual(scans.displayed_record(loaded["game-one"])["plan"]["verified"], 1)
        self.assertEqual(scans.displayed_record(loaded["game-two"])["plan"]["verified"], 1)
        self.assertEqual(self.snapshot.stat().st_mode & 0o777, 0o600)

    def test_current_file_keeps_saved_verified_status_but_is_a_snapshot(self):
        plan, path = self.make_scan("game-one")
        record = scans.persist(plan)
        rendered = scans.displayed_record(record)
        self.assertEqual(rendered["plan"]["rows"][0]["status"],
                         "Pinned SHA-256 verified")
        self.assertEqual(rendered["plan"]["verified"], 1)
        self.assertIn("T", record["scanned_at"])
        self.assertEqual(path.read_bytes(), b"real archive bytes")

    def test_modified_file_blocks_old_pinned_verification(self):
        plan, path = self.make_scan("game-one")
        record = scans.persist(plan)
        path.write_bytes(b"DIFFERENT DATA that never matched pinned hash")
        rendered = scans.displayed_record(record)
        row = rendered["plan"]["rows"][0]
        self.assertEqual(row["status"], "Archive changed — rescan required")
        self.assertEqual(row["file"], "")
        self.assertEqual(rendered["plan"]["verified"], 0)
        self.assertEqual(rendered["plan"]["changed"], 1)
        # The stored historical snapshot is not destructively modified.
        self.assertEqual(scans.load_saved()["game-one"]["plan"]["verified"], 1)

    def test_deleted_file_blocks_stale_status(self):
        plan, path = self.make_scan("game-one")
        scans.persist(plan)
        path.unlink()
        rendered = scans.displayed_record(scans.load_saved()["game-one"])
        self.assertEqual(rendered["plan"]["rows"][0]["status"],
                         "Archive changed — rescan required")
        self.assertEqual(rendered["plan"]["verified"], 0)

    def test_symlink_replacement_does_not_follow_source(self):
        plan, path = self.make_scan("game-one")
        scans.persist(plan)
        source = self.root / "foreign-sensitive.txt"
        source.write_text("untouched external file")
        path.unlink()
        path.symlink_to(source)
        displayed = scans.displayed_record(scans.load_saved()["game-one"])
        self.assertEqual(displayed["plan"]["changed"], 1)
        self.assertEqual(source.read_text(), "untouched external file")
        self.assertTrue(path.is_symlink())

    def test_global_change_invalidates_only_affected_games(self):
        first, _ = self.make_scan("game-one")
        scans.persist(first)
        planner.set_location("game", str(self.other), "game-two")
        second, _ = self.make_scan("game-two", folder=self.other, payload=b"different")
        scans.persist(second)
        planner.set_location("global", str(self.other))
        removed = scans.remove_changed_folders()
        self.assertEqual(removed, ["game-one"])
        self.assertEqual(set(scans.load_saved()), {"game-one", "game-two"})
        self.assertEqual(scans.remove_changed_folders(), ["game-one"])

    def test_changing_one_game_folder_does_not_purge_other_game(self):
        first, _ = self.make_scan("game-one")
        scans.persist(first)
        second, _ = self.make_scan("game-two", payload=b"different")
        scans.persist(second)
        planner.set_location("game", str(self.other), "game-one")
        self.assertEqual(scans.remove_changed_folders(), ["game-one"])
        self.assertEqual(set(scans.load_saved()), {"game-one", "game-two"})

    def test_malformed_snapshot_is_never_replaced(self):
        plan, _ = self.make_scan("game-one")
        self.snapshot.write_bytes(b'{"not-a-valid-snapshot":true}')
        before = self.snapshot.read_bytes()
        with self.assertRaises(ValueError):
            scans.load_saved()
        with self.assertRaises(ValueError):
            scans.persist(plan)
        self.assertEqual(self.snapshot.read_bytes(), before)

    def test_symlink_snapshot_is_preserved_and_refused(self):
        plan, _ = self.make_scan("game-one")
        foreign = self.root / "important.json"
        foreign.write_text('{"data":"keep"}')
        self.snapshot.symlink_to(foreign)
        with self.assertRaises(ValueError):
            scans.persist(plan)
        self.assertEqual(foreign.read_text(), '{"data":"keep"}')

    def test_saved_archive_path_must_belong_to_selected_library(self):
        plan, _ = self.make_scan("game-one")
        plan["rows"][0]["file"] = "/tmp/other-game.zip"
        with self.assertRaisesRegex(ValueError, "outside"):
            scans.persist(plan)
        self.assertFalse(self.snapshot.exists())

    def test_save_without_moving_or_modifying_archives(self):
        plan, path = self.make_scan("game-one")
        prior = path.read_bytes()
        scans.persist(plan)
        self.assertEqual(path.read_bytes(), prior)
        self.assertEqual(sorted(p.name for p in self.main.iterdir()),
                         ["BepInEx-loader.zip"])


if __name__ == "__main__":
    unittest.main()
