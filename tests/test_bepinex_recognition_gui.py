# SPDX-License-Identifier: GPL-3.0-only
"""Exercise the existing Verify installed files control on disposable games."""
import unittest
import time
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from tests import test_subnautica, test_valheim
from tests.test_bepinex_recognition import RecognitionCases
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub import bepinex_recognition, hub


class GuiCases:
    setUp = RecognitionCases.setUp
    snapshot = RecognitionCases.snapshot

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def dispose(self, page):
        page.close()
        self.wait(page)
        page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def page(self):
        root = self.f.fixture.home
        for name, value in (("vrhub.download_planner.preferences_file", root/"prefs.json"),
                            ("vrhub.download_planner.default_library", root),
                            ("vrhub.archive_scans.snapshot_file", root/"scans.json")):
            self.enterContext(patch(name, return_value=value))
        page = GuidedDownloadsPage()
        self.addCleanup(self.dispose, page)
        page.show()
        page.set_recipe(self.recipe)
        return page

    def rows(self):
        return [dict(id=p["id"], sha256=p["sha256"], file=str(a),
                     status="Pinned SHA-256 verified")
                for p,a in zip(self.recipe["packages"],self.archives)]

    def wait(self,page):
        for _ in range(500):
            if page.integrity_worker is None:
                break
            self.app.processEvents()
            time.sleep(0.01)
        self.assertIsNone(page.integrity_worker)

    def test_verify_existing_button_and_changed_files(self):
        self.f.install()
        page=self.page()
        with patch.object(page,"_fresh_review_rows",return_value=self.rows()):
            before=self.snapshot()
            action=page.install_review_button.text()
            page.integrity_button.click()
            self.wait(page)
            self.assertIn("Pinned bytes match",page.integrity_status.text())
            self.assertIn("Historical record integrity (separate)",page.integrity_status.text())
            self.assertEqual(page._integrity_result["bepinex_recognition"]["root"],str(self.game.resolve()))
            self.assertEqual(page._integrity_result["status"],"Verified")
            self.assertIn("Repair and update are not authorized",page.integrity_status.text())
            self.assertIsNone(page.recognition_result)
            self.assertEqual(action,page.install_review_button.text())
            self.assertEqual(before,self.snapshot())
            (self.game/"winhttp.dll").write_bytes(b"modified")
            (self.game/"BepInEx/config/BepInEx.cfg").write_bytes(b"settings")
            (self.game/"BepInEx/core/BepInEx.dll").unlink()
            before=self.snapshot()
            page.integrity_button.click()
            self.wait(page)
            self.assertIn("1 missing, 1 different, 1 modified settings",page.integrity_status.text())
            self.assertIn("winhttp.dll",page.integrity_details.toPlainText())
            self.assertIn("modified settings",page.integrity_details.toPlainText())
            self.assertEqual(before,self.snapshot())
            self.assertEqual(action,page.install_review_button.text())
        page.set_recipe(self.recipe)
        self.assertIsNone(page._integrity_result)
        self.assertIn("not checked",page.integrity_status.text())

    def test_ambiguous_archive_and_game_switch(self):
        page=self.page()
        rows=self.rows()
        rows[0]["ambiguous"]=True
        with patch.object(page,"_fresh_review_rows",return_value=rows):
            page.integrity_button.click()
            self.wait(page)
        self.assertIn("Current dependency check: Unknown",page.integrity_status.text())
        self.assertIn("Scan both verified",page.integrity_status.text())
        page.set_recipe(hub.load_recipes()["elden-ring"])
        self.assertIsNone(page._integrity_result)
        self.assertIn("not checked",page.integrity_status.text())

    def test_stale_or_incomplete_selection_rejected(self):
        rows=self.rows()
        self.assertEqual(bepinex_recognition.archives_from_rows(self.recipe,rows),tuple(self.archives))
        for key,value in (("sha256","bad"),("candidate_incomplete",True),("status","Hash mismatch — do not install")):
            changed=[dict(r) for r in rows]
            changed[0][key]=value
            self.assertEqual(bepinex_recognition.archives_from_rows(self.recipe,changed),())
        self.assertEqual(bepinex_recognition.archives_from_rows(self.recipe,rows[:1]),())


class SubnauticaGui(GuiCases,unittest.TestCase):
    fixture_class=test_subnautica.SubnauticaTests


class ValheimGui(GuiCases,unittest.TestCase):
    fixture_class=test_valheim.ValheimTests
