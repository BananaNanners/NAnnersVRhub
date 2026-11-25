# SPDX-License-Identifier: GPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vrhub import fatekeeper_commit as transaction, hub, profile_safety
from vrhub.fatekeeper_install import PreparedInstall


class FatekeeperCommitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(
            tempfile.TemporaryDirectory(prefix="nanners-fk4-", dir="/tmp")))
        self.prefix, self.injector, self.profile, self.state = transaction._roots(self.root)
        self.backend = self.injector / "UEVRBackend.dll"
        self.config = self.profile / "config.txt"

    def prepare(self, repair):
        self.prefix.mkdir()
        records = {}
        if repair:
            self.injector.mkdir(parents=True)
            self.profile.mkdir(parents=True)
            self.backend.write_bytes(b"approved backend already installed")
            self.config.write_bytes(b"old configuration")
            (self.profile / "custom.ini").write_bytes(b"player customisation")
            records = {"fatekeeper:profile": {"backup": "legacy"}, "other": {"files": []}}
            self.state.write_bytes(json.dumps(records).encode() + b"  \n")
        writes = {str(self.config): b"new configuration"}
        if not repair:
            writes[str(self.backend)] = b"verified backend"
        return PreparedInstall(self.prefix, profile_safety._snapshot(self.injector),
                               profile_safety._snapshot(self.profile), records, writes)

    def test_fresh_install_and_explicit_rollback(self):
        transaction.commit(self.root, self.prepare(False))
        self.assertEqual(self.backend.read_bytes(), b"verified backend")
        self.assertIn("fatekeeper", hub._load_state(path=self.state))
        transaction.recover(self.root)
        transaction.recover(self.root)
        self.assertFalse(self.injector.exists())
        self.assertFalse(self.profile.exists())
        self.assertFalse(self.state.exists())

    def test_interrupted_repair_recovers_with_new_call(self):
        prepared = self.prepare(True)
        before = self.state.read_bytes()
        identity = self.backend.stat().st_ino
        transaction.commit(self.root, prepared, interrupt_after_files=True)
        self.assertEqual(self.config.read_bytes(), b"new configuration")
        self.assertEqual(self.state.read_bytes(), before)
        transaction.recover(self.root)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.backend.stat().st_ino, identity)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.assertEqual((self.profile / "custom.ini").read_bytes(), b"player customisation")

    def test_corrupt_backup_blocks_rollback_before_writes(self):
        transaction.commit(self.root, self.prepare(True))
        (self.root / "fk4-backup/0").write_bytes(b"wrong")
        state = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "rollback blocked"):
            transaction.recover(self.root)
        self.assertEqual(self.state.read_bytes(), state)
        self.assertEqual(self.config.read_bytes(), b"new configuration")

    def test_live_or_unrelated_prefix_refused(self):
        with self.assertRaisesRegex(RuntimeError, "Live Fatekeeper"):
            transaction.commit(self.root / "elsewhere", self.prepare(False))


    def test_production_entry_points_refuse_before_resolving_paths(self):
        with patch.object(hub, "_pfx", side_effect=AssertionError("touched live resolver")):
            with self.assertRaisesRegex(RuntimeError, "Explicit live Fatekeeper authorization"):
                transaction.install_reviewed(None)
            with self.assertRaisesRegex(RuntimeError, "Explicit live Fatekeeper authorization"):
                transaction.recover_live()

    def test_production_entry_points_use_resolved_disposable_paths(self):
        prepared = self.prepare(True)
        storage = self.root / "hub"
        storage.mkdir()
        state_path = storage / "state.json"
        self.state.rename(state_path)
        original = state_path.read_bytes()
        home = self.root / "fixture-home"
        (home / ".local/share").mkdir(parents=True)
        with (patch("pathlib.Path.home", return_value=home),
            patch.multiple(hub, _pfx=lambda *_: self.prefix, _uevr_dir=lambda *_: self.injector,
                            profile_dir=lambda *_: self.profile, state_file=lambda: state_path),
            patch.object(profile_safety, "_assert_game_stopped") as stopped,
            patch.object(transaction, "live_install_authorized", return_value=True), patch(
            "vrhub.fatekeeper_install.prepare_reviewed_install", return_value=prepared
        ) as preflight):
            self.assertEqual(transaction.install_reviewed("review", verified_backend=b"asset"),
                             [self.config])
            preflight.assert_called_once_with("review", None, verified_backend=b"asset")
            records = hub._load_state(path=state_path)
            self.assertNotIn(str(self.profile / "custom.ini"), records["fatekeeper:profile"]["files"])
            self.assertTrue((storage / "fatekeeper-recovery/fk4-journal.json").is_file())
            authority = home / ".local/share/nannersvrhub-transaction-authority"
            self.assertEqual(len(list(authority.glob("*.json"))), 1)
            hub.uninstall("fatekeeper:profile", profile_confirm=True)
            self.assertEqual(state_path.read_bytes(), original)
            self.assertEqual(self.config.read_bytes(), b"old configuration")
            stopped.assert_called_with("fatekeeper")

    def production_fixture(self, repair=True):
        prepared = self.prepare(repair)
        storage = self.root / "hub"
        storage.mkdir()
        state = storage / "state.json"
        if self.state.exists():
            self.state.rename(state)
        home = self.root / "fixture-home"
        (home / ".local/share").mkdir(parents=True)
        self.enterContext(patch("pathlib.Path.home", return_value=home))
        self.enterContext(patch.multiple(hub, _pfx=lambda *_: self.prefix,
            _uevr_dir=lambda *_: self.injector, profile_dir=lambda *_: self.profile,
            state_file=lambda: state))
        self.enterContext(patch.object(profile_safety, "_assert_game_stopped"))
        self.enterContext(patch.object(transaction, "live_install_authorized", return_value=True))
        self.enterContext(patch("vrhub.fatekeeper_install.prepare_reviewed_install", return_value=prepared))
        return state, storage / "fatekeeper-recovery", home / ".local/share/nannersvrhub-transaction-authority"

    def test_production_staging_retry_preserves_existing_install(self):
        state, journal, authority = self.production_fixture()
        original = state.read_bytes()
        write = transaction._write
        def interrupt(path, data, mode=0o600):
            write(path, data, mode)
            if path.name == "state-new":
                raise OSError("staging interruption")
        with patch.object(transaction, "_write", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "staging interruption"):
                transaction.install_reviewed("review")
        backup = journal / "fk4-backup/state-new"
        retained = backup.read_bytes()
        self.assertEqual(state.read_bytes(), original)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        transaction.install_reviewed("review")
        self.assertEqual(backup.read_bytes(), retained)
        transaction.recover_live()
        self.assertEqual(state.read_bytes(), original)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.assertEqual((self.profile / "custom.ini").read_bytes(), b"player customisation")

    def test_production_staging_retry_fresh(self):
        state, journal, authority = self.production_fixture(False)
        write = transaction._write
        def interrupt(path, data, mode=0o600):
            write(path, data, mode)
            if path.name == "state-new":
                raise OSError("staging interruption")
        with patch.object(transaction, "_write", side_effect=interrupt):
            with self.assertRaises(OSError):
                transaction.install_reviewed("review")
        self.assertFalse(state.exists())
        transaction.install_reviewed("review")
        transaction.recover_live()
        self.assertFalse(state.exists())
        self.assertFalse(self.injector.exists())
        self.assertFalse(self.profile.exists())

    def test_production_missing_authority_refuses_recovery(self):
        state, journal, authority = self.production_fixture()
        transaction.install_reviewed("review")
        next(authority.glob("*.json")).unlink()
        before = state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "provenance"):
            transaction.recover_live()
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), b"new configuration")

    def test_production_corrupt_authority_refuses_recovery(self):
        state, journal, authority = self.production_fixture()
        transaction.install_reviewed("review")
        next(authority.glob("*.json")).write_bytes(b"bad JSON")
        with self.assertRaisesRegex(RuntimeError, "provenance"):
            transaction.recover_live()
        self.assertEqual(self.config.read_bytes(), b"new configuration")

    def test_production_redirected_authority_refuses_recovery(self):
        state, journal, authority = self.production_fixture()
        transaction.install_reviewed("review")
        saved = authority.with_name("saved-authority")
        authority.rename(saved)
        authority.symlink_to(saved)
        with self.assertRaisesRegex(RuntimeError, "storage"):
            transaction.recover_live()
        self.assertEqual(self.config.read_bytes(), b"new configuration")

    def test_production_finalized_replay_refused(self):
        state, journal, authority = self.production_fixture()
        transaction.install_reviewed("review")
        path = journal / "fk4-journal.json"
        old = path.read_bytes()
        transaction.recover_live()
        path.write_bytes(old)
        with self.assertRaisesRegex(RuntimeError, "provenance"):
            transaction.recover_live()
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def test_production_foreign_staging_evidence_refused(self):
        state, journal, authority = self.production_fixture()
        journal.mkdir(mode=0o700)
        foreign = journal / "player-file"
        foreign.write_bytes(b"keep")
        with self.assertRaisesRegex(RuntimeError, "staging evidence"):
            transaction.install_reviewed("review")
        self.assertEqual(foreign.read_bytes(), b"keep")
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def production_child_fixture(self):
        # A disk-backed disposable HOME, with no real Steam tree or Hub state.
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(
            prefix="nanners-e8-process-", dir=Path.home())))
        self.prefix = self.root / "pfx"
        self.injector = self.prefix / "drive_c/uevr"
        self.profile = self.prefix / "drive_c/users/steamuser/AppData" / hub.load_recipes()["fatekeeper"]["profile"]["dir"]
        self.backend = self.injector / "UEVRBackend.dll"
        self.config = self.profile / "config.txt"
        self.state = self.root / "hub/state.json"
        self.state.parent.mkdir()
        (self.root / "home/.local/share").mkdir(parents=True)
        self.prepare(True)
        return self.state.read_bytes()

    def production_child(self, action, interruption="none", expected=0):
        import subprocess
        import sys
        script = r"""
import os, sys, json
from pathlib import Path
from unittest.mock import patch
from vrhub import fatekeeper_commit as tx, fatekeeper_authorization as auth, hub, profile_safety
from vrhub.fatekeeper_install import PreparedInstall
root = Path(sys.argv[1])
action, interruption = sys.argv[2:]
assert root.name.startswith("nanners-e8-process-")
assert root.resolve() == root and root.stat().st_mode & 0o777 == 0o700
prefix = root / "pfx"
injector = prefix / "drive_c/uevr"
profile = prefix / "drive_c/users/steamuser/AppData" / hub.load_recipes()["fatekeeper"]["profile"]["dir"]
state = root / "hub/state.json"
journal = state.parent / "fatekeeper-recovery/fk4-journal.json"
backend = injector / "UEVRBackend.dll"
config = profile / "config.txt"
assert not tx.live_install_authorized()
original_write = tx._write
original_record = auth._record_journal
def write(path, data, mode=0o600):
    original_write(path, data, mode)
    if interruption == "staging" and path.name == "state-new":
        os._exit(73)
    if interruption == "payload" and path == config:
        os._exit(73)
    if interruption == "rollback-payload" and path == config and data == b"old configuration":
        os._exit(73)
    if path == journal and interruption == json.loads(data)["phase"] + "-published":
        os._exit(73)
def record(scope, stage, previous, digest):
    original_record(scope, stage, previous, digest)
    if stage == "before" and interruption == "initial-intent" and previous is None:
        os._exit(73)
    if stage == "before" and interruption == "terminal-intent":
        raw, _ = tx._read(journal)
        if raw is not None:
            parsed = json.loads(raw)
            if tx._digest(json.dumps(dict(parsed, phase="rolled-back")).encode()) == digest:
                os._exit(73)
def prepare(*args, **kwargs):
    return PreparedInstall(prefix, profile_safety._snapshot(injector),
        profile_safety._snapshot(profile), hub._load_state(path=state),
        {str(config): b"new configuration", str(backend): b"new backend"})
with (patch("pathlib.Path.home", return_value=root / "home"),
      patch.multiple(hub, _pfx=lambda *_: prefix, _uevr_dir=lambda *_: injector,
          profile_dir=lambda *_: profile, state_file=lambda: state),
      patch.object(profile_safety, "_assert_game_stopped"),
      patch.object(tx, "live_install_authorized", return_value=True),
      patch("vrhub.fatekeeper_install.prepare_reviewed_install", side_effect=prepare),
      patch.object(tx, "_write", side_effect=write),
      patch.object(auth, "_record_journal", side_effect=record)):
    if action == "install":
        tx.install_reviewed("disposable review")
    else:
        try:
            tx.recover_live()
        except RuntimeError as exc:
            if action != "reject-terminal" or "Pending terminal" not in str(exc):
                raise
        else:
            assert action != "reject-terminal", "terminal replay was accepted"
assert not tx.live_install_authorized()
"""
        result = subprocess.run([sys.executable, "-B", "-c", script,
            str(self.root), action, interruption], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def assert_production_child_restored(self, original):
        self.assertEqual(self.state.read_bytes(), original)
        self.assertEqual(self.backend.read_bytes(), b"approved backend already installed")
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.assertEqual((self.profile / "custom.ini").read_bytes(), b"player customisation")
        journal = self.state.parent / "fatekeeper-recovery/fk4-journal.json"
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "rolled-back")

    def test_production_child_completed_install_recovery(self):
        original = self.production_child_fixture()
        self.production_child("install")
        self.assertEqual(self.backend.read_bytes(), b"new backend")
        self.production_child("recover")
        self.assert_production_child_restored(original)

    def test_production_child_interrupted_install_recovery(self):
        original = self.production_child_fixture()
        self.production_child("install", "payload", 73)
        self.assertEqual(self.config.read_bytes(), b"new configuration")
        self.assertEqual(self.state.read_bytes(), original)
        self.production_child("recover")
        self.assert_production_child_restored(original)

    def test_production_child_interrupted_rollback_resume(self):
        original = self.production_child_fixture()
        self.production_child("install")
        self.production_child("recover", "rollback-payload", 73)
        journal = self.state.parent / "fatekeeper-recovery/fk4-journal.json"
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "recovering")
        self.production_child("recover")
        self.assert_production_child_restored(original)

    def test_production_child_initial_intent_retry(self):
        original = self.production_child_fixture()
        self.production_child("install", "initial-intent", 73)
        backup = self.state.parent / "fatekeeper-recovery/fk4-backup/state-new"
        retained = backup.read_bytes()
        self.assertEqual(self.state.read_bytes(), original)
        self.production_child("install")
        self.assertEqual(backup.read_bytes(), retained)
        self.production_child("recover")
        self.assert_production_child_restored(original)

    def test_production_child_applying_publication_recovery(self):
        original = self.production_child_fixture()
        self.production_child("install", "applying-published", 73)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.production_child("recover")
        self.assert_production_child_restored(original)

    def test_production_child_terminal_intent_blocks_replay(self):
        original = self.production_child_fixture()
        self.production_child("install")
        self.production_child("recover", "terminal-intent", 73)
        self.assertEqual(self.state.read_bytes(), original)
        journal = self.state.parent / "fatekeeper-recovery/fk4-journal.json"
        before = journal.read_bytes()
        self.assertEqual(json.loads(before)["phase"], "recovering")
        self.production_child("reject-terminal")
        self.assertEqual(journal.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def test_repair_retains_prior_same_root_ownership_only(self):
        from dataclasses import replace
        prepared = self.prepare(True)
        records = {"fatekeeper": {"root": str(self.injector), "files": [str(self.backend), str(self.root / "foreign.dll")]},
                   "fatekeeper:profile": {"root": str(self.root / "foreign"), "files": [str(self.profile / "custom.ini")]}}
        self.state.write_text(json.dumps(records))
        original = self.state.read_bytes()
        transaction.commit(self.root, replace(prepared, state=records))
        current = hub._load_state(path=self.state)
        self.assertEqual(current["fatekeeper"]["files"], [str(self.backend)])
        self.assertEqual(current["fatekeeper:profile"]["files"], [str(self.config)])
        transaction.recover(self.root)
        self.assertEqual(self.state.read_bytes(), original)

    def test_guard_blocks_before_payload_and_defers_recovery_while_running(self):
        prepared = self.prepare(True)
        destination = transaction._fixture_destination(self.root)
        before = self.state.read_bytes()
        running = False
        original_write = transaction._write
        def guard():
            if running:
                raise RuntimeError("UEVR injector is running")
        def write(path, data, mode=0o600):
            nonlocal running
            original_write(path, data, mode)
            if path == self.config:
                running = True
        with patch.object(transaction, "_write", side_effect=write):
            with self.assertRaisesRegex(RuntimeError, "injector is running"):
                transaction._commit(destination, prepared, process_guard=guard)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), b"new configuration")
        journal = self.root / "fk4-journal.json"
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "applying")
        with self.assertRaisesRegex(RuntimeError, "injector is running"):
            transaction._recover(destination, process_guard=guard)
        self.assertEqual(self.config.read_bytes(), b"new configuration")
        running = False
        transaction._recover(destination, process_guard=guard)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.assertEqual(self.state.read_bytes(), before)

    def test_guard_rechecks_after_backup_before_payload(self):
        prepared = self.prepare(True)
        before = self.state.read_bytes()
        destination = transaction._fixture_destination(self.root)
        guard = unittest.mock.Mock(side_effect=[None, RuntimeError("game is running")])
        with self.assertRaisesRegex(RuntimeError, "game is running"):
            transaction._commit(destination, prepared, process_guard=guard)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.assertEqual(self.state.read_bytes(), before)
        self.assertFalse((self.root / "fk4-journal.json").exists())

    def next_repair(self):
        return PreparedInstall(self.prefix, profile_safety._snapshot(self.injector),
                               profile_safety._snapshot(self.profile), hub._load_state(path=self.state),
                               {str(self.backend): b"repaired backend"})

    def test_repeat_commit_retains_history_and_latest_rollback(self):
        transaction.commit(self.root, self.prepare(False))
        previous_state = self.state.read_bytes()
        previous_journal = (self.root / "fk4-journal.json").read_bytes()
        self.backend.write_bytes(b"damaged backend")
        (self.profile / "custom.ini").write_bytes(b"player customization")
        before = (profile_safety._snapshot(self.injector), profile_safety._snapshot(self.profile))
        transaction.commit(self.root, self.next_repair())
        self.assertEqual(self.backend.read_bytes(), b"repaired backend")
        history, = self.root.glob("history-*")
        self.assertEqual((history / "fk4-journal.json").read_bytes(), previous_journal)
        self.assertTrue((self.root / "fk4-backup").is_dir())
        active = json.loads((self.root / "fk4-journal.json").read_bytes())
        self.assertNotEqual(active["backup"], "fk4-backup")
        transaction.recover(self.root)
        transaction.recover(self.root)
        self.assertEqual(self.state.read_bytes(), previous_state)
        self.assertEqual((profile_safety._snapshot(self.injector), profile_safety._snapshot(self.profile)), before)
        self.assertEqual((history / "fk4-journal.json").read_bytes(), previous_journal)

    def test_repeat_interruption_blocks_retry_until_recovered(self):
        transaction.commit(self.root, self.prepare(True))
        old_state = self.state.read_bytes()
        old_backend = self.backend.read_bytes()
        old_backup = (self.root / "fk4-backup/0").read_bytes()
        transaction.commit(self.root, self.next_repair(), interrupt_after_files=True)
        with self.assertRaisesRegex(RuntimeError, "Recover the existing"):
            transaction.commit(self.root, self.next_repair())
        transaction.recover(self.root)
        self.assertEqual(self.backend.read_bytes(), old_backend)
        self.assertEqual(self.state.read_bytes(), old_state)
        history, = self.root.glob("history-*")
        self.assertEqual((history / "fk4-backup/0").read_bytes(), old_backup)
        transaction.commit(self.root, self.next_repair())
        self.assertEqual(self.backend.read_bytes(), b"repaired backend")

    def test_repeat_staging_failure_preserves_active_journal_and_state(self):
        transaction.commit(self.root, self.prepare(True))
        journal = self.root / "fk4-journal.json"
        original = journal.read_bytes()
        before = self.state.read_bytes()
        guard = unittest.mock.Mock(side_effect=[None, RuntimeError("game is running")])
        with self.assertRaisesRegex(RuntimeError, "game is running"):
            transaction._commit(transaction._fixture_destination(self.root), self.next_repair(), process_guard=guard)
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(self.state.read_bytes(), before)
        transaction.recover(self.root)
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def test_repeat_corrupt_prior_backup_blocks_new_transaction(self):
        transaction.commit(self.root, self.prepare(True))
        journal = self.root / "fk4-journal.json"
        original = journal.read_bytes()
        before = self.state.read_bytes()
        (self.root / "fk4-backup/0").write_bytes(b"corrupt")
        with self.assertRaisesRegex(RuntimeError, "Previous Fatekeeper backup verification failed"):
            transaction.commit(self.root, self.next_repair())
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.backend.read_bytes(), b"approved backend already installed")

    def test_recovery_rejects_malformed_journal_before_mutation(self):
        transaction.commit(self.root, self.prepare(True))
        journal = self.root / "fk4-journal.json"
        raw = journal.read_bytes()
        before = (self.state.read_bytes(), self.config.read_bytes(), self.backend.read_bytes())
        def duplicate(r): r["rows"].insert(0, dict(r["rows"][0]))
        def escape(r): r["rows"][0]["path"] = "../foreign"
        def digest(r): r["rows"][0]["old"] = "bad"
        def mode(r): r["rows"][0]["mode"] = True
        def directory(r): r["directories"].append("pfx")
        def missing_state(r): r["rows"].pop()
        def backup(r): r["backup"] = "../foreign"
        def legacy(r): r.pop("identity")
        for change in (duplicate, escape, digest, mode, directory, missing_state, backup, legacy):
            with self.subTest(change=change.__name__):
                record = json.loads(raw); change(record); journal.write_text(json.dumps(record))
                altered = journal.read_bytes()
                with self.assertRaises(RuntimeError): transaction.recover(self.root)
                self.assertEqual(journal.read_bytes(), altered)
                self.assertEqual((self.state.read_bytes(), self.config.read_bytes(), self.backend.read_bytes()), before)
        journal.write_bytes(raw)
        transaction.recover(self.root)
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def test_recovery_rejects_replaced_prefix_at_same_path(self):
        import shutil
        transaction.commit(self.root, self.prepare(True))
        journal = self.root / "fk4-journal.json"
        raw = journal.read_bytes(); before = self.state.read_bytes()
        displaced = self.root / "displaced-prefix"
        self.prefix.rename(displaced)
        shutil.copytree(displaced, self.prefix)
        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            transaction.recover(self.root)
        self.assertEqual(journal.read_bytes(), raw)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), b"new configuration")
        shutil.rmtree(self.prefix); displaced.rename(self.prefix)
        transaction.recover(self.root)
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def test_recovery_resumes_after_interruption(self):
        transaction.commit(self.root, self.prepare(True))
        journal = self.root / "fk4-journal.json"
        original_write = transaction._write
        def fail_once(path, data, mode=0o600):
            if path == self.config: raise OSError("simulated interruption")
            original_write(path, data, mode)
        with patch.object(transaction, "_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                transaction.recover(self.root)
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "recovering")
        transaction.recover(self.root)
        self.assertEqual(self.config.read_bytes(), b"old configuration")
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "rolled-back")

    def test_pending_noop_refused(self):
        transaction.commit(self.root, self.prepare(True), interrupt_after_files=True)
        dest = transaction._fixture_destination(self.root)
        no = PreparedInstall(self.prefix, profile_safety._snapshot(self.injector),
                             profile_safety._snapshot(self.profile), hub._load_state(path=self.state), {})
        with patch.object(transaction, "_live_destination", return_value=dest), patch(
                "vrhub.fatekeeper_install.prepare_reviewed_install", return_value=no):
            with self.assertRaisesRegex(RuntimeError, "Recover the existing"):
                transaction.install_reviewed(None)
        transaction.recover(self.root)

    def test_rollback_preserves_unrelated_state_changes_and_resume(self):
        transaction.commit(self.root, self.prepare(True))
        records = hub._load_state(path=self.state)
        records["other"]["new"] = "keep"
        records["new-game"] = {"files": ["new"]}
        hub._save_state(records, path=self.state)
        original_write = transaction._write
        def fail(path, data, mode=0o600):
            if path == self.config: raise OSError("interrupted")
            original_write(path, data, mode)
        with patch.object(transaction, "_write", side_effect=fail):
            with self.assertRaisesRegex(OSError, "interrupted"):
                transaction.recover(self.root)
        transaction.recover(self.root)
        restored = hub._load_state(path=self.state)
        self.assertEqual(restored, {"fatekeeper:profile":{"backup":"legacy"},
                         "other":{"files":[],"new":"keep"},"new-game":{"files":["new"]}})
        self.assertEqual(self.config.read_bytes(), b"old configuration")

    def test_rollback_refuses_conflicting_fatekeeper_record(self):
        transaction.commit(self.root, self.prepare(True))
        records = hub._load_state(path=self.state)
        records["fatekeeper"]["files"] = ["conflict"]
        hub._save_state(records, path=self.state)
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "changed ownership records"):
            transaction.recover(self.root)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), b"new configuration")

    def test_rollback_refuses_corrupted_incoming_state(self):
        transaction.commit(self.root, self.prepare(True))
        (self.root / "fk4-backup/state-new").write_bytes(b"corrupt")
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "incoming state evidence"):
            transaction.recover(self.root)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), b"new configuration")

    def test_pending_notice_read_only_and_uninstall_routing(self):
        storage = self.root / "hub"
        state = storage / "state.json"
        self.assertEqual(transaction.recovery_notice(state), "")
        self.assertFalse(storage.exists())
        journal = storage / "fatekeeper-recovery/fk4-journal.json"
        journal.parent.mkdir(parents=True)
        journal.write_text(json.dumps({"schema":2,"phase":"applying"}))
        self.assertIn("recovery pending", transaction.recovery_notice(state))
        with patch.object(hub,"state_file",return_value=state), patch.object(transaction,"recover_live") as recover:
            hub.uninstall("fatekeeper:profile",profile_confirm=True)
            recover.assert_called_once()
        journal.write_text("invalid")
        self.assertIn("manual review",transaction.recovery_notice(state))

    def test_retry_keeps_prior_recovery_artifacts(self):
        prepared = self.prepare(False)
        transaction.commit(self.root, prepared)
        transaction.recover(self.root)
        transaction.commit(self.root, prepared)
        history, = self.root.glob("history-*")
        self.assertTrue((history / "fk4-journal.json").is_file())
        self.assertTrue((history / "fk4-backup").is_dir())
