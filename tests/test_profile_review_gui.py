# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C3 profile confirmation dialogs, never game mutation."""
import unittest
from dataclasses import replace

from PySide6.QtWidgets import QApplication, QDialog, QLabel
from vrhub.profile_review_gui import ProfileReviewDialog
from vrhub.profile_safety import ProfilePlan


class UEVRReviewGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def plan(self, blocked=()):
        return ProfilePlan(
            "fatekeeper", "Fatekeeper", "/test/archive.zip", "a"*64,
            "/test/prefix/UnrealVRMod/SLASHER-Win64-Shipping",
            ("config.txt", "plugins/custom/feature.dll"),
            2, 17, 5, 125, 3, True, tuple(blocked), "b"*64)

    def test_display_uses_consistent_kb_mb_gb_units_and_exact_tooltips(self):
        scenarios = (
            (1_250, 2_500, "1.25 KB", "2.5 KB"),
            (3_750_000, 54_483_692, "3.75 MB", "54.48 MB"),
            (2_000_000_000, 1_500_000_000, "2 GB", "1.5 GB"),
        )
        for new_bytes, original_bytes, new_expected, original_expected in scenarios:
            with self.subTest(new_bytes=new_bytes, original_bytes=original_bytes):
                plan = replace(self.plan(), profile_bytes=new_bytes,
                               existing_bytes=original_bytes)
                dialog = ProfileReviewDialog(plan, allow_install=False)
                self.addCleanup(dialog.close)
                overview = dialog.findChild(QLabel, "uevrProfileReviewOverview")
                self.assertIsNotNone(overview)
                self.assertIn(new_expected, overview.text())
                self.assertIn(original_expected, overview.text())
                self.assertNotIn("bytes", overview.text().lower())
                self.assertIn(f"{new_bytes:,} bytes", overview.toolTip())
                self.assertIn(f"{original_bytes:,} bytes", overview.toolTip())
                self.assertFalse(dialog.apply_btn.isEnabled())

    def test_small_sizes_and_zero_still_use_normal_formatter(self):
        plan = replace(self.plan(), profile_bytes=0, existing_bytes=125)
        dialog = ProfileReviewDialog(plan, allow_install=False)
        self.addCleanup(dialog.close)
        overview = dialog.findChild(QLabel, "uevrProfileReviewOverview")
        self.assertIn("0 B", overview.text())
        self.assertIn("125 B", overview.text())
        self.assertIn("0 bytes", overview.toolTip())

    def test_ready_review_requires_explicit_checkbox(self):
        dialog = ProfileReviewDialog(self.plan())
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.apply_btn.isEnabled())
        self.assertFalse(dialog.confirmed_by_user)
        dialog.ack.setChecked(True)
        self.assertFalse(dialog.apply_btn.isEnabled())
        dialog.manifest_toggle.setChecked(True)
        self.assertFalse(dialog.apply_btn.isEnabled())
        dialog.ack.setChecked(True)
        self.assertTrue(dialog.apply_btn.isEnabled())
        dialog.apply_btn.click()
        self.assertTrue(dialog.confirmed_by_user)
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_legacy_record_blocks_even_with_checkbox(self):
        dialog = ProfileReviewDialog(self.plan(
            ("Legacy profile ownership not verified; manual review required.",)))
        self.addCleanup(dialog.close)
        dialog.ack.setChecked(True)
        self.assertFalse(dialog.apply_btn.isEnabled())
        dialog._confirmed()
        self.assertFalse(dialog.confirmed_by_user)
        self.assertIn("BLOCKED", dialog.status.text())

    def test_read_only_desktop_preview_never_enables_apply(self):
        dialog = ProfileReviewDialog(self.plan(), allow_install=False)
        self.addCleanup(dialog.close)
        dialog.ack.setChecked(True)
        self.assertFalse(dialog.apply_btn.isEnabled())
        self.assertIn("READ-ONLY PREVIEW", dialog.status.text())
        dialog._confirmed()
        self.assertFalse(dialog.confirmed_by_user)

    def test_exact_destination_archive_and_backup_policy_visible(self):
        plan = self.plan()
        dialog = ProfileReviewDialog(plan, allow_install=False)
        self.addCleanup(dialog.close)
        labels = " ".join(label.text() for label in dialog.findChildren(__import__(
            "PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
        self.assertIn(plan.destination, labels)
        self.assertIn(plan.archive, labels)
        self.assertIn("whole-directory", labels)
        self.assertIn("SHA-256", labels)
        self.assertEqual(dialog.table.rowCount(), 2)
        self.assertEqual(dialog.table.item(1, 0).text(), "plugins/custom/feature.dll")
