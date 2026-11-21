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
        self.assertIs(self.window.game_launch_btn.parent(), self.window.more_tools_panel)
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
                self.assertEqual(self.window.launch_tools_panel.isVisible(),
                                 copy_supported or injector_supported)
                self.assertEqual(self.window.copy_btn.isEnabled(), copy_supported)
                self.assertEqual(self.window.inject_btn.isEnabled(), injector_supported)

    def test_switching_from_no_actions_to_both_restores_buttons(self):
        self.select_game("doom-2016-gog")
        self.assertTrue(self.window.launch_tools_panel.isHidden())
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
                      self.window.more_tools_panel)
        self.assertNotIn(self.window.copy_btn,
                         self.window.more_tools_panel.findChildren(
                             __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton))
        self.assertNotIn(self.window.inject_btn,
                         self.window.more_tools_panel.findChildren(
                             __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton))


if __name__ == "__main__":
    unittest.main()
