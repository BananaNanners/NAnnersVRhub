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
