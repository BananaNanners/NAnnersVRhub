# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-L: offline-only preparation, ownership, directory and crash hardening."""
import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from vrhub import offline_transaction as tx


class OfflineHardeningTests(unittest.TestCase):
    def sample(self):
        return tx.fixture_sandbox(
            {"mods/vr.dll":b"old-vr", "config/options.ini":b"keep-config",
             "managed/unchanged.dat":b"unchanged"},
            {"mods/vr.dll":b"new-vr",
             "extra/nested/helper.dll":b"new-helper"})

    def _values(self, fixture):
        return (tx._read(fixture,"installed","mods/vr.dll"),
                tx._read(fixture,"installed","config/options.ini"),
                tx._read(fixture,"installed","extra/nested/helper.dll",optional=True),
                tx._inventory(fixture))

    def test_hardened_demo_fixture_only(self):
        result=tx.demo_hardened()
        self.assertTrue(result["fixture_only"])
        self.assertFalse(result["real_game_files_modified"])
        self.assertFalse(result["authorized_live_install"])
        self.assertTrue(result["manual_edit_protected"])
        self.assertTrue(result["temporary_fixtures_discarded"])
        self.assertEqual(result["directories_restored"],2)
        self.assertIn("Aborted incomplete",result["preparation"])

    def test_interrupted_preparation_is_not_a_verified_backup(self):
        for fault in ("after_prepare_start","after_backup_file:1",
                      "after_backup_file:2","after_backup_file:3",
                      "after_stage_file:1","after_stage_file:2"):
            with self.subTest(fault=fault), self.sample() as fixture:
                before=self._values(fixture)
                before_dirs=tx._snapshot_dirs(fixture)
                with self.assertRaises(tx.SimulatedCrash):
                    tx.execute(fixture,tx.build_plan(fixture),fault=fault)
                self.assertEqual(tx.status(fixture)["phase"],"preparing")
                result=tx.recover(fixture)
                self.assertFalse(result["partial_backup_trusted"])
                self.assertIn("Aborted incomplete",result["status"])
                self.assertEqual(tx.status(fixture)["phase"],"aborted_before_apply")
                self.assertEqual(before,self._values(fixture))
                self.assertEqual(before_dirs,tx._snapshot_dirs(fixture))
                again=tx.recover(fixture)
                self.assertFalse(again["partial_backup_trusted"])
                with self.assertRaises(tx.TransactionBlocked):
                    tx.build_plan(fixture)

    def test_failed_backup_io_leaves_abortable_intent(self):
        with self.sample() as fixture:
            original=tx._write
            failures=[0]
            def failing(fixture_arg,section,rel,data):
                if section=="transaction" and rel.startswith("backup/"):
                    failures[0]+=1
                    if failures[0]==2:
                        raise OSError("Synthetic disk I/O failure")
                return original(fixture_arg,section,rel,data)
            with mock.patch.object(tx,"_write",side_effect=failing):
                with self.assertRaisesRegex(tx.TransactionBlocked,"Backup preparation failed"):
                    tx.execute(fixture,tx.build_plan(fixture))
            self.assertEqual(tx.status(fixture)["phase"],"preparing")
            self.assertFalse(tx.recover(fixture)["partial_backup_trusted"])
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"old-vr")

    def test_user_edit_while_backup_incomplete_blocks_clean_abort(self):
        with self.sample() as fixture:
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,tx.build_plan(fixture),
                           fault="after_backup_file:1")
            tx._write(fixture,"installed","mods/vr.dll",b"user-edited")
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"user-edited")
            self.assertEqual(tx.status(fixture)["phase"],"preparing")

    def test_ownership_seal_detects_stale_modified_records(self):
        with self.sample() as fixture:
            doc=fixture.root/"transaction/inventory.json"
            original=doc.read_bytes()
            changed=json.loads(original)
            changed["managed"]["mods/vr.dll"]="f"*64
            doc.write_text(json.dumps(changed))
            with self.assertRaisesRegex(tx.TransactionBlocked,"seal"):
                tx.build_plan(fixture)
            doc.write_bytes(original)
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            doc.write_text(json.dumps(changed))
            with self.assertRaises((tx.RecoveryBlocked,tx.TransactionBlocked)):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"new-vr")
            doc.write_bytes(original)
            self.assertEqual(tx.recover(fixture)["status"],
                             "Rolled back to recorded pre-update files")

    def test_same_content_but_new_owner_record_is_untrusted(self):
        with self.sample() as fixture:
            doc=fixture.root/"transaction/inventory.json"
            data=json.loads(doc.read_bytes())
            data.pop("seal")
            doc.write_text(json.dumps(data))
            with self.assertRaisesRegex(tx.TransactionBlocked,"seal"):
                tx.build_plan(fixture)

    def test_complete_directory_tree_and_file_modes_are_restored(self):
        with self.sample() as fixture:
            empty=fixture.root/"installed/empty/keep"
            empty.mkdir(parents=True)
            empty.chmod(0o750)
            file=fixture.root/"installed/mods/vr.dll"
            file.chmod(0o640)
            before_dirs=tx._snapshot_dirs(fixture)
            before_mode=stat.S_IMODE(file.stat().st_mode)
            p=tx.build_plan(fixture)
            self.assertIn("extra",p.fingerprint and tx._plan_body(fixture)["new_dirs"])
            tx.execute(fixture,p)
            self.assertTrue((fixture.root/"installed/extra/nested").is_dir())
            self.assertEqual(stat.S_IMODE(file.stat().st_mode),before_mode)
            report=tx.rollback(fixture)
            self.assertEqual(report["directories_restored"],2)
            self.assertEqual(tx._snapshot_dirs(fixture),before_dirs)
            self.assertTrue(empty.is_dir())
            self.assertEqual(stat.S_IMODE(empty.stat().st_mode),0o750)
            self.assertEqual(stat.S_IMODE(file.stat().st_mode),before_mode)
            self.assertFalse((fixture.root/"installed/extra").exists())

    def test_recovery_after_cleanup_interruption_is_idempotent(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            dirs_before=tx._snapshot_dirs(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            with self.assertRaises(tx.SimulatedCrash):
                tx.recover(fixture,fault="after_directory_cleanup:1")
            self.assertEqual(tx.status(fixture)["phase"],"rolling_back")
            self.assertEqual(tx.recover(fixture)["status"],
                             "Rolled back to recorded pre-update files")
            self.assertEqual(tx._snapshot_dirs(fixture),dirs_before)
            self.assertFalse((fixture.root/"installed/extra").exists())

    def test_untracked_file_inside_new_directory_blocks_rollback(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            manual=fixture.root/"installed/extra/nested/my-notes.ini"
            manual.write_bytes(b"please preserve")
            with self.assertRaisesRegex(tx.RecoveryBlocked,"Untracked user file"):
                tx.recover(fixture)
            self.assertEqual(manual.read_bytes(),b"please preserve")
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"new-vr")
            manual.unlink()
            self.assertEqual(tx.recover(fixture)["status"],
                             "Rolled back to recorded pre-update files")

    def test_unexpected_manual_empty_directory_blocks_rollback(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            custom=fixture.root/"installed/manual-dir"
            custom.mkdir()
            with self.assertRaisesRegex(tx.RecoveryBlocked,"user-created directory"):
                tx.recover(fixture)
            self.assertTrue(custom.is_dir())
            custom.rmdir()
            self.assertEqual(tx.recover(fixture)["status"],
                             "Rolled back to recorded pre-update files")

    def test_original_directory_mode_tamper_blocks_recovery(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            dirname=fixture.root/"installed/mods"
            dirname.chmod(0o755)
            with self.assertRaisesRegex(tx.RecoveryBlocked,"directory permissions"):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"new-vr")
            dirname.chmod(0o700)
            tx.recover(fixture)

    def test_file_mode_tamper_blocks_recovery_and_preserves_mode(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:1")
            path=fixture.root/"installed/mods/vr.dll"
            path.chmod(0o644)
            with self.assertRaisesRegex(tx.RecoveryBlocked,"permissions"):
                tx.recover(fixture)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o644)
            path.chmod(0o600)
            tx.recover(fixture)

    def test_directory_change_after_plan_is_stale(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            (fixture.root/"installed/new-empty-dir").mkdir()
            with self.assertRaisesRegex(tx.TransactionBlocked,"Stale fixture plan"):
                tx.execute(fixture,p)
            self.assertEqual(tx.status(fixture)["phase"],"unstarted")

    def test_case_only_directory_collision_rejected(self):
        with tx.fixture_sandbox(
            {"Mods/original.dll":b"old"},
            {"mods/new.dll":b"new"}) as fixture:
            with self.assertRaisesRegex(tx.TransactionBlocked,"directory differs"):
                tx.build_plan(fixture)

    def test_resealed_inconsistent_new_dir_manifest_rejected(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_replace:2")
            journal=tx._journal(fixture)
            journal["new_dirs"]=["wrong-directory"]
            tx._save_journal(fixture,journal)
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"new-vr")

    def test_preparing_seal_tamper_never_marks_backup_safe(self):
        with self.sample() as fixture:
            p=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,p,fault="after_backup_file:1")
            journal=fixture.root/"transaction/journal.json"
            contents=json.loads(journal.read_bytes())
            contents["phase"]="prepared"
            journal.write_text(json.dumps(contents))
            with self.assertRaises(tx.RecoveryBlocked):
                tx.recover(fixture)
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"old-vr")

    def _subprocess_exit(self,fixture,needle,phase,exit_code):
        code='''import os,sys
from pathlib import Path
from vrhub import offline_transaction as tx
fixture=tx.Fixture(Path(sys.argv[1]),sys.argv[2])
original=tx._write
def exit_after(f,s,r,data):
    original(f,s,r,data)
    if s=="transaction" and r==sys.argv[3]:
        os._exit(int(sys.argv[4]))
tx._write=exit_after
tx.execute(fixture,tx.build_plan(fixture))
'''
        proc=subprocess.run(
            [sys.executable,"-B","-c",code,str(fixture.root),fixture.token,
             needle,str(exit_code)],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=20)
        self.assertEqual(proc.returncode,exit_code,proc.stderr)

    def test_actual_process_exit_during_backup_recovers_by_abort(self):
        with self.sample() as fixture:
            self._subprocess_exit(fixture,"backup/config/options.ini","preparing",73)
            self.assertEqual(tx.status(fixture)["phase"],"preparing")
            result=tx.recover(fixture)
            self.assertFalse(result["partial_backup_trusted"])
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"old-vr")

    def test_actual_process_exit_before_progress_journal_recovers(self):
        with self.sample() as fixture:
            # Child exits after installed file replacement, before journal progress.
            code='''import os,sys
from pathlib import Path
from vrhub import offline_transaction as tx
fixture=tx.Fixture(Path(sys.argv[1]),sys.argv[2])
original=tx._write
def exit_after(f,s,r,data):
    original(f,s,r,data)
    if s=="installed" and r=="mods/vr.dll":
        os._exit(74)
tx._write=exit_after
tx.execute(fixture,tx.build_plan(fixture))
'''
            proc=subprocess.run([sys.executable,"-B","-c",code,str(fixture.root),fixture.token],
                                cwd=str(Path(__file__).resolve().parents[1]),
                                capture_output=True,text=True,timeout=20)
            self.assertEqual(proc.returncode,74,proc.stderr)
            self.assertEqual(tx.status(fixture)["phase"],"applying")
            self.assertEqual(tx._read(fixture,"installed","mods/vr.dll"),b"new-vr")
            self.assertEqual(tx.recover(fixture)["status"],
                             "Rolled back to recorded pre-update files")
            self.assertFalse((fixture.root/"installed/extra").exists())

    def test_explicit_real_path_is_still_refused(self):
        fake=tx.Fixture(Path.home()/".local/share/Steam/steamapps/common", "bad")
        with self.assertRaises(tx.TransactionBlocked):
            tx.recover(fake)
        with self.assertRaises(tx.TransactionBlocked):
            tx.status(fake)


if __name__ == "__main__":
    unittest.main()
