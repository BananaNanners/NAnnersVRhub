# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Window percentages are visible and independent of font/desktop scaling."""
import unittest
from unittest import mock
from tests import test_source_selection_ui as helpers
from tests.test_game_saves import SaveFixtures,HAS_QT

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class RecoveryWindowSizeTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(helpers.SourceSelectionUiTests.setUpClass.__func__)
    wait=helpers.SourceSelectionUiTests.wait
    dispose=helpers.SourceSelectionUiTests.dispose
    dialog=helpers.SourceSelectionUiTests.dialog
    select=helpers.SourceSelectionUiTests.select

    def flush(self):
        for _ in range(12):self.app.processEvents()

    def screen(self):
        from PySide6.QtCore import QRect
        screen=mock.Mock();screen.availableGeometry.return_value=QRect(0,0,1600,1200)
        return screen

    def test_presets_resize_and_report_both_actual_percentages_without_save_changes(self):
        d,b,source,target=self.dialog();controls=d.window_size_controls
        font=d.font().toString();before=b.snapshot(target)['fingerprint']
        with mock.patch.object(d,'screen',return_value=self.screen()):
            for percent in [70,80,90,70]:
                controls.selector.setCurrentIndex(controls.selector.findData(percent))
                self.flush();controls.update_readout()
                self.assertEqual(d.size().toTuple(),(16*percent,12*percent))
                self.assertEqual(controls.readout.text(),f'Actual: {percent}% wide × {percent}% high')
                self.assertEqual(controls.selector.currentData(),percent)
                self.assertIn('logical pixels',controls.readout.toolTip())
        self.assertEqual(d.font().toString(),font)
        self.assertEqual(b.snapshot(target)['fingerprint'],before)

    def test_manual_resize_is_custom_with_measured_size(self):
        d,b,source,target=self.dialog();c=d.window_size_controls
        with mock.patch.object(d,'screen',return_value=self.screen()):
            d.resize(1200,900);c.update_readout()
            self.assertEqual(c.selector.currentText(),'Custom')
            self.assertEqual(c.readout.text(),'Actual: 75% wide × 75% high')
            c.selector.setCurrentIndex(c.selector.findData(80));self.flush()
            self.assertEqual(d.size().toTuple(),(1280,960))
            self.assertEqual(c.selector.currentData(),80)

    def test_readout_and_close_stay_outside_scrolling_form(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from PySide6.QtCore import QPoint,QRect
        d,b,source,target=self.dialog();d.resize(1000,720);d.show();self.flush()
        c=d.window_size_controls
        self.assertFalse(d.recovery_body.isAncestorOf(c))
        self.assertTrue(d.rect().contains(QRect(c.mapTo(d,QPoint(0,0)),c.size())))
        close=next(box for box in d.findChildren(QDialogButtonBox) if box.parentWidget() is d).button(QDialogButtonBox.Close)
        self.assertTrue(d.rect().contains(QRect(close.mapTo(d,QPoint(0,0)),close.size())))
        text=c.readout.text()
        d.recovery_scroll.verticalScrollBar().setValue(d.recovery_scroll.verticalScrollBar().maximum());self.flush()
        self.assertEqual(c.readout.text(),text)
        self.assertTrue(c.isVisible());self.assertTrue(close.isVisible())

    def test_missing_screen_readout_and_pending_timer_close_are_safe(self):
        d,b,source,target=self.dialog();c=d.window_size_controls
        with mock.patch.object(d,'screen',return_value=None):
            c.update_readout();self.assertEqual(c.readout.text(),'Actual size unavailable')
            c.apply_preset(c.selector.findData(70))
        c._timer.start(0)
        self.doCleanups();self.flush()
