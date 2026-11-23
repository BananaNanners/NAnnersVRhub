# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-D: contextual actions, no new install/transfer authority."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from vrhub import hub, archive_scans, download_planner as planner
from vrhub.downloads_gui import GuidedDownloadsPage


from tests.fatekeeper_fixtures import recipes as fixture_recipes


class CleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "archives"
        self.folder.mkdir()
        for patch in (
            mock.patch.object(planner, "default_library", return_value=self.folder),
            mock.patch.object(planner, "preferences_file", return_value=self.root / "prefs.json"),
            mock.patch.object(archive_scans, "snapshot_file", return_value=self.root / "scans.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.events = []
        self.page.install_review_requested.connect(self.events.append)

    def recipe(self, rid):
        return copy.deepcopy(fixture_recipes()[rid])

    def scan(self, recipe):
        record = archive_scans.persist(planner.build_plan(recipe, self.folder))
        self.page._saved[recipe["id"]] = record
        self.page.set_recipe(recipe)
        self.app.processEvents()
        return record

    def pinned(self):
        recipe = self.recipe("valheim")
        for package in recipe["packages"]:
            path = self.folder / (package["id"] + ".zip")
            path.write_bytes(package["id"].encode())
            package["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return recipe

    def test_no_scan_one_scan_action_and_deliberate_manual_fallback(self):
        self.page.set_recipe(self.recipe("fatekeeper"))
        self.assertTrue(self.page.scan.isVisible())
        self.assertTrue(self.page.install_review_button.isHidden())
        self.assertEqual(self.page.manual_review_button.text(), "Choose profile manually…")
        self.page.manual_review_button.click()
        self.assertEqual(self.events[-1]["route"], "profile")
        self.assertEqual(self.events[-1]["archives"], [])

    def test_complete_pair_has_no_manual_fallback(self):
        for name in ("UEVR_FK.zip", "SLASHER-Win64-Shipping.zip"):
            (self.folder / name).write_bytes(name.encode())
        self.scan(self.recipe("fatekeeper"))
        self.assertEqual(self.page.install_review_button.text(), "Review installation")
        self.assertTrue(self.page.manual_review_button.isHidden())
        self.assertNotIn("0 mismatched", self.page.summary.text())
        self.assertIn("0 mismatched", self.page.summary.toolTip())
        self.assertTrue(self.page.download_button.isHidden())
        self.assertTrue(self.page.download_cancel.isHidden())
        self.assertTrue(self.page.download_status.isHidden())

    def test_full_pin_set_routes_review_and_hides_download(self):
        recipe = self.pinned()
        record = self.scan(recipe)
        self.assertEqual(self.page.install_review_button.text(), "Install verified dependencies")
        self.assertIn("Nothing changes without confirmation", self.page.install_review_button.toolTip())
        self.page.table.selectRow(0)
        self.assertTrue(self.page.download_button.isHidden())
        self.assertTrue(self.page.manual_review_button.isHidden())
        self.page.install_review_button.click()
        self.assertEqual(self.events[-1]["archives"], [r["file"] for r in record["plan"]["rows"]])

    def test_missing_and_mismatch_fail_closed(self):
        recipe = self.pinned()
        (self.folder / "loader.zip").unlink()
        self.scan(recipe)
        self.assertTrue(self.page.install_review_button.isHidden())
        self.assertTrue(self.page.manual_review_button.isHidden())
        self.assertTrue(self.page.scan.isEnabled())
        (self.folder / "denikson-BepInExPack_Valheim-5.4.2351.zip").write_bytes(b"wrong digest")
        self.scan(recipe)
        self.assertEqual(self.page.install_review_button.text(), "Installation blocked")
        self.assertFalse(self.page.install_review_button.isEnabled())
        self.assertTrue(self.page.manual_review_button.isHidden())
        self.page.install_review_button.click()
        self.assertFalse(self.events)

    def test_stale_pair_only_rescan_no_manual_picker(self):
        for name in ("UEVR_FK.zip", "SLASHER-Win64-Shipping.zip"):
            (self.folder / name).write_bytes(name.encode())
        recipe = self.recipe("fatekeeper")
        self.scan(recipe)
        (self.folder / "UEVR_FK.zip").write_bytes(b"changed")
        self.page.set_recipe(recipe)
        self.assertTrue(self.page.install_review_button.isHidden())
        self.assertTrue(self.page.manual_review_button.isHidden())
        self.assertIn("stale", self.page.guidance.text())
        self.assertTrue(self.page.scan.isEnabled())

    def test_single_detected_archive_no_picker_and_no_row_selection_required(self):
        path = self.folder / "VRO-6914.zip"
        path.write_bytes(b"fixture")
        self.scan(self.recipe("ready-or-not"))
        self.assertEqual(self.page.table.currentRow(), -1)
        self.page.install_review_button.click()
        self.assertEqual(self.events[-1]["archives"], [str(path)])
        self.assertTrue(self.page.manual_review_button.isHidden())

    def test_deliberate_manual_batch_revalidates_scan_before_request(self):
        files = (self.folder / "CET-107.zip", self.folder / "RED4ext-2380.zip")
        for f in files:
            f.write_bytes(f.name.encode())
        recipe = self.recipe("cyberpunk-2077")
        record = self.scan(recipe)
        self.assertGreaterEqual(sum(bool(r["file"]) for r in record["plan"]["rows"]), 2)
        self.assertTrue(self.page.manual_review_button.isVisible())
        files[0].write_bytes(b"changed")
        self.page.manual_review_button.click()
        self.assertFalse(self.events)
        self.assertIn("Rescan", self.page.folder_action_feedback.text())

    def test_only_real_ambiguity_uses_selector(self):
        for name, data in (("UEVR_FK.zip", b"injector"), ("SLASHER-Win64-Shipping.zip", b"one"),
                           ("SLASHER-Win64-Shipping (1).zip", b"two")):
            (self.folder / name).write_bytes(data)
        self.scan(self.recipe("fatekeeper"))
        self.assertEqual(self.page.install_review_button.text(), "Choose archive")
        with mock.patch.object(self.page, "_choose_archive_candidate", return_value=None) as chooser:
            self.page.install_review_button.click()
        chooser.assert_called_once()
        self.assertFalse(self.events)

    def test_guide_only_games_keep_setup_guide(self):
        for rid in ("skyrim-vr-mgo",):
            self.page.set_recipe(self.recipe(rid))
            self.assertEqual(self.page.install_review_button.text(), "Open Setup Guide")
            self.assertTrue(self.page.manual_review_button.isHidden())
            self.page.install_review_button.click()
            self.assertEqual(self.events[-1]["route"], "guide")
