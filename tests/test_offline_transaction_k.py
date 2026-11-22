# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-K transaction rehearsals: ALL writes occur in disposable /tmp fixtures."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import offline_transaction as tx


class FixtureTransactions(unittest.TestCase):
    def sample(self):
        return tx.fixture_sandbox(
            {"mods/main.dll":b"installed-v1", "mods/optional.dll":b"owned-unaffected",
             "config/settings.ini":b"user-preset-original"},
            {"mods/main.dll":b"installed-v2", "mods/new-helper.dll":b"new-mod-file"})

    def test_demo_reports_fixture_recovery_not_live_install(self):
        result=tx.demo()
        self.assertTrue(result["fixture_only"])
        self.assertFalse(result["real_game_files_modified"])
        self.assertFalse(result["authorized_live_install"])
        self.assertEqual(result["backups_checked"],2)
        self.assertEqual(result["interruption"],"applying")

    def test_commit_and_explicit_rollback_restores_owned_and_additions(self):
        with self.sample() as fixture:
            plan=tx.build_plan(fixture)
            self.assertFalse(plan.authorized_live_install)
            self.assertEqual([r["path"] for r in plan.rows],
                             ["mods/main.dll","mods/new-helper.dll"])
            self.assertEqual([r["action"] for r in plan.rows],["replace","add"])
            result=tx.execute(fixture,plan)
            self.assertEqual(result["status"],"Committed in disposable fixture")
            self.assertFalse(result["authorized_live_install"])
            self.assertEqual(tx.status(fixture)["phase"],"committed")
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),b"installed-v2")
            self.assertEqual(tx._read(fixture,"installed","mods/new-helper.dll"),b"new-mod-file")
            self.assertEqual(tx._read(fixture,"installed","mods/optional.dll"),b"owned-unaffected")
            self.assertEqual(tx._inventory(fixture),plan.after)
            restored=tx.rollback(fixture)
            self.assertEqual(restored["checked"],3)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),b"installed-v1")
            self.assertIsNone(tx._read(fixture,"installed","mods/new-helper.dll",optional=True))
            self.assertEqual(tx._read(fixture,"installed","config/settings.ini"),b"user-preset-original")
            self.assertEqual(tx._inventory(fixture),plan.before)
            self.assertEqual(tx.recover(fixture)["status"],"Already rolled back")
            self.assertEqual(tx.status(fixture)["phase"],"rolled_back")

    def test_all_interruption_points_recover_and_are_idempotent(self):
        for fault in ("after_backup","after_replace:1","after_replace:2",
                      "after_all_files","after_inventory"):
            with self.subTest(fault=fault):
                with self.sample() as fixture:
                    p=tx.build_plan(fixture)
                    with self.assertRaises(tx.SimulatedCrash):
                        tx.execute(fixture,p,fault=fault)
                    self.assertIn(tx.status(fixture)["phase"],
                                  ("prepared","applying"))
                    self.assertEqual(tx.recover(fixture)["status"],
                                     "Rolled back to recorded pre-update files")
                    self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),
                                     b"installed-v1")
                    self.assertIsNone(tx._read(fixture,"installed","mods/new-helper.dll",optional=True))
                    self.assertEqual(tx._inventory(fixture),p.before)
                    self.assertEqual(tx.recover(fixture)["status"],"Already rolled back")

    def test_crash_during_rollback_can_resume(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            with self.assertRaises(tx.SimulatedCrash):
                tx.recover(fixture,fault="after_rollback:1")
            self.assertEqual(tx.status(fixture)["phase"],"rolling_back")
            result=tx.recover(fixture)
            self.assertEqual(result["status"],"Rolled back to recorded pre-update files")
            self.assertEqual(tx._inventory(fixture),p.before)

    def test_recovery_does_not_erase_manually_modified_files(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:1")
            changed=b"manual-change-after-failed-update"
            tx._write(fixture,"installed","mods/main.dll",changed)
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),changed)
            self.assertEqual(tx.status(fixture)["phase"],"applying")
            # A user can remove their edit or inspect the interrupted fixture.
            tx._write(fixture,"installed","mods/main.dll",b"installed-v2")
            self.assertEqual(tx.recover(fixture)["status"],
                             "Rolled back to recorded pre-update files")

    def test_untracked_user_file_collision_prevents_plan_without_writes(self):
        with tx.fixture_sandbox(
            {"mods/main.dll":b"unowned-but-real"},
            {"mods/main.dll":b"would-overwrite"},managed=()) as fixture:
            with self.assertRaisesRegex(tx.TransactionBlocked,"Untracked existing"):
                tx.build_plan(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),
                             b"unowned-but-real")
            self.assertEqual(tx.status(fixture)["phase"],"unstarted")

    def test_case_only_untracked_collision_is_blocked(self):
        with tx.fixture_sandbox(
            {"Mods/Installed.dll":b"user-owned-untracked"},
            {"mods/installed.DLL":b"candidate"},
            managed=()) as fixture:
            with self.assertRaisesRegex(tx.TransactionBlocked,"letter case"):
                tx.build_plan(fixture)
            self.assertEqual(tx._read(fixture,"installed","Mods/Installed.dll"),
                             b"user-owned-untracked")

    def test_unchanged_untracked_config_survives_update(self):
        with tx.fixture_sandbox(
            {"mods/main.dll":b"owned-1","config/experimental.ini":b"manual"},
            {"mods/main.dll":b"owned-2"},managed=("mods/main.dll",)) as fixture:
            tx.execute(fixture,tx.build_plan(fixture))
            self.assertEqual(tx._read(fixture,"installed","config/experimental.ini"),b"manual")
            tx.rollback(fixture)
            self.assertEqual(tx._read(fixture,"installed","config/experimental.ini"),b"manual")

    def test_manually_modified_managed_file_blocks_stale_plan(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            tx._write(fixture,"installed","config/settings.ini",b"edited-config")
            with self.assertRaisesRegex(tx.TransactionBlocked,"manually modified"):
                tx.execute(fixture,p)
            self.assertEqual(tx._read(fixture,"installed","config/settings.ini"),b"edited-config")
            self.assertIsNone(tx._read(fixture,"transaction","journal.json",optional=True))

    def test_incoming_file_changed_after_planning_blocks_commit(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            tx._write(fixture,"incoming","mods/main.dll",b"surprise-new-build")
            with self.assertRaisesRegex(tx.TransactionBlocked,"Stale fixture plan"):
                tx.execute(fixture,p)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),b"installed-v1")
            self.assertEqual(tx.status(fixture)["phase"],"unstarted")

    def test_temporary_disk_preflight_refuses_before_backup_or_game_write(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            from collections import namedtuple
            usage=namedtuple("usage","total used free")(1024,1024,0)
            with mock.patch.object(tx.shutil,"disk_usage",return_value=usage):
                with self.assertRaisesRegex(tx.TransactionBlocked,"disk space"):
                    tx.execute(fixture,p)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),
                             b"installed-v1")
            self.assertIsNone(tx._journal(fixture))

    def test_regular_io_failure_triggers_automatic_fixture_rollback(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            original=tx._write
            attempts=[0]
            def interrupted_write(sandbox,section,rel,data):
                if section=="installed" and rel=="mods/new-helper.dll" and attempts[0]==0:
                    attempts[0]+=1
                    raise OSError("simulated fixture disk write error")
                return original(sandbox,section,rel,data)
            with mock.patch.object(tx,"_write",side_effect=interrupted_write):
                with self.assertRaisesRegex(tx.TransactionBlocked,
                                            "rolled back automatically"):
                    tx.execute(fixture,p)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),
                             b"installed-v1")
            self.assertIsNone(tx._read(fixture,"installed","mods/new-helper.dll",optional=True))
            self.assertEqual(tx._inventory(fixture),p.before)
            self.assertEqual(tx.status(fixture)["phase"],"rolled_back")

    def test_user_edits_after_commit_block_explicit_rollback(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            tx.execute(fixture,p)
            tx._write(fixture,"installed","mods/main.dll",b"manual-edit")
            with self.assertRaises(tx.RecoveryBlocked):
                tx.rollback(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),
                             b"manual-edit")
            self.assertEqual(tx.status(fixture)["phase"],"committed")

    def test_backup_tamper_refuses_recovery_before_mutation(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:1")
            tx._write(fixture,"transaction","backup/config/settings.ini",b"tampered-backup")
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/main.dll"),b"installed-v2")
            self.assertEqual(tx._read(fixture,"installed","config/settings.ini"),
                             b"user-preset-original")

    def test_journal_tamper_or_symlink_refuses_recovery(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:1")
            path=fixture.root/"transaction/journal.json"
            original=path.read_bytes()
            data=json.loads(original)
            data["phase"]="committed"
            path.write_text(json.dumps(data))
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)
            path.write_bytes(original)
            other=fixture.root/"transaction/inventory.json"
            path.unlink()
            path.symlink_to(other)
            with self.assertRaises(tx.TransactionBlocked):
                tx.recover(fixture)

    def test_symlink_file_and_parent_during_recovery_is_refused(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_backup")
            external=fixture.root.parent / ("unexpected-outside-" + fixture.root.name)
            external.write_bytes(b"do-not-touch")
            try:
                path=fixture.root/"installed/mods/main.dll"
                path.unlink()
                path.symlink_to(external)
                with self.assertRaises(tx.TransactionBlocked):
                    tx.recover(fixture)
                self.assertEqual(external.read_bytes(),b"do-not-touch")
            finally:
                external.unlink(missing_ok=True)

    def test_symlink_incoming_file_refuses_planning(self):
        with self.sample() as fixture:
            path=fixture.root/"incoming/mods/main.dll"
            path.unlink()
            path.symlink_to(fixture.root/"installed/mods/main.dll")
            with self.assertRaises(tx.TransactionBlocked):
                tx.build_plan(fixture)

    def test_case_collision_and_path_escape_refused(self):
        for inputs in [
            ({"Mods/main.dll":b"a"},{"mods/MAIN.dll":b"b"}),
            ({},{"../home/data":b"bad"}),
            ({},{"mod\file.dll":b"bad"}),
            ({},{"C:/Windows/dll":b"bad"}),
            ({},{"mods//dll":b"bad"}),
        ]:
            installed,incoming=inputs
            with self.subTest(inputs=inputs):
                if list(incoming)[0] in ("mods/MAIN.dll",):
                    with tx.fixture_sandbox(installed,incoming) as fixture:
                        # Distinct casing collides with an existing owned file.
                        with self.assertRaises(tx.TransactionBlocked):
                            tx.build_plan(fixture)
                else:
                    with self.assertRaises(tx.TransactionBlocked):
                        with tx.fixture_sandbox(installed,incoming):
                            pass

    def test_outside_fake_root_and_wrong_token_never_allowed(self):
        fixture=tx.Fixture(Path.home()/"Games"/"FakeGame", "anything")
        with self.assertRaises(tx.TransactionBlocked):
            tx.build_plan(fixture)
        with self.sample() as sandbox:
            fake=tx.Fixture(sandbox.root, "another-token")
            with self.assertRaises(tx.TransactionBlocked):
                tx.execute(fake,tx.build_plan(sandbox))
            fake2=tx.Fixture(sandbox.root.parent / "steamapps",sandbox.token)
            with self.assertRaises(tx.TransactionBlocked):
                tx.recover(fake2)

    def test_source_files_or_real_games_are_never_imported_into_fixture_api(self):
        with self.assertRaises(tx.TransactionBlocked):
            with tx.fixture_sandbox({"mods/file":Path(__file__)},
                                    {"mods/file":b"next"}):
                pass
        with self.assertRaises(tx.TransactionBlocked):
            with tx.fixture_sandbox({},{"mods/file":b"x"*(tx.MAX_FILE_BYTES+1)}):
                pass

    def test_existing_journal_prevents_retry_or_double_install(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            tx.execute(fixture,p)
            with self.assertRaises(tx.TransactionBlocked):
                tx.execute(fixture,p)
            with self.assertRaises(tx.TransactionBlocked):
                tx.build_plan(fixture)
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)

    def test_created_fixture_is_disposed_when_context_exits(self):
        with self.sample() as fixture:
            root=fixture.root
            self.assertTrue(root.is_dir())
        self.assertFalse(root.exists())
        with self.assertRaises(tx.TransactionBlocked):
            tx.status(fixture)

    def test_resume_across_python_process_boundary(self):
        with self.sample() as fixture:
            parent=tx.build_plan(fixture)
            code='''import sys
from pathlib import Path
from vrhub import offline_transaction as tx
f=tx.Fixture(Path(sys.argv[1]),sys.argv[2])
p=tx.build_plan(f)
try:
 tx.execute(f,p,fault="after_replace:1")
except tx.SimulatedCrash:
 sys.exit(37)
sys.exit(1)
'''
            child=subprocess.run(
                [sys.executable,"-B","-c",code,str(fixture.root),fixture.token],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=15)
            self.assertEqual(child.returncode,37,(child.stdout,child.stderr))
            self.assertEqual(tx.status(fixture)["phase"],"applying")
            self.assertEqual(tx.recover(fixture)["checked"],3)
            self.assertEqual(tx._inventory(fixture),parent.before)


if __name__ == "__main__":
    unittest.main()
