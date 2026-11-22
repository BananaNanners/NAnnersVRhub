# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-H1 — legacy installation tools without duplicate controls."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtTest import QTest

from vrhub import hub, installed_integrity
from vrhub.app_update_gui import HubUpdateController
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.gui import HubWindow


class ConsolidatedToolsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for patch in (
            mock.patch.object(HubWindow,"scan_setup"),
            mock.patch.object(HubWindow,"check_updates"),
            mock.patch.object(HubUpdateController,"startup"),
            mock.patch.dict("os.environ", {
                "VRHUB_STATE":str(self.root/"isolated-state.json"),
                "VRHUB_NEXUS_KEY_FILE":str(self.root/"isolated-key")}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.win=HubWindow()
        self.win.show()
        self.app.processEvents()
        self.addCleanup(self.win.close)

    def select(self, game):
        index=next(i for i,row in enumerate(self.win.rows)
                   if row["recipe"]["id"]==game)
        self.win.sidebar.game_list.setCurrentRow(index)
        self.win.game_details_tabs.setCurrentWidget(self.win.downloads)
        self.app.processEvents()

    def test_no_more_installation_tools_or_duplicate_visible_actions(self):
        self.select("valheim")
        page=self.win.downloads
        self.assertTrue(self.win.install_tools_toggle.isHidden())
        self.assertFalse(self.win.install_tools_toggle.isVisible())
        self.assertFalse(self.win.install_tools_panel.isVisible())
        self.assertEqual(page.layout().indexOf(self.win.install_tools_panel),-1)
        self.assertTrue(self.win.verify_btn.isHidden())
        self.assertTrue(self.win.inspect_btn.isHidden())
        self.assertIs(page.manual_review_button.parent(),page.review_actions)
        self.assertIs(page.inspect.parent(),page.review_actions)
        self.assertIs(page.download_button.parent(),page)
        self.assertTrue(page.integrity_button.isVisible())
        # No replacement second Verify mods button was introduced.
        self.assertEqual(
            sum(b.isVisible() for b in (
                page.integrity_button,self.win.verify_btn)),1)

    def test_contextual_manual_selection_preserved(self):
        self.select("fatekeeper")
        page=self.win.downloads
        self.assertEqual(page.manual_review_button.text(),"Choose profile manually…")
        self.assertTrue(page.manual_review_button.isVisible())
        self.assertFalse(self.win.install_tools_panel.isVisible())
        self.select("skyrim-vr-mgo")
        self.assertTrue(page.manual_review_button.isHidden())
        self.assertTrue(self.win.install_tools_toggle.isHidden())

    def test_existing_inspector_available_through_archive_menu(self):
        self.select("valheim")
        page=self.win.downloads
        action=self.win.manual_archive_inspect_action
        self.assertTrue(action.isVisible())
        self.assertTrue(action.isEnabled())
        with mock.patch.object(QFileDialog,"getOpenFileName",return_value=("","")) as chooser:
            action.trigger()
        chooser.assert_called_once()
        self.assertTrue(self.win.inspect_btn.isHidden())
        self.select("fatekeeper")
        self.assertFalse(action.isVisible())
        self.select("valheim")
        page.worker=object()
        self.win._sync_inspect_menu()
        self.assertFalse(action.isEnabled())
        page.worker=None

    def test_kharvox_tools_in_compatibility_only(self):
        self.select("doom-2016-gog")
        for button in (self.win.kharvox_folder_btn,
                       self.win.doom_prepare_btn,self.win.doom_import_btn):
            self.assertIs(button.parent(),self.win.more_tools_panel)
            self.assertFalse(button.isHidden())
        self.win.game_details_tabs.setCurrentWidget(self.win.compat_page)
        self.win.more_tools_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.win.kharvox_folder_btn.isVisible())
        self.assertTrue(self.win.doom_prepare_btn.isVisible())
        self.win.more_tools_toggle.click()
        self.select("subnautica")
        self.assertTrue(self.win.kharvox_folder_btn.isHidden())
        self.assertTrue(self.win.doom_import_btn.isHidden())
        self.assertFalse(self.win.install_tools_panel.isVisible())


class ReadinessIntegrityMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        for patch in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scan.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.page=GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.recipe=hub.load_recipes()["valheim"]
        self.page.set_recipe(self.recipe)

    def click_and_finish(self):
        self.page.integrity_button.click()
        for _ in range(300):
            if self.page.integrity_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.integrity_worker)

    def test_on_demand_readiness_is_separate_from_hash_integrity(self):
        with mock.patch.object(installed_integrity,"verify",return_value={
                "game_id":"valheim","status":"Unknown","checked":0,
                "rows":[
                    {"id":"loader","name":"Loader","status":"Unknown",
                     "checked":0,"files":0,"issues":[],
                     "reason":"No recorded file hashes."}
                ]}) as hashes, mock.patch.object(hub,"verify",return_value={
                    "ready":False,"ok":1,"total":2,
                    "required_bad":[{"name":"VHVR","status":"missing"}],
                    "later_bad":[]}) as presence:
            self.assertIn("not checked",self.page.integrity_status.text())
            hashes.assert_not_called()
            presence.assert_not_called()
            before_review = (self.page.install_review_button.text(),
                             self.page.install_review_button.isEnabled())
            self.click_and_finish()
        hashes.assert_called_once()
        presence.assert_called_once()
        self.assertIn("Required mod presence: 1/2 recorded present",
                      self.page.integrity_status.text())
        self.assertIn("presence only; not hash verification",
                      self.page.integrity_status.text())
        self.assertIn("Required mod presence (required): VHVR",
                      self.page.integrity_details.toPlainText())
        self.assertIn("Loader: Unknown",self.page.integrity_details.toPlainText())
        self.assertEqual(
            (self.page.install_review_button.text(),
             self.page.install_review_button.isEnabled()), before_review)

    def test_ready_presence_does_not_imply_sha_verified(self):
        with mock.patch.object(installed_integrity,"verify",return_value={
                "game_id":"valheim","status":"Unknown","checked":0,
                "rows":[]}), mock.patch.object(hub,"verify",return_value={
                    "ready":True,"ok":2,"total":2,"required_bad":[],"later_bad":[]}):
            self.click_and_finish()
        self.assertIn("0 tracked file(s) matched",self.page.integrity_status.text())
        self.assertIn("Required mod presence: 2/2",self.page.integrity_status.text())
        self.assertFalse(self.page.integrity_details.isVisible())

    def test_unavailable_presence_does_not_crash_or_greenlight(self):
        with mock.patch.object(installed_integrity,"verify",return_value={
                "game_id":"valheim","status":"Unknown","checked":0,
                "rows":[]}), mock.patch.object(hub,"verify",
                side_effect=RuntimeError("intentional fixture failure")):
            self.click_and_finish()
        self.assertIn("Required mod presence: unknown",
                      self.page.integrity_status.text())
        self.assertIn("Required mod presence: unknown",
                      self.page.integrity_details.toPlainText())

    def test_old_game_result_does_not_follow_new_game(self):
        with mock.patch.object(installed_integrity,"verify",return_value={
                "game_id":"valheim","status":"Unknown","checked":0,
                "rows":[]}), mock.patch.object(hub,"verify",return_value=None):
            self.click_and_finish()
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertIn("not checked",self.page.integrity_status.text())
        self.assertFalse(self.page.integrity_details.isVisible())
