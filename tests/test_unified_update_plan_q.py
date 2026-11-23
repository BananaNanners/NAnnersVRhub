# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-Q unified review: deterministic, fail-closed and non-executable."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vrhub import (hub, download_planner as planner, update_integration,
                   unified_update_plan as unified, offline_transaction)
from vrhub.downloads_gui import GuidedDownloadsPage


def inputs(recipe):
    rid = recipe["id"]
    rows = [{
        "id": c["id"], "eligible": False,
        "backups_verified_for_update": False,
        "future_destinations": None,
        "ownership_conflicts": [], "untracked_collisions": [],
    } for c in planner.plan_components(recipe) if c["id"] != "guide"]
    safe = {
        "game_id": rid, "rows": rows, "authorized": False,
        "has_live_install_plan": False,
    }
    return safe, update_integration.assess(recipe, safety=safe)


def complete_one(recipe, cid):
    safe, integration = inputs(recipe)
    row = next(x for x in integration["contracts"] if x["id"] == cid)
    row.update({
        "recorded_ownership": True, "integrity_observed": True,
        "verified_future_candidate": True, "mapped_destinations": 2,
    })
    match = next(x for x in safe["rows"] if x["id"] == cid)
    match["future_destinations"] = 2
    return safe, integration


class UnifiedUpdatePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = hub.load_recipes()

    def check_not_live(self, report):
        self.assertFalse(report["authorized"])
        self.assertFalse(report["has_live_install_plan"])
        self.assertFalse(report["live_executor_connected"])
        self.assertTrue(report["requires_explicit_future_approval"])
        self.assertIn("LIVE UPDATE DISABLED", report["status"])
        self.assertEqual(len(report["outstanding_live_gates"]), 6)
        for row in report["rows"]:
            self.assertFalse(row["authorized"])
            self.assertFalse(row["live_executor_connected"])
            self.assertFalse(row["real_compatibility_verified"])
            self.assertFalse(row["fixture_run_on_this_installation"])
            self.assertTrue(row["requires_explicit_future_approval"])
            self.assertIn(row["code"], ("blocked", "needs_evidence", "manual"))

    def test_all_nine_games_and_27_components_have_one_plan_each(self):
        self.assertEqual(len(self.recipes), 9)
        total = 0
        for rid, recipe in self.recipes.items():
            with self.subTest(game=rid):
                safe, contracts = inputs(recipe)
                report = unified.assess(recipe, safe, contracts)
                self.check_not_live(report)
                self.assertEqual(report["game_id"], rid)
                self.assertEqual(
                    [r["id"] for r in report["rows"]],
                    [str(c["id"]) for c in planner.plan_components(recipe)])
                self.assertEqual(
                    sum(report["counts"].values()), len(report["rows"]))
                total += len(report["rows"])
        self.assertEqual(total, 27)

    def test_three_guide_only_workflows_stay_manual(self):
        for rid in ("doom-2016-gog", "skyrim-vr-mgo", "ready-or-not"):
            with self.subTest(game=rid):
                recipe = self.recipes[rid]
                safe, contracts = inputs(recipe)
                report = unified.assess(recipe, safe, contracts)
                self.assertEqual(report["counts"],{
                    "blocked":0, "needs_evidence":0, "manual":1})
                self.assertIn("manual",report["rows"][0]["next_step"].lower())
                self.check_not_live(report)

    def test_fatekeeper_and_hogwarts_separate_injector_and_profile(self):
        for rid in ("fatekeeper", "hogwarts-legacy"):
            with self.subTest(game=rid):
                recipe=self.recipes[rid]
                safe, contracts=inputs(recipe)
                report=unified.assess(recipe,safe,contracts)
                self.assertEqual([r["adapter"] for r in report["rows"]],
                                 ["uevr_injector","uevr_profile"])
                self.assertEqual([r["code"] for r in report["rows"]],
                                 ["manual","needs_evidence"])
                self.assertIn("whole profile",report["rows"][1]["offline_fixture_model"])
                self.check_not_live(report)

    def test_cyberpunk_all_15_independently_need_review(self):
        r=self.recipes["cyberpunk-2077"]
        safe, contracts=inputs(r)
        report=unified.assess(r,safe,contracts)
        self.assertEqual(len(report["rows"]),15)
        self.assertEqual(report["counts"]["needs_evidence"],15)
        self.assertEqual(set(x["adapter"] for x in report["rows"]),{"gameroot"})
        self.check_not_live(report)

    def test_pinned_package_family_has_model_not_real_compatibility(self):
        for rid in ("valheim","subnautica","elden-ring"):
            recipe=self.recipes[rid]
            safe,contracts=inputs(recipe)
            report=unified.assess(recipe,safe,contracts)
            self.assertTrue(all("Pinned package" in x["offline_fixture_model"]
                                for x in report["rows"]))
            self.check_not_live(report)

    def test_next_step_follows_evidence_priority(self):
        recipe=self.recipes["valheim"]
        safe, contracts=inputs(recipe)
        selected=contracts["contracts"][0]
        cid=selected["id"]
        def check(expected):
            report=unified.assess(recipe,safe,contracts)
            row=next(x for x in report["rows"] if x["id"]==cid)
            self.assertIn(expected,row["next_step"])
            self.check_not_live(report)
        check("provenance")
        selected["recorded_ownership"]=True
        check("Verify installed files")
        selected["integrity_observed"]=True
        check("Scan Downloads")
        selected["verified_future_candidate"]=True
        check("ZIP-to-target map")
        selected["mapped_destinations"]=2
        safenext=next(x for x in safe["rows"] if x["id"]==cid)
        safenext["future_destinations"]=2
        check("separate future milestone")

    def test_complete_recorded_evidence_still_blocked_for_live_execution(self):
        recipe=self.recipes["elden-ring"]
        cid=planner.plan_components(recipe)[0]["id"]
        safe, contracts=complete_one(recipe,cid)
        report=unified.assess(recipe,safe,contracts)
        self.assertEqual(report["rows"][0]["code"],"blocked")
        self.assertEqual(report["rows"][0]["observed_count"],4)
        self.assertIn("live replacement disabled",report["rows"][0]["label"])
        self.check_not_live(report)

    def test_explicit_cross_owner_collision_blocks_even_if_other_evidence_missing(self):
        recipe=self.recipes["cyberpunk-2077"]
        safe,contracts=inputs(recipe)
        safe["rows"][0]["ownership_conflicts"]=["manual overlap"]
        report=unified.assess(recipe,safe,contracts)
        self.assertEqual(report["rows"][0]["code"],"blocked")
        self.assertIn("overlapping",report["rows"][0]["next_step"].lower())
        self.assertEqual(report["counts"]["blocked"],1)
        self.check_not_live(report)

    def test_untracked_or_missing_collision_inventory_blocks(self):
        recipe=self.recipes["valheim"]
        for key, value in (
            ("untracked_collisions", ["manual.dll"]),
            ("untracked_collisions", None),
            ("ownership_conflicts", None),
        ):
            with self.subTest(key=key,value=value):
                safe,contracts=inputs(recipe)
                safe["rows"][0][key]=value
                report=unified.assess(recipe,safe,contracts)
                self.assertEqual(report["rows"][0]["code"],"blocked")
                self.assertFalse(report["rows"][0]["observed"]["target_mapping"])

    def test_nonmatching_target_count_never_is_observed(self):
        recipe=self.recipes["valheim"]
        cid=planner.plan_components(recipe)[0]["id"]
        safe, contracts=complete_one(recipe,cid)
        safe["rows"][0]["future_destinations"]=1
        report=unified.assess(recipe,safe,contracts)
        self.assertFalse(report["rows"][0]["observed"]["target_mapping"])
        self.assertIn("destination mapping",report["rows"][0]["label"])

    def test_missing_or_duplicate_safety_rows_refused(self):
        r=self.recipes["valheim"]
        safe,contracts=inputs(r)
        safe["rows"].pop()
        with self.assertRaisesRegex(ValueError,"missing"):
            unified.assess(r,safe,contracts)
        safe,contracts=inputs(r)
        safe["rows"].append(copy.deepcopy(safe["rows"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            unified.assess(r,safe,contracts)

    def test_missing_duplicate_extra_or_foreign_adapter_rows_refused(self):
        r=self.recipes["valheim"]
        safe,contracts=inputs(r)
        contracts["contracts"].pop()
        with self.assertRaisesRegex(ValueError,"incomplete"):
            unified.assess(r,safe,contracts)
        safe,contracts=inputs(r)
        contracts["contracts"].append(copy.deepcopy(contracts["contracts"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            unified.assess(r,safe,contracts)
        safe,contracts=inputs(r)
        contracts["contracts"][0]["id"]="not-an-actual-package"
        with self.assertRaisesRegex(ValueError,"unexpected"):
            unified.assess(r,safe,contracts)
        safe,contracts=inputs(r)
        contracts["contracts"][0]["adapter"]="unrecognized-executor"
        with self.assertRaisesRegex(ValueError,"Unknown"):
            unified.assess(r,safe,contracts)

    def test_cross_game_safety_or_adapter_is_rejected(self):
        r=self.recipes["fatekeeper"]
        for side in ("safety","integration"):
            with self.subTest(side=side):
                safe,contracts=inputs(r)
                (safe if side=="safety" else contracts)["game_id"]="hogwarts-legacy"
                with self.assertRaisesRegex(ValueError,"Cross-game"):
                    unified.assess(r,safe,contracts)

    def test_unauthorized_auth_flags_are_rejected_not_promoted(self):
        r=self.recipes["valheim"]
        for where,key in (
            ("safety","authorized"),("safety","has_live_install_plan"),
            ("integration","authorized"),("integration","live_executor_connected"),
            ("component","replacement_supported"),("component","authorized"),
            ("component","live_executor_connected"),("safetyrow","eligible"),
            ("safetyrow","backups_verified_for_update"),
        ):
            with self.subTest(where=where,key=key):
                safe, contracts=inputs(r)
                target=(
                    safe if where=="safety" else
                    contracts if where=="integration" else
                    contracts["contracts"][0] if where=="component" else
                    safe["rows"][0]
                )
                target[key]=True
                with self.assertRaises(ValueError):
                    unified.assess(r,safe,contracts)

    def test_doom_kharvox_manual_dependency_remains_covered(self):
        r=self.recipes["doom-2016-gog"]
        safe,contracts=inputs(r)
        self.assertEqual([x["id"] for x in safe["rows"]], ["kharvox"])
        report=unified.assess(r,safe,contracts)
        self.assertEqual(report["rows"][0]["id"],"kharvox")
        self.assertEqual(report["rows"][0]["code"],"manual")

    def test_manual_workflow_with_collision_is_blocked_not_hidden(self):
        r=self.recipes["doom-2016-gog"]
        safe,contracts=inputs(r)
        safe["rows"][0]["ownership_conflicts"]=["user-owned.dll"]
        report=unified.assess(r,safe,contracts)
        self.assertEqual(report["rows"][0]["code"],"blocked")
        self.assertEqual(report["counts"]["blocked"],1)
        self.check_not_live(report)

    def test_analyzer_does_no_io_and_does_not_change_inputs(self):
        recipe=self.recipes["cyberpunk-2077"]
        safe,contracts=inputs(recipe)
        before=copy.deepcopy((recipe,safe,contracts))
        from vrhub import bepinex, profile_safety
        with (mock.patch.object(hub,"install", side_effect=AssertionError("live")),
              mock.patch.object(hub,"install_many", side_effect=AssertionError("live")),
              mock.patch.object(bepinex,"install", side_effect=AssertionError("live")),
              mock.patch.object(profile_safety,"install",side_effect=AssertionError("live")),
              mock.patch.object(offline_transaction,"execute",side_effect=AssertionError("write"))):
            result=unified.assess(recipe,safe,contracts)
        self.assertEqual(before,(recipe,safe,contracts))
        self.check_not_live(result)

    def test_synthetic_unified_rehearsal_all_six_and_no_real_authority(self):
        r=unified.rehearse_unified_fixtures()
        self.assertEqual(r["families"],{
            "pinned_package":3,"uevr_profile":2,"gameroot":1})
        self.assertEqual(r["game_fixtures"],6)
        self.assertEqual(r["rollback_rehearsals"],6)
        self.assertTrue(r["fixture_only"])
        self.assertTrue(r["temporary_fixtures_discarded"])
        self.assertTrue(r["preserved_manual_files"])
        self.assertFalse(r["real_game_files_modified"])
        self.assertFalse(r["real_game_compatibility_verified"])
        self.assertFalse(r["live_update_authorized"])

    def test_incomplete_unified_fixture_rehearsal_fails_closed(self):
        from vrhub import pinned_staging
        with mock.patch.object(pinned_staging,"rehearse_pinned_packages",
                               return_value={"fixture_only":False}):
            with self.assertRaises(RuntimeError):
                unified.rehearse_unified_fixtures()


class UnifiedGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        for p in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.page=GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])

    def review(self):
        if not self.page.comparison_toggle.isChecked():
            self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for i in range(400):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)

    def test_only_explicit_safety_review_produces_unified_plan(self):
        with mock.patch.object(unified,"assess", wraps=unified.assess) as planner_fn:
            self.assertNotIn("UNIFIED UPDATE PLAN",self.page.safety_details.toPlainText())
            planner_fn.assert_not_called()
            before=(self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled())
            self.review()
            planner_fn.assert_called_once()
        self.assertIsNotNone(self.page._safety_result)
        combined=self.page._safety_result["unified"]
        self.assertEqual(combined["game_id"],"fatekeeper")
        self.assertEqual(combined["counts"]["manual"],1)
        self.assertEqual(combined["counts"]["needs_evidence"],1)
        self.assertFalse(combined["authorized"])
        report=self.page.safety_details.toPlainText()
        self.assertIn("UNIFIED UPDATE PLAN — REVIEW ONLY",report)
        self.assertIn("2 dependencies",report)
        self.assertIn("manual",report)
        self.assertIn("Next:",report)
        self.assertIn("UPDATE ADAPTER CONTRACTS",report)
        self.assertIn("PLANNING ONLY",report)
        self.assertEqual(before,(self.page.install_review_button.text(),
                                self.page.install_review_button.isEnabled()))

    def test_game_switch_and_online_refresh_invalidate_unified_plan(self):
        self.review()
        self.assertIn("unified",self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
        self.review()
        self.assertEqual(self.page._safety_result["unified"]["game_id"],
                         "cyberpunk-2077")
        self.page.set_online_results([])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
