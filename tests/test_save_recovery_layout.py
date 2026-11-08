# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Save rows remain visible and scrollable in a compact recovery window."""
import unittest
from unittest import mock
from tests.test_save_undo import UndoFixtures
from tests.test_game_saves import HAS_QT

@unittest.skipUnless(HAS_QT, 'Qt unavailable')
class SaveRecoveryLayoutTests(UndoFixtures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_compact_list_details_divider_and_scrolling(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        from vrhub.game_save_gui import GameSavesDialog
        from vrhub.theme import STYLESHEET
        backend,source,target,original,result=self.restored_pair()
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True);d.backend=backend
        try:
            d.setStyleSheet(STYLESHEET)
            with mock.patch.object(backend,'targets',return_value=[target]):report=backend.discover(backend.recipe)
            # Enough real rows to exceed the viewport, plus a long source path.
            row=dict(report['rows'][0]);report['rows'] += [dict(row,label='Experiment save',root='/tmp/experiment-'+str(i)+'/Saved Games/id Software/DOOM/base/savegame',current=False) for i in range(30)]
            d.scanned(report);d.resize(1158,745);d.show();self.app.processEvents()
            self.assertGreaterEqual(d.table.viewport().height(),3*d.table.verticalHeader().defaultSectionSize())
            self.assertGreater(d.table.height(),d.details.height())
            self.assertGreater(d.table.verticalScrollBar().maximum(),0)
            d.table.scrollToBottom();self.app.processEvents()
            last=d.table.rowCount()-1
            self.assertTrue(d.table.viewport().rect().intersects(d.table.visualItemRect(d.table.item(last,0))))
            self.assertFalse(d.save_splitter.childrenCollapsible())
            # Divider movement needs room beyond both panes' minimum sizes.
            d.resize(1158,900);self.app.processEvents()
            before=d.save_splitter.sizes();d.save_splitter.setSizes([before[0]-30,before[1]+30]);self.app.processEvents()
            self.assertGreater(d.save_splitter.sizes()[1],before[1])
            d.table.selectRow(last);d.selection_changed()
            self.assertIn(d.report['rows'][last]['root'],d.details.toPlainText())
            self.assertEqual(backend.snapshot(target)['fingerprint'],backend.snapshot(source)['fingerprint'])
        finally:
            d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
