# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Local, per-game preferences never select a restore or bypass validation."""
import json
import time
import unittest
from unittest import mock
from pathlib import Path
from tests.test_game_saves import SaveFixtures, FIXTURES, HAS_QT, write
from vrhub import save_locations as prefs

class RememberedLocationsTests(SaveFixtures, unittest.TestCase):
    def test_all_nine_roundtrip_and_game_isolation_without_state_changes(self):
        for rid in FIXTURES:
            backend,source,target=self.pair(rid)
            before=backend.snapshot(target)['fingerprint']
            backend.remember_folder('sources',source);backend.remember_folder('targets',target)
            self.assertEqual(prefs.load(rid),{'sources':[str(source)],'targets':[str(target)]})
            fresh=self.backend(rid)
            with mock.patch.object(fresh,'targets',return_value=[]):report=fresh.discover(fresh.recipe)
            self.assertIsNone(report['target'])
            self.assertEqual(report['remembered_targets'],[str(target)])
            self.assertEqual(report['remembered_sources'],[str(source)])
            self.assertFalse(any(row['current'] for row in report['rows']))
            self.assertEqual(backend.snapshot(target)['fingerprint'],before)
        self.assertEqual(len(json.loads(prefs.preferences_file().read_text())['games']),9)
        self.assertFalse((self.home/'hub/state.json').exists())
        self.assertEqual(prefs.preferences_file().stat().st_mode & 0o777,0o600)

    def test_dedup_bound_and_forget_only_one_game(self):
        backend,source,target=self.pair('fatekeeper')
        other,other_source,other_target=self.pair('ready-or-not')
        other.remember_folder('targets',other_target)
        for i in range(10):
            folder=write(self.home/('source-'+str(i)),FIXTURES['fatekeeper']);backend.remember_folder('sources',folder)
        backend.remember_folder('sources',folder)
        self.assertEqual(len(prefs.load('fatekeeper')['sources']),8)
        backend.forget_folders()
        self.assertEqual(prefs.load('fatekeeper'),{'sources':[],'targets':[]})
        self.assertEqual(prefs.load('ready-or-not')['targets'],[str(other_target)])
        self.assertTrue(folder.is_dir());self.assertTrue(other_target.is_dir())

    def test_missing_changed_and_redirected_paths_stay_blocked(self):
        backend,source,target=self.pair('fatekeeper')
        backend.remember_folder('sources',source);backend.remember_folder('targets',target)
        (source/'Slot0.sav').unlink();source.rmdir();target.rename(target.with_name('moved'))
        target.symlink_to(target.with_name('moved'),target_is_directory=True)
        fresh=self.backend('fatekeeper')
        with mock.patch.object(fresh,'targets',return_value=[]):report=fresh.discover(fresh.recipe)
        rows={row['root']:row for row in report['rows']}
        self.assertFalse(rows[str(source)]['usable']);self.assertFalse(rows[str(target)]['usable'])
        self.assertIn('resolves elsewhere',rows[str(target)]['error'])
        self.assertIsNone(report['target'])

    def test_disabled_invalid_folder_and_backup_target_never_store(self):
        backend,source,target=self.pair('fatekeeper');backend.development_enabled=False
        with self.assertRaisesRegex(RuntimeError,'disabled'):backend.remember_folder('targets',target)
        with self.assertRaisesRegex(RuntimeError,'disabled'):backend.forget_folders()
        backend.development_enabled=True
        wrong=write(self.home/'wrong',{'settings.ini':b'no'})
        with self.assertRaises(RuntimeError):backend.remember_folder('sources',wrong)
        backup=write(self.home/'hub/backups/example',FIXTURES['fatekeeper'])
        with self.assertRaisesRegex(RuntimeError,'backup'):backend.remember_folder('targets',backup)
        self.assertFalse(prefs.preferences_file().exists())

    def test_corrupt_preferences_not_overwritten_or_used(self):
        backend,source,target=self.pair('fatekeeper');p=prefs.preferences_file();p.parent.mkdir()
        for raw in ['bad json',json.dumps({'schema':1,'games':{'fatekeeper':{'sources':['relative'], 'targets':[]}}})]:
            p.write_text(raw)
            with mock.patch.object(backend,'targets',return_value=[]):report=backend.discover(backend.recipe)
            self.assertEqual(report['remembered_sources'],[])
            self.assertTrue(any('need review' in note for note in report['notes']))
            with self.assertRaises(RuntimeError):backend.remember_folder('sources',source)
            with self.assertRaises(RuntimeError):backend.forget_folders()
            self.assertEqual(p.read_text(),raw)

    def test_linked_preferences_are_not_replaced(self):
        backend,source,target=self.pair('fatekeeper');p=prefs.preferences_file();p.parent.mkdir()
        other=self.home/'other.json';other.write_text('{"schema":1,"games":{}}');p.symlink_to(other)
        with self.assertRaises(RuntimeError):backend.remember_folder('sources',source)
        self.assertTrue(p.is_symlink());self.assertEqual(other.read_text(),'{"schema":1,"games":{}}')

@unittest.skipUnless(HAS_QT,'Qt unavailable')
class RememberedLocationsQtTests(SaveFixtures,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def wait(self,d):
        end=time.monotonic()+8
        while d.worker is not None and time.monotonic()<end:self.app.processEvents();time.sleep(.005)
        self.assertIsNone(d.worker)

    def dispose(self,d):
        from PySide6.QtCore import QCoreApplication,QEvent
        d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()

    def test_choose_reopen_explicit_target_and_forget(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend,source,target=self.pair('fatekeeper')
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True);d.backend=backend
        try:
            with mock.patch.object(backend,'targets',return_value=[]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=str(source)):
                d.choose();self.wait(d)
            with mock.patch.object(backend,'targets',return_value=[]),mock.patch('vrhub.game_save_gui.QFileDialog.getExistingDirectory',return_value=str(target)):
                d.choose_target();self.wait(d)
            self.assertEqual(prefs.load(backend.rid),{'sources':[str(source)],'targets':[str(target)]})
        finally:self.dispose(d)
        d=GameSavesDialog(backend.recipe,auto_scan=False,development_enabled=True)
        try:
            with mock.patch.object(d.backend,'targets',return_value=[]):d.scanned(d.backend.discover(backend.recipe))
            self.assertIsNone(d.backend.target);self.assertIsNone(d.plan)
            self.assertEqual(d.target_combo.currentIndex(),0)
            self.assertTrue(d.forget_locations_button.isEnabled())
            index=d.target_combo.findData(str(target));self.assertGreater(index,0)
            with mock.patch.object(d.backend,'targets',return_value=[]):d.target_combo.setCurrentIndex(index);self.wait(d)
            self.assertEqual(d.backend.target,str(target));self.assertTrue(d.backend.manual_target)
            with mock.patch.object(d,'confirm_forget_locations',return_value=False):d.forget_locations()
            self.assertTrue(prefs.load(backend.rid)['targets'])
            with mock.patch.object(d,'confirm_forget_locations',return_value=True),mock.patch.object(d.backend,'targets',return_value=[]):d.forget_locations();self.wait(d)
            self.assertIsNone(d.backend.target);self.assertIsNone(d.plan)
            self.assertFalse(d.forget_locations_button.isEnabled())
            self.assertEqual(prefs.load(backend.rid),{'sources':[],'targets':[]})
            self.assertTrue(source.is_dir());self.assertTrue(target.is_dir())
        finally:self.dispose(d)
