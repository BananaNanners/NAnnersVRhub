# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-O: UEVR profile whole-directory synthetic-only update validation."""
import copy
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import hub, offline_transaction as tx, profile_safety
from vrhub import uevr_profile_staging as o


def zip_bytes(files):
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name, contents in files.items():
            z.writestr(name,contents)
    return bio.getvalue()


class ProfileStageModelTests(unittest.TestCase):
    def scenario(self, game="fatekeeper"):
        p=o._scenario(game)
        return p

    def supplied(self, game="fatekeeper", **kwargs):
        p=self.scenario(game)
        return {
            "game_id":game,
            "raw_zip":o._synthetic_zip(
                "SLASHER-Win64-Shipping" if game=="fatekeeper" else "HogwartsLegacy",
                p.candidate),
            "expected_sha":p.archive_sha256,
            "current":copy.deepcopy(p.current),
            "recorded_sha256":dict(p.recorded_sha256),
            "current_dirs":tuple(p.current_dirs),
            "recorded_dirs":tuple(p.current_dirs),
            "current_version":p.current_version,
            "future_version":p.future_version,
            "game_build":p.game_build,
            "compatible_builds":(p.game_build,),
            "injector_version":"TEST-INJECTOR-1",
            "compatible_injector_versions":("TEST-INJECTOR-1",),
            "explicit_removals":tuple(p.explicit_removals),
        } | kwargs

    def test_both_games_whole_directory_metadata_and_version(self):
        for game in ("fatekeeper","hogwarts-legacy"):
            with self.subTest(game=game):
                p=self.scenario(game)
                self.assertEqual(p.game_id,game)
                self.assertEqual(p.current_version,"v1.0.0")
                self.assertEqual(p.future_version,"v1.1.0")
                self.assertEqual(len(p.replacements),2)
                self.assertEqual(p.additions,("plugins/gesture.lua",))
                self.assertEqual(p.explicit_removals,("user-mappings/settings.ini",))
                self.assertIn("empty-preserved",p.current_dirs)
                self.assertFalse(p.authorized)
                self.assertFalse(p.live_executor_connected)
                self.assertFalse(p.real_game_compatibility_verified)
                self.assertFalse(p.injector_installation_authorized)
                self.assertIn("LIVE UPDATE BLOCKED",p.status)

    def test_two_full_directory_rehearsals_are_synthetic(self):
        report=o.rehearse_uevr_profiles()
        self.assertTrue(report["fixture_only"])
        self.assertTrue(report["temporary_fixtures_discarded"])
        self.assertFalse(report["real_game_files_modified"])
        self.assertFalse(report["authorized"])
        self.assertFalse(report["real_game_compatibility_verified"])
        self.assertFalse(report["live_profile_replacement_enabled"])
        self.assertFalse(report["injector_installation_enabled"])
        self.assertEqual([r["game"] for r in report["results"]],
                         ["fatekeeper","hogwarts-legacy"])
        self.assertTrue(all(r["whole_directory_backup_verified"] and
                            r["original_directories_restored"] and
                            r["rollback_passed"] and r["profile_files_restored"]==3 and
                            r["injector_separately_managed"] and not r["authorized"]
                            for r in report["results"]))

    def test_unverified_or_wrong_zip_sha_fails_before_staging(self):
        p=self.supplied()
        p["expected_sha"]="0"*64
        with mock.patch.object(profile_safety,"_archive_entries",
                               side_effect=AssertionError("no parse")):
            with self.assertRaisesRegex(o.ProfileStageBlocked,"SHA-256"):
                o.prepare_fixture(**p)

    def test_file_path_instead_of_zip_bytes_is_never_accepted(self):
        p=self.supplied()
        p["raw_zip"]="/home/user/Downloads/SLASHER.zip"
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**p)

    def test_unknown_game_or_injector_cannot_be_mistaken_for_profile(self):
        for game in ("valheim","cyberpunk-2077","ready-or-not","uevr"):
            with self.subTest(game=game), self.assertRaisesRegex(
                    o.ProfileStageBlocked,"Only Fatekeeper/Hogwarts"):
                o.prepare_fixture(**self.supplied(game_id=game))

    def test_old_equal_new_and_non_numeric_versions_are_rejected(self):
        for version in ("v1.0.0","0.9.0","v0.9","v1.1.0-beta","newest",None):
            with self.subTest(version=version):
                with self.assertRaises(o.ProfileStageBlocked):
                    o.prepare_fixture(**self.supplied(future_version=version))
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**self.supplied(current_version="unknown"))

    def test_game_build_must_be_explicit_and_declared(self):
        for bad in ((),("OTHER-GAME-BUILD",),("SIMULATED-UEVR-GAME-BUILD-2",)):
            with self.subTest(build=bad), self.assertRaisesRegex(
                    o.ProfileStageBlocked,"game-build"):
                o.prepare_fixture(**self.supplied(compatible_builds=bad))

    def test_injector_requires_separate_fixture_compatibility_declaration(self):
        for bad in ((),("INCOMPATIBLE-INJECTOR",)):
            with self.subTest(versions=bad), self.assertRaisesRegex(
                    o.ProfileStageBlocked,"injector compatibility"):
                o.prepare_fixture(**self.supplied(compatible_injector_versions=bad))
        with self.assertRaisesRegex(o.ProfileStageBlocked,"injector compatibility"):
            o.prepare_fixture(**self.supplied(injector_version="UNKNOWN"))

    def test_user_edit_to_recorded_config_blocks_staging(self):
        p=self.supplied()
        p["current"]["config.txt"]=b"user changed settings"
        with self.assertRaisesRegex(o.ProfileStageBlocked,"Untracked or changed"):
            o.prepare_fixture(**p)

    def test_user_added_empty_directory_requires_separate_inventory_review(self):
        p=self.supplied()
        p["current_dirs"] += ("manually-added-empty-folder",)
        with self.assertRaisesRegex(o.ProfileStageBlocked,"directory inventory"):
            o.prepare_fixture(**p)
        p=self.supplied(recorded_dirs=None)
        with self.assertRaisesRegex(o.ProfileStageBlocked,"directory inventory"):
            o.prepare_fixture(**p)

    def test_user_added_file_blocks_unverified_profile_adoption(self):
        p=self.supplied()
        p["current"]["user-mappings/user-config.ini"]=b"my personal bindings"
        with self.assertRaisesRegex(o.ProfileStageBlocked,"Untracked"):
            o.prepare_fixture(**p)

    def test_missing_exact_removal_requires_explicit_disposition(self):
        with self.assertRaisesRegex(o.ProfileStageBlocked,"exact explicit review"):
            o.prepare_fixture(**self.supplied(explicit_removals=()))
        with self.assertRaisesRegex(o.ProfileStageBlocked,"exact explicit review"):
            o.prepare_fixture(**self.supplied(explicit_removals=("user-mappings/settings.ini",
                                                                 "plugins/other.dll")))
        self.assertTrue(self.scenario().explicit_removals)

    def test_outside_wrapper_file_is_not_silently_dropped(self):
        p=self.supplied()
        raw=zip_bytes({
            "SLASHER-Win64-Shipping/config.txt":b"new",
            "SLASHER-Win64-Shipping/input.lua":b"new",
            "unrelated/other.dll":b"never silently ignore",
        })
        with self.assertRaisesRegex(o.ProfileStageBlocked,"outside"):
            o.prepare_fixture(**self.supplied(raw_zip=raw,expected_sha=o._sha(raw)))

    def test_profile_without_config_anchor_is_rejected(self):
        raw=zip_bytes({"WRAPPER/main.lua":b"not profile"})
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**self.supplied(raw_zip=raw,expected_sha=o._sha(raw)))

    def test_duplicate_config_anchors_are_ambiguous(self):
        raw=zip_bytes({"A/config.txt":b"x","B/config.txt":b"y"})
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**self.supplied(raw_zip=raw,expected_sha=o._sha(raw)))

    def test_unsafe_paths_and_zip_symlink_are_rejected(self):
        for name in ("../escape.txt","WRAPPER/../escape.txt","WRAPPER/C:/test.bin",
                     "WRAPPER/./bad.lua","WRAPPER/evil\bad.lua"):
            with self.subTest(name=name):
                raw=zip_bytes({"WRAPPER/config.txt":b"ok",name:b"bad"})
                with self.assertRaises(o.ProfileStageBlocked):
                    o.prepare_fixture(**self.supplied(raw_zip=raw,expected_sha=o._sha(raw)))
        bio=io.BytesIO()
        with zipfile.ZipFile(bio,"w") as z:
            z.writestr("wrapper/config.txt",b"good")
            link=zipfile.ZipInfo("wrapper/plugins/link.dll")
            link.create_system=3
            link.external_attr=0o120777 << 16
            z.writestr(link,"../../outside")
        raw=bio.getvalue()
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**self.supplied(raw_zip=raw,expected_sha=o._sha(raw)))

    def test_casefold_collision_between_old_files_and_directory_is_blocked(self):
        p=self.supplied()
        p["current"]["FILES"]=b"content"
        p["recorded_sha256"]["FILES"]=o._sha(b"content")
        p["current_dirs"] += ("files",)
        with self.assertRaisesRegex(o.ProfileStageBlocked,"case-colliding"):
            o.prepare_fixture(**p)

    def test_nonbytes_and_oversize_input_are_rejected(self):
        p=self.supplied()
        p["current"]["config.txt"]=Path("/tmp/not-bytes")
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**p)
        with self.assertRaises(o.ProfileStageBlocked):
            o.prepare_fixture(**self.supplied(raw_zip=b"x"*(o.MAX_ZIP_BYTES+1)))

    def test_stale_review_fingerprint_cannot_execute(self):
        p=self.scenario()
        with tx.fixture_sandbox(p.current,p.candidate,
                                managed=tuple(p.current)) as fixture:
            for name in p.current_dirs:
                (fixture.root/"installed"/name).mkdir(parents=True,exist_ok=True)
            p.candidate["config.txt"]=b"mutated-after-review"
            with self.assertRaisesRegex(o.ProfileStageBlocked,"changed"):
                o.execute_fixture(fixture,p)
            self.assertIsNone(o._document(fixture,optional=True))

    def test_no_live_installer_or_hub_state_called_by_rehearsal(self):
        with (mock.patch.object(hub,"install_profile",side_effect=AssertionError("live")),
              mock.patch.object(profile_safety,"install",side_effect=AssertionError("live")),
              mock.patch.object(hub,"_load_state",side_effect=AssertionError("state")),
              mock.patch.object(hub,"_save_state",side_effect=AssertionError("state"))):
            ans=o.rehearse_uevr_profiles()
            self.assertFalse(ans["authorized"])

    def test_user_inputs_are_not_mutated_during_preparation(self):
        p=self.supplied()
        before=copy.deepcopy(p)
        o.prepare_fixture(**p)
        self.assertEqual(before,p)


class WholeDirectoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.p=o._scenario("fatekeeper")

    def fixture(self):
        return tx.fixture_sandbox(self.p.current,self.p.candidate,
                                  managed=tuple(self.p.current))

    def initialize(self,fixture):
        for name in self.p.current_dirs:
            (fixture.root/"installed"/name).mkdir(parents=True,exist_ok=True)
        return profile_safety._snapshot(fixture.root/"installed")

    def original(self,fixture):
        self.assertEqual(profile_safety._snapshot(
            fixture.root/"installed"),self.before)
        for name,contents in self.p.current.items():
            self.assertEqual(tx._read(fixture,"installed",name),contents)
        self.assertTrue((fixture.root/"installed/empty-preserved").is_dir())
        self.assertFalse((fixture.root/"installed/plugins/gesture.lua").exists())

    def test_recovery_from_each_swap_interrupt_stage(self):
        for fault in ("after_journal","after_backup","after_prepare",
                      "after_displace","after_activate"):
            with self.subTest(fault=fault),self.fixture() as fixture:
                self.before=self.initialize(fixture)
                with self.assertRaises(tx.SimulatedCrash):
                    o.execute_fixture(fixture,self.p,fault=fault)
                result=o.recover_fixture(fixture)
                self.assertFalse(result["authorized"])
                if fault in ("after_journal","after_backup"):
                    self.assertFalse(result["partial_backup_trusted"])
                self.original(fixture)
                again=o.recover_fixture(fixture)
                self.assertFalse(again["authorized"])

    def test_explicit_rollback_after_committed_fixture_update(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            result=o.execute_fixture(fixture,self.p)
            self.assertFalse(result["authorized"])
            self.assertNotEqual(profile_safety._snapshot(
                fixture.root/"installed"),self.before)
            self.assertFalse((fixture.root/"installed/user-mappings/settings.ini").exists())
            self.assertEqual((fixture.root/"installed/config.txt").read_bytes(),
                             b"new-config-fatekeeper")
            with self.assertRaisesRegex(o.ProfileRecoveryBlocked,"explicit rollback"):
                o.recover_fixture(fixture)
            result=o.recover_fixture(fixture,explicit=True)
            self.assertIn("Restored",result["status"])
            self.original(fixture)

    def test_resume_if_interrupted_between_reject_and_restore(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            with self.assertRaises(tx.SimulatedCrash):
                o.recover_fixture(fixture,fault="after_reject")
            self.assertFalse((fixture.root/"installed").exists())
            self.assertTrue((fixture.root/"transaction/profile-rejected").is_dir())
            self.assertTrue((fixture.root/"transaction/profile-displaced").is_dir())
            result=o.recover_fixture(fixture)
            self.assertIn("Restored",result["status"])
            self.original(fixture)

    def test_resume_if_interrupted_just_after_original_restore(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            with self.assertRaises(tx.SimulatedCrash):
                o.recover_fixture(fixture,fault="after_restore")
            result=o.recover_fixture(fixture)
            self.assertFalse(result["authorized"])
            self.original(fixture)

    def test_user_added_file_after_activation_blocks_recovery(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            extra=fixture.root/"installed/manual-settings.ini"
            extra.write_bytes(b"user-added-settings")
            with self.assertRaises(o.ProfileRecoveryBlocked):
                o.recover_fixture(fixture)
            self.assertEqual(extra.read_bytes(),b"user-added-settings")
            self.assertEqual((fixture.root/"installed/config.txt").read_bytes(),
                             b"new-config-fatekeeper")
            extra.unlink()
            o.recover_fixture(fixture)
            self.original(fixture)

    def test_user_edits_staged_profile_config_cannot_be_lost(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            config=fixture.root/"installed/config.txt"
            config.write_bytes(b"manual-settings-after-update")
            with self.assertRaises(o.ProfileRecoveryBlocked):
                o.recover_fixture(fixture)
            self.assertEqual(config.read_bytes(),b"manual-settings-after-update")

    def test_manually_changed_permissions_block_recovery(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            config=fixture.root/"installed/config.txt"
            config.chmod(0o644)
            with self.assertRaisesRegex(o.ProfileRecoveryBlocked,"permission"):
                o.recover_fixture(fixture)
            self.assertEqual(stat.S_IMODE(config.stat().st_mode),0o644)
            config.chmod(0o600)
            o.recover_fixture(fixture)
            self.original(fixture)

    def test_backup_modified_after_activation_refuses_restore(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            backup=fixture.root/"transaction/profile-backup/config.txt"
            backup.write_bytes(b"corrupted-backup")
            with self.assertRaises(o.ProfileRecoveryBlocked):
                o.recover_fixture(fixture)
            self.assertEqual((fixture.root/"installed/config.txt").read_bytes(),
                             b"new-config-fatekeeper")
            self.assertTrue(backup.exists())

    def test_displaced_profile_symlink_refuses_recovery(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            target=fixture.root/"transaction/profile-displaced/scripts/input.lua"
            target.unlink()
            target.symlink_to(fixture.root/"installed/config.txt")
            with self.assertRaises(o.ProfileRecoveryBlocked):
                o.recover_fixture(fixture)

    def test_recovery_journal_tamper_refused_without_mutation(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            journal=fixture.root/"transaction/uevr-profile-journal.json"
            data=json.loads(journal.read_bytes())
            data["phase"]="committed"
            journal.write_text(json.dumps(data))
            with self.assertRaises(o.ProfileRecoveryBlocked):
                o.recover_fixture(fixture)
            self.assertEqual((fixture.root/"installed/config.txt").read_bytes(),
                             b"new-config-fatekeeper")

    def test_free_space_preflight_fails_before_any_profile_journal(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            from collections import namedtuple
            no_space=namedtuple("usage","total used free")(10,10,0)
            with mock.patch.object(o.shutil,"disk_usage",return_value=no_space):
                with self.assertRaisesRegex(o.ProfileStageBlocked,"Insufficient temporary"):
                    o.execute_fixture(fixture,self.p)
            self.assertIsNone(o._document(fixture,optional=True))
            self.original(fixture)

    def test_source_plan_mutation_during_staging_blocks_directory_swap(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            original=o._stage_copy
            def mutate_inputs(f,*args):
                result=original(f,*args)
                self.p.candidate["config.txt"]=b"later source changed"
                return result
            with mock.patch.object(o,"_stage_copy",side_effect=mutate_inputs):
                with self.assertRaisesRegex(o.ProfileStageBlocked,
                                            "snapshot failed|changed during staging"):
                    o.execute_fixture(fixture,self.p)
            self.original(fixture)
            self.assertEqual(o._document(fixture)["phase"],"preparing")
            result=o.recover_fixture(fixture)
            self.assertFalse(result["partial_backup_trusted"])
            self.original(fixture)

    def test_stale_in_fixture_installed_tree_blocks_execution(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            (fixture.root/"installed/config.txt").write_bytes(b"changed-before-review")
            with self.assertRaisesRegex(o.ProfileStageBlocked,"changed"):
                o.execute_fixture(fixture,self.p)
            self.assertIsNone(o._document(fixture,optional=True))

    def test_original_empty_directory_and_file_modes_restored(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            directory=fixture.root/"installed/empty-preserved"
            directory.chmod(0o750)
            config=fixture.root/"installed/config.txt"
            config.chmod(0o640)
            with self.assertRaises(tx.SimulatedCrash):
                o.execute_fixture(fixture,self.p,fault="after_activate")
            result=o.recover_fixture(fixture)
            self.assertIn("Restored",result["status"])
            self.original(fixture)
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode),0o750)
            self.assertEqual(stat.S_IMODE(config.stat().st_mode),0o640)

    def test_process_exit_between_directory_swaps_is_recoverable(self):
        with self.fixture() as fixture:
            self.before=self.initialize(fixture)
            code='''import os,sys
from pathlib import Path
from vrhub import offline_transaction as tx, uevr_profile_staging as o
fixture=tx.Fixture(Path(sys.argv[1]),sys.argv[2])
p=o._scenario("fatekeeper")
original=Path.rename
def kill_after(self,dest):
 result=original(self,dest)
 if self==fixture.root/"installed":
  os._exit(76)
 return result
Path.rename=kill_after
o.execute_fixture(fixture,p)
'''
            proc=subprocess.run(
                [sys.executable,"-B","-c",code,str(fixture.root),fixture.token],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=20)
            self.assertEqual(proc.returncode,76,proc.stderr)
            self.assertFalse((fixture.root/"installed").exists())
            result=o.recover_fixture(fixture)
            self.assertFalse(result["authorized"])
            self.original(fixture)

    def test_fixture_root_restriction_refuses_arbitrary_prefix(self):
        fake=tx.Fixture(Path.home()/"Games/Heroic/HogwartsLegacy",
                        "random")
        with self.assertRaises(tx.TransactionBlocked):
            o.recover_fixture(fake)
        with self.assertRaises(tx.TransactionBlocked):
            o.execute_fixture(fake,self.p)


if __name__=="__main__":
    unittest.main()
