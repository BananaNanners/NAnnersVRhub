# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C3 profile confirmation dialogs, never game mutation."""
import unittest

from PySide6.QtWidgets import QApplication, QDialog
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

    def test_ready_review_requires_explicit_checkbox(self):
        dialog = ProfileReviewDialog(self.plan())
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.apply_btn.isEnabled())
        self.assertFalse(dialog.confirmed_by_user)
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
