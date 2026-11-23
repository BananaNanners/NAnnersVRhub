# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-S: non-destructive legacy ownership / changed-file triage tests."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vrhub import (download_planner, hub, installed_integrity, ownership_triage as triage,
                   real_readiness_audit as audit, update_integration)
from vrhub.downloads_gui import GuidedDownloadsPage


def result_for(recipe, verified=False):
    rows = []
    for comp in download_planner.plan_components(recipe):
        if str(comp["id"]) == "guide":
            continue
        rows.append({"id":str(comp["id"]),"status":"Verified" if verified else "Unknown",
                     "files":1 if verified else 0,"checked":1 if verified else 0,
                     "issues":[]})
    return {"game_id":recipe["id"],"rows":rows,
            "status":"Verified" if verified else "Unknown","checked":len(rows) if verified else 0}


def issue(file, status="Modified"):
    return {"file":file,"status":status,"detail":"Synthetic difference only"}


class OwnershipTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes=hub.load_recipes()

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="nanners-dev5d3s-tests-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        for rid in self.recipes:
            (self.root/rid).mkdir()
        for rid in ("fatekeeper","hogwarts-legacy"):
            (self.root/rid/"profile").mkdir()
    def game(self,recipe):
        return self.root/recipe["id"]
    def profile(self,recipe):
        return self.root/recipe["id"]/"profile"
    def owned(self,rid):
        recipe=self.recipes[rid]
        state={rid: {
            "installer":{"valheim":"vhvr-1","subnautica":"submersed-vr-1",
                         "elden-ring":"ervr-1"}[rid],
            "keep":str(self.game(recipe)),
            "file_hashes":{},
            "packages":{},
        }}
        for comp in recipe["packages"]:
            relative=f"mods/{comp['id']}.dll"
            absolute=str(self.game(recipe)/relative)
            state[rid]["file_hashes"][relative]="a"*64
            state[rid]["packages"][comp["id"]]={
                "sha256":comp["sha256"],"files":[absolute]}
        return state
    def assess(self,rid,state=None,history=None):
        recipe=self.recipes[rid]
        state={} if state is None else state
        point=audit.audit_game(recipe,state,integrity=history,
                               game_locator=self.game,profile_locator=self.profile)
        return triage.assess(recipe,state,point,integrity=history)
    def assert_safe(self,report):
        self.assertFalse(report["files_read_or_hashed_by_triage"])
        self.assertTrue(report["provided_integrity_is_point_in_time"])
        self.assertFalse(report["recorded_file_hashes_rewritten"])
        self.assertFalse(report["legacy_state_migrated"])
        self.assertFalse(report["manual_files_adopted"])
        self.assertFalse(report["live_update_authorized"])
        self.assertFalse(report["real_compatibility_verified"])
        self.assertTrue(report["requires_separate_approval"])
        self.assertTrue(all(not x["live_update_authorized"] and
                            not x["manual_files_adopted"] and
                            not x["recorded_file_hashes_rewritten"]
                            for x in report["rows"]))

    def test_all_nine_games_and_27_dependencies_non_authorizing(self):
        count=0
        for rid,recipe in self.recipes.items():
            with self.subTest(rid=rid):
                result=self.assess(rid)
                self.assertEqual(result["game_id"],rid)
                self.assertEqual([row["id"] for row in result["rows"]],
                                 [c["id"] for c in download_planner.plan_components(recipe)])
                self.assert_safe(result)
                count+=len(result["rows"])
        self.assertEqual(count,27)

    def test_valheim_exact_three_synthetic_differences_with_no_inferred_causes(self):
        rid="valheim"
        record=self.owned(rid)
        history=result_for(self.recipes[rid])
        history["rows"][0].update({
            "status":"Review","checked":22,"files":23,
            "issues":[issue("BepInEx/config/BepInEx.cfg")]})
        history["rows"][1].update({
            "status":"Review","checked":110,"files":112,
            "issues":[issue("valheim_Data/Managed/UnityEngine.SpatialTracking.dll"),
                      issue("valheim_Data/Managed/UnityEngine.XR.LegacyInputHelpers.dll")]})
        result=self.assess(rid,record,history)
        self.assertEqual(result["issue_counts"]["possible_customization"],1)
        self.assertEqual(result["issue_counts"]["binary_drift"],2)
        self.assertEqual([r["classification"] for r in result["rows"]],
                         ["file_differences","file_differences"])
        self.assertEqual(
            [i["cause_confirmed"] for row in result["rows"]
             for i in row["reported_issues"]],[False]*3)
        self.assert_safe(result)

    def test_subnautica_only_loader_modified_and_vr_mod_prior_verified(self):
        rid="subnautica"
        integrity=result_for(self.recipes[rid])
        integrity["rows"][0].update({
            "status":"Review","checked":35,"files":36,
            "issues":[issue("BepInEx/config/BepInEx.cfg")]})
        integrity["rows"][1].update({
            "status":"Verified","checked":9,"files":9})
        result=self.assess(rid,self.owned(rid),integrity)
        self.assertEqual(result["issue_counts"]["possible_customization"],1)
        self.assertEqual(result["rows"][1]["classification"],"historical_match_only")
        self.assertIn("at scan time",result["rows"][1]["next_step"])
        self.assert_safe(result)

    def test_legacy_cyberpunk_remains_unverified_not_automatically_adopted(self):
        rid="cyberpunk-2077"
        record={rid:{"installer":"gameroot-1",
                     "components":{"107":{"files":["/fake/CET.dll"]}}}}
        report=self.assess(rid,record,result_for(self.recipes[rid]))
        self.assertEqual(len(report["rows"]),15)
        self.assertTrue(all(x["classification"]=="ownership_unverified"
                            for x in report["rows"]))
        self.assertTrue(all("never" not in x["next_step"] or x["manual_files_adopted"] is False
                            for x in report["rows"]))
        self.assert_safe(report)

    def test_uevr_injector_manual_profile_distinguishes_location_and_provenance(self):
        for rid in ("fatekeeper","hogwarts-legacy"):
            result=self.assess(rid,{},result_for(self.recipes[rid]))
            self.assertEqual(result["rows"][0]["classification"],"manual")
            self.assertEqual(result["rows"][1]["classification"],"ownership_unverified")
            self.assertFalse(result["rows"][0]["owned_by_hub"])
            self.assertFalse(result["rows"][1]["owned_by_hub"])
            self.assert_safe(result)

    def test_missing_uevr_profile_location_is_blocker_not_automatic_adoption(self):
        rid="fatekeeper"
        (self.root/rid/"profile").rmdir()
        report=self.assess(rid,{},result_for(self.recipes[rid]))
        self.assertEqual(report["rows"][1]["classification"],"root_or_location_blocked")
        self.assertIn("Reconcile",report["rows"][1]["next_step"])
        self.assert_safe(report)

    def test_missing_game_location_wins_over_manual_workflow(self):
        rid="ready-or-not"
        (self.root/rid).rmdir()
        report=self.assess(rid,{})
        self.assertEqual(report["rows"][0]["classification"],"root_or_location_blocked")
        self.assert_safe(report)

    def test_prior_verified_without_ownership_is_not_reconciled(self):
        rid="valheim"
        report=self.assess(rid,{},result_for(self.recipes[rid],verified=True))
        self.assertEqual(report["rows"][0]["classification"],"ownership_unverified")
        self.assertFalse(report["rows"][0]["owned_by_hub"])
        self.assert_safe(report)

    def test_integrity_not_requested_stays_unknown_not_clean(self):
        result=self.assess("valheim",self.owned("valheim"))
        self.assertEqual([x["classification"] for x in result["rows"]],
                         ["integrity_not_established","integrity_not_established"])
        self.assertTrue(all(x["status"]=="Not checked" for x in result["rows"]))
        self.assert_safe(result)

    def test_unknown_and_unreadable_file_not_interpreted_as_modified(self):
        rid="valheim"
        history=result_for(self.recipes[rid])
        history["rows"][0].update({"status":"Unknown","files":1,"checked":0,
                                    "issues":[issue("mods/large.dll","Unknown")]})
        result=self.assess(rid,self.owned(rid),history)
        self.assertEqual(result["issue_counts"]["unknown"],1)
        self.assertEqual(result["issue_counts"]["binary_drift"],0)
        self.assertFalse(result["rows"][0]["reported_issues"][0]["cause_confirmed"])
        self.assert_safe(result)

    def test_missing_and_unsafe_are_separately_explained(self):
        rid="valheim"
        history=result_for(self.recipes[rid])
        history["rows"][0].update({"status":"Review","files":2,"checked":0,
                                    "issues":[issue("BepInEx/core/x.dll","Missing"),
                                              issue("BepInEx/plugins/link.dll","Unsafe")]})
        result=self.assess(rid,self.owned(rid),history)
        self.assertEqual(result["issue_counts"]["missing"],1)
        self.assertEqual(result["issue_counts"]["unsafe"],1)
        self.assertIn("symlinks",result["rows"][0]["reported_issues"][1]["next_step"])
        self.assert_safe(result)

    def test_other_modified_kind_not_assumed_binary(self):
        rid="valheim"
        history=result_for(self.recipes[rid])
        history["rows"][0].update({"status":"Review","files":1,"checked":0,
                                    "issues":[issue("r6/input/Mappings.csv")]})
        result=self.assess(rid,self.owned(rid),history)
        self.assertEqual(result["issue_counts"]["other_modified"],1)

    def test_issues_bounded_and_truncation_observed_not_hidden(self):
        rid="valheim"
        history=result_for(self.recipes[rid])
        files=20
        history["rows"][0].update({
            "status":"Review","files":files,"checked":0,
            "issues":[issue(f"BepInEx/plugins/{i}.dll") for i in range(12)]})
        result=self.assess(rid,self.owned(rid),history)
        self.assertEqual(len(result["rows"][0]["reported_issues"]),12)
        self.assertEqual(result["rows"][0]["unreported_issues"],8)
        self.assertEqual(result["issue_counts"]["binary_drift"],12)
        self.assert_safe(result)

    def test_malformed_status_and_missing_review_count_fail_closed(self):
        rid="valheim"
        for patch in (
            {"status":"Ready"},
            {"status":"Verified","files":0,"checked":0},
            {"status":"Verified","files":1,"checked":0},
            {"status":"Review","files":1,"checked":1},
            {"status":"Review","files":-1,"checked":0},
            {"status":"Review","files":1,"checked":True},
        ):
            with self.subTest(patch=patch):
                history=result_for(self.recipes[rid])
                history["rows"][0].update(patch)
                with self.assertRaises(ValueError):
                    self.assess(rid,self.owned(rid),history)

    def test_invalid_issue_path_never_leaks_external_location(self):
        rid="valheim"
        for path in ("/home/user/private.txt","../outside.ini","BepInEx//evil.dll",
                     "C:/Windows/evil.dll","mods\backdoor.dll","mods/../escape.dll",
                     "bad\nname.dll"):
            with self.subTest(path=path):
                history=result_for(self.recipes[rid])
                history["rows"][0].update({
                    "status":"Review","files":1,"checked":0,
                    "issues":[issue(path)]})
                with self.assertRaises(ValueError):
                    self.assess(rid,self.owned(rid),history)

    def test_foreign_duplicate_and_wrong_game_integrity_refused(self):
        rid="valheim"
        for action in ("foreign","duplicate","wronggame"):
            history=result_for(self.recipes[rid])
            if action=="foreign": history["rows"][0]["id"]="unrecognized"
            if action=="duplicate": history["rows"].append(copy.deepcopy(history["rows"][0]))
            if action=="wronggame": history["game_id"]="subnautica"
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.assess(rid,self.owned(rid),history)

    def test_duplicate_casefold_file_issues_refused(self):
        rid="valheim"
        history=result_for(self.recipes[rid])
        history["rows"][0].update({
            "status":"Review","files":2,"checked":0,
            "issues":[issue("Mods/Mod.DLL"),issue("mods/mod.dll")]})
        with self.assertRaises(ValueError):
            self.assess(rid,self.owned(rid),history)

    def test_issue_count_larger_than_unmatched_files_refused(self):
        rid="valheim"
        history=result_for(self.recipes[rid])
        history["rows"][0].update({
            "status":"Review","files":2,"checked":1,
            "issues":[issue("one.dll"),issue("two.dll")]})
        with self.assertRaises(ValueError):
            self.assess(rid,self.owned(rid),history)

    def test_cross_game_and_forged_authorized_audit_refused(self):
        rid="valheim"
        recipe=self.recipes[rid]
        state=self.owned(rid)
        original=audit.audit_game(recipe,state,game_locator=self.game)
        for replacement in ("foreign","authorized","migrated","extra"):
            suspect=copy.deepcopy(original)
            if replacement=="foreign": suspect["game_id"]="subnautica"
            elif replacement=="authorized": suspect["authorized"]=True
            elif replacement=="migrated": suspect["rows"][0]["live_executor_connected"]=True
            else: suspect["rows"].append(copy.deepcopy(suspect["rows"][0]))
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                triage.assess(recipe,state,suspect)

    def test_real_live_calls_not_possible_in_pure_triage(self):
        rid="valheim"
        recipe=self.recipes[rid]
        state=self.owned(rid)
        snapshot=audit.audit_game(recipe,state,game_locator=self.game)
        history=result_for(recipe)
        before=copy.deepcopy((state,snapshot,history))
        with (mock.patch.object(Path,"read_bytes",side_effect=AssertionError("file content read")),
              mock.patch.object(Path,"write_bytes",side_effect=AssertionError("write")),
              mock.patch.object(hub,"install",side_effect=AssertionError("live install")),
              mock.patch.object(hub,"state",side_effect=AssertionError("state read"))):
            result=triage.assess(recipe,state,snapshot,integrity=history)
        self.assertEqual(before,(state,snapshot,history))
        self.assert_safe(result)

    def test_all_config_suffixes_are_only_possible_customization(self):
        for suffix in (".cfg",".ini",".json",".toml",".yaml",".yml",".xml"):
            with self.subTest(suffix=suffix):
                self.assertEqual(triage._category("Modified","CONFIG"+suffix),
                                 "possible_customization")
                self.assertIn("Possible",triage._next_for("possible_customization"))
        for suffix in (".dll",".exe",".asi",".so",".bin",".pdb"):
            self.assertEqual(triage._category("Modified","file"+suffix),"binary_drift")


class OwnershipTriageGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="nanners-dev5d3s-gui-")
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        (root/"valheim").mkdir()
        for p in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
            mock.patch.object(hub,"game_path",return_value=root/"valheim"),
        ):
            p.start();self.addCleanup(p.stop)
        self.page=GuidedDownloadsPage()
        self.page.show();self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["valheim"])

    def test_explicit_integrity_action_displays_tentative_explanations(self):
        from types import SimpleNamespace
        from threading import Event
        worker=SimpleNamespace(cancel_flag=Event(),recipe=self.page.recipe)
        self.page.integrity_worker=worker
        result={
            "game_id":"valheim","checked":0,"status":"Review",
            "rows":[{"id":"loader","name":"BepInExPack","status":"Review",
                     "checked":0,"files":1,"reason":"test fixture",
                     "issues":[issue("BepInEx/config/BepInEx.cfg")]},
                    {"id":"vhvr","name":"VHVR","status":"Review",
                     "checked":0,"files":1,"reason":"test fixture",
                     "issues":[issue("valheim_Data/Managed/UnityEngine.SpatialTracking.dll")]}],
        }
        self.page._integrity_done(result,worker)
        displayed=self.page.integrity_details.toPlainText()
        self.assertIn("Possible local configuration change",displayed)
        self.assertIn("Binary bytes differ",displayed)
        self.assertIn("not a diagnosis",displayed)
        self.assertFalse(self.page._safety_result)
        self.page.integrity_worker=None

    def test_on_demand_safety_review_includes_triage_but_no_update_controls(self):
        # No SHA result: must show missing evidence instead of invented success.
        with mock.patch.object(triage,"assess",wraps=triage.assess) as probe:
            self.assertNotIn("OWNERSHIP RECONCILIATION",self.page.safety_details.toPlainText())
            before=(self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled())
            self.page.comparison_toggle.click()
            self.page.safety_button.click()
            for _ in range(400):
                if self.page.safety_worker is None:
                    break
                QTest.qWait(10)
            self.assertIsNone(self.page.safety_worker)
            probe.assert_called_once()
        result=self.page._safety_result
        self.assertFalse(result["triage"]["live_update_authorized"])
        self.assertEqual(result["triage"]["game_id"],"valheim")
        self.assertTrue(all(x["status"]=="Not checked" for x in result["triage"]["rows"]))
        display=self.page.safety_details.toPlainText()
        self.assertIn("OWNERSHIP RECONCILIATION & MODIFIED-FILE TRIAGE",display)
        self.assertIn("no installed files read again",display.lower())
        self.assertIn("REAL INSTALLATION READINESS AUDIT",display)
        self.assertIn("LIVE UPDATE DISABLED",display)
        self.assertEqual((self.page.install_review_button.text(),
                          self.page.install_review_button.isEnabled()),before)

    def test_game_switch_clears_old_review(self):
        self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(400):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNotNone(self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())


if __name__=="__main__":
    unittest.main()
