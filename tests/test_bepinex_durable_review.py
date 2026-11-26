# SPDX-License-Identifier: GPL-3.0-only
"""Independent-process interruption tests, exclusively synthetic fixtures."""
import subprocess
import sys
import unittest
from vrhub import bepinex_transaction_review as adapter, offline_transaction as tx
from tests.test_bepinex_transaction_review import snapshot

CHILD = """
import os, sys
from pathlib import Path
from vrhub import offline_transaction as tx
f = tx.Fixture(Path(sys.argv[1]), sys.argv[2])
try:
    if sys.argv[3] == 'apply':
        tx.execute(f, tx.build_plan(f), fault=sys.argv[4])
    else:
        tx.recover(f, fault=sys.argv[4])
except tx.SimulatedCrash:
    os._exit(37)
except tx.RecoveryBlocked:
    os._exit(38)
except tx.TransactionBlocked:
    os._exit(39)
os._exit(0)
"""


class Cases:
    def child(self, f, operation, fault, expected):
        result = subprocess.run(
            [sys.executable, "-B", "-c", CHILD, str(f.root), f.token,
             operation, fault], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))

    def test_process_exit_each_phase(self):
        for point in ("after_prepare_start", "after_backup_file:1",
                      "after_backup_file:7", "after_stage_file:1",
                      "after_stage_file:2", "after_backup",
                      "after_replace:1", "after_replace:2",
                      "after_all_files", "after_inventory"):
            with self.subTest(point=point), adapter.rehearsal(self.game) as (f, p, _):
                before, owners = snapshot(f), tx._inventory(f)
                self.child(f, "apply", point, 37)
                if point.startswith(("after_prepare", "after_backup", "after_stage")):
                    self.assertEqual(snapshot(f), before)
                self.child(f, "recover", "", 0)
                self.assertEqual(snapshot(f), before)
                self.assertEqual(tx._inventory(f), owners)
                self.child(f, "recover", "", 0)
                self.assertEqual(snapshot(f), before)
                self.assertFalse(tx.status(f)["authorized_live_install"])

    def test_recovery_process_exit_then_resume(self):
        for point in ("after_rollback:1", "after_rollback:2",
                      "after_directory_cleanup:1"):
            with self.subTest(point=point), adapter.rehearsal(self.game) as (f, p, _):
                before, owners = snapshot(f), tx._inventory(f)
                self.child(f, "apply", "after_all_files", 37)
                self.child(f, "recover", point, 37)
                self.child(f, "recover", "", 0)
                self.assertEqual(snapshot(f), before)
                self.assertEqual(tx._inventory(f), owners)

    def test_tampered_recovery_evidence(self):
        for section, name in (
            ("installed", "winhttp.dll"),
            ("installed", "BepInEx/config/BepInEx.cfg"),
            ("installed", "prefix/save.dat"),
            ("installed", "hub/state.json"),
            ("installed", "hub/backups/original/files/winhttp.dll"),
            ("transaction", "backup/winhttp.dll"),
            ("transaction", "journal.json"),
        ):
            with self.subTest(section=section, name=name), adapter.rehearsal(self.game) as (f, p, _):
                self.child(f, "apply", "after_all_files", 37)
                tx._write(f, section, name, b"unexpected external edit")
                before = snapshot(f)
                self.child(f, "recover", "", 39 if name == "journal.json" else 38)
                self.assertEqual(snapshot(f), before)

    def test_committed_transaction_requires_explicit_rollback(self):
        with adapter.rehearsal(self.game) as (f, p, _):
            before = snapshot(f)
            self.child(f, "apply", "", 0)
            committed = snapshot(f)
            self.child(f, "recover", "", 38)
            self.assertEqual(snapshot(f), committed)
            tx.rollback(f)
            self.assertEqual(snapshot(f), before)


class Subnautica(Cases, unittest.TestCase):
    game = "subnautica"


class Valheim(Cases, unittest.TestCase):
    game = "valheim"
