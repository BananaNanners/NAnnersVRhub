# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-J: pre-update backup/impact planning never authorizes replacement."""
import copy
import hashlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from threading import Event
from unittest import mock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from vrhub import hub, preupdate_safety as safety
from vrhub.downloads_gui import GuidedDownloadsPage


def digest(data):
    return hashlib.sha256(data).hexdigest()


class PreUpdateSafetyTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.storage = self.root / "data"
        self.storage.mkdir()
        self.state_path = self.storage / "state.json"
        self.game = self.root / "game"
        self.game.mkdir()
        self.backup = self.storage / "backups" / "fixture-123"
        self.backup.mkdir(parents=True)
        self.old = b"original-before-mod"
        original = self.backup / "files" / "mod.dll"
        original.parent.mkdir()
        original.write_bytes(self.old)
        self.recipe = {"id": "fixture", "name": "Fixture", "method": "gameroot",
                       "components": [{"nexus_mod": 2380, "name": "Mod A", "phase": 1},
                                      {"nexus_mod": 191, "name": "Mod B", "phase": 2}]}
        self.state = {"fixture": {
            "installer": "gameroot-2", "keep": str(self.game),
            "backup": str(self.backup),
            "originals": {"mod.dll": {"sha256": digest(self.old), "size": len(self.old)},
                          "created.dll": None},
            "installed_sha256": {"mod.dll": "1"*64, "created.dll": "2"*64},
            "components": {
                "2380": {"files": [str(self.game/"mod.dll")],
                         "archive": "Mod-2380-1.0.0.zip"},
                "191": {"files": [str(self.game/"created.dll")],
                        "archive": "Mod-191-1.0.0.zip"}},
        }}
        self.decisions = [
            {"id": "2380", "code": "candidate", "label": "Future update candidate · review"},
            {"id": "191", "code": "integrity-unchecked",
             "label": "Verify installed files first"},
        ]
        self.scan = {"warning": None, "rows": []}
        for method in (
            mock.patch.object(hub, "state_file", return_value=self.state_path),
            mock.patch.object(hub, "game_path", return_value=self.game),
        ):
            method.start()
            self.addCleanup(method.stop)

    def result(self):
        return safety.review(self.recipe, self.scan, self.state, self.decisions)

    def test_historical_original_hash_matches_but_new_backup_required(self):
        result = self.result()
        self.assertFalse(result["authorized"])
        self.assertFalse(result["has_live_install_plan"])
        self.assertEqual(result["existing_backup"]["status"], "Recorded originals matched")
        self.assertEqual(result["existing_backup"]["verified"], 1)
        self.assertIn("fresh, verified backup", result["new_backup"])
        self.assertIn("NOT been", result["recovery"])
        self.assertEqual(result["rows"][0]["current_managed"], 1)
        self.assertIsNone(result["rows"][0]["future_destinations"])
        self.assertTrue(all(not row["eligible"] for row in result["rows"]))

    def test_changed_and_missing_backup_fails_closed(self):
        source = self.backup / "files/mod.dll"
        source.write_bytes(b"tampered-original")
        self.assertEqual(self.result()["existing_backup"]["status"], "Needs review")
        source.unlink()
        self.assertEqual(self.result()["existing_backup"]["status"], "Needs review")

    def test_untracked_or_symlink_backup_is_rejected(self):
        source = self.backup/"files/mod.dll"
        source.unlink()
        secret = self.root/"sensitive.txt"
        secret.write_bytes(self.old)
        source.symlink_to(secret)
        result = self.result()
        self.assertEqual(result["existing_backup"]["status"], "Needs review")
        self.assertEqual(secret.read_bytes(), self.old)
        source.unlink()
        self.backup.rmdir() if not (self.backup/"files").exists() else None
        outside = self.root/"outside"
        outside.mkdir()
        self.state["fixture"]["backup"] = str(outside)
        self.assertEqual(self.result()["existing_backup"]["status"], "Needs review")

    def test_manifest_traversal_and_mismatched_installed_hash_lists_block(self):
        old = self.state["fixture"]["originals"]
        self.state["fixture"]["originals"] = {"../secret": old["mod.dll"]}
        self.state["fixture"]["installed_sha256"] = {"../secret": "1"*64}
        self.assertEqual(self.result()["existing_backup"]["status"], "Needs review")
        self.state["fixture"]["originals"] = old
        self.state["fixture"]["installed_sha256"] = {"mod.dll": "1"*64, "created.dll": "2"*64}
        self.assertEqual(self.result()["existing_backup"]["status"], "Recorded originals matched")
        self.state["fixture"]["installed_sha256"] = {}
        self.assertEqual(self.result()["existing_backup"]["status"], "Needs review")

    def test_overlapping_component_ownership_is_visible(self):
        self.state["fixture"]["components"]["191"]["files"] = [str(self.game/"mod.dll")]
        row = self.result()["rows"][0]
        self.assertIn("mod.dll", row["ownership_conflicts"])
        self.assertIn("Overlapping", row["file_issue"])

    def test_legacy_no_state_cannot_certify_recovery(self):
        self.state = {}
        result = self.result()
        self.assertEqual(result["existing_backup"]["status"], "Needs review")
        self.assertEqual(result["rows"][0]["current_managed"], 0)
        self.assertFalse(result["authorized"])

    def test_unchanged_originals_never_are_new_backup(self):
        self.state["fixture"]["originals"]["mod.dll"] = None
        self.state["fixture"]["originals"]["created.dll"] = None
        result = self.result()
        self.assertEqual(result["existing_backup"]["status"], "No prior originals")
        self.assertIn("NEW pre-update backup", result["existing_backup"]["reason"])

    def test_pinned_package_historical_backup_hash(self):
        recipe = {"id":"valheim","name":"Valheim","method":"bepinex",
                  "packages":[{"id":"loader","name":"Loader"}]}
        entry={"valheim":{"installer":"vhvr-1",
                          "backup":str(self.backup),
                          "keep":str(self.game),
                          "originals":["mod.dll"],
                          "original_hashes":{"mod.dll":digest(self.old)},
                          "retired":[]}}
        result=safety.review(recipe,{"rows":[],"warning":None},entry,[])
        self.assertEqual(result["existing_backup"]["status"],"Recorded originals matched")
        self.assertFalse(result["authorized"])
        entry["valheim"]["retired"]=["BepInEx/patchers/Old"]
        result=safety.review(recipe,{"rows":[],"warning":None},entry,[])
        self.assertEqual(result["existing_backup"]["status"],"Needs review")

    def test_cancelled_check_never_returns_success(self):
        cancel = Event()
        cancel.set()
        with self.assertRaises(safety.installed_integrity.Cancelled):
            safety.review(self.recipe, self.scan, self.state, self.decisions, cancel=cancel)

    def test_does_not_mutate_ownership_records(self):
        before = (copy.deepcopy(self.state), copy.deepcopy(self.scan),
                  copy.deepcopy(self.decisions))
        self.result()
        self.assertEqual(before, (self.state, self.scan, self.decisions))


class ProfileProspectiveTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.statepath = self.root/"state.json"
        self.game = self.root/"profile"
        self.game.mkdir()
        self.backups = self.root/"backups"
        self.backups.mkdir()
        self.zip_path = self.root/"profile-v2.zip"
        with zipfile.ZipFile(self.zip_path, "w") as z:
            z.writestr("SLASHER-Win64-Shipping/config.txt", "fixture config")
            z.writestr("SLASHER-Win64-Shipping/settings.ini", "fixture settings")
        self.sha = safety.install_review._hash(self.zip_path)
        self.recipe = {"id": "fatekeeper", "name": "Fatekeeper",
                       "method": "uevr", "profile": {"dir": "profile"},
                       "archive_releases": {"profile": {"repo": "fiction/example", "asset": "profile-v2.zip"}}}
        self.scan = {"warning": None, "rows": [
            {"id": "profile", "status": "Possible archive — inspect first",
             "file": str(self.zip_path), "candidates": [
                 {"file": str(self.zip_path), "sha256": self.sha,
                  "tags": ["v2.0.0"], "expected": True}],
             "ambiguous": False, "candidate_incomplete": False,
             "release_review": False}]}
        self.decisions = [{"id": "profile", "code": "candidate",
                           "label": "Future update candidate · review"}]
        self.state = {"fatekeeper:profile": {
            "installer": "uevr-profile-2", "root": str(self.game),
            "original": {"exists": False, "files": {}, "dirs": [], "bytes": 0},
            "installed": {"exists": True,
                          "files": {"config.txt": {"sha256": "a"*64, "size": 4}}},
            "backup": None,
        }}
        for patch in (
            mock.patch.object(hub, "state_file", return_value=self.statepath),
            mock.patch.object(hub, "profile_dir", return_value=self.game),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def result(self):
        return safety.review(self.recipe, self.scan, self.state, self.decisions)

    def test_profile_zip_safe_metadata_mapping_but_never_authorized(self):
        report = self.result()
        row = report["rows"][1]
        self.assertEqual(row["future_destinations"], 2)
        self.assertIn("config.txt", row["future_sample"])
        self.assertEqual(row["integrity"], "Not checked")
        self.assertFalse(report["authorized"])
        self.assertEqual(report["existing_backup"]["status"], "No prior originals")
        self.assertIn("NEW, verified backup", report["existing_backup"]["reason"])

    def test_stale_zip_changes_fail_closed_even_with_old_scan(self):
        with zipfile.ZipFile(self.zip_path, "w") as z:
            z.writestr("SLASHER-Win64-Shipping/config.txt", "different zip content")
        row = self.result()["rows"][1]
        self.assertIsNone(row["future_destinations"])
        self.assertIn("digest", row["mapping"].lower())

    def test_zip_swapped_during_metadata_check_is_not_mapped(self):
        expected=self.sha
        original=safety.profile_safety._digest
        count=[0]
        def changing_digest(path):
            count[0]+=1
            return expected if count[0]==1 else "f"*64
        with mock.patch.object(safety.profile_safety,"_digest",
                               side_effect=changing_digest):
            report=self.result()
        row=report["rows"][1]
        self.assertIsNone(row["future_destinations"])
        self.assertIn("digest changed",row["mapping"])

    def test_invalid_zip_and_symlink_are_not_mapped(self):
        self.zip_path.unlink()
        self.zip_path.symlink_to(self.root/"missing.zip")
        self.assertIsNone(self.result()["rows"][1]["future_destinations"])

    def test_new_target_colliding_with_untracked_file_is_reported(self):
        (self.game/"settings.ini").write_text("user custom file")
        row = self.result()["rows"][1]
        self.assertEqual(row["future_destinations"], 2)
        self.assertIn("settings.ini", row["untracked_collisions"])
        self.assertIn("Untracked", row["file_issue"])

    def test_prior_profile_backup_snapshot_is_verified(self):
        expected = {
            "exists": True,
            "files": {"config.txt": {"size": 13, "sha256": digest(b"original-data")}},
            "dirs": [], "bytes": 13}
        retained = self.backups/"fixture-profile"
        retained.mkdir()
        (retained/"config.txt").write_bytes(b"original-data")
        self.state["fatekeeper:profile"]["backup"] = str(retained)
        self.state["fatekeeper:profile"]["original"] = expected
        self.assertEqual(self.result()["existing_backup"]["status"], "Recorded originals matched")
        (retained/"config.txt").write_bytes(b"modified data")
        self.assertEqual(self.result()["existing_backup"]["status"], "Needs review")

    def test_ambiguous_archive_does_not_become_mapped(self):
        self.scan["rows"][0]["ambiguous"] = True
        self.assertIsNone(self.result()["rows"][1]["future_destinations"])


class PreUpdateSafetyGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        for patch in (
            mock.patch("vrhub.download_planner.preferences_file", return_value=root/"prefs.json"),
            mock.patch("vrhub.download_planner.default_library", return_value=root),
            mock.patch("vrhub.archive_scans.snapshot_file", return_value=root/"scans.json"),
            mock.patch.object(hub, "state", return_value={}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["valheim"])

    def test_not_triggered_on_game_switch_or_comparison_expand(self):
        with mock.patch.object(safety, "review", side_effect=AssertionError("not clicked")):
            self.page.set_recipe(hub.load_recipes()["valheim"])
            self.page.comparison_toggle.click()
            self.page.set_online_results([])
            self.assertEqual(self.page.safety_summary.text(),
                             "File replacement: not reviewed.")
            self.assertFalse(self.page.safety_details.isVisible())
            self.assertEqual(self.page.safety_button.text(),
                             "Review replacement safety (read-only)")

    def test_button_worker_and_invalidation_do_not_change_install_gate(self):
        before = (self.page.install_review_button.text(),
                  self.page.install_review_button.isEnabled())
        self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(300):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertIsNotNone(self.page._safety_result)
        self.assertIn("Replacement blocked", self.page.safety_summary.text())
        self.assertIn("NEW", self.page.safety_details.toPlainText().upper())
        self.assertEqual((self.page.install_review_button.text(),
                          self.page.install_review_button.isEnabled()), before)
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())

    def test_refresh_invalidates_old_safety_report(self):
        self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(300):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNotNone(self.page._safety_result)
        self.page.set_online_results([])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
