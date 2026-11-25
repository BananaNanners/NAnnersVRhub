# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D1-B launch-tools refinement: move existing actions without changing behavior."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QLabel
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow
from vrhub import hub


class OverviewLaunchToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = (
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        )
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def select_game(self, recipe_id):
        row = next(
            i for i, r in enumerate(self.window.rows)
            if r["recipe"]["id"] == recipe_id)
        self.window.table.selectRow(row)
        self.window.game_details_tabs.setCurrentIndex(
            self.window.game_details_tabs.indexOf(self.window.overview_page))
        self.app.processEvents()
        self.assertEqual(self.window.current()["id"], recipe_id)

    def test_original_buttons_reparented_to_compact_overview_row(self):
        self.select_game("fatekeeper")
        panel = self.window.launch_tools_panel
        self.assertIs(panel.parent(), self.window.overview_page)
        self.assertIs(self.window.copy_btn.parent(), panel)
        self.assertIs(self.window.inject_btn.parent(), panel)
        self.assertEqual(panel.objectName(), "overviewLaunchTools")
        self.assertLessEqual(panel.maximumWidth(), 760)
        self.assertIsInstance(self.window.launch_tools_label, QLabel)
        self.assertEqual(self.window.launch_tools_label.text(), "LAUNCH TOOLS")
        self.assertIs(self.window.game_launch_btn.parent(), panel)
        self.assertIs(self.window.doom_probe_btn.parent(), panel)
        self.assertEqual(self.window.quick_actions.buttons,
                         (self.window.game_play_btn, self.window.preflight_btn))
        self.assertTrue(panel.isVisible())
        self.assertTrue(self.window.copy_btn.isVisible())
        self.assertTrue(self.window.inject_btn.isVisible())

    def test_visibility_uses_actual_game_launch_capability(self):
        expectations = {
            "cyberpunk-2077": (True, False),
            "fatekeeper": (True, True),
            "hogwarts-legacy": (False, True),
            "doom-2016-gog": (False, False),
            "valheim": (True, False),
            "skyrim-vr-mgo": (True, False),
            "ready-or-not": (True, False),
        }
        for recipe_id, (copy_supported, injector_supported) in expectations.items():
            with self.subTest(recipe_id=recipe_id):
                self.select_game(recipe_id)
                self.assertEqual(self.window.copy_btn.isVisible(), copy_supported)
                self.assertEqual(self.window.inject_btn.isVisible(), injector_supported)
                special_launcher = recipe_id in ("skyrim-vr-mgo", "doom-2016-gog")
                self.assertEqual(self.window.launch_tools_panel.isVisible(),
                                 copy_supported or injector_supported or special_launcher)
                self.assertEqual(self.window.game_launch_btn.isVisible(),
                                 special_launcher)
                self.assertEqual(self.window.doom_probe_btn.isVisible(),
                                 recipe_id == "doom-2016-gog")
                self.assertEqual(self.window.copy_btn.isEnabled(), copy_supported)
                self.assertEqual(self.window.inject_btn.isEnabled(), injector_supported)

    def test_switching_from_no_actions_to_both_restores_buttons(self):
        self.select_game("doom-2016-gog")
        self.assertTrue(self.window.launch_tools_panel.isVisible())
        self.assertEqual(self.window.game_launch_btn.text(), "Launch DOOM VR")
        self.assertEqual(self.window.game_play_btn.text(), "Launch DOOM (flat)")
        self.assertTrue(self.window.doom_probe_btn.isVisible())
        self.select_game("skyrim-vr-mgo")
        self.assertTrue(self.window.launch_tools_panel.isVisible())
        self.assertEqual(self.window.game_launch_btn.text(), "Launch MO2")
        self.assertEqual(self.window.game_play_btn.text(), "Launch Skyrim VR")
        self.assertTrue(self.window.copy_btn.isVisible())
        self.assertFalse(self.window.doom_probe_btn.isVisible())
        self.select_game("fatekeeper")
        self.assertTrue(self.window.launch_tools_panel.isVisible())
        self.assertTrue(self.window.copy_btn.isVisible())
        self.assertTrue(self.window.inject_btn.isVisible())
        self.select_game("hogwarts-legacy")
        self.assertFalse(self.window.copy_btn.isVisible())
        self.assertTrue(self.window.inject_btn.isVisible())
        self.select_game("cyberpunk-2077")
        self.assertTrue(self.window.copy_btn.isVisible())
        self.assertFalse(self.window.inject_btn.isVisible())

    def test_copy_launch_options_uses_existing_clipboard_handler(self):
        self.select_game("fatekeeper")
        original = QApplication.clipboard().text()
        self.addCleanup(lambda: QApplication.clipboard().setText(original))
        with mock.patch("vrhub.gui.hub.launch_options",
                        return_value="TEST_OPTS=1 %command%") as launch:
            self.window.copy_btn.click()
            launch.assert_called_once_with(self.window.current())
        self.assertEqual(QApplication.clipboard().text(),
                         "TEST_OPTS=1 %command%")

    def test_injector_click_keeps_existing_handler_without_launching_anything(self):
        # Replace class handler before creating the test window; this checks
        # original signal wiring without ever starting a real injector.
        self.window.close()
        self.window.deleteLater()
        with mock.patch.object(HubWindow, "run_injector") as injector:
            fresh = HubWindow()
            self.addCleanup(fresh.close)
            fresh.show()
            self.app.processEvents()
            row = next(i for i, r in enumerate(fresh.rows)
                       if r["recipe"]["id"] == "hogwarts-legacy")
            fresh.table.selectRow(row)
            fresh.game_details_tabs.setCurrentIndex(
                fresh.game_details_tabs.indexOf(fresh.overview_page))
            self.app.processEvents()
            self.assertTrue(fresh.inject_btn.isVisible())
            fresh.inject_btn.click()
            injector.assert_called_once_with()

    def test_bridge_logs_are_compatibility_diagnostics_with_distinct_labels(self):
        from pathlib import Path
        with mock.patch("vrhub.gui.hub.game_bridge_log",
                        return_value=Path("/fake/bridge.log")):
            self.select_game("skyrim-vr-mgo")
            self.assertEqual(self.window.bridge_log_btn.text(), "Open MO2 bridge log")
            self.assertIs(self.window.bridge_log_btn.parent(),
                          self.window.more_tools_panel)
            self.assertFalse(self.window.doom_logs_btn.isVisible())
            self.select_game("doom-2016-gog")
            self.assertEqual(self.window.bridge_log_btn.text(), "Open KHARVOX log")
            self.assertIs(self.window.bridge_log_btn.parent(),
                          self.window.more_tools_panel)
            self.assertIs(self.window.doom_logs_btn.parent(),
                          self.window.more_tools_panel)
            self.window.game_details_tabs.setCurrentIndex(
                self.window.game_details_tabs.indexOf(self.window.compat_page))
            self.window.more_tools_toggle.setChecked(True)
            self.app.processEvents()
            self.assertTrue(self.window.bridge_log_btn.isVisible())

    def test_original_mo2_and_doom_launcher_handlers_are_still_wired(self):
        # Patch before constructing the window so the real Qt click signal
        # connects to the mock rather than launching any Steam or DOOM process.
        self.window.close()
        self.window.deleteLater()
        with mock.patch.object(HubWindow, "launch_game_tool") as launcher:
            fresh = HubWindow()
            self.addCleanup(fresh.close)
            fresh.show()
            for game_id, title in (
                ("skyrim-vr-mgo", "Launch MO2"),
                ("doom-2016-gog", "Launch DOOM VR"),
            ):
                row = next(i for i, r in enumerate(fresh.rows)
                           if r["recipe"]["id"] == game_id)
                fresh.table.selectRow(row)
                fresh.game_details_tabs.setCurrentIndex(
                    fresh.game_details_tabs.indexOf(fresh.overview_page))
                self.app.processEvents()
                self.assertEqual(fresh.game_launch_btn.text(), title)
                self.assertTrue(fresh.game_launch_btn.isVisible())
                fresh.game_launch_btn.click()
            self.assertEqual(launcher.call_count, 2)
            self.assertEqual([args for args, _ in launcher.call_args_list],
                             [(), ()])

    def test_doom_bridge_probe_keeps_its_guarded_handler(self):
        self.window.close()
        self.window.deleteLater()
        with mock.patch.object(HubWindow, "run_kharvox_bridge") as probe:
            fresh = HubWindow()
            self.addCleanup(fresh.close)
            fresh.show()
            row = next(i for i, r in enumerate(fresh.rows)
                       if r["recipe"]["id"] == "doom-2016-gog")
            fresh.table.selectRow(row)
            fresh.game_details_tabs.setCurrentIndex(
                fresh.game_details_tabs.indexOf(fresh.overview_page))
            self.app.processEvents()
            self.assertTrue(fresh.doom_probe_btn.isVisible())
            self.assertEqual(fresh.doom_probe_btn.text(), "Test VR Setup")
            fresh.doom_probe_btn.click()
            probe.assert_called_once_with("probe")

    def test_compatibility_diagnostics_still_accessible(self):
        self.select_game("fatekeeper")
        self.window.game_details_tabs.setCurrentIndex(
            self.window.game_details_tabs.indexOf(self.window.compat_page))
        self.window.more_tools_toggle.setChecked(True)
        self.app.processEvents()
        self.assertTrue(self.window.more_tools_panel.isVisible())
        self.assertIs(self.window.log_diagnostics_btn.parent(),
                      self.window.more_tools_panel)
        self.assertIs(self.window.support_report_btn.parent(),
                      self.window.more_tools_panel)
        self.assertIs(self.window.game_launch_btn.parent(),
                      self.window.launch_tools_panel)
        self.assertIs(self.window.doom_probe_btn.parent(),
                      self.window.launch_tools_panel)
        self.assertNotIn(self.window.copy_btn,
                         self.window.more_tools_panel.findChildren(
                             __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton))
        self.assertNotIn(self.window.inject_btn,
                         self.window.more_tools_panel.findChildren(
                             __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton))


if __name__ == "__main__":
    unittest.main()
