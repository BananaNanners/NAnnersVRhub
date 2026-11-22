# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev3 Mod Updates: truthful per-mod versions, grouped UI, preserved Hub flows."""
import unittest
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QPushButton
from vrhub import hub, updates
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow
from vrhub.mod_updates_gui import (
    ModUpdatesPage, UpdateTable, grouped_updates, safe_source_url,
)


def sample_updates():
    base = "https://www.nexusmods.com/cyberpunk2077/mods/"
    def item(name, mod_id, status, local=None, remote=None, detail=None):
        return {
            "name": name, "mod_id": mod_id, "status": status,
            "page": base + str(mod_id),
            "detail": detail or (f"{name} requires review" if status == "unknown"
                                 else f"{name} status {status}"),
            **({"installed_version": local} if local is not None else {}),
            **({"latest_version": remote} if remote is not None else {}),
        }
    result = [
        item("Cyber Engine Tweaks", 107, "update", "1.37.1", "1.38.1"),
        item("Input Loader", 4575, "update", "0.2.3", "0.2.6"),
        item("Codeware", 7780, "update", "1.20.5", "1.21.4"),
        item("Visual Holsters", 21936, "update", "1.2", "1.4"),
        item("Visible Bullets", 22251, "unknown", "2.31", "2.5"),
        item("CyberpunkVR Port", 30093, "not_installed"),
    ]
    for name, mod_id, version in (
        ("RED4ext", 2380, "1.31.1"),
        ("redscript", 1511, "0.5.32"),
        ("TweakXL", 4197, "1.12.2"),
        ("ArchiveXL", 4198, "1.28.8"),
        ("Nova Optics", 29190, "1.4.2"),
        ("Equipment-EX", 6945, "1.3.1"),
        ("Military Pistol Holsters", 18002, "1.5"),
        ("Equipable Katana", 22071, "1.4"),
        ("More Occluders", 33136, "0.4"),
    ):
        result.append(item(name, mod_id, "current", version, version))
    return result


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.recipe = hub.load_recipes()["cyberpunk-2077"]

    def test_exact_15_components_separated_by_status(self):
        grouping = grouped_updates(self.recipe, sample_updates())
        self.assertEqual({k: len(v) for k, v in grouping.items()}, {
            "update": 4, "review": 1, "later": 1, "not_installed": 0, "current": 9})
        self.assertEqual(grouping["review"][0]["installed"], "2.31")
        self.assertEqual(grouping["review"][0]["latest"], "2.5")
        self.assertEqual(grouping["review"][0]["status"], "Review version")
        self.assertEqual(grouping["later"][0]["status"], "Install later")
        self.assertEqual(grouping["later"][0]["latest"], "—")
        self.assertEqual(grouping["update"][0]["latest"], "1.38.1")

    def test_later_stage_only_if_recipe_explicitly_says_phase2(self):
        raw = [{"name": "Package", "mod_id": 4575, "status": "not_installed"}]
        rows = grouped_updates(self.recipe, raw)
        self.assertEqual(len(rows["not_installed"]), 1)
        self.assertEqual(len(rows["later"]), 0)
        self.assertEqual(grouped_updates({}, raw)["not_installed"][0]["status"], "Not installed")

    def test_failed_key_or_fetch_are_review_not_current(self):
        rows = [{"name": "A", "status": x} for x in
                ("unknown", "error", "manual", "no_key", "bogus")]
        grouping = grouped_updates(self.recipe, rows)
        self.assertEqual(len(grouping["review"]), 5)
        self.assertFalse(grouping["current"])

    def test_github_rate_limit_is_explicit_review_not_failed_install(self):
        records = [{"name": "VHVR", "status": "error",
                    "detail": "Couldn't check GitHub: GitHub API rate limit reached; retry later.",
                    "page": "https://github.com/org/project/releases"}]
        groups = grouped_updates({"id": "valheim"}, records)
        self.assertEqual(groups["review"][0]["status"], "Rate limited")
        self.assertFalse(groups["current"])
        self.assertFalse(groups["update"])

    def test_empty_and_missing_versions_never_fabricated(self):
        self.assertEqual(sum(map(len, grouped_updates(self.recipe, None).values())), 0)
        result = grouped_updates(self.recipe, [{"name": "A", "status": "update"}])
        self.assertEqual(result["update"][0]["installed"], "—")
        self.assertEqual(result["update"][0]["latest"], "—")

    def test_safe_source_links_only_https_without_credentials(self):
        for candidate in ("javascript:alert(1)", "file:///etc/passwd",
                          "http://example.com", "https://user:password@host/test",
                          "", "ftp://example.com/file"):
            self.assertEqual(safe_source_url(candidate), "")
        self.assertEqual(
            safe_source_url("https://www.nexusmods.com/cyberpunk2077/mods/107"),
            "https://www.nexusmods.com/cyberpunk2077/mods/107")
        self.assertEqual(
            safe_source_url("https://github.com/org/project/releases"),
            "https://github.com/org/project/releases")

    def test_guide_has_short_summary_only_in_actual_gui_mode(self):
        before = hub.details_html(self.recipe, sample_updates())
        compact = hub.details_html(self.recipe, sample_updates(), compact_updates=True)
        self.assertIn("Update status", before)
        self.assertIn("Cyber Engine Tweaks", before)
        self.assertIn("See the <b>Updates</b> tab", compact)
        self.assertNotIn("<li><b>Cyber Engine Tweaks", compact)
        self.assertIn("4 update(s) available", compact)
        self.assertIn("1 require manual review", compact)


class QtModUpdatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.recipe = hub.load_recipes()["cyberpunk-2077"]
        self.page = ModUpdatesPage()
        self.page.show()
        self.app.processEvents()
        self.addCleanup(self.dispose_page)

    def dispose_page(self):
        self.page.close()
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_native_tables_have_correct_counts(self):
        self.page.set_recipe(self.recipe, sample_updates())
        self.app.processEvents()
        self.assertIn("4 updates available", self.page.summary.text())
        self.assertEqual(self.page.sections["update"].table.rowCount(), 4)
        self.assertEqual(self.page.sections["review"].table.rowCount(), 1)
        self.assertEqual(self.page.sections["later"].table.rowCount(), 1)
        self.assertEqual(self.page.sections["current"].table.rowCount(), 9)
        self.assertFalse(self.page.sections["current"].table.isVisible())
        self.assertEqual(self.page.sections["update"].table.item(0, 1).text(), "1.37.1")
        self.assertEqual(self.page.sections["update"].table.item(0, 2).text(), "1.38.1")
        self.assertEqual(self.page.sections["review"].table.item(0, 1).text(), "2.31")
        self.assertEqual(self.page.sections["review"].table.item(0, 2).text(), "2.5")

    def test_status_column_uses_original_brand_colors_and_icons(self):
        self.page.set_recipe(self.recipe, sample_updates())
        updates = self.page.sections["update"].table.item(0, 3)
        review = self.page.sections["review"].table.item(0, 3)
        current = self.page.sections["current"].table.item(0, 3)
        later = self.page.sections["later"].table.item(0, 3)
        self.assertTrue(updates.text().startswith("↑"))
        self.assertEqual(updates.foreground().color().name().lower(), "#ffd21a")
        self.assertTrue(review.text().startswith("!"))
        self.assertEqual(review.foreground().color().name().lower(), "#ffd21a")
        self.assertTrue(current.text().startswith("✓"))
        self.assertEqual(current.foreground().color().name().lower(), "#4fe39a")
        self.assertIn("Install later", later.text())

    def test_rate_limit_warning_appears_and_clears_between_games(self):
        error = [{"name": "VHVR", "status": "error",
                  "detail": "Couldn't check GitHub: GitHub API rate limit reached; retry later.",
                  "page": "https://github.com/org/project/releases"}]
        self.page.set_recipe({"id": "valheim", "name": "Valheim"}, error)
        self.app.processEvents()
        self.assertTrue(self.page.github_notice.isVisible())
        self.assertIn("temporary online lookup", self.page.github_notice.text())
        self.assertIn("no mod files were changed", self.page.github_notice.text())
        self.assertEqual(self.page.sections["review"].table.item(0, 3).text(),
                         "!  Rate limited")
        self.page.set_recipe(self.recipe, sample_updates())
        self.app.processEvents()
        self.assertFalse(self.page.github_notice.isVisible())

    def test_up_to_date_expands_and_collapses_on_click(self):
        self.page.set_recipe(self.recipe, sample_updates())
        section = self.page.sections["current"]
        self.assertFalse(section.table.isVisible())
        section.disclosure.click()
        self.app.processEvents()
        self.assertTrue(section.table.isVisible())
        self.assertIn("Up to date (9)", section.disclosure.text())
        section.disclosure.click()
        self.app.processEvents()
        self.assertFalse(section.table.isVisible())

    def test_rechecking_same_game_preserves_user_expand_choice(self):
        self.page.set_recipe(self.recipe, sample_updates())
        section = self.page.sections["current"]
        section.disclosure.click()
        self.page.set_recipe(self.recipe, sample_updates())
        self.app.processEvents()
        self.assertTrue(section.table.isVisible())
        self.page.set_recipe({"id": "valheim", "name": "Valheim"}, [
            {"name": "VHVR", "status": "current", "page": "https://github.com/org/a"}])
        self.page.set_recipe(self.recipe, sample_updates())
        self.app.processEvents()
        self.assertFalse(section.table.isVisible())

    def test_refresh_is_signal_only_no_install_action(self):
        calls = []
        self.page.refresh_requested.connect(lambda: calls.append("check"))
        self.page.refresh_button.click()
        self.assertEqual(calls, ["check"])
        self.page.set_checking(True)
        self.assertFalse(self.page.refresh_button.isEnabled())
        self.page.refresh_button.click()
        self.assertEqual(calls, ["check"])
        self.page.set_checking(False)
        self.assertTrue(self.page.refresh_button.isEnabled())

    def test_switching_games_does_not_leave_ghost_source_buttons(self):
        self.page.set_recipe(self.recipe, sample_updates())
        table = self.page.sections["update"].table
        self.assertEqual(table.rowCount(), 4)
        self.page.set_recipe({"id": "hogwarts-legacy", "name": "Hogwarts Legacy"}, [
            {"name": "HL_UEVR", "status": "update",
             "page": "https://github.com/jbusfield/HL_UEVR/releases",
             "detail": "Update available"}])
        self.app.processEvents()
        self.assertEqual(table.rowCount(), 1)
        self.assertEqual(
            len([button for button in table.findChildren(QPushButton)
                 if button.isVisible()]), 1)
        self.assertEqual(table.cellWidget(0, 4).text(), "Open source")
        self.assertEqual(table.item(0, 0).text(), "HL_UEVR")

    def test_source_buttons_use_web_url_and_never_install(self):
        self.page.set_recipe(self.recipe, sample_updates())
        table = self.page.sections["update"].table
        btn = table.cellWidget(0, 4)
        self.assertIsInstance(btn, QPushButton)
        with mock.patch(
                "vrhub.mod_updates_gui.QDesktopServices.openUrl",
                return_value=True) as open_url:
            btn.click()
            self.assertEqual(open_url.call_count, 1)
            self.assertEqual(
                open_url.call_args.args[0].toString(),
                "https://www.nexusmods.com/cyberpunk2077/mods/107")

    def test_legacy_single_github_release_has_no_fake_local_version(self):
        self.page.set_recipe({"id": "valheim", "name": "Valheim"}, [
            {"name": "VHVR", "status": "current",
             "latest_version": "v0.11.2",
             "page": "https://github.com/org/project/releases"}])
        self.assertEqual(self.page.sections["current"].table.item(0, 1).text(), "—")
        self.assertEqual(self.page.sections["current"].table.item(0, 2).text(), "v0.11.2")


class HubIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patches = [
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.win = HubWindow()
        self.win.show()
        self.app.processEvents()
        self.addCleanup(self.win.close)

    def select_cyberpunk(self):
        idx = next(i for i, v in enumerate(self.win.rows)
                   if v["recipe"]["id"] == "cyberpunk-2077")
        self.win.select_launcher_game(idx)

    def test_fourth_tab_preserves_existing_tab_indices(self):
        self.assertEqual(
            [self.win.game_details_tabs.tabText(i)
             for i in range(self.win.game_details_tabs.count())],
            ["Overview", "Updates", "Install / Update", "Rollback",
             "Compatibility", "Controller Bindings", "Setup Guide"])
        self.assertIs(self.win.game_details_tabs.widget(self.win.game_details_tabs.indexOf(self.win.mod_updates)), self.win.mod_updates)

    def test_game_switch_refreshes_mod_update_tab(self):
        self.select_cyberpunk()
        self.win.update_results["cyberpunk-2077"] = sample_updates()
        self.win.show_details()
        self.assertEqual(self.win.game_details_tabs.tabText(self.win.game_details_tabs.indexOf(self.win.mod_updates)), "Updates (4)")
        self.assertEqual(self.win.mod_updates.sections["update"].table.rowCount(), 4)
        self.assertEqual(self.win.mod_updates.sections["current"].table.rowCount(), 9)
        self.assertNotIn("Cyber Engine Tweaks —", self.win.details.toPlainText())
        self.win.select_launcher_game(next(
            i for i, v in enumerate(self.win.rows) if v["recipe"]["id"] == "valheim"))
        self.assertEqual(self.win.game_details_tabs.tabText(self.win.game_details_tabs.indexOf(self.win.mod_updates)), "Updates")
        self.assertEqual(self.win.mod_updates.sections["update"].table.rowCount(), 0)

    def test_update_worker_controls_are_synchronized(self):
        self.assertEqual(self.win.mod_updates.refresh_button.text(), "Refresh update status")
        # Mocked check call is still exactly the original HubWindow method.
        calls_before = HubWindow.check_updates.call_count
        self.win.mod_updates.refresh_button.click()
        self.assertEqual(HubWindow.check_updates.call_count, calls_before + 1)
        self.win.mod_updates.set_checking(True)
        self.assertFalse(self.win.mod_updates.refresh_button.isEnabled())
        self.win.mod_updates.set_checking(False)
        self.assertTrue(self.win.mod_updates.refresh_button.isEnabled())

    def test_expanding_nine_current_mods_does_not_force_window_growth(self):
        self.select_cyberpunk()
        self.win.update_results["cyberpunk-2077"] = sample_updates()
        self.win.show_details()
        self.win.game_details_tabs.setCurrentIndex(self.win.game_details_tabs.indexOf(self.win.mod_updates))
        for width, height in ((1630, 1060), (920, 600)):
            with self.subTest(dimensions=(width, height)):
                self.win.resize(width, height)
                self.app.processEvents()
                self.win.mod_updates.sections["current"].disclosure.setChecked(True)
                self.win.mod_updates.sections["current"].table.show()
                self.app.processEvents()
                self.assertEqual((self.win.width(), self.win.height()), (width, height))
                self.assertEqual(
                    self.win.game_page_scroll.horizontalScrollBar().maximum(), 0)
                self.assertEqual(
                    self.win.mod_updates.sections["current"].table.rowCount(), 9)

    def test_original_default_dimensions_and_brand_are_preserved(self):
        from vrhub.gui import preferred_launcher_size
        self.assertEqual(preferred_launcher_size(2327, 1309), (1630, 1060))
        self.assertIn("#FFD21A", self.win.styleSheet())
        self.assertIn("#23B7FF", self.win.styleSheet())


if __name__ == "__main__":
    unittest.main()
