# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Side-by-side summaries display reviewed roles without changing restore guards."""
import unittest
from unittest import mock
from tests import test_source_selection_ui as helpers
from tests.test_game_saves import SaveFixtures,HAS_QT

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class SaveSidePanelTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(helpers.SourceSelectionUiTests.setUpClass.__func__)
    wait=helpers.SourceSelectionUiTests.wait
    dispose=helpers.SourceSelectionUiTests.dispose
    dialog=helpers.SourceSelectionUiTests.dialog
    select=helpers.SourceSelectionUiTests.select

    def test_distinct_full_summaries_and_horizontal_divider(self):
        from PySide6.QtCore import Qt
        d,b,source,target=self.dialog();before=b.snapshot(target)['fingerprint']
        self.select(d,source)
        self.assertIn(str(source),d.details.toPlainText())
        self.assertNotIn(str(target),d.details.toPlainText())
        self.assertIn(str(target),d.target_details.toPlainText())
        self.assertNotIn(str(source),d.target_details.toPlainText())
        self.assertIn('FILE COMPARISON',d.details.toPlainText())
        self.assertTrue(d.details.isReadOnly());self.assertTrue(d.target_details.isReadOnly())
        self.assertEqual(d.summary_splitter.orientation(),Qt.Horizontal)
        self.assertEqual(d.save_splitter.orientation(),Qt.Vertical)
        self.assertFalse(d.summary_splitter.childrenCollapsible())
        d.resize(1180,900);d.show();self.app.processEvents()
        self.assertLess(d.details.mapTo(d,d.details.rect().topRight()).x(),d.target_details.mapTo(d,d.target_details.rect().topLeft()).x())
        d.summary_splitter.setSizes([250,850]);self.app.processEvents()
        self.assertLess(d.details.width(),d.target_details.width())
        self.assertIn(str(source),d.details.toPlainText())
        self.assertEqual(b.snapshot(target)['fingerprint'],before)

    def test_current_row_and_rescan_clear_source_but_keep_target(self):
        d,b,source,target=self.dialog();self.select(d,source);self.select(d,target)
        self.assertIn('Choose a different save row',d.details.toPlainText())
        self.assertNotIn(str(source),d.details.toPlainText());self.assertIn(str(target),d.target_details.toPlainText())
        self.assertIsNone(d.plan)
        self.select(d,source)
        with mock.patch.object(b,'targets',return_value=[target]):d.scan();self.wait(d)
        self.assertEqual(d.source_path.text(),'');self.assertNotIn(str(source),d.details.toPlainText())
        self.assertIn(str(target),d.target_details.toPlainText());self.assertIsNone(d.plan)
        b.target=None
        with mock.patch.object(b,'targets',return_value=[]):d.scanned(b.discover(b.recipe))
        self.assertIn('No active target selected',d.target_details.toPlainText())
        self.assertNotIn(str(target),d.target_details.toPlainText())

    def test_invalid_source_and_target_errors_are_visible_and_restore_blocked(self):
        d,b,source,target=self.dialog();missing=self.home/'missing'
        with mock.patch.object(b,'targets',return_value=[target]):d.scanned(b.discover(b.recipe,[missing]))
        self.select(d,missing)
        self.assertIn('Restore blocked',d.details.toPlainText());self.assertIn(str(missing),d.details.toPlainText())
        self.assertIn('RESTORE BLOCKED',d.source_heading.text())
        self.assertIn(str(target),d.target_details.toPlainText());self.assertIsNone(d.plan)
        (target/'Slot0.sav').unlink()
        with mock.patch.object(b,'targets',return_value=[target]):d.scanned(b.discover(b.recipe,[source]))
        self.select(d,source)
        self.assertIn('Target blocked',d.target_details.toPlainText())
        self.assertIn(str(target),d.target_details.toPlainText())
        self.assertIn(str(source),d.details.toPlainText());self.assertIsNone(d.plan)
        self.assertFalse(d.restore_button.isEnabled())

    def test_version_conflict_remains_visible_beside_both_summaries(self):
        d,b,source,target=self.dialog()
        with mock.patch.object(b,'targets',return_value=[target]):report=b.discover(b.recipe,[source])
        for row in report['rows']:row['game_version']='one' if row['root']==str(source) else 'two'
        d.scanned(report);self.select(d,source)
        self.assertIn('Different game versions',d.details.toPlainText())
        self.assertIn('Game version: one',d.details.toPlainText())
        self.assertIn('Game version: two',d.target_details.toPlainText())
        self.assertIsNone(d.plan);self.assertFalse(d.restore_button.isEnabled())
