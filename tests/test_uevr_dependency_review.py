# SPDX-License-Identifier: GPL-3.0-only
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication
from vrhub import hub, uevr_dependency_review as review
from vrhub.uevr_dependency_review_gui import DependencyReviewDialog


class DependencyReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.prefix = self.root / "prefix"
        self.prefix.mkdir()
        self.dest = self.prefix / "drive_c/uevr"
        self.profile = self.prefix / "drive_c/users/steamuser/AppData/Roaming/UnrealVRMod/test"
        self.injector_zip = self.root / "injector.zip"
        self.profile_zip = self.root / "profile.zip"
        self.write_zip(self.injector_zip, {"UEVR/UEVRInjector.exe": b"exe", "UEVR/UEVRBackend.dll": b"dll"})
        self.write_zip(self.profile_zip, {"test/config.txt": b"config", "test/plugins/custom.dll": b"custom"})
        self.recipe = hub.load_recipes()["fatekeeper"]
        for patcher in (
            mock.patch.object(hub, "_pfx", return_value=self.prefix),
            mock.patch.object(hub, "_uevr_dir", return_value=self.dest),
            mock.patch.object(hub, "profile_dir", return_value=self.profile),
            mock.patch.object(hub, "state_file", return_value=self.root / "isolated-state.json"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_zip(self, path, members):
        with zipfile.ZipFile(path, "w") as z:
            for name, data in members.items():
                z.writestr(name, data)

    def plan(self, **kwargs):
        return review.build_plan(self.recipe, [self.injector_zip, self.profile_zip], **kwargs)

    def test_both_destinations_and_no_writes(self):
        self.dest.mkdir(parents=True)
        (self.dest / "custom.ini").write_bytes(b"personal")
        self.profile.mkdir(parents=True)
        (self.profile / "config.txt").write_bytes(b"old")
        plan = self.plan()
        self.assertEqual(plan.injector_destination, str(self.dest))
        self.assertEqual(plan.profile.destination, str(self.profile))
        self.assertEqual(plan.existing_bytes, 8)
        self.assertEqual(plan.profile.existing_bytes, 3)
        self.assertIn("recovery review", plan.blockers[0])
        self.assertEqual((self.dest / "custom.ini").read_bytes(), b"personal")
        self.assertEqual((self.profile / "config.txt").read_bytes(), b"old")
        self.assertFalse((self.root / "isolated-state.json").exists())

    def test_unsafe_injector_zip_and_missing_backend_rejected(self):
        for entries in ({"UEVRInjector.exe": b"exe"}, {"../escape": b"x"},
                        {"UEVRInjector.exe": b"exe", "UEVRBackend.dll": b"dll", "A": b"a", "A/file": b"b"}):
            self.write_zip(self.injector_zip, entries)
            with self.assertRaises(RuntimeError):
                self.plan()

    def test_symlink_target_rejected(self):
        self.dest.parent.mkdir()
        self.dest.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.plan()

    def test_same_archive_and_wrong_roles_rejected(self):
        for files in ([self.profile_zip]*2, [self.profile_zip, self.injector_zip]):
            with self.assertRaises(RuntimeError):
                review.build_plan(self.recipe, files)

    def test_hogwarts_unknown_pair_explicitly_blocked(self):
        self.recipe = hub.load_recipes()["hogwarts-legacy"]
        plan = self.plan()
        self.assertTrue(any("Matching Hogwarts Legacy" in b for b in plan.blockers))

    def test_changed_digest_evidence_rejected(self):
        from vrhub.download_planner import archive_identity
        evidence = [{"file": str(self.injector_zip), "identity": archive_identity(self.injector_zip),
                     "sha256": "0"*64, "tags": ["1.0.0"]}, None]
        with self.assertRaisesRegex(RuntimeError, "evidence changed"):
            self.plan(evidence=evidence)

    def test_dialog_cannot_apply(self):
        dialog = DependencyReviewDialog(self.plan())
        self.addCleanup(dialog.close)
        dialog.show()
        self.app.processEvents()
        self.assertEqual(dialog.archives.rowCount(), 2)
        self.assertFalse(dialog.inventory.isVisible())
        dialog.inventory_toggle.click()
        self.assertTrue(dialog.inventory.isVisible())
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertIn("LIVE INSTALLATION DISABLED", dialog.status.text())
        dialog.apply_button.click()
        self.assertTrue(dialog.isVisible())
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.profile.exists())
