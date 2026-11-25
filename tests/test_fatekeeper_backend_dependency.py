# SPDX-License-Identifier: GPL-3.0-only
"""Dev5E2: Fatekeeper's tested DLL is a real dependency, not a third ZIP."""
import os
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from vrhub import download_planner, hub, updates
from vrhub import fatekeeper_backend_status
from vrhub.mod_updates_gui import grouped_updates
from vrhub.uevr_dependency_review import FATEKEEPER_BACKEND_SHA256, FATEKEEPER_BACKEND_SIZE


class FatekeeperBackendDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = hub.load_recipes()["fatekeeper"]

    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        self.root = Path(self.temp)
        self.injector = self.root / "uevr"
        self.injector.mkdir()
        self.file = self.injector / "UEVRBackend.dll"
        self.good = b"tested backend payload from a disposable fixture"
        self.digest = sha256(self.good).hexdigest()
        self.enterContext(patch.object(hub, "_uevr_dir", return_value=self.injector))
        self.enterContext(patch("vrhub.uevr_dependency_review.FATEKEEPER_BACKEND_SHA256",
                                self.digest))
        self.enterContext(patch("vrhub.uevr_dependency_review.FATEKEEPER_BACKEND_SIZE",
                                len(self.good)))

    def backend(self, *, state=None):
        rows = updates.check_recipe(self.recipe, {} if state is None else state)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["dependency_type"] for r in rows], ["Mod", "Profile", "Backend"])
        return rows[-1], rows

    def test_recipe_keeps_exactly_two_archive_dependencies(self):
        self.assertEqual([c["id"] for c in download_planner.plan_components(self.recipe)],
                         ["uevr", "profile"])
        self.assertEqual(set(self.recipe["archive_releases"]), {"uevr", "profile"})
        self.assertEqual(self.recipe["updates"][-1]["verified_backend"], True)
        self.assertEqual(FATEKEEPER_BACKEND_SHA256,
                         "b883dd7f0b5e06bff74b42b4fabc66fc7c39c6baff57634d5132abe5b05ed6fc")
        self.assertEqual(FATEKEEPER_BACKEND_SIZE, 15_203_840)

    def test_verified_exact_bytes_are_not_inferred_from_hub_timestamp(self):
        self.file.write_bytes(self.good)
        before = self.file.read_bytes()
        result, rows = self.backend(state={"fatekeeper": {"installed_at": 1}})
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["installed_version"], "100526UE58_6RefreshUpdate")
        self.assertIn("SHA-256", result["detail"])
        self.assertIn("not Hub ownership", result["detail"])
        self.assertEqual(updates.release_count(rows), 0)
        grouped = grouped_updates(self.recipe, rows)
        self.assertEqual(grouped["current"][0]["status"], "Verified pinned build")
        self.assertEqual(grouped["current"][0]["type"], "Backend")
        self.assertIn("joeyhodge/UEVR/releases/tag/", grouped["current"][0]["page"])
        self.assertEqual(self.file.read_bytes(), before)

    def test_missing_file_is_not_installed_even_with_hub_record(self):
        result, rows = self.backend(state={"fatekeeper": {"installed_at": 999999999}})
        self.assertEqual(result["status"], "not_installed")
        self.assertNotIn("installed_version", result)
        self.assertIn("gated", result["detail"])
        self.assertEqual(updates.release_count(rows), 0)

    def test_same_size_wrong_sha_needs_review(self):
        self.file.write_bytes(b"x" * len(self.good))
        before = self.file.read_bytes()
        result, rows = self.backend()
        self.assertEqual(result["status"], "unknown")
        self.assertIn("SHA-256", result["detail"])
        self.assertIn("not overwrite", result["detail"])
        self.assertEqual(updates.release_count(rows), 0)
        self.assertEqual(self.file.read_bytes(), before)

    def test_wrong_size_needs_review(self):
        self.file.write_bytes(self.good + b"x")
        result, rows = self.backend()
        self.assertEqual(result["status"], "unknown")
        self.assertIn("size", result["detail"])
        self.assertEqual(updates.release_count(rows), 0)

    def test_symlinked_backend_is_not_followed(self):
        real = self.root / "external.dll"
        real.write_bytes(self.good)
        self.file.symlink_to(real)
        result, _ = self.backend()
        self.assertEqual(result["status"], "unknown")
        self.assertIn("symlink", result["detail"].lower())
        self.assertEqual(real.read_bytes(), self.good)

    def test_symlinked_injector_folder_refused(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        (outside / "UEVRBackend.dll").write_bytes(self.good)
        self.injector.rmdir()
        self.injector.symlink_to(outside, target_is_directory=True)
        result, _ = self.backend()
        self.assertEqual(result["status"], "unknown")
        self.assertIn("symlink", result["detail"].lower())

    def test_no_proton_prefix_is_unknown_not_missing(self):
        with patch.object(hub, "_uevr_dir", side_effect=RuntimeError("game unavailable")):
            result, _ = self.backend()
        self.assertEqual(result["status"], "unknown")
        self.assertIn("Cannot locate", result["detail"])

    def test_non_fatekeeper_does_not_accept_pinned_backend_check(self):
        with self.assertRaises(ValueError):
            fatekeeper_backend_status.check_backend({"id": "hogwarts-legacy"})

    def test_install_update_explains_automatic_backend_install_without_third_zip(self):
        from PySide6.QtWidgets import QApplication
        from vrhub import archive_scans
        from vrhub.downloads_gui import GuidedDownloadsPage
        app = QApplication.instance() or QApplication([])
        with (patch.object(download_planner, "preferences_file",
                           return_value=self.root / "prefs.json"),
              patch.object(download_planner, "default_library",
                           return_value=self.root),
              patch.object(archive_scans, "snapshot_file",
                           return_value=self.root / "scans.json")):
            page = GuidedDownloadsPage()
            try:
                page.set_recipe(self.recipe)
                self.assertIn("Missing", page.backend_install_status.text())
                self.assertIn("automatically download and verify", page.backend_install_status.text())
                self.assertIn("No manual DLL copying", page.backend_install_status.text())
                self.assertEqual(page.table.rowCount(), 2)  # only the ZIPs

                self.file.write_bytes(self.good)
                page.set_recipe(self.recipe)
                self.assertIn("Tested version installed and verified",
                              page.backend_install_status.text())
                self.assertIn("preserve", page.backend_install_status.text())
                self.assertEqual(page.table.rowCount(), 2)

                self.file.write_bytes(b"modified")
                page.set_recipe(self.recipe)
                self.assertIn("Needs review", page.backend_install_status.text())
                self.assertIn("will not be silently overwritten",
                              page.backend_install_status.text())

                page.set_recipe(hub.load_recipes()["hogwarts-legacy"])
                self.assertTrue(page.backend_install_status.isHidden())
                self.assertFalse(page.backend_install_status.text())
            finally:
                page.close()
                page.deleteLater()
                app.processEvents()

    def test_pending_recovery_blocks_existing_install_action(self):
        from PySide6.QtWidgets import QApplication
        from vrhub.downloads_gui import GuidedDownloadsPage
        from vrhub import archive_scans
        app = QApplication.instance() or QApplication([])
        self.file.write_bytes(self.good)
        state = self.root / "state.json"
        journal = self.root / "fatekeeper-recovery/fk4-journal.json"
        journal.parent.mkdir()
        journal.write_text('{"schema":2,"phase":"applying"}')
        with (patch.object(hub,"state_file",return_value=state),
              patch.object(download_planner,"preferences_file",return_value=self.root/"prefs.json"),
              patch.object(download_planner,"default_library",return_value=self.root),
              patch.object(archive_scans,"snapshot_file",return_value=self.root/"scans.json")):
            page=GuidedDownloadsPage()
            try:
                page.set_recipe(self.recipe)
                self.assertIn("recovery pending",page.backend_install_status.text())
                self.assertEqual(page._primary_action(),("recovery-blocked","Recovery required"))
                self.assertFalse(page.install_review_button.isEnabled())
                self.assertIsNone(page._manual_review_route())
                self.assertEqual(page.table.rowCount(),2)
            finally:
                page.close(); page.deleteLater(); app.processEvents()

    def test_install_update_guidance_explains_prefix_prerequisite(self):
        from vrhub.fatekeeper_backend_status import install_update_guidance
        message = install_update_guidance({
            "status": "unknown", "detail": "Cannot locate the Fatekeeper Proton prefix: game unavailable."
        })
        self.assertIn("Launch Fatekeeper once from Steam", message)
        self.assertIn("then scan the two ZIP archives", message)

    def test_row_is_read_only_and_never_offers_an_archive_install(self):
        self.file.write_bytes(self.good)
        from PySide6.QtWidgets import QApplication
        from vrhub.mod_updates_gui import ModUpdatesPage
        app = QApplication.instance() or QApplication([])
        records = updates.check_recipe(self.recipe, {})
        page = ModUpdatesPage()
        try:
            grouped = page.set_recipe(self.recipe, records)
            table = page.sections["current"].table
            self.assertEqual(table.rowCount(), 1)
            self.assertEqual(table.item(0, 0).text(), "UEVRBackend.dll (joeyhodge)")
            self.assertEqual(table.item(0, 3).text(), "✓  Verified pinned build")
            self.assertEqual(table.item(0, 5).text(), "Backend")
            self.assertEqual(table.cellWidget(0, 4).text(), "Open source")
            self.assertEqual(page.sections["update"].table.rowCount(), 0)
            self.assertEqual(len(grouped["not_installed"]), 2)
            self.assertIn("3 dependencies checked", page.summary.text())
            self.assertIn("1 tested build verified", page.summary.text())
            self.assertIn("0 up to date", page.summary.text())
            self.assertIn("Verified pinned builds (1)",
                          page.sections["current"].disclosure.text())
        finally:
            page.close()
            page.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
