# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-H read-only integrity, ownership and Qt acceptance fixtures."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest import mock
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import hub, installed_integrity as integrity
from vrhub.downloads_gui import GuidedDownloadsPage


def sha(data):
    return hashlib.sha256(data).hexdigest()


class InstalledIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)/"game"
        self.base.mkdir()
        self.userfile = Path(self.tmp.name)/"do-not-touch"
        self.userfile.write_bytes(b"private untouched")
        self.recipe = {
            "id":"valheim", "method":"bepinex",
            "packages":[
                {"id":"loader","name":"Loader","sha256":"a"*64},
                {"id":"vhvr","name":"VHVR","sha256":"b"*64},
            ],
        }
        self.files = {
            "BepInEx/core/loader.dll":b"pinned-loader",
            "BepInEx/plugins/vr.dll":b"pinned-VR",
        }
        for name, data in self.files.items():
            target = self.base/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.state = {"valheim":{
            "installer":"vhvr-1",
            "keep":str(self.base),
            "files":[str(self.base/name) for name in self.files],
            "file_hashes":{name:sha(data) for name,data in self.files.items()},
            "packages":{
                "loader":{"sha256":"a"*64, "files":[str(self.base/"BepInEx/core/loader.dll")]},
                "vhvr":{"sha256":"b"*64,"files":[str(self.base/"BepInEx/plugins/vr.dll")]},
            },
        }}
        p=mock.patch.object(hub,"game_path",return_value=self.base)
        p.start()
        self.addCleanup(p.stop)

    def result(self):
        return integrity.verify(self.recipe,state=self.state)

    def test_unchanged_hub_managed_packages_verify_without_writes(self):
        before={p:p.read_bytes() for p in [self.base/n for n in self.files]}
        result=self.result()
        self.assertEqual(result["status"],"Verified")
        self.assertEqual(result["checked"],2)
        self.assertEqual([r["status"] for r in result["rows"]],["Verified","Verified"])
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.assertEqual(self.userfile.read_bytes(),b"private untouched")

    def test_modified_and_missing_individual_files(self):
        (self.base/"BepInEx/plugins/vr.dll").write_bytes(b"changed by user")
        result=self.result()
        self.assertEqual(result["status"],"Review")
        self.assertEqual(result["rows"][0]["status"],"Verified")
        self.assertEqual(result["rows"][1]["issues"][0]["status"],"Modified")
        (self.base/"BepInEx/core/loader.dll").unlink()
        result=self.result()
        self.assertEqual(result["rows"][0]["issues"][0]["status"],"Missing")
        self.assertEqual(result["checked"],0)

    def test_untracked_files_are_not_scanned_or_claimed(self):
        extra=self.base/"BepInEx/plugins/private-user.ini"
        extra.write_bytes(b"manually edited")
        self.assertEqual(self.result()["status"],"Verified")
        self.assertEqual(extra.read_bytes(),b"manually edited")
        self.assertIn("recorded SHA-256",self.result()["message"])

    def test_symlink_file_and_directory_refused_without_follow(self):
        target=self.base/"BepInEx/plugins/vr.dll"
        target.unlink()
        target.symlink_to(self.userfile)
        result=self.result()
        self.assertIn(result["rows"][1]["issues"][0]["status"],("Unsafe","Unknown"))
        self.assertEqual(self.userfile.read_bytes(),b"private untouched")
        target.unlink()
        plugin_dir=self.base/"BepInEx/plugins"
        plugin_dir.rmdir()
        plugin_dir.symlink_to(self.userfile.parent)
        result=self.result()
        self.assertIn(result["rows"][1]["issues"][0]["status"],("Unsafe","Unknown"))
        self.assertEqual(self.userfile.read_bytes(),b"private untouched")

    def test_root_identity_change_returns_unknown_without_read(self):
        with mock.patch.object(hub,"game_path",return_value=self.userfile.parent):
            result=self.result()
        self.assertEqual(result["status"],"Unknown")
        self.assertEqual(result["checked"],0)
        self.state["valheim"]["keep"]=str(self.userfile.parent/"not-a-game")
        self.assertEqual(self.result()["status"],"Unknown")

    def test_missing_global_hashes_or_bad_pin_unknown_not_verified(self):
        self.state["valheim"]["file_hashes"]={}
        self.assertEqual(self.result()["status"],"Unknown")
        self.state["valheim"]["file_hashes"]={n:sha(v) for n,v in self.files.items()}
        self.state["valheim"]["packages"]["vhvr"]["sha256"]="f"*64
        result=self.result()
        self.assertEqual(result["status"],"Unknown")
        self.assertEqual(result["rows"][1]["status"],"Unknown")
        self.assertEqual(result["rows"][0]["status"],"Verified")

    def test_root_file_symlink_refused_even_if_hash_matches(self):
        link=self.base.parent/"link-root"
        link.symlink_to(self.base,target_is_directory=True)
        self.state["valheim"]["keep"]=str(link)
        with mock.patch.object(hub,"game_path",return_value=link):
            result=self.result()
        self.assertEqual(result["status"],"Unknown")

    def test_invalid_per_package_paths_are_never_opened(self):
        bads=[str(self.base/"../do-not-touch"),str(self.userfile),
              "not-absolute.dll",str(self.base/"BepInEx/core/../plugins/vr.dll")]
        for bad in bads:
            self.state["valheim"]["packages"]["vhvr"]["files"]=[bad]
            self.assertEqual(self.result()["rows"][1]["status"],"Unknown")
        self.assertEqual(self.userfile.read_bytes(),b"private untouched")

    def test_cancel_before_start_and_mid_hash(self):
        flag=Event()
        flag.set()
        with self.assertRaises(integrity.Cancelled):
            integrity.verify(self.recipe,state=self.state,cancel=flag)
        flag.clear()
        with mock.patch.object(integrity,"_read_hash",side_effect=lambda *a: (
                flag.set(), ("Hash", (sha(b"pinned-loader"), 13)))[1]):
            with self.assertRaises(integrity.Cancelled):
                integrity.verify(self.recipe,state=self.state,cancel=flag)
        self.assertEqual(self.userfile.read_bytes(),b"private untouched")

    def test_overlap_between_packages_is_not_verifiable(self):
        files=self.state["valheim"]["packages"]
        files["vhvr"]["files"]=list(files["loader"]["files"])
        self.assertEqual(self.result()["status"],"Unknown")

    def test_safe_limits_bounded_no_false_verified(self):
        with mock.patch.object(integrity,"MAX_FILES",1):
            result=self.result()
        self.assertEqual(result["status"],"Unknown")
        with mock.patch.object(integrity,"MAX_SCAN_BYTES",5):
            result=self.result()
        self.assertEqual(result["status"],"Unknown")
        with mock.patch.object(integrity,"MAX_FILE_BYTES",5):
            result=self.result()
        self.assertEqual(result["status"],"Unknown")

    def test_cyberpunk_per_component_manifest_and_unknown_legacy(self):
        recipe={"id":"cyberpunk-2077","method":"gameroot",
                "components":[{"nexus_mod":2380,"name":"RED4ext"},
                              {"nexus_mod":191,"name":"CET"}]}
        self.state={"cyberpunk-2077":{
            "installer":"gameroot-2","keep":str(self.base),
            "files":[str(self.base/"BepInEx/plugins/vr.dll")],
            "installed_sha256":{"BepInEx/plugins/vr.dll":sha(b"pinned-VR")},
            "components":{"2380":{"files":[str(self.base/"BepInEx/plugins/vr.dll")],
                                  "archive":"RED4ext-2380-1.31.1.zip"}}}}
        result=integrity.verify(recipe,state=self.state)
        self.assertEqual(result["rows"][0]["status"],"Verified")
        self.assertEqual(result["rows"][1]["status"],"Unknown")
        self.state["cyberpunk-2077"]["installer"]="gameroot-legacy"
        self.assertEqual(integrity.verify(recipe,state=self.state)["status"],"Unknown")

    def test_uevr_profile_exact_snapshot_and_bad_paths(self):
        recipe={"id":"hogwarts-legacy","method":"uevr",
                "profile":{"dir":"Roaming/UnrealVRMod/HogwartsLegacy"}}
        dest=self.base/"profile"
        dest.mkdir()
        (dest/"config.txt").write_bytes(b"profile-v2")
        record={"installer":"uevr-profile-2","root":str(dest),
                "files":[str(dest/"config.txt")],
                "installed":{"exists":True,"files":{
                    "config.txt":{"size":10,"sha256":sha(b"profile-v2")}}}}
        self.state={"hogwarts-legacy:profile":record}
        with mock.patch.object(hub,"profile_dir",return_value=dest):
            result=integrity.verify(recipe,state=self.state)
            self.assertEqual(result["rows"][0]["status"],"Verified")
            self.assertEqual(result["rows"][1]["status"],"Unknown")
            (dest/"config.txt").write_bytes(b"modified")
            self.assertEqual(integrity.verify(recipe,state=self.state)["rows"][0]["issues"][0]["status"],"Modified")
            record["installed"]["files"]["../do-not-touch"]=record["installed"]["files"]["config.txt"]
            self.assertEqual(integrity.verify(recipe,state=self.state)["status"],"Unknown")
        self.assertEqual(self.userfile.read_bytes(),b"private untouched")

    def test_guide_without_hash_manifest_is_unknown(self):
        self.assertEqual(integrity.verify({"id":"doom-2016-gog","method":"guide"},
                                          state={})["status"],"Unknown")


class InstalledIntegrityGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        for patch in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.page=GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)

    def test_button_one_per_game_no_unprompted_scan(self):
        recipe=hub.load_recipes()["valheim"]
        with mock.patch.object(integrity,"verify",side_effect=AssertionError("not requested")):
            self.page.set_recipe(recipe)
            self.assertEqual(self.page.integrity_button.text(),"Verify installed files")
            self.assertIn("not checked",self.page.integrity_status.text())
            self.assertFalse(self.page.integrity_details.isVisible())

    def test_review_details_visible_success_details_hidden(self):
        self.page.set_recipe(hub.load_recipes()["valheim"])
        worker=type("FixtureWorker",(),{"recipe":{"id":"valheim"},
              "cancel_flag":Event()})()
        self.page.integrity_worker=worker
        result={"game_id":"valheim","checked":1,"status":"Review",
                "rows":[
                    {"id":"loader","name":"Loader","status":"Verified","issues":[]},
                    {"id":"vhvr","name":"VHVR","status":"Review","reason":"1 modified",
                     "issues":[{"file":"BepInEx/plugins/vr.dll","status":"Modified",
                                "detail":"SHA differs"}]},
                ]}
        self.page._integrity_done(result,worker)
        self.assertTrue(self.page.integrity_details.isVisible())
        self.assertIn("Modified",self.page.integrity_details.toPlainText())
        self.assertIn("1 tracked file",self.page.integrity_status.text())
        result["rows"]=[{"id":"loader","name":"Loader","status":"Verified",
                         "issues":[]}]
        self.page._integrity_done(result,worker)
        self.assertFalse(self.page.integrity_details.isVisible())
        self.page.integrity_worker=None

    def test_real_button_click_runs_worker_on_disposable_fixture(self):
        root=Path(self.tmp.name)/"fixture-game"
        root.mkdir()
        mod=root/"BepInEx/core/one.dll"
        mod.parent.mkdir(parents=True)
        mod.write_bytes(b"qt-readonly-fixture")
        recipe=hub.load_recipes()["valheim"]
        state={"valheim":{
            "installer":"vhvr-1", "keep":str(root),
            "files":[str(mod)],
            "file_hashes":{"BepInEx/core/one.dll":sha(b"qt-readonly-fixture")},
            "packages":{"loader":{"sha256":recipe["packages"][0]["sha256"],
                                  "files":[str(mod)]}}}}
        with mock.patch.object(hub,"state",return_value=state), mock.patch.object(
                hub,"game_path",return_value=root):
            self.page.set_recipe(recipe)
            self.assertIsNone(self.page.integrity_worker)
            self.page.integrity_button.click()
            self.assertIsNotNone(self.page.integrity_worker)
            for _ in range(300):
                if self.page.integrity_worker is None:
                    break
                QTest.qWait(10)
            self.assertIsNone(self.page.integrity_worker)
        self.assertIsNotNone(self.page._integrity_result)
        self.assertEqual(self.page._integrity_result["checked"],1)
        self.assertIn("matched",self.page.integrity_status.text())
        self.assertTrue(self.page.integrity_details.isVisible())
        self.assertIn("VHVR 0.11.2: Unknown",self.page.integrity_details.toPlainText())
        self.assertEqual(mod.read_bytes(),b"qt-readonly-fixture")

    def test_stale_game_result_cannot_leak(self):
        self.page.set_recipe(hub.load_recipes()["valheim"])
        worker=type("FixtureWorker",(),{"recipe":{"id":"subnautica"},
              "cancel_flag":Event()})()
        self.page.integrity_worker=worker
        self.page._integrity_done({"game_id":"subnautica","status":"Verified",
                                   "checked":10,"rows":[]},worker)
        self.assertIsNone(self.page._integrity_result)
        self.page.integrity_worker=None
