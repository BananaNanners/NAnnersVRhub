# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Feedback transitions must not overlap controls in a short recovery window."""
import unittest
from unittest import mock
from tests import test_source_selection_ui as helpers
from tests.test_game_saves import SaveFixtures,HAS_QT,FIXTURES,write

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class RecoveryFeedbackLayoutTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(helpers.SourceSelectionUiTests.setUpClass.__func__)
    wait=helpers.SourceSelectionUiTests.wait
    dispose=helpers.SourceSelectionUiTests.dispose
    dialog=helpers.SourceSelectionUiTests.dialog
    select=helpers.SourceSelectionUiTests.select

    def rect(self,d,w):
        from PySide6.QtCore import QPoint,QRect
        return QRect(w.mapTo(d.recovery_body,QPoint(0,0)),w.size())

    def check_order(self,d):
        self.app.processEvents()
        table=self.rect(d,d.table);bar=self.rect(d,d.source_bar);panes=self.rect(d,d.summary_splitter)
        self.assertLess(table.bottom(),bar.top())
        self.assertLess(bar.bottom(),panes.top())
        self.assertLess(panes.bottom(),self.rect(d,d.compare_button).top())
        self.assertLess(self.rect(d,d.compare_button).bottom(),self.rect(d,d.restore_button).top())
        self.assertLess(self.rect(d,d.restore_button).bottom(),d.recovery_body.height())
        self.assertTrue(d.recovery_body.isAncestorOf(d.table))
        self.assertTrue(d.recovery_body.isAncestorOf(d.backup_current_button))
        self.assertTrue(d.recovery_body.isAncestorOf(d.target_feedback_box))

    def test_rejected_target_transition_rescan_dismiss_and_scroll_keep_controls_separate(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from vrhub.theme import STYLESHEET
        d,b,source,target=self.dialog();d.setStyleSheet(STYLESHEET)
        d.resize(1158,745);d.show();self.app.processEvents();before=d.size()
        self.check_order(d)
        backup=write(self.home/'hub/backups/recovery',FIXTURES['fatekeeper'])
        with mock.patch.object(b,'targets',return_value=[target]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=str(backup)):
            d.choose_target();self.wait(d)
        self.assertIn('Target change blocked',d.target_feedback.toPlainText())
        self.assertEqual(d.size(),before);self.assertEqual(b.target,str(target));self.check_order(d)
        self.assertGreater(d.recovery_scroll.verticalScrollBar().maximum(),0)
        d.recovery_scroll.ensureWidgetVisible(d.restore_button);self.app.processEvents()
        from PySide6.QtCore import QPoint,QRect
        visible=QRect(d.restore_button.mapTo(d.recovery_scroll.viewport(),QPoint(0,0)),d.restore_button.size())
        self.assertTrue(d.recovery_scroll.viewport().rect().contains(visible))
        close=next(box for box in d.findChildren(QDialogButtonBox) if box.parentWidget() is d).button(QDialogButtonBox.Close)
        self.assertTrue(close.isVisible());self.assertTrue(d.rect().contains(QRect(close.mapTo(d,QPoint(0,0)),close.size())))
        with mock.patch.object(b,'targets',return_value=[target]):d.scan();self.wait(d)
        self.check_order(d)
        maximum=d.recovery_scroll.verticalScrollBar().maximum()
        d.dismiss_target_feedback.click();self.app.processEvents();self.check_order(d)
        self.assertLess(d.recovery_scroll.verticalScrollBar().maximum(),maximum)

    def test_long_feedback_large_text_and_resize_do_not_overlap(self):
        from vrhub.theme import STYLESHEET
        d,b,source,target=self.dialog()
        before=b.snapshot(target)['fingerprint']
        d.setStyleSheet(STYLESHEET.replace('10.5pt','14pt'))
        d.resize(1000,720);d.show();self.app.processEvents()
        for size in [(1000,720),(1180,900),(1000,720)]:
            d.resize(*size)
            d.show_target_feedback('Target change blocked. Target unchanged; no saves were moved.\n'+('Long diagnostic details and chosen folder. '*100))
            for _ in range(3):self.app.processEvents()
            self.check_order(d)
            self.assertGreater(d.target_feedback.verticalScrollBar().maximum(),0)
            d.clear_target_feedback()
            for _ in range(3):self.app.processEvents()
            self.check_order(d)
        self.assertEqual(b.snapshot(target)['fingerprint'],before)
