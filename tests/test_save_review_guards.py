# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression cases from dev19 review; disposable saves only."""
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock
from tests.test_game_saves import SaveFixtures, write, FIXTURES
from vrhub import doom_saves


class ReviewedLocationTests(SaveFixtures, unittest.TestCase):
    def test_source_and_target_symlink_redirects_rejected_with_identical_contents(self):
        for role in ('source', 'target'):
            with self.subTest(role=role):
                backend, source, target = self.pair('fatekeeper')
                plan = backend.preview(source, target)
                path = source if role == 'source' else target
                other = self.home / ('other-' + role)
                shutil.copytree(path, other)
                moved = path.with_name('moved-' + role)
                path.rename(moved); path.symlink_to(other, target_is_directory=True)
                with mock.patch.object(backend, 'ensure_closed'), self.assertRaisesRegex(RuntimeError, 'location changed'):
                    backend.restore(plan)
                self.assertEqual((target / 'Slot0.sav').read_bytes(), b'saveold')
                self.assertFalse((self.home / 'hub/backups').exists())
                path.unlink(); moved.rename(path); shutil.rmtree(other)

    def test_same_path_different_directory_rejected(self):
        backend, source, target = self.pair('fatekeeper')
        plan = backend.preview(source, target)
        moved = target.with_name('original');target.rename(moved);shutil.copytree(moved, target)
        with mock.patch.object(backend, 'ensure_closed'), self.assertRaisesRegex(RuntimeError, 'identity changed'):
            backend.restore(plan)
        self.assertEqual((target / 'Slot0.sav').read_bytes(), b'saveold')

    def test_redirect_during_preparation_rejected(self):
        backend, source, target = self.pair('fatekeeper')
        plan = backend.preview(source, target);original_guard=backend.ensure_closed
        other=target.with_name('other');shutil.copytree(target,other)
        calls=0
        def guard():
            nonlocal calls
            calls+=1
            if calls==2:
                target.rename(target.with_name('retained'));target.symlink_to(other,target_is_directory=True)
        with mock.patch.object(backend,'ensure_closed',side_effect=guard),self.assertRaisesRegex(RuntimeError,'location changed'):
            backend.restore(plan)
        self.assertEqual((other/'Slot0.sav').read_bytes(),b'saveold')

    def test_all_adapters_record_directory_identity(self):
        for rid in FIXTURES:
            b,s,t=self.pair(rid)
            self.assertEqual(b.snapshot(t)['directory_identity'],doom_saves.directory_identity(t))


class RecoveryIntegrityTests(SaveFixtures, unittest.TestCase):
    def restore_pair(self, rid='fatekeeper'):
        backend, source, target=self.pair(rid)
        with mock.patch.object(backend,'ensure_closed'):
            result=backend.restore(backend.preview(source,target))
        return backend,source,target,Path(result['backup'])

    def test_changed_recovery_payload_blocked_as_ordinary_source_all_games(self):
        for rid in FIXTURES:
            with self.subTest(rid=rid):
                b,s,t,backup=self.restore_pair(rid)
                original=backup/'target-before-savegame'
                filename=next(iter(FIXTURES[rid]))
                p=original/filename;p.write_bytes(p.read_bytes()+b'corrupted')
                with self.assertRaisesRegex(RuntimeError,'Backup verification needed'):
                    b.preview(original,t)

    def test_valid_recovery_copy_remains_restorable(self):
        b,s,t,backup=self.restore_pair()
        plan=b.preview(backup/'target-before-savegame',t)
        with mock.patch.object(b,'ensure_closed'):b.restore(plan)
        self.assertEqual((t/'Slot0.sav').read_bytes(),b'saveold')

    def test_missing_malformed_incomplete_and_wrong_game_records_block(self):
        b,s,t,backup=self.restore_pair();p=backup/'restore.json';raw=p.read_text();record=json.loads(raw)
        for value in (None,'[]','broken',json.dumps(dict(record,status='preparing')),json.dumps(dict(record,game_id='valheim'))):
            with self.subTest(value=value):
                if value is None:p.unlink()
                else:p.write_text(value)
                with self.assertRaisesRegex(RuntimeError,'Backup verification needed'):
                    b.preview(backup/'target-before-savegame',t)
                p.write_text(raw)

    def test_changed_source_side_recovery_copy_blocked(self):
        b,s,t,backup=self.restore_pair()
        copy=backup/'source-savegame';(copy/'Slot0.sav').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'Backup verification needed'):
            b.preview(copy,t)
