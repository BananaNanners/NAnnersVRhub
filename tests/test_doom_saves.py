# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Disposable save fixtures, failure injection and real offscreen Qt controls."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from vrhub import doom_saves as saves, hub, self_install

REAL_ENSURE_CLOSED = saves.ensure_closed


class SaveFixture:
    def setup_fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.state = self.home / ".local/share/vrhub/state.json"
        self.state.parent.mkdir(parents=True)
        self.state.write_bytes(b'{"existing-record": {"files": []}}\n')
        self.history = self.state.with_name("live-tests.json")
        self.history.write_bytes(b'{"schema_version":1,"games":{}}\n')
        self.original_data = {p: p.read_bytes() for p in (self.state, self.history)}
        self.recipe = hub.load_recipes()["doom-2016-gog"]
        self.prefix = self.home / "Games/Heroic/Prefixes/DOOM (2016)"
        self.lab = self.home / ".local/share/nanners-kharvox-lab"
        self.source_prefix = self.lab / "renderer-queue-comparison-0.1.1/baseline/prefix"
        self.target = self.make_set(self.prefix, 100, 200, b"old")
        self.source = self.make_set(self.source_prefix, 200, 400, b"new")
        for p in (mock.patch.dict(os.environ, {"HOME": str(self.home), "VRHUB_STATE": str(self.state)}),
                  mock.patch.object(saves.kharvox, "prefix", return_value=self.prefix),
                  mock.patch.object(saves, "ensure_closed")):
            p.start()
            self.addCleanup(p.stop)

    def make_set(self, prefix, date, duration, content, user="steamuser", version="100"):
        root = prefix / f"drive_c/users/{user}/Saved Games/id Software/DOOM/base/savegame"
        details = f"checksum=123\ncompleted=0\ndate={date}\ndifficulty=0\ngameVersion={version}\nmapDesc=Resource Operations\nmapName=game/sp/resource_ops/resource_ops\ntime={duration}\n"
        for name, data in {"GAME-AUTOSAVE0/game.details": details.encode(),
                           "GAME-AUTOSAVE0/checkpoint.dat": content,
                           "GAME-AUTOSAVE0/checkpoint.dat.verify": b"verification-sidecar",
                           "PROFILE/profile.bin": content + b"-profile"}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return root

    def check_data(self):
        for path, original in self.original_data.items():
            self.assertEqual(path.read_bytes(), original)


