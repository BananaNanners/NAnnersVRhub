# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-I advisory readiness: never an installation authorization."""
import copy
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub import hub, download_planner as planner
from vrhub import update_readiness as readiness
from vrhub.downloads_gui import GuidedDownloadsPage


class ReadinessModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.recipe = copy.deepcopy(hub.load_recipes()["fatekeeper"])
        self.new_sha = "b" * 64
        self.old_sha = "a" * 64
        self.profile = {
            "id": "profile", "name": "Matching game profile", "phase": 1,
            "status": "Possible archive — inspect first",
            "file": "/fixtures/Downloads/SLASHER-Win64-Shipping-1.zip",
            "candidates": [
                {"file": "/fixtures/Downloads/SLASHER-Win64-Shipping-1.zip",
                 "sha256": self.new_sha, "tags": ["v1.0.4"],
                 "expected": True, "copies": 1},
                {"file": "/fixtures/Older/SLASHER-Win64-Shipping-older.zip",
                 "sha256": self.old_sha, "tags": ["v1.0.3"],
                 "expected": False, "copies": 1},
            ],
            "release_expected": "v1.0.4",
            "release_review": False, "ambiguous": False,
            "candidate_incomplete": False,
        }
        self.injector = {
            "id": "uevr", "name": "Matching UEVR injector package", "phase": 1,
            "status": "Not found locally", "file": "",
        }
        self.plan = {"rows": [self.injector, self.profile], "warning": None}
        self.state = {"fatekeeper:profile": {
            "installer": "uevr-profile-2",
            "archive_sha256": self.old_sha,
            "installed": {
                "exists": True,
                "files": {"config.txt": {"sha256": "c" * 64, "size": 12}},
            },
        }}
        self.online = [{"name": "SLASHER-Win64-Shipping.zip",
                        "status": "update", "latest_version": "v1.0.4"}]
        self.integrity = {"game_id": "fatekeeper", "status": "Unknown",
                          "checked": 1, "rows": [
                              {"id": "profile", "name": "Matching game profile",
                               "status": "Verified", "files": 1, "checked": 1}
                          ], "presence": {
                              "status": "Ready", "ok": 2, "total": 2,
                              "required_bad": [], "later_bad": [],
                          }}

    def result(self):
        return {x["id"]: x for x in readiness.assess(
            self.recipe, self.plan, self.state, self.online, self.integrity)}

    def check(self, code):
        item = self.result()["profile"]
        self.assertEqual(item["code"], code, item)
        self.assertFalse(item["authorized"])
        self.assertTrue(item["next"])
        return item

    def test_candidate_still_needs_backups_and_compatibility(self):
        row = self.check("candidate")
        self.assertIn("Future update candidate", row["label"])
        self.assertIn("backup", row["next"].lower())
        self.assertIn("compatibility", row["next"].lower())
        self.assertIn("NOT authorization", row["detail"])

    def test_integrity_verified_label_without_complete_count_is_not_enough(self):
        self.integrity["rows"][0].pop("files")
        self.check("integrity-unknown")
        self.integrity["rows"][0]["files"] = 1
        self.integrity["rows"][0]["checked"] = 0
        self.check("integrity-unknown")
        self.integrity["rows"][0]["checked"] = 1
        self.check("candidate")

    def test_no_integrity_never_becomes_candidate(self):
        self.integrity = None
        self.check("integrity-unchecked")

    def test_integrity_for_other_game_is_ignored(self):
        self.integrity["game_id"] = "hogwarts-legacy"
        self.check("integrity-unchecked")

    def test_changed_or_missing_installed_files_block(self):
        self.integrity["rows"][0]["status"] = "Review"
        self.check("integrity-review")
        self.integrity["rows"][0]["status"] = "Unknown"
        self.check("integrity-unknown")

    def test_required_mod_presence_does_not_equal_integrity(self):
        self.integrity["presence"]["status"] = "Needs review"
        self.check("presence")
        self.integrity["presence"]["status"] = "Ready"
        self.integrity["presence"]["required_bad"] = [
            {"name": "profile", "status": "missing"}]
        self.check("presence")
        self.integrity.pop("presence")
        self.check("presence")

    def test_missing_or_failed_online_lookup_prevents_candidate(self):
        self.online = None
        self.check("online")
        self.online = [{"name": "SLASHER-Win64-Shipping.zip",
                        "status": "no_key"}]
        self.check("online")
        self.online = [
            {"name": "SLASHER-Win64-Shipping.zip",
             "status": "update", "latest_version": "v1.0.4"},
            {"name": "SLASHER-Win64-Shipping.zip",
             "status": "update", "latest_version": "v1.0.5"},
        ]
        self.check("online")

    def test_older_archive_and_matching_release_not_updates(self):
        self.profile["candidates"][0]["tags"] = ["v1.0.2"]
        self.profile["release_expected"] = "v1.0.2"
        self.check("older")
        self.profile["candidates"][0]["tags"] = ["v1.0.3"]
        self.profile["release_expected"] = "v1.0.3"
        self.online[0]["latest_version"] = "v1.0.3"
        self.check("same")
        self.online[0]["latest_version"] = "v1.0.4"
        self.check("online-newer")

    def test_newer_online_release_than_downloaded(self):
        self.online[0]["latest_version"] = "v1.0.5"
        self.check("online-newer")

    def test_download_ahead_of_last_online_metadata(self):
        self.online[0]["latest_version"] = "v1.0.3"
        self.check("ahead")

    def test_non_numeric_tag_requires_manual_comparison(self):
        self.profile["candidates"][0]["tags"] = ["v1.0.4-beta"]
        self.profile["release_expected"] = "v1.0.4-beta"
        self.online[0]["latest_version"] = "v1.0.4-beta"
        self.check("versions")

    def test_blocked_pins_mismatch_and_ambiguous_zip(self):
        self.profile["release_review"] = True
        self.profile["status"] = "Hash mismatch — do not install"
        self.check("blocked")
        self.profile["status"] = "Possible archive — inspect first"
        self.check("pin")
        self.profile["release_review"] = False
        self.profile["ambiguous"] = True
        self.check("blocked")
        self.profile["ambiguous"] = False
        self.profile["candidate_incomplete"] = True
        self.check("blocked")

    def test_stale_scan_and_missing_archive(self):
        self.plan["warning"] = "Archive inventory exceeded limit."
        self.check("rescan")
        self.plan["warning"] = None
        self.profile["file"] = ""
        self.profile["status"] = "Not found locally"
        self.check("missing")
        self.plan["rows"] = []
        self.check("rescan")

    def test_old_profile_not_attributed_when_old_zip_missing(self):
        self.profile["candidates"] = self.profile["candidates"][:1]
        self.check("provenance")

    def test_filename_hint_cannot_authorize_cyberpunk(self):
        recipe = hub.load_recipes()["cyberpunk-2077"]
        comp = planner.plan_components(recipe)[0]
        name = comp["id"]
        plan = {"rows": [{**comp, "status": "Possible archive — inspect first",
                          "file": f"/fixtures/RED4ext-{name}-1.31.1.zip"}],
                "warning": None}
        state = {recipe["id"]: {
            "installer": "gameroot-2",
            "components": {name: {
                "archive": f"RED4ext-{name}-1.30.0.zip",
                "files": ["/game/mods/RED4ext.dll"],
            }},
        }}
        online = [{"mod_id": int(name), "latest_version": "1.31.1", "status": "update"}]
        integrity = {"game_id": recipe["id"], "rows": [
            {"id": name, "status": "Verified"}], "presence": {
                "status": "Ready", "required_bad": []}}
        decisions = readiness.assess(recipe, plan, state, online, integrity)
        self.assertEqual(decisions[0]["code"], "unverified")
        self.assertTrue(all(not row["authorized"] for row in decisions))

    def test_pinned_loader_release_tag_from_recipe_source_not_filename(self):
        recipe = hub.load_recipes()["valheim"]
        comp = planner.plan_components(recipe)[0]
        plan = {"rows": [{**comp, "status": "Pinned SHA-256 verified",
                          "file": "/fixture/arbitrary-name.zip"}], "warning": None}
        state = {recipe["id"]: {
            "installer": "vhvr-1",
            "packages": {"loader": {
                "sha256": recipe["packages"][0]["sha256"],
                "files": ["/game/BepInEx/loader.dll"]}},
        }}
        from vrhub import archive_update_comparison
        row = archive_update_comparison.compare(recipe, plan, state)[0]
        self.assertEqual(row["downloaded"], "Pinned SHA-256 · 5.4.2351")
        self.assertEqual(row["download_version"], "5.4.2351")
        self.assertEqual(readiness.assess(recipe, plan, state)[0]["code"],
                         "integrity-unchecked")

    def test_pin_change_disallows_relabel_as_installed(self):
        recipe = hub.load_recipes()["valheim"]
        comp = planner.plan_components(recipe)[1]
        plan = {"rows": [{**comp, "status": "Pinned SHA-256 verified",
                          "file": "/fixture/vhvr.zip"}], "warning": None}
        recorded = {recipe["id"]: {
            "installer": "vhvr-1",
            "packages": {"vhvr": {
                "sha256": "d" * 64,
                "files": ["/game/BepInEx/vr.dll"]}},
        }}
        integrity = {"game_id": recipe["id"], "rows": [
            {"id": "vhvr", "status": "Verified"}],
            "presence": {"status": "Ready", "required_bad": []}}
        result = readiness.assess(recipe, plan, recorded, [
            {"name": "VHVR (pinned GitHub build; review newer releases)",
             "latest_version": "v0.11.4", "status": "update"}], integrity)
        self.assertEqual(result[1]["code"], "provenance")
        self.assertFalse(result[1]["authorized"])

    def test_does_not_modify_fixture_inputs(self):
        before = (copy.deepcopy(self.recipe), copy.deepcopy(self.plan),
                  copy.deepcopy(self.state), copy.deepcopy(self.online),
                  copy.deepcopy(self.integrity))
        self.result()
        self.assertEqual(before, (self.recipe, self.plan, self.state, self.online,
                                 self.integrity))


class ReadinessGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        patches = (
            mock.patch("vrhub.download_planner.preferences_file", return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library", return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file", return_value=root/"scan.json"),
            mock.patch.object(hub, "state", return_value={}),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.recipe = hub.load_recipes()["valheim"]
        self.page.set_recipe(self.recipe)

    def test_collapsed_default_five_columns_and_no_install_action_change(self):
        self.assertFalse(self.page.comparison_panel.isVisible())
        self.assertEqual(self.page.comparison_table.columnCount(), 5)
        self.assertEqual(self.page.comparison_table.horizontalHeaderItem(4).text(),
                         "Update readiness")
        action_before = (self.page.install_review_button.text(),
                         self.page.install_review_button.isEnabled())
        self.page.comparison_toggle.click()
        self.assertTrue(self.page.comparison_panel.isVisible())
        self.assertIn("planning only", self.page.readiness_summary.text())
        self.assertIn("No update is authorized", self.page.readiness_summary.text())
        self.assertIn("Scan archives", self.page.comparison_table.item(1, 4).text())
        self.assertIn("No replacement", self.page.comparison_table.item(1, 4).toolTip())
        self.assertEqual((self.page.install_review_button.text(),
                          self.page.install_review_button.isEnabled()), action_before)

    def test_online_refresh_and_game_switch_never_reuse_integrity(self):
        self.page.set_online_results([{"name": "VHVR (pinned GitHub build; review newer releases)",
                                       "status": "update", "latest_version": "v0.11.4"}])
        self.assertEqual(self.page.comparison_table.item(1, 3).text(), "v0.11.4")
        self.assertIn("Scan archives", self.page.comparison_table.item(1, 4).text())
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertIsNone(self.page._integrity_result)
        self.assertEqual(self.page.comparison_table.item(1, 3).text(), "Not checked")

    def test_dangerous_verification_result_does_not_trigger_installer(self):
        worker = type("SyntheticWorker", (), {
            "recipe": {"id": "valheim"}, "cancel_flag": Event()})()
        self.page.integrity_worker = worker
        plan = {"game_id": "valheim",
                "rows": [{"id": "vhvr", "status": "Review",
                          "name": "VHVR", "reason": "modified", "issues": [
                              {"file": "vr.dll", "status": "Modified", "detail": "diff"}]}],
                "checked": 0, "presence": {
                    "status": "Needs review", "required_bad": [], "later_bad": []}}
        action_before = (self.page.install_review_button.text(),
                         self.page.install_review_button.isEnabled())
        self.page._integrity_done(plan, worker)
        self.assertEqual((self.page.install_review_button.text(),
                          self.page.install_review_button.isEnabled()), action_before)
        self.assertIn("No update is authorized", self.page.readiness_summary.text())
        self.page.integrity_worker = None
