# SPDX-License-Identifier: GPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path

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
