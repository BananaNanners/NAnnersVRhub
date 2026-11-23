# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-U — synthetic before/after and incomplete real-evidence safeguards."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import (hub, download_planner, preservation_decisions as policy,
                   update_manifest_preview as preview)
from vrhub.downloads_gui import GuidedDownloadsPage


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture():
    before={"BepInEx/config/custom.ini":b"locally-configured",
            "BepInEx/core/loader.dll":b"old-loader",
            "BepInEx/plugins/manual.dll":b"manual-user-file"}
    owners={"BepInEx/config/custom.ini":"loader",
            "BepInEx/core/loader.dll":"loader"}
    after={"BepInEx/config/custom.ini":b"future-default-config",
           "BepInEx/core/loader.dll":b"future-loader",
           "BepInEx/plugins/new-vr.dll":b"future-new"}
    candidate={n:"loader" for n in after}
    record={n:sha(before[n]) for n in owners}
    return before, after, owners, candidate, record


def worksheet(recipe):
    rows=[]
    for c in download_planner.plan_components(recipe):
        entries=[]
        if c["id"]=="loader":
            entries=[{
                "relative_file":"BepInEx/config/custom.ini",
                "observed_status":"Modified",
                "category":"possible_customization",
                "cause_confirmed":False,
                "permitted_mutation":False,
            }]
        rows.append({
            "id":c["id"],"name":c["name"],"owned_by_hub":True,
            "classification":"file_differences" if entries else "integrity_not_established",
            "unreported_issues":0,
            "reported_issues":entries,"live_update_authorized":False,
            "manual_files_adopted":False,
            "recorded_file_hashes_rewritten":False,
            "legacy_state_migrated":False,
        })
    triage={
        "game_id":recipe["id"],"rows":rows,
        "live_update_authorized":False,"manual_files_adopted":False,
        "recorded_file_hashes_rewritten":False,
        "legacy_state_migrated":False,
        "files_read_or_hashed_by_triage":False,
        "real_compatibility_verified":False,
    }
    return policy.assess(recipe,triage)


def safety(recipe, *, complete=False):
    rows=[]
    for c in download_planner.plan_components(recipe):
        if c["id"]=="guide":
            continue
        rows.append({
            "id":c["id"],"name":c["name"],"eligible":False,
            "backups_verified_for_update":False,
            "current_managed":0,"future_destinations":2 if complete else None,
            "future_sample":["mods/"+str(c["id"])+"-new.dll"] if complete else [],
            "ownership_conflicts":[],"untracked_collisions":[],
        })
    return {"game_id":recipe["id"],"authorized":False,
            "has_live_install_plan":False,"rows":rows}


class FixtureManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes=hub.load_recipes()

    def inspect(self, before=None, after=None, owners=None, candidate=None,
                recorded=None, **kw):
        a,b,c,d,e=fixture()
        return preview.compare_fixture(
            "valheim", a if before is None else before,
            b if after is None else after,
            c if owners is None else owners,
            d if candidate is None else candidate,
            e if recorded is None else recorded, **kw)

    def not_live(self, report):
        self.assertFalse(report["live_update_authorized"])
        self.assertFalse(report["files_modified"])
        self.assertFalse(report["backups_created"])
        self.assertFalse(report["preservation_enforced"])
        self.assertFalse(report["real_compatibility_verified"])
        self.assertIsNone(report["executable_plan"])
        self.assertEqual(report["evidence_level"],"synthetic_complete")
        self.assertTrue(all(not r["actual_file_modified"] and
                            not r["live_authorized"] for r in report["rows"]))

    def test_before_after_add_replace_untouched_manual(self):
        output=self.inspect()
        self.assertEqual(output["counts"]["add"],1)
        self.assertEqual(output["counts"]["replace"],2)
        self.assertEqual(output["counts"]["preserve_untouched"],1)
        self.assertEqual(output["files_before"],3)
        self.assertEqual(output["candidate_files"],3)
        unchanged=next(x for x in output["rows"]
                       if x["path"]=="BepInEx/plugins/manual.dll")
        self.assertEqual(unchanged["action"],"preserve_untouched")
        self.assertEqual(unchanged["before_sha256"],unchanged["hypothetical_after_sha256"])
        self.not_live(output)

    def test_preservation_worksheet_turns_config_replacement_into_hold(self):
        report=self.inspect(worksheet=worksheet(self.recipes["valheim"]))
        self.assertEqual(report["counts"]["preservation_hold"],1)
        held=next(x for x in report["rows"] if x["action"]=="preservation_hold")
        self.assertEqual(held["path"],"BepInEx/config/custom.ini")
        self.assertEqual(held["decision"],policy.PRESERVE)
        self.assertEqual(held["before_sha256"],held["hypothetical_after_sha256"])
        self.assertNotEqual(held["candidate_sha256"],held["hypothetical_after_sha256"])
        self.not_live(report)

    def test_even_consider_replacement_draft_does_not_overwrite_config(self):
        sheet=worksheet(self.recipes["valheim"])
        sheet["rows"][0]["draft_decision"]=policy.CONSIDER
        report=self.inspect(worksheet=sheet)
        self.assertEqual(report["counts"]["preservation_hold"],1)
        self.assertEqual(
            next(x for x in report["rows"] if x["action"]=="preservation_hold")["decision"],
            policy.CONSIDER)
        self.not_live(report)

    def test_preserve_binary_as_advisory_still_holds_candidate(self):
        before,after,owners,candidate,recorded=fixture()
        recipe=self.recipes["valheim"]
        sheet=worksheet(recipe)
        path="BepInEx/core/loader.dll"
        # A second decision for the same component still requires distinct file.
        template=copy.deepcopy(sheet["rows"][0])
        template["relative_file"]=path
        template["draft_decision"]=policy.INVESTIGATE
        sheet["rows"]=[sheet["rows"][0],template]
        result=self.inspect(worksheet=sheet)
        self.assertEqual(result["counts"]["preservation_hold"],2)
        self.not_live(result)

    def test_untracked_file_candidate_is_blocked(self):
        before,after,owners,candidate,recorded=fixture()
        after["BepInEx/plugins/manual.dll"]=b"not-my-mod"
        candidate["BepInEx/plugins/manual.dll"]="loader"
        result=self.inspect(after=after,candidate=candidate)
        self.assertEqual(result["counts"]["untracked_collision"],1)
        self.not_live(result)

    def test_other_component_owned_collision_is_blocked(self):
        before,after,owners,candidate,recorded=fixture()
        candidate["BepInEx/core/loader.dll"]="vhvr"
        result=self.inspect(candidate=candidate)
        self.assertEqual(result["counts"]["cross_component_collision"],1)
        self.not_live(result)

    def test_case_only_conflict_is_blocked(self):
        before,after,owners,candidate,recorded=fixture()
        value=after.pop("BepInEx/core/loader.dll")
        candidate.pop("BepInEx/core/loader.dll")
        after["bepinex/core/LOADER.DLL"]=value
        candidate["bepinex/core/LOADER.DLL"]="loader"
        result=self.inspect(after=after,candidate=candidate)
        self.assertEqual(result["counts"]["case_collision"],1)
        self.not_live(result)

    def test_parent_file_and_new_child_collision_blocked(self):
        before,after,owners,candidate,recorded=fixture()
        before["BepInEx/core/not-directory"]=b"manual-file"
        after["BepInEx/core/not-directory/new.dll"]=b"malicious-child"
        candidate["BepInEx/core/not-directory/new.dll"]="loader"
        result=self.inspect(before=before,after=after,candidate=candidate)
        self.assertEqual(result["counts"]["path_collision"],1)
        self.not_live(result)

    def test_file_candidate_where_old_path_has_child_is_blocked(self):
        before,after,owners,candidate,recorded=fixture()
        after["BepInEx"]=b"would-replace-directory"
        candidate["BepInEx"]="loader"
        result=self.inspect(after=after,candidate=candidate)
        self.assertGreaterEqual(result["counts"]["path_collision"],1)
        self.assertTrue(all(x["action"]=="path_collision" for x in result["rows"]
                            if x["path"]=="BepInEx"))

    def test_changed_owned_bytes_require_manual_review(self):
        before,after,owners,candidate,recorded=fixture()
        before["BepInEx/core/loader.dll"]=b"user-updated-it"
        result=self.inspect(before=before)
        self.assertEqual(result["counts"]["changed_owned_hold"],1)
        self.not_live(result)

    def test_candidate_equal_old_bytes_is_unchanged(self):
        before,after,owners,candidate,recorded=fixture()
        after["BepInEx/core/loader.dll"]=before["BepInEx/core/loader.dll"]
        result=self.inspect(after=after)
        self.assertEqual(result["counts"]["unchanged"],1)
        self.not_live(result)

    def test_uevr_retirement_is_hold_not_an_authorized_delete(self):
        from vrhub import uevr_profile_staging
        plan=uevr_profile_staging._scenario("fatekeeper")
        result=preview.compare_fixture(
            "fatekeeper",plan.current,plan.candidate,
            {n:"profile" for n in plan.current},
            {n:"profile" for n in plan.candidate},
            plan.recorded_sha256,retirements=plan.explicit_removals)
        self.assertEqual(result["counts"]["retirement_hold"],1)
        retirement=next(x for x in result["rows"] if x["action"]=="retirement_hold")
        self.assertEqual(retirement["path"],"user-mappings/settings.ini")
        self.assertEqual(retirement["before_sha256"],
                         retirement["hypothetical_after_sha256"])
        self.not_live(result)

    def test_retirement_of_manual_absent_or_replaced_is_rejected(self):
        for retired in (("BepInEx/plugins/manual.dll",),
                        ("not-present.dll",),
                        ("BepInEx/core/loader.dll",)):
            with self.subTest(retired=retired),self.assertRaises(ValueError):
                self.inspect(retirements=retired)
    def test_invalid_sha_or_incomplete_ownership_never_promoted(self):
        a,b,c,d,e=fixture()
        e.pop("BepInEx/config/custom.ini")
        with self.assertRaises(ValueError):
            self.inspect(recorded=e)
        a,b,c,d,e=fixture()
        e["BepInEx/core/loader.dll"]="not-a-sha"
        with self.assertRaises(ValueError):
            self.inspect(recorded=e)

    def test_invalid_bytes_paths_or_duplicate_casefold_inputs_rejected(self):
        a,b,c,d,e=fixture()
        b["BepInEx/new.txt"]="/home/user/private.txt"
        d["BepInEx/new.txt"]="loader"
        with self.assertRaises(ValueError):
            self.inspect(after=b,candidate=d)
        a,b,c,d,e=fixture()
        b["../outside.dll"]=b"outside"
        d["../outside.dll"]="loader"
        with self.assertRaises(ValueError):
            self.inspect(after=b,candidate=d)
        a,b,c,d,e=fixture()
        b["bepinex/core/LOADER.DLL"]=b"duplicate-case"
        d["bepinex/core/LOADER.DLL"]="loader"
        with self.assertRaises(ValueError):
            self.inspect(after=b,candidate=d)

    def test_unknown_game_or_forged_policy_rejected(self):
        a,b,c,d,e=fixture()
        with self.assertRaises(ValueError):
            preview.compare_fixture("other-game",a,b,c,d,e)
        sheet=worksheet(self.recipes["valheim"])
        for key in ("live_update_authorized","choices_saved",
                    "real_compatibility_verified","recorded_file_hashes_rewritten"):
            other=copy.deepcopy(sheet)
            other[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.inspect(worksheet=other)
        other=worksheet(self.recipes["valheim"])
        other["game_id"]="subnautica"
        with self.assertRaises(ValueError):
            self.inspect(worksheet=other)

    def test_foreign_file_or_component_decision_rejected(self):
        for change in ("file","component","authority"):
            sheet=worksheet(self.recipes["valheim"])
            row=sheet["rows"][0]
            if change=="file":
                row["relative_file"]="../secret"
            elif change=="component":
                row["component_id"]="not-a-component"
            else:
                row["replacement_authorized"]=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.inspect(worksheet=sheet)

    def test_six_synthetic_families_and_retirement_safeguards(self):
        summary=preview.rehearse_six_fixture_previews()
        self.assertEqual(summary["games"],6)
        self.assertEqual(summary["families"],{"pinned":3,"uevr":2,"cyberpunk":1})
        self.assertEqual(summary["holds"],2)
        self.assertTrue(summary["uevr_retirements_blocked"])
        self.assertTrue(summary["manual_files_preserved"])
        self.assertFalse(summary["real_game_files_modified"])
        self.assertFalse(summary["live_update_authorized"])
        for item in summary["examples"].values():
            self.not_live(item)

    def test_complete_model_pure_with_no_file_or_state_operations(self):
        a,b,c,d,e=fixture()
        before=copy.deepcopy((a,b,c,d,e))
        with (mock.patch.object(Path,"read_bytes",side_effect=AssertionError("read")),
              mock.patch.object(Path,"write_bytes",side_effect=AssertionError("write")),
              mock.patch.object(hub,"state",side_effect=AssertionError("state"))):
            result=preview.compare_fixture("valheim",a,b,c,d,e)
        self.assertEqual((a,b,c,d,e),before)
        self.not_live(result)


class RealReviewPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes=hub.load_recipes()

    def get(self,game="valheim",*,full=False):
        recipe=self.recipes[game]
        sheet=worksheet(recipe) if game=="valheim" else policy.assess(
            recipe, {
                "game_id":game,
                "rows":[{
                    "id":c["id"],"name":c["name"],
                    "reported_issues":[],"unreported_issues":0,
                    "owned_by_hub":False,
                    "live_update_authorized":False,
                    "manual_files_adopted":False,
                    "recorded_file_hashes_rewritten":False,
                    "legacy_state_migrated":False,
                } for c in download_planner.plan_components(recipe)],
                "live_update_authorized":False,
                "manual_files_adopted":False,"recorded_file_hashes_rewritten":False,
                "legacy_state_migrated":False,"files_read_or_hashed_by_triage":False,
                "real_compatibility_verified":False,
            })
        return recipe,safety(recipe,complete=full),sheet

    def assert_blocked(self,out):
        self.assertEqual(out["evidence_level"],"real_readonly_samples")
        self.assertFalse(out["candidate_mapping_complete"])
        self.assertFalse(out["live_update_authorized"])
        self.assertFalse(out["real_compatibility_verified"])
        self.assertFalse(out["files_read_or_modified"])
        self.assertTrue(out["no_real_before_after_hash_comparison"])
        self.assertIsNone(out["executable_plan"])
        self.assertTrue(all(not r["live_update_authorized"] for r in out["rows"]))

    def test_all_nine_recipes_and_27_components_are_only_samples(self):
        count=0
        for game in self.recipes:
            recipe,safe,sheet=self.get(game)
            output=preview.preview_from_review(recipe,safe,sheet)
            self.assertEqual(len(output["rows"]),
                             len(download_planner.plan_components(recipe)))
            self.assert_blocked(output)
            count+=len(output["rows"])
        self.assertEqual(count,27)

    def test_missing_mapping_never_converts_current_count_to_full_after(self):
        recipe,safe,sheet=self.get("cyberpunk-2077")
        safe["rows"][0]["current_managed"]=25
        result=preview.preview_from_review(recipe,safe,sheet)
        self.assertEqual(result["counts"]["mapping_incomplete"],15)
        self.assertFalse(result["candidate_mapping_complete"])
        self.assertEqual(result["rows"][0]["current_managed_count"],25)
        self.assertIsNone(result["rows"][0]["candidate_count"])

    def test_sampled_destinations_explicitly_remain_incomplete(self):
        recipe,safe,sheet=self.get("valheim",full=True)
        # The potential config preservation takes priority over a partial sample.
        report=preview.preview_from_review(recipe,safe,sheet)
        self.assertEqual(report["rows"][0]["status"],"preservation_review")
        self.assertEqual(report["rows"][1]["status"],"sample_only")
        self.assertEqual(report["rows"][1]["sample_paths"],["mods/vhvr-new.dll"])
        self.assert_blocked(report)

    def test_known_untracked_or_owner_overlap_blocks_preview(self):
        recipe,safe,sheet=self.get("valheim",full=True)
        safe["rows"][1]["untracked_collisions"]=["manual.dll"]
        report=preview.preview_from_review(recipe,safe,sheet)
        self.assertEqual(report["counts"]["known_conflict"],1)
        self.assertEqual(report["rows"][1]["known_conflicts"],["manual.dll"])
        self.assert_blocked(report)

    def test_shared_future_sample_target_flags_both_components(self):
        recipe,safe,sheet=self.get("valheim",full=True)
        safe["rows"][1]["future_sample"]=["MODS/LOADER-NEW.DLL"]
        report=preview.preview_from_review(recipe,safe,sheet)
        self.assertEqual(report["counts"]["known_conflict"],2)
        self.assertTrue(all(any("Shared sampled future target" in hint
                                for hint in row["known_conflicts"])
                            for row in report["rows"]))
        self.assert_blocked(report)

    def test_repeated_casefold_target_within_same_sample_fails_closed(self):
        recipe,safe,sheet=self.get("valheim",full=True)
        safe["rows"][0]["future_sample"]=[
            "mods/Loader-new.dll", "MODS/LOADER-NEW.DLL"]
        with self.assertRaisesRegex(ValueError,"Duplicate destination"):
            preview.preview_from_review(recipe,safe,sheet)

    def test_incomplete_or_forged_source_does_not_claim_ready(self):
        recipe,safe,sheet=self.get()
        safe["rows"].pop()
        with self.assertRaises(ValueError):
            preview.preview_from_review(recipe,safe,sheet)
        for key in ("authorized","has_live_install_plan"):
            recipe,safe,sheet=self.get()
            safe[key]=True
            with self.assertRaises(ValueError):
                preview.preview_from_review(recipe,safe,sheet)
        recipe,safe,sheet=self.get()
        sheet["game_id"]="subnautica"
        with self.assertRaises(ValueError):
            preview.preview_from_review(recipe,safe,sheet)

    def test_unsafe_sample_and_conflicting_count_refuse_report(self):
        for problem in ("unsafe","count","collision"):
            recipe,safe,sheet=self.get(full=True)
            if problem=="unsafe":safe["rows"][0]["future_sample"]=["../escape"]
            if problem=="count":safe["rows"][0]["future_destinations"]=0
            if problem=="collision":safe["rows"][0]["ownership_conflicts"]=["x"]*20
            with self.subTest(problem=problem),self.assertRaises(ValueError):
                preview.preview_from_review(recipe,safe,sheet)

    def test_manual_guide_uses_no_hypothetical_destinations(self):
        recipe,safe,sheet=self.get("skyrim-vr-mgo")
        report=preview.preview_from_review(recipe,safe,sheet)
        self.assertEqual(report["counts"]["manual_or_guide"],1)
        self.assert_blocked(report)

    def test_no_filesystem_access_for_real_evidence_view(self):
        recipe,safe,sheet=self.get("valheim",full=True)
        baseline=copy.deepcopy((recipe,safe,sheet))
        with (mock.patch.object(Path,"read_bytes",side_effect=AssertionError("file read")),
              mock.patch.object(Path,"write_bytes",side_effect=AssertionError("write")),
              mock.patch.object(hub,"state",side_effect=AssertionError("state read"))):
            result=preview.preview_from_review(recipe,safe,sheet)
        self.assertEqual((recipe,safe,sheet),baseline)
        self.assert_blocked(result)


class RealManifestGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="nanners-dev5d3u-qt-")
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        (root/"valheim").mkdir()
        for patched in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
            mock.patch.object(hub,"game_path",return_value=root/"valheim"),
        ):
            patched.start();self.addCleanup(patched.stop)
        self.page=GuidedDownloadsPage()
        self.page.show();self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["valheim"])

    def review(self):
        if not self.page.comparison_toggle.isChecked():
            self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(450):
            if self.page.safety_worker is None:break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertIsNotNone(self.page._safety_result)

    def test_existing_readonly_review_adds_no_install_buttons(self):
        with mock.patch.object(preview,"preview_from_review",
                               wraps=preview.preview_from_review) as probe:
            self.assertNotIn("PRESERVATION-AWARE UPDATE MANIFEST PREVIEW",
                             self.page.safety_details.toPlainText())
            old=(self.page.install_review_button.text(),
                 self.page.install_review_button.isEnabled())
            self.review()
            probe.assert_called_once()
        report=self.page._safety_result["manifest_preview"]
        self.assert_blocked_dummy(report)
        details=self.page.safety_details.toPlainText()
        self.assertIn("PRESERVATION-AWARE UPDATE MANIFEST PREVIEW",details)
        self.assertIn("SAMPLES only",details)
        self.assertIn("NOT a complete target manifest",details)
        self.assertIn("LIVE UPDATE DISABLED",details)
        self.assertEqual(old,(self.page.install_review_button.text(),
                              self.page.install_review_button.isEnabled()))

    def assert_blocked_dummy(self, report):
        self.assertFalse(report["candidate_mapping_complete"])
        self.assertFalse(report["live_update_authorized"])
        self.assertIsNone(report["executable_plan"])

    def test_switching_game_discards_partial_manifest(self):
        self.review()
        self.assertIn("manifest_preview",self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())

if __name__=="__main__":
    unittest.main()
