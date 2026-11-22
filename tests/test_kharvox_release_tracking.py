# SPDX-License-Identifier: GPL-3.0-only
"""KHARVOX release metadata is not permission to replace the tested runtime."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from vrhub import hub, archive_releases, archive_scans, download_planner as planner, updates
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.kharvox_archive_review import build_review, ReviewDialog
from vrhub.mod_updates_gui import grouped_updates
from tests.test_archive_releases import release


class KharvoxTrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.recipe = hub.load_recipes()["doom-2016-gog"]
        self.source = self.recipe["archive_releases"]["kharvox"]
        self.folder = self.root / "downloads"
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

    def asset(self, name="KHARVOX-v1.11.zip", tag="v1.1.1", day=1, payload=b"launcher"):
        path = self.folder / name
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("KharvoxLauncher.exe", payload)
            z.writestr("KharvoxLayer.dll", b"layer")
        return path, release(tag, day, path.read_bytes(), name)

    def scan(self, history):
        catalog = archive_releases.asset_catalog(self.source, history)
        plan = planner.build_plan(self.recipe, self.folder, release_catalogs={"kharvox": catalog})
        self.page._saved[self.recipe["id"]] = archive_scans.persist(plan)
        self.page.set_recipe(self.recipe)
        self.app.processEvents()
        return plan["rows"][0]

    def test_names_and_official_digest_only(self):
        old, older = self.asset()
        new, latest = self.asset("KHARVOX-v1.4a.zip","v1.4a", 27, b"new")
        duplicate = self.folder / "KHARVOX-v1.4a (1).zip"
        duplicate.write_bytes(new.read_bytes())
        for name in ("NAnners-KHARVOX-Lab-0.1.6.zip","KHARVOX-v1.4a-source.zip",
                     "KHARVOX-bridge.zip", "KHARVOX-v1.4a.zip.sha256"):
            (self.folder / name).write_bytes(new.read_bytes())
        row = self.scan([older, latest])
        self.assertEqual(row["matches"], 3)
        self.assertEqual(row["release_expected"], "v1.4a")
        self.assertEqual(row["candidates"][0]["tags"], ["v1.4a"])
        self.assertEqual(row["candidates"][0]["copies"], 2)
        self.assertFalse(row["ambiguous"])
        self.assertEqual(row["status"], "Possible archive — inspect first")

    def test_older_release_review_no_picker_and_no_apply(self):
        path, old = self.asset()
        latest = release("v1.4a", 27, b"other", "KHARVOX-v1.4a.zip")
        row = self.scan([old, latest])
        self.assertIn("Older release matched", self.page.table.item(0,3).text())
        self.assertEqual(self.page.install_review_button.text(), "Review installation")
        self.assertTrue(self.page.install_review_button.isEnabled())
        with mock.patch.object(self.page, "_choose_archive_candidate") as picker:
            self.page.install_review_button.click()
        picker.assert_not_called()
        request = self.events[-1]
        self.assertEqual(request["archives"], [str(path)])
        plan = build_review(path, request["evidence"], request["latest"])
        self.assertFalse(plan.tested_archive)
        self.assertEqual(plan.tags, ("v1.1.1",))
        d = ReviewDialog(plan)
        self.addCleanup(d.close)
        self.assertFalse(d.apply_button.isEnabled())
        self.assertIn("COMPATIBILITY BLOCKED", d.compatibility.text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["candidates"][0]["sha256"])

    def test_unknown_missing_and_stale_are_not_install_authority(self):
        self.page.set_recipe(self.recipe)
        self.assertEqual(self.page.install_review_button.text(), "Review installation")
        self.assertFalse(self.page.install_review_button.isEnabled())
        path, old = self.asset()
        self.scan([])
        self.assertFalse(self.page.install_review_button.isEnabled())
        self.scan([old])
        path.write_bytes(b"changed")
        self.page.install_review_button.click()
        self.assertFalse(self.events)
        self.assertIn("Rescan", self.page.folder_action_feedback.text())
        self.page.set_recipe(self.recipe)
        self.assertFalse(self.page.install_review_button.isEnabled())

    def test_review_rejects_wrong_digest_and_unsafe_zip(self):
        path, old = self.asset()
        row = self.scan([old])
        evidence = row["candidates"][0]
        with self.assertRaises(RuntimeError):
            build_review(path, dict(evidence, sha256="0"*64))
        with zipfile.ZipFile(path,"w") as z:
            z.writestr("../KharvoxLauncher.exe", b"bad")
        rec = release("v1.1.1",1,path.read_bytes(),path.name)
        row = self.scan([rec])
        with self.assertRaises(RuntimeError):
            build_review(path,row["candidates"][0])

    def test_latest_update_does_not_infer_installed_version(self):
        fetch = lambda repo: {"tag":"v1.4a", "published":"2026-10-27T07:13:52Z",
                              "url":"https://github.com/CactusVRStudios/KHARVOX/releases/tag/v1.4a"}
        for state in ({}, {self.recipe["id"]: {"installed_at":9999999999}}):
            rows = updates.check_recipe(self.recipe, state, fetch=fetch)
            self.assertEqual(updates.release_count(rows),1)
            self.assertTrue(rows[0]["newer_release"])
            self.assertEqual(rows[0]["tested_version"], "v1.4.0")
            self.assertNotIn("installed_version", rows[0])
            self.assertEqual(grouped_updates(self.recipe, rows)["review"][0]["installed"], "Unknown")
        rows = updates.check_recipe(self.recipe, {}, fetch=lambda repo: {
            "tag":"v1.4.0","published":"2026-10-19T16:34:38Z"})
        self.assertEqual(updates.release_count(rows),0)
        def offline(repo):
            raise OSError("offline")
        rows = updates.check_recipe(self.recipe, {}, fetch=offline)
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(updates.release_count(rows),0)
