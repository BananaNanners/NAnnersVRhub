# SPDX-License-Identifier: GPL-3.0-only
"""Disposable Qt integration of recognition with existing controls."""
from threading import Event
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from vrhub import hub, profile_safety, uevr_dependency_review as review, fatekeeper_recognition as recognition
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.uevr_dependency_review_gui import DependencyReviewDialog
from vrhub.gui import HubWindow
from vrhub.app_update_gui import HubUpdateController
from tests.test_fatekeeper_recognition import RecognitionTests


class RecognitionGuiTests(RecognitionTests):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def rows(self):
        return [dict(id=role, status='Pinned SHA-256 verified', file=str(path), sha256=self.recipe['archive_pins'][role]) for role,path in zip(('uevr','profile'), self.archives)]

    def page(self):
        root=self.state.parent
        for name, value in (('vrhub.download_planner.preferences_file',root/'prefs.json'),('vrhub.download_planner.default_library',root),('vrhub.archive_scans.snapshot_file',root/'scans.json')):
            self.enterContext(patch(name,return_value=value))
        page=GuidedDownloadsPage(); self.addCleanup(page.close); page.show(); page.set_recipe(self.recipe)
        return page

    def wait(self,page):
        for _ in range(300):
            if page.integrity_worker is None: break
            QTest.qWait(10)
        self.assertIsNone(page.integrity_worker)

    def test_maintenance_labels_and_stale_evidence(self):
        page = self.page()
        rows = self.rows()
        page._last_plan = {"rows": rows}
        with patch("vrhub.fatekeeper_commit.recovery_notice", return_value=""):
            self.assertEqual(page._primary_action(), ("uevr-pair", "Review installation"))
            page.recognition_result = self.scan()
            self.assertEqual(page._primary_action(), ("uevr-pair", "Review verified dependencies"))
            (self.injector / "UEVRBackend.dll").unlink()
            page.recognition_result = self.scan()
            self.assertEqual(page._primary_action(), ("uevr-pair", "Review repair"))
            rows[0]["ambiguous"] = True
            self.assertEqual(page._primary_action(), ("uevr-pair", "Choose archive"))
            rows[0]["ambiguous"] = False
            rows[0]["status"] = "Hash mismatch — do not install"
            self.assertEqual(page._primary_action(), ("uevr-hash-review", "Review installation"))
            rows[0]["status"] = "Pinned SHA-256 verified"
            page.set_recipe(self.recipe)
            page._last_plan = {"rows": rows}
            self.assertIsNone(page.recognition_result)
            self.assertEqual(page._primary_action(), ("uevr-pair", "Review installation"))

    def test_maintenance_dialog_labels_preserve_gate(self):
        from dataclasses import replace
        plan = review.build_plan(self.recipe, self.archives)
        dialog = DependencyReviewDialog(plan, install_action=lambda *_: self.fail("unexpected write"),
                                        install_authorized=lambda: False)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.apply_button.text(), "No dependency changes needed")
        self.assertIn("Recovery evidence is checked separately", dialog.blockers.text())
        self.assertFalse(dialog.apply_button.isEnabled())
        (self.profile / "plugin.dll").write_bytes(b"changed")
        plan = review.build_plan(self.recipe, self.archives)
        repair = DependencyReviewDialog(plan, install_action=lambda *_: self.fail("unexpected write"),
                                        install_authorized=lambda: False)
        self.addCleanup(repair.close)
        self.assertEqual(repair.apply_button.text(), "Apply reviewed repair")
        self.assertFalse(repair.apply_button.isEnabled())
        repair.run_rehearsal()
        self.assertFalse(repair.install_attempted)
        blocked = replace(plan, compatibility_blockers=("obsolete",))
        self.assertEqual(recognition.summarize_plan(blocked)["maintenance"], "blocked")
        dialog = DependencyReviewDialog(blocked, install_authorized=lambda: True)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.apply_button.text(), "Compatibility review required")
        self.assertFalse(dialog.apply_button.isEnabled())

    def test_maintenance_cross_game_and_recovery_priority(self):
        page = self.page()
        page._last_plan = {"rows": self.rows()}
        page.recognition_result = {"maintenance": "repair-review"}
        with patch("vrhub.fatekeeper_commit.recovery_notice", return_value="pending"):
            self.assertEqual(page._primary_action(), ("recovery-blocked", "Recovery required"))
        page.set_recipe(hub.load_recipes()["hogwarts-legacy"])
        page._last_plan = {"rows": self.rows()}
        page.recognition_result = {"maintenance": "repair-review"}
        self.assertEqual(page._primary_action(), ("uevr-pair", "Review installation"))

    def test_existing_review_noop_stays_disabled_and_reports_blockers(self):
        plan=review.build_plan(self.recipe,self.archives)
        dialog=DependencyReviewDialog(plan,install_action=lambda *_:self.fail('no writes'),install_authorized=lambda:True)
        self.addCleanup(dialog.close)
        self.assertIn('Verified existing dependencies',dialog.blockers.text())
        self.assertIn('3 immutable matches',dialog.blockers.text())
        self.assertIn('recovery review',dialog.blockers.text())
        self.assertEqual(dialog.backup.text(),'Install 0 / Replace 0 / Preserve 6')
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.run_rehearsal()
        self.assertFalse(dialog.install_attempted)

    def test_compatibility_blocker_disables_all_install_paths(self):
        from dataclasses import replace
        plan = review.build_plan(self.recipe, self.archives)
        blocker = "Profile: old.dll is no longer supplied. Preserved; compatibility review required."
        plan = replace(plan, compatibility_blockers=(blocker,), blockers=(blocker,),
                       file_decisions=tuple(("Replace", role, name) if (role, name)==("Profile", "plugin.dll") else (action, role, name) for action, role, name in plan.file_decisions),
                       needs_backend_verification=True)
        for disposable in (False, True):
            with self.subTest(disposable=disposable):
                with patch("vrhub.uevr_dependency_review_gui.BackendVerification") as worker:
                    dialog = DependencyReviewDialog(plan, disposable_rehearsal=disposable,
                        install_action=lambda *_: self.fail("blocked install invoked"), install_authorized=lambda: True)
                    self.addCleanup(dialog.close)
                    worker.assert_not_called()
                self.assertIn(blocker, dialog.blockers.text())
                self.assertFalse(dialog.apply_button.isEnabled())
                dialog.show_backend_result(b"verified")
                self.assertFalse(dialog.apply_button.isEnabled())
                dialog.run_rehearsal()
                self.assertIsNone(dialog.install_worker)
                self.assertFalse(dialog.install_attempted)

    def test_real_verify_button_legacy_and_missing_backend(self):
        page=self.page(); before=self.state.read_bytes()
        with patch.object(page,'_fresh_review_rows',return_value=self.rows()), patch.object(hub,'verify',return_value={}):
            page.integrity_button.click(); self.wait(page)
            self.assertIn('Verified existing dependencies',page.integrity_status.text())
            self.assertIn('Historical record integrity (separate)',page.integrity_status.text())
            self.assertEqual(page.recognition_result['counts']['matching'],3)
            (self.injector/'UEVRBackend.dll').unlink()
            page.integrity_button.click(); self.wait(page)
            self.assertEqual(page.recognition_result['status'],'Review')
            self.assertIn('UEVRBackend.dll',page.integrity_details.toPlainText())
        self.assertEqual(self.state.read_bytes(),before)
        self.assertFalse((self.injector/'UEVRBackend.dll').exists())

    def test_ambiguous_rows_and_same_game_refresh_invalidate(self):
        page=self.page(); rows=self.rows(); rows[0]['ambiguous']=True
        self.assertEqual(recognition.archives_from_rows(self.recipe,rows),())
        with patch.object(page,'_fresh_review_rows',return_value=rows), patch.object(hub,'verify',return_value={}):
            page.integrity_button.click(); self.wait(page)
        self.assertEqual(page.recognition_result['status'],'Unknown')
        self.assertIn('Scan both verified',page.integrity_status.text())
        page.set_recipe(self.recipe)
        self.assertIsNone(page.recognition_result)
        self.assertIn('not checked',page.integrity_status.text())

    def test_rollback_controls_follow_selected_game(self):
        with patch.object(HubWindow, "check_updates"), patch.object(HubWindow, "scan_setup"), patch.object(HubUpdateController, "startup"):
            win = HubWindow()
        self.addCleanup(win.close)
        win.show()
        for game, label, profile_hidden in (
                ("fatekeeper", "Restore previous installation", True),
                ("hogwarts-legacy", "Uninstall mod", False),
                ("subnautica", "Uninstall mod", True),
                ("fatekeeper", "Restore previous installation", True)):
            with self.subTest(game=game):
                idx = next(i for i, r in enumerate(win.rows) if r["recipe"]["id"] == game)
                win.select_launcher_game(idx)
                win.game_details_tabs.setCurrentWidget(win.rollback_page)
                self.assertEqual(win.uninstall_btn.text(), label)
                self.assertTrue(win.uninstall_btn.isVisible())
                self.assertEqual(win.unprofile_btn.isHidden(), profile_hidden)
                self.assertEqual(win.unprofile_btn.text(), "Remove profile")

    def test_compatibility_sample_separate_and_cleared(self):
        with patch.object(HubWindow,'check_updates'), patch.object(HubWindow,'scan_setup'), patch.object(HubUpdateController,'startup'):
            win=HubWindow()
        self.addCleanup(win.close)
        idx=next(i for i,r in enumerate(win.rows) if r['recipe']['id']=='fatekeeper')
        win.select_launcher_game(idx)
        result=self.scan(); win.downloads.recognition_result=result
        win.refresh_compatibility()
        text=win.compat_details.toPlainText()
        self.assertIn('Last explicit pinned dependency verification',text)
        self.assertIn('Not a fresh rescan',text)
        self.assertIn('Latest local gameplay test',text)
        win.downloads.set_recipe(self.recipe)
        self.assertNotIn('Last explicit pinned dependency verification',win.compat_details.toPlainText())
