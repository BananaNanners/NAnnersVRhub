# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Screen-relative recovery sizing and wrapped text reflow."""
import unittest
from unittest import mock
from tests import test_source_selection_ui as helpers
from tests.test_game_saves import SaveFixtures,HAS_QT

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class RecoveryScreenFitTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(helpers.SourceSelectionUiTests.setUpClass.__func__)
    wait=helpers.SourceSelectionUiTests.wait
    dispose=helpers.SourceSelectionUiTests.dispose
    dialog=helpers.SourceSelectionUiTests.dialog
    select=helpers.SourceSelectionUiTests.select

    def flush(self):
        for _ in range(12):self.app.processEvents()

    def test_initial_size_uses_screen_available_area(self):
        from vrhub.game_save_gui import GameSavesDialog
        from PySide6.QtCore import QRect
        b,source,target=self.pair('fatekeeper')
        screen=mock.Mock();screen.availableGeometry.return_value=QRect(0,0,1600,1200)
        with mock.patch.object(GameSavesDialog,'screen',return_value=screen):
            d=GameSavesDialog(b.recipe,auto_scan=False,development_enabled=True)
        self.addCleanup(self.dispose,d)
        self.assertEqual(d.size().toTuple(),(1280,960))

    def test_wrapped_status_fits_after_feedback_rescan_resize_and_large_text(self):
        from vrhub.theme import STYLESHEET
        from PySide6.QtCore import QPoint,QRect
        d,b,source,target=self.dialog()
        d.setStyleSheet(STYLESHEET.replace('10.5pt','14pt'));d.show()
        before=b.snapshot(target)['fingerprint']
        message=('Scan status and a long readable development recovery explanation. '*12)
        for width,height in [(1000,720),(1500,1000),(1000,720)]:
            d.resize(width,height);d.status.setText(message)
            d.show_target_feedback('Target change blocked. Target unchanged; no saves were moved.\nUse a backup as the source.')
            self.flush()
            from PySide6.QtWidgets import QLabel
            for label in d._wrapped_labels:
                if label.text():
                    probe=QLabel(d)
                    probe.setWordWrap(True);probe.setTextFormat(label.textFormat());probe.setFont(label.font())
                    probe.setText(label.text());probe.ensurePolished();probe.hide()
                    self.assertGreaterEqual(label.height(),probe.heightForWidth(label.width()))
                    probe.deleteLater()
            status_rect=QRect(d.status.mapTo(d.recovery_body,QPoint(0,0)),d.status.size())
            help_rect=QRect(d.source_help.mapTo(d.recovery_body,QPoint(0,0)),d.source_help.size())
            self.assertLess(status_rect.bottom(),help_rect.top())
            d.clear_target_feedback();self.flush()
        d.status.setText('Ready.');self.flush()
        self.assertLess(d.status.minimumHeight(),100)
        self.assertEqual(b.snapshot(target)['fingerprint'],before)

    def test_hidden_feedback_and_close_with_pending_reflow_are_safe(self):
        d,b,source,target=self.dialog();d.show();self.flush()
        d.status.setText('A new long status message. '*10)
        d.queue_label_fit()
        self.assertTrue(d._label_fit_timer.isActive())
        # Timer belongs to the dialog, so deletion also cancels pending work.
        from PySide6.QtCore import QCoreApplication,QEvent
        self.doCleanups()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.flush()
