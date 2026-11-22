# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-E2: Downloads + optional extra root, history and safety."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from vrhub import hub, archive_scans as scans, download_planner as planner
from vrhub.downloads_gui import GuidedDownloadsPage


class MultiFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.down = self.root / "Downloads"
        self.down.mkdir()
        self.custom = self.down / "Organized/Archive-Library/VR-Mods/Fatekeeper"
        self.custom.mkdir(parents=True)
        self.unrelated = self.root / "sensitive.txt"
        self.unrelated.write_bytes(b"DO NOT TOUCH")
        self.state = self.root / "state.json"
        self.saved = self.root / "scans.json"
        self.prefs = self.root / "prefs.json"
        for ctx in (mock.patch.object(Path, "home", return_value=self.root),
                    mock.patch.object(scans, "snapshot_file", return_value=self.saved),
                    mock.patch.object(planner, "preferences_file", return_value=self.prefs)):
            ctx.start()
            self.addCleanup(ctx.stop)
        self.recipe = copy.deepcopy(hub.load_recipes()["fatekeeper"])
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)

    def archive(self, folder, name, data=b"test"):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("test.dll", data)
        return path

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_downloads_and_game_folder_and_shared_fallback(self):
        self.assertEqual(planner.scan_folders(self.recipe), (self.down,))
        planner.set_location("global", str(self.custom))
        self.assertEqual(planner.scan_folders(self.recipe), (self.down, self.custom))
        game = self.root / "GameOnly"
        game.mkdir()
        planner.set_location("game", str(game), self.recipe["id"])
        self.assertEqual(planner.scan_folders(self.recipe), (self.down, game))
        planner.set_location("global", None)
        self.assertEqual(planner.scan_folders(self.recipe), (self.down, game))
        planner.set_location("game", None, self.recipe["id"])
        self.assertEqual(planner.scan_folders(self.recipe), (self.down,))
        self.assertEqual(self.unrelated.read_bytes(), b"DO NOT TOUCH")

    def test_two_roots_find_cross_folder_packages_with_one_scan(self):
        injector = self.archive(self.down, "UEVR_FK.zip")
        profile = self.archive(self.custom, "SLASHER-Win64-Shipping.zip")
        planner.set_location("game", str(self.custom), self.recipe["id"])
        roots = planner.scan_folders(self.recipe)
        plan = planner.build_plan(self.recipe, roots)
        self.assertEqual(plan["folders"], [str(self.down), str(self.custom)])
        self.assertEqual(plan["scanned"], 2)  # nested path is not counted twice
        self.assertEqual([r["file"] for r in plan["rows"]], [str(injector), str(profile)])
        rec = scans.persist(plan)
        self.page.set_recipe(self.recipe)
        self.assertEqual(self.page.install_review_button.text(), "Review installation")
        self.assertTrue(self.page.install_review_button.isEnabled())
        self.assertIn("2 scanned location(s)", self.page.summary.text())
        self.assertEqual(self.page._fresh_review_rows()[1]["file"], str(profile))
        self.assertEqual(scans.matching_record(self.recipe["id"], roots), rec)
        self.assertEqual(self.unrelated.read_bytes(), b"DO NOT TOUCH")

    def test_same_bytes_grouped_and_different_version_flagged(self):
        a = self.archive(self.down, "SLASHER-Win64-Shipping.zip", b"old")
        copy_a = self.custom / "SLASHER-Win64-Shipping (1).zip"
        copy_a.write_bytes(a.read_bytes())
        b = self.archive(self.custom, "SLASHER-Win64-Shipping (2).zip", b"new")
        catalog = {"assets":[{"tag":"v1.0.4","when":123,"sha256":self.digest(b),
                              "size":b.stat().st_size},
                             {"tag":"v1.0.3","when":122,"sha256":self.digest(a),
                              "size":a.stat().st_size}],
                   "expected":"v1.0.4","fixed":False}
        planner.set_location("game", str(self.custom), self.recipe["id"])
        plan = planner.build_plan(self.recipe,planner.scan_folders(self.recipe),
                                  release_catalogs={"profile":catalog})
        row=plan["rows"][1]
        self.assertEqual(row["matches"],3)
        self.assertEqual(len(row["candidates"]),2)
        self.assertEqual(sorted(c["copies"] for c in row["candidates"]), [1,2])
        self.assertFalse(row["ambiguous"])
        self.assertEqual(row["file"], str(b))
        self.assertEqual(row["candidates"][0]["tags"],["v1.0.4"])
        self.assertEqual(a.read_bytes(),copy_a.read_bytes())
        scans.persist(plan)
        self.page.set_recipe(self.recipe)
        self.assertEqual(self.page._fresh_review_rows()[1]["file"],str(b))

    def test_history_versioning_legacy_import_and_folder_switch(self):
        legacy_zip=self.archive(self.custom,"UEVR_FK.zip")
        legacy_plan=planner.build_plan(self.recipe,self.custom)
        rid, rec=scans._record(legacy_plan)
        original={"schema":1,"games":{rid:rec}}
        self.saved.write_text(json.dumps(original))
        self.assertEqual(scans.load_histories()[rid],[rec])
        planner.set_location("game",str(self.custom),rid)
        self.page.set_recipe(self.recipe)
        self.assertIsNone(self.page._last_plan)
        self.assertIn("Previous scan retained",self.page.scan_age.text())
        self.assertTrue(self.page.saved_folder_action.isVisible() or self.page._last_roots == (self.down,self.custom))
        old_bytes=self.saved.read_bytes()
        first=scans.persist(planner.build_plan(self.recipe,planner.scan_folders(self.recipe)))
        backup=self.saved.with_name("archive-scan-snapshots.pre-multifolder-v1.json")
        self.assertEqual(backup.read_bytes(), old_bytes)
        self.assertEqual(len(scans.load_histories()[rid]),2)
        self.assertEqual(scans.load_histories()[rid][1],rec)
        self.page.set_recipe(self.recipe)
        self.assertIsNotNone(self.page._last_plan)
        custom2=self.root/"Other";custom2.mkdir()
        planner.set_location("game",str(custom2),rid)
        self.page.set_recipe(self.recipe)
        self.assertIsNone(self.page._last_plan)
        second=scans.persist(planner.build_plan(self.recipe,planner.scan_folders(self.recipe)))
        self.assertEqual(len(scans.load_histories()[rid]),3)
        planner.set_location("game",str(self.custom),rid)
        self.page.set_recipe(self.recipe)
        self.assertEqual(scans.matching_record(rid,(self.down,self.custom)),first)
        self.assertEqual(scans.load_histories()[rid][0],second)
        self.assertEqual(legacy_zip.read_bytes(),(self.custom/"UEVR_FK.zip").read_bytes())
        self.assertEqual(self.unrelated.read_bytes(), b"DO NOT TOUCH")

    def test_stale_replacement_and_missing_extra_fail_closed(self):
        archive=self.archive(self.custom,"SLASHER-Win64-Shipping.zip")
        planner.set_location("game",str(self.custom),self.recipe["id"])
        scans.persist(planner.build_plan(self.recipe,planner.scan_folders(self.recipe)))
        archive.write_bytes(b"modified")
        self.page.set_recipe(self.recipe)
        self.assertEqual(self.page._last_plan["rows"][1]["status"],"Archive changed — rescan required")
        self.assertEqual(self.page._fresh_review_rows()[1]["file"],"")
        archive.unlink()
        # A missing extra root makes an incomplete scan. Its available
        # Downloads archives do not authorize review.
        for path in self.custom.iterdir(): path.unlink()
        self.custom.rmdir()
        plan=planner.build_plan(self.recipe,planner.scan_folders(self.recipe))
        self.assertIn("unavailable",plan["warning"])
        scans.persist(plan)
        self.page.set_recipe(self.recipe)
        self.assertFalse(self.page.install_review_button.isEnabled())

    def test_symlink_root_and_symlink_archive_never_followed(self):
        other=self.root/"other";other.mkdir()
        foreign=self.archive(other,"UEVR_FK.zip")
        custom_link=self.root/"my-symlink"
        custom_link.symlink_to(other,target_is_directory=True)
        with self.assertRaises(ValueError):
            planner.set_location("game", str(custom_link), self.recipe["id"])
        plan=planner.build_plan(self.recipe, (self.down, custom_link))
        self.assertIn("unsafe",plan["warning"])
        self.assertEqual(plan["rows"][0]["status"],"Not found locally")
        file_link=self.down/"UEVR_FK.zip"
        file_link.symlink_to(foreign)
        plan=planner.build_plan(self.recipe,(self.down,))
        self.assertEqual(plan["rows"][0]["status"],"Not found locally")
        self.assertTrue(foreign.is_file())

    def test_unchanged_scan_isolated_process_reads_schema2(self):
        self.archive(self.down,"UEVR_FK.zip")
        scans.persist(planner.build_plan(self.recipe,(self.down,)))
        before=self.saved.read_bytes()
        # A separate process reads only the isolated fixture, no production.
        command=[sys.executable,"-B","-c",(
            "import json,sys;d=json.load(open(sys.argv[1]));"
            "assert d['schema']==2;"
            "assert len(d['games']['fatekeeper'])==1;"
            "print('REOPEN_OK')")]
        output=subprocess.check_output(command+[str(self.saved)],text=True)
        self.assertIn("REOPEN_OK",output)
        self.assertEqual(self.saved.read_bytes(),before)

    def test_old_history_never_silently_evicted(self):
        self.archive(self.down,"UEVR_FK.zip")
        for i in range(scans.MAX_SCANS_PER_GAME):
            folder=self.root/("extra"+str(i))
            folder.mkdir()
            scans.persist(planner.build_plan(self.recipe,(self.down,folder)))
        before=self.saved.read_bytes()
        extra=self.root/"ninth";extra.mkdir()
        with self.assertRaisesRegex(ValueError,"history full"):
            scans.persist(planner.build_plan(self.recipe,(self.down,extra)))
        self.assertEqual(self.saved.read_bytes(),before)
