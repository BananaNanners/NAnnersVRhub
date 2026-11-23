# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-F: conservative, read-only version comparison."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub import hub, archive_update_comparison as comp, archive_scans, download_planner
from vrhub.downloads_gui import GuidedDownloadsPage


from tests.fatekeeper_fixtures import recipes as fixture_recipes


class ComparisonModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def recipe(self, rid):
        return copy.deepcopy(fixture_recipes()[rid])

    def plan(self, recipe):
        rows = [
            {**c, "status": "Not found locally", "file": ""}
            for c in download_planner.plan_components(recipe)
        ]
        return {"rows": rows, "warning": None}

    def compare(self, recipe, plan, state=None, online=None):
        return comp.compare(recipe, plan, {} if state is None else state, online)

    def test_pinned_download_and_online_later_not_installed(self):
        recipe = self.recipe("valheim")
        plan = self.plan(recipe)
        row = plan["rows"][1]
        row.update(status="Pinned SHA-256 verified", file="/tmp/vhvr.zip")
        result = self.compare(recipe, plan, {}, [{
            "name": "VHVR (pinned GitHub build; review newer releases)",
            "latest_version": "v0.11.4", "status": "update"}])
        self.assertEqual(result[1]["installed"], "Unknown")
        self.assertEqual(result[1]["downloaded"], "Pinned SHA-256 · v0.11.2")
        self.assertEqual(result[1]["latest"], "v0.11.4")
        self.assertIn("newer upstream", result[1]["assessment"])
        self.assertIn("install unknown", result[1]["assessment"])
        self.assertTrue(result[1]["matched_release"])
        self.assertEqual(result[0]["latest"], "Not checked")

    def test_timestamps_cannot_prove_installed_version(self):
        recipe = self.recipe("subnautica")
        plan = self.plan(recipe)
        plan["rows"][1].update(
            status="Pinned SHA-256 verified", file="/tmp/SubmersedVR_0.2.1.zip")
        records = {"subnautica": {"installed_at": 9999999999, "files": ["/game/mod.dll"]}}
        result = self.compare(recipe, plan, records, [{
            "name": "SubmersedVR (pinned build; review before updating)",
            "status": "current", "latest_version": "0.2.1"}])
        self.assertEqual(result[1]["installed"], "Hub record · version unknown")
        self.assertIn("install unknown", result[1]["assessment"])
        self.assertIn("latest label matches", result[1]["assessment"])
        self.assertNotIn("installed version is current", result[1]["assessment"].lower())

    def test_fatekeeper_profile_github_not_assigned_to_injector(self):
        recipe = self.recipe("fatekeeper")
        plan = self.plan(recipe)
        plan["rows"][1].update(
            status="Possible archive — inspect first",
            file="/tmp/SLASHER-Win64-Shipping.zip",
            release_expected="v1.0.4",
            candidates=[{"file":"/tmp/SLASHER-Win64-Shipping.zip",
                         "sha256":"a"*64,"tags":["v1.0.4"],
                         "expected":True,"copies":1}])
        data = [{"name":"SLASHER-Win64-Shipping.zip",
                 "latest_version":"v1.0.4","status":"unknown"}]
        result = self.compare(recipe, plan, {}, data)
        self.assertEqual(result[1]["latest"], "v1.0.4")
        self.assertEqual(result[0]["latest"], "Not checked")
        self.assertEqual(result[1]["downloaded"], "Official v1.0.4 · review")
        self.assertIn("latest label matches", result[1]["assessment"])

    def test_hogwarts_injector_does_not_inherit_profile_source(self):
        recipe = self.recipe("hogwarts-legacy")
        result = self.compare(recipe, self.plan(recipe), {}, [
            {"name":"HogwartsLegacy.zip","latest_version":"v2.1.0"},
            {"name":"UEVR.zip","latest_version":"2026.10.01"}])
        self.assertEqual(result[0]["latest"], "Not checked")
        self.assertEqual(result[1]["latest"], "v2.1.0")

    def test_cyberpunk_filename_hint_is_unverified(self):
        recipe = self.recipe("cyberpunk-2077")
        plan = self.plan(recipe)
        record = next(x for x in plan["rows"] if x["id"] == "2380")
        record.update(status="Possible archive — inspect first",
                      file="/tmp/RED4ext-2380-1.31.1-xyz.zip")
        state = {"cyberpunk-2077":{"components":{"2380":{
            "archive":"RED4ext-2380-1.30.0.zip","files":["/game/example.dll"]}}}}
        result = next(x for x in self.compare(recipe,plan,state,[
            {"mod_id":2380,"name":"RED4ext","status":"update",
             "installed_version":"1.30.0","latest_version":"1.31.1"}
        ]) if x["id"] == "2380")
        self.assertEqual(result["installed"], "Recorded filename 1.30.0")
        self.assertIn("Filename suggests", result["downloaded"])
        self.assertFalse(result["matched_release"])
        self.assertEqual(result["assessment"], "Filename suggests newer · verify ZIP")
        self.assertIn("No cryptographic release identity", result["detail"])
        self.assertNotIn("Downloaded newer", result["assessment"])
        plan["rows"] = [dict(c, status="Not found locally", file="")
                        for c in download_planner.plan_components(recipe)]
        rec = next(x for x in plan["rows"] if x["id"] == "2380")
        rec.update(status="Possible archive — inspect first",
                   file="/tmp/RED4ext-2380-1.29.9-xyz.zip")
        older = next(x for x in self.compare(recipe,plan,state,[
            {"mod_id":2380,"name":"RED4ext","status":"update",
             "latest_version":"1.31.1"}]) if x["id"]=="2380")
        self.assertEqual(older["assessment"], "Filename suggests older · verify ZIP")

    def test_legacy_uevr_and_doom_unknown_installed(self):
        for rid in ("doom-2016-gog", "fatekeeper", "hogwarts-legacy"):
            recipe = self.recipe(rid)
            state = {rid: {"installed_at": 9999999999,
                           "files": ["/game/uevr/UEVRInjector.exe"]}}
            records = self.compare(recipe,self.plan(recipe),state,[{
                "name":"KHARVOX","latest_version":"v1.4a",
                "tested_version":"v1.4.0","status":"unknown"}])
            self.assertTrue(records)
            self.assertTrue(all(
                "version unknown" in x["installed"] or x["installed"] == "Unknown"
                for x in records))
            self.assertTrue(all("v1.4.0" not in x["installed"] for x in records))

    def test_stale_and_incomplete_scans_fail_closed(self):
        recipe = self.recipe("valheim")
        plan = self.plan(recipe)
        plan["rows"][1].update(status="Archive changed — rescan required",
                               file="/tmp/vhvr.zip",
                               candidates=[{"file":"/tmp/vhvr.zip",
                                            "sha256":"b"*64,"tags":["v0.11.3"],
                                            "expected":True}])
        result = self.compare(recipe,plan)[1]
        self.assertEqual(result["downloaded"], "Rescan needed")
        self.assertFalse(result["matched_release"])
        self.assertEqual(result["assessment"], "Scan / rescan needed")
        plan["warning"] = "Inventory limit reached"
        self.assertEqual(self.compare(recipe,plan)[1]["downloaded"],"Scan incomplete")

    def test_official_newer_digest_cannot_bypass_pin(self):
        recipe = self.recipe("valheim")
        plan = self.plan(recipe)
        plan["rows"][1].update(
            status="Hash mismatch — do not install", file="/tmp/vhvr.zip",
            release_expected="v0.11.3", release_review=True,
            candidates=[{"file":"/tmp/vhvr.zip",
                         "sha256":"a"*64,"tags":["v0.11.3"],
                         "expected":True,"copies":1}])
        row = self.compare(recipe,plan)[1]
        self.assertEqual(row["downloaded"], "Official v0.11.3 · pin blocked")
        self.assertEqual(row["assessment"], "New release · recipe pin blocked")
        plan["rows"][1]["release_review"] = False
        self.assertEqual(self.compare(recipe,plan)[1]["assessment"],"Verification blocked")

    def test_legacy_malformed_component_record_is_unknown(self):
        recipe = self.recipe("cyberpunk-2077")
        plan = self.plan(recipe)
        for state in (
            {"cyberpunk-2077":{"components":None}},
            {"cyberpunk-2077":{"components":["invalid"]}},
            {"cyberpunk-2077":{"components":{"2380":{"archive":None}}}},
        ):
            records = self.compare(recipe,plan,state,online=["invalid",None])
            self.assertEqual(len(records),len(recipe["components"]))
            self.assertTrue(all(item["installed"] in ("Unknown","Hub record · version unknown")
                                for item in records))

    def test_offline_errors_no_key_and_ambiguous_sources(self):
        recipe = self.recipe("ready-or-not")
        plan = self.plan(recipe)
        row = self.compare(recipe,plan,{},[{
            "mod_id":6914,"name":"VRO","status":"no_key"}])[0]
        self.assertEqual(row["latest"],"Unavailable")
        self.assertIn("Nexus key",row["detail"])
        self.assertEqual(self.compare(recipe,plan,{},None)[0]["latest"],"Not checked")
        duplicate = [
            {"mod_id":6914,"latest_version":"1.1.0"},
            {"mod_id":6914,"latest_version":"1.2.0"}]
        self.assertEqual(self.compare(recipe,plan,{},duplicate)[0]["latest"],"Not checked")


class ComparisonGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.down = self.root / "Downloads"
        self.down.mkdir()
        for ctx in (
            mock.patch.object(download_planner, "default_library", return_value=self.down),
            mock.patch.object(download_planner, "preferences_file", return_value=self.root/"prefs.json"),
            mock.patch.object(archive_scans, "snapshot_file", return_value=self.root/"scans.json"),
            mock.patch.object(hub, "state", return_value={}),
        ):
            ctx.start()
            self.addCleanup(ctx.stop)
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)

    def test_collapsed_independent_refresh_and_no_action_change(self):
        recipe = fixture_recipes()["valheim"]
        self.page.set_recipe(recipe)
        self.assertFalse(self.page.comparison_panel.isVisible())
        self.assertEqual(self.page.comparison_table.rowCount(), 2)
        self.assertEqual(self.page.comparison_table.item(1, 3).text(),"Not checked")
        action_before=(self.page.install_review_button.text(),
                       self.page.install_review_button.isEnabled())
        self.page.comparison_toggle.click()
        self.assertTrue(self.page.comparison_panel.isVisible())
        self.page.set_online_results([{
            "name":"VHVR (pinned GitHub build; review newer releases)",
            "latest_version":"v0.11.3","status":"update"}])
        self.assertEqual(self.page.comparison_table.item(1,3).text(),"v0.11.3")
        self.assertEqual(action_before,(
            self.page.install_review_button.text(),self.page.install_review_button.isEnabled()))
        self.page.set_recipe(fixture_recipes()["fatekeeper"])
        self.assertEqual(self.page.comparison_table.item(1,3).text(),"Not checked")
        self.page.comparison_toggle.click()
        self.assertFalse(self.page.comparison_panel.isVisible())

    def test_guide_without_dependencies_does_not_show_empty_comparison(self):
        self.page.set_recipe(fixture_recipes()["skyrim-vr-mgo"])
        self.assertTrue(self.page.comparison_toggle.isHidden())
        self.assertEqual(self.page.comparison_table.rowCount(),0)

    def test_model_rebuild_after_scan_without_online_fetch(self):
        recipe=fixture_recipes()["valheim"]
        self.page.set_recipe(recipe)
        self.page.set_online_results([{"name":"VHVR (pinned GitHub build; review newer releases)",
                                       "latest_version":"v0.11.4","status":"update"}])
        plan=download_planner.build_plan(recipe,(self.down,))
        plan["rows"][1].update(
            file=str(self.down/"vhvr.zip"), status="Pinned SHA-256 verified")
        self.page._last_plan=plan
        self.page._show_plan(plan)
        self.assertIn("Pinned SHA-256",self.page.comparison_table.item(1,2).text())
        self.assertEqual(self.page.comparison_table.item(1,3).text(),"v0.11.4")
        self.assertEqual(self.page.table.columnCount(),5)
