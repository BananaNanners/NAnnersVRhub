# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-G: explicit installed version provenance without touching live games."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication

from vrhub import hub, download_planner as planner
from vrhub import archive_update_comparison, installed_provenance as provenance
from vrhub.downloads_gui import GuidedDownloadsPage


class ProvenanceModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def recipe(self, rid):
        return copy.deepcopy(hub.load_recipes()[rid])

    def part(self, recipe, comp_id):
        return next(c for c in planner.plan_components(recipe) if c["id"] == comp_id)

    def package_state(self, recipe, names=None):
        marker = {"valheim": "vhvr-1", "subnautica": "submersed-vr-1",
                  "elden-ring": "ervr-1"}[recipe["id"]]
        return {recipe["id"]: {
            "installer": marker,
            "installed_at": 99999999,
            "packages": {
                p["id"]: {"archive": "renamed-archive.zip",
                          "sha256": p["sha256"],
                          "files": ["/fixture/game/mod.dll"]}
                for p in recipe["packages"]
            },
        }}

    def profile_state(self, recipe, sha="a"*64):
        return {recipe["id"]+":profile": {
            "installer": "uevr-profile-2",
            "archive_sha256": sha,
            "installed": {"exists": True,
                          "files": {"config.txt": {"size": 10,"sha256": "c"*64}},
                          "dirs": [], "bytes": 10},
            "installed_at": 9999999,
        }}

    def official_profile_row(self, sha="a"*64, tag="v2.0.6"):
        return {
            "id": "profile", "status": "Possible archive — inspect first",
            "file": "/fixture/Downloads/HogwartsLegacy.zip",
            "candidate_incomplete": False, "ambiguous": False,
            "candidates": [{
                "file": "/fixture/Downloads/HogwartsLegacy.zip",
                "sha256": sha, "tags": [tag],
                "expected": True, "copies": 1}],
        }

    def test_subnautica_each_recorded_pinned_release_is_attributable(self):
        recipe = self.recipe("subnautica")
        state = self.package_state(recipe)
        for id_, tag in (("loader", "v5.4.23-pack.3.1.1"),
                         ("submersedvr", "0.2.1")):
            record = provenance.evidence(recipe, self.part(recipe, id_), state)
            self.assertEqual(record["source"], "recipe-pinned-hash")
            self.assertEqual(record["label"], "Recorded pin "+tag)
            self.assertEqual(record["version"], tag)
            self.assertTrue(record["identified"])
            self.assertIn("NOT verified", record["detail"])
        results=archive_update_comparison.compare(recipe,None,state)
        self.assertTrue(all(row["installed_attributed"] for row in results))
        self.assertTrue(all(row["provenance_source"] == "recipe-pinned-hash" for row in results))

    def test_valheim_loader_and_vhvr_version_provenance(self):
        recipe = self.recipe("valheim")
        state = self.package_state(recipe)
        loader = provenance.evidence(recipe, self.part(recipe, "loader"), state)
        vhvr = provenance.evidence(recipe, self.part(recipe, "vhvr"), state)
        self.assertEqual(loader["label"], "Recorded pin 5.4.2351")
        self.assertEqual(vhvr["label"], "Recorded pin v0.11.2")
        self.assertNotIn("Downloaded", loader["detail"])

    def test_recipe_pin_drift_cannot_relabel_historical_package(self):
        recipe = self.recipe("valheim")
        state = self.package_state(recipe)
        recipe["packages"][1]["sha256"] = "e" * 64
        recipe["archive_releases"]["vhvr"]["pinned_tag"] = "v9.9.9"
        result = provenance.evidence(recipe, self.part(recipe, "vhvr"), state)
        self.assertEqual(result["label"], "Recorded hash · pin differs")
        self.assertIsNone(result["version"])
        self.assertFalse(result["identified"])
        self.assertIn("must not rewrite", result["detail"])

    def test_pinned_record_requires_correct_installer_and_inventory(self):
        recipe = self.recipe("valheim")
        state = self.package_state(recipe)
        state["valheim"]["installer"] = "some-other-mod"
        x = provenance.evidence(recipe, self.part(recipe, "vhvr"), state)
        self.assertEqual(x["source"], "unknown")
        self.assertIsNone(x["version"])
        state["valheim"]["installer"] = "vhvr-1"
        state["valheim"]["packages"]["vhvr"]["files"]=[]
        x = provenance.evidence(recipe, self.part(recipe, "vhvr"), state)
        self.assertFalse(x["identified"])
        self.assertIn("files unrecorded", x["label"])
        state["valheim"]["packages"]["vhvr"]["sha256"]="bad"
        x=provenance.evidence(recipe, self.part(recipe,"vhvr"),state)
        self.assertEqual(x["label"], "Hub package · release unknown")
        state["valheim"]["packages"]=None
        x=provenance.evidence(recipe,self.part(recipe,"vhvr"),state)
        self.assertEqual(x["label"],"Hub record · version unknown")

    def test_pinned_recipe_tag_must_be_from_trusted_page(self):
        recipe=self.recipe("valheim")
        state=self.package_state(recipe)
        recipe["archive_releases"]["vhvr"].pop("pinned_tag")
        recipe["packages"][1]["page"]="https://bad.example/releases/unknown/9.9"
        self.assertEqual(
            provenance.evidence(recipe,self.part(recipe,"vhvr"),state)["label"],
            "Recorded pinned archive")
        recipe["packages"][1]["page"]="http://host/release/tag/9.9.9"
        self.assertEqual(
            provenance.evidence(recipe,self.part(recipe,"vhvr"),state)["version"],None)

    def test_exact_profile_archive_hash_maps_to_unique_official_release(self):
        recipe=self.recipe("hogwarts-legacy")
        state=self.profile_state(recipe)
        row=self.official_profile_row()
        record=provenance.evidence(recipe,self.part(recipe,"profile"),state,row)
        self.assertEqual(record["label"],"Recorded profile v2.0.6")
        self.assertEqual(record["version"],"v2.0.6")
        self.assertEqual(record["source"],"official-hash-match")
        self.assertTrue(record["identified"])
        self.assertIn("NOT verified",record["detail"])
        plan={"rows":[{"id":"uevr","status":"Not found locally","file":""},row],
              "warning":None}
        combined=archive_update_comparison.compare(recipe,plan,state)
        self.assertEqual(combined[1]["installed"],"Recorded profile v2.0.6")
        self.assertTrue(combined[1]["installed_attributed"])
        self.assertEqual(combined[0]["installed"],"Unknown")

    def test_profile_incomplete_or_mismatched_scan_never_relabels(self):
        recipe=self.recipe("fatekeeper")
        state=self.profile_state(recipe)
        row=self.official_profile_row(tag="v1.0.4")
        for modifier in (
            {"candidate_incomplete":True}, {"ambiguous":True},
            {"status":"Archive changed — rescan required"},
            {"status":"Not found locally"},
            {"candidates":[dict(row["candidates"][0],sha256="b"*64)]},
            {"candidates":[dict(row["candidates"][0],tags=["v1.0.4","v1.0.3"])]},
        ):
            changed=dict(row,**modifier)
            record=provenance.evidence(recipe,self.part(recipe,"profile"),state,changed)
            self.assertIsNone(record["version"])
            self.assertFalse(record["identified"])
        record=provenance.evidence(recipe,self.part(recipe,"profile"),state,row,
                                   warning="Unscanned additional folder")
        self.assertIsNone(record["version"])
        self.assertFalse(record["identified"])

    def test_profile_source_mapping_and_empty_snapshot_required(self):
        recipe=self.recipe("hogwarts-legacy")
        state=self.profile_state(recipe)
        row=self.official_profile_row()
        recipe["archive_releases"]["profile"].pop("asset")
        result=provenance.evidence(recipe,self.part(recipe,"profile"),state,row)
        self.assertFalse(result["identified"])
        self.assertEqual(result["source"],"recorded-archive-hash")
        recipe=self.recipe("hogwarts-legacy")
        state["hogwarts-legacy:profile"]["installed"]["files"]={}
        result=provenance.evidence(recipe,self.part(recipe,"profile"),state,row)
        self.assertFalse(result["identified"])
        self.assertEqual(result["label"],"Recorded profile SHA · inventory unknown")

    def test_profile_legacy_and_invalid_digest_dont_fabricate_tag(self):
        recipe=self.recipe("hogwarts-legacy")
        component=self.part(recipe,"profile")
        state=self.profile_state(recipe)
        state["hogwarts-legacy:profile"]["installer"]="uevr-profile-legacy"
        self.assertIn("Legacy",provenance.evidence(recipe,component,state)["label"])
        state["hogwarts-legacy:profile"]["installer"]="uevr-profile-2"
        state["hogwarts-legacy:profile"]["archive_sha256"]="unverified"
        self.assertEqual(provenance.evidence(recipe,component,state)["version"],None)
        state["hogwarts-legacy:profile"]["archive_sha256"]="a"*64
        state["hogwarts-legacy:profile"]["installed"]["files"]=None
        self.assertEqual(provenance.evidence(recipe,component,state)["source"],"unknown")

    def test_cyberpunk_filename_only_is_not_identified_release(self):
        recipe=self.recipe("cyberpunk-2077")
        component=self.part(recipe,"2380")
        state={"cyberpunk-2077": {
            "installer":"gameroot-2",
            "installed_sha256":{"mods/example.dll":"f"*64},
            "components":{"2380":{"archive":"RED4ext-2380-1.31.1.zip",
                                  "files":["/fixture/game/mods/example.dll"]}}}}
        result=provenance.evidence(recipe,component,state)
        self.assertEqual(result["label"],"Recorded filename 1.31.1")
        self.assertEqual(result["version"],"1.31.1")
        self.assertEqual(result["source"],"filename-only")
        self.assertFalse(result["identified"])
        self.assertIn("not been rechecked",result["detail"])
        state["cyberpunk-2077"]["installer"]="unrecognized"
        result=provenance.evidence(recipe,component,state)
        self.assertIsNone(result["version"])
        self.assertIn("provenance unknown",result["label"])

    def test_legacy_manual_and_date_only_records_are_unknown(self):
        for rid in ("ready-or-not","doom-2016-gog","fatekeeper","hogwarts-legacy"):
            recipe=self.recipe(rid)
            state={rid:{"installed_at":99999999,"files":["/game/plugin.dll"]}}
            for component in planner.plan_components(recipe):
                result=provenance.evidence(recipe,component,state)
                self.assertIsNone(result["version"])
                self.assertFalse(result["identified"])
        recipe=self.recipe("valheim")
        state={"valheim":{"installed_at":999999,"files":["/game/mod.dll"]}}
        result=provenance.evidence(recipe,self.part(recipe,"vhvr"),state)
        self.assertIsNone(result["version"])
        self.assertFalse(result["identified"])
        self.assertEqual(provenance.evidence(recipe,self.part(recipe,"vhvr"),{})["label"],
                         "Unknown")

    def test_online_and_downloaded_do_not_infer_installed_provenance(self):
        recipe=self.recipe("valheim")
        plan={"rows":[{"id":"loader","status":"Not found locally","file":""},
                      {"id":"vhvr","status":"Pinned SHA-256 verified",
                       "file":"/fixture/Downloads/vhvr.zip"}],"warning":None}
        results=archive_update_comparison.compare(recipe,plan,{},[
            {"name":"VHVR (pinned GitHub build; review newer releases)",
             "latest_version":"v0.11.2","status":"current"}])
        self.assertEqual(results[1]["installed"],"Unknown")
        self.assertEqual(results[1]["latest"],"v0.11.2")
        self.assertIn("Pinned SHA-256",results[1]["downloaded"])
        self.assertFalse(results[1]["installed_attributed"])


class ProvenanceGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        patches=[
            mock.patch("vrhub.download_planner.preferences_file",return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library",return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file",return_value=root/"snapshots.json"),
        ]
        self.state={}
        patches.append(mock.patch.object(hub,"state",side_effect=lambda:self.state))
        for ctx in patches:
            ctx.start()
            self.addCleanup(ctx.stop)
        self.page=GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)

    def test_gui_installed_columns_distinguish_pin_vs_unknown(self):
        recipe=hub.load_recipes()["valheim"]
        self.state={"valheim":{"installer":"vhvr-1","packages":{
            "loader":{"sha256":recipe["packages"][0]["sha256"],"files":["/fixture/loader.dll"]},
            "vhvr":{"sha256":recipe["packages"][1]["sha256"],"files":["/fixture/vhvr.dll"]}}}}
        self.page.set_recipe(recipe)
        self.assertEqual(self.page.comparison_table.item(0,1).text(),
                         "Recorded pin 5.4.2351")
        self.assertEqual(self.page.comparison_table.item(1,1).text(),
                         "Recorded pin v0.11.2")
        self.assertIn("2 Hub-recorded release",self.page.comparison_summary.text())
        self.assertIn("recipe-pinned-hash",self.page.comparison_table.item(0,1).toolTip())
        self.assertFalse(self.page.comparison_panel.isVisible())
        before=(self.page.install_review_button.text(),
                self.page.install_review_button.isEnabled())
        self.page.comparison_toggle.click()
        self.assertTrue(self.page.comparison_panel.isVisible())
        self.assertEqual(before,(self.page.install_review_button.text(),
                                 self.page.install_review_button.isEnabled()))
        self.page.set_recipe(hub.load_recipes()["ready-or-not"])
        self.assertEqual(self.page.comparison_table.item(0,1).text(),"Unknown")
