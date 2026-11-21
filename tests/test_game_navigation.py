# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D1-A: navigation reorganizes existing pages without changing behaviors."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QLabel

from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow


NAMES = ("Overview", "Mod Updates", "Install / Update", "Rollback",
         "Compatibility", "Controller Bindings", "Setup Guide")


class GameNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patches = (
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.win = HubWindow()
        self.win.show()
        self.app.processEvents()
        self.addCleanup(self.win.close)

    def tab(self, widget):
        return self.win.game_details_tabs.indexOf(widget)

    def test_exact_seven_tabs_with_kde_icons_and_scrollable_overflow(self):
        tabs = self.win.game_details_tabs
        self.assertEqual(tabs.count(), 7)
        self.assertEqual(tuple(tabs.tabText(i) for i in range(tabs.count())), NAMES)
        self.assertTrue(all(not tabs.tabIcon(i).isNull() for i in range(7)))
        self.assertTrue(tabs.tabBar().usesScrollButtons())
        self.assertFalse(tabs.tabBar().expanding())
        self.assertEqual(tabs.objectName(), "gameDetailsTabs")
        self.assertIn("QTabWidget#gameDetailsTabs QTabBar::tab:selected",
                      self.win.styleSheet())
        self.assertIn("#FFD21A", self.win.styleSheet())
        self.assertIn("#23B7FF", self.win.styleSheet())

    def test_navigation_reuses_exact_existing_widgets(self):
        self.assertIs(self.win.game_details_tabs.widget(0), self.win.overview_page)
        self.assertIs(self.win.game_details_tabs.widget(1), self.win.mod_updates)
        self.assertIs(self.win.game_details_tabs.widget(2), self.win.downloads)
        self.assertIs(self.win.game_details_tabs.widget(3), self.win.rollback_page)
        self.assertIs(self.win.game_details_tabs.widget(4), self.win.compat_page)
        self.assertIs(self.win.game_details_tabs.widget(5), self.win.controller_bindings)
        self.assertIs(self.win.game_details_tabs.widget(6), self.win.details)
        self.assertIs(self.win.game_dashboard.parent(), self.win.overview_page)
        self.assertEqual(self.win.game_details_tabs.currentIndex(), 0)

    def test_compatibility_preserves_dated_evidence_and_local_checks(self):
        self.win.game_details_tabs.setCurrentIndex(self.tab(self.win.compat_page))
        self.app.processEvents()
        self.assertEqual(self.win.current()["id"], "cyberpunk-2077")
        self.assertIsNotNone(self.win.compat_report)
        self.assertIn("profile", self.win.compat_report)
        self.assertIn("checks", self.win.compat_report)
        self.assertIn("local_test", self.win.compat_report)
        self.assertIn("Bundled compatibility reference", self.win.compat_details.toHtml())
        self.assertIn("Refresh compatibility", self.win.compat_refresh_btn.text())
        self.assertEqual(self.win.compat_copy_btn.text(), "Copy compatibility report")
        self.assertEqual(self.win.test_history_btn.text(), "Test history…")

    def test_update_count_keeps_original_update_grouping(self):
        idx = next(i for i,r in enumerate(self.win.rows)
                   if r["recipe"]["id"] == "cyberpunk-2077")
        self.win.update_results["cyberpunk-2077"] = [
            {"name":"a", "status":"update"},
            {"name":"b", "status":"update"},
            {"name":"c", "status":"current"},
        ]
        self.win.table.selectRow(idx)
        self.win.show_details()
        self.assertEqual(self.win.game_details_tabs.tabText(
            self.tab(self.win.mod_updates)), "Mod Updates (2)")
        self.assertEqual(self.win.mod_updates.sections["update"].table.rowCount(), 2)

    def test_rollback_is_explicitly_not_a_new_restoration_engine(self):
        recipe = self.win.current()
        with mock.patch("vrhub.gui.hub.state", return_value={
            recipe["id"]: {"installer":"legacy"},
            recipe["id"] + ":profile": {"root":"/old"},
        }):
            self.win.refresh_rollback_summary(recipe)
        self.assertIn("recovery policy depends on installer",
                      self.win.rollback_summary.text())
        self.assertIn("No UEVR profile step",
                      self.win.rollback_summary.text())
        self.assertIn("Recorded does not mean verified",
                      self.win.rollback_page.findChild(QLabel, "rollbackNotice").text())
        self.assertIsNotNone(self.win.uninstall_btn)
        self.assertIsNotNone(self.win.unprofile_btn)
        self.assertEqual(self.win.uninstall_btn.parent(), self.win.rollback_page)

    def test_game_switching_preserves_selected_navigation(self):
        self.win.game_details_tabs.setCurrentIndex(self.tab(self.win.compat_page))
        idx = next(i for i,r in enumerate(self.win.rows)
                   if r["recipe"]["id"] == "fatekeeper")
        self.win.select_launcher_game(idx)
        self.app.processEvents()
        self.assertEqual(self.win.game_details_tabs.currentIndex(), 4)
        self.assertEqual(self.win.current()["id"], "fatekeeper")
        self.assertIn("Fatekeeper", self.win.compat_details.toPlainText())
