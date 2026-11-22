# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5B2 Qt safety: user authorization, manual-only gating, progress, cancel."""
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from vrhub import hub, archive_scans, download_planner as planner
from vrhub import verified_download as engine
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow


class QtVerifiedDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / "archives"
        self.folder.mkdir()
        for p in (
            mock.patch.object(planner, "preferences_file",
                              return_value=self.root / "preferences.json"),
            mock.patch.object(planner, "default_library",
                              return_value=self.folder),
            mock.patch.object(archive_scans, "snapshot_file",
                              return_value=self.root / "snapshots.json"),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.page = GuidedDownloadsPage()
        self.page.resize(1180, 780)
        self.page.show()
        self.app.processEvents()
        self.addCleanup(self.dispose)

    def dispose(self):
        if self.page.download_worker and self.page.download_worker.isRunning():
            self.page.download_worker.cancel()
            self.page.download_worker.wait(4000)
            self.app.processEvents()
        self.page.close()
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def select_valheim(self):
        recipe = hub.load_recipes()["valheim"]
        self.page.set_recipe(recipe)
        comps = planner.plan_components(recipe)
        row = next(i for i,c in enumerate(comps) if c["id"] == "vhvr")
        self.page.table.selectRow(row)
        self.app.processEvents()
        return recipe, comps[row]

    def wait_transfer(self):
        deadline = time.monotonic() + 5
        while self.page.download_worker is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertIsNone(self.page.download_worker, "worker did not close")

    def test_nexus_unpinned_row_disables_transfer(self):
        self.page.set_recipe(hub.load_recipes()["cyberpunk-2077"])
        self.page.table.selectRow(0)
        self.app.processEvents()
        self.assertFalse(self.page.download_button.isEnabled())
        self.assertTrue(self.page.download_button.isHidden())
        self.assertTrue(self.page.download_status.isHidden())
        self.assertIn("No pinned SHA-256", self.page.download_status.text())
        self.assertTrue(self.page.table.cellWidget(0, 4).isEnabled())

    def test_valheim_pinned_github_row_enables_transfer(self):
        recipe, item = self.select_valheim()
        self.assertTrue(self.page.download_button.isEnabled())
        self.assertTrue(self.page.download_button.isVisible())
        self.assertIn("SHA-256 verified", self.page.download_status.text())
        self.assertFalse(self.page.download_cancel.isEnabled())
        self.assertTrue(self.page.download_cancel.isHidden())

    def test_game_switch_and_scan_never_start_network_transfer(self):
        with mock.patch("vrhub.downloads_gui.verified_download.download",
                        side_effect=AssertionError("unexpected network call")) as fetch:
            for rid in ("cyberpunk-2077", "valheim", "subnautica", "elden-ring"):
                self.page.set_recipe(hub.load_recipes()[rid])
                self.page.table.selectRow(0)
                self.app.processEvents()
            self.assertIsNone(self.page.download_worker)
            fetch.assert_not_called()

    def test_confirmation_defaults_to_no_and_starts_nothing(self):
        self.select_valheim()
        direct = ("https://github.com/brandonmousseau/vhvr-mod/"
                  "releases/download/v0.11.2/VHVR-test.zip")
        with mock.patch("vrhub.downloads_gui.QInputDialog.getText",
                        return_value=(direct, True)), mock.patch(
                    "vrhub.downloads_gui.QMessageBox.question",
                    return_value=QMessageBox.No) as question, mock.patch.object(
                    self.page, "_start_verified_download") as transfer:
            self.page.download_button.click()
        transfer.assert_not_called()
        self.assertEqual(question.call_count, 1)
        self.assertIn("Expected SHA-256", question.call_args.args[2])
        self.assertIn("THIS WILL NOT INSTALL", question.call_args.args[2])
        self.assertEqual(question.call_args.args[-1], QMessageBox.No)
        self.assertFalse(list(self.folder.iterdir()))

    def test_confirm_yes_passes_recipe_pinned_authorization_only(self):
        recipe, selected = self.select_valheim()
        direct = ("https://github.com/brandonmousseau/vhvr-mod/"
                  "releases/download/v0.11.2/VHVR-test.zip")
        with mock.patch("vrhub.downloads_gui.QInputDialog.getText",
                        return_value=(direct, True)), mock.patch(
                    "vrhub.downloads_gui.QMessageBox.question",
                    return_value=QMessageBox.Yes), mock.patch.object(
                    self.page, "_start_verified_download") as transfer:
            self.page.download_button.click()
        transfer.assert_called_once()
        authority = transfer.call_args.args[0]
        self.assertEqual(authority.game_id, "valheim")
        self.assertEqual(authority.component_id, "vhvr")
        self.assertEqual(authority.expected_sha256, selected["sha256"])
        self.assertEqual(authority.destination_folder, self.folder)
        self.assertEqual(authority.destination_name, "VHVR-test.zip")

    def test_untrusted_url_warns_before_confirmation_or_network(self):
        self.select_valheim()
        with mock.patch("vrhub.downloads_gui.QInputDialog.getText",
                        return_value=("https://evil.example/asset.zip", True)), mock.patch(
                    "vrhub.downloads_gui.QMessageBox.warning") as warning, mock.patch(
                    "vrhub.downloads_gui.QMessageBox.question") as confirmation, mock.patch.object(
                    self.page, "_start_verified_download") as transfer:
            self.page.download_button.click()
        warning.assert_called_once()
        confirmation.assert_not_called()
        transfer.assert_not_called()

    def test_dialog_cancel_never_starts_transfer(self):
        self.select_valheim()
        with mock.patch("vrhub.downloads_gui.QInputDialog.getText",
                        return_value=("", False)), mock.patch.object(
                    self.page, "_start_verified_download") as transfer:
            self.page.download_button.click()
        transfer.assert_not_called()

    def test_isolated_preview_cannot_transfer_even_after_selection_changes(self):
        self.page.allow_transfers = False
        self.select_valheim()
        self.assertFalse(self.page.download_button.isEnabled())
        with mock.patch("vrhub.downloads_gui.QInputDialog.getText") as prompt, mock.patch.object(
                self.page, "_start_verified_download", wraps=self.page._start_verified_download):
            self.page.download_button.click()
            prompt.assert_not_called()
        self.assertIsNone(self.page.download_worker)

    def test_mocked_success_reports_verification_but_does_not_install(self):
        recipe, selected = self.select_valheim()
        direct = ("https://github.com/brandonmousseau/vhvr-mod/"
                  "releases/download/v0.11.2/VHVR-test.zip")
        authorization = engine.create_authorization(
            recipe, selected, direct, self.folder)
        result = engine.DownloadResult(
            self.folder / authorization.destination_name,
            authorization.expected_sha256, 128, False)
        with mock.patch("vrhub.downloads_gui.verified_download.download",
                        return_value=result) as net, mock.patch(
                    "vrhub.downloads_gui.planner.build_plan",
                    return_value={"game_id": "valheim",
                                  "folder": str(self.folder),
                                  "rows": [{**c, "status": "Not found locally",
                                            "file": "", "matches": 0,
                                            "size": 0,
                                            "phase_label": "Stage 1: prerequisites"}
                                           for c in planner.plan_components(recipe)],
                                  "scanned": 0, "warning": None, "verified": 0,
                                  "possible": 0, "mismatch": 0,
                                  "unverified": 0, "missing": 2}):
            self.page._start_verified_download(authorization)
            self.wait_transfer()
            deadline = time.monotonic() + 3
            while self.page.worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
        self.assertEqual(net.call_count, 1)
        self.assertIn("SHA-256 verified", self.page.download_status.text())
        self.assertIn("No mods installed", self.page.download_status.text())

    def test_cancel_requests_worker_stop_and_disables_cancel_button(self):
        recipe, selected = self.select_valheim()
        authorization = engine.create_authorization(
            recipe, selected,
            "https://github.com/brandonmousseau/vhvr-mod/releases/download/v0.11.2/VHVR-test.zip",
            self.folder)
        invoked = Event()

        def cancellable(authority, *, cancel_event, progress):
            invoked.set()
            until = time.monotonic() + 3
            while not cancel_event.is_set() and time.monotonic() < until:
                time.sleep(0.01)
            raise engine.DownloadCancelled("Download cancelled; partial file discarded.")
        with mock.patch("vrhub.downloads_gui.verified_download.download",
                        side_effect=cancellable):
            self.page._start_verified_download(authorization)
            self.assertTrue(invoked.wait(2))
            self.assertTrue(self.page.download_cancel.isVisible())
            self.assertTrue(self.page.download_status.isVisible())
            self.assertTrue(self.page.download_button.isHidden())
            self.page.cancel_download()
            self.page._update_download_button()
            self.assertFalse(self.page.download_cancel.isEnabled())
            self.assertTrue(self.page.download_cancel.isVisible())
            self.wait_transfer()
        self.assertTrue(self.page.download_cancel.isHidden())
        self.assertTrue(self.page.download_status.isVisible())
        self.assertIn("cancelled", self.page.download_status.text().lower())
        self.assertFalse(list(self.folder.iterdir()))

    def test_progress_display_accepts_large_byte_counts(self):
        recipe, selected = self.select_valheim()
        authority = engine.create_authorization(
            recipe, selected,
            "https://github.com/brandonmousseau/vhvr-mod/releases/download/v0.11.2/VHVR-test.zip",
            self.folder)
        fake = mock.Mock(authority=authority)
        self.page.download_worker = fake
        self.page._download_progress(2_600_000_000, 3_000_000_000, fake)
        self.assertEqual(self.page.download_progress.value(), 86)
        self.page.download_worker = None

class WindowTransferShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_parent_window_does_not_close_with_active_transfer(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        for patcher in (
            mock.patch.object(planner, "default_library", return_value=folder),
            mock.patch.object(planner, "preferences_file", return_value=folder / "prefs.json"),
            mock.patch.object(archive_scans, "snapshot_file", return_value=folder / "scans.json"),
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup")
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        window = HubWindow()
        window.show()
        self.app.processEvents()
        active = mock.Mock()
        active.isRunning.return_value = True
        with mock.patch.object(window.downloads, "download_worker", active):
            window.close()
            self.assertTrue(window.isVisible())
            active.cancel.assert_called()
        window.close_when_idle()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

if __name__ == "__main__":
    unittest.main()
