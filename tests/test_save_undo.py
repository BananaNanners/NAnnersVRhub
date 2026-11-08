# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Verified pre-restore recovery, stale review and undo UI fixtures."""
import json
import os
from pathlib import Path
import shutil
import time
import unittest
from unittest import mock
from tests.test_game_saves import SaveFixtures, FIXTURES, HAS_QT, write
from vrhub import game_saves as saves


class UndoFixtures(SaveFixtures):
    def restored_pair(self, rid="fatekeeper"):
        backend, source, target = self.pair(rid)
        original = backend.snapshot(target)["fingerprint"]
        with mock.patch.object(backend, "ensure_closed"):
            result = backend.restore(backend.preview(source, target))
        return backend, source, target, original, result


class UndoTests(UndoFixtures, unittest.TestCase):
    def test_all_nine_roundtrips_keep_pre_undo_saves_and_prevent_repeat(self):
        for rid in FIXTURES:
            with self.subTest(rid=rid):
                backend, source, target, original, result = self.restored_pair(rid)
                pre_undo = backend.snapshot(target)["fingerprint"]
                plan = backend.undo_preview()
                self.assertFalse(plan["current_changed_since_restore"])
                with mock.patch.object(backend, "ensure_closed"):
                    undone = backend.undo(plan)
                self.assertEqual(backend.snapshot(target)["fingerprint"], original)
                self.assertEqual(backend.snapshot(undone["previous"])["fingerprint"], pre_undo)
                self.assertTrue(Path(result["backup"]).exists())
                record = json.loads((Path(undone["backup"]) / "restore.json").read_text())
                self.assertEqual(record["operation"], "undo")
                with self.assertRaisesRegex(RuntimeError, "already been undone"):
                    backend.undo_preview()

    def test_progress_after_restore_is_flagged_and_backed_up(self):
        backend, source, target, original, result = self.restored_pair()
        (target / "Slot0.sav").write_bytes(b"newer gameplay")
        plan = backend.undo_preview()
        self.assertTrue(plan["current_changed_since_restore"])
        with mock.patch.object(backend, "ensure_closed"):
            undone = backend.undo(plan)
        self.assertEqual(backend.snapshot(target)["fingerprint"], original)
        self.assertEqual((Path(undone["previous"]) / "Slot0.sav").read_bytes(), b"newer gameplay")

    def test_source_corruption_missing_or_linked_blocks(self):
        backend, source, target, original, result = self.restored_pair()
        backup = Path(result["backup"]) / "target-before-savegame"
        (backup / "Slot0.sav").write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "Backup verification needed"):
            backend.undo_preview()
        shutil.rmtree(backup)
        with self.assertRaises(OSError):backend.undo_preview()
        backup.symlink_to(source, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "linked"):
            backend.undo_preview()

    def test_latest_incomplete_or_corrupt_record_never_falls_back(self):
        backend, source, target, original, result = self.restored_pair()
        path = Path(result["backup"]) / "restore.json"
        data=json.loads(path.read_text());data["status"]="ready";path.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError, "incomplete or unconfirmed"):
            backend.undo_preview()
        path.write_text("broken json")
        with self.assertRaisesRegex(RuntimeError, "Cannot safely inspect"):
            backend.undo_preview()

    def test_changed_current_files_or_history_after_preview_blocks(self):
        backend, source, target, original, result = self.restored_pair()
        plan=backend.undo_preview()
        (target / "Slot0.sav").write_bytes(b"changed after preview")
        with self.assertRaisesRegex(RuntimeError, "after undo preview"):
            backend.undo(plan)
        plan=backend.undo_preview()
        path=Path(result["backup"])/"restore.json";path.write_text(path.read_text()+"\n")
        with self.assertRaisesRegex(RuntimeError, "history changed"):
            backend.undo(plan)

    def test_disabled_or_running_blocks_without_new_transaction(self):
        backend, source, target, original, result=self.restored_pair()
        plan=backend.undo_preview();before=backend.snapshot(target)["fingerprint"]
        backend.development_enabled=False
        with self.assertRaisesRegex(RuntimeError,"disabled"):backend.undo(plan)
        backend.development_enabled=True
        with mock.patch.object(backend,"ensure_closed",side_effect=RuntimeError("game running")):
            with self.assertRaisesRegex(RuntimeError,"game running"):backend.undo(plan)
        self.assertEqual(backend.snapshot(target)["fingerprint"],before)
        self.assertEqual(len(list((self.home/'hub/backups').glob(backend.backup_prefix+'*'))),1)

    def test_latest_restore_for_each_target_and_no_guessing_oldest(self):
        backend, source, target, original, result=self.restored_pair()
        write(source,{"Slot0.sav":b"second restore"})
        with mock.patch.object(backend,"ensure_closed"):
            second=backend.restore(backend.preview(source,target))
        self.assertEqual(backend.undo_preview()["undo_record"],str(Path(second["backup"])/"restore.json"))
        with mock.patch.object(backend,"ensure_closed"):
            backend.undo(backend.undo_preview())
        self.assertEqual((target/'Slot0.sav').read_bytes(),b'save')
        with self.assertRaisesRegex(RuntimeError,"already been undone"):backend.undo_preview()

    def test_legacy_record_and_target_change(self):
        backend, source, target, original, result=self.restored_pair()
        path=Path(result['backup'])/'restore.json';data=json.loads(path.read_text())
        for key in ('operation','game_id','hub_version'):data.pop(key,None)
        path.write_text(json.dumps(data))
        plan=backend.undo_preview()
        other=write(self.home/'other-target',FIXTURES['fatekeeper']);backend.target=str(other)
        with self.assertRaisesRegex(RuntimeError,"No recorded restore"):backend.undo(plan)
        backend.target=str(target)
        with mock.patch.object(backend,'ensure_closed'):backend.undo(backend.undo_preview())
        self.assertEqual(backend.snapshot(target)['fingerprint'],original)

    def test_history_changed_during_preparation_blocks_before_target_switch(self):
        backend, source, target, original, result=self.restored_pair()
        plan=backend.undo_preview();before=backend.snapshot(target)['fingerprint']
        path=Path(result['backup'])/'restore.json';copy=shutil.copytree;changed=False
        def alter(src,dst,**kwargs):
            nonlocal changed
            out=copy(src,dst,**kwargs)
            if not changed:
                path.write_text(path.read_text()+'\n');changed=True
            return out
        with mock.patch.object(backend,'ensure_closed'),mock.patch.object(saves.shutil,'copytree',side_effect=alter):
            with self.assertRaisesRegex(RuntimeError,'history changed'):backend.undo(plan)
        self.assertEqual(backend.snapshot(target)['fingerprint'],before)

    def test_rename_failure_rolls_back_undo(self):
        backend, source, target, original, result=self.restored_pair()
        plan=backend.undo_preview();before=backend.snapshot(target)['fingerprint'];replace=os.replace
        def fail(src,dst):
            if Path(src).name=='replacement-savegame':raise OSError('injected swap failure')
            return replace(src,dst)
        with mock.patch.object(backend,'ensure_closed'),mock.patch.object(os,'replace',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'original target was restored'):backend.undo(plan)
        self.assertEqual(backend.snapshot(target)['fingerprint'],before)


