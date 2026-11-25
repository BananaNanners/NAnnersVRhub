# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-M — normalized non-executable installer integration contracts."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vrhub import hub, download_planner as planner, update_integration
from vrhub.downloads_gui import GuidedDownloadsPage


def proof(recipe, cid, *, count=1):
    return (
        [{"id": str(cid), "code": "candidate",
          "label": "Future update candidate · review"}],
        {"game_id": recipe["id"], "rows": [
            {"id": str(cid), "status": "Verified", "checked": count,
             "files": count}],
         "presence": {"status": "Ready", "required_bad": []}},
        {"game_id": recipe["id"],
         "authorized": False,
         "rows": [{"id": str(cid), "future_destinations": count,
                   "ownership_conflicts": [], "untracked_collisions": [],
                   "eligible": False, "backups_verified_for_update": False}]},
    )


class IntegrationContractsTests(unittest.TestCase):
    def setUp(self):
        self.recipes = hub.load_recipes()

    def check_blocked(self, answer):
        self.assertFalse(answer["authorized"])
        self.assertFalse(answer["live_executor_connected"])
        self.assertTrue(answer["requires_explicit_future_approval"])
        self.assertIn("blocked", answer["status"])
        for row in answer["contracts"]:
            self.assertFalse(row["authorized"])
            self.assertFalse(row["live_executor_connected"])
            self.assertFalse(row["replacement_supported"])
            self.assertTrue(row["requires_explicit_future_approval"])
            self.assertIn("live_executor", [x["id"] for x in row["requirements"]])
            self.assertTrue(any(x["id"] == "fresh_backup" and not x["observed"]
                                for x in row["requirements"]))
            self.assertTrue(any("authorization" in text for text in row["blockers"]))

    def test_all_nine_known_recipes_have_stable_nonexecuting_contracts(self):
        self.assertEqual(len(self.recipes), 9)
        expectations = {
            "cyberpunk-2077": ("gameroot", 15),
            "doom-2016-gog": ("manual", 1),
            "elden-ring": ("pinned_package", 1),
            "fatekeeper": ("uevr_profile", 2),
            "hogwarts-legacy": ("uevr_profile", 2),
            "ready-or-not": ("manual", 1),
            "skyrim-vr-mgo": ("manual", 1),
            "subnautica": ("pinned_package", 2),
            "valheim": ("pinned_package", 2),
        }
        for rid, recipe in self.recipes.items():
            with self.subTest(game=rid):
                ans = update_integration.assess(recipe)
                self.check_blocked(ans)
                self.assertEqual(len(ans["contracts"]), expectations[rid][1])
                self.assertEqual(
                    {c["id"] for c in ans["contracts"]},
                    {c["id"] for c in planner.plan_components(recipe)})
                if rid in ("fatekeeper", "hogwarts-legacy"):
                    self.assertEqual(
                        [c["adapter"] for c in ans["contracts"]],
                        ["uevr_injector", "uevr_profile"])
                else:
                    self.assertTrue(
                        all(c["adapter"] == expectations[rid][0]
                            for c in ans["contracts"]))

    def test_complete_pinned_evidence_never_authorizes_live_update(self):
        r = self.recipes["valheim"]
        cid = "loader"
        sha = next(p["sha256"] for p in r["packages"] if p["id"] == cid)
        record = {"valheim": {
            "installer": "vhvr-1",
            "keep": "/fixture/game",
            "file_hashes": {"BepInEx/core/BepInEx.dll": "a"*64},
            "packages": {cid: {
                "sha256": sha,
                "files": ["/fixture/game/BepInEx/core/BepInEx.dll"]}},
        }}
        decision, integrity, safety = proof(r, cid)
        ans = update_integration.assess(r, record, decision, integrity, safety)
        self.check_blocked(ans)
        row = next(x for x in ans["contracts"] if x["id"] == cid)
        self.assertTrue(row["recorded_ownership"])
        self.assertTrue(row["verified_future_candidate"])
        self.assertTrue(row["integrity_observed"])
        self.assertEqual(row["mapped_destinations"], 1)
        self.assertEqual(row["adapter"], "pinned_package")
        self.assertEqual(row["expected_installer"], "vhvr-1")
        self.assertEqual(row["contract_stage"], "Draft — not executable")
        self.assertEqual(len([req for req in row["requirements"]
                              if not req["observed"]]), 6)

    def test_mismatched_pin_and_legacy_record_fail_closed(self):
        r = self.recipes["valheim"]
        cid = "loader"
        dec, integrity, safety = proof(r, cid)
        state = {"valheim": {"installer": "vhvr-1",
                "keep":"/fixture/game",
                "packages": {cid: {
                    "sha256": "1"*64, "files": ["/fixture/game/BepInEx/core/BepInEx.dll"]}},
                "file_hashes":{"BepInEx/core/BepInEx.dll":"a"*64}}}
        row = update_integration.assess(r,state,dec,integrity,safety)["contracts"][0]
        self.assertFalse(row["recorded_ownership"])
        self.assertIn("pin changed", row["ownership_note"])
        state["valheim"]["installer"] = "vhvr-legacy"
        row = update_integration.assess(r,state,dec,integrity,safety)["contracts"][0]
        self.assertFalse(row["recorded_ownership"])
        self.assertIn("legacy", row["ownership_note"])

    def test_bepinex_and_ervr_use_distinct_record_markers(self):
        for rid,marker in (
            ("subnautica", "submersed-vr-1"),
            ("elden-ring", "ervr-1")):
            r = self.recipes[rid]
            comp = planner.plan_components(r)[0]
            state = {rid: {"installer": marker,"keep":"/fixture/game",
                           "packages": {comp["id"]: {
                               "sha256": comp["sha256"],
                               "files": ["/fixture/game/mods/plugin.dll"]}},
                           "file_hashes":{"mods/plugin.dll":"b"*64}}}
            with self.subTest(rid=rid):
                row = update_integration.assess(r,state)["contracts"][0]
                self.assertTrue(row["recorded_ownership"])
                self.assertEqual(row["expected_installer"], marker)
                self.assertFalse(row["replacement_supported"])

    def test_game_root_component_inventory_must_belong_to_root(self):
        r = self.recipes["cyberpunk-2077"]
        cid = str(r["components"][0]["nexus_mod"])
        dec, integrity, safety = proof(r,cid)
        state = {"cyberpunk-2077": {"installer": "gameroot-2",
                "keep":"/fixture/cyberpunk",
                "installed_sha256":{"bin/x64/plugin.dll":"c"*64},
                "components":{cid:{
                    "files":["/fixture/cyberpunk/bin/x64/plugin.dll"],
                    "archive":"archive.zip"}},
        }}
        ans = update_integration.assess(r,state,dec,integrity,safety)
        row = next(c for c in ans["contracts"] if c["id"] == cid)
        self.assertTrue(row["recorded_ownership"])
        self.assertTrue(row["integrity_observed"])
        self.assertEqual(row["adapter"], "gameroot")
        self.assertIn("Resolve Nexus ZIP wrappers", row["handoff"][0])
        self.assertFalse(row["authorized"])
        state["cyberpunk-2077"]["components"][cid]["files"] = [
            "/fixture/other/rogue.dll"]
        row = next(c for c in update_integration.assess(r,state,dec,integrity,safety)["contracts"]
                   if c["id"] == cid)
        self.assertFalse(row["recorded_ownership"])

    def test_uevr_profile_requires_complete_snapshot_and_injector_is_manual(self):
        r = self.recipes["fatekeeper"]
        dec, integrity, safety = proof(r,"profile")
        state = {"fatekeeper:profile": {
            "installer":"uevr-profile-2", "root":"/fixture/prefix/profile",
            "installed":{"exists": True,
                "files":{"config.txt":{"sha256":"a"*64,"size":5}},
                "dirs":[], "bytes":5},
            "original":{"exists":False, "files":{}, "dirs":[], "bytes":0},
        }}
        ans=update_integration.assess(r,state,dec,integrity,safety)
        injector, profile=ans["contracts"]
        self.assertEqual(injector["adapter"], "uevr_injector")
        self.assertFalse(injector["recorded_ownership"])
        self.assertEqual(profile["adapter"], "uevr_profile")
        self.assertEqual(profile["target_scope"], "wine-prefix-profile")
        self.assertTrue(profile["recorded_ownership"])
        self.assertTrue(profile["integrity_observed"])
        self.assertEqual(profile["mapped_destinations"], 1)
        self.assertIn("whole-directory", " ".join(profile["handoff"]))
        self.check_blocked(ans)
        state["fatekeeper:profile"]["installed"].pop("dirs")
        broken=update_integration.assess(r,state,dec,integrity,safety)
        self.assertFalse(broken["contracts"][1]["recorded_ownership"])

    def test_guide_and_ready_or_not_remain_manual(self):
        for rid in ("doom-2016-gog", "skyrim-vr-mgo", "ready-or-not"):
            with self.subTest(rid=rid):
                result = update_integration.assess(self.recipes[rid])
                self.assertEqual(result["drafts"], 0)
                self.assertEqual(result["manual"], 1)
                self.assertFalse(result["authorized"])
                self.assertEqual(result["contracts"][0]["contract_stage"],
                                 "Manual integration required")

    def test_cross_game_integrity_and_safety_are_not_reused(self):
        r=self.recipes["valheim"]
        cid="loader"
        dec, integrity, safety=proof(r,cid)
        integrity["game_id"]="subnautica"
        safety["game_id"]="elden-ring"
        ans=update_integration.assess(r,{},dec,integrity,safety)
        row=ans["contracts"][0]
        self.assertFalse(row["integrity_observed"])
        self.assertIsNone(row["mapped_destinations"])
        self.assertFalse(row["recorded_ownership"])

    def test_status_labels_or_zero_file_checks_cannot_fake_integrity(self):
        r=self.recipes["valheim"]
        dec,integrity,safety=proof(r,"loader")
        integrity["rows"][0]["files"]=0
        integrity["rows"][0]["checked"]=0
        ans=update_integration.assess(r,{},dec,integrity,safety)
        self.assertFalse(ans["contracts"][0]["integrity_observed"])
        integrity["rows"][0]["files"]=1
        integrity["rows"][0]["checked"]=1
        integrity["presence"]["status"]="Needs review"
        self.assertFalse(update_integration.assess(
            r,{},dec,integrity,safety)["contracts"][0]["integrity_observed"])

    def test_collisions_and_missing_future_mapping_fail_closed(self):
        r=self.recipes["valheim"]
        dec,integrity,safety=proof(r,"loader")
        safety["rows"][0]["ownership_conflicts"]=["mod.dll"]
        answer=update_integration.assess(r,{},dec,integrity,safety)
        self.assertIsNone(answer["contracts"][0]["mapped_destinations"])
        safety["rows"][0]["ownership_conflicts"]=[]
        safety["rows"][0]["future_destinations"]=None
        self.assertIsNone(update_integration.assess(
            r,{},dec,integrity,safety)["contracts"][0]["mapped_destinations"])

    def test_unsafe_or_noncanonical_owned_paths_are_not_accepted(self):
        r=self.recipes["valheim"]
        comp=planner.plan_components(r)[0]
        state={"valheim":{"installer":"vhvr-1","keep":"/fixture/game",
                          "file_hashes":{"BepInEx/core/mod.dll":"a"*64},
                          "packages":{comp["id"]:{
                              "sha256":comp["sha256"],
                              "files":["/fixture/game/BepInEx/core/mod.dll"]}}}}
        self.assertTrue(update_integration.assess(
            r,state)["contracts"][0]["recorded_ownership"])
        for injected in (
            "/fixture/game/BepInEx/../outside.dll",
            "/fixture/game/./mod.dll",
            "/fixture/game/else.dll",
            "/fixture/game//mod.dll",
            "/fixture/other/mod.dll",
        ):
            with self.subTest(path=injected):
                state["valheim"]["packages"][comp["id"]]["files"]=[injected]
                self.assertFalse(update_integration.assess(
                    r,state)["contracts"][0]["recorded_ownership"])

    def test_profile_inconsistent_size_and_directory_inventory_are_refused(self):
        r=self.recipes["fatekeeper"]
        state={"fatekeeper:profile":{"installer":"uevr-profile-2",
               "root":"/fixture/prefix/profile",
               "installed":{"exists":True,
                   "files":{"settings.ini":{"sha256":"a"*64,"size":8}},
                   "dirs":["configs"],"bytes":8}}}
        self.assertTrue(update_integration.assess(
            r,state)["contracts"][1]["recorded_ownership"])
        for bad_dirs in (["../profile"],["configs","CONFIGS"],["settings.ini"]):
            with self.subTest(dirs=bad_dirs):
                state["fatekeeper:profile"]["installed"]["dirs"]=bad_dirs
                self.assertFalse(update_integration.assess(
                    r,state)["contracts"][1]["recorded_ownership"])
        state["fatekeeper:profile"]["installed"]["dirs"]=["configs"]
        state["fatekeeper:profile"]["installed"]["bytes"]=99
        self.assertFalse(update_integration.assess(
            r,state)["contracts"][1]["recorded_ownership"])

    def test_conflicting_duplicate_readiness_is_never_promoted(self):
        r=self.recipes["valheim"]
        decision,integrity,safety=proof(r,"loader")
        decision.append({"id":"loader","code":"candidate"})
        ans=update_integration.assess(r,{},decision,integrity,safety)
        self.assertFalse(ans["contracts"][0]["verified_future_candidate"])
        self.assertFalse(ans["authorized"])

    def test_readonly_contract_never_invokes_existing_live_installers(self):
        from vrhub import bepinex, profile_safety, offline_transaction
        probes=(mock.patch.object(hub,"install",side_effect=AssertionError("live install")),
                mock.patch.object(hub,"install_many",side_effect=AssertionError("live install")),
                mock.patch.object(bepinex,"install",side_effect=AssertionError("live install")),
                mock.patch.object(profile_safety,"install",side_effect=AssertionError("live install")),
                mock.patch.object(offline_transaction,"execute",side_effect=AssertionError("executor")))
        with probes[0], probes[1], probes[2], probes[3], probes[4]:
            for recipe in self.recipes.values():
                answer=update_integration.assess(recipe)
                self.check_blocked(answer)

    def test_no_input_mutation_or_file_side_effects(self):
        r=self.recipes["fatekeeper"]
        dec,integrity,safety=proof(r,"profile")
        state={"fatekeeper:profile":{"installer":"unknown"}}
        data=(copy.deepcopy(r),copy.deepcopy(state),copy.deepcopy(dec),
              copy.deepcopy(integrity),copy.deepcopy(safety))
        update_integration.assess(r,state,dec,integrity,safety)
        self.assertEqual(data,(r,state,dec,integrity,safety))

    def test_synthetic_adapter_rehearsal_all_three_transaction_paths(self):
        result=update_integration.fixture_adapter_rehearsal()
        self.assertTrue(result["fixture_only"])
        self.assertTrue(result["temporary_fixtures_discarded"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["real_game_files_modified"])
        self.assertFalse(result["live_executor_connected"])
        self.assertEqual(
            [x["adapter"] for x in result["tests"]],
            ["pinned_package","uevr_profile","gameroot"])
        self.assertTrue(all(x["fixture_recovered"] and
                            x["directory_topology_restored"] and
                            not x["authorized"] for x in result["tests"]))


class IntegrationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        for patch in (
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"scans.json"),
            mock.patch.object(hub,"state",return_value={}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.page=GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])

    def _clicked(self):
        self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(400):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)

    def test_only_explicit_safety_review_generates_integration_contract(self):
        with mock.patch.object(update_integration,"assess",
                               wraps=update_integration.assess) as adapter:
            self.assertNotIn("UPDATE ADAPTER CONTRACTS",
                             self.page.safety_details.toPlainText())
            self.assertEqual(self.page.safety_summary.text(),
                             "File replacement: not reviewed.")
            adapter.assert_not_called()
            before=(self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled())
            self._clicked()
            adapter.assert_called_once()
        result=self.page._safety_result
        self.assertIsNotNone(result)
        self.assertEqual(result["integration"]["game_id"],"fatekeeper")
        self.assertFalse(result["integration"]["authorized"])
        self.assertFalse(result["integration"]["live_executor_connected"])
        self.assertIn("UPDATE ADAPTER CONTRACTS",self.page.safety_details.toPlainText())
        self.assertIn("UEVR profile",self.page.safety_details.toPlainText())
        self.assertIn("manual workflow",self.page.safety_details.toPlainText())
        self.assertIn("No changes made",self.page.safety_summary.text())
        self.assertEqual(
            (self.page.install_review_button.text(),
             self.page.install_review_button.isEnabled()),before)

    def test_game_switch_or_online_refresh_drops_contract(self):
        self._clicked()
        self.assertIsNotNone(self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["valheim"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
        self._clicked()
        self.page.set_online_results([])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
