# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-Y: default gamer flow and original install-safety routing."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub import hub, archive_scans, download_planner as planner
from vrhub.downloads_gui import GuidedDownloadsPage


class PlayerFirstInstallPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nanners-dev5d3y-unit-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root/"downloads"
        self.folder.mkdir()
        for x in (
            mock.patch.object(planner,"default_library",return_value=self.folder),
            mock.patch.object(planner,"preferences_file",return_value=self.root/"prefs.json"),
            mock.patch.object(archive_scans,"snapshot_file",return_value=self.root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
        ):
            x.start()
            self.addCleanup(x.stop)
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.events=[]
        self.page.install_review_requested.connect(self.events.append)

    def scan(self, recipe):
        archive_scans.persist(planner.build_plan(recipe, self.folder))
        self.page.set_recipe(recipe)
        self.app.processEvents()

    def test_all_game_profiles_reuse_one_early_guarded_review_button(self):
        for rid, recipe in hub.load_recipes().items():
            with self.subTest(game=rid):
                self.page.set_recipe(recipe)
                self.assertLess(
                    self.page.layout().indexOf(self.page.review_actions),
                    self.page.layout().indexOf(self.page.table))
                self.assertLess(
                    self.page.layout().indexOf(self.page.backup_safety_status),
                    self.page.layout().indexOf(self.page.review_actions))
                self.assertLess(
                    self.page.layout().indexOf(self.page.review_actions),
                    self.page.layout().indexOf(self.page.scan_age))
                self.assertTrue(self.page.scan.isVisible())
                self.assertFalse(self.page.comparison_panel.isVisible())
                self.assertEqual(self.page.install_review_button.text(),
                                 self.page._primary_action()[1])

    def test_versions_not_shown_in_install_even_when_advanced_opens(self):
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        self.assertIn("Advanced diagnostics",self.page.comparison_toggle.text())
        self.assertNotIn("Compare versions",self.page.comparison_toggle.text())
        self.page.comparison_toggle.click()
        self.assertTrue(self.page.comparison_panel.isVisible())
        self.assertFalse(self.page.comparison_table.isVisible())
        self.assertFalse(self.page.comparison_summary.isVisible())
        self.assertFalse(self.page.readiness_summary.isVisible())
        self.assertTrue(self.page.safety_button.isVisible())
        self.assertFalse(self.page.safety_details.isVisible())

    def test_advanced_is_explicit_and_does_not_start_safety_worker(self):
        with mock.patch("vrhub.preupdate_safety.review",
                        side_effect=AssertionError("safety must be on demand")):
            self.page.set_recipe(hub.load_recipes()["valheim"])
            self.page.comparison_toggle.click()
            self.page.set_online_results([])
            self.assertIsNone(self.page.safety_worker)
            self.assertIsNone(self.page._safety_result)

    def test_original_verified_bepinex_review_route_unchanged(self):
        recipe = copy.deepcopy(hub.load_recipes()["valheim"])
        for package in recipe["packages"]:
            data = package["id"].encode()
            file = self.folder / (package["id"] + ".zip")
            file.write_bytes(data)
            package["sha256"] = hashlib.sha256(data).hexdigest()
        self.scan(recipe)
        self.assertEqual(self.page.install_review_button.text(),
                         "Install verified dependencies")
        self.page.install_review_button.click()
        self.assertEqual(len(self.events),1)
        self.assertEqual(self.events[0]["game_id"],"valheim")
        self.assertEqual(len(self.events[0]["archives"]),2)
        self.assertTrue(all(Path(a).is_file() for a in self.events[0]["archives"]))

    def test_stale_or_missing_dependencies_still_have_no_review_bypass(self):
        recipe = hub.load_recipes()["ready-or-not"]
        self.page.set_recipe(recipe)
        self.assertTrue(self.page.install_review_button.isHidden())
        self.page.install_review_button.click()
        self.assertEqual(self.events, [])
        self.assertTrue(self.page.scan.isEnabled())
        name = self.folder / "VRO-6914.zip"
        name.write_bytes(b"temporary, invented ZIP")
        self.scan(recipe)
        self.assertFalse(self.page.install_review_button.isHidden())
        name.write_bytes(b"archive changed and stale")
        self.page.install_review_button.click()
        self.assertFalse(self.events)
        self.assertIn("rescan",self.page.folder_action_feedback.text().lower())

    def test_updates_are_separate_from_archive_revision_and_state_reset(self):
        recipe = hub.load_recipes()["fatekeeper"]
        self.page.set_recipe(recipe)
        before=(self.page.install_review_button.text(),
                self.page.install_review_button.isEnabled())
        self.page.set_online_results([{"mod_id": 1, "latest_version":"fictional-v4"}])
        self.assertEqual(
            before,(self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled()))
        self.assertFalse(self.page.comparison_panel.isVisible())
        self.page.set_recipe(hub.load_recipes()["hogwarts-legacy"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
