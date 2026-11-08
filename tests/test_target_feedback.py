# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Target validation never silently replaces a valid target on rejection."""
import unittest
from unittest import mock
from pathlib import Path
from tests import test_source_selection_ui as helpers
from tests.test_game_saves import SaveFixtures,FIXTURES,HAS_QT,write
from vrhub import save_locations

class TargetValidationTests(SaveFixtures,unittest.TestCase):
    def test_all_nine_readonly_validation(self):
        for rid in FIXTURES:
            b,source,target=self.pair(rid);before=b.snapshot(target)['fingerprint']
            self.assertEqual(b.validate_target_folder(target),str(target))
            self.assertEqual(b.target,str(target));self.assertEqual(b.snapshot(target)['fingerprint'],before)
        self.assertFalse(save_locations.preferences_file().exists())

    def test_reasons_and_guard_leave_target_and_preferences_unchanged(self):
        b,source,target=self.pair('fatekeeper');empty=self.home/'empty';empty.mkdir()
        bad=write(self.home/'wrong',{'settings.ini':b'no'})
        file=self.home/'file';file.write_bytes(b'file')
        backup=write(self.home/'hub/backups/originals',FIXTURES['fatekeeper'])
        cases=[(empty,'empty'),(bad,'configuration'),(self.home/'missing','no longer exists'),(file,'not a folder'),(backup,'recovery backup')]
        for path,reason in cases:
            with self.subTest(path=path),self.assertRaisesRegex(RuntimeError,reason):b.remember_folder('targets',path)
        with mock.patch.object(b,'snapshot',side_effect=PermissionError('no access')):
            with self.assertRaisesRegex(RuntimeError,'Access denied'):b.remember_folder('targets',target)
        self.assertEqual(b.target,str(target));self.assertFalse(save_locations.preferences_file().exists())

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class TargetFeedbackQtTests(SaveFixtures,unittest.TestCase):
    setUpClass=classmethod(helpers.SourceSelectionUiTests.setUpClass.__func__)
    wait=helpers.SourceSelectionUiTests.wait
    dispose=helpers.SourceSelectionUiTests.dispose
    dialog=helpers.SourceSelectionUiTests.dialog
    select=helpers.SourceSelectionUiTests.select

    def choose_target(self,d,b,path,target):
        with mock.patch.object(b,'targets',return_value=[target]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=str(path)) as pick:
            d.choose_target();self.wait(d)
        return pick

    def test_backup_rejection_persists_through_rescan_and_cancel_then_dismisses(self):
        d,b,source,target=self.dialog();backup=write(self.home/'hub/backups/set',FIXTURES['fatekeeper'])
        before=b.snapshot(target)['fingerprint'];pick=self.choose_target(d,b,backup,target)
        self.assertEqual(pick.call_args.args[2],str(target))
        self.assertEqual(b.target,str(target));self.assertEqual(d.target_combo.currentData(),str(target))
        text=d.target_feedback.toPlainText()
        self.assertIn('Target change blocked',text);self.assertIn('Use it as a source',text)
        self.assertIn(str(backup),text);self.assertFalse(d.target_feedback_box.isHidden())
        with mock.patch.object(b,'targets',return_value=[target]):d.scan();self.wait(d)
        self.assertEqual(d.target_feedback.toPlainText(),text)
        with mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=''):d.choose_target()
        self.assertEqual(d.target_feedback.toPlainText(),text)
        self.assertFalse(save_locations.preferences_file().exists())
        self.assertEqual(b.snapshot(target)['fingerprint'],before)
        d.dismiss_target_feedback.click();self.assertTrue(d.target_feedback_box.isHidden())

    def test_success_is_explicit_updates_current_state_and_does_not_move_saves(self):
        d,b,source,target=self.dialog();before=b.snapshot(source)['fingerprint']
        with mock.patch.object(b,'targets',return_value=[target]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=str(source)):
            d.choose_target()
            self.assertEqual(b.target,str(target))  # only the validated callback switches it
            self.wait(d)
        self.assertEqual(b.target,str(source));self.assertEqual(d.target_combo.currentData(),str(source))
        self.assertIn('Target changed. No saves were moved.',d.target_feedback.toPlainText())
        self.assertIn(str(source),d.target_feedback.toPlainText())
        row=next(i for i,r in enumerate(d.report['rows']) if r.get('root')==str(source))
        self.assertEqual(d.table.item(row,5).text(),'Current target')
        self.assertEqual(b.snapshot(source)['fingerprint'],before)
        self.assertTrue((target/'Slot0.sav').is_file())

    def test_empty_missing_wrong_format_and_denied_messages_remain_visible(self):
        d,b,source,target=self.dialog();empty=self.home/'empty';empty.mkdir()
        wrong=write(self.home/'wrong',{'unrelated.txt':b'not a save'})
        for path,reason in [(empty,'empty'),(self.home/'missing','no longer exists'),(wrong,'No recognized complete save set')]:
            self.choose_target(d,b,path,target)
            self.assertIn(reason,d.target_feedback.toPlainText());self.assertEqual(b.target,str(target))
            self.assertFalse(d.target_feedback_box.isHidden())
        with mock.patch.object(b,'snapshot',side_effect=PermissionError('denied')):
            self.choose_target(d,b,source,target)
        self.assertIn('Access denied',d.target_feedback.toPlainText());self.assertEqual(b.target,str(target))
        self.assertFalse(save_locations.preferences_file().exists())

    def test_invalid_dropdown_target_is_rejected_and_previous_choice_restored(self):
        d,b,source,target=self.dialog();empty=self.home/'empty';empty.mkdir()
        d.target_combo.addItem('Missing saves',str(empty));index=d.target_combo.count()-1
        with mock.patch.object(b,'targets',return_value=[target]):d.target_combo.setCurrentIndex(index);self.wait(d)
        self.assertEqual(b.target,str(target));self.assertEqual(d.target_combo.currentData(),str(target))
        self.assertIn('empty',d.target_feedback.toPlainText())
        self.assertFalse(save_locations.preferences_file().exists())
