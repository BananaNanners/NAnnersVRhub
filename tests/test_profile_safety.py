# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Offline, disposable-only safety evidence for Dev5C3 UEVR profile-2."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import hub, profile_safety
from vrhub.profile_safety import ProfilePlan


class ProfileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nanners-profile-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.prefix = self.base / "prefix"
        self.dest = self.prefix / "drive_c/users/steamuser/AppData/Roaming/UnrealVRMod/SLASHER-Win64-Shipping"
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        self.state = self.base / "hub-state/state.json"
        self.recipe = {"id": "fatekeeper", "name": "Fatekeeper", "method": "uevr",
                       "profile": {"dir": "Roaming/UnrealVRMod/SLASHER-Win64-Shipping"}}
        self.archive = self.base / "profile.zip"
        self.zip({"wrapper/config.txt": b"new configuration",
                  "wrapper/plugins/uevr.dll": b"new dll"})
        for target, replacement in (
            ("vrhub.hub.profile_dir", self.dest),
            ("vrhub.hub._pfx", self.prefix),
            ("vrhub.hub.load_recipes", {"fatekeeper": self.recipe}),
        ):
            patch = mock.patch(target, return_value=replacement)
            patch.start()
            self.addCleanup(patch.stop)
        self.real_process_guard = profile_safety._assert_game_stopped
        proc = mock.patch("vrhub.profile_safety._assert_game_stopped")
        proc.start(); self.addCleanup(proc.stop)
        self.real_execution_gate = profile_safety._assert_execution_gate
        gate = mock.patch("vrhub.profile_safety._assert_execution_gate")
        gate.start(); self.addCleanup(gate.stop)
        env = mock.patch.dict("os.environ", {"VRHUB_STATE": str(self.state)})
        env.start(); self.addCleanup(env.stop)

    def zip(self, entries):
        with zipfile.ZipFile(self.archive, "w") as z:
            for name, data in entries.items():
                z.writestr(name, data)

    def seed_original(self):
        (self.dest / "config.txt").parent.mkdir(parents=True, exist_ok=True)
        (self.dest / "config.txt").write_bytes(b"custom settings")
        (self.dest / "untracked/custom.lua").parent.mkdir(parents=True, exist_ok=True)
        (self.dest / "untracked/custom.lua").write_bytes(b"user script")
        (self.dest / "empty-directory").mkdir()

    def plan(self):
        return hub.review_profile_install(self.recipe, self.archive)

    def apply(self, plan=None):
        plan = plan or self.plan()
        return hub.install_profile(self.recipe, self.archive,
                                   approved_fingerprint=plan.fingerprint, confirmed=True)

    def restore(self):
        return hub.uninstall("fatekeeper:profile", profile_confirm=True)

    def record(self):
        return json.loads(self.state.read_text())["fatekeeper:profile"]

    def test_plan_is_read_only_and_lists_full_existing_directory(self):
        self.seed_original()
        p = self.plan()
        self.assertIsInstance(p, ProfilePlan)
        self.assertTrue(p.ready)
        self.assertEqual((p.existing_files, p.existing_dirs, p.existing_bytes), (2, 2, 26))
        self.assertEqual(p.profile_files, 2)
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"custom settings")
        self.assertFalse(self.state.exists())

    def test_install_requires_explicit_confirmation_and_fingerprint(self):
        self.seed_original()
        with self.assertRaisesRegex(RuntimeError, "explicit reviewed confirmation"):
            hub.install_profile(self.recipe, self.archive)
        with self.assertRaisesRegex(RuntimeError, "explicit reviewed confirmation"):
            hub.install_profile(self.recipe, self.archive, confirmed=True)
        self.assertFalse(self.state.exists())
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"custom settings")

    def test_persistent_backup_retains_every_file_empty_folder_and_restore(self):
        self.seed_original()
        self.apply()
        rec = self.record()
        self.assertEqual(rec["installer"], "uevr-profile-2")
        backup = Path(rec["backup"])
        self.assertEqual((backup / "config.txt").read_bytes(), b"custom settings")
        self.assertEqual((backup / "untracked/custom.lua").read_bytes(), b"user script")
        self.assertTrue((backup / "empty-directory").is_dir())
        self.assertFalse((self.dest / "untracked/custom.lua").exists())
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"new configuration")
        self.restore()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"custom settings")
        self.assertEqual((self.dest / "untracked/custom.lua").read_bytes(), b"user script")
        self.assertTrue((self.dest / "empty-directory").is_dir())
        self.assertFalse((self.dest / "plugins/uevr.dll").exists())
        self.assertNotIn("fatekeeper:profile", json.loads(self.state.read_text()))
        self.assertTrue(backup.is_dir())  # retained even after restoration

    def test_fresh_install_without_existing_profile_removes_only_new_files(self):
        self.apply()
        rec = self.record()
        self.assertIsNone(rec["backup"])
        self.restore()
        self.assertFalse(self.dest.exists())
        self.assertNotIn("fatekeeper:profile", json.loads(self.state.read_text()))

    def test_legacy_inventory_blocks_replacement_without_touching_profile(self):
        self.seed_original()
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps({"fatekeeper:profile": {
            "root": str(self.dest), "files": [str(self.dest/"config.txt")]}}))
        p = self.plan()
        self.assertFalse(p.ready)
        self.assertIn("existing Hub profile", " ".join(p.blocked))
        with self.assertRaisesRegex(RuntimeError, "blocked"):
            self.apply(p)
        with self.assertRaisesRegex(RuntimeError, "Legacy/missing"):
            self.restore()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"custom settings")

    def test_missing_legacy_directory_blocks_even_with_record(self):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text('{"fatekeeper:profile":{"root":"missing","files":[]}}')
        self.assertFalse(self.plan().ready)
        self.assertFalse(self.dest.exists())

    def test_modified_installed_configuration_is_preserved(self):
        self.seed_original()
        self.apply()
        (self.dest / "config.txt").write_bytes(b"changed by user")
        with self.assertRaisesRegex(RuntimeError, "additions, removals, or modifications"):
            self.restore()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"changed by user")
        self.assertIn("fatekeeper:profile", json.loads(self.state.read_text()))

    def test_added_and_missing_installed_files_block_restore(self):
        for change in ("added", "missing"):
            with self.subTest(change=change):
                self.apply()
                if change == "added":
                    (self.dest / "additional.json").write_text("{}")
                else:
                    (self.dest / "plugins/uevr.dll").unlink()
                with self.assertRaisesRegex(RuntimeError, "additions, removals, or modifications"):
                    self.restore()
                if change == "added":
                    (self.dest / "additional.json").unlink()
                else:
                    (self.dest / "plugins/uevr.dll").write_bytes(b"new dll")
                self.restore()

    def test_changed_original_backup_blocks_restoration(self):
        self.seed_original()
        self.apply()
        backup = Path(self.record()["backup"])
        (backup / "config.txt").write_bytes(b"damaged original")
        with self.assertRaisesRegex(RuntimeError, "missing, unsafe, or changed"):
            self.restore()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"new configuration")

    def test_stale_review_detects_profile_changes(self):
        self.seed_original()
        plan = self.plan()
        (self.dest / "extra.bin").write_bytes(b"added after review")
        with self.assertRaisesRegex(RuntimeError, "changed after review"):
            self.apply(plan)
        self.assertFalse(self.state.exists())

    def test_stale_review_detects_archive_changes(self):
        plan = self.plan()
        self.zip({"config.txt": b"different"})
        with self.assertRaisesRegex(RuntimeError, "changed after review"):
            self.apply(plan)
        self.assertFalse(self.dest.exists())

    def test_symlink_inside_existing_profile_is_blocked(self):
        self.seed_original()
        (self.dest / "untracked/file-link").symlink_to(self.archive)
        with self.assertRaisesRegex(RuntimeError, "nonregular"):
            self.plan()

    def test_symlinked_profile_destination_is_blocked(self):
        target = self.base / "outside"
        target.mkdir()
        self.dest.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "Symbolic link"):
            self.plan()

    def test_unsafe_zip_path_rejected_without_mutation(self):
        self.seed_original()
        self.zip({"config.txt": b"new", "../escape.txt": b"bad"})
        with self.assertRaisesRegex(RuntimeError, "Unsafe ZIP path"):
            self.plan()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"custom settings")

    def test_case_insensitive_duplicate_zip_path_is_rejected(self):
        self.zip({"config.txt": b"a", "CONFIG.TXT": b"b"})
        with self.assertRaisesRegex(RuntimeError, "duplicate ZIP path"):
            self.plan()

    def test_reject_file_directory_zip_collision(self):
        self.zip({"config.txt": b"cfg", "foo": b"one", "foo/bar.txt": b"two"})
        with self.assertRaisesRegex(RuntimeError, "collision"):
            self.plan()

    def test_failed_install_state_commit_rolls_back_directory(self):
        self.seed_original()
        before = (self.dest / "config.txt").read_bytes()
        with mock.patch("vrhub.hub._save_state", side_effect=OSError("test commit failure")):
            with self.assertRaisesRegex(OSError, "test commit failure"):
                self.apply()
        self.assertEqual((self.dest / "config.txt").read_bytes(), before)
        self.assertEqual((self.dest / "untracked/custom.lua").read_bytes(), b"user script")
        self.assertFalse(self.state.exists())

    def test_failed_restoration_state_commit_rolls_back_new_profile(self):
        self.seed_original()
        self.apply()
        with mock.patch("vrhub.hub._save_state", side_effect=OSError("test restore failure")):
            with self.assertRaisesRegex(OSError, "test restore failure"):
                self.restore()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"new configuration")
        self.assertIn("fatekeeper:profile", json.loads(self.state.read_text()))

    def test_bad_backup_root_symlink_blocks_without_writes(self):
        self.seed_original()
        self.state.parent.mkdir(parents=True)
        backup = self.state.parent/"backups"
        backup.symlink_to(self.base)
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            self.apply()
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"custom settings")

    def test_live_execution_remains_closed_without_fixture_override(self):
        plan = self.plan()
        with mock.patch("vrhub.profile_safety._assert_execution_gate",
                        side_effect=self.real_execution_gate) as gate:
            with self.assertRaisesRegex(RuntimeError, "LIVE PROFILE EXECUTION IS DISABLED"):
                self.apply(plan)
            gate.assert_called_once()
        self.assertFalse(self.dest.exists())

    def test_original_changed_while_staging_does_not_get_overwritten(self):
        self.seed_original()
        plan = self.plan()
        original_stage = profile_safety._stage_zip
        def stage_then_modify(*args):
            result = original_stage(*args)
            (self.dest / "config.txt").write_bytes(b"late user changes")
            return result
        with mock.patch("vrhub.profile_safety._stage_zip", side_effect=stage_then_modify):
            with self.assertRaisesRegex(RuntimeError, "changed during staging"):
                self.apply(plan)
        self.assertEqual((self.dest / "config.txt").read_bytes(), b"late user changes")
        self.assertFalse(self.state.exists())

    def test_installed_profile_changed_during_restore_staging_is_protected(self):
        self.seed_original()
        self.apply()
        original_copy = profile_safety._verified_copy
        def copy_then_modify(*args):
            result = original_copy(*args)
            (self.dest / "config.txt").write_bytes(b"post-install customization")
            return result
        with mock.patch("vrhub.profile_safety._verified_copy",
                        side_effect=copy_then_modify):
            with self.assertRaisesRegex(RuntimeError, "changed during restore staging"):
                self.restore()
        self.assertEqual((self.dest / "config.txt").read_bytes(),
                         b"post-install customization")
        self.assertIn("fatekeeper:profile", json.loads(self.state.read_text()))

    def test_read_only_restore_review_checks_current_and_original(self):
        self.seed_original()
        self.apply()
        ready = profile_safety.review_restore("fatekeeper:profile")
        self.assertTrue(ready["ready"], ready)
        self.assertEqual(ready["original_files"], 2)
        (self.dest / "config.txt").write_bytes(b"customized again")
        blocked = profile_safety.review_restore("fatekeeper:profile")
        self.assertFalse(blocked["ready"])
        self.assertIn("modifications", blocked["reason"])
        self.assertIn("fatekeeper:profile", json.loads(self.state.read_text()))

    def test_game_running_guard_rejects_known_executable(self):
        proc = self.base / "proc"
        pid = proc / "1234"
        pid.mkdir(parents=True)
        (pid / "comm").write_text("wine-preloader\n")
        (pid / "cmdline").write_bytes(b"/games/HogwartsLegacy.exe\0")
        with self.assertRaisesRegex(RuntimeError, "running"):
            self.real_process_guard("hogwarts-legacy", proc=proc)

    def test_game_running_guard_allows_verified_empty_process_list(self):
        proc = self.base / "proc"
        proc.mkdir()
        self.real_process_guard("hogwarts-legacy", proc=proc)

    def test_game_running_guard_fails_closed_without_process_access(self):
        with self.assertRaisesRegex(RuntimeError, "Cannot verify"):
            self.real_process_guard("hogwarts-legacy", proc=self.base/"absent")

    def test_restore_requires_confirmation(self):
        self.apply()
        with self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            hub.uninstall("fatekeeper:profile")
        self.assertTrue(self.dest.exists())
