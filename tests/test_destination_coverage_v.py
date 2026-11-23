# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-V destination mapping and preservation coverage safety tests."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import (hub, download_planner, destination_coverage as v,
                   preservation_decisions as policy)
from tests.test_update_manifest_preview_u import safety as source_safety
from tests.test_update_manifest_preview_u import worksheet as source_worksheet
from vrhub.downloads_gui import GuidedDownloadsPage


class CompleteDestinationCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes=hub.load_recipes()

    def docs(self, rid):
        recipe=self.recipes[rid]
        s=source_safety(recipe)
        for row in s["rows"]:
            row["full_target_list"]=[]
            row["full_target_provenance"]=None
        return recipe,s,source_worksheet(recipe) if rid=="valheim" else policy.assess(
            recipe,{
                "game_id":rid,"rows":[{
                    "id":str(c["id"]),"name":str(c["name"]),"reported_issues":[],
                    "unreported_issues":0,"owned_by_hub":False,
                    "live_update_authorized":False,"manual_files_adopted":False,
                    "recorded_file_hashes_rewritten":False,"legacy_state_migrated":False,
                } for c in download_planner.plan_components(recipe)],
                "live_update_authorized":False,"manual_files_adopted":False,
                "recorded_file_hashes_rewritten":False,"legacy_state_migrated":False,
                "files_read_or_hashed_by_triage":False,
                "real_compatibility_verified":False,
            })

    def mapped(self,s, cid, names, provenance="pinned_package"):
        row=next(r for r in s["rows"] if r["id"]==cid)
        row["future_destinations"]=len(names)
        row["future_sample"]=names[:12]
        row["full_target_list"]=list(names)
        row["full_target_provenance"]=provenance

    def blocked(self,result):
        self.assertFalse(result["live_update_authorized"])
        self.assertFalse(result["real_compatibility_verified"])
        self.assertFalse(result["full_archive_member_accounting_proven"])
        self.assertFalse(result["installed_file_coverage_proven"])
        self.assertFalse(result["file_preservation_enforced"])
        self.assertFalse(result["cross_component_coverage_complete"])
        self.assertIsNone(result["executable_plan"])
        self.assertTrue(result["requires_separate_live_approval"])
        self.assertIn("LIVE UPDATE DISABLED",result["status"])
        for row in result["rows"]:
            self.assertFalse(row["live_update_authorized"])
            self.assertFalse(row["mapping_future_compatible"])

    def test_all_nine_games_and_27_dependencies_need_proof_by_default(self):
        total=0
        for rid in self.recipes:
            with self.subTest(game=rid):
                recipe,s,worksheet=self.docs(rid)
                report=v.assess(recipe,s,worksheet)
                self.blocked(report)
                self.assertEqual(report["total_dependencies"],
                                 len(download_planner.plan_components(recipe)))
                self.assertEqual(report["complete_recipe_target_lists"],0)
                self.assertEqual(report["counts"]["target_list_mapped"],0)
                total+=len(report["rows"])
        self.assertEqual(total,27)

    def test_two_pinned_archives_can_have_complete_recipe_target_lists(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/config/custom.ini","BepInEx/core/bepinex.dll"])
        self.mapped(s,"vhvr",["BepInEx/plugins/VHVR.dll","valheim_Data/Managed/UnityEngine.XR.dll"])
        result=v.assess(recipe,s,worksheet)
        self.assertEqual(result["complete_recipe_target_lists"],2)
        self.assertEqual(result["counts"]["preservation_review"],1)
        self.assertEqual(result["counts"]["target_list_mapped"],1)
        self.assertEqual(result["rows"][0]["preservation_overlaps"],1)
        self.assertEqual(result["rows"][0]["full_target_count"],2)
        self.assertFalse(result["rows"][0]["source_file_accounting_complete"])
        self.blocked(result)

    def test_unlisted_modified_file_still_needs_review(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/core/bepinex.dll"])
        result=v.assess(recipe,s,worksheet)
        self.assertEqual(result["rows"][0]["preservation_overlaps"],0)
        self.assertEqual(result["rows"][0]["unmapped_preservation_issues"],1)
        self.assertEqual(result["rows"][0]["status"],"preservation_review")
        self.blocked(result)

    def test_complete_uevr_profile_target_list_separate_from_manual_injector(self):
        recipe,s,worksheet=self.docs("fatekeeper")
        self.mapped(s,"profile",["config.txt","scripts/test.lua"],"uevr_profile")
        result=v.assess(recipe,s,worksheet)
        self.assertEqual(result["rows"][0]["status"],"mapping_missing")
        self.assertEqual(result["rows"][1]["status"],"target_list_mapped")
        self.assertEqual(result["complete_recipe_target_lists"],1)
        self.blocked(result)

    def test_hogwarts_profile_is_not_injector_compatibility(self):
        recipe,s,worksheet=self.docs("hogwarts-legacy")
        self.mapped(s,"profile",["config.txt"],"uevr_profile")
        report=v.assess(recipe,s,worksheet)
        self.assertFalse(report["rows"][1]["mapping_future_compatible"])
        self.assertFalse(report["installed_file_coverage_proven"])
        self.blocked(report)

    def test_cyberpunk_legacy_real_mapping_not_silently_supported(self):
        recipe,s,worksheet=self.docs("cyberpunk-2077")
        first=s["rows"][0]["id"]
        self.mapped(s,first,["bin/x64/plugins/one.dll"],"pinned_package")
        with self.assertRaisesRegex(ValueError,"Wrong mapper"):
            v.assess(recipe,s,worksheet)

    def test_unsupported_mapped_target_provenance_blocks_instead_of_guessing(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/core/a.dll"],"guessed-archive-wrapper")
        with self.assertRaisesRegex(ValueError,"Unrecognized target mapper"):
            v.assess(recipe,s,worksheet)

    def test_duplicate_casefold_and_file_directory_ancestor_rejected(self):
        for paths in (
            ["BepInEx/core/A.dll","bepinex/core/a.DLL"],
            ["BepInEx/core/parent", "BepInEx/core/parent/nested.dll"],
        ):
            with self.subTest(paths=paths):
                recipe,s,worksheet=self.docs("valheim")
                self.mapped(s,"loader",paths)
                with self.assertRaises(ValueError):
                    v.assess(recipe,s,worksheet)

    def test_real_map_sample_count_mismatch_or_unsafe_path_rejected(self):
        for field,value in (
            ("future_destinations",99),
            ("future_sample",["BepInEx/core/wrong.dll"]),
            ("full_target_list",["../unsafe.dll"]),
            ("full_target_list",[r"mods\windows.dll"]),
            ("full_target_list",[]),
        ):
            with self.subTest(field=field,value=value):
                recipe,s,worksheet=self.docs("valheim")
                self.mapped(s,"loader",["BepInEx/core/a.dll"])
                s["rows"][0][field]=value
                with self.assertRaises(ValueError):
                    v.assess(recipe,s,worksheet)

    def test_mapped_but_unattributed_list_is_refused(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/core/a.dll"])
        s["rows"][0]["full_target_provenance"]=None
        with self.assertRaisesRegex(ValueError,"Unattributed"):
            v.assess(recipe,s,worksheet)

    def test_cross_component_same_future_target_blocks_both_packages(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/plugins/a.dll","BepInEx/config/custom.ini"])
        self.mapped(s,"vhvr",["bepinex/plugins/A.DLL"])
        result=v.assess(recipe,s,worksheet)
        self.assertEqual(result["counts"]["conflict_review"],2)
        self.assertGreater(result["rows"][0]["cross_component_overlaps"],0)
        self.assertGreater(result["rows"][1]["cross_component_overlaps"],0)
        self.blocked(result)

    def test_cross_component_ancestor_collision_blocks_both(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/plugins/folder"])
        self.mapped(s,"vhvr",["BepInEx/plugins/folder/nested.dll"])
        report=v.assess(recipe,s,worksheet)
        self.assertEqual(report["counts"]["conflict_review"],2)
        self.blocked(report)

    def test_existing_untracked_or_owner_conflict_has_priority_over_complete_map(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/config/custom.ini"])
        s["rows"][0]["untracked_collisions"]=["manual-data.dll"]
        report=v.assess(recipe,s,worksheet)
        self.assertEqual(report["rows"][0]["status"],"conflict_review")
        self.assertEqual(report["rows"][0]["untracked_hints"],1)
        self.blocked(report)

    def test_a_consider_future_replacement_draft_is_still_hold(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/config/custom.ini"])
        worksheet["rows"][0]["draft_decision"]="consider_future_replacement"
        report=v.assess(recipe,s,worksheet)
        self.assertEqual(report["rows"][0]["preservation_overlaps"],1)
        self.assertEqual(report["rows"][0]["status"],"preservation_review")
        self.blocked(report)

    def test_partial_candidate_mapping_never_becomes_complete(self):
        recipe,s,worksheet=self.docs("valheim")
        row=s["rows"][0]
        row["future_destinations"]=19
        row["future_sample"]=["BepInEx/core/a.dll"]
        result=v.assess(recipe,s,worksheet)
        self.assertEqual(result["rows"][0]["status"],"preservation_review")
        self.assertFalse(result["rows"][0]["scope_complete_at_review"])
        self.blocked(result)

    def test_malformed_foreign_future_row_fails_closed(self):
        recipe,s,worksheet=self.docs("valheim")
        for edit in ("duplicate","other_id","live","othergame","foreign_choice"):
            saf, sheet=copy.deepcopy((s,worksheet))
            if edit=="duplicate":
                saf["rows"].append(copy.deepcopy(saf["rows"][0]))
            elif edit=="other_id":
                saf["rows"][0]["id"]="unrecognized"
            elif edit=="live":
                saf["authorized"]=True
            elif edit=="othergame":
                saf["game_id"]="cyberpunk-2077"
            else:
                sheet["rows"][0]["component_id"]="cyberpunk-2077"
            with self.subTest(edit=edit),self.assertRaises(ValueError):
                v.assess(recipe,saf,sheet)

    def test_tampered_preservation_authority_fails_closed(self):
        recipe,s,worksheet=self.docs("valheim")
        for key in ("replacement_authorized","selection_saved"):
            data=copy.deepcopy(worksheet)
            data["rows"][0][key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):
                v.assess(recipe,s,data)

    def test_nothing_in_coverage_audit_reads_files_or_changes_inputs(self):
        recipe,s,worksheet=self.docs("valheim")
        self.mapped(s,"loader",["BepInEx/config/custom.ini"])
        old=copy.deepcopy((recipe,s,worksheet))
        with (mock.patch.object(Path,"read_bytes",side_effect=AssertionError("read")),
              mock.patch.object(Path,"write_bytes",side_effect=AssertionError("write")),
              mock.patch.object(hub,"state",side_effect=AssertionError("state")),
              mock.patch.object(hub,"install",side_effect=AssertionError("install"))):
            result=v.assess(recipe,s,worksheet)
        self.assertEqual(old,(recipe,s,worksheet))
        self.blocked(result)

    def test_six_existing_fixture_families_reuse_complete_synthetic_maps(self):
        report=v.rehearse_synthetic_mapping_coverage()
        self.assertEqual(report["games"],6)
        self.assertEqual(report["families"],{"pinned":3,"uevr":2,"cyberpunk":1})
        self.assertEqual(report["retirement_holds"],2)
        self.assertTrue(report["manual_files_preserved"])
        self.assertFalse(report["real_file_contents_read"])
        self.assertFalse(report["live_update_authorized"])
        self.assertEqual(report["target_lists"]["cyberpunk-2077"]["candidate_targets"],4)


class CompleteCoverageGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="nanners-dev5d3v-gui-")
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        (root/"valheim").mkdir()
        for patch in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
            mock.patch.object(hub,"game_path",return_value=root/"valheim"),
        ):
            patch.start();self.addCleanup(patch.stop)
        self.page=GuidedDownloadsPage()
        self.page.show();self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["valheim"])

    def review(self):
        if not self.page.comparison_toggle.isChecked():
            self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(450):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertIsNotNone(self.page._safety_result)

    def test_existing_safety_report_only_contains_new_readonly_coverage(self):
        with mock.patch.object(v,"assess",wraps=v.assess) as checked:
            self.assertNotIn("COMPLETE DESTINATION MAPPING",
                             self.page.safety_details.toPlainText())
            before=(self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled())
            self.review()
            checked.assert_called_once()
        result=self.page._safety_result["coverage"]
        self.assertEqual(result["total_dependencies"],2)
        self.assertFalse(result["live_update_authorized"])
        text=self.page.safety_details.toPlainText()
        self.assertIn("COMPLETE DESTINATION MAPPING & PRESERVATION COVERAGE",text)
        self.assertIn("FULL list means mapped INSTALL TARGETS",text)
        self.assertIn("LIVE UPDATE DISABLED",text)
        self.assertIn("PRESERVATION-AWARE UPDATE MANIFEST PREVIEW",text)
        self.assertEqual(before,(self.page.install_review_button.text(),
                                 self.page.install_review_button.isEnabled()))

    def test_switching_games_clears_mapping_coverage_result(self):
        self.review()
        self.assertIn("coverage",self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
