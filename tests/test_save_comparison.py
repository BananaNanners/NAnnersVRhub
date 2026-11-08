# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only hash comparison and explicit restore review."""
import unittest
from unittest import mock
from pathlib import Path
from vrhub.game_saves import compare_files
from tests.test_game_saves import SaveFixtures, HAS_QT, write


class ComparisonTests(unittest.TestCase):
    def test_target_perspective_and_deterministic_paths(self):
        source = {"new/z.sav": "a", "same.sav": "x", "changed.sav": "new", "new/a.sav": "b"}
        target = {"removed.sav": "old", "same.sav": "x", "changed.sav": "old"}
        with mock.patch("pathlib.Path.open", side_effect=AssertionError("comparison must not read or write disk")):
            result = compare_files(source, target)
        self.assertEqual(result, {"added": ["new/a.sav", "new/z.sav"], "changed": ["changed.sav"], "removed": ["removed.sav"], "unchanged": ["same.sav"]})
        self.assertEqual(source["changed.sav"], "new")
        self.assertEqual(target["changed.sav"], "old")

    def test_identical_empty_and_renamed_files(self):
        self.assertEqual(compare_files({}, {}), dict(added=[], changed=[], removed=[], unchanged=[]))
        result = compare_files({"old.sav": "a"}, {"old.sav": "a"})
        self.assertEqual(result["unchanged"], ["old.sav"])
        result = compare_files({"new.sav": "same content"}, {"old.sav": "same content"})
        self.assertEqual(result["added"], ["new.sav"])
        self.assertEqual(result["removed"], ["old.sav"])
        self.assertFalse(result["changed"])

    def test_path_file_directory_conflict_is_add_remove(self):
        result = compare_files({"slot": "new"}, {"slot/save.sav": "old"})
        self.assertEqual(result["added"], ["slot"])
        self.assertEqual(result["removed"], ["slot/save.sav"])


@unittest.skipUnless(HAS_QT, "Qt unavailable")
class ComparisonQtTests(SaveFixtures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make_dialog(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend, source, target = self.pair("fatekeeper")
        write(source, {"new.sav": b"added", "same.sav": b"same"})
        write(target, {"old.sav": b"removed", "same.sav": b"same"})
        d = GameSavesDialog(backend.recipe, auto_scan=False, development_enabled=True);d.backend = backend
        with mock.patch.object(backend, "targets", return_value=[target]):report=backend.discover(backend.recipe,[source])
        d.scanned(report)
        return d,backend,source,target

    def dispose(self, d):
        from PySide6.QtCore import QCoreApplication, QEvent
        if d.comparison_dialog is not None:d.comparison_dialog.close()
        d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()

    def select_source(self,d,source):
        index=next(i for i,row in enumerate(d.report["rows"]) if row["root"]==str(source))
        d.table.selectRow(index);self.app.processEvents()

    def test_counts_full_paths_and_no_file_changes(self):
        d,backend,source,target=self.make_dialog()
        try:
            before=backend.snapshot(target)["fingerprint"]
            self.assertFalse(d.compare_button.isEnabled())
            self.select_source(d,source)
            self.assertTrue(d.compare_button.isEnabled())
            self.assertIn("Added: 1 | Changed: 1 | Removed: 1 | Unchanged: 1",d.details.toPlainText())
            d.compare_button.click()
            table=d.comparison_dialog.table
            rows={(table.item(i,0).text(),table.item(i,1).text()) for i in range(table.rowCount())}
            self.assertEqual(rows,{("Added","new.sav"),("Changed","Slot0.sav"),("Removed","old.sav"),("Unchanged","same.sav")})
            self.assertEqual(backend.snapshot(target)["fingerprint"],before)
            self.assertFalse((self.home/"hub").exists())
        finally:self.dispose(d)

    def test_confirmation_contains_counts_paths_and_cancel_is_safe(self):
        from PySide6.QtWidgets import QMessageBox
        records=[]
        class ReviewBox(QMessageBox):
            def exec(self):
                records.append((self.text(),self.detailedText(),self.defaultButton()==self.button(QMessageBox.No)))
                return QMessageBox.No
        d,backend,source,target=self.make_dialog()
        try:
            self.select_source(d,source)
            before=backend.snapshot(target)["fingerprint"]
            with mock.patch("PySide6.QtWidgets.QMessageBox", ReviewBox):d.restore_button.click()
            text,detail,no_default=records[0]
            self.assertIn("Added: 1 | Changed: 1 | Removed: 1 | Unchanged: 1",text)
            self.assertIn("Target-only files",text)
            self.assertIn("old.sav",detail)
            self.assertIn("new.sav",detail)
            self.assertTrue(no_default)
            self.assertEqual(backend.snapshot(target)["fingerprint"],before)
            self.assertFalse((self.home/"hub").exists())
        finally:self.dispose(d)

    def test_current_target_has_no_restore_comparison(self):
        d,backend,source,target=self.make_dialog()
        try:
            self.select_source(d,source)
            index=next(i for i,row in enumerate(d.report["rows"]) if row["current"])
            d.table.selectRow(index)
            self.assertFalse(d.compare_button.isEnabled())
            self.assertIsNone(d.plan)
        finally:self.dispose(d)
