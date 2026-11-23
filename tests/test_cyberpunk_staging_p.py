# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-P — synthetic Cyberpunk game-root component update safeguards."""
import copy
import hashlib
import io
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import cyberpunk_staging as p, hub, install_review
from vrhub import offline_transaction as tx


def zipdata(rows):
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in rows.items():
            archive.writestr(name, content)
    return buff.getvalue()


class CyberpunkStagingTests(unittest.TestCase):
    def setUp(self):
        self.recipe = hub.load_recipes()["cyberpunk-2077"]
        self.inputs = p._scenario(self.recipe)

    def stage(self, **changes):
        data = copy.deepcopy(self.inputs)
        data.update(changes)
        return p.prepare_fixture(self.recipe, **data)

    def changed_zip(self, component, rows):
        data = copy.deepcopy(self.inputs)
        blob = zipdata(rows)
        data["archives"][component] = blob
        for candidate in data["proposals"]:
            if candidate["id"] == component:
                candidate["sha256"] = hashlib.sha256(blob).hexdigest()
        return data

    def test_staged_components_and_targets_are_distinct(self):
        batch = self.stage()
        self.assertEqual([r["component_id"] for r in batch.candidate_rows],
                         ["107", "30093"])
        self.assertEqual(batch.candidate_rows[1]["phase"], 2)
        self.assertEqual(len(batch.destination_rows), 4)
        self.assertEqual(
            {r["owner"] for r in batch.destination_rows}, {"107", "30093"})
        self.assertEqual(sum(r["action"] == "add" for r in batch.destination_rows),2)
        self.assertFalse(batch.authorized)
        self.assertFalse(batch.real_game_compatibility_verified)
        self.assertFalse(batch.live_executor_connected)
        self.assertIn("LIVE UPDATE DISABLED",batch.status)

    def test_synthetic_multi_component_interrupt_and_rollback(self):
        result = p.rehearse_cyberpunk_components()
        self.assertTrue(result["fixture_only"])
        self.assertEqual(result["component_archives"],2)
        self.assertEqual(result["staged_files"],4)
        self.assertTrue(result["multi_component_rollback_passed"])
        self.assertTrue(result["other_component_preserved"])
        self.assertTrue(result["untracked_mod_preserved"])
        self.assertTrue(result["temporary_fixture_discarded"])
        self.assertFalse(result["live_update_authorized"])
        self.assertFalse(result["real_compatibility_verified"])
        self.assertFalse(result["real_game_files_modified"])

    def test_15_recipe_ids_are_supported_but_never_live(self):
        self.assertEqual(len(self.recipe["components"]),15)
        listed = {str(row["nexus_mod"]) for row in self.recipe["components"]}
        self.assertEqual(len(listed),15)
        self.assertIn("30093",listed)
        self.assertIn("107",listed)
        self.assertFalse(self.stage().authorized)

    def test_wrong_or_missing_sha_never_opens_candidate_zip(self):
        for forged in ("0"*64,None,"not-a-sha"):
            with self.subTest(forged=forged):
                inputs=copy.deepcopy(self.inputs)
                inputs["proposals"][0]["sha256"]=forged
                with mock.patch.object(install_review,"_zip_preflight",
                                       side_effect=AssertionError("ZIP parser called")):
                    with self.assertRaises(p.ComponentStageBlocked):
                        p.prepare_fixture(self.recipe,**inputs)

    def test_source_paths_instead_of_synthetic_bytes_blocked(self):
        data=copy.deepcopy(self.inputs)
        data["archives"]["107"]="/home/user/Downloads/CET-107-v2.zip"
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_unknown_or_ambiguous_component_archive_name_refused(self):
        for filename in ("new-file.zip","Cyber Engine Tweaks-999.zip",
                         "CET-107-and-30093.zip","folder/CET-107.zip",
                         "CET-107.7z"):
            with self.subTest(filename=filename):
                data=copy.deepcopy(self.inputs)
                data["proposals"][0]["archive_name"]=filename
                with self.assertRaises(p.ComponentStageBlocked):
                    p.prepare_fixture(self.recipe,**data)

    def test_component_duplicate_or_missing_archive_refused(self):
        data=copy.deepcopy(self.inputs)
        data["proposals"].append(copy.deepcopy(data["proposals"][0]))
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)
        data=copy.deepcopy(self.inputs)
        data["archives"].pop("107")
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_existing_manual_script_unchanged_across_successful_fixture_commit(self):
        batch=self.stage()
        with tx.fixture_sandbox(batch.installed,batch.incoming,
                                managed=batch.managed) as fixture:
            before=tx._read(fixture,"installed","r6/scripts/my-manual-overrides.reds")
            transaction=tx.build_plan(fixture)
            result=tx.execute(fixture,transaction)
            self.assertFalse(result["authorized_live_install"])
            self.assertEqual(
                tx._read(fixture,"installed","r6/scripts/my-manual-overrides.reds"),
                before)
            self.assertEqual(
                tx._read(fixture,"installed","red4ext/plugins/red4ext.dll"),
                b"synthetic-RED4ext-v1")
            tx.rollback(fixture)
            self.assertEqual(
                tx._read(fixture,"installed","r6/scripts/my-manual-overrides.reds"),
                before)

    def test_cross_component_owned_file_collision_fails_closed(self):
        data=self.changed_zip("107",{
            "bin/x64/plugins/cet.dll":b"new-CET",
            "red4ext/plugins/red4ext.dll":b"steal-red4ext",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"unrelated or manual"):
            p.prepare_fixture(self.recipe,**data)

    def test_manual_file_collision_fails_closed(self):
        data=self.changed_zip("107",{
            "bin/x64/plugins/cet.dll":b"new-CET",
            "r6/scripts/my-manual-overrides.reds":b"overwrite manual",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"unrelated or manual"):
            p.prepare_fixture(self.recipe,**data)

    def test_case_only_collision_fails_closed(self):
        data=self.changed_zip("107",{
            "bin/x64/plugins/cet.dll":b"new-CET",
            "r6/scripts/MY-MANUAL-OVERRIDES.reds":b"wrong case",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"unrelated or manual"):
            p.prepare_fixture(self.recipe,**data)

    def test_two_selected_component_zips_mapping_same_target_fails(self):
        data=self.changed_zip("30093",{
            "bin/x64/plugins/cet.dll":b"overlap",
            "red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll":b"new-vr",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"overlap"):
            p.prepare_fixture(self.recipe,**data)

    def test_removed_managed_file_requires_future_retirement_design(self):
        data=self.changed_zip("107",{
            "r6/scripts/new-cet.reds":b"only new file",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"omits a previously owned"):
            p.prepare_fixture(self.recipe,**data)

    def test_missing_vr_port_required_dll_is_rejected(self):
        data=self.changed_zip("30093",{
            "r6/scripts/vr-helper.reds":b"not required dll",
        })
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_new_destination_conflicting_with_manual_file_ancestor_is_blocked(self):
        data=copy.deepcopy(self.inputs)
        data["installed"]["r6/scripts/extra-folder"]=b"manual file, not a directory"
        updated=self.changed_zip("107",{
            "bin/x64/plugins/cet.dll":b"new-CET",
            "r6/scripts/extra-folder/nested.reds":b"child cannot be created",
        })
        updated["installed"]=data["installed"]
        with self.assertRaisesRegex(p.ComponentStageBlocked,"file ancestor"):
            p.prepare_fixture(self.recipe,**updated)

    def test_versions_with_equivalent_trailing_zeros_not_upgrades(self):
        data=copy.deepcopy(self.inputs)
        data["installed_versions"]["107"]="1.0"
        data["proposals"][0]["future_version"]="1.0.0"
        with self.assertRaisesRegex(p.ComponentStageBlocked,"strictly newer"):
            p.prepare_fixture(self.recipe,**data)

    def test_malformed_unhashable_owner_and_prerequisite_refused(self):
        data=copy.deepcopy(self.inputs)
        data["owners"]["bin/x64/plugins/cet.dll"]=["107"]
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)
        data=copy.deepcopy(self.inputs)
        data["proposals"][1]["requires"]=[["107"]]
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_multiple_cyberpunk_interruption_stages_recover_all_owned_and_manual(self):
        batch=self.stage()
        for fault in ("after_backup","after_replace:1","after_replace:4",
                      "after_all_files","after_inventory"):
            with self.subTest(fault=fault):
                with tx.fixture_sandbox(batch.installed,batch.incoming,
                                        managed=batch.managed) as fixture:
                    plan=tx.build_plan(fixture)
                    with self.assertRaises(tx.SimulatedCrash):
                        tx.execute(fixture,plan,fault=fault)
                    result=tx.recover(fixture)
                    self.assertFalse(result["authorized_live_install"])
                    self.assertEqual(tx._inventory(fixture),plan.before)
                    for name,original in batch.installed.items():
                        self.assertEqual(tx._read(fixture,"installed",name),original)
                    for name in batch.incoming:
                        if name not in batch.installed:
                            self.assertIsNone(tx._read(fixture,"installed",name,optional=True))

    def test_unmapped_zip_member_refused_before_staging(self):
        data=self.changed_zip("107",{
            "bin/x64/plugins/cet.dll":b"new",
            "README.txt":b"manual content not silently dropped",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"Unmapped"):
            p.prepare_fixture(self.recipe,**data)

    def test_invalid_archive_members_rejected_by_existing_parser(self):
        for name in ("../outside.dll","bin/x64/../../outside.dll",
                     "C:/escape.dll","r6/scripts/evil\bad.reds"):
            with self.subTest(name=name):
                data=self.changed_zip("107",{
                    "bin/x64/plugins/cet.dll":b"new",
                    name:b"untrusted",
                })
                with self.assertRaises(p.ComponentStageBlocked):
                    p.prepare_fixture(self.recipe,**data)

    def test_symlink_zip_member_refused(self):
        buff=io.BytesIO()
        with zipfile.ZipFile(buff,"w") as z:
            z.writestr("bin/x64/plugins/cet.dll",b"new")
            link=zipfile.ZipInfo("r6/scripts/link.reds")
            link.create_system=3
            link.external_attr=0o120777<<16
            z.writestr(link,"../../unsafe")
        data=copy.deepcopy(self.inputs)
        raw=buff.getvalue()
        data["archives"]["107"]=raw
        data["proposals"][0]["sha256"]=p._sha(raw)
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_stale_recorded_sha_or_missing_owner_blocks_batch(self):
        data=copy.deepcopy(self.inputs)
        key="bin/x64/plugins/cet.dll"
        data["recorded_sha256"][key]="f"*64
        with self.assertRaisesRegex(p.ComponentStageBlocked,"changed"):
            p.prepare_fixture(self.recipe,**data)
        data=copy.deepcopy(self.inputs)
        data["owners"].pop(key)
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_untracked_original_file_survives_component_transaction(self):
        data=copy.deepcopy(self.inputs)
        data["installed"]["r6/scripts/another-untracked.reds"]=b"user-only"
        batch=p.prepare_fixture(self.recipe,**data)
        with tx.fixture_sandbox(batch.installed,batch.incoming,
                                managed=batch.managed) as fixture:
            old=tx._read(fixture,"installed","r6/scripts/another-untracked.reds")
            transaction=tx.build_plan(fixture)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(fixture,transaction,fault="after_replace:1")
            tx.recover(fixture)
            self.assertEqual(
                tx._read(fixture,"installed","r6/scripts/another-untracked.reds"),old)

    def test_wrong_phase_and_prerequisites_fail(self):
        data=copy.deepcopy(self.inputs)
        data["proposals"][1]["requires"]=[]
        with self.assertRaisesRegex(p.ComponentStageBlocked,"Later-phase"):
            p.prepare_fixture(self.recipe,**data)
        data=copy.deepcopy(self.inputs)
        data["proposals"][1]["requires"]=["uninstalled-component"]
        with self.assertRaisesRegex(p.ComponentStageBlocked,"prerequisite"):
            p.prepare_fixture(self.recipe,**data)
        data=copy.deepcopy(self.inputs)
        data["proposals"][0]["requires"]=["30093"]
        with self.assertRaisesRegex(p.ComponentStageBlocked,"phase"):
            p.prepare_fixture(self.recipe,**data)

    def test_out_of_order_batch_rejected(self):
        data=copy.deepcopy(self.inputs)
        data["proposals"].reverse()
        with self.assertRaisesRegex(p.ComponentStageBlocked,"ordering"):
            p.prepare_fixture(self.recipe,**data)

    def test_stale_versions_and_game_builds_fail(self):
        for version in ("1.0.0","0.5.0","2.0.0-beta","newest"):
            with self.subTest(version=version):
                data=copy.deepcopy(self.inputs)
                data["proposals"][0]["future_version"]=version
                with self.assertRaises(p.ComponentStageBlocked):
                    p.prepare_fixture(self.recipe,**data)
        data=copy.deepcopy(self.inputs)
        data["proposals"][0]["compatible_builds"]=["OTHER-BUILD"]
        with self.assertRaisesRegex(p.ComponentStageBlocked,"build"):
            p.prepare_fixture(self.recipe,**data)

    def test_unchanged_component_file_fails_noop(self):
        data=self.changed_zip("107",{
            "bin/x64/plugins/cet.dll":b"synthetic-CET-v1",
        })
        with self.assertRaisesRegex(p.ComponentStageBlocked,"Unchanged"):
            p.prepare_fixture(self.recipe,**data)

    def test_fake_recipe_or_unknown_id_cannot_grant_update(self):
        bad=copy.deepcopy(self.recipe)
        bad["id"]="other-game"
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(bad,**self.inputs)
        data=copy.deepcopy(self.inputs)
        data["proposals"][0]["id"]="999999"
        with self.assertRaises(p.ComponentStageBlocked):
            p.prepare_fixture(self.recipe,**data)

    def test_post_review_installed_or_zip_change_blocks_transaction(self):
        batch=self.stage()
        with tx.fixture_sandbox(batch.installed,batch.incoming,
                                managed=batch.managed) as fixture:
            transaction=tx.build_plan(fixture)
            tx._write(fixture,"installed","bin/x64/plugins/cet.dll",b"edited")
            with self.assertRaises(tx.TransactionBlocked):
                tx.execute(fixture,transaction)
        with tx.fixture_sandbox(batch.installed,batch.incoming,
                                managed=batch.managed) as fixture:
            transaction=tx.build_plan(fixture)
            tx._write(fixture,"incoming","bin/x64/plugins/cet.dll",b"changed")
            with self.assertRaises(tx.TransactionBlocked):
                tx.execute(fixture,transaction)

    def test_no_real_installer_invoked_by_synthetic_rehearsal(self):
        with (mock.patch.object(hub,"install_many",
                                side_effect=AssertionError("live installer")),
              mock.patch.object(hub,"_install_gameroot",
                                side_effect=AssertionError("live installer")),
              mock.patch.object(hub,"_load_state",
                                side_effect=AssertionError("live state")),
              mock.patch.object(hub,"_save_state",
                                side_effect=AssertionError("live write"))):
            report=p.rehearse_cyberpunk_components()
            self.assertFalse(report["live_update_authorized"])

    def test_only_owned_temporary_zip_is_inspected(self):
        data=copy.deepcopy(self.inputs)
        original=install_review._zip_preflight
        seen=[]
        def checked(path):
            self.assertTrue(str(path).startswith("/tmp/nanners-dev5d3p-stage-"))
            seen.append(path)
            return original(path)
        with mock.patch.object(install_review,"_zip_preflight",side_effect=checked):
            batch=p.prepare_fixture(self.recipe,**data)
        self.assertEqual(len(seen),2)
        self.assertTrue(all(not x.exists() for x in seen))
        self.assertFalse(batch.authorized)

    def test_inputs_not_mutated_by_staging(self):
        data=copy.deepcopy(self.inputs)
        baseline=copy.deepcopy(data)
        p.prepare_fixture(self.recipe,**data)
        self.assertEqual(data,baseline)


if __name__ == "__main__":
    unittest.main()