@unittest.skipUnless(HAS_QT,"Qt unavailable")
class UndoQtTests(UndoFixtures,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def dispose(self,d):
        from PySide6.QtCore import QCoreApplication,QEvent
        if d.undo_dialog is not None:d.undo_dialog.close()
        d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()

    def test_preview_cancel_and_worker_undo(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend,source,target,original,result=self.restored_pair()
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True);d.backend=backend
        try:
            with mock.patch.object(backend,'targets',return_value=[target]),mock.patch.object(backend,'ensure_closed'):
                d.scanned(backend.discover(backend.recipe))
                self.assertTrue(d.undo_button.isEnabled())
                before=backend.snapshot(target)['fingerprint']
                d.undo_button.click();self.assertIsNotNone(d.undo_dialog)
                with mock.patch.object(d,'confirm_restore',return_value=False):d.undo_dialog.proceed_button.click()
                self.assertIsNone(d.worker)
                self.assertEqual(backend.snapshot(target)['fingerprint'],before)
                d.undo_button.click()
                with mock.patch.object(d,'confirm_restore',return_value=True):d.undo_dialog.proceed_button.click()
                deadline=time.monotonic()+10
                while d.worker is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.005)
                self.assertIsNone(d.worker)
                self.assertIn('Undo completed',d.result.text())
                self.assertEqual(backend.snapshot(target)['fingerprint'],original)
                self.assertFalse(d.undo_button.isEnabled())
        finally:self.dispose(d)

    def test_no_restore_reason_is_visible_on_disabled_button(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend,source,target=self.pair('fatekeeper')
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True);d.backend=backend
        try:
            with mock.patch.object(backend,'targets',return_value=[target]):d.scanned(backend.discover(backend.recipe))
            self.assertFalse(d.undo_button.isEnabled())
            self.assertIn('No recorded restore',d.undo_button.toolTip())
        finally:self.dispose(d)
