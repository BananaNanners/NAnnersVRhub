# SPDX-License-Identifier: GPL-3.0-only
"""Regression coverage for per-game folder persistence and release-only review."""
import copy
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from vrhub import hub, archive_scans, archive_releases, download_planner as planner
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.pinned_release_review import build_review, ReviewDialog
from tests.test_archive_releases import release


class PersistenceActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.down = self.root / "Downloads"
        self.down.mkdir()
        self.organized = self.down / "Organized/Archive-Library/VR-Mods"
        self.organized.mkdir(parents=True)
        self.other = self.root / "custom"
        self.other.mkdir()
        for patch in (
            mock.patch.object(Path, "home", return_value=self.root),
            mock.patch.object(planner, "preferences_file", return_value=self.root / "prefs.json"),
            mock.patch.object(archive_scans, "snapshot_file", return_value=self.root / "scans.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.page = self.page_instance()

    def page_instance(self):
        page = GuidedDownloadsPage()
        page.show()
        self.addCleanup(page.close)
        return page

    def recipe(self, rid):
        return copy.deepcopy(hub.load_recipes()[rid])

    def select_folder(self, page, recipe, path, *, shared=False):
        page.set_recipe(recipe)
        with mock.patch("vrhub.downloads_gui.QFileDialog.getExistingDirectory", return_value=str(path)):
            page._sync_folder_actions()
            page.folder_menu_actions[page.set_global if shared else page.set_game].trigger()
        self.app.processEvents()

    def put(self, folder, name, data=b"fixture"):
        path = folder / name
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("example.dll", data)
        return path

    def test_downloads_default_even_when_organized_exists(self):
        self.assertEqual(planner.default_library(), self.down)
        self.assertEqual(planner.folder_for(self.recipe("doom-2016-gog"))[0], self.down)
        self.assertFalse(planner.preferences_file().exists())

    def test_menu_choices_survive_reopened_pages_and_shared_reset(self):
        a = self.recipe("fatekeeper")
        b = self.recipe("ready-or-not")
        self.select_folder(self.page, a, self.organized)
        self.select_folder(self.page, b, self.other)
        self.assertEqual(planner.load_preferences()["games"], {a["id"]:str(self.organized), b["id"]:str(self.other)})
        reopened = self.page_instance()
        for r, folder in ((a,self.organized),(b,self.other)):
            reopened.set_recipe(r)
            self.assertIn(f"Additional folder (Per-game override): {folder}", reopened.location.text())
        self.select_folder(reopened, b, self.down, shared=True)
        reopened._sync_folder_actions()
        reopened.folder_menu_actions[reopened.reset_global].trigger()
        self.assertEqual(planner.folder_for(a)[0], self.organized)
        self.assertEqual(planner.folder_for(b)[0], self.other)
        self.assertIsNone(planner.load_preferences()["global"])
        reopened._sync_folder_actions()
        reopened.folder_menu_actions[reopened.clear_game].trigger()
        self.assertEqual(planner.folder_for(b)[0], self.down)
        self.assertEqual(planner.folder_for(a)[0], self.organized)

    def test_legacy_scan_retained_inactive_then_explicitly_reused(self):
        a = self.recipe("ready-or-not")
        b = self.recipe("fatekeeper")
        self.put(self.organized,"VRO-6914.zip")
        self.put(self.organized,"UEVR_FK.zip")
        for recipe in (a,b):
            archive_scans.persist(planner.build_plan(recipe,self.organized))
        original = archive_scans.snapshot_file().read_bytes()
        self.page.set_recipe(a)
        self.assertIn("Previous scan retained", self.page.scan_age.text())
        self.assertIsNone(self.page._last_plan)
        self.page._sync_folder_actions()
        self.assertTrue(self.page.saved_folder_action.isVisible())
        self.page.saved_folder_action.trigger()
        # Legacy single-folder history is retained, but cannot authorize a
        # two-folder scan before the new Downloads root is inspected.
        self.assertIn("Previous scan retained", self.page.scan_age.text())
        self.assertIsNone(self.page._last_plan)
        self.assertEqual(original, archive_scans.snapshot_file().read_bytes())
        archive_scans.persist(planner.build_plan(a, planner.scan_folders(a)))
        self.page.set_recipe(a)
        self.assertIn("Saved scan:", self.page.scan_age.text())
        self.assertEqual(self.page._last_plan["rows"][0]["file"], str(self.organized/"VRO-6914.zip"))
        self.assertEqual(len(archive_scans.load_histories()[a["id"]]), 2)
        self.select_folder(self.page,a,self.other)
        self.assertEqual(len(archive_scans.load_histories()[a["id"]]), 2)
        self.assertIsNone(self.page._last_plan)
        next_page = self.page_instance()
        next_page.set_recipe(a)
        self.assertEqual(planner.folder_for(a)[0],self.other)
        self.assertIn("Previous scan retained",next_page.scan_age.text())
        next_page.set_recipe(b)
        self.assertIn("Previous scan retained",next_page.scan_age.text())

    def test_newer_saved_scan_reloaded_across_windows(self):
        recipe = self.recipe("ready-or-not")
        self.page.set_recipe(recipe)
        path = self.put(self.down,"VRO-6914.zip")
        archive_scans.persist(planner.build_plan(recipe,self.down))
        self.page.set_recipe(recipe)
        self.assertEqual(self.page._last_plan["rows"][0]["file"],str(path))

    def test_pinned_set_switches_only_for_official_new_release(self):
        for rid, cid, old_tag, new_tag, name in (
            ("valheim","vhvr","v0.11.2","v0.11.3","vhvr.zip"),
            ("subnautica","submersedvr","0.2.1","0.2.2","SubmersedVR_0.2.2.zip"),
        ):
            with self.subTest(game=rid):
                recipe=self.recipe(rid)
                folder=self.root/rid
                folder.mkdir()
                planner.set_location("game",str(folder),rid)
                for pkg in recipe["packages"]:
                    path=self.put(folder,pkg["id"]+".zip",pkg["id"].encode())
                    pkg["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                old_path=folder/(cid+".zip")
                old_data=old_path.read_bytes()
                old_name="SubmersedVR_0.2.1.zip" if rid=="subnautica" else "vhvr.zip"
                old=release(old_tag,1,old_data,old_name)
                new_path=self.put(folder,name,b"new official content")
                # VHVR's same official asset name happens to be the fixture
                # pin filename; retain the old download under a duplicate name.
                if new_path==old_path:
                    (folder/"vhvr (1).zip").write_bytes(old_data)
                new=release(new_tag,2,new_path.read_bytes(),name)
                catalog=archive_releases.asset_catalog(recipe["archive_releases"][cid],[old,new])
                self.assertTrue(catalog["newer_than_pin"])
                plan=planner.build_plan(recipe,planner.scan_folders(recipe),release_catalogs={cid:catalog})
                row=next(r for r in plan["rows"] if r["id"]==cid)
                self.assertTrue(row["release_review"])
                self.assertEqual(row["status"],"Hash mismatch — do not install")
                self.assertEqual(row["file"],str(new_path))
                archive_scans.persist(plan)
                self.page.set_recipe(recipe)
                self.assertEqual(self.page.install_review_button.text(),"Review installation")
                events=[]
                self.page.install_review_requested.connect(events.append)
                self.page.install_review_button.click()
                self.page.install_review_requested.disconnect(events.append)
                self.assertEqual(events[-1]["route"],"pinned-release-review")
                dialog=ReviewDialog(build_review(recipe,events[-1]["rows"]))
                self.addCleanup(dialog.close)
                self.assertFalse(dialog.apply_button.isEnabled())
                # An unknown replacement is never elevated to review.
                new_path.write_bytes(b"unrecognized")
                for file in folder.glob(cid+"*.zip"):
                    if file != new_path:
                        file.unlink()
                plan=planner.build_plan(recipe,planner.scan_folders(recipe),release_catalogs={cid:catalog})
                archive_scans.persist(plan)
                self.page.set_recipe(recipe)
                self.assertEqual(self.page.install_review_button.text(),"Installation blocked")
                self.assertFalse(self.page.install_review_button.isEnabled())
