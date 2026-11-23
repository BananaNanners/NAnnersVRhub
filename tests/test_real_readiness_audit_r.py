# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-R — read-only real-installation evidence and fail-closed audit tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vrhub import (hub, download_planner, real_readiness_audit as audit,
                   update_integration, offline_transaction)
from vrhub.downloads_gui import GuidedDownloadsPage


class ReadOnlyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = hub.load_recipes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nanners-dev5d3r-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game_dirs = {rid: self.root / rid for rid in self.recipes}
        for path in self.game_dirs.values():
            path.mkdir()
        self.profile_dirs = {
            rid: self.game_dirs[rid] / "profile"
            for rid in ("fatekeeper", "hogwarts-legacy")}
        for p in self.profile_dirs.values():
            p.mkdir()

    def game(self, recipe):
        return self.game_dirs[recipe["id"]]

    def profile(self, recipe):
        return self.profile_dirs[recipe["id"]]

    def inspect(self, rid, state=None, **overrides):
        return audit.audit_game(
            self.recipes[rid], {} if state is None else state,
            game_locator=self.game, profile_locator=self.profile,
            **overrides)

    def pinned_record(self, rid):
        recipe = self.recipes[rid]
        comp = recipe["packages"][0]
        name = "mods/sample.dll"
        path = str(self.game_dirs[rid] / name)
        marker = {"valheim":"vhvr-1","subnautica":"submersed-vr-1",
                  "elden-ring":"ervr-1"}[rid]
        return {rid: {
            "installer": marker, "keep":str(self.game_dirs[rid]),
            "packages": {comp["id"]: {
                "sha256":comp["sha256"], "files":[path]}},
            "file_hashes":{name:"a"*64}}}, comp["id"]

    def profile_record(self, rid):
        return {rid+":profile":{
            "installer":"uevr-profile-2",
            "root":str(self.profile_dirs[rid]),
            "installed":{"exists":True,"bytes":8,"dirs":["scripts"],
                         "files":{"config.txt":{"sha256":"b"*64,"size":8}}},
        }}

    def assert_never_live(self, report):
        self.assertFalse(report["authorized"])
        self.assertFalse(report["real_installer_connected"])
        self.assertTrue(report["requires_separate_live_approval"])
        self.assertIn("LIVE UPDATE DISABLED", report["status"])
        self.assertEqual(len(report["live_gates"]),6)
        self.assertTrue(all(not x["verified"] for x in report["live_gates"]))
        for item in report["rows"]:
            self.assertFalse(item["authorized"])
            self.assertFalse(item["live_executor_connected"])
            self.assertFalse(item["fresh_preupdate_backup"])
            self.assertFalse(item["exclusive_game_lock_verified"])
            self.assertFalse(item["production_recovery_verified"])
            self.assertFalse(item["real_compatibility_verified"])

    def test_nine_games_27_dependency_inventory_and_no_live_authority(self):
        result=audit.audit_all(self.recipes,{},game_locator=self.game,
                               profile_locator=self.profile)
        self.assertEqual(result["games_audited"],9)
        self.assertEqual(result["dependencies_audited"],27)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["live_update_enabled"])
        for rid,r in result["games"].items():
            with self.subTest(game=rid):
                self.assertEqual(r["game_id"],rid)
                self.assertEqual(
                    {x["id"] for x in r["rows"]},
                    {c["id"] for c in download_planner.plan_components(self.recipes[rid])})
                self.assert_never_live(r)

    def test_package_record_is_bound_to_discovered_root_not_to_current_hashes(self):
        for rid in ("valheim","subnautica","elden-ring"):
            with self.subTest(game=rid):
                state,cid=self.pinned_record(rid)
                r=self.inspect(rid,state)
                row=next(x for x in r["rows"] if x["id"]==cid)
                self.assertTrue(row["root_bound_ownership"])
                self.assertTrue(row["hub_recorded_ownership"])
                self.assertEqual(row["integrity"],"not_checked")
                self.assertEqual(row["verdict"],"needs_evidence")
                self.assertIn("Verify installed files",row["next_step"])
                self.assert_never_live(r)

    def test_root_found_does_not_mean_installation_is_owned(self):
        r=self.inspect("cyberpunk-2077")
        self.assertEqual(r["game_location"],"directory")
        self.assertTrue(all(not x["root_bound_ownership"] for x in r["rows"]))
        self.assertEqual(r["counts"]["needs_evidence"],15)
        self.assert_never_live(r)

    def test_legacy_cyberpunk_components_not_silently_adopted(self):
        state={"cyberpunk-2077":{
            "keep":str(self.game_dirs["cyberpunk-2077"]),
            "components":{"107":{"files":["some/file.dll"]}},
            "installed_at":123456,
        }}
        r=self.inspect("cyberpunk-2077",state)
        self.assertEqual(r["game_record_marker"],"legacy_or_unclassified")
        self.assertTrue(r["game_record_present"])
        self.assertTrue(all(not x["root_bound_ownership"] for x in r["rows"]))
        self.assertEqual(r["counts"]["needs_evidence"],15)

    def test_untrusted_marker_values_never_leak_or_crash(self):
        state={"valheim":{"installer":["sensitive-value"],"keep":"/other"}}
        r=self.inspect("valheim",state)
        self.assertEqual(r["game_record_marker"],"legacy_or_unclassified")
        self.assertNotIn("sensitive-value",json.dumps(r))

    def test_missing_game_location_blocks_even_manual_workflows(self):
        rid="ready-or-not"
        r=audit.audit_game(self.recipes[rid],{},
                           game_locator=lambda _: self.root/"missing")
        self.assertEqual(r["game_location"],"missing")
        self.assertEqual(r["rows"][0]["verdict"],"blocked")
        self.assertIn("target_location_unconfirmed",r["rows"][0]["blockers"])

    def test_symlinked_game_root_not_accepted_as_identity(self):
        actual=self.root/"real"
        actual.mkdir()
        fake=self.root/"link"
        fake.symlink_to(actual,target_is_directory=True)
        rid="valheim"
        state,_=self.pinned_record(rid)
        state[rid]["keep"]=str(fake)
        report=audit.audit_game(
            self.recipes[rid],state,game_locator=lambda _:fake)
        self.assertEqual(report["game_location"],"symlink")
        self.assertEqual(report["counts"]["blocked"],2)
        self.assertFalse(any(x["root_bound_ownership"] for x in report["rows"]))

    def test_file_instead_of_directory_never_is_profile_identity(self):
        rid="fatekeeper"
        file=self.root/"profile-file"
        file.write_bytes(b"not a directory")
        state=self.profile_record(rid)
        r=audit.audit_game(self.recipes[rid],state,
                           game_locator=self.game,
                           profile_locator=lambda _:file)
        self.assertEqual(r["profile_location"],"not_directory")
        row=next(x for x in r["rows"] if x["id"]=="profile")
        self.assertEqual(row["verdict"],"blocked")

    def test_matching_uevr_profile_root_and_manifest_still_need_hash_check(self):
        for rid in ("fatekeeper","hogwarts-legacy"):
            with self.subTest(game=rid):
                report=self.inspect(rid,self.profile_record(rid))
                self.assertEqual(
                    [x["adapter"] for x in report["rows"]],
                    ["uevr_injector","uevr_profile"])
                self.assertEqual(report["rows"][0]["verdict"],"manual")
                self.assertTrue(report["rows"][1]["root_bound_ownership"])
                self.assertEqual(report["rows"][1]["verdict"],"needs_evidence")
                self.assert_never_live(report)

    def test_profile_missing_despite_record_is_blocked(self):
        rid="fatekeeper"
        self.profile_dirs[rid].rmdir()
        report=self.inspect(rid,self.profile_record(rid))
        self.assertEqual(report["profile_location"],"missing")
        self.assertEqual(report["rows"][1]["verdict"],"blocked")
        self.assertFalse(report["rows"][1]["root_bound_ownership"])

    def test_profile_record_does_not_certify_uevr_injector(self):
        r=self.inspect("fatekeeper",self.profile_record("fatekeeper"))
        self.assertEqual(r["rows"][0]["adapter"],"uevr_injector")
        self.assertFalse(r["rows"][0]["root_bound_ownership"])
        self.assertEqual(r["rows"][0]["verdict"],"manual")

    def test_path_mismatch_blocks_even_with_recorded_package_hashes(self):
        state,cid=self.pinned_record("valheim")
        state["valheim"]["keep"]=str(self.root/"other")
        report=self.inspect("valheim",state)
        row=next(x for x in report["rows"] if x["id"]==cid)
        # Even structurally valid pinned-package data becomes untrusted when
        # its recorded root changes. The hard stop must still be visible.
        self.assertFalse(row["hub_recorded_ownership"])
        self.assertFalse(row["root_identity_matches"])
        self.assertEqual(row["verdict"],"blocked")
        self.assertIn("root_identity_mismatch",row["blockers"])

    def test_traversal_or_foreign_record_root_never_treated_as_safe(self):
        path=self.game_dirs["valheim"]
        for entry in (str(path)+"/../valheim",str(path)+"//",
                      "/tmp/elsewhere","relative/valheim",str(path)+"\bad"):
            with self.subTest(entry=entry):
                self.assertFalse(audit._identity(path,entry))

    def test_prior_verified_hash_is_not_current_live_compatibility(self):
        state,cid=self.pinned_record("valheim")
        rows=[{"id":cid,"status":"Verified","checked":1,"files":1}]
        report=self.inspect("valheim",state,
                            integrity={"game_id":"valheim","rows":rows})
        row=next(x for x in report["rows"] if x["id"]==cid)
        self.assertEqual(row["integrity"],"verified_at_prior_check")
        self.assertEqual(row["verdict"],"blocked")
        self.assertIn("prior check",row["next_step"])
        self.assert_never_live(report)

    def test_prior_modified_or_missing_hash_blocks_update(self):
        state,cid=self.pinned_record("valheim")
        rows=[{"id":cid,"status":"Review","checked":0,"files":1}]
        report=self.inspect("valheim",state,
                            integrity={"game_id":"valheim","rows":rows})
        row=next(x for x in report["rows"] if x["id"]==cid)
        self.assertEqual(row["verdict"],"blocked")
        self.assertIn("prior_integrity_needs_review",row["blockers"])

    def test_fake_verified_zero_file_and_cross_game_hash_not_trusted(self):
        state,cid=self.pinned_record("valheim")
        for inp in (
            {"game_id":"valheim","rows":[{"id":cid,"status":"Verified",
                                          "checked":0,"files":0}]},
            {"game_id":"subnautica","rows":[{"id":cid,"status":"Verified",
                                            "checked":1,"files":1}]},
            {"game_id":"valheim","rows":[{"id":cid,"status":"Verified",
                                          "checked":1,"files":1}]*2},
        ):
            with self.subTest(inp=inp):
                r=self.inspect("valheim",state,integrity=inp)
                found=next(x for x in r["rows"] if x["id"]==cid)
                self.assertNotEqual(found["integrity"],"verified_at_prior_check")
                self.assertFalse(found["authorized"])

    def test_retained_originals_is_not_a_fresh_backup(self):
        r=self.recipes["valheim"]
        state,cid=self.pinned_record("valheim")
        integration=update_integration.assess(r,state=state)
        for status,label in (
            ("Recorded originals matched","prior_originals_verified"),
            ("No prior originals","no_prior_originals"),
            ("Needs review","needs_review"),
        ):
            with self.subTest(status=status):
                safe={"game_id":"valheim","authorized":False,
                      "has_live_install_plan":False,
                      "existing_backup":{"status":status}}
                report=self.inspect("valheim",state,safety=safe,
                                    integration=integration)
                self.assertEqual(report["retained_originals"],label)
                self.assertTrue(all(not x["fresh_preupdate_backup"]
                                    for x in report["rows"]))

    def test_forged_source_record_ownership_is_rejected(self):
        rid="valheim"
        state,cid=self.pinned_record(rid)
        fabricated=update_integration.assess(self.recipes[rid],state=state)
        fabricated["contracts"][0]["recorded_ownership"]=False
        with self.assertRaisesRegex(ValueError,"contradictory recorded ownership"):
            self.inspect(rid,state,integration=fabricated)
        fabricated=update_integration.assess(self.recipes[rid],state={})
        fabricated["contracts"][0]["recorded_ownership"]=True
        with self.assertRaisesRegex(ValueError,"contradictory recorded ownership"):
            self.inspect(rid,{},integration=fabricated)

    def test_cross_game_safety_report_rejected(self):
        state,_=self.pinned_record("valheim")
        with self.assertRaisesRegex(ValueError,"Cross-game"):
            self.inspect("valheim",state,safety={
                "game_id":"subnautica","authorized":False,
                "has_live_install_plan":False})

    def test_live_authority_or_duplicate_contract_rejected(self):
        recipe=self.recipes["valheim"]
        state,_=self.pinned_record("valheim")
        integ=update_integration.assess(recipe,state=state)
        integ["contracts"].append(copy.deepcopy(integ["contracts"][0]))
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            self.inspect("valheim",state,integration=integ)
        integ=update_integration.assess(recipe,state=state)
        integ["contracts"][0]["authorized"]=True
        with self.assertRaisesRegex(ValueError,"Contradictory"):
            self.inspect("valheim",state,integration=integ)

    def test_missing_untrusted_locator_and_game_record_do_not_crash(self):
        for exception in (RuntimeError("no Steam root"),PermissionError("missing")):
            with self.subTest(exception=exception):
                def fail(_):
                    raise exception
                r=audit.audit_game(self.recipes["valheim"],{},
                                   game_locator=fail)
                self.assertEqual(r["game_location"],"unavailable")
                self.assertEqual(r["counts"]["blocked"],2)

    def test_audit_only_lstats_known_root_and_never_reads_mod_contents(self):
        rid="valheim"
        state,cid=self.pinned_record(rid)
        record=copy.deepcopy(state)
        recipe=copy.deepcopy(self.recipes[rid])
        with (mock.patch.object(Path,"read_bytes",
                                side_effect=AssertionError("opened file contents")),
              mock.patch.object(Path,"write_bytes",
                                side_effect=AssertionError("wrote file contents")),
              mock.patch.object(hub,"install",side_effect=AssertionError("live install")),
              mock.patch.object(hub,"state",side_effect=AssertionError("state retrieval")),
              mock.patch.object(offline_transaction,"execute",
                                side_effect=AssertionError("fixture execution"))):
            report=self.inspect(rid,state)
        self.assert_never_live(report)
        self.assertEqual(record,state)
        self.assertEqual(recipe,self.recipes[rid])
        self.assertNotIn(str(self.root),json.dumps(report))
        self.assertNotIn(str(self.game_dirs[rid]),json.dumps(report))

    def test_marker_or_unrecognized_component_shape_fails_closed(self):
        recipe=copy.deepcopy(self.recipes["cyberpunk-2077"])
        record=update_integration.assess(recipe,state={})
        record["contracts"][0]["adapter"]="magically-automatic"
        with self.assertRaisesRegex(ValueError,"Unknown updater"):
            audit.audit_game(recipe,{},integration=record,
                             game_locator=self.game)


class RealAuditGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="nanners-dev5d3r-qt-")
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        (root/"fatekeeper").mkdir()
        (root/"fatekeeper/profile").mkdir()
        for p in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
            mock.patch.object(hub,"game_path",return_value=root/"fatekeeper"),
            mock.patch.object(hub,"profile_dir",return_value=root/"fatekeeper/profile"),
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
        for _ in range(400):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertIsNotNone(self.page._safety_result)

    def test_on_demand_review_appends_real_audit_but_not_live_action(self):
        with mock.patch.object(audit,"audit_game",wraps=audit.audit_game) as probe:
            self.assertNotIn("REAL INSTALLATION READINESS AUDIT",
                             self.page.safety_details.toPlainText())
            before=(self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled())
            probe.assert_not_called()
            self.review()
            probe.assert_called_once()
        result=self.page._safety_result["real_audit"]
        self.assertEqual(result["game_id"],"fatekeeper")
        self.assertFalse(result["authorized"])
        self.assertFalse(result["real_installer_connected"])
        lines=self.page.safety_details.toPlainText()
        self.assertIn("REAL INSTALLATION READINESS AUDIT",lines)
        self.assertIn("SHA not checked",lines)
        self.assertIn("UNIFIED UPDATE PLAN",lines)
        self.assertIn("LIVE UPDATE DISABLED",lines)
        self.assertIn("fresh verified backup",lines)
        self.assertEqual(before,(self.page.install_review_button.text(),
                                 self.page.install_review_button.isEnabled()))

    def test_game_switch_and_online_refresh_drop_point_in_time_audit(self):
        self.review()
        self.assertIn("real_audit",self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["valheim"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
        self.review()
        self.assertEqual(self.page._safety_result["real_audit"]["game_id"],
                         "valheim")
        self.page.set_online_results([])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())


if __name__=="__main__":
    unittest.main()
