# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Blocked backup messages explain the reason without offering approval."""
import json
import unittest
from pathlib import Path
from unittest import mock
from tests import test_save_locations as qt_helpers
from tests.test_game_saves import SaveFixtures,HAS_QT
from vrhub.game_saves import BackupVerificationError


class BlockedMessageTests(SaveFixtures,unittest.TestCase):
    def test_distinct_record_failures_explain_why_restore_is_blocked(self):
        b,s,t=self.pair('fatekeeper')
        with mock.patch.object(b,'ensure_closed'):result=b.restore(b.preview(s,t))
        folder=Path(result['backup']);record_path=folder/'restore.json'
        original=record_path.read_text();record=json.loads(original)
        cases=[(None,'record is missing'),('broken','record cannot be read'),
               ('[]','unsupported format'),
               (json.dumps(dict(record,status='preparing')),'does not confirm'),
               (json.dumps(dict(record,game_id='valheim')),'different game'),
               (json.dumps(dict(record,target={'fingerprint':'x'})),'no valid verification hash')]
        for raw,reason in cases:
            with self.subTest(reason=reason):
                if raw is None:record_path.unlink()
                else:record_path.write_text(raw)
                with self.assertRaises(BackupVerificationError) as error:b.preview(folder/'target-before-savegame',t)
                self.assertIn(reason,str(error.exception));self.assertIn('no manual approval button',str(error.exception))
                record_path.write_text(original)
        self.assertEqual((t/'Slot0.sav').read_bytes(),b'save')


@unittest.skipUnless(HAS_QT,'Qt unavailable')
class BlockedMessageQtTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(qt_helpers.RememberedLocationsQtTests.setUpClass.__func__)
    dispose=qt_helpers.RememberedLocationsQtTests.dispose

    def test_invalid_backup_selection_explains_block_and_disables_actions(self):
        from vrhub.game_save_gui import GameSavesDialog
        b,s,t=self.pair('fatekeeper')
        with mock.patch.object(b,'ensure_closed'):result=b.restore(b.preview(s,t))
        folder=Path(result['backup']);(folder/'restore.json').unlink()
        d=GameSavesDialog(b.recipe,auto_scan=False,development_enabled=True);d.backend=b
        self.addCleanup(self.dispose,d)
        with mock.patch.object(b,'targets',return_value=[t]):d.scanned(b.discover(b.recipe))
        index=next(i for i,row in enumerate(d.report['rows']) if row.get('root')==str(folder/'target-before-savegame'))
        d.table.selectRow(index);d.selection_changed()
        self.assertEqual(d.table.item(index,5).text(),'Restore blocked — backup verification needed')
        self.assertEqual(d.source_heading.text(),'SELECTED SOURCE — RESTORE BLOCKED')
        self.assertIn('record is missing',d.details.toPlainText())
        self.assertIn('no manual approval button',d.details.toPlainText())
        self.assertFalse(d.restore_button.isEnabled());self.assertFalse(d.compare_button.isEnabled())
        self.assertIsNone(d.plan)
