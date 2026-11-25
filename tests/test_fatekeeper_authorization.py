# SPDX-License-Identifier: GPL-3.0-only
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from vrhub import fatekeeper_authorization as auth, fatekeeper_commit, hub
from vrhub.profile_safety import ProfilePlan
from vrhub.uevr_dependency_review import DependencyReview


class ScopedAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='nanners-e6-test-', dir='/tmp')))
        self.steam = self.root / 'steam'
        self.prefix = self.steam / 'steamapps/compatdata/2186990/pfx'
        (self.prefix / 'drive_c').mkdir(parents=True)
        (self.steam / 'steamapps/common/Fatekeeper').mkdir(parents=True)
        (self.steam / 'steamapps/libraryfolders.vdf').write_text('"libraryfolders" {}')
        (self.steam / 'steamapps/appmanifest_2186990.acf').write_text('"AppState" { "appid" "2186990" "installdir" "Fatekeeper" }')
        self.state = self.root / 'hub/state.json'
        (self.state.parent / 'fatekeeper-recovery').mkdir(parents=True)
        self.authority = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='nanners-e6-authority-', dir='/tmp')))
        self.enterContext(patch.dict(os.environ, {'VRHUB_STATE': str(self.state), 'VRHUB_SCOPED_AUTHORITY_DIR': str(self.authority)}))
        self.scope = auth.resolve_scope(self.root)
        profile = ProfilePlan('fatekeeper', 'Fatekeeper', '/tmp/profile.zip', auth.PINS['profile'], str(self.scope.profile), ('config.txt',), 1, 1, 0, 0, 0, False, (), 'fingerprint')
        self.review = DependencyReview('Fatekeeper', '/tmp/uevr.zip', auth.PINS['uevr'], str(self.scope.injector), ('UEVRBackend.dll',), 1, 0, 0, 0, profile, ((), ()), (), file_decisions=(('Install', 'Injector', 'UEVRBackend.dll'),))

    def issue(self, **kw):
        return auth.authorize_install(self.root, self.review, confirmed=True, **kw)

    def consume(self, token, review=None, operation='install'):
        return auth.consume(token, self.root, operation, auth.review_digest(self.scope, review or self.review))

    def test_single_use(self):
        token = self.issue()
        self.assertEqual(self.consume(token), self.scope)
        with self.assertRaisesRegex(RuntimeError, 'consumed'):
            self.consume(token)
        self.assertFalse(fatekeeper_commit.live_install_authorized())

    def test_explicit_confirmation(self):
        with self.assertRaises(RuntimeError):
            auth.authorize_install(self.root, self.review)

    def test_expiry(self):
        with patch.object(auth, 'monotonic', return_value=100):
            token = self.issue(ttl=1)
        with patch.object(auth, 'monotonic', return_value=102):
            with self.assertRaisesRegex(RuntimeError, 'expired'):
                self.consume(token)

    def test_wrong_operation_burns_token(self):
        token = self.issue()
        with self.assertRaises(RuntimeError):
            self.consume(token, operation='recover')
        with self.assertRaises(RuntimeError):
            self.consume(token)

    def test_changed_review_burns_token(self):
        token = self.issue()
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            self.consume(token, replace(self.review, backend_status='different'))
        with self.assertRaises(RuntimeError):
            self.consume(token)

    def test_wrong_pins(self):
        with self.assertRaises(RuntimeError):
            auth.authorize_install(self.root, replace(self.review, injector_sha256='0'*64), confirmed=True)

    def test_wrong_state(self):
        with patch.dict(os.environ, {'VRHUB_STATE': str(self.root / 'foreign.json')}):
            with self.assertRaisesRegex(RuntimeError, 'resolver mismatch'):
                auth.resolve_scope(self.root)

    def test_non_private_root(self):
        self.root.chmod(0o755)
        with self.assertRaises(RuntimeError):
            auth.resolve_scope(self.root)

    def test_symlink_prefix(self):
        moved = self.prefix.with_name('old-pfx')
        self.prefix.rename(moved)
        self.prefix.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            auth.resolve_scope(self.root)

    def test_replaced_directory_identity(self):
        token = self.issue()
        drive = self.prefix / 'drive_c'
        drive.rename(self.prefix / 'old-drive')
        drive.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            self.consume(token)

    def test_existing_dependencies_refused(self):
        self.scope.injector.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'fresh'):
            self.issue()

    def test_non_test_root_refused(self):
        with self.assertRaises(RuntimeError):
            auth.resolve_scope(Path.home())

    def test_lifetime_bound(self):
        with self.assertRaises(RuntimeError):
            self.issue(ttl=301)

    def install(self, token, **kw):
        return fatekeeper_commit.install_reviewed(self.review, scoped_root=self.root,
                                                   scoped_token=token, **kw)

    def prepared(self):
        from vrhub import profile_safety
        from vrhub.fatekeeper_install import PreparedInstall
        return PreparedInstall(self.prefix, profile_safety._snapshot(self.scope.injector),
                               profile_safety._snapshot(self.scope.profile), {},
                               {str(self.scope.injector / 'UEVRBackend.dll'): b'test fixture'},
                               archive_pins=auth.PINS.copy())

    def test_production_entry_scoped_real_commit_synthetic_payload(self):
        token = self.issue()
        prepared = self.prepared()
        with (patch('vrhub.fatekeeper_install.prepare_reviewed_install', return_value=prepared) as preflight,
              patch('vrhub.profile_safety._assert_game_stopped') as stopped):
            self.assertEqual(self.install(token), [self.scope.injector / 'UEVRBackend.dll'])
            preflight.assert_called_once_with(self.review, [self.steam], verified_backend=None)
            self.assertGreater(stopped.call_count, 2)
            self.assertEqual((self.scope.injector / 'UEVRBackend.dll').read_bytes(), b'test fixture')
            self.assertTrue(self.state.is_file())
            self.assertTrue((self.scope.journal_dir / 'fk4-journal.json').is_file())
            with self.assertRaises(RuntimeError):
                self.install(token)
            with self.assertRaisesRegex(RuntimeError, 'Explicit live'):
                fatekeeper_commit.recover_live([self.steam])
            self.assertFalse(fatekeeper_commit.live_install_authorized())

    def test_scoped_wrong_roots_rejected_before_preflight(self):
        token = self.issue()
        with patch('vrhub.fatekeeper_install.prepare_reviewed_install') as preflight:
            with self.assertRaisesRegex(RuntimeError, 'root mismatch'):
                self.install(token, steam_roots=[self.root / 'foreign'])
            with self.assertRaises(RuntimeError):
                self.install(token)
            preflight.assert_not_called()

    def test_missing_permission_does_not_stage(self):
        with patch('vrhub.fatekeeper_install.prepare_reviewed_install') as preflight:
            with self.assertRaises(RuntimeError):
                self.install(None)
            with self.assertRaises(RuntimeError):
                self.install('unissued')
            preflight.assert_not_called()

    def test_stale_fresh_destination_rejected(self):
        token = self.issue()
        self.scope.injector.mkdir()
        with (patch('vrhub.profile_safety._assert_game_stopped'),
              patch('vrhub.fatekeeper_install.prepare_reviewed_install') as preflight):
            with self.assertRaisesRegex(RuntimeError, 'fresh'):
                self.install(token)
            preflight.assert_not_called()

    def test_destination_changes_during_staging(self):
        token = self.issue()
        prepared = self.prepared()
        def stage(*args, **kwargs):
            drive = self.prefix / 'drive_c'
            drive.rename(self.prefix / 'old-drive')
            drive.mkdir()
            return prepared
        with (patch('vrhub.profile_safety._assert_game_stopped'),
              patch('vrhub.fatekeeper_install.prepare_reviewed_install', side_effect=stage),
              patch.object(fatekeeper_commit, '_commit') as commit):
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                self.install(token)
            commit.assert_not_called()

    def test_running_game_blocks_before_staging(self):
        token = self.issue()
        with (patch('vrhub.profile_safety._assert_game_stopped', side_effect=RuntimeError('game running')),
              patch('vrhub.fatekeeper_install.prepare_reviewed_install') as preflight):
            with self.assertRaisesRegex(RuntimeError, 'game running'):
                self.install(token)
            preflight.assert_not_called()

    def test_game_symlink_refused(self):
        game = self.steam / 'steamapps/common/Fatekeeper'
        game.rmdir()
        game.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            auth.resolve_scope(self.root)

    def test_invalid_review_burns_permission(self):
        token = self.issue()
        with self.assertRaises(RuntimeError):
            fatekeeper_commit.install_reviewed(replace(self.review, injector_sha256='0'*64),
                                               scoped_root=self.root, scoped_token=token)
        with self.assertRaises(RuntimeError):
            self.install(token)

    def installed_fixture(self):
        token = self.issue()
        with (patch('vrhub.fatekeeper_install.prepare_reviewed_install', return_value=self.prepared()),
              patch('vrhub.profile_safety._assert_game_stopped')):
            self.install(token)
        return self.scope.journal_dir / 'fk4-journal.json'

    def recovery_token(self):
        return auth.authorize_recovery(self.root, expected_journal=auth.recovery_digest(self.scope), confirmed=True)

    def rollback(self, token, **kw):
        return fatekeeper_commit.recover_live(scoped_root=self.root, scoped_token=token, **kw)

    def test_scoped_recovery_restores_fresh_state_and_burns_token(self):
        journal = self.installed_fixture()
        token = self.recovery_token()
        with patch('vrhub.profile_safety._assert_game_stopped'):
            self.rollback(token)
            self.assertFalse(self.state.exists())
            self.assertFalse(self.scope.injector.exists())
            self.assertIn('rolled-back', journal.read_text())
            with self.assertRaises(RuntimeError):
                self.rollback(token)
        self.assertFalse(fatekeeper_commit.live_install_authorized())

    def test_unapproved_valid_journal_cannot_authorize_recovery(self):
        # A structurally valid journal from an unscoped writer must not
        # confer permission, even with matching payload and state evidence.
        destination = fatekeeper_commit.Destination(
            self.scope.root, self.scope.prefix, self.scope.injector,
            self.scope.profile, self.scope.state, self.scope.journal_dir)
        fatekeeper_commit._commit(destination, self.prepared())
        digest = auth.recovery_digest(self.scope)
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            auth.authorize_recovery(self.root, expected_journal=digest, confirmed=True)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertTrue(self.scope.injector.exists())

    def test_modified_journal_before_approval_is_rejected(self):
        journal = self.installed_fixture()
        journal.write_bytes(journal.read_bytes() + b'\n')
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            self.recovery_token()
        self.assertTrue(self.state.exists())

    def test_missing_provenance_fails_closed(self):
        self.installed_fixture()
        ledger = auth._ledger_path(self.scope)
        raw = ledger.read_bytes()
        ledger.unlink()
        with self.assertRaisesRegex(RuntimeError, 'manual review'):
            self.recovery_token()
        self.assertTrue(self.state.exists())
        ledger.write_bytes(raw)
        ledger.chmod(0o600)
        with patch('vrhub.profile_safety._assert_game_stopped'):
            self.rollback(self.recovery_token())
        self.assertFalse(self.state.exists())

    def test_other_process_cannot_reuse_permission(self):
        self.installed_fixture()
        token = self.recovery_token()
        with patch.object(auth.os, 'getpid', return_value=os.getpid()+1):
            with self.assertRaisesRegex(RuntimeError, 'consumed'):
                self.rollback(token)
        self.assertTrue(self.state.exists())

    def test_old_phase_replay_rejected(self):
        import json
        journal = self.installed_fixture()
        record = json.loads(journal.read_bytes())
        record['phase'] = 'applying'
        journal.write_bytes(json.dumps(record).encode())
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            self.recovery_token()
        self.assertTrue(self.state.exists())

    def test_recovering_phase_can_resume_after_interruption(self):
        journal = self.installed_fixture()
        original = fatekeeper_commit._journal
        interrupted = False
        def publish(*args, **kwargs):
            nonlocal interrupted
            result = original(*args, **kwargs)
            if args[1] == 'recovering':
                interrupted = True
            return result
        def guard(*args):
            if interrupted:
                raise RuntimeError('game running')
        with (patch.object(fatekeeper_commit, '_journal', side_effect=publish),
              patch('vrhub.profile_safety._assert_game_stopped', side_effect=guard)):
            with self.assertRaisesRegex(RuntimeError, 'game running'):
                self.rollback(self.recovery_token())
        self.assertIn('recovering', journal.read_text())
        with patch('vrhub.profile_safety._assert_game_stopped'):
            self.rollback(self.recovery_token())
        self.assertFalse(self.state.exists())
        self.assertFalse(self.scope.injector.exists())

    def child_transaction(self, action, interruption='none'):
        import subprocess
        import sys
        script = r"""
import os, sys
from pathlib import Path
from unittest.mock import patch
from vrhub import fatekeeper_authorization as auth, fatekeeper_commit as tx, profile_safety
from vrhub.fatekeeper_install import PreparedInstall
from vrhub.profile_safety import ProfilePlan
from vrhub.uevr_dependency_review import DependencyReview
root = Path(sys.argv[1])
action, interruption = sys.argv[2:]
scope = auth.resolve_scope(root)
assert not tx.live_install_authorized()
backend = scope.injector / 'UEVRBackend.dll'
profile_file = scope.profile / 'config.txt'
profile = ProfilePlan('fatekeeper', 'Fatekeeper', '/tmp/profile.zip', auth.PINS['profile'], str(scope.profile), ('config.txt',), 1, 1, 0, 0, 0, False, (), 'fingerprint')
review = DependencyReview('Fatekeeper', '/tmp/uevr.zip', auth.PINS['uevr'], str(scope.injector), ('UEVRBackend.dll',), 1, 0, 0, 0, profile, ((), ()), (), file_decisions=(('Install', 'Injector', 'UEVRBackend.dll'), ('Install', 'Profile', 'config.txt')))
prepared = PreparedInstall(scope.prefix, profile_safety._snapshot(scope.injector), profile_safety._snapshot(scope.profile), {}, {str(backend): b'test fixture', str(profile_file): b'profile fixture'}, archive_pins=auth.PINS.copy())
original_write = tx._write
original_record = auth._record_journal
def write(path, data, mode=0o600):
    original_write(path, data, mode)
    if interruption == 'payload' and path == backend:
        os._exit(73)
    if path == scope.journal_dir / 'fk4-journal.json':
        import json
        phase = json.loads(data)['phase']
        if interruption == phase + '-published':
            os._exit(73)
def record(scope_arg, stage, previous, digest):
    original_record(scope_arg, stage, previous, digest)
    if stage == 'before' and previous is not None and interruption == 'transition-intent':
        os._exit(73)
original_unlink = Path.unlink
def unlink(path, *args, **kwargs):
    result = original_unlink(path, *args, **kwargs)
    if interruption == 'rollback-payload' and path == profile_file:
        os._exit(73)
    return result
with (patch('vrhub.fatekeeper_install.prepare_reviewed_install', return_value=prepared),
      patch('vrhub.profile_safety._assert_game_stopped'),
      patch.object(tx, '_write', side_effect=write),
      patch.object(auth, '_record_journal', side_effect=record),
      patch.object(Path, 'unlink', unlink)):
    if action == 'install':
        token = auth.authorize_install(root, review, confirmed=True)
        tx.install_reviewed(review, scoped_root=root, scoped_token=token)
    else:
        token = auth.authorize_recovery(root, expected_journal=auth.recovery_digest(scope), confirmed=True)
        tx.recover_live(scoped_root=root, scoped_token=token)
assert not tx.live_install_authorized()
"""
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.root), action, interruption],
                                capture_output=True, text=True, timeout=30)
        expected = 0 if interruption == 'none' else 73
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def assert_child_recovered(self):
        self.child_transaction('recover')
        self.assertFalse(self.state.exists())
        self.assertFalse(self.scope.injector.exists())
        self.assertFalse(self.scope.profile.exists())
        self.assertIn('rolled-back', (self.scope.journal_dir / 'fk4-journal.json').read_text())
        with self.assertRaisesRegex(RuntimeError, 'not recoverable'):
            self.recovery_token()

    def test_independent_process_completed_install_recovery(self):
        self.child_transaction('install')
        self.assertTrue(self.state.exists())
        self.assert_child_recovered()

    def test_independent_process_crash_after_first_payload(self):
        self.child_transaction('install', 'payload')
        self.assertTrue(self.scope.injector.exists())
        self.assertFalse(self.state.exists())
        self.assert_child_recovered()

    def test_independent_process_crash_after_applying_publication(self):
        self.child_transaction('install', 'applying-published')
        self.assertFalse(self.scope.injector.exists())
        self.assert_child_recovered()

    def test_independent_process_crash_before_committed_publication(self):
        self.child_transaction('install', 'transition-intent')
        self.assertTrue(self.state.exists())
        self.assert_child_recovered()

    def test_independent_process_crash_after_committed_publication(self):
        self.child_transaction('install', 'committed-published')
        self.assertTrue(self.state.exists())
        self.assert_child_recovered()

    def test_independent_process_crash_after_recovering_publication(self):
        self.child_transaction('install')
        self.child_transaction('recover', 'recovering-published')
        self.assertTrue(self.state.exists())
        self.assert_child_recovered()

    def test_independent_process_crash_during_rollback(self):
        self.child_transaction('install')
        self.child_transaction('recover', 'rollback-payload')
        self.assertFalse(self.state.exists())
        self.assertTrue(self.scope.injector.exists())
        self.assert_child_recovered()

    def test_corrupt_authority_evidence_refused(self):
        self.installed_fixture()
        auth._ledger_path(self.scope).write_bytes(b'not json')
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            self.recovery_token()
        self.assertTrue(self.state.exists())

    def test_authority_symlink_refused(self):
        self.installed_fixture()
        ledger = auth._ledger_path(self.scope)
        saved = ledger.with_suffix('.saved')
        ledger.rename(saved)
        ledger.symlink_to(saved)
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            self.recovery_token()
        self.assertTrue(self.state.exists())

    def test_recovery_requires_explicit_confirmation_and_exact_digest(self):
        self.installed_fixture()
        with self.assertRaises(RuntimeError):
            auth.authorize_recovery(self.root, expected_journal=auth.recovery_digest(self.scope))
        with self.assertRaisesRegex(RuntimeError, 'review changed'):
            auth.authorize_recovery(self.root, expected_journal='0'*64, confirmed=True)

    def test_changed_journal_rejects_recovery_before_writes(self):
        journal = self.installed_fixture()
        token = self.recovery_token()
        journal.write_bytes(journal.read_bytes() + b'\n')
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            self.rollback(token)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertTrue(self.scope.injector.exists())

    def test_changed_journal_under_lock_rejected(self):
        journal = self.installed_fixture()
        token = self.recovery_token()
        from contextlib import contextmanager
        original = fatekeeper_commit._locked
        @contextmanager
        def changed(destination):
            with original(destination):
                journal.write_bytes(journal.read_bytes() + b'\n')
                yield
        with (patch.object(fatekeeper_commit, '_locked', changed),
              patch('vrhub.profile_safety._assert_game_stopped')):
            with self.assertRaisesRegex(RuntimeError, 'journal changed'):
                self.rollback(token)
        self.assertTrue(self.state.exists())

    def test_corrupt_incoming_evidence_rejected(self):
        self.installed_fixture()
        token = self.recovery_token()
        (self.scope.journal_dir / 'fk4-backup/state-new').write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError, 'evidence changed'):
            self.rollback(token)
        self.assertTrue(self.state.exists())

    def test_install_token_cannot_authorize_recovery(self):
        token = self.issue()
        with self.assertRaises(RuntimeError):
            self.rollback(token)
        with self.assertRaises(RuntimeError):
            self.install(token)

    def test_recovery_token_cannot_authorize_install(self):
        self.installed_fixture()
        token = self.recovery_token()
        with self.assertRaises(RuntimeError):
            self.install(token)
        with self.assertRaises(RuntimeError):
            self.rollback(token)

    def test_recovery_wrong_root_and_running_game_rejected(self):
        self.installed_fixture()
        with self.assertRaisesRegex(RuntimeError, 'root mismatch'):
            self.rollback(self.recovery_token(), steam_roots=[self.root / 'foreign'])
        with patch('vrhub.profile_safety._assert_game_stopped', side_effect=RuntimeError('game running')):
            with self.assertRaisesRegex(RuntimeError, 'game running'):
                self.rollback(self.recovery_token())
        self.assertTrue(self.state.exists())

    def test_automatic_failure_recovery(self):
        token = self.issue()
        original = fatekeeper_commit._write
        def fail_state(path, data, mode=0o600):
            if path == self.state:
                raise OSError('injected state write failure')
            return original(path, data, mode)
        with (patch('vrhub.fatekeeper_install.prepare_reviewed_install', return_value=self.prepared()),
              patch('vrhub.profile_safety._assert_game_stopped'),
              patch.object(fatekeeper_commit, '_write', side_effect=fail_state)):
            with self.assertRaisesRegex(OSError, 'injected state'):
                self.install(token)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.scope.injector.exists())
        self.assertIn('rolled-back', (self.scope.journal_dir / 'fk4-journal.json').read_text())
        with self.assertRaises(RuntimeError):
            self.install(token)

    def test_interrupted_install_explicit_recovery_after_game_stops(self):
        token = self.issue()
        original = fatekeeper_commit._write
        running = False
        def write(path, data, mode=0o600):
            nonlocal running
            original(path, data, mode)
            if path == self.scope.injector / 'UEVRBackend.dll':
                running = True
        def guard(*args):
            if running:
                raise RuntimeError('game running')
        with (patch('vrhub.fatekeeper_install.prepare_reviewed_install', return_value=self.prepared()),
              patch('vrhub.profile_safety._assert_game_stopped', side_effect=guard),
              patch.object(fatekeeper_commit, '_write', side_effect=write)):
            with self.assertRaisesRegex(RuntimeError, 'game running'):
                self.install(token)
        journal = self.scope.journal_dir / 'fk4-journal.json'
        self.assertIn('applying', journal.read_text())
        self.assertTrue(self.scope.injector.exists())
        self.assertFalse(self.state.exists())
        with patch('vrhub.profile_safety._assert_game_stopped', side_effect=guard):
            with self.assertRaisesRegex(RuntimeError, 'game running'):
                self.rollback(self.recovery_token())
            running = False
            self.rollback(self.recovery_token())
        self.assertFalse(self.scope.injector.exists())
        self.assertFalse(self.state.exists())
        self.assertIn('rolled-back', journal.read_text())

    def test_second_permission_cannot_reinstall(self):
        first, second = self.issue(), self.issue()
        with (patch('vrhub.fatekeeper_install.prepare_reviewed_install', return_value=self.prepared()) as stage,
              patch('vrhub.profile_safety._assert_game_stopped')):
            self.install(first)
            with self.assertRaisesRegex(RuntimeError, 'fresh'):
                self.install(second)
            stage.assert_called_once()

    def test_expired_recovery_permission(self):
        self.installed_fixture()
        with patch.object(auth, 'monotonic', return_value=100):
            token = auth.authorize_recovery(self.root, expected_journal=auth.recovery_digest(self.scope), confirmed=True, ttl=1)
        with patch.object(auth, 'monotonic', return_value=102):
            with self.assertRaisesRegex(RuntimeError, 'expired'):
                self.rollback(token)
        self.assertTrue(self.state.exists())

    def test_changed_payload_blocks_recovery(self):
        self.installed_fixture()
        token = self.recovery_token()
        backend = self.scope.injector / 'UEVRBackend.dll'
        backend.write_bytes(b'player changed file')
        with patch('vrhub.profile_safety._assert_game_stopped'):
            with self.assertRaisesRegex(RuntimeError, 'rollback blocked'):
                self.rollback(token)
        self.assertEqual(backend.read_bytes(), b'player changed file')
        self.assertTrue(self.state.exists())

    def test_external_library_refused(self):
        outside = self.root / 'other-library'
        (outside / 'steamapps').mkdir(parents=True)
        (self.steam / 'steamapps/libraryfolders.vdf').write_text('"libraryfolders" { "0" { "path" "' + str(outside) + '" } }')
        with self.assertRaisesRegex(RuntimeError, 'library or game mismatch'):
            auth.resolve_scope(self.root)

    def test_mountpoint_refused(self):
        from unittest.mock import mock_open
        line = '1 2 0:1 / ' + str(self.prefix) + ' rw - tmpfs tmpfs rw\n'
        with patch('vrhub.fatekeeper_authorization.open', mock_open(read_data=line), create=True):
            with self.assertRaisesRegex(RuntimeError, 'Mounted directory'):
                auth.resolve_scope(self.root)

    def test_recovery_does_not_authorize_repeat_install(self):
        self.installed_fixture()
        with patch('vrhub.profile_safety._assert_game_stopped'):
            self.rollback(self.recovery_token())
        with self.assertRaisesRegex(RuntimeError, 'fresh'):
            self.issue()
