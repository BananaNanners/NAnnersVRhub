# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-W — read-only Cyberpunk game-root ZIP mapping and collision tests."""
import copy
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from threading import Event
from unittest import mock

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import (hub, cyberpunk_archive_mapping as mapping,
                   preupdate_safety as safety, destination_coverage as coverage,
                   installed_integrity, preservation_decisions as policy)
from tests.test_destination_coverage_v import CompleteDestinationCoverageTests
from vrhub.downloads_gui import GuidedDownloadsPage


def zip_write(path, entries):
    """Only disposable test data; repeated names intentionally stay repeated."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, payload in entries:
            z.writestr(name, payload)
    return path


class RealCyberpunkArchiveMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = hub.load_recipes()[mapping.GAME]
        cls.components = {str(c["nexus_mod"]): c for c in cls.recipe["components"]}
        cls.required = cls.components["30093"]["required_files"][0]

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nanners-dev5d3w-zip-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root/"fake-cyberpunk-game"
        self.game.mkdir()
        self.name = "Cyber Engine Tweaks-107-1-37-1-TEST.zip"
        self.path = self.root/self.name
        zip_write(self.path, [("bin/x64/plugins/cyber_engine_tweaks.asi",b"synthetic payload")])
        self.state = {}
        for patch in (
            mock.patch.object(hub, "game_path", return_value=self.game),
            mock.patch.object(hub, "state_file", return_value=self.root/"state.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def scan(self, cid="107", *, checksum=None):
        row = {
            "id":cid, "status":"Possible archive — inspect first",
            "file":str(self.path),
            "size":self.path.stat().st_size,
            "matches":1,
            "ambiguous":False,"candidate_incomplete":False,
            "release_review":False,
        }
        if checksum:
            row["candidates"]=[{"file":str(self.path),"tags":["test"],"sha256":checksum}]
        return {"warning":None,"rows":[row]}

    def review(self, cid="107", *, scan=None):
        return safety.review(
            self.recipe, scan if scan is not None else self.scan(cid),
            self.state,
            [{"id":cid,"code":"candidate","label":"Review candidate"}])

    def row(self,cid="107",*,scan=None):
        return next(r for r in self.review(cid,scan=scan)["rows"] if r["id"]==cid)

    def rezip(self, name, entries):
        self.path = self.root/name
        return zip_write(self.path,entries)

    def assert_never_live(self, cid="107", *, scan=None):
        result=self.review(cid,scan=scan)
        self.assertFalse(result["authorized"])
        self.assertFalse(result["has_live_install_plan"])
        self.assertFalse(result["rows"][0]["eligible"])
        self.assertTrue(all(not r["backups_verified_for_update"] for r in result["rows"]))
        self.assertIn("NOT been",result["recovery"])
        return next(r for r in result["rows"] if r["id"]==cid)

    def test_single_archive_can_map_metadata_without_nexus_hash_or_update_permission(self):
        targets,info=mapping.map_checked_zip(self.recipe,{"id":"107"},self.path)
        self.assertEqual(targets,("bin/x64/plugins/cyber_engine_tweaks.asi",))
        self.assertEqual(info["component_id"],"107")
        self.assertEqual(info["archive_members"],1)
        self.assertEqual(info["mapped_targets"],1)
        self.assertTrue(info["all_regular_members_accounted"])
        self.assertFalse(info["source_version_authenticated"])
        self.assertFalse(info["game_build_compatibility_verified"])
        self.assertFalse(info["live_update_authorized"])
        row=self.assert_never_live()
        self.assertEqual(row["full_target_provenance"],"cyberpunk_gameroot")
        self.assertEqual(row["full_target_list"],list(targets))
        self.assertEqual(row["future_destinations"],1)
        self.assertIn("source version unverified",row["mapping"])

    def test_readonly_layout_map_is_separate_from_blocked_online_readiness(self):
        result=safety.review(self.recipe,self.scan(),{},[{
            "id":"107","code":"integrity-unchecked",
            "label":"Verify installed files before any update"}])
        mapped=next(r for r in result["rows"] if r["id"]=="107")
        self.assertEqual(mapped["future_destinations"],1)
        self.assertEqual(mapped["full_target_provenance"],"cyberpunk_gameroot")
        self.assertIn("Verify installed files",mapped["readiness"])
        self.assertFalse(mapped["eligible"])
        self.assertFalse(mapped["backups_verified_for_update"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["has_live_install_plan"])

    def test_multiple_unverified_archives_remain_unmapped_when_readiness_blocked(self):
        scan=self.scan()
        scan["rows"][0]["matches"]=2
        result=safety.review(self.recipe,scan,{},[{
            "id":"107","code":"integrity-unchecked",
            "label":"Version identity unknown"}])
        row=next(r for r in result["rows"] if r["id"]=="107")
        self.assertIsNone(row["future_destinations"])
        self.assertIsNone(row["full_target_provenance"])
        self.assertFalse(result["authorized"])

    def test_single_zip_with_wrapper_folder_is_mapped_after_normalization(self):
        self.rezip(self.name,[
            ("A New Release/Bin/x64/plugins/cet.asi",b"fixture"),
            ("A New Release/r6/scripts/cet.script",b"fixture2")])
        row=self.assert_never_live()
        self.assertEqual(row["full_target_list"],
                         ["bin/x64/plugins/cet.asi","r6/scripts/cet.script"])
        self.assertEqual(row["full_target_provenance"],"cyberpunk_gameroot")

    def test_root_dir_mixed_upper_case_gets_canonical_top_level(self):
        self.rezip(self.name,[("RED4EXT/plugins/abc/file.dll",b"fixture")])
        row=self.assert_never_live()
        self.assertEqual(row["full_target_list"],["red4ext/plugins/abc/file.dll"])

    def test_vrport_required_file_must_be_present(self):
        self.rezip("CyberpunkVR-Port-30093-2.0.zip",
                   [(self.required,b"synthetic stereo")])
        row=self.assert_never_live("30093")
        self.assertEqual(row["full_target_list"],[self.required])
        self.rezip("CyberpunkVR-Port-30093-2.0.zip",
                   [("red4ext/plugins/wrong.dll",b"fake")])
        blocked=self.row("30093")
        self.assertIsNone(blocked["future_destinations"])
        self.assertIsNone(blocked["full_target_provenance"])
        self.assertIn("Required component payload",blocked["mapping"])

    def test_name_must_identify_exact_component_even_for_valid_zip(self):
        for name in ("CET-sample.zip","CET-107-2380.zip",
                     "Cyber Engine Tweaks-2380-v1.zip"):
            with self.subTest(name=name):
                self.rezip(name,[("bin/x64/plugins/cet.asi",b"synthetic")])
                with self.assertRaises(mapping.MappingBlocked):
                    mapping.map_checked_zip(self.recipe,{"id":"107"},self.path)
                self.assertIsNone(self.row()["future_destinations"])

    def test_unmapped_docs_ignored_by_installer_but_refused_as_complete_update(self):
        self.rezip(self.name,[
            ("bin/x64/plugins/cet.asi",b"fake"),
            ("README.txt",b"unmapped documentation")])
        with self.assertRaises(mapping.MappingBlocked):
            mapping.map_checked_zip(self.recipe,{"id":"107"},self.path)
        rejected=self.row()
        self.assertIsNone(rejected["future_destinations"])
        self.assertIn("unmapped files",rejected["mapping"])
        self.assertNotIn(str(self.root),rejected["mapping"])

    def test_outside_supported_game_roots_blocked(self):
        self.rezip(self.name,[("unrecognized/payload.dll",b"fake")])
        self.assertIsNone(self.row()["future_destinations"])

    def test_duplicate_case_insensitive_member_targets_blocked(self):
        self.rezip(self.name,[
            ("bin/x64/plugins/CET.dll",b"one"),
            ("BIN/x64/plugins/cet.DLL",b"two")])
        self.assertIsNone(self.row()["future_destinations"])

    def test_duplicate_exact_member_name_blocked(self):
        with mock.patch("warnings.warn"):
            self.rezip(self.name,[
                ("bin/x64/plugins/cet.dll",b"one"),
                ("bin/x64/plugins/cet.dll",b"two")])
        self.assertIsNone(self.row()["future_destinations"])

    def test_file_parent_child_conflict_blocked(self):
        self.rezip(self.name,[
            ("r6/scripts/entry",b"file"),
            ("r6/scripts/entry/child.dll",b"file")])
        self.assertIsNone(self.row()["future_destinations"])

    def test_traversal_absolute_and_windows_drive_member_paths_blocked(self):
        for entry in ("../escape.dll","/bin/x64/escape.dll",
                      "C:/fake/evil.dll","bin/x64/../escape.dll",
                      r"bin\x64\..\escape.dll"):
            with self.subTest(entry=entry):
                self.rezip(self.name,[(entry,b"fake")])
                self.assertIsNone(self.row()["future_destinations"])

    def test_symlink_zip_entry_blocked_by_preflight(self):
        info = zipfile.ZipInfo("bin/x64/plugins/link.dll")
        info.create_system=3
        info.external_attr=(0o120777<<16)
        self.rezip(self.name,[(info,b"fake")])
        self.assertIsNone(self.row()["future_destinations"])

    def test_zip_symlink_or_parent_symlink_never_followed(self):
        original=self.path
        link=self.root/"CET-107-link.zip"
        link.symlink_to(original)
        with self.assertRaises(mapping.MappingBlocked):
            mapping.map_checked_zip(self.recipe,{"id":"107"},link)
        wrapped=self.root/"linked-folder"
        wrapped.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(mapping.MappingBlocked):
            mapping.map_checked_zip(
                self.recipe,{"id":"107"},wrapped/self.name)

    def test_scan_identity_stale_size_or_digest_refused(self):
        scan=self.scan()
        scan["rows"][0]["size"]+=1
        self.assertIsNone(self.row(scan=scan)["future_destinations"])
        scan=self.scan(checksum="f"*64)
        self.assertIsNone(self.row(scan=scan)["future_destinations"])
        scan=self.scan()
        scan["rows"][0]["matches"]=0
        self.assertIsNone(self.row(scan=scan)["future_destinations"])

    def test_content_replaced_after_scanned_path_blocks_cached_row(self):
        old=self.scan()
        self.rezip(self.name,[("bin/x64/plugins/cet.asi",b"longer fixture payload")])
        self.assertIsNone(self.row(scan=old)["future_destinations"])

    def test_archive_mutated_during_mapping_digest_check_refused(self):
        original=safety.profile_safety._digest
        count=[0]
        def changing(path):
            count[0]+=1
            return original(path) if count[0]==1 else "f"*64
        with mock.patch.object(safety.profile_safety,"_digest",side_effect=changing):
            row=self.row()
        self.assertIsNone(row["future_destinations"])
        self.assertIn("digest changed",row["mapping"])

    def test_release_review_ambiguous_or_incomplete_scan_never_mapped(self):
        for flag in ("release_review","ambiguous","candidate_incomplete"):
            scan=self.scan()
            scan["rows"][0][flag]=True
            with self.subTest(flag=flag):
                self.assertIsNone(self.row(scan=scan)["future_destinations"])
        scan=self.scan(); scan["warning"]="incomplete scan"
        self.assertIsNone(self.row(scan=scan)["future_destinations"])

    def test_optional_archive_with_mismatched_extension_blocked(self):
        p=self.rezip("Cyber Engine Tweaks-107-1.7z",
                     [("bin/x64/plugins/cet.asi",b"fake")])
        with self.assertRaises(mapping.MappingBlocked):
            mapping.map_checked_zip(self.recipe,{"id":"107"},p)
        self.assertIsNone(self.row()["future_destinations"])

    def test_real_manual_file_collision_hint_never_silent_clearance(self):
        (self.game/"bin/x64/plugins").mkdir(parents=True)
        (self.game/"bin/x64/plugins/cyber_engine_tweaks.asi").write_bytes(b"manual")
        result=self.row()
        self.assertEqual(result["future_destinations"],1)
        self.assertTrue(result["untracked_collisions"])
        self.assertEqual(result["untracked_collisions"][0],
                         "bin/x64/plugins/cyber_engine_tweaks.asi")
        self.assertFalse(result["eligible"])

    def test_legacy_installed_record_is_never_auto_adopted(self):
        self.state={"cyberpunk-2077":{"installer":"gameroot-1",
                    "components":{"107":{"files":["manual/cet.asi"]}}}}
        row=self.row()
        self.assertEqual(row["full_target_provenance"],"cyberpunk_gameroot")
        self.assertFalse(row["eligible"])
        self.assertFalse(row["backups_verified_for_update"])

    def test_two_mapped_component_zips_same_target_get_conflict_review(self):
        from vrhub import preservation_decisions
        recipe=self.recipe
        # The complete mapper supports distinct IDs. Both synthetic valid
        # archives target the SAME relative game file.
        self.rezip(self.name,[("bin/x64/plugins/shared.dll",b"first")])
        other=zip_write(self.root/"RED4ext-2380-2.0.zip",
                        [("BIN/x64/plugins/shared.dll",b"second")])
        scan=self.scan()
        scan["rows"].append({
            "id":"2380","status":"Possible archive — inspect first",
            "file":str(other),"size":other.stat().st_size,"matches":1,
            "ambiguous":False,"candidate_incomplete":False,"release_review":False})
        dec=[{"id":x,"code":"candidate","label":"Future candidate"}
             for x in ("107","2380")]
        safe=safety.review(recipe,scan,{},dec)
        worksheet=policy.assess(recipe,{
            "game_id":recipe["id"],"rows":[{
                "id":c["id"],"name":c["name"],"owned_by_hub":False,
                "reported_issues":[],"unreported_issues":0,
                "live_update_authorized":False,"manual_files_adopted":False,
                "recorded_file_hashes_rewritten":False,
                "legacy_state_migrated":False,
            } for c in __import__("vrhub.download_planner",fromlist=["plan_components"]).plan_components(recipe)],
            "live_update_authorized":False,"manual_files_adopted":False,
            "recorded_file_hashes_rewritten":False,
            "legacy_state_migrated":False,"files_read_or_hashed_by_triage":False,
            "real_compatibility_verified":False})
        result=coverage.assess(recipe,safe,worksheet)
        self.assertEqual(result["complete_recipe_target_lists"],2)
        self.assertEqual(result["counts"]["conflict_review"],2)
        self.assertFalse(result["live_update_authorized"])
        self.assertTrue(all(not x["mapping_future_compatible"] for x in result["rows"]))

    def test_fixture_rehearsal_covers_synthetic_direct_wrapper_and_refusals(self):
        report=mapping.rehearse_synthetic_archive_mapping()
        self.assertTrue(report["fixture_only"])
        self.assertEqual(report["successful_archive_maps"],2)
        self.assertEqual(report["mapped_destination_paths"],3)
        self.assertEqual(report["blocked_archives"],4)
        self.assertTrue(report["temporary_fixture_discarded"])
        self.assertFalse(report["real_archive_source_authenticated"])
        self.assertFalse(report["real_game_files_modified"])
        self.assertFalse(report["live_update_authorized"])

    def test_metadata_parser_never_calls_unzip_or_live_update(self):
        with (mock.patch.object(hub,"_stage_archive",
                                side_effect=AssertionError("unzip")),
              mock.patch.object(hub,"install",
                                side_effect=AssertionError("live install")),
              mock.patch.object(Path,"write_bytes",
                                side_effect=AssertionError("mutate"))):
            targets, _=mapping.map_checked_zip(self.recipe,{"id":"107"},self.path)
        self.assertEqual(len(targets),1)

    def test_preserved_state_and_archive_not_modified_by_readonly_review(self):
        before=(self.path.read_bytes(),copy.deepcopy(self.state))
        self.review()
        self.assertEqual(before,(self.path.read_bytes(),self.state))


class CyberpunkMappingGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="nanners-dev5d3w-qt-")
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        (self.root/"fakegame").mkdir()
        for p in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=self.root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=self.root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=self.root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
            mock.patch.object(hub,"game_path",return_value=self.root/"fakegame"),
        ):
            p.start();self.addCleanup(p.stop)
        self.page=GuidedDownloadsPage()
        self.page.show();self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])

    def test_safety_report_remains_unauthorized_without_actual_candidate(self):
        self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(400):
            if self.page.safety_worker is None:break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertFalse(self.page._safety_result["authorized"])
        self.assertEqual(self.page._safety_result["coverage"]["complete_recipe_target_lists"],0)
        self.assertFalse(self.page._safety_result["coverage"]["live_update_authorized"])
        text=self.page.safety_details.toPlainText()
        self.assertIn("COMPLETE DESTINATION MAPPING",text)
        self.assertIn("LIVE UPDATE DISABLED",text)
        self.assertFalse(self.page.install_review_button.isEnabled())

    def test_switch_game_discards_old_mapping_report(self):
        self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(400):
            if self.page.safety_worker is None:break
            QTest.qWait(10)
        self.assertIn("coverage",self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["valheim"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
