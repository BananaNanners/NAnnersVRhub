# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-X read-only payload taxonomy and compatibility-evidence tests."""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from vrhub import (
    hub, payload_evidence as x, preupdate_safety as safety,
    cyberpunk_archive_mapping as w,
)
from vrhub.downloads_gui import GuidedDownloadsPage


def write_zip(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, payload in members:
            z.writestr(name, payload)
    return path


class PayloadClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = hub.load_recipes()["cyberpunk-2077"]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nanners-dev5d3x-test-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "fake-game-root"
        self.game.mkdir()
        self.file = self.root / "CET-107-TEST-FIXTURE.zip"
        self.members = [
            ("bin/x64/plugins/cet.asi", b"invented-CET")]
        write_zip(self.file, self.members)

    def rewrite(self, members=None, filename=None):
        if filename:
            self.file = self.root / filename
        return write_zip(self.file, members if members is not None else self.members)

    def classify(self, cid="107"):
        return x.classify_zip(self.recipe, {"id": cid}, self.file)

    def reviewed(self, *, scan=None, decisions=None):
        if scan is None:
            scan = {
                "game_id": "cyberpunk-2077",
                "warning": None,
                "rows": [{
                    "id": "107",
                    "status": "Possible archive — inspect first",
                    "file": str(self.file),
                    "size": self.file.stat().st_size,
                    "matches": 1,
                    "ambiguous": False,
                    "candidate_incomplete": False,
                    "release_review": False,
                }],
            }
        if decisions is None:
            decisions = [{
                "id": "107", "code": "integrity-unchecked",
                "label": "Installed files not yet verified"}]
        with mock.patch.object(hub, "game_path", return_value=self.game):
            return safety.review(self.recipe, scan, {}, decisions)

    def current_row(self, **kw):
        review = self.reviewed(**kw)
        self.assertFalse(review["authorized"])
        self.assertFalse(review["has_live_install_plan"])
        return next(r for r in review["rows"] if r["id"] == "107")

    def assert_no_authority(self, report):
        self.assertFalse(report["safe_to_apply"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["latest_release_verified"])
        self.assertFalse(report["game_build_verified"])
        self.assertFalse(report["runtime_compatibility_verified"])
        self.assertFalse(report["dependencies_verified"])
        self.assertFalse(report["member_crc_verified"])
        self.assertFalse(report["current_install_ownership_verified"])
        self.assertFalse(report["fresh_backup_verified"])
        self.assertFalse(report["live_update_authorized"])
        self.assertFalse(report["unknown_files_automatically_ignored"])
        self.assertFalse(report["optional_files_automatically_selected"])

    def test_clean_direct_cet_zip_classified_but_release_is_not_authenticated(self):
        report = self.classify()
        self.assertEqual(report["counts"]["installable"], 1)
        self.assertEqual(sum(report["counts"].values()), 1)
        self.assertTrue(report["member_classification_complete"])
        self.assertTrue(report["metadata_preflight_passed"])
        self.assertFalse(report["required_payload_contract_exists"])
        self.assert_no_authority(report)
        existing = self.current_row()
        self.assertEqual(existing["full_target_provenance"], "cyberpunk_gameroot")
        self.assertEqual(existing["payload_evidence"]["counts"]["installable"], 1)
        self.assertFalse(existing["eligible"])

    def test_root_readme_and_license_are_documentation_not_automatic_exclusions(self):
        self.rewrite([
            ("bin/x64/plugins/cet.asi", b"invented"),
            ("README.txt", b"synthetic documentation"),
            ("LICENSE.md", b"synthetic license")])
        info = self.classify()
        self.assertEqual(info["counts"]["installable"], 1)
        self.assertEqual(info["counts"]["documentation"], 2)
        self.assertEqual(info["regular_members"], 3)
        self.assertTrue(info["member_classification_complete"])
        self.assertIn("README.txt", info["samples"]["documentation"])
        self.assert_no_authority(info)
        with self.assertRaisesRegex(w.MappingBlocked, "unmapped"):
            w.map_checked_zip(self.recipe, {"id": "107"}, self.file)
        reviewed = self.current_row()
        self.assertIsNone(reviewed["future_destinations"])
        self.assertIsNone(reviewed["full_target_provenance"])
        self.assertEqual(reviewed["payload_evidence"]["counts"]["documentation"], 2)
        self.assertFalse(reviewed["eligible"])

    def test_wrapper_docs_and_nested_license_only_in_recognized_docs_area(self):
        self.rewrite([
            ("Wrapper/BIN/x64/plugins/cet.asi", b"invented"),
            ("Wrapper/readme.md", b"docs"),
            ("Wrapper/docs/LICENSE.txt", b"license"),
            ("Wrapper/somewhere/README.txt", b"not trusted")])
        report = self.classify()
        self.assertEqual(report["counts"]["installable"], 1)
        self.assertEqual(report["counts"]["documentation"], 2)
        self.assertEqual(report["counts"]["unknown"], 1)
        self.assertTrue(report["single_wrapper_detected"])
        self.assertIn("somewhere/README", report["samples"]["unknown"][0])
        self.assert_no_authority(report)

    def test_optional_variant_is_labeled_but_never_selected(self):
        self.rewrite([
            ("bin/x64/plugins/cet.asi", b"payload"),
            ("Optional/alternate.dll", b"alternative"),
            ("Variants/other.asi", b"other")])
        report = self.classify()
        self.assertEqual(report["counts"]["optional"], 2)
        self.assertEqual(report["counts"]["installable"], 1)
        self.assert_no_authority(report)
        row = self.current_row()
        self.assertIsNone(row["future_destinations"])
        self.assertEqual(row["payload_evidence"]["counts"]["optional"], 2)
        self.assertIn("Optional/alternate.dll", row["payload_evidence"]["samples"]["optional"])

    def test_optional_inside_the_game_root_is_never_silently_dropped(self):
        self.rewrite([
            ("bin/x64/plugins/cet.asi", b"install"),
            ("r6/scripts/optional/extra.reds", b"could-be-game-file")])
        report = self.classify()
        self.assertEqual(report["counts"]["installable"], 2)
        self.assertEqual(report["counts"]["optional"], 0)
        self.assert_no_authority(report)

    def test_unknown_executable_and_unknown_document_names_stay_unknown(self):
        self.rewrite([
            ("bin/x64/plugins/cet.asi", b"payload"),
            ("INSTALLER.EXE", b"unknown"),
            ("docs/release_notes.rtf", b"unsupported docs")])
        report = self.classify()
        self.assertEqual(report["counts"]["unknown"], 2)
        self.assertEqual(report["counts"]["documentation"], 0)
        self.assert_no_authority(report)

    def test_readme_inside_game_root_is_a_target_not_excluded_documentation(self):
        self.rewrite([
            ("bin/x64/plugins/CET.asi", b"payload"),
            ("r6/scripts/README.md", b"part of game tree")])
        report = self.classify()
        self.assertEqual(report["counts"]["installable"], 2)
        self.assertEqual(report["counts"]["documentation"], 0)
        self.assert_no_authority(report)

    def test_required_vrport_payload_is_distinguished_from_compatibility(self):
        required = next(c for c in self.recipe["components"]
                        if str(c["nexus_mod"]) == "30093")["required_files"][0]
        self.rewrite([
            (required, b"fictional VR Port")],
            filename="CyberpunkVR-Port-30093-fixture.zip")
        report = self.classify(cid="30093")
        self.assertTrue(report["required_payload_contract_exists"])
        self.assertTrue(report["required_payload_contract_satisfied"])
        self.assertFalse(report["game_build_verified"])
        self.assertFalse(report["source_authenticated"])
        self.assert_no_authority(report)
        self.rewrite([
            ("red4ext/plugins/something-else.dll", b"fiction")])
        other = self.classify(cid="30093")
        self.assertTrue(other["required_payload_contract_exists"])
        self.assertFalse(other["required_payload_contract_satisfied"])
        self.assert_no_authority(other)

    def test_traversal_and_symlink_entries_are_blocking_signals_not_exact_counts(self):
        self.rewrite([
            ("../outside.dll", b"unsafe")])
        report = self.classify()
        self.assertFalse(report["metadata_preflight_passed"])
        self.assertEqual(report["counts"]["unsafe"], 1)
        self.assertIsNone(report["regular_members"])
        self.assertFalse(report["member_classification_complete"])
        self.assertIn("not an exact file total", report["reason"])
        self.assert_no_authority(report)
        row = self.current_row()
        self.assertIsNotNone(row["payload_evidence"])
        self.assertFalse(row["payload_evidence"]["metadata_preflight_passed"])
        self.assertEqual(row["payload_evidence"]["counts"]["unsafe"], 1)
        self.assertFalse(row["eligible"])
        self.assertIsNone(row["future_destinations"])

        info = zipfile.ZipInfo("bin/x64/plugins/link.dll")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        self.rewrite([(info, b"unsafe symlink")])
        bad = self.classify()
        self.assertEqual(bad["counts"]["unsafe"], 1)
        self.assertFalse(bad["metadata_preflight_passed"])
        self.assert_no_authority(bad)

    def test_encrypted_duplicate_casefold_and_unsafe_zip_metadata_blocked(self):
        with mock.patch("warnings.warn"):
            self.rewrite([
                ("bin/x64/plugins/CET.dll", b"one"),
                ("BIN/x64/plugins/cet.DLL", b"two")])
        report = self.classify()
        self.assertEqual(report["counts"]["unsafe"], 1)
        self.assertFalse(report["metadata_preflight_passed"])
        self.assert_no_authority(report)

    def test_wrapped_readme_is_not_a_source_authenticity_claim(self):
        self.rewrite([
            ("SomeWrapper/bin/x64/plugins/cet.dll", b"fake game file"),
            ("SomeWrapper/README.md", b"fake source")])
        report = self.classify()
        self.assertTrue(report["single_wrapper_detected"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["latest_release_verified"])
        self.assertFalse(report["member_crc_verified"])
        self.assert_no_authority(report)

    def test_filename_identity_ambiguity_cannot_be_classified_as_a_known_component(self):
        self.rewrite([("bin/x64/plugins/cet.asi", b"payload")],
                     filename="CET-107-2380-ambiguous.zip")
        report = self.classify()
        self.assertFalse(report["metadata_preflight_passed"])
        self.assertFalse(report["member_classification_complete"])
        self.assert_no_authority(report)
        row = self.current_row()
        self.assertIsNone(row["future_destinations"])
        self.assertFalse(row["payload_evidence"]["metadata_preflight_passed"])
        self.assertIn("not uniquely identify",
                      row["payload_evidence"]["reason"])
        self.assertFalse(row["eligible"])

    def test_changed_archive_scan_size_discards_payload_evidence(self):
        scan = {
            "game_id": "cyberpunk-2077", "warning": None,
            "rows": [{
                "id": "107", "status": "Possible archive — inspect first",
                "file": str(self.file), "size": self.file.stat().st_size + 1,
                "matches": 1, "ambiguous": False,
                "candidate_incomplete": False, "release_review": False,
            }],
        }
        self.assertIsNone(self.current_row(scan=scan)["payload_evidence"])

    def test_digest_change_during_classification_discards_entire_report(self):
        original = safety.profile_safety._digest
        seen = [0]
        def inconsistent(candidate):
            seen[0] += 1
            return original(candidate) if seen[0] == 1 else "0" * 64
        with mock.patch.object(safety.profile_safety, "_digest",
                               side_effect=inconsistent):
            row = self.current_row()
        self.assertIsNone(row["payload_evidence"])
        self.assertIsNone(row["future_destinations"])
        self.assertIn("digest changed", row["mapping"])

    def test_last_digest_change_after_strict_mapping_drops_payload_report(self):
        original = safety.profile_safety._digest
        seen = [0]
        def changing_at_final_check(candidate):
            seen[0] += 1
            return original(candidate) if seen[0] < 3 else "0" * 64
        with mock.patch.object(safety.profile_safety, "_digest",
                               side_effect=changing_at_final_check):
            row = self.current_row()
        self.assertGreaterEqual(seen[0], 3)
        self.assertIsNone(row["payload_evidence"])
        self.assertIsNone(row["future_destinations"])
        self.assertIn("digest changed", row["mapping"])

    def test_readonly_classification_does_not_read_member_contents_or_write(self):
        before = hashlib.sha256(self.file.read_bytes()).hexdigest()
        with (mock.patch.object(zipfile.ZipFile, "read",
                                side_effect=AssertionError("member data read")),
              mock.patch.object(hub, "install",
                                side_effect=AssertionError("install")),
              mock.patch.object(Path, "write_bytes",
                                side_effect=AssertionError("write"))):
            report = self.classify()
        self.assertTrue(report["member_classification_complete"])
        self.assertEqual(before, hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assert_no_authority(report)

    def test_user_archive_and_state_unmodified_by_safety_review(self):
        old = hashlib.sha256(self.file.read_bytes()).hexdigest()
        snapshot = {}
        report = self.reviewed()
        self.assertFalse(report["authorized"])
        self.assertEqual(old, hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(snapshot, {})

    def test_bounded_synthetic_classifier_rehearsal(self):
        result = x.rehearse_synthetic_payload_classification()
        self.assertEqual(result["cases"], 5)
        self.assertEqual(result["classifications"], {
            "installable": 1, "documentation": 2, "optional": 1,
            "unknown": 1, "unsafe": 1})
        self.assertTrue(result["temporary_fixture_discarded"])
        self.assertFalse(result["real_archive_bytes_read"])
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["live_update_authorized"])


class PayloadClassificationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="nanners-dev5d3x-qt-")
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        (self.root / "cyber").mkdir()
        for thing in (
            mock.patch("vrhub.download_planner.preferences_file",
                       return_value=self.root / "prefs.json"),
            mock.patch("vrhub.download_planner.default_library",
                       return_value=self.root),
            mock.patch("vrhub.archive_scans.snapshot_file",
                       return_value=self.root / "scans.json"),
            mock.patch.object(hub, "state", return_value={}),
            mock.patch.object(hub, "game_path", return_value=self.root / "cyber"),
        ):
            thing.start()
            self.addCleanup(thing.stop)
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.addCleanup(self.page.close)
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])

    def review(self):
        if not self.page.comparison_toggle.isChecked():
            self.page.comparison_toggle.click()
        self.page.safety_button.click()
        for _ in range(450):
            if self.page.safety_worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.page.safety_worker)
        self.assertIsNotNone(self.page._safety_result)

    def test_existing_review_displays_unverified_evidence_without_extra_controls(self):
        previous = (self.page.install_review_button.text(),
                    self.page.install_review_button.isEnabled())
        self.review()
        displayed = self.page.safety_details.toPlainText()
        self.assertIn("ARCHIVE PAYLOAD CLASSIFICATION & COMPATIBILITY EVIDENCE", displayed)
        self.assertIn("Nexus release authenticity", displayed)
        self.assertIn("LIVE UPDATE DISABLED", displayed)
        self.assertIn("0 local Cyberpunk ZIP payload review(s)", displayed)
        self.assertEqual(
            (self.page.install_review_button.text(),
             self.page.install_review_button.isEnabled()), previous)
        self.assertFalse(self.page._safety_result["authorized"])

    def test_switch_game_discards_payload_classification_review(self):
        self.review()
        self.assertIsNotNone(self.page._safety_result)
        self.page.set_recipe(hub.load_recipes()["fatekeeper"])
        self.assertIsNone(self.page._safety_result)
        self.assertFalse(self.page.safety_details.isVisible())
