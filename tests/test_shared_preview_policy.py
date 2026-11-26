# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import patch
from threading import Event
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from vrhub import hub, game_capabilities as caps, gui
from vrhub.preview_policy import ReadOnlyPreview


class SharedPreviewPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_complete_capability_inventory(self):
        self.assertEqual(set(caps.CAPABILITIES), set(hub.load_recipes()))
        for rid, row in caps.CAPABILITIES.items():
            self.assertEqual(set(row), set(caps.OPERATIONS))
            self.assertTrue(set(row.values()) <= {caps.I, caps.R, caps.N, caps.E})
            self.assertEqual(row["version_check"], caps.I)
        self.assertEqual(caps.capabilities("unknown")["install"], caps.N)
        self.assertEqual(caps.capabilities("fatekeeper")["latest_rollback"], caps.R)
        for rid in ("subnautica", "valheim"):
            self.assertEqual(caps.capabilities(rid)["repair"], caps.N)
            self.assertEqual(caps.capabilities(rid)["original_restore"], caps.I)

    def test_update_worker_skips_metadata_writes(self):
        recipes = hub.load_recipes()
        with patch.object(hub, "refresh_component_names") as names, patch.object(hub, "state", return_value={}), patch.object(gui.updates, "check_all", return_value={}) as check:
            gui.UpdateWorker(refresh_names=False).run()
            names.assert_not_called()
            check.assert_called_once_with(recipes, {})

    def test_preview_refresh_and_mutation_policy_across_games(self):
        with patch.object(gui.updates, "check_all", return_value={rid: [] for rid in hub.load_recipes()}) as check, patch.object(hub, "refresh_component_names") as names:
            win = ReadOnlyPreview()
            self.addCleanup(win.close)
            win.show()
            for i, row in enumerate(win.rows):
                with self.subTest(game=row["recipe"]["id"]):
                    win.select_launcher_game(i)
                    self.assertTrue(win.mod_updates.refresh_button.isEnabled())
                    self.assertFalse(win.uninstall_btn.isEnabled())
                    self.assertFalse(win.unprofile_btn.isEnabled())
                    self.assertFalse(win.hub_update_btn.isEnabled())
                    self.assertFalse(win.allow_guided_installs)
                    self.assertFalse(win.downloads.allow_transfers)
                    win.mod_updates.set_checking(True)
                    win.apply_preview_policy()
                    self.assertFalse(win.mod_updates.refresh_button.isEnabled())
                    win.mod_updates.set_checking(False)
            win.mod_updates.refresh_button.click()
            for _ in range(300):
                QTest.qWait(10)
                if win.worker and not win.worker.isRunning() and win.mod_updates.refresh_button.isEnabled():
                    break
            self.assertIsNotNone(win.worker)
            self.assertFalse(win.worker.isRunning())
            self.assertTrue(win.mod_updates.refresh_button.isEnabled())
            self.assertEqual(set(win.update_results), set(hub.load_recipes()))
            check.assert_called_once()
            names.assert_not_called()
            self.assertFalse(win.uninstall_btn.isEnabled())
            with patch.object(hub, "uninstall") as remove:
                win.uninstall()
                remove.assert_not_called()

    def test_async_refresh_navigation_and_scan_completion(self):
        entered, release = Event(), Event()
        def lookup(*args):
            entered.set()
            release.wait(5)
            return {rid: [] for rid in hub.load_recipes()}
        with patch.object(gui.updates, "check_all", side_effect=lookup), patch.object(hub, "refresh_component_names") as names:
            win = ReadOnlyPreview()
            self.addCleanup(win.close)
            try:
                win.mod_updates.refresh_button.click()
                self.assertTrue(entered.wait(2))
                for i in range(len(win.rows)):
                    win.select_launcher_game(i)
                    win.downloads.set_recipe(win.current())
                    win.downloads.scan_idle.emit()
                    self.assertFalse(win.mod_updates.refresh_button.isEnabled())
                    self.assertFalse(win.downloads.download_button.isEnabled())
                    self.assertFalse(win.uninstall_btn.isEnabled())
                    self.assertFalse(win.hub_update_btn.isEnabled())
                release.set()
                for _ in range(300):
                    QTest.qWait(10)
                    if not win.worker.isRunning() and win.mod_updates.refresh_button.isEnabled():
                        break
                self.assertTrue(win.mod_updates.refresh_button.isEnabled())
                self.assertFalse(win.worker.isRunning())
                self.assertFalse(win.downloads.download_button.isEnabled())
                names.assert_not_called()
            finally:
                release.set()
                if win.worker:
                    win.worker.wait(6000)

    def test_system_dashboard_readonly_scan_and_refresh(self):
        from copy import deepcopy
        from PySide6.QtCore import QCoreApplication, QEvent
        from vrhub import system_scan
        # The actual scanner contract is covered separately; use deterministic
        # telemetry here to test the shared preview, not a historical subclass.
        with patch.object(system_scan, "_process_names", return_value=set()):
            sample = system_scan.scan()
        sample["runtime"] = "WiVRn"
        sample["live"].update(runtime_selected=True, server_running=True,
                              headset_connected=True, activity="WiVRn CONNECTED",
                              controllers_verified=False)
        disconnected = deepcopy(sample)
        disconnected["live"].update(headset_connected=False, activity="Idle")
        with patch.object(system_scan, "scan", return_value=sample) as scan, \
             patch.object(system_scan, "refresh_live", return_value=disconnected) as refresh, \
             patch.object(gui.QFileDialog, "getSaveFileName") as save:
            win = ReadOnlyPreview()
            try:
                win.show()
                win.scan_timer.stop()
                scan.assert_not_called()
                win.tabs.setCurrentIndex(0)
                for _ in range(300):
                    QTest.qWait(10)
                    if win.scan_report is not None and win.scan_worker is None:
                        break
                scan.assert_called_once()
                self.assertIsNone(win.scan_worker)
                self.assertEqual(win.headset_state.text(), "Headset: CONNECTED")
                self.assertTrue(win.scan_btn.isEnabled())
                self.assertTrue(win.copy_scan_btn.isEnabled())
                self.assertFalse(win.save_scan_btn.isEnabled())
                win.save_system_report()
                save.assert_not_called()
                win.refresh_system_live()
                for _ in range(300):
                    QTest.qWait(10)
                    if win.scan_worker is None:
                        break
                refresh.assert_called_once()
                self.assertEqual(win.headset_state.text(), "Headset: DISCONNECTED")
                self.assertIn("Not tested", win.controllers_state.text())
                win.auto_live.setChecked(False)
                win.refresh_system_live()
                refresh.assert_called_once()
                win.scan_btn.click()
                for _ in range(300):
                    QTest.qWait(10)
                    if win.scan_worker is None:
                        break
                self.assertEqual(scan.call_count, 2)
                self.assertEqual(win.headset_state.text(), "Headset: CONNECTED")
                win.apply_preview_policy()
                self.assertTrue(win.scan_btn.isEnabled())
                self.assertTrue(win.copy_scan_btn.isEnabled())
                self.assertFalse(win.save_scan_btn.isEnabled())
                self.assertFalse(win.allow_guided_installs)
                self.assertFalse(win.downloads.allow_transfers)
                self.assertFalse(win.hub_update_btn.isEnabled())
            finally:
                if win.scan_worker:
                    win.scan_worker.wait(6000)
                    self.app.processEvents()
                win.close()
                win.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
