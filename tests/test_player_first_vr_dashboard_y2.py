# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-Y2 regression: usable read-only VR System in isolated preview."""
from __future__ import annotations

import copy
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import hub, gui, system_scan
from vrhub.app_update_gui import HubUpdateController
from tests.manual_launcher_dev5d3y2_preview import PlayerFirstPreview


class PlayerFirstSystemDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # The host scanner is read-only. Capture once, then return this
        # immutable snapshot from a fast QThread fixture. No test is allowed
        # to launch game installers or create user-state artifacts.
        cls.sample = system_scan.scan()

    def setUp(self):
        self.patches = [
            mock.patch.object(gui.HubWindow, "check_updates"),
            mock.patch.object(HubUpdateController, "startup"),
            mock.patch.object(hub, "state", return_value={}),
            mock.patch.object(hub, "refresh_component_names", return_value=0),
            mock.patch.object(system_scan, "scan",
                              side_effect=lambda: copy.deepcopy(self.sample)),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.window = PlayerFirstPreview()
        self.window.show()
        self.addCleanup(self.close)
        self.wait_for_scan()
        # Disable periodic refresh for deterministic manual button tests.
        # Test the real live-refresh toggle separately.
        self.window.auto_live.setChecked(False)

    def close(self):
        self.window.close()
        for _ in range(150):
            if self.window.scan_worker is None:
                break
            QTest.qWait(10)

    def wait_for_scan(self):
        for _ in range(300):
            if self.window.scan_report is not None and self.window.scan_worker is None:
                return
            QTest.qWait(10)
        self.fail("Read-only system scan did not finish in bounded Qt time.")

    def test_dashboard_populates_after_real_scan_worker_path(self):
        r = self.window.scan_report
        self.assertEqual(r["status"], self.sample["status"])
        self.assertNotIn("checking", self.window.runtime_state.text().lower())
        self.assertNotIn("checking", self.window.server_state.text().lower())
        self.assertNotIn("checking", self.window.headset_state.text().lower())
        self.assertNotIn("checking", self.window.scan_summary.text().lower())
        self.assertTrue(self.window.scan_btn.isEnabled())
        self.assertTrue(self.window.copy_scan_btn.isEnabled())
        # Save report requires arbitrary disk writes; held in safe preview.
        self.assertFalse(self.window.save_scan_btn.isEnabled())
        self.assertIsNotNone(self.window.scan_report)
        self.assertIn(r["status"], self.window.system_details.toPlainText())

    def test_player_can_scan_again_and_copy_existing_report(self):
        self.window.sidebar.system_button.click()
        self.app.processEvents()
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        with mock.patch.object(system_scan, "scan",
                               side_effect=lambda: copy.deepcopy(self.sample)) as scan:
            self.window.scan_btn.click()
            self.wait_for_scan()
            scan.assert_called_once()
        self.window.copy_scan_btn.click()
        clipboard = QApplication.clipboard().text()
        self.assertIn("VR System Scan", clipboard)
        self.assertIn(self.sample["status"], clipboard)
        self.assertFalse(self.window.save_scan_btn.isEnabled())

    def test_automatic_live_refresh_stays_read_only(self):
        self.window.sidebar.system_button.click()
        self.app.processEvents()
        original = copy.deepcopy(self.window.scan_report)
        refreshed = copy.deepcopy(original)
        refreshed["live"]["headset_connected"] = None
        with mock.patch.object(system_scan, "refresh_live",
                               return_value=refreshed) as live:
            # The existing "Auto-refresh live status" control immediately
            # samples once when enabled on the VR System page.
            self.window.auto_live.setChecked(True)
            for _ in range(300):
                if self.window.scan_worker is None and live.called:
                    break
                QTest.qWait(10)
            live.assert_called_once()
        self.assertIsNone(self.window.scan_worker)
        self.assertTrue(self.window.scan_btn.isEnabled())
        self.assertFalse(self.window.save_scan_btn.isEnabled())
        self.assertFalse(self.window.allow_guided_installs)
        self.assertFalse(self.window.downloads.allow_transfers)

    def test_openxr_host_manifest_is_read_only_visible_to_isolated_preview(self):
        import os
        from pathlib import Path
        from unittest import mock
        from tests.manual_launcher_dev5d3y2_preview import (
            _bind_host_openxr_runtime_for_preview,
        )
        import tempfile
        with tempfile.TemporaryDirectory(prefix="nanners-y2-runtime-fixture-") as t:
            host = Path(t)
            source = host/"openxr/1"
            source.mkdir(parents=True)
            manifest = source/"active_runtime.json"
            manifest.write_text(
                '{"file_format_version":"1.0.0","runtime":{'
                '"library_path":"/test/libopenxr.so"}}')
            original = manifest.read_bytes()
            with mock.patch.dict(os.environ, {"XR_RUNTIME_JSON":""}):
                self.assertTrue(_bind_host_openxr_runtime_for_preview(host))
                self.assertEqual(os.environ.get("XR_RUNTIME_JSON"), str(manifest))
                self.assertFalse(_bind_host_openxr_runtime_for_preview(host))
            self.assertEqual(original, manifest.read_bytes())
            with mock.patch.dict(os.environ, {"XR_RUNTIME_JSON":"/fixed/external.json"}):
                self.assertFalse(_bind_host_openxr_runtime_for_preview(host))
                self.assertEqual(os.environ["XR_RUNTIME_JSON"], "/fixed/external.json")

    def test_sidebar_has_only_real_player_destinations(self):
        sidebar = self.window.sidebar
        self.assertTrue(sidebar.games_button.isVisible())
        self.assertTrue(sidebar.system_button.isVisible())
        self.assertFalse(sidebar.future_toggle.isVisible())
        self.assertFalse(sidebar.future_toggle.isEnabled())
        self.assertFalse(sidebar.future_panel.isVisible())
        sidebar.future_toggle.setChecked(True)
        self.app.processEvents()
        self.assertFalse(sidebar.future_panel.isVisible())
        self.assertEqual(sidebar.game_list.count(), 9)
        self.assertEqual(self.window.tabs.count(), 2)

    def test_scanner_cannot_enable_mutating_preview_actions(self):
        self.window.disable_mutations()
        self.assertTrue(self.window.scan_btn.isEnabled())
        self.assertTrue(self.window.copy_scan_btn.isEnabled())
        self.assertFalse(self.window.save_scan_btn.isEnabled())
        self.assertFalse(self.window.allow_guided_installs)
        self.assertFalse(self.window.downloads.allow_transfers)
        self.assertFalse(self.window.hub_update_btn.isEnabled())
        self.assertFalse(self.window.doom_saves_btn.isEnabled())
        self.assertFalse(self.window.downloads.download_button.isEnabled())