class DoomSaveTests(SaveFixture, unittest.TestCase):
    def setUp(self):
        self.setup_fixture()

    def tearDown(self):
        self.check_data()

    def plan(self):
        return saves.preview(self.source, self.target)

    def test_read_only_discovery_and_metadata(self):
        files_before = sorted(str(p) for p in self.home.rglob("*"))
        report = saves.discover(self.recipe)
        self.assertEqual(sorted(str(p) for p in self.home.rglob("*")), files_before)
        self.assertEqual(report["target"], str(self.target.resolve()))
        self.assertEqual(len(report["rows"]), 2)
        source = next(r for r in report["rows"] if not r["current"])
        self.assertEqual(source["mission"], "Resource Operations")
        self.assertEqual(source["time_value"], "400")
        self.assertEqual(source["game_version"], "100")
        saves.ensure_closed.assert_not_called()

    def test_alias_users_are_deduplicated_by_resolved_root(self):
        users = self.prefix / "drive_c/users"
        (users / "alias").symlink_to(users / "steamuser", target_is_directory=True)
        self.assertEqual(saves.current_target(self.recipe), self.target.resolve())
        self.assertEqual(len(saves.discover(self.recipe)["rows"]), 2)

    def test_ambiguous_target_is_not_chosen(self):
        self.make_set(self.prefix, 100, 200, b"other", user="another-user")
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            saves.current_target(self.recipe)
        self.assertIsNone(saves.discover(self.recipe)["target"])

    def test_missing_heroic_configuration_still_lists_experiments(self):
        with mock.patch.object(saves.kharvox, "prefix", side_effect=RuntimeError("missing Heroic prefix")):
            report = saves.discover(self.recipe)
        self.assertIsNone(report["target"])
        self.assertTrue(report["rows"])
        self.assertIn("missing Heroic prefix", report["notes"])

    def test_runner_trees_are_not_scanned(self):
        self.make_set(self.lab / "some-runner/prefix", 900, 900, b"ignore")
        self.assertEqual(len(saves.discover(self.recipe)["rows"]), 2)

    def test_explicit_extra_folder_is_discovered(self):
        extra = self.make_set(self.home / "manual-prefix", 300, 500, b"custom")
        self.assertEqual(len(saves.discover(self.recipe, [extra])["rows"]), 3)

    def test_standalone_and_hub_backups_are_discovered(self):
        import shutil
        backups = self.state.parent / "backups"
        for directory, name in (("doom-save-restore-fixture", "heroic-before-savegame"),
                                ("doom-saves-fixture", "target-before-savegame")):
            shutil.copytree(self.source, backups / directory / name)
        self.assertEqual(len(saves.discover(self.recipe)["rows"]), 4)

    def test_complete_set_is_required(self):
        (self.source / "PROFILE/profile.bin").unlink()
        with self.assertRaisesRegex(RuntimeError, "complete savegame"):
            saves.snapshot(self.source)

    def test_symlink_in_save_set_is_rejected(self):
        (self.source / "linked.dat").symlink_to(self.target / "PROFILE/profile.bin")
        with self.assertRaisesRegex(RuntimeError, "linked"):
            saves.snapshot(self.source)

    def test_file_size_limit_is_enforced(self):
        with mock.patch.object(saves, "MAX_FILE", 1):
            with self.assertRaisesRegex(RuntimeError, "size limits"):
                saves.snapshot(self.source)

    def test_invalid_date_stays_unknown(self):
        details = self.source / "GAME-AUTOSAVE0/game.details"
        details.write_bytes(details.read_bytes().replace(b"date=200", b"date=invalid"))
        self.assertIsNone(saves.snapshot(self.source)["saved_at"])

    def test_same_and_overlapping_roots_rejected(self):
        for source in (self.target, self.target.parent):
            with self.assertRaisesRegex(RuntimeError, "separate"):
                saves.preview(source, self.target)

    def test_identical_set_needs_no_restore(self):
        import shutil
        shutil.rmtree(self.source)
        shutil.copytree(self.target, self.source)
        with self.assertRaisesRegex(RuntimeError, "already matches"):
            self.plan()

    def test_different_versions_block_restore(self):
        details = self.source / "GAME-AUTOSAVE0/game.details"
        details.write_bytes(details.read_bytes().replace(b"gameVersion=100", b"gameVersion=200"))
        with self.assertRaisesRegex(RuntimeError, "different game versions"):
            self.plan()

    def test_restore_copies_whole_set_keeps_both_backups_and_leaves_settings(self):
        extra = self.target / "old-only.dat"
        extra.write_bytes(b"old-only")
        config = self.target.parent / "DOOMConfig.cfg"
        config.write_bytes(b"graphics settings")
        plan = self.plan()
        result = saves.restore(plan, self.recipe)
        backup = Path(result["backup"])
        for root in (self.source, self.target, backup / "source-savegame"):
            self.assertEqual(saves.snapshot(root)["fingerprint"], plan["source"]["fingerprint"])
        for root in (backup / "target-before-savegame", Path(result["previous"])):
            self.assertEqual(saves.snapshot(root)["fingerprint"], plan["target"]["fingerprint"])
        self.assertFalse(extra.exists())
        self.assertEqual(config.read_bytes(), b"graphics settings")
        self.assertEqual(json.loads((backup / "restore.json").read_text())["status"], "restored")
        self.assertIsNone(result["warning"])

    def test_stale_source_or_target_preview_is_rejected(self):
        for root in (self.source, self.target):
            plan = self.plan()
            checkpoint = root / "GAME-AUTOSAVE0/checkpoint.dat"
            checkpoint.write_bytes(checkpoint.read_bytes() + b"changed")
            with self.assertRaisesRegex(RuntimeError, "changed since"):
                saves.restore(plan, self.recipe)
        self.assertFalse((self.state.parent / "backups").exists())

    def test_new_heroic_target_blocks_old_preview(self):
        plan = self.plan()
        with mock.patch.object(saves, "current_target", return_value=self.home / "other"):
            with self.assertRaisesRegex(RuntimeError, "location changed"):
                saves.restore(plan, self.recipe)
        self.assertFalse((self.state.parent / "backups").exists())

    def test_running_game_blocks_before_backup(self):
        with mock.patch.object(saves, "ensure_closed", side_effect=RuntimeError("Close DOOM")):
            with self.assertRaisesRegex(RuntimeError, "Close DOOM"):
                saves.restore(self.plan(), self.recipe)
        self.assertFalse((self.state.parent / "backups").exists())

    def test_process_guard_recognizes_game_launcher_and_heroic(self):
        process = self.home / "fake-process"
        process.mkdir()
        for name in ("DOOMx64vk.exe", "KharvoxLauncher", "heroic"):
            (process / "comm").write_text(name + "\n")
            with mock.patch.object(Path, "glob", return_value=[process]):
                with self.assertRaisesRegex(RuntimeError, "Close DOOM"):
                    REAL_ENSURE_CLOSED()
        (process / "comm").write_text("unrelated\n")
        with mock.patch.object(Path, "glob", return_value=[process]):
            REAL_ENSURE_CLOSED()

    def test_heroic_location_change_during_preparation_blocks_swap(self):
        plan = self.plan()
        with mock.patch.object(saves, "current_target", side_effect=[self.target, self.home / "other"]):
            with self.assertRaisesRegex(RuntimeError, "location changed during preparation"):
                saves.restore(plan, self.recipe)
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], plan["target"]["fingerprint"])

    def test_failed_backup_does_not_modify_target(self):
        plan = self.plan()
        with mock.patch.object(saves.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "Recovery copies retained"):
                saves.restore(plan, self.recipe)
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], plan["target"]["fingerprint"])

    def test_corrupt_backup_is_detected_before_replacement(self):
        plan = self.plan()
        real_copy = saves.shutil.copytree

        def corrupt(src, dst, *args, **kwargs):
            result = real_copy(src, dst, *args, **kwargs)
            if Path(dst).name == "source-savegame":
                (Path(dst) / "PROFILE/profile.bin").write_bytes(b"corrupt")
            return result

        with mock.patch.object(saves.shutil, "copytree", side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                saves.restore(plan, self.recipe)
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], plan["target"]["fingerprint"])

    def test_failed_swap_rolls_back_target_and_retains_backups(self):
        plan = self.plan()
        replace = saves.os.replace

        def fail(src, dst):
            if Path(src).name == "replacement-savegame":
                raise OSError("injected swap failure")
            return replace(src, dst)

        with mock.patch.object(saves.os, "replace", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "original target was restored"):
                saves.restore(plan, self.recipe)
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], plan["target"]["fingerprint"])
        backups = list((self.state.parent / "backups").glob("doom-saves-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "source-savegame").is_dir())

    def test_failed_rollback_retains_recovery_locations(self):
        plan = self.plan()
        replace = saves.os.replace

        def fail(src, dst):
            if Path(src).name in {"replacement-savegame", "previous-savegame"}:
                raise OSError("injected rename failure")
            return replace(src, dst)

        with mock.patch.object(saves.os, "replace", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "rollback failed; originals remain"):
                saves.restore(plan, self.recipe)
        backup = next((self.state.parent / "backups").glob("doom-saves-*"))
        self.assertEqual(saves.snapshot(backup / "target-before-savegame")["fingerprint"], plan["target"]["fingerprint"])

    def test_final_record_failure_reports_verified_restore(self):
        plan = self.plan()
        atomic = saves.self_install._atomic
        calls = []

        def fail_final(*args, **kwargs):
            calls.append(1)
            if len(calls) == 3:
                raise OSError("final record full")
            return atomic(*args, **kwargs)

        with mock.patch.object(saves.self_install, "_atomic", side_effect=fail_final):
            result = saves.restore(plan, self.recipe)
        self.assertIsNotNone(result["warning"])
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], plan["source"]["fingerprint"])

    def test_target_change_during_preparation_is_not_overwritten(self):
        plan = self.plan()
        calls = []

        def changed():
            calls.append(1)
            if len(calls) == 2:
                (self.target / "PROFILE/profile.bin").write_bytes(b"concurrent progress")

        with mock.patch.object(saves, "ensure_closed", side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                saves.restore(plan, self.recipe)
        self.assertEqual((self.target / "PROFILE/profile.bin").read_bytes(), b"concurrent progress")

    def test_another_recovery_lock_blocks_restore(self):
        import fcntl
        path = self.state.parent / "doom-save-restore.lock"
        with path.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "Another save recovery"):
                saves.restore(self.plan(), self.recipe)
        self.assertFalse((self.state.parent / "backups").exists())

    def test_previous_backup_can_explicitly_restore_prior_progress(self):
        old = self.plan()["target"]["fingerprint"]
        first = saves.restore(self.plan(), self.recipe)
        undo = saves.preview(Path(first["backup"]) / "target-before-savegame", self.target)
        saves.restore(undo, self.recipe)
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], old)

    def test_packaged_recovery_modules_are_required(self):
        import shutil
        root = Path(__file__).resolve().parents[1]
        candidate = self.home / "source-package"
        shutil.copytree(root / "vrhub", candidate / "vrhub", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(root / "pyproject.toml", candidate / "pyproject.toml")
        _, files = self_install._source_files(candidate)
        self.assertIn("vrhub/doom_saves.py", files)
        self.assertIn("vrhub/doom_save_gui.py", files)
        (candidate / "vrhub/doom_save_gui.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "doom_save_gui.py"):
            self_install._source_files(candidate)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Optional PySide6 is not installed")
class DoomSaveQtTests(SaveFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.setup_fixture()
        from vrhub.doom_save_gui import DoomSavesDialog
        self.dialog = DoomSavesDialog(self.recipe, auto_scan=False)
        self.dialog.show()
        self.addCleanup(self.dispose_dialog)

    def dispose_dialog(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.dialog.close()
        self.dialog.deleteLater()
        # Destroy test widgets deterministically after their workers have finished,
        # rather than allowing Python cycle collection during a later test scan.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def tearDown(self):
        self.wait()
        self.check_data()

    def wait(self):
        deadline = time.monotonic() + 10
        while self.dialog.worker is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.app.processEvents()
        self.assertIsNone(self.dialog.worker)

    def select_source(self):
        row = next(i for i, r in enumerate(self.dialog.report["rows"]) if not r["current"])
        self.dialog.table.selectRow(row)
        self.app.processEvents()

    def test_scan_does_not_select_or_restore(self):
        with mock.patch.object(saves, "restore", side_effect=AssertionError("scan must not restore")):
            self.dialog.scan_button.click()
            self.wait()
        self.assertEqual(self.dialog.table.rowCount(), 2)
        self.assertIsNone(self.dialog.plan)
        self.assertFalse(self.dialog.restore_button.isEnabled())
        self.select_source()
        self.assertTrue(self.dialog.restore_button.isEnabled())
        self.assertIn("Resource Operations", self.dialog.details.toPlainText())
        self.assertIn(str(self.target), self.dialog.details.toPlainText())

    def test_cancel_confirmation_never_modifies_saves(self):
        self.dialog.scan(); self.wait(); self.select_source()
        with mock.patch.object(self.dialog, "confirm_restore", return_value=False), \
                mock.patch.object(saves, "restore", side_effect=AssertionError("cancel must not restore")):
            self.dialog.restore_button.click()
        self.assertFalse((self.state.parent / "backups").exists())

    def test_real_restore_worker_and_rescan_preserve_history(self):
        self.dialog.scan(); self.wait(); self.select_source()
        with mock.patch.object(self.dialog, "confirm_restore", return_value=True):
            self.dialog.restore_button.click()
            self.assertFalse(self.dialog.restore_button.isEnabled())
            self.wait()
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], saves.snapshot(self.source)["fingerprint"])
        self.assertIn("verification passed", self.dialog.result.text())
        self.assertTrue(self.dialog.backup_button.isEnabled())
        self.assertFalse(self.dialog.restore_button.isEnabled())

    def test_failed_restore_is_visible_and_scan_recovers(self):
        self.dialog.scan(); self.wait(); self.select_source()
        before = saves.snapshot(self.target)["fingerprint"]
        with mock.patch.object(self.dialog, "confirm_restore", return_value=True), \
                mock.patch.object(saves, "restore", side_effect=RuntimeError("injected failure")):
            self.dialog.restore_button.click(); self.wait()
        self.assertIn("injected failure", self.dialog.result.text())
        self.assertEqual(saves.snapshot(self.target)["fingerprint"], before)

    def test_dialog_cannot_close_while_worker_is_running(self):
        import threading
        gate = threading.Event()
        report = saves.discover(self.recipe)

        def waiting_scan(*args):
            gate.wait(5)
            return report

        with mock.patch.object(saves, "discover", side_effect=waiting_scan):
            try:
                self.dialog.scan()
                self.dialog.close()
                self.app.processEvents()
                self.assertTrue(self.dialog.isVisible())
            finally:
                gate.set()
                self.wait()

    def test_changing_selection_to_current_save_disables_restore(self):
        self.dialog.scan(); self.wait(); self.select_source()
        self.assertTrue(self.dialog.restore_button.isEnabled())
        current = next(i for i, row in enumerate(self.dialog.report["rows"]) if row["current"])
        self.dialog.table.selectRow(current)
        self.app.processEvents()
        self.assertIsNone(self.dialog.plan)
        self.assertFalse(self.dialog.restore_button.isEnabled())

    def test_identical_source_is_shown_without_restore_option(self):
        saves.restore(saves.preview(self.source, self.target), self.recipe)
        self.dialog.scan(); self.wait(); self.select_source()
        self.assertIn("already matches", self.dialog.details.toPlainText())
        self.assertFalse(self.dialog.restore_button.isEnabled())
