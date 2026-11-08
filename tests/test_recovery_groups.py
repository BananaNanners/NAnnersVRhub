# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Recovery labels and visual groups must preserve source/target selection."""
import json
from pathlib import Path
import unittest
from unittest import mock
from tests.test_save_undo import UndoFixtures
from tests.test_game_saves import HAS_QT


class RecoveryGroupTests(UndoFixtures, unittest.TestCase):
    def test_restore_undo_groups_preserve_original_paths(self):
        backend, source, target, original, result = self.restored_pair()
        with mock.patch.object(backend, 'ensure_closed'):
            undone = backend.undo(backend.undo_preview())
        with mock.patch.object(backend, 'targets', return_value=[target]):
            report = backend.discover(backend.recipe)
        rows = [r for r in report['rows'] if r.get('recovery_group')]
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['recovery_operation'] for r in rows}, {'Restore', 'Undo'})
        self.assertEqual({r['label'] for r in rows}, {'Selected source', 'Original saves before restore', 'Saves preserved before undo'})
        for row in rows:
            self.assertTrue(row['usable'])
            self.assertTrue(row['recovery_created_at'])
            self.assertEqual(Path(row['root']).parent, Path(row['recovery_group']))
        self.assertEqual(backend.snapshot(target)['fingerprint'], original)

    def test_bad_or_missing_record_uses_honest_undated_group(self):
        backend, source, target, original, result = self.restored_pair()
        path=Path(result['backup'])/'restore.json'
        for value in ['bad json', '{}', '{"schema_version":1,"created_at":"not a date"}']:
            path.write_text(value)
            with mock.patch.object(backend,'targets',return_value=[target]):report=backend.discover(backend.recipe)
            backups=[r for r in report['rows'] if r.get('recovery_group')]
            self.assertEqual(len(backups),2)
            self.assertTrue(all(r['recovery_operation']=='Recovery backup' and r['recovery_created_at'] is None for r in backups))
            self.assertIsNone(report['undo_plan'])

    def test_legacy_doom_backup_names_are_grouped_without_fabricated_dates(self):
        from tests.test_game_saves import FIXTURES, write
        backend, source, target = self.pair('doom-2016-gog')
        folder = self.home / 'hub/backups/doom-save-restore-old'
        for name in ['experimental-savegame', 'heroic-before-savegame']:
            write(folder / name, FIXTURES['doom-2016-gog'])
        with mock.patch.object(backend, 'targets', return_value=[target]):report=backend.discover(backend.recipe)
        rows=[r for r in report['rows'] if r.get('recovery_group')]
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['label'] for r in rows}, {'Selected source', 'Original target saves'})
        self.assertTrue(all(r['recovery_operation']=='Recovery backup' and r['recovery_created_at'] is None for r in rows))

    def test_legacy_record_is_read_without_rewriting_history(self):
        backend, source, target, original, result=self.restored_pair()
        path=Path(result['backup'])/'restore.json';record=json.loads(path.read_text())
        record.pop('operation');record.pop('game_id');path.write_text(json.dumps(record)); before=path.read_bytes()
        with mock.patch.object(backend,'targets',return_value=[target]):report=backend.discover(backend.recipe)
        self.assertEqual(path.read_bytes(),before)
        self.assertTrue(all(r['recovery_operation']=='Restore' for r in report['rows'] if r.get('recovery_group')))


@unittest.skipUnless(HAS_QT, 'Qt unavailable')
class RecoveryGroupQtTests(UndoFixtures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_group_headers_mapping_rescan_and_details(self):
        from PySide6.QtCore import Qt,QCoreApplication,QEvent
        from vrhub.game_save_gui import GameSavesDialog
        backend,source,target,original,result=self.restored_pair()
        with mock.patch.object(backend,'ensure_closed'):backend.undo(backend.undo_preview())
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True);d.backend=backend
        try:
            with mock.patch.object(backend,'targets',return_value=[target]):report=backend.discover(backend.recipe)
            for repeat in range(2):
                d.scanned(report)
                headers=[i for i,r in enumerate(d.report['rows']) if r.get('group_header')]
                self.assertEqual(len(headers),3)
                self.assertEqual(d.table.rowCount(),8)
                self.assertEqual(d.report['rows'][1]['root'],str(target))
                self.assertIn('1 save locations and 2 recovery backup sets (4 saved copies)',d.status.text())
                for i in headers:
                    self.assertFalse(d.table.item(i,0).flags() & Qt.ItemIsSelectable)
                    self.assertEqual(d.table.columnSpan(i,0),6)
                    d.table.setCurrentCell(i,0);d.selection_changed();self.assertIsNone(d.plan)
                selected = False
                for i,row in enumerate(d.report['rows']):
                    if row.get('recovery_operation')=='Undo' and row['label']=='Saves preserved before undo':
                        selected = True
                        d.table.selectRow(i);d.selection_changed()
                        self.assertEqual(d.plan['source']['root'],row['root'])
                        self.assertEqual(d.plan['target']['root'],str(target))
                        self.assertIn(row['root'],d.details.toPlainText())
                        self.assertEqual(d.table.item(i,0).text(),row['label'])
                        self.assertIn(row['root'],d.table.item(i,0).toolTip())
                self.assertTrue(selected)
            d.scanned(dict(report,rows=[r for r in report['rows'] if not r.get('recovery_group')]))
            self.assertEqual(d.table.rowCount(),1)
            self.assertEqual(d.table.columnSpan(0,0),1)
        finally:
            d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
