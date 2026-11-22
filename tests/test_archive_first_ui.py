# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D2: presentation never grants archive or installation authority."""
import copy
import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub import archive_scans, hub, download_planner as planner
from vrhub.archive_checklist_ui import status_icon
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.install_review_gui import InstallReviewDialog
from vrhub.profile_review_gui import ProfileReviewDialog
from tests.test_install_review_gui import fixture_plan
from vrhub.profile_safety import ProfilePlan


class ArchiveChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "archives"
        self.folder.mkdir()
        for patcher in (
            mock.patch.object(planner, "preferences_file", return_value=self.root / "prefs.json"),
            mock.patch.object(planner, "default_library", return_value=self.folder),
            mock.patch.object(archive_scans, "snapshot_file", return_value=self.root / "scans.json"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.page = GuidedDownloadsPage()
        self.addCleanup(self.page.close)
        self.page.show()
        self.app.processEvents()

    def pinned_recipe(self):
        recipe = copy.deepcopy(hub.load_recipes()["valheim"])
        for pkg in recipe["packages"]:
            path = self.folder / (pkg["id"] + ".zip")
            payload = f"test-{pkg['id']}".encode()
            path.write_bytes(payload)
            pkg["sha256"] = hashlib.sha256(payload).hexdigest()
        return recipe

    def test_archive_first_visual_order_keeps_existing_logical_columns(self):
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        header = self.page.table.horizontalHeader()
        self.assertEqual([header.logicalIndex(i) for i in range(5)], [2,0,3,1,4])
        self.assertEqual(self.page.table.horizontalHeaderItem(2).text(), "Downloaded archive")
        self.assertEqual(self.page.table.rowCount(), 15)
        self.assertIn("Later", self.page.table.item(14,1).text())

    def test_pinned_check_marks_and_complete_existing_batch_request(self):
        recipe = self.pinned_recipe()
        record = archive_scans.persist(planner.build_plan(recipe,self.folder))
        self.page._saved = {recipe["id"]: record}
        before = (self.root / "scans.json").read_bytes()
        self.page.set_recipe(recipe)
        self.assertEqual(self.page.table.rowCount(), len(recipe["packages"]))
        for index in range(self.page.table.rowCount()):
            cell = self.page.table.item(index,3)
            self.assertEqual(cell.text(), "Pinned SHA-256 verified")
            self.assertFalse(cell.icon().isNull())
            self.assertIn("not permission",cell.toolTip())
        self.assertEqual(self.page.install_review_button.text(),
                         f"Review {len(recipe['packages'])} verified archives")
        requests = []
        self.page.install_review_requested.connect(requests.append)
        self.page.install_review_button.click()
        self.assertEqual(requests,[{"game_id": recipe["id"], "archives": [
            row["file"] for row in record["plan"]["rows"]], "origin": "downloads-page"}])
        self.assertEqual((self.root / "scans.json").read_bytes(),before)

    def _scan_fixture(self, rid, names):
        recipe = hub.load_recipes()[rid]
        for name in names:
            (self.folder / name).write_bytes(b"fixture archive")
        record = archive_scans.persist(planner.build_plan(recipe, self.folder))
        self.page._saved[rid] = record
        self.page.set_recipe(recipe)
        return recipe, record

    def test_uevr_profile_and_injector_route_without_extra_picker(self):
        for rid, names in (
            ("fatekeeper", ("UEVR_FK.zip", "SLASHER-Win64-Shipping.zip")),
            ("hogwarts-legacy", ("UEVR.zip", "HogwartsLegacy.zip")),
        ):
            with self.subTest(game=rid):
                recipe, record = self._scan_fixture(rid, names)
                events = []
                self.page.install_review_requested.connect(events.append)
                try:
                    self.page.table.selectRow(1)
                    self.assertEqual(self.page.install_review_button.text(), "Review profile")
                    self.page.install_review_button.click()
                    self.assertEqual(events[-1], {
                        "game_id": rid, "route": "profile",
                        "archives": [record["plan"]["rows"][1]["file"]],
                        "origin": "downloads-page"})
                    self.assertTrue(events[-1]["archives"][0])
                    self.page.table.selectRow(0)
                    self.assertEqual(self.page.install_review_button.text(), "Open Setup Guide")
                    self.page.install_review_button.click()
                    self.assertEqual(events[-1]["route"], "guide")
                    self.assertEqual(events[-1]["archives"], [])
                finally:
                    self.page.install_review_requested.disconnect(events.append)
                for name in names:
                    (self.folder / name).unlink()

    def test_changed_profile_does_not_emit_review_or_fallback(self):
        _, record = self._scan_fixture("fatekeeper", ("SLASHER-Win64-Shipping.zip",))
        self.page.table.selectRow(1)
        path = Path(record["plan"]["rows"][1]["file"])
        path.write_bytes(b"different contents and size")
        events = []
        self.page.install_review_requested.connect(events.append)
        self.page.install_review_button.click()
        self.assertFalse(events)
        self.assertIn("blocked", self.page.folder_action_feedback.text())

    def test_incomplete_pinned_set_does_not_emit_partial_batch(self):
        recipe = self.pinned_recipe()
        (self.folder / "loader.zip").unlink()
        self.page._saved[recipe["id"]] = archive_scans.persist(
            planner.build_plan(recipe, self.folder))
        self.page.set_recipe(recipe)
        events = []
        self.page.install_review_requested.connect(events.append)
        self.page.install_review_button.click()
        self.assertFalse(events)
        self.assertIn("Complete the verified archive set", self.page.folder_action_feedback.text())

    def test_guide_only_and_switching_game_clear_previous_profile_intent(self):
        self._scan_fixture("fatekeeper", ("SLASHER-Win64-Shipping.zip",))
        self.page.table.selectRow(1)
        events = []
        self.page.install_review_requested.connect(events.append)
        for rid in ("skyrim-vr-mgo", "doom-2016-gog"):
            self.page.set_recipe(hub.load_recipes()[rid])
            self.assertEqual(self.page.install_review_button.text(), "Open Setup Guide")
            self.page.install_review_button.click()
            self.assertEqual(events[-1]["game_id"], rid)
            self.assertEqual(events[-1]["route"], "guide")
            self.assertEqual(events[-1]["archives"], [])

    def test_selected_unpinned_mod_routes_to_existing_review(self):
        for rid, filename in (("cyberpunk-2077", "CET-107.zip"),
                              ("ready-or-not", "VRO-6914.zip")):
            _, record = self._scan_fixture(rid, (filename,))
            self.page.table.selectRow(0)
            events = []
            self.page.install_review_requested.connect(events.append)
            self.page._request_install_review()
            request = events[-1]
            self.assertEqual(request["game_id"], rid)
            self.assertEqual(request["archives"], [record["plan"]["rows"][0]["file"]])
            self.assertTrue(request["archives"][0])
            self.assertNotIn("route", request)
            self.page.install_review_requested.disconnect(events.append)

    def _ambiguous_profile(self):
        recipe = hub.load_recipes()["fatekeeper"]
        first = self.folder / "SLASHER-Win64-Shipping.zip"
        second = self.folder / "SLASHER-Win64-Shipping (1).zip"
        first.write_bytes(b"one fixture")
        second.write_bytes(b"different fixture")
        record = archive_scans.persist(planner.build_plan(recipe, self.folder))
        self.page._saved["fatekeeper"] = record
        self.page.set_recipe(recipe)
        self.page.table.selectRow(1)
        self.assertEqual(self.page.install_review_button.text(), "Choose archive")
        self.assertEqual(self.page.table.item(1,3).text(), "Choose archive")
        return record

    def test_ambiguous_profile_cancel_and_explicit_choice(self):
        record = self._ambiguous_profile()
        events = []
        self.page.install_review_requested.connect(events.append)
        before = (self.root / "scans.json").read_bytes()
        with mock.patch("vrhub.downloads_gui.QInputDialog.getItem", return_value=("", False)):
            self.page.install_review_button.click()
        self.assertEqual(events, [])
        with mock.patch("vrhub.downloads_gui.QInputDialog.getItem",
                        side_effect=lambda *args: (args[3][2], True)):
            self.page.install_review_button.click()
        self.assertEqual(events[-1]["archives"],
                         [record["plan"]["rows"][1]["candidates"][1]["file"]])
        self.assertEqual(events[-1]["route"], "profile")
        self.assertEqual((self.root / "scans.json").read_bytes(), before)

    def test_candidate_changed_during_chooser_is_rejected(self):
        record = self._ambiguous_profile()
        events = []
        self.page.install_review_requested.connect(events.append)
        def mutate(*args):
            Path(record["plan"]["rows"][1]["candidates"][1]["file"]).write_bytes(b"changed")
            return args[3][2], True
        with mock.patch("vrhub.downloads_gui.QInputDialog.getItem", side_effect=mutate):
            self.page.install_review_button.click()
        self.assertEqual(events, [])
        self.assertIn("changed", self.page.folder_action_feedback.text().lower())

    def test_release_match_keeps_review_color_and_no_picker(self):
        from vrhub.archive_releases import asset_catalog
        from tests.test_archive_releases import release
        recipe = hub.load_recipes()["fatekeeper"]
        (self.folder / "SLASHER-Win64-Shipping (1).zip").write_bytes(b"old")
        expected = self.folder / "SLASHER-Win64-Shipping (2).zip"
        expected.write_bytes(b"new")
        catalog = asset_catalog(recipe["archive_releases"]["profile"],
                                [release("1.0.0", 1, b"old"), release("v1.0.4", 4, b"new")])
        record = archive_scans.persist(planner.build_plan(
            recipe, self.folder, release_catalogs={"profile": catalog}))
        self.page._saved["fatekeeper"] = record
        self.page.set_recipe(recipe)
        self.page.table.selectRow(1)
        cell = self.page.table.item(1,3)
        self.assertEqual(cell.text(), "v1.0.4 — Latest release matched")
        self.assertEqual(cell.foreground().color().name().upper(), "#FFD21A")
        self.assertIn("compatibility", cell.toolTip())
        self.assertIn("1 official release matches", self.page.summary.text())
        self.assertEqual(self.page.install_review_button.text(), "Review profile")
        events = []
        self.page.install_review_requested.connect(events.append)
        with mock.patch("vrhub.downloads_gui.QInputDialog.getItem") as picker:
            self.page.install_review_button.click()
        picker.assert_not_called()
        self.assertEqual(events[-1]["archives"], [str(expected)])

    def test_changed_recipe_pin_hides_historical_checks_without_rewriting_snapshot(self):
        recipe = self.pinned_recipe()
        record = archive_scans.persist(planner.build_plan(recipe,self.folder))
        self.page._saved = {recipe["id"]: record}
        before = (self.root / "scans.json").read_bytes()
        updated = copy.deepcopy(recipe)
        updated["packages"][0]["sha256"] = "b"*64
        self.page.set_recipe(updated)
        self.assertEqual(self.page.table.item(0,3).text(), "Not checked")
        self.assertIn("Rescan required",self.page.scan_age.text())
        self.assertEqual(self.page.install_review_button.text(), "Review installation")
        self.assertEqual((self.root / "scans.json").read_bytes(),before)

    def test_filename_match_missing_and_changed_never_render_verified(self):
        recipe = hub.load_recipes()["cyberpunk-2077"]
        archive = self.folder / "CET-107.zip"
        archive.write_bytes(b"not pinned")
        record = archive_scans.persist(planner.build_plan(recipe,self.folder))
        self.page._saved = {recipe["id"]: record}
        self.page.set_recipe(recipe)
        possible = self.page.table.item(0,3)
        self.assertEqual(possible.text(),"Possible archive — inspect first")
        self.assertIn("does not establish",possible.toolTip())
        self.assertFalse(possible.icon().isNull())
        self.assertEqual(self.page.table.item(1,3).text(),"Not found locally")
        archive.unlink()
        self.page.set_recipe(recipe)
        self.assertEqual(self.page.table.item(0,3).text(),"Archive changed — rescan required")
        self.assertEqual(self.page.table.item(0,2).text(),"—")

    def test_status_icons_have_distinct_verification_semantics(self):
        from PySide6.QtGui import QColor
        expected = {
            "Pinned SHA-256 verified": "#4FE39A",
            "Possible archive — inspect first": "#FFD21A",
            "Hash mismatch — do not install": "#FF5B50",
            "Hash not verified — do not install": "#FF5B50",
            "Archive changed — rescan required": "#FF5B50",
            "Not found locally": "#A7ADB7",
            "Not checked": "#A7ADB7",
        }
        for status, color in expected.items():
            with self.subTest(status=status):
                target=QColor(color)
                img=status_icon(status).pixmap(20,20).toImage()
                self.assertTrue(any(
                    img.pixelColor(x,y).alpha() >= 250
                    and all(abs(a-b)<=2 for a,b in zip(
                        img.pixelColor(x,y).getRgb()[:3],target.getRgb()[:3]))
                    for x in range(img.width()) for y in range(img.height())))

    def test_archive_review_defaults_to_package_summary_and_preserves_exact_inventory(self):
        plan = replace(fixture_plan(), archives=("/one/A.zip","/two/B.zip"),
                       archive_sha256=("a"*64,"b"*64),package_labels=("B","A"))
        dialog=InstallReviewDialog(plan,allow_install=False)
        self.addCleanup(dialog.close)
        dialog.show();self.app.processEvents()
        self.assertTrue(dialog.archives.isVisible())
        self.assertEqual(dialog.archives.rowCount(),2)
        self.assertEqual(dialog.archives.item(0,0).text(),"A.zip")
        self.assertEqual(dialog.archives.item(1,0).toolTip(),"/two/B.zip")
        self.assertIn("not pinned verification",dialog.archives.item(0,2).toolTip())
        self.assertFalse(dialog.targets.isVisible())
        self.assertTrue(dialog.confirm_targets.isEnabled())
        dialog.manifest_toggle.click();self.app.processEvents()
        self.assertTrue(dialog.targets.isVisible())
        self.assertEqual(dialog.targets.rowCount(),len(plan.target_rows))
        self.assertTrue(dialog.confirm_targets.isEnabled())
        for ack in (dialog.confirm_targets,dialog.confirm_backup,dialog.confirm_closed):
            ack.setChecked(True)
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.manifest_toggle.click();self.app.processEvents()
        self.assertFalse(dialog.targets.isVisible())

    def test_dependency_mapping_uses_digest_not_selection_order(self):
        plan = replace(fixture_plan(), archives=("/one/A.zip","/two/B.zip"),
                       archive_sha256=("a"*64,"b"*64),package_labels=("B","A"))
        recipe = {"id":plan.game_id, "packages":[
            {"name":"B","sha256":"b"*64},{"name":"A","sha256":"a"*64}]}
        dialog=InstallReviewDialog(plan,allow_install=False,recipe=recipe)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.archives.item(0,1).text(),"A")
        self.assertEqual(dialog.archives.item(1,1).text(),"B")
        self.assertTrue(dialog.confirm_targets.isEnabled())
        dialog.confirm_targets.setChecked(True)
        self.assertTrue(dialog.targets.isHidden())
        dialog.manifest_toggle.setChecked(True)
        self.assertTrue(dialog.confirm_targets.isChecked())

    def test_cyberpunk_review_dependency_identified(self):
        recipe=hub.load_recipes()["cyberpunk-2077"]
        plan=replace(fixture_plan(),game_id=recipe["id"],method="gameroot",
                     archives=("/test/CET-107.zip",),
                     package_labels=("Cyber Engine Tweaks",))
        dialog=InstallReviewDialog(plan,allow_install=False,recipe=recipe)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.archives.item(0,1).text(),"Cyber Engine Tweaks")

    def test_hogwarts_upstream_download_link_only_on_matching_recipe(self):
        recipe=hub.load_recipes()["hogwarts-legacy"]
        self.page.set_recipe(recipe)
        self.assertFalse(self.page.upstream_link.isHidden())
        self.assertIn("releases#release-100526UE58_6RefreshUpdate",
                      self.page.upstream_link.text())
        self.assertIn("jbusfield/HL_UEVR",planner.plan_components(recipe)[0]["url"])
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertTrue(self.page.upstream_link.isHidden())
        self.assertEqual(self.page.upstream_link.text(),"")
        self.assertEqual(self.page.table.item(0,0).text(), "UEVR FK — Mod / injector")
        self.assertIn("/tag/1.0.0",
                      self.page.table.cellWidget(0,4).toolTip())
        self.assertEqual(self.page.table.item(1,0).text(), "Fatekeeper — VR profile")
        self.assertIn("/tag/v1.0.4",
                      self.page.table.cellWidget(1,4).toolTip())
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        self.assertTrue(self.page.upstream_link.isHidden())
        self.assertEqual(self.page.upstream_link.text(),"")

    def test_blocked_archive_review_does_not_hide_blocker_in_preview(self):
        dialog=InstallReviewDialog(fixture_plan(blocked=("Overlapping destination",)),
                                   allow_install=False)
        self.addCleanup(dialog.close)
        self.assertIn("BLOCKED",dialog.status.text())
        self.assertIn("Overlapping destination",dialog.notes.toPlainText())
        self.assertFalse(dialog.apply_button.isEnabled())

    def test_profile_summary_hidden_inventory_and_closed_preview_gate(self):
        plan=ProfilePlan("fatekeeper","Fatekeeper","/test/archive.zip","a"*64,
                         "/test/prefix/UnrealVRMod/SLASHER",
                         ("config.txt","plugins/custom.dll"),2,17,5,125,3,
                         True,(),"b"*64)
        dialog=ProfileReviewDialog(plan,allow_install=False)
        self.addCleanup(dialog.close)
        dialog.show();self.app.processEvents()
        self.assertFalse(dialog.table.isVisible())
        self.assertEqual(dialog.archives.item(0,1).text(),"Matching game profile")
        self.assertTrue(dialog.ack.isEnabled())
        dialog.ack.setChecked(True)
        self.assertFalse(dialog.apply_btn.isEnabled())
        dialog.manifest_toggle.click();self.app.processEvents()
        self.assertTrue(dialog.table.isVisible())
        self.assertEqual(dialog.table.rowCount(),len(plan.file_names))
        dialog.ack.setChecked(True)
        self.assertFalse(dialog.apply_btn.isEnabled())
