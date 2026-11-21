# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A Qt acceptance checks: read-only scanning, new tab and folder settings."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QPushButton

from vrhub import download_planner as planner, archive_scans, hub
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow


class DownloadsQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / "library"
        self.library.mkdir()
        patches = [
            mock.patch.object(planner, "preferences_file", return_value=self.root / "settings.json"),
            mock.patch.object(planner, "default_library", return_value=self.library),
            mock.patch.object(archive_scans, "snapshot_file",
                              return_value=self.root / "scans.json"),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.recipe = hub.load_recipes()["cyberpunk-2077"]
        self.page = GuidedDownloadsPage()
        self.page.resize(1060, 540)
        self.page.show()
        self.app.processEvents()
        self.addCleanup(self.dispose)

    def dispose(self):
        self.page.close()
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def wait_scanned(self):
        end = time.monotonic() + 6
        while self.page.worker is not None and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.015)
        self.app.processEvents()
        self.assertIsNone(self.page.worker, "local inventory should finish bounded")

    def test_download_buttons_have_descriptive_labels_and_hover_help(self):
        self.page.set_recipe(self.recipe)
        texts = [
            self.page.set_global.text(),
            self.page.set_game.text(),
            self.page.clear_game.text(),
            self.page.reset_global.text(),
            self.page.scan.text(),
        ]
        self.assertEqual(texts, [
            "Choose default folder",
            "Choose game folder",
            "Use default folder",
            "Auto-detect default",
            "Scan local archives",
        ])
        for button in (self.page.set_global, self.page.set_game,
                       self.page.clear_game, self.page.reset_global,
                       self.page.scan, self.page.inspect):
            with self.subTest(button=button.text()):
                self.assertNotIn("...", button.text())
                self.assertNotIn("…", button.text())
                lines = button.toolTip().splitlines()
                self.assertGreaterEqual(len(lines), 2)
                self.assertLessEqual(len(lines), 3)
                self.assertTrue(all(len(line) <= 58 for line in lines))
                self.assertLessEqual(
                    max(button.fontMetrics().horizontalAdvance(line)
                        for line in lines), 425)
        self.assertIn("shared archive", self.page.set_global.toolTip())
        self.assertIn("this game only", self.page.set_game.toolTip())
        self.assertIn("Other games", self.page.set_game.toolTip())
        self.assertIn("Unchanged-folder scans", self.page.clear_game.toolTip())
        self.assertIn("SHARED folder", self.page.reset_global.toolTip())
        self.assertIn("game-specific folder stays", self.page.reset_global.toolTip())
        self.assertIn("No archives", self.page.scan.toolTip())
        self.assertIn("nothing is installed", self.page.inspect.toolTip())

    def test_auto_detect_folder_keeps_saved_scan_if_effective_folder_unchanged(self):
        self.page.set_recipe(self.recipe)
        archive = self.library / "CET-107.zip"
        archive.write_bytes(b"sample")
        self.page.scan.click()
        self.wait_scanned()
        before = archive_scans.load_saved()
        self.assertIn("cyberpunk-2077", before)
        self.page.reset_global.click()
        self.app.processEvents()
        after = archive_scans.load_saved()
        self.assertEqual(after, before)
        self.assertIn("Saved scan:", self.page.scan_age.text())
        self.assertIn("1 possible matches", self.page.summary.text())
        self.assertEqual(archive.read_bytes(), b"sample")

    def test_auto_detect_explains_why_game_specific_folder_does_not_change(self):
        default = self.root / "shared-custom"
        custom = self.root / "game-custom"
        default.mkdir()
        custom.mkdir()
        planner.set_location("global", str(default))
        planner.set_location("game", str(custom), self.recipe["id"])
        self.page.set_recipe(self.recipe)
        self.assertIn(f"Shared default (manually selected): {default}",
                      self.page.location.text())
        self.assertIn(f"Current game folder (Per-game override): {custom}",
                      self.page.location.text())
        self.page.reset_global.click()
        self.app.processEvents()
        self.assertIsNone(planner.load_preferences()["global"])
        self.assertEqual(planner.folder_for(self.recipe)[0], custom)
        self.assertIn("Shared default (auto-detected)", self.page.location.text())
        self.assertIn("still uses its custom folder",
                      self.page.folder_action_feedback.text())
        self.assertIn("'Use default folder'",
                      self.page.folder_action_feedback.text())
        self.page.clear_game.click()
        self.app.processEvents()
        self.assertEqual(planner.folder_for(self.recipe)[0], self.library)
        self.assertIn(f"Current game folder (Auto-discovered archive library): {self.library}",
                      self.page.location.text())

    def test_auto_detect_without_custom_shared_folder_explains_no_change(self):
        self.page.set_recipe(self.recipe)
        self.assertFalse((self.root / "settings.json").exists())
        self.page.reset_global.click()
        self.app.processEvents()
        self.assertFalse((self.root / "settings.json").exists())
        self.assertIn("already auto-detected",
                      self.page.folder_action_feedback.text())

    def test_choose_shared_folder_under_game_override_explains_priority(self):
        chosen = self.root / "shared-custom"
        custom = self.root / "game-custom"
        chosen.mkdir()
        custom.mkdir()
        planner.set_location("game", str(custom), self.recipe["id"])
        self.page.set_recipe(self.recipe)
        with mock.patch("vrhub.downloads_gui.QFileDialog.getExistingDirectory",
                        return_value=str(chosen)):
            self.page.set_global.click()
        self.app.processEvents()
        self.assertEqual(planner.folder_for(self.recipe)[0], custom)
        self.assertIn(f"Shared default (manually selected): {chosen}",
                      self.page.location.text())
        self.assertIn("still uses its custom folder",
                      self.page.folder_action_feedback.text())

    def test_native_component_list_has_15_rows_without_scanning(self):
        self.page.set_recipe(self.recipe)
        self.assertEqual(self.page.table.rowCount(), 15)
        self.assertIn("Scan local archives", self.page.scan.text())
        self.assertEqual(self.page.table.item(0, 3).text(), "Not checked")
        self.assertEqual(self.page.table.item(14, 1).text(),
                         "Later: install after first flat launch")
        self.assertFalse((self.root / "settings.json").exists())

    def test_scan_is_read_only_and_detects_probable_archive(self):
        archive = self.library / "CET-107-1-37.zip"
        archive.write_bytes(b"download fixture")
        before = archive.read_bytes()
        self.page.set_recipe(self.recipe)
        self.page.scan.click()
        self.wait_scanned()
        self.assertIn("1 archives found", self.page.summary.text())
        self.assertIn("1 possible matches", self.page.summary.text())
        self.assertIn("Possible archive", self.page.table.item(0, 3).text())
        self.assertEqual(self.page.table.item(0, 2).text(), archive.name)
        self.assertEqual(archive.read_bytes(), before)
        self.assertFalse((self.root / "settings.json").exists())

    def test_switching_games_does_not_preserve_stale_local_candidates(self):
        archive = self.library / "CET-107-1-37.zip"
        archive.write_bytes(b"download fixture")
        self.page.set_recipe(self.recipe)
        self.page.start_scan()
        self.wait_scanned()
        self.page.set_recipe(hub.load_recipes()["subnautica"])
        self.assertEqual(self.page.table.rowCount(), 2)
        self.assertEqual(self.page.table.item(0, 3).text(), "Not checked")
        self.assertNotIn("1 possible matches", self.page.summary.text())

    def test_preference_change_requires_user_click_and_is_scoped(self):
        self.page.set_recipe(self.recipe)
        other = self.root / "custom"
        other.mkdir()
        with mock.patch("vrhub.downloads_gui.QFileDialog.getExistingDirectory",
                        return_value=str(other)):
            self.page.set_game.click()
        self.assertEqual(planner.folder_for(self.recipe)[0], other)
        self.assertIn("Per-game override", self.page.location.text())
        self.page.clear_game.click()
        self.assertEqual(planner.folder_for(self.recipe)[0], self.library)

    def test_reset_global_restores_auto_discovered_library(self):
        self.page.set_recipe(self.recipe)
        other = self.root / "default"
        other.mkdir()
        planner.set_location("global", str(other))
        self.page.set_recipe(self.recipe)
        self.page.reset_global.click()
        self.assertEqual(planner.folder_for(self.recipe)[0], self.library)
        self.assertIsNone(planner.load_preferences()["global"])

    def test_global_folder_is_used_for_other_games_without_override(self):
        self.page.set_recipe(self.recipe)
        other = self.root / "default"
        other.mkdir()
        with mock.patch("vrhub.downloads_gui.QFileDialog.getExistingDirectory",
                        return_value=str(other)):
            self.page.set_global.click()
        self.assertEqual(planner.folder_for(self.recipe)[0], other)
        self.assertEqual(planner.folder_for(hub.load_recipes()["subnautica"])[0], other)

    def test_inspection_signal_emits_only_selected_existing_archive(self):
        archive = self.library / "CET-107.zip"
        archive.write_bytes(b"mock")
        self.page.set_recipe(self.recipe)
        self.page.scan.click()
        self.wait_scanned()
        calls = []
        self.page.inspect_requested.connect(calls.append)
        self.assertFalse(self.page.inspect.isEnabled())
        self.page.table.selectRow(0)
        self.app.processEvents()
        self.assertTrue(self.page.inspect.isEnabled())
        self.page.inspect.click()
        self.assertEqual(calls, [str(archive)])
        archive.unlink()
        self.page._update_inspect_button()
        self.assertFalse(self.page.inspect.isEnabled())

    def test_scanned_game_restored_after_scanning_another_game(self):
        self.library.joinpath("CET-107-1-37.zip").write_bytes(b"cyberpunk owned archive")
        self.page.set_recipe(self.recipe)
        self.page.scan.click()
        self.wait_scanned()
        self.assertEqual(self.page.table.item(0, 3).text(),
                         "Possible archive — inspect first")
        first_timestamp = self.page.scan_age.text()
        self.assertIn("Saved scan:", first_timestamp)
        self.assertIn("snapshot", first_timestamp)
        valheim = hub.load_recipes()["valheim"]
        self.page.set_recipe(valheim)
        self.page.scan.click()
        self.wait_scanned()
        self.assertIn("Saved scan:", self.page.scan_age.text())
        self.page.set_recipe(self.recipe)
        self.app.processEvents()
        self.assertEqual(self.page.table.item(0, 3).text(),
                         "Possible archive — inspect first")
        self.assertIn("1 archives found", self.page.summary.text())
        self.assertEqual(self.page.scan_age.text(), first_timestamp)
        self.assertEqual(set(archive_scans.load_saved()),
                         {"cyberpunk-2077", "valheim"})

    def test_scans_persist_across_new_page_instance(self):
        self.library.joinpath("CET-107.zip").write_bytes(b"archive")
        self.page.set_recipe(self.recipe)
        self.page.scan.click()
        self.wait_scanned()
        self.assertEqual(self.page.table.item(0, 3).text(),
                         "Possible archive — inspect first")
        second = GuidedDownloadsPage()
        self.addCleanup(second.close)
        second.set_recipe(self.recipe)
        self.app.processEvents()
        self.assertEqual(second.table.item(0, 3).text(),
                         "Possible archive — inspect first")
        self.assertIn("Saved scan:", second.scan_age.text())

    def test_archived_game_result_persisted_when_worker_finishes_after_switch(self):
        self.library.joinpath("CET-107.zip").write_bytes(b"archive")
        self.page.set_recipe(self.recipe)
        self.page.start_scan()
        valheim = hub.load_recipes()["valheim"]
        self.page.set_recipe(valheim)
        self.wait_scanned()
        self.assertEqual(self.page.recipe["id"], "valheim")
        self.assertEqual(self.page.table.rowCount(), 2)
        self.assertNotIn("1 possible matches", self.page.summary.text())
        self.page.set_recipe(self.recipe)
        self.assertIn("1 possible matches", self.page.summary.text())
        self.assertEqual(self.page.table.item(0, 2).text(), "CET-107.zip")

    def test_archived_file_change_blocks_old_verification_in_gui(self):
        import hashlib
        payload = b"a pinned file for test"
        item = {"id": "testgame", "name": "Test", "method": "bepinex",
                "packages": [{"id": "loader", "name": "Test package",
                              "sha256": hashlib.sha256(payload).hexdigest()}]}
        archive = self.library / "BepInEx-loader.zip"
        archive.write_bytes(payload)
        self.page.set_recipe(item)
        self.page.scan.click()
        self.wait_scanned()
        self.assertEqual(self.page.table.item(0, 3).text(),
                         "Pinned SHA-256 verified")
        self.page.set_recipe(self.recipe)
        archive.write_bytes(b"archive modified after verification")
        self.page.set_recipe(item)
        self.app.processEvents()
        self.assertEqual(self.page.table.item(0, 3).text(),
                         "Archive changed — rescan required")
        self.assertIn("1 changed", self.page.summary.text())
        self.assertFalse(self.page.inspect.isEnabled())

    def test_changing_one_folder_invalidates_only_its_saved_scan(self):
        archive = self.library / "CET-107.zip"
        archive.write_bytes(b"archive")
        self.page.set_recipe(self.recipe)
        self.page.scan.click()
        self.wait_scanned()
        valheim = hub.load_recipes()["valheim"]
        self.page.set_recipe(valheim)
        self.page.scan.click()
        self.wait_scanned()
        self.assertEqual(len(archive_scans.load_saved()), 2)
        self.page.set_recipe(self.recipe)
        other = self.root / "other-archives"
        other.mkdir()
        with mock.patch("vrhub.downloads_gui.QFileDialog.getExistingDirectory",
                        return_value=str(other)):
            self.page.set_game.click()
        self.assertEqual(
            set(archive_scans.load_saved()), {"valheim"})
        self.assertEqual(self.page.table.item(0, 3).text(), "Not checked")
        self.page.set_recipe(valheim)
        self.assertIn("Saved scan:", self.page.scan_age.text())

    def test_source_button_opens_source_page_on_explicit_click(self):
        self.page.set_recipe(self.recipe)
        button = self.page.table.cellWidget(0, 4)
        self.assertIsInstance(button, QPushButton)
        with mock.patch("vrhub.downloads_gui.QDesktopServices.openUrl",
                        return_value=True) as url:
            button.click()
            self.assertEqual(url.call_count, 1)
            self.assertEqual(url.call_args.args[0].toString(),
                             "https://www.nexusmods.com/cyberpunk2077/mods/107")


class DownloadsHubWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / "library"
        self.library.mkdir()
        for patcher in (
            mock.patch.object(planner, "preferences_file",
                              return_value=self.root / "folders.json"),
            mock.patch.object(planner, "default_library", return_value=self.library),
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
        self.addCleanup(self.dispose)

    def dispose(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_install_page_is_preserved_in_seven_tab_navigation(self):
        self.assertEqual(
            [self.window.game_details_tabs.tabText(i)
             for i in range(self.window.game_details_tabs.count())],
            ["Overview", "Mod Updates", "Install / Update", "Rollback",
             "Compatibility", "Controller Bindings", "Setup Guide"])
        self.assertIs(self.window.game_details_tabs.widget(2), self.window.downloads)
        self.assertEqual(self.window.sidebar.game_list.count(), 9)

    def test_existing_installer_file_picker_starts_at_selected_directory(self):
        chosen = self.root / "new-default"
        chosen.mkdir()
        planner.set_location("global", str(chosen))
        with mock.patch("vrhub.gui.QFileDialog.getOpenFileNames",
                        return_value=([], "")) as picker:
            self.window._pick_many("Choose mod files")
        self.assertEqual(picker.call_args.args[2], str(chosen))
        with mock.patch("vrhub.gui.QFileDialog.getOpenFileName",
                        return_value=("", "")) as picker:
            self.window._pick("Choose profile")
        self.assertEqual(picker.call_args.args[2], str(chosen))

    def test_game_switch_and_layout_are_unchanged(self):
        from vrhub.gui import preferred_launcher_size
        self.assertEqual(preferred_launcher_size(2327, 1309), (1630, 1060))
        for rid in ("valheim", "cyberpunk-2077", "fatekeeper"):
            i = next(i for i, row in enumerate(self.window.rows)
                     if row["recipe"]["id"] == rid)
            self.window.sidebar.game_list.setCurrentRow(i)
            self.app.processEvents()
            self.assertEqual(self.window.downloads.recipe["id"], rid)
        for size in ((1630, 1060), (920, 600), (850, 560)):
            self.window.resize(*size)
            self.app.processEvents()
            self.assertEqual((self.window.width(), self.window.height()), size)
            self.assertEqual(
                self.window.game_page_scroll.horizontalScrollBar().maximum(), 0)
        self.assertIn("#FFD21A", self.window.styleSheet())
        self.assertIn("#23B7FF", self.window.styleSheet())

    def test_window_close_is_guarded_while_local_scan_thread_runs(self):
        active = mock.Mock()
        active.isRunning.return_value = True
        with mock.patch.object(self.window.downloads, "worker", active):
            self.window.close()
            self.assertTrue(self.window.isVisible())
        self.window.close_when_idle()
        self.app.processEvents()
        self.assertFalse(self.window.isVisible())

    def test_plan_inspection_uses_existing_inspector_and_never_installs(self):
        index = next(i for i, row in enumerate(self.window.rows)
                     if row["recipe"]["id"] == "cyberpunk-2077")
        self.window.sidebar.game_list.setCurrentRow(index)
        archive = self.root / "CET-107.zip"
        archive.write_bytes(b"dummy")
        report = {"archive": archive.name, "archive_files": 1, "install_files": 1,
                  "component": "CET", "nexus_mod": 107, "roots": {},
                  "sample": [], "required_files": []}
        with mock.patch("vrhub.gui.hub.inspect_archive", return_value=report) as inspect, \
             mock.patch("vrhub.gui.hub.inspect_text", return_value="Read-only inspection"), \
             mock.patch("vrhub.gui.hub.install_many") as install, \
             mock.patch("vrhub.gui.QMessageBox.information") as info:
            self.window.inspect_planned_archive(str(archive))
        inspect.assert_called_once()
        install.assert_not_called()
        info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
