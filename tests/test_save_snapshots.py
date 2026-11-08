# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Disposable snapshot, history, failure and Qt workflow checks."""
import json
import os
from pathlib import Path
import shutil
import time
import unittest
from unittest import mock
from vrhub import game_saves as saves, __version__
from tests.test_game_saves import SaveFixtures, FIXTURES, write, HAS_QT


class SnapshotTests(SaveFixtures, unittest.TestCase):
    def backup(self, backend, target, note="Before testing"):
        with mock.patch.object(backend, "ensure_closed"):
            return backend.backup_current(backend.snapshot(target), note)

    def test_all_nine_backups_preserve_active_files_and_record_labels(self):
        for rid in FIXTURES:
            with self.subTest(rid=rid):
                backend, source, target = self.pair(rid)
                before = backend.snapshot(target)["fingerprint"]
                result = self.backup(backend, target)
                self.assertEqual(backend.snapshot(target)["fingerprint"], before)
                folder = Path(result["backup"])
                self.assertEqual(backend.snapshot(folder / "savegame")["fingerprint"], before)
                record = json.loads((folder / "snapshot.json").read_text())
                self.assertEqual(record["game_id"], rid)
                self.assertEqual(record["hub_version"], __version__)
                self.assertEqual(record["note"], "Before testing")
                self.assertEqual(record["status"], "complete")
                self.assertTrue(record["created_at"].endswith("+00:00"))
                self.assertFalse(any(target.parent.glob(".nanners-save-restore-*")))

    def test_unique_snapshots_and_optional_empty_note(self):
        backend, source, target = self.pair("fatekeeper")
        a = self.backup(backend, target, "")
        b = self.backup(backend, target, "second")
        self.assertNotEqual(a["backup"], b["backup"])
        history = backend.backup_history()
        self.assertEqual(len(history), 2)
        self.assertEqual({r["note"] for r in history}, {"", "second"})

    def test_disabled_stale_running_and_invalid_notes_block_before_copy(self):
        backend, source, target = self.pair("fatekeeper")
        expected = backend.snapshot(target)
        backend.development_enabled = False
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            backend.backup_current(expected)
        backend.development_enabled = True
        for note in ("x" * 301, "line\nbreak", None):
            with self.assertRaisesRegex(RuntimeError, "note"):
                backend.backup_current(expected, note)
        with mock.patch.object(backend, "ensure_closed", side_effect=RuntimeError("game running")):
            with self.assertRaisesRegex(RuntimeError, "game running"):
                backend.backup_current(expected)
        (target / "Slot0.sav").write_bytes(b"new")
        with mock.patch.object(backend, "ensure_closed"), self.assertRaisesRegex(RuntimeError, "changed"):
            backend.backup_current(expected)
        self.assertFalse((self.home / "hub").exists())

    def test_copy_corruption_is_incomplete_and_active_saves_unchanged(self):
        backend, source, target = self.pair("fatekeeper")
        before = backend.snapshot(target)["fingerprint"]
        copy = shutil.copytree
        def corrupt(src, dst, **kwargs):
            result = copy(src, dst, **kwargs)
            (Path(dst) / "Slot0.sav").write_bytes(b"corrupt")
            return result
        with mock.patch.object(backend, "ensure_closed"), mock.patch.object(saves.shutil, "copytree", side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                backend.backup_current(backend.snapshot(target))
        self.assertEqual(backend.snapshot(target)["fingerprint"], before)
        self.assertEqual(backend.backup_history()[0]["status"], "incomplete")

    def test_source_changes_during_copy_not_marked_complete(self):
        backend, source, target = self.pair("fatekeeper")
        expected = backend.snapshot(target)
        copy = shutil.copytree
        def change(src, dst, **kwargs):
            result = copy(src, dst, **kwargs)
            (target / "Slot0.sav").write_bytes(b"external game change")
            return result
        with mock.patch.object(backend, "ensure_closed"), mock.patch.object(saves.shutil, "copytree", side_effect=change):
            with self.assertRaisesRegex(RuntimeError, "changed during backup"):
                backend.backup_current(expected)
        self.assertEqual((target / "Slot0.sav").read_bytes(), b"external game change")
        self.assertEqual(backend.backup_history()[0]["status"], "incomplete")

    def test_final_record_failure_is_not_success(self):
        backend, source, target = self.pair("fatekeeper")
        atomic = saves.self_install._atomic
        def fail_final(path, data):
            if b'"status": "complete"' in data:
                raise OSError("disk full")
            return atomic(path, data)
        with mock.patch.object(backend, "ensure_closed"), mock.patch.object(saves.self_install, "_atomic", side_effect=fail_final):
            with self.assertRaisesRegex(RuntimeError, "disk full"):
                backend.backup_current(backend.snapshot(target))
        self.assertEqual(backend.backup_history()[0]["status"], "incomplete")

    def test_corrupt_and_wrong_game_records_are_visible_but_blocked(self):
        backend, source, target = self.pair("fatekeeper")
        result = self.backup(backend, target)
        record = Path(result["backup"]) / "snapshot.json"
        record.write_text("not json")
        self.assertEqual(backend.backup_history()[0]["status"], "review required")
        record.write_text(json.dumps({"schema": 1, "kind": "save-snapshot", "game_id": "ready-or-not", "status": "complete"}))
        self.assertEqual(backend.backup_history()[0]["status"], "review required")

    def test_tampered_backup_blocked_as_source_in_scan_and_restore(self):
        backend, source, target = self.pair("fatekeeper")
        result = self.backup(backend, target)
        payload = Path(result["backup"]) / "savegame"
        (payload / "Slot0.sav").write_bytes(b"tampered")
        with mock.patch.object(backend, "targets", return_value=[target]):
            row = next(r for r in backend.discover(backend.recipe)["rows"] if r["root"] == str(payload))
        self.assertFalse(row["usable"])
        self.assertIn("Snapshot", row["error"])
        with self.assertRaisesRegex(RuntimeError, "Snapshot"):
            backend.preview(payload, target)

    def test_snapshot_can_restore_after_game_changes_with_existing_safeguards(self):
        backend, source, target = self.pair("fatekeeper")
        original = backend.snapshot(target)["fingerprint"]
        result = self.backup(backend, target)
        payload = Path(result["backup"]) / "savegame"
        (target / "Slot0.sav").write_bytes(b"later game progress")
        with mock.patch.object(backend, "ensure_closed"):
            restored = backend.restore(backend.preview(payload, target))
        self.assertEqual(backend.snapshot(target)["fingerprint"], original)
        self.assertEqual((Path(restored["previous"]) / "Slot0.sav").read_bytes(), b"later game progress")

    def test_history_is_read_only_and_game_scoped(self):
        backend, source, target = self.pair("fatekeeper")
        self.assertEqual(backend.backup_history(), [])
        self.assertFalse((self.home / "hub").exists())
        self.backup(backend, target)
        other = self.backend("ready-or-not")
        self.assertEqual(other.backup_history(), [])

    def test_snapshot_is_not_an_active_target(self):
        backend, source, target = self.pair("fatekeeper")
        result = self.backup(backend, target)
        backend.target = str(Path(result["backup"]) / "savegame")
        with self.assertRaisesRegex(RuntimeError, "cannot be the active"):
            backend.current_target(backend.recipe)

    def test_history_does_not_follow_record_links(self):
        backend, source, target = self.pair("fatekeeper")
        result = self.backup(backend, target)
        folder = Path(result["backup"])
        record = folder / "snapshot.json"
        record.rename(folder / "original.json")
        record.symlink_to(folder / "original.json")
        self.assertEqual(backend.backup_history()[0]["status"], "review required")

    def test_incomplete_copy_cannot_be_manually_added_as_source(self):
        backend, source, target = self.pair("fatekeeper")
        result = self.backup(backend, target)
        folder = Path(result["backup"]); record = folder / "snapshot.json"
        data = json.loads(record.read_text());data["status"] = "incomplete";record.write_text(json.dumps(data))
        payload = folder / "savegame"
        with mock.patch.object(backend, "targets", return_value=[target]):
            row = next(r for r in backend.discover(backend.recipe, [payload])["rows"] if r["root"] == str(payload))
        self.assertFalse(row["usable"])


@unittest.skipUnless(HAS_QT, "Qt unavailable")
class SnapshotQtTests(SaveFixtures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, dialog):
        deadline = time.monotonic() + 10
        while dialog.worker is not None and time.monotonic() < deadline:
            self.app.processEvents(); time.sleep(.005)
        self.assertIsNone(dialog.worker)

    def test_backup_worker_history_and_no_active_save_replacement(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend, source, target = self.pair("fatekeeper")
        d = GameSavesDialog(backend.recipe, auto_scan=False, development_enabled=True);d.backend = backend
        before = backend.snapshot(target)["fingerprint"]
        with mock.patch.object(backend, "targets", return_value=[target]), mock.patch.object(backend, "ensure_closed"):
            d.scanned(backend.discover(backend.recipe))
            self.assertTrue(d.backup_current_button.isEnabled())
            with mock.patch.object(d, "backup_note", return_value="Before dev test"):
                d.backup_current_button.click();self.wait(d)
            self.assertIn("Active saves were not replaced", d.result.text())
            self.assertEqual(backend.snapshot(target)["fingerprint"], before)
            d.history_button.click();self.wait(d)
            history = d.history_dialog
            self.assertEqual(history.table.rowCount(), 1)
            self.assertEqual(history.table.item(0, 4).text(), "Before dev test")
            self.assertFalse(history.use_button.isEnabled())
            history.table.selectRow(0);self.assertTrue(history.use_button.isEnabled())
            history.use_button.click();self.wait(d)
            self.assertTrue(d.extra_roots)
            self.assertIsNone(d.plan)
            self.assertFalse(d.restore_button.isEnabled())
        d.close();d.deleteLater();self.app.processEvents()

    def test_cancel_backup_creates_nothing(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend, source, target = self.pair("fatekeeper")
        d = GameSavesDialog(backend.recipe, auto_scan=False, development_enabled=True);d.backend = backend
        with mock.patch.object(backend, "targets", return_value=[target]):d.scanned(backend.discover(backend.recipe))
        with mock.patch.object(d, "backup_note", return_value=None):d.backup_current_button.click()
        self.assertFalse((self.home / "hub").exists())
        d.close();d.deleteLater();self.app.processEvents()

    def test_invalid_target_and_incomplete_history_buttons_disabled(self):
        from vrhub.game_save_gui import GameSavesDialog, BackupHistoryDialog
        d = GameSavesDialog(self.recipes["fatekeeper"], auto_scan=False, development_enabled=True)
        self.assertFalse(d.backup_current_button.isEnabled())
        history = BackupHistoryDialog(d.recipe, [{"folder": "/missing", "status": "incomplete", "note": "partial", "created_at": "", "hub_version": "test", "file_count": 1, "game_name": "Fatekeeper"}], d)
        history.table.selectRow(0);self.assertFalse(history.use_button.isEnabled())
        history.close();d.close();d.deleteLater();self.app.processEvents()
