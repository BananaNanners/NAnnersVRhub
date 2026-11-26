# SPDX-License-Identifier: GPL-3.0-only
"""Existing primary action exercises real read-only update review on fixtures."""
import time
import unittest
import zipfile
from pathlib import Path
from threading import Event
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent
from tests.test_bepinex_recognition_gui import GuiCases
from tests import test_subnautica, test_valheim
from tests.test_archive_releases import release
from vrhub import archive_releases, archive_scans, bepinex, bepinex_update_manifest, download_planner as planner, hub


class Cases:
    setUp=GuiCases.setUp
    snapshot=GuiCases.snapshot
    setUpClass=GuiCases.__dict__["setUpClass"]
    page=GuiCases.page
    dispose=GuiCases.dispose
    wait=GuiCases.wait

    def wait_safety(self,page):
        for _ in range(600):
            self.app.processEvents()
            if page.safety_worker is None:
                break
            time.sleep(.01)
        self.assertIsNone(page.safety_worker)

    def setup_candidate(self):
        self.f.install()
        role="submersedvr" if self.recipe["id"]=="subnautica" else "vhvr"
        old=self.archives[1]
        pkg,members=bepinex.archive_plan(old,self.recipe)
        with zipfile.ZipFile(old) as z:
            data={name:z.read(origin) for origin,name in members.items()}
        changed="BepInEx/plugins/"+("SubmersedVR.dll" if role=="submersedvr" else "ValheimVRMod.dll")
        removed=next(n for n in data if n not in pkg["required_files"])
        added="BepInEx/plugins/update-test.dll"
        del data[removed]
        data[changed]=b"synthetic replacement"
        data[added]=b"synthetic addition"
        filename="SubmersedVR_0.2.2.zip" if role=="submersedvr" else "vhvr.zip"
        tag="0.2.2" if role=="submersedvr" else "v0.11.3"
        source=self.recipe["archive_releases"][role]
        candidate=old.parent/filename
        with zipfile.ZipFile(candidate,"w") as z:
            for n,v in data.items():
                z.writestr(n,v)
        history=[release(source["pinned_tag"],1,old.read_bytes(),filename),
                 release(tag,2,candidate.read_bytes(),filename)]
        self.enterContext(patch.object(archive_releases,"fetch_history",side_effect=lambda repo:history if repo==source["repo"] else []))
        (self.game/"BepInEx/config/BepInEx.cfg").write_bytes(b"player settings")
        page=self.page()
        plan=planner.build_plan(self.recipe,page._folders(),release_catalogs={role:archive_releases.asset_catalog(source,history)})
        archive_scans.persist(plan)
        page.set_recipe(self.recipe)
        self.assertEqual(page.install_review_button.text(),"Review update")
        return page,candidate,changed,removed,added

    def test_primary_review_and_global_block(self):
        page,candidate,changed,removed,added=self.setup_candidate()
        events=[]
        page.install_review_requested.connect(events.append)
        before=self.snapshot()
        page.install_review_button.click()
        self.wait_safety(page)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(events,[])
        self.assertIn("Update reviewed",page.safety_summary.text())
        detail=page.safety_details.toPlainText()
        self.assertIn("Install — "+added,detail)
        self.assertIn("Replace — "+changed,detail)
        self.assertIn("Remove — "+removed,detail)
        self.assertIn("Preserve — BepInEx/config/BepInEx.cfg",detail)
        self.assertIn("Installation is not approved",page.safety_summary.text())
        self.assertIsNone(page._safety_result)
        (self.game/added).write_bytes(b"foreign")
        before=self.snapshot()
        page.install_review_button.click()
        self.wait_safety(page)
        self.assertEqual(self.snapshot(),before)
        self.assertIn("Update blocked",page.safety_summary.text())
        detail=page.safety_details.toPlainText()
        for action in ("Install —","Replace —","Remove —"):
            self.assertNotIn(action,detail)
        self.assertIn("Block — "+added,detail)
        self.assertEqual(events,[])
        page.set_recipe(hub.load_recipes()["elden-ring"])
        self.assertFalse(page.safety_details.toPlainText())

    def test_missing_pin_and_stale_candidate(self):
        page,candidate,changed,removed,added=self.setup_candidate()
        self.archives[1].unlink()
        before=self.snapshot()
        page.install_review_button.click()
        self.wait_safety(page)
        self.assertIn("Update blocked",page.safety_summary.text())
        self.assertIn("Keep both previously supported ZIP",page.safety_details.toPlainText())
        self.assertEqual(self.snapshot(),before)
        candidate.write_bytes(b"tampered")
        page.install_review_button.click()
        self.assertIn("Rescan",page.folder_action_feedback.text())
        self.assertIsNone(page.safety_worker)

    def test_switch_discards_late_result(self):
        page,*_=self.setup_candidate()
        started,release_event=Event(),Event()
        original=bepinex_update_manifest.review
        def held(*args,**kwargs):
            started.set()
            if not release_event.wait(5):
                raise RuntimeError("timeout")
            return original(*args,**kwargs)
        with patch.object(bepinex_update_manifest,"review",side_effect=held):
            page.install_review_button.click()
            try:
                self.assertTrue(started.wait(3))
                page.set_recipe(hub.load_recipes()["elden-ring"])
            finally:
                release_event.set()
            self.wait_safety(page)
        self.assertFalse(page.safety_details.toPlainText())
        self.assertIsNone(page._safety_result)


class Subnautica(Cases,unittest.TestCase):
    fixture_class=test_subnautica.SubnauticaTests


class Valheim(Cases,unittest.TestCase):
    fixture_class=test_valheim.ValheimTests
