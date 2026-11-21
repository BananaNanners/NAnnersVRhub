# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C2 GUI: distinguish legacy Cyberpunk records, ask before restoration."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from vrhub import archive_scans, download_planner as planner, hub
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow


class GamerootRestoreUIAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dev5c2-ui-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state.json"
        self.state.write_text("{}")
        self.archives = self.root / "archives"
        self.archives.mkdir()
        for patcher in (
            mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.state)}),
            mock.patch.object(planner, "preferences_file",
                              return_value=self.root / "folders.json"),
            mock.patch.object(planner, "default_library",
                              return_value=self.archives),
            mock.patch.object(archive_scans, "snapshot_file",
                              return_value=self.root / "scans.json"),
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        index = next(i for i, r in enumerate(self.window.rows)
                     if r["recipe"]["id"] == "cyberpunk-2077")
        self.window.sidebar.game_list.setCurrentRow(index)
        self.app.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def write_record(self, record):
        self.state.write_text(json.dumps({"cyberpunk-2077": record}))
        self.window.downloads.set_recipe(self.window.current())
        self.app.processEvents()

    def test_fresh_profile_notice_explains_retained_origins(self):
        self.assertIn("retain original", self.window.downloads.backup_safety_status.text())
        self.assertNotIn("LEGACY", self.window.downloads.backup_safety_status.text())

    def test_legacy_record_is_clearly_marked_unsafe_to_auto_restore(self):
        self.write_record({
            "keep": "/old/game", "files": ["/old/game/bin/test.dll"],
            "components": {"107": {"files": ["/old/game/bin/test.dll"]}}})
        self.assertIn("LEGACY CYBERPUNK INSTALLATION",
                      self.window.downloads.backup_safety_status.text())
        self.assertIn("BLOCKED", self.window.downloads.backup_safety_status.text())
        with mock.patch("vrhub.gui.QMessageBox.warning") as warning, \
                mock.patch("vrhub.gui.QMessageBox.question") as confirm, \
                mock.patch("vrhub.gui.hub.uninstall") as uninstall:
            self.window.uninstall()
        warning.assert_called_once()
        confirm.assert_not_called()
        uninstall.assert_not_called()

    def test_new_backup_record_has_explicit_restore_consent_default_no(self):
        self.write_record({
            "installer": "gameroot-2",
            "keep": "/fake/game", "backup": "/fake/hub/backups/x",
            "originals": {"bin/old.dll": {"size": 10, "sha256": "a"*64},
                          "r6/new.reds": None},
            "installed_sha256": {"bin/old.dll": "b"*64,
                                  "r6/new.reds": "c"*64},
            "files": ["/fake/game/bin/old.dll", "/fake/game/r6/new.reds"],
        })
        self.assertIn("1 original file", self.window.downloads.backup_safety_status.text())
        with mock.patch("vrhub.gui.QMessageBox.question",
                        return_value=QMessageBox.No) as question, \
                mock.patch("vrhub.gui.hub.uninstall") as uninstall:
            self.window.uninstall()
        question.assert_called_once()
        self.assertIn("Restore 1 original", question.call_args.args[2])
        self.assertIn("remove 1 files", question.call_args.args[2])
        self.assertIn("rehashed", question.call_args.args[2])
        self.assertEqual(question.call_args.args[-1], QMessageBox.No)
        uninstall.assert_not_called()

    def test_no_state_record_does_not_offer_removal(self):
        with mock.patch("vrhub.gui.QMessageBox.information") as notice, \
                mock.patch("vrhub.gui.QMessageBox.question") as ask, \
                mock.patch("vrhub.gui.hub.uninstall") as undo:
            self.window.uninstall()
        notice.assert_called_once()
        ask.assert_not_called()
        undo.assert_not_called()

if __name__ == "__main__":
    unittest.main()
