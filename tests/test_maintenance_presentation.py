# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from vrhub import game_capabilities as caps, gui, hub
from vrhub.preview_policy import ReadOnlyPreview

# Independent expectations: mod control, profile control, guidance fragment.
EXPECTED = {
    "fatekeeper": (True, False, "Latest-transaction rollback"),
    "hogwarts-legacy": (False, True, "Original restoration"),
    "subnautica": (True, False, "Original restoration"),
    "valheim": (True, False, "Original restoration"),
    "elden-ring": (True, False, "Original restoration"),
    "ready-or-not": (True, False, "Original restoration"),
    "cyberpunk-2077": (True, False, "Original restoration"),
    "doom-2016-gog": (False, False, "KHARVOX"),
    "skyrim-vr-mgo": (False, False, "external mod manager"),
}


class MaintenancePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def dispose_widget(self, widget):
        self.assertTrue(widget.close())
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_inventory_and_unknown(self):
        recipes = hub.load_recipes()
        self.assertEqual(set(recipes), set(EXPECTED))
        for rid, (mod, profile, guidance) in EXPECTED.items():
            with self.subTest(game=rid):
                result = caps.restoration_presentation(recipes[rid])
                self.assertEqual((result["mod_visible"], result["profile_visible"]), (mod, profile))
                self.assertIn(guidance, caps.maintenance_guidance(rid))
        for recipe in (None, {}, {"id": "unknown", "profile": {"dir": "test"}}):
            result = caps.restoration_presentation(recipe)
            self.assertFalse(result["mod_visible"])
            self.assertFalse(result["profile_visible"])

    def test_normal_and_read_only_windows_across_all_games(self):
        with patch.object(gui.HubWindow, "check_updates"), patch.object(gui.HubWindow, "scan_setup"), patch.object(gui.HubUpdateController, "startup"), patch.object(hub, "state", return_value={}):
            for window_type in (gui.HubWindow, ReadOnlyPreview):
                win = window_type()
                try:
                    win.show()
                    order = list(range(len(win.rows)))
                    for i in order + order[::-1]:
                        rid = win.rows[i]["recipe"]["id"]
                        with self.subTest(window=window_type.__name__, game=rid):
                            win.select_launcher_game(i)
                            win.game_details_tabs.setCurrentWidget(win.rollback_page)
                            self.app.processEvents()
                            mod, profile, guidance = EXPECTED[rid]
                            self.assertEqual(win.uninstall_btn.isVisible(), mod)
                            self.assertEqual(win.unprofile_btn.isVisible(), profile)
                            self.assertIn(guidance, win.rollback_summary.text())
                            self.assertEqual(win.uninstall_btn.text(), "Restore previous installation" if rid == "fatekeeper" else "Review removal and restoration")
                            self.assertEqual(win.unprofile_btn.text(), "Restore original profile")
                            self.assertIs(win.uninstall_btn.parent(), win.rollback_page)
                            self.assertIs(win.unprofile_btn.parent(), win.rollback_page)
                            if window_type is ReadOnlyPreview:
                                self.assertFalse(win.uninstall_btn.isEnabled())
                                self.assertFalse(win.unprofile_btn.isEnabled())
                                self.assertFalse(win.downloads.allow_transfers)
                                self.assertFalse(win.allow_guided_installs)
                            else:
                                self.assertEqual(win.uninstall_btn.isEnabled(), mod)
                                self.assertEqual(win.unprofile_btn.isEnabled(), profile)
                finally:
                    self.dispose_widget(win)


    def test_update_guidance_across_nine_games(self):
        from vrhub.mod_updates_gui import ModUpdatesPage
        page = ModUpdatesPage()
        self.addCleanup(self.dispose_widget, page)
        recipes = hub.load_recipes()
        for rid in list(EXPECTED) + list(reversed(EXPECTED)):
            with self.subTest(game=rid):
                expected = (
                    "require compatibility and safety review"
                    if rid in ("fatekeeper", "hogwarts-legacy") else
                    "external mod manager" if rid == "skyrim-vr-mgo" else
                    "does not yet support managed updates")
                for items in (None, [{"name": "Fixture", "status": "update",
                                      "installed_version": "1", "latest_version": "2"}]):
                    groups = page.set_recipe(recipes[rid], items)
                    self.assertIn(expected, page.explanation.text())
                    self.assertIn("does not download, install", page.explanation.text())
                    self.assertEqual(len(groups["update"]), int(bool(items)))
                    self.assertTrue(page.refresh_button.isEnabled())
        page.set_recipe(None, None)
        self.assertNotIn("managed updates", page.explanation.text())
        self.assertNotIn("external mod manager", page.explanation.text())
        self.assertIn("does not yet support", caps.update_guidance("unknown"))
