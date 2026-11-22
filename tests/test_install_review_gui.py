# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C Qt confirmation gates and integration without touching installed games."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from vrhub import hub, install_review, archive_scans, download_planner as planner
from vrhub.install_review_gui import InstallReviewDialog
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow
from vrhub.downloads_gui import GuidedDownloadsPage


def fixture_plan(*, blocked=(), files=2):
    rows = tuple(
        install_review.Target(
            f"BepInEx/plugins/VR{i}.dll",
            f"/tmp/sample-game/BepInEx/plugins/VR{i}.dll",
            "Add new file", 0, None, None, None, None)
        for i in range(files))
    return install_review.InstallPlan(
        "valheim", "Valheim", "bepinex", "/tmp/sample-game",
        ("/tmp/archives/test.zip",),
        ("a" * 64,), ("Pinned loader",),
        rows, files, 0, 0,
        "Persistent, Hub-managed original-file backups",
        tuple(blocked), ("No live test game is modified.",), "f" * 64)


class InstallDialogAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def create_dialog(self, blocked=(), allow_install=True):
        d = InstallReviewDialog(fixture_plan(blocked=blocked),
                                allow_install=allow_install)
        d.show()
        self.app.processEvents()
        self.addCleanup(d.close)
        return d

    def test_backup_overview_and_file_sizes_show_mb_gb_with_exact_hover_bytes(self):
        from dataclasses import replace
        for size, rendered in ((24_500_000, "24.5 MB"),
                               (2_500_000_000, "2.5 GB")):
            with self.subTest(size=size):
                row = replace(
                    fixture_plan().target_rows[0],
                    action="Replace; back up original",
                    current_bytes=size,
                    current_sha256="a" * 64)
                plan = replace(
                    fixture_plan(files=1),
                    target_rows=(row,), new_files=0, overwrites=1,
                    backup_bytes=size)
                d = InstallReviewDialog(plan, allow_install=False)
                try:
                    self.assertIn(rendered, d.findChild(
                        type(d.status), "installReviewOverview").text())
                    self.assertIn(f"{size:,} bytes", d.findChild(
                        type(d.status), "installReviewOverview").toolTip())
                    self.assertEqual(d.targets.item(0, 2).text(), rendered)
                    self.assertIn(f"{size:,} bytes",
                                  d.targets.item(0, 2).toolTip())
                    self.assertIn(rendered, d.notes.toPlainText())
                    self.assertFalse(d.apply_button.isEnabled())
                    self.assertEqual(d.plan.backup_bytes, size)
                finally:
                    d.close()
                    d.deleteLater()
                    self.app.processEvents()

    def test_install_cannot_be_enabled_without_all_three_checks(self):
        d = self.create_dialog()
        self.assertFalse(d.apply_button.isEnabled())
        self.assertFalse(d.confirmed_by_user)
        d.confirm_targets.setChecked(True)
        d.confirm_backup.setChecked(True)
        self.assertFalse(d.apply_button.isEnabled())
        d.confirm_closed.setChecked(True)
        self.assertTrue(d.apply_button.isEnabled())
        self.assertFalse(d.targets.isVisible())
        d.manifest_toggle.setChecked(True)
        self.assertTrue(d.apply_button.isEnabled())
        self.assertTrue(d.targets.columnCount() == 3)
        self.assertEqual(d.targets.item(0, 0).text(),
                         "BepInEx/plugins/VR0.dll")
        self.assertIn("Persistent", d.notes.toPlainText())
        d.apply_button.click()
        self.assertTrue(d.confirmed_by_user)
        self.assertEqual(d.result(), QDialog.Accepted)

    def test_blockers_always_disable_install_even_if_acknowledged(self):
        d = self.create_dialog(blocked=(
            "Existing mod would be overwritten without retained backup",))
        for c in (d.confirm_targets, d.confirm_backup, d.confirm_closed):
            c.setChecked(True)
        self.assertFalse(d.apply_button.isEnabled())
        self.assertFalse(d.confirmed_by_user)
        d.manifest_toggle.setChecked(True)
        self.assertFalse(d.apply_button.isEnabled())
        self.assertIn("BLOCKED", d.status.text())
        self.assertIn("Existing mod", d.notes.toPlainText())

    def test_preview_always_disables_install_even_with_three_checks(self):
        d = self.create_dialog(allow_install=False)
        for c in (d.confirm_targets, d.confirm_backup, d.confirm_closed):
            c.setChecked(True)
        self.assertFalse(d.apply_button.isEnabled())
        d._accept_confirmed()
        self.assertFalse(d.confirmed_by_user)
        self.assertNotEqual(d.result(), QDialog.Accepted)
        self.assertIn("PREVIEW ONLY", d.status.text())

    def test_cancel_never_confirms(self):
        d = self.create_dialog()
        d.confirm_targets.setChecked(True)
        d.cancel_button.click()
        self.assertEqual(d.result(), QDialog.Rejected)
        self.assertFalse(d.confirmed_by_user)


class HubGuidedInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.library = self.root / "archives"
        self.library.mkdir()
        for p in (
            mock.patch.object(planner, "preferences_file",
                              return_value=self.root / "prefs.json"),
            mock.patch.object(planner, "default_library",
                              return_value=self.library),
            mock.patch.object(archive_scans, "snapshot_file",
                              return_value=self.root / "scans.json"),
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        index = next(i for i, row in enumerate(self.window.rows)
                     if row["recipe"]["id"] == "valheim")
        self.window.sidebar.game_list.setCurrentRow(index)
        self.app.processEvents()
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_downloads_page_emits_review_request_for_current_recipe(self):
        events = []
        self.window.downloads.install_review_requested.connect(events.append)
        with mock.patch.object(self.window, "_pick_many",
                               return_value=[]) as picker:
            self.window.downloads.install_review_button.click()
        picker.assert_called_once()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["game_id"], "valheim")
        self.assertEqual(events[0]["origin"], "downloads-page")

    def test_main_install_button_routes_through_review_not_direct_installer(self):
        selected = self.root / "selected.zip"
        selected.write_bytes(b"test")
        with mock.patch.object(self.window, "_pick_many",
                               return_value=[selected]), mock.patch.object(
                self.window, "review_installation") as review, mock.patch(
                "vrhub.gui.hub.install_many") as install:
            self.window.install()
        review.assert_called_once()
        self.assertEqual(review.call_args.args[0]["id"], "valheim")
        self.assertEqual(review.call_args.args[1], [selected])
        install.assert_not_called()

    def test_existing_profile_button_cannot_bypass_review(self):
        with mock.patch.object(self.window, "_pick", return_value=None), mock.patch(
                "vrhub.gui.hub.install_profile") as install:
            self.window.install_profile()
        install.assert_not_called()

    def test_profile_request_reuses_exact_path_and_never_installs(self):
        self.window.sidebar.game_list.setCurrentRow(next(
            i for i, row in enumerate(self.window.rows)
            if row["recipe"]["id"] == "fatekeeper"))
        path = self.root / "SLASHER-Win64-Shipping.zip"
        with mock.patch.object(self.window, "_pick") as picker, mock.patch(
                "vrhub.gui.hub.review_profile_install") as plan, mock.patch(
                "vrhub.gui.ProfileReviewDialog") as dialog, mock.patch(
                "vrhub.gui.hub.install_profile") as install:
            # Even a faulty dialog reporting accepted cannot authorize writes.
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.confirmed_by_user = True
            self.window.review_requested_install({
                "game_id": "fatekeeper", "route": "profile",
                "archives": [str(path)], "origin": "downloads-page"})
            picker.assert_not_called()
            self.assertEqual(plan.call_args.args[1], path)
            self.assertFalse(dialog.call_args.kwargs["allow_install"])
            install.assert_not_called()

    def test_wrong_game_or_wrong_route_cannot_review(self):
        with mock.patch.object(self.window, "_pick") as picker, mock.patch.object(
                self.window, "review_profile_archive") as profile:
            for rid in ("fatekeeper", "valheim"):
                self.window.review_requested_install({
                    "game_id": rid, "route": "profile", "archives": ["wrong.zip"]})
            picker.assert_not_called()
            profile.assert_not_called()

    def test_guide_route_navigates_without_picker(self):
        with mock.patch.object(self.window, "_pick_many") as picker:
            self.window.review_requested_install({
                "game_id": "valheim", "route": "guide", "archives": []})
            self.assertIs(self.window.game_details_tabs.currentWidget(), self.window.details)
            picker.assert_not_called()

    def test_cancelling_dialog_never_invokes_install(self):
        with mock.patch("vrhub.gui.install_review.build_install_plan",
                        return_value=fixture_plan()), mock.patch(
                "vrhub.gui.InstallReviewDialog") as dialog, mock.patch(
                "vrhub.gui.hub.install_many") as install, mock.patch.object(
                self.window, "_run") as runner:
            dialog.return_value.exec.return_value = QDialog.Rejected
            dialog.return_value.confirmed_by_user = False
            self.window.review_installation(self.window.current(), [
                self.root / "fake.zip"])
        runner.assert_not_called()
        install.assert_not_called()

    def test_preview_kill_switch_guards_even_forged_acceptance(self):
        self.window.allow_guided_installs = False
        with mock.patch("vrhub.gui.install_review.build_install_plan",
                        return_value=fixture_plan()), mock.patch(
                "vrhub.gui.InstallReviewDialog") as dialog, mock.patch(
                "vrhub.gui.hub.install_many") as install, mock.patch.object(
                self.window, "_run") as runner:
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.confirmed_by_user = True
            self.window.review_installation(self.window.current(), [
                self.root / "fake.zip"])
            self.assertFalse(dialog.call_args.kwargs["allow_install"])
        runner.assert_not_called()
        install.assert_not_called()

    def test_revalidation_failure_cancels_before_install(self):
        with mock.patch("vrhub.gui.install_review.build_install_plan",
                        return_value=fixture_plan()), mock.patch(
                "vrhub.gui.InstallReviewDialog") as dialog, mock.patch(
                "vrhub.gui.install_review.revalidate",
                side_effect=install_review.PlanRejected("changed after review")), mock.patch(
                "vrhub.gui.QMessageBox.warning") as warn, mock.patch.object(
                self.window, "_run") as runner, mock.patch(
                "vrhub.gui.hub.install_many") as install:
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.confirmed_by_user = True
            self.window.review_installation(self.window.current(),
                                            [self.root / "selected.zip"])
        warn.assert_called_once()
        self.assertIn("changed after review", warn.call_args.args[2])
        runner.assert_not_called()
        install.assert_not_called()

    def test_explicit_consent_and_revalidation_only_authorizes_named_archives(self):
        plan = fixture_plan()
        with mock.patch("vrhub.gui.install_review.build_install_plan",
                        return_value=plan), mock.patch(
                "vrhub.gui.InstallReviewDialog") as dialog, mock.patch(
                "vrhub.gui.install_review.revalidate", return_value=plan) as verify, mock.patch(
                "vrhub.gui.hub.install_many", return_value=[]) as install, mock.patch(
                "vrhub.gui.QMessageBox.information"), mock.patch.object(
                self.window, "refresh"):
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.confirmed_by_user = True
            self.window.review_installation(self.window.current(),
                                            [self.root / "selected.zip"])
        verify.assert_called_once()
        install.assert_called_once()
        self.assertEqual([str(p) for p in install.call_args.args[1]],
                         ["/tmp/archives/test.zip"])

    def test_blocked_plan_cannot_install_even_if_dialog_was_forged(self):
        with mock.patch("vrhub.gui.install_review.build_install_plan",
                        return_value=fixture_plan(blocked=("block",))), mock.patch(
                "vrhub.gui.InstallReviewDialog") as dialog, mock.patch.object(
                self.window, "_run") as runner:
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.confirmed_by_user = True
            self.window.review_installation(self.window.current(),
                                            [self.root / "test.zip"])
        runner.assert_not_called()

    def test_current_game_mismatch_does_not_show_review(self):
        wrong = {"id": "other", "name": "Other"}
        with mock.patch("vrhub.gui.InstallReviewDialog") as dialog:
            self.window.review_installation(wrong, [self.root / "x.zip"])
        dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
