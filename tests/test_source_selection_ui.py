# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Selecting, browsing and remembering source rows are separate explicit actions."""
import unittest
from unittest import mock
from pathlib import Path
from tests import test_save_locations as helpers
from tests.test_game_saves import SaveFixtures,HAS_QT
from vrhub import save_locations

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class SourceSelectionUiTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(helpers.RememberedLocationsQtTests.setUpClass.__func__)
    wait=helpers.RememberedLocationsQtTests.wait
    dispose=helpers.RememberedLocationsQtTests.dispose

    def dialog(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend,source,target=self.pair('fatekeeper')
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True);d.backend=backend
        self.addCleanup(self.dispose,d)
        with mock.patch.object(backend,'targets',return_value=[target]):d.scanned(backend.discover(backend.recipe,[source]))
        return d,backend,source,target

    def select(self,d,path):
        index=next(i for i,row in enumerate(d.report['rows']) if row.get('root')==str(path))
        d.table.selectRow(index);d.selection_changed()
        return index

    def test_selection_labels_browser_start_and_cancel_need_no_pasted_path(self):
        from PySide6.QtWidgets import QPushButton
        d,b,source,target=self.dialog();before=b.snapshot(target)['fingerprint']
        index=self.select(d,source)
        self.assertEqual(d.source_path.text(),str(source));self.assertTrue(d.source_path.isReadOnly())
        self.assertEqual(d.table.item(index,5).text(),'Selected source')
        self.assertNotIn('No source selected',d.status.text())
        self.assertTrue(d.remember_source_button.isEnabled())
        self.assertEqual(d.choose_button.text(),'Browse for another source folder')
        self.assertEqual(d.target_choose.text(),'Choose active target folder')
        self.assertFalse(any(w.text().endswith(('…','...')) for w in d.findChildren(QPushButton)))
        with mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value='') as pick:
            d.choose()
        self.assertEqual(pick.call_args.args[2],str(source))
        self.assertIsNone(d.worker);self.assertEqual(d.plan['source']['root'],str(source))
        self.assertFalse(save_locations.preferences_file().exists())
        self.assertEqual(b.snapshot(target)['fingerprint'],before)

    def test_remember_selected_source_keeps_selection_without_browsing(self):
        from vrhub.game_save_gui import GameSavesDialog
        d,b,source,target=self.dialog();self.select(d,source)
        before=b.snapshot(target)['fingerprint']
        with mock.patch.object(b,'targets',return_value=[target]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory') as pick:
            d.remember_source_button.click();self.wait(d)
            pick.assert_not_called()
        self.assertEqual(d.plan['source']['root'],str(source))
        self.assertEqual(d.source_path.text(),str(source))
        self.assertEqual(d.remember_source_button.text(),'Source remembered')
        self.assertFalse(d.remember_source_button.isEnabled())
        self.assertEqual(save_locations.load(b.rid)['sources'],[str(source)])
        self.assertEqual(b.snapshot(target)['fingerprint'],before)
        fresh=GameSavesDialog(b.recipe,auto_scan=False,development_enabled=True);self.addCleanup(self.dispose,fresh)
        with mock.patch.object(fresh.backend,'targets',return_value=[target]):fresh.scanned(fresh.backend.discover(b.recipe))
        self.assertEqual(fresh.source_path.text(),'');self.assertIsNone(fresh.plan)

    def test_current_header_invalid_and_matching_rows_do_not_bypass_restore_guards(self):
        d,b,source,target=self.dialog()
        self.select(d,target)
        self.assertEqual(d.source_path.text(),'');self.assertFalse(d.remember_source_button.isEnabled())
        (source/'Slot0.sav').write_bytes((target/'Slot0.sav').read_bytes())
        missing=self.home/'missing'
        with mock.patch.object(b,'targets',return_value=[target]):d.scanned(b.discover(b.recipe,[source,missing]))
        self.select(d,source)
        self.assertIsNone(d.plan);self.assertFalse(d.restore_button.isEnabled())
        self.assertTrue(d.remember_source_button.isEnabled())
        self.select(d,missing)
        self.assertEqual(d.source_title.text(),'Folder blocked:')
        self.assertFalse(d.remember_source_button.isEnabled());self.assertIsNone(d.plan)
        # No current row and no source selection falls back to the home directory.
        d.table.clearSelection()
        with mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value='') as pick:d.choose()
        self.assertEqual(pick.call_args.args[2],str(self.home))

    def test_browsed_source_is_explicitly_selected_after_revalidation(self):
        d,b,source,target=self.dialog()
        with mock.patch.object(b,'targets',return_value=[target]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=str(source)):
            d.choose();self.wait(d)
        self.assertEqual(d.source_path.text(),str(source))
        self.assertEqual(d.plan['source']['root'],str(source))
        # Ordinary rescans clear selection rather than silently restoring it.
        with mock.patch.object(b,'targets',return_value=[target]):d.scan();self.wait(d)
        self.assertEqual(d.source_path.text(),'');self.assertIsNone(d.plan)
