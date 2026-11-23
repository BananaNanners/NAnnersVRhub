# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-T: advisory-only preservation decision policy and GUI checks."""
import copy
import tempfile
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest import mock

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import (hub, download_planner, ownership_triage,
                   preservation_decisions as decisions)
from vrhub.downloads_gui import GuidedDownloadsPage


def worksheet(recipe, changes=None, *, owned=True):
    changes = changes or {}
    rows = []
    for component in download_planner.plan_components(recipe):
        cid = str(component["id"])
        issues = []
        for status, name in changes.get(cid, []):
            category = ownership_triage._category(status, name)
            issues.append({
                "relative_file": name, "observed_status": status,
                "category": category, "cause_confirmed": False,
                "permitted_mutation": False,
                "next_step": ownership_triage._next_for(category),
            })
        rows.append({
            "id": cid, "name": str(component.get("name", cid)),
            "adapter": "pinned_package", "classification": (
                "file_differences" if issues else "integrity_not_established"),
            "owned_by_hub": owned,
            "reported_issues": issues, "unreported_issues": 0,
            "live_update_authorized": False, "manual_files_adopted": False,
            "recorded_file_hashes_rewritten": False, "legacy_state_migrated": False,
        })
    return {
        "game_id": recipe["id"], "rows": rows,
        "live_update_authorized": False, "manual_files_adopted": False,
        "recorded_file_hashes_rewritten": False, "legacy_state_migrated": False,
        "files_read_or_hashed_by_triage": False,
        "real_compatibility_verified": False,
    }


class PreservationDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = hub.load_recipes()

    def valheim(self, *, owned=True):
        recipe = self.recipes["valheim"]
        data=worksheet(recipe,{
            "loader": [("Modified", "BepInEx/config/BepInEx.cfg")],
            "vhvr": [
                ("Modified", "valheim_Data/Managed/UnityEngine.SpatialTracking.dll"),
                ("Modified", "valheim_Data/Managed/UnityEngine.XR.LegacyInputHelpers.dll"),
            ],
        }, owned=owned)
        return recipe,data

    def subnautica(self):
        recipe = self.recipes["subnautica"]
        return recipe,worksheet(recipe,{
            "loader":[("Modified","BepInEx/config/BepInEx.cfg")]
        })

    def assert_never_live(self, report):
        self.assertFalse(report["live_update_authorized"])
        self.assertFalse(report["real_backup_created"])
        self.assertFalse(report["recorded_file_hashes_rewritten"])
        self.assertFalse(report["manual_files_adopted"])
        self.assertFalse(report["choices_saved"])
        self.assertFalse(report["real_compatibility_verified"])
        self.assertTrue(report["session_only"])
        self.assertTrue(report["requires_separate_live_approval"])
        self.assertEqual(len(report["all_live_gates_unresolved"]), 6)
        self.assertTrue(all(not row["replacement_authorized"]
                            and not row["fresh_verified_backup"]
                            and not row["current_file_preserved_by_executor"]
                            and not row["recorded_sha_rewritten"]
                            and not row["real_compatibility_verified"]
                            and not row["selection_saved"]
                            for row in report["rows"]))

    def test_all_nine_games_27_dependencies_report_with_no_auto_choices(self):
        total=0
        for rid, recipe in self.recipes.items():
            with self.subTest(game=rid):
                data=worksheet(recipe)
                output=decisions.assess(recipe,data)
                self.assertEqual(output["game_id"],rid)
                self.assertEqual(output["rows"],[])
                self.assertFalse(output["user_confirmed_any_choice"])
                self.assertIn("0 reported difference",output["summary"])
                self.assert_never_live(output)
                total+=len(data["rows"])
        self.assertEqual(total,27)

    def test_valheim_recommend_preserve_config_investigate_binaries(self):
        recipe,data=self.valheim()
        report=decisions.assess(recipe,data)
        self.assertEqual(len(report["rows"]),3)
        self.assertEqual([r["recommendation"] for r in report["rows"]],[
            decisions.PRESERVE,decisions.INVESTIGATE,decisions.INVESTIGATE])
        self.assertEqual(report["counts"][decisions.PRESERVE],1)
        self.assertEqual(report["counts"][decisions.INVESTIGATE],2)
        self.assertEqual(report["counts"][decisions.CONSIDER],0)
        self.assertTrue(all(not r["selected_in_this_review"] for r in report["rows"]))
        self.assertFalse(report["user_confirmed_any_choice"])
        self.assertIn("does not enforce",report["rows"][0]["next_step"])
        self.assert_never_live(report)

    def test_subnautica_recommend_preserve_one_configuration(self):
        recipe,data=self.subnautica()
        result=decisions.assess(recipe,data)
        self.assertEqual(len(result["rows"]),1)
        self.assertEqual(result["rows"][0]["draft_decision"],decisions.PRESERVE)
        self.assertEqual(result["rows"][0]["relative_file"],
                         "BepInEx/config/BepInEx.cfg")
        self.assert_never_live(result)

    def test_explicit_preserve_choice_never_rewrites_or_enforces(self):
        recipe,data=self.valheim()
        override={"loader":{"BepInEx/config/BepInEx.cfg": decisions.PRESERVE}}
        report=decisions.assess(recipe,data,choices=override)
        self.assertTrue(report["user_confirmed_any_choice"])
        self.assertTrue(report["rows"][0]["selected_in_this_review"])
        self.assertFalse(report["rows"][0]["current_file_preserved_by_executor"])
        self.assertFalse(report["rows"][0]["selection_saved"])
        self.assert_never_live(report)

    def test_explicit_investigate_overrides_preserve_recommendation_session_only(self):
        recipe,data=self.valheim()
        choice={"loader":{"BepInEx/config/BepInEx.cfg":decisions.INVESTIGATE}}
        result=decisions.assess(recipe,data,choices=choice)
        self.assertEqual(result["rows"][0]["recommendation"],decisions.PRESERVE)
        self.assertEqual(result["rows"][0]["draft_decision"],decisions.INVESTIGATE)
        self.assertTrue(result["rows"][0]["selected_in_this_review"])
        self.assertEqual(result["counts"][decisions.PRESERVE],0)
        self.assert_never_live(result)

    def test_consider_future_replacement_only_review_cannot_execute(self):
        recipe,data=self.valheim()
        filename="valheim_Data/Managed/UnityEngine.SpatialTracking.dll"
        result=decisions.assess(
            recipe,data,choices={"vhvr":{filename:decisions.CONSIDER}})
        row=next(x for x in result["rows"] if x["relative_file"]==filename)
        self.assertEqual(row["draft_decision"],decisions.CONSIDER)
        self.assertIn("Future replacement is only a review candidate",row["next_step"])
        self.assertFalse(row["replacement_authorized"])
        self.assertTrue(row["selected_in_this_review"])
        self.assert_never_live(result)

    def test_future_replacement_refused_for_unowned_legacy_components(self):
        recipe,data=self.valheim(owned=False)
        with self.assertRaisesRegex(ValueError,"trusted installed ownership"):
            decisions.assess(recipe,data,choices={
                "vhvr":{"valheim_Data/Managed/UnityEngine.SpatialTracking.dll":
                        decisions.CONSIDER}})
        result=decisions.assess(recipe,data)
        self.assertEqual(result["rows"][1]["draft_decision"],decisions.INVESTIGATE)
        self.assert_never_live(result)

    def test_future_replacement_refused_for_ambiguous_classification(self):
        recipe,data=self.valheim()
        data["rows"][1]["classification"]="ownership_unverified"
        with self.assertRaises(ValueError):
            decisions.assess(recipe,data,choices={
                "vhvr":{"valheim_Data/Managed/UnityEngine.SpatialTracking.dll":
                        decisions.CONSIDER}})

    def test_draft_preserve_for_binary_is_still_only_a_review_choice(self):
        recipe,data=self.valheim()
        name="valheim_Data/Managed/UnityEngine.XR.LegacyInputHelpers.dll"
        result=decisions.assess(recipe,data,choices={"vhvr":{name:decisions.PRESERVE}})
        row=next(r for r in result["rows"] if r["relative_file"]==name)
        self.assertEqual(row["recommendation"],decisions.INVESTIGATE)
        self.assertEqual(row["draft_decision"],decisions.PRESERVE)
        self.assertFalse(row["current_file_preserved_by_executor"])
        self.assert_never_live(result)

    def test_missing_unsafe_unknown_file_cannot_be_preserved_or_replaced(self):
        recipe=self.recipes["valheim"]
        for status in ("Missing","Unsafe","Unknown"):
            filename="mods/changed.dll"
            data=worksheet(recipe,{"loader":[(status,filename)]})
            with self.subTest(status=status):
                for choice in (decisions.PRESERVE, decisions.CONSIDER):
                    with self.assertRaisesRegex(ValueError,"Cannot preserve or replace"):
                        decisions.assess(recipe,data,choices={"loader":{filename:choice}})
                output=decisions.assess(recipe,data,choices={
                    "loader":{filename:decisions.INVESTIGATE}})
                self.assertEqual(output["rows"][0]["draft_decision"],decisions.INVESTIGATE)
                self.assert_never_live(output)

    def test_unknown_target_file_component_or_decision_refused(self):
        recipe,data=self.valheim()
        for choice in (
            {"not-a-mod":{"BepInEx/config/BepInEx.cfg":decisions.PRESERVE}},
            {"loader":{"mods/untracked.dll":decisions.PRESERVE}},
            {"loader":{"BepInEx/config/BepInEx.cfg":"replace_now"}},
            {"loader":{"BepInEx/config/BepInEx.cfg":True}},
            {"loader":None},
        ):
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                decisions.assess(recipe,data,choices=choice)

    def test_cross_game_row_and_forged_permission_refused(self):
        recipe,data=self.valheim()
        for location,key,value in (
            ("top","game_id","subnautica"),
            ("top","live_update_authorized",True),
            ("top","manual_files_adopted",True),
            ("top","recorded_file_hashes_rewritten",True),
            ("top","real_compatibility_verified",True),
            ("issue","cause_confirmed",True),
            ("issue","permitted_mutation",True),
            ("row","live_update_authorized",True),
            ("row","recorded_file_hashes_rewritten",True),
        ):
            with self.subTest(location=location,key=key):
                sample=copy.deepcopy(data)
                target=sample if location=="top" else (
                    sample["rows"][0] if location=="row" else
                    sample["rows"][0]["reported_issues"][0])
                target[key]=value
                with self.assertRaises(ValueError):
                    decisions.assess(recipe,sample)

    def test_untrusted_path_and_category_mismatch_refused(self):
        recipe,data=self.valheim()
        for path in ("/home/user/private","../traversal.dll",
                     "C:/Windows/config.ini","BepInEx//config.ini",
                     r"folder\evil.dll"):
            with self.subTest(path=path):
                sample=copy.deepcopy(data)
                sample["rows"][0]["reported_issues"][0]["relative_file"]=path
                with self.assertRaises(ValueError):
                    decisions.assess(recipe,sample)
        sample=copy.deepcopy(data)
        sample["rows"][0]["reported_issues"][0]["category"]="binary_drift"
        with self.assertRaises(ValueError):
            decisions.assess(recipe,sample)

    def test_cross_component_casefold_collision_refused(self):
        recipe,data=self.valheim()
        data["rows"][1]["reported_issues"][0]["relative_file"]="bepinex/CONFIG/BEPINEX.cfg"
        data["rows"][1]["reported_issues"][0]["category"]="possible_customization"
        with self.assertRaisesRegex(ValueError,"Cross-component"):
            decisions.assess(recipe,data)

    def test_partial_triage_never_silently_claims_complete_inventory(self):
        recipe,data=self.valheim()
        data["rows"][1]["unreported_issues"]=9
        result=decisions.assess(recipe,data)
        self.assertEqual(result["unreported_differences"],9)
        self.assertIn("9 unlisted difference",result["summary"])
        self.assert_never_live(result)
        data["rows"][1]["unreported_issues"]=-1
        with self.assertRaises(ValueError):
            decisions.assess(recipe,data)

    def test_duplicate_missing_extra_or_unbounded_dependency_evidence_refused(self):
        recipe,data=self.valheim()
        for alter in ("duplicate","missing","foreign"):
            sample=copy.deepcopy(data)
            if alter=="duplicate":sample["rows"].append(copy.deepcopy(sample["rows"][0]))
            if alter=="missing":sample["rows"].pop()
            if alter=="foreign":sample["rows"][0]["id"]="foreign"
            with self.subTest(alter=alter),self.assertRaises(ValueError):
                decisions.assess(recipe,sample)

    def test_no_mutating_calls_or_state_persistence(self):
        recipe,data=self.valheim()
        before=copy.deepcopy(data)
        with (mock.patch.object(Path,"read_bytes",side_effect=AssertionError("read")),
              mock.patch.object(Path,"write_bytes",side_effect=AssertionError("write")),
              mock.patch.object(hub,"state",side_effect=AssertionError("state")),
              mock.patch.object(hub,"install",side_effect=AssertionError("install")),
              mock.patch.object(hub,"_save_state",side_effect=AssertionError("persist"))):
            result=decisions.assess(recipe,data)
        self.assertEqual(before,data)
        self.assert_never_live(result)


class PreservationDecisionGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="nanners-dev5d3t-gui-")
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
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
        self.page.show()
        self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["valheim"])

    def safety_review(self):
        if not self.page.comparison_toggle.isChecked():
            self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(450):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertIsNotNone(self.page._safety_result)

    def test_read_only_worksheet_attached_to_existing_safety_review(self):
        with mock.patch.object(decisions,"assess",wraps=decisions.assess) as probe:
            self.assertNotIn("MODIFIED-FILE PRESERVATION DECISION WORKSHEET",
                             self.page.safety_details.toPlainText())
            original=(self.page.install_review_button.text(),
                      self.page.install_review_button.isEnabled())
            self.safety_review()
            probe.assert_called_once()
        report=self.page._safety_result["preservation"]
        self.assertFalse(report["live_update_authorized"])
        self.assertFalse(report["choices_saved"])
        self.assertEqual(report["rows"],[])
        contents=self.page.safety_details.toPlainText()
        self.assertIn("MODIFIED-FILE PRESERVATION DECISION WORKSHEET",contents)
        self.assertIn("Recommendations are NOT user decisions",contents)
        self.assertIn("No listed differences to plan",contents)
        self.assertIn("LIVE UPDATE DISABLED",contents)
        self.assertEqual(original,(self.page.install_review_button.text(),
                                   self.page.install_review_button.isEnabled()))

    def test_synthetic_hash_differences_show_preserve_and_investigate(self):
        fake=SimpleNamespace(cancel_flag=Event(),recipe=self.page.recipe)
        integrity={
            "game_id":"valheim","status":"Review","checked":0,
            "rows":[
                {"id":"loader","name":"BepInExPack","status":"Review","files":1,
                 "checked":0,"reason":"fixture-only","issues":[{
                     "status":"Modified","file":"BepInEx/config/BepInEx.cfg",
                     "detail":"synthetic config difference"}]},
                {"id":"vhvr","name":"VHVR","status":"Review","files":1,
                 "checked":0,"reason":"fixture-only","issues":[{
                     "status":"Modified",
                     "file":"valheim_Data/Managed/UnityEngine.SpatialTracking.dll",
                     "detail":"synthetic binary difference"}]},
            ],
        }
        self.page.integrity_worker=fake
        self.page._integrity_done(integrity,fake)
        self.page.integrity_worker=None
        self.safety_review()
        plan=self.page._safety_result["preservation"]
        self.assertEqual(plan["counts"][decisions.PRESERVE],1)
        self.assertEqual(plan["counts"][decisions.INVESTIGATE],1)
        self.assertFalse(plan["user_confirmed_any_choice"])
        self.assertFalse(plan["live_update_authorized"])
        report=self.page.safety_details.toPlainText()
        self.assertIn("Recommend preserving current file pending review",report)
        self.assertIn("Investigate difference before deciding",report)
        self.assertIn("No choice saved.",report)

    def test_switch_game_clears_nonpersistent_worksheet(self):
        self.safety_review()
        self.assertIn("preservation",self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())

if __name__=="__main__":
    unittest.main()
