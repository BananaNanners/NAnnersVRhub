# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-N pinned staging tests: synthetic ZIP bytes, private /tmp only."""
import copy
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import bepinex, offline_transaction as tx, pinned_staging as stage


def make_zip(files):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED) as f:
        for name, contents in files.items():
            f.writestr(name,contents)
    return buf.getvalue()


class PinnedStagingTests(unittest.TestCase):
    def sample(self,game="valheim"):
        build, packages, archives, old, owned = stage._scenario(game)
        return build, copy.deepcopy(packages), dict(archives), dict(old), tuple(owned)

    def prepared(self,game="valheim"):
        build,packages,archives,old,owned=self.sample(game)
        return stage.prepare_fixture(game,build,packages,archives,old,managed=owned)

    def test_successful_mapping_game_specific_destinations(self):
        expectations={
            "valheim":{"winhttp.dll","BepInEx/core/BepInEx.dll",
                       "BepInEx/plugins/vrmod.dll","valheim_Data/Managed/SteamVR.dll"},
            "subnautica":{"winhttp.dll","BepInEx/core/BepInEx.dll",
                         "BepInEx/plugins/vrmod.dll","Subnautica_Data/Managed/SteamVR.dll"},
            "elden-ring":{"Game/dxgi.dll","Game/ERVR/ERVR.dll"},
        }
        for game, expected in expectations.items():
            with self.subTest(game=game):
                result=self.prepared(game)
                self.assertEqual(set(result.incoming),expected)
                self.assertEqual({x["path"] for x in result.destination_rows},expected)
                self.assertFalse(result.authorized)
                self.assertFalse(result.live_executor_connected)
                self.assertFalse(result.real_game_compatibility_verified)
                self.assertIn("NOT live compatible",result.status)
                self.assertEqual(
                    [x["phase"] for x in result.package_rows],
                    sorted(x["phase"] for x in result.package_rows))
                self.assertTrue(all(x["live_authorized"] is False for x in result.package_rows))
                self.assertEqual(
                    {r["path"]:r["payload_sha256"] for r in result.destination_rows},
                    {name:hashlib.sha256(data).hexdigest() for name,data in result.incoming.items()})

    def test_all_three_rehearsal_results_nonlive(self):
        result=stage.rehearse_pinned_packages()
        self.assertTrue(result["fixture_only"])
        self.assertTrue(result["temporary_fixtures_discarded"])
        self.assertFalse(result["live_update_authorized"])
        self.assertFalse(result["real_game_files_modified"])
        self.assertFalse(result["real_game_compatibility_verified"])
        self.assertEqual([r["game"] for r in result["results"]],
                         ["valheim","subnautica","elden-ring"])
        self.assertTrue(all(r["rollback_passed"] and
                            r["synthetic_pin_verified"] and
                            not r["real_compatibility_verified"]
                            for r in result["results"]))

    def test_bad_pin_refuses_to_open_any_archive(self):
        build,pkgs,zips,old,owned=self.sample()
        pkgs[0]["sha256"]="f"*64
        with mock.patch.object(bepinex,"archive_plan",
                               side_effect=AssertionError("should not open")):
            with self.assertRaisesRegex(stage.StageBlocked,"differs"):
                stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_declared_game_build_required_and_does_not_prove_live_compatibility(self):
        build,pkgs,zips,old,owned=self.sample()
        pkgs[0]["compatible_builds"]=["DIFFERENT-TEST-BUILD"]
        with self.assertRaisesRegex(stage.StageBlocked,"compatibility"):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        pkgs[0]["compatible_builds"].append(build)
        result=stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        self.assertFalse(result.real_game_compatibility_verified)

    def test_old_new_versions_must_be_comparable_and_newer(self):
        for version in ("1.0.0","0.9.9","1.1.0-alpha","v2.0","../2.0"):
            with self.subTest(version=version):
                build,pkgs,zips,old,owned=self.sample()
                pkgs[0]["future_version"]=version
                with self.assertRaises(stage.StageBlocked):
                    stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_missing_duplicate_or_out_of_order_dependency_is_blocked(self):
        for required, phase, swap in (
            (["missing"],2,False),
            (["loader"],1,False),
            (["loader"],2,True),
            (["loader","loader"],2,False),
        ):
            with self.subTest(required=required,phase=phase,swap=swap):
                build,pkgs,zips,old,owned=self.sample()
                pkgs[1]["requires"]=required
                pkgs[1]["phase"]=phase
                if swap:
                    pkgs.reverse()
                with self.assertRaises(stage.StageBlocked):
                    stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_support_scope_never_includes_uevr_or_cyberpunk(self):
        for game in ("cyberpunk-2077","fatekeeper","ready-or-not","skyrim-vr-mgo"):
            with self.subTest(game=game):
                build,pkgs,zips,old,owned=self.sample()
                with self.assertRaisesRegex(stage.StageBlocked,"Only the three"):
                    stage.prepare_fixture(game,build,pkgs,zips,old,managed=owned)

    def test_malformed_or_missing_archive_is_blocked(self):
        build,pkgs,zips,old,owned=self.sample()
        zips.pop("loader")
        with self.assertRaises(stage.StageBlocked):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        zips["loader"]="/home/user/Downloads/real.zip"
        with self.assertRaises(stage.StageBlocked):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_untracked_existing_file_refuses_staging(self):
        build,pkgs,zips,old,owned=self.sample()
        owned=tuple(x for x in owned if x!="winhttp.dll")
        with self.assertRaisesRegex(stage.StageBlocked,"untracked"):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        owned=tuple(x for x in owned if x!="BepInEx/plugins/vrmod.dll")
        with self.assertRaisesRegex(stage.StageBlocked,"untracked"):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_case_only_collision_with_untracked_file(self):
        build,pkgs,zips,old,owned=self.sample()
        old["WinHTTP.dll"]=old.pop("winhttp.dll")
        owned=tuple(n for n in owned if n!="winhttp.dll")
        with self.assertRaisesRegex(stage.StageBlocked,"differently cased"):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_modified_installed_bytes_after_staging_block_transaction(self):
        prepared=self.prepared()
        with tx.fixture_sandbox(prepared.installed,prepared.incoming,
                                managed=prepared.managed) as fixture:
            plan=tx.build_plan(fixture)
            tx._write(fixture,"installed","winhttp.dll",b"user-modified-after-scan")
            with self.assertRaises(tx.TransactionBlocked):
                tx.execute(fixture,plan)
            self.assertEqual(tx._read(fixture,"installed","winhttp.dll"),
                             b"user-modified-after-scan")

    def test_stale_incoming_payload_after_staging_blocks_transaction(self):
        prepared=self.prepared()
        with tx.fixture_sandbox(prepared.installed,prepared.incoming,
                                managed=prepared.managed) as fixture:
            plan=tx.build_plan(fixture)
            tx._write(fixture,"incoming","winhttp.dll",b"different-build")
            with self.assertRaisesRegex(tx.TransactionBlocked,"Stale"):
                tx.execute(fixture,plan)
            self.assertEqual(tx.status(fixture)["phase"],"unstarted")

    def test_parser_rejects_unsafe_member_escape_and_symlinks(self):
        for bad_name in ("../winhttp.dll","BepInEx/../../winhttp.dll",
                         "BepInEx/evil\thing.dll","C:/bad.dll"):
            with self.subTest(name=bad_name):
                build,pkgs,zips,old,owned=self.sample("subnautica")
                files={"winhttp.dll":b"ok",
                       "BepInEx/core/BepInEx.dll":b"good",
                       bad_name:b"unsafe"}
                zipdata=make_zip(files)
                pkgs[0]["sha256"]=hashlib.sha256(zipdata).hexdigest()
                zips["loader"]=zipdata
                with self.assertRaises(stage.StageBlocked):
                    stage.prepare_fixture("subnautica",build,pkgs,zips,old,managed=owned)

    def test_incomplete_archive_required_files_rejected(self):
        build,pkgs,zips,old,owned=self.sample("subnautica")
        raw=make_zip({"winhttp.dll":b"only one"})
        pkgs[0]["sha256"]=hashlib.sha256(raw).hexdigest()
        zips["loader"]=raw
        with self.assertRaises(stage.StageBlocked):
            stage.prepare_fixture("subnautica",build,pkgs,zips,old,managed=owned)

    def test_cross_package_overlapping_destinations_refused(self):
        build,pkgs,zips,old,owned=self.sample("subnautica")
        raw=make_zip({"BepInEx/core/BepInEx.dll":b"other",
                      "BepInEx/plugins/vrmod.dll":b"mod"})
        pkgs[1]["sha256"]=hashlib.sha256(raw).hexdigest()
        zips["vrmod"]=raw
        with self.assertRaisesRegex(stage.StageBlocked,"overlap"):
            stage.prepare_fixture("subnautica",build,pkgs,zips,old,managed=owned)

    def test_identical_file_not_accepted_as_replacement(self):
        build,pkgs,zips,old,owned=self.sample("subnautica")
        old["winhttp.dll"]=b"future-loader"
        with self.assertRaisesRegex(stage.StageBlocked,"Identical"):
            stage.prepare_fixture("subnautica",build,pkgs,zips,old,managed=owned)

    def test_boolean_phase_and_bad_version_fields_refused(self):
        build,pkgs,zips,old,owned=self.sample("valheim")
        pkgs[0]["phase"]=True
        with self.assertRaisesRegex(stage.StageBlocked,"Dependency phase"):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        pkgs[0]["phase"]=1
        pkgs[0]["installed_version"]=None
        with self.assertRaisesRegex(stage.StageBlocked,"numeric"):
            stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)

    def test_duplicate_zip_member_and_case_alias_are_blocked(self):
        build,pkgs,zips,old,owned=self.sample("subnautica")
        zipbuf=io.BytesIO()
        with zipfile.ZipFile(zipbuf,"w") as z:
            z.writestr("winhttp.dll",b"old")
            z.writestr("WINHTTP.DLL",b"alias")
            z.writestr("BepInEx/core/BepInEx.dll",b"core")
        raw=zipbuf.getvalue()
        pkgs[0]["sha256"]=hashlib.sha256(raw).hexdigest()
        zips["loader"]=raw
        with self.assertRaises(stage.StageBlocked):
            stage.prepare_fixture("subnautica",build,pkgs,zips,old,managed=owned)

    def test_zip_symlink_member_rejected_by_existing_parser(self):
        build,pkgs,zips,old,owned=self.sample("subnautica")
        zipbuf=io.BytesIO()
        with zipfile.ZipFile(zipbuf,"w") as z:
            z.writestr("winhttp.dll",b"loader")
            z.writestr("BepInEx/core/BepInEx.dll",b"core")
            link=zipfile.ZipInfo("BepInEx/plugins/untrusted.dll")
            link.create_system=3
            link.external_attr=(0o120777 << 16)
            z.writestr(link,"../../outside")
        raw=zipbuf.getvalue()
        pkgs[0]["sha256"]=hashlib.sha256(raw).hexdigest()
        zips["loader"]=raw
        with self.assertRaises(stage.StageBlocked):
            stage.prepare_fixture("subnautica",build,pkgs,zips,old,managed=owned)

    def test_renamed_archive_and_reordered_zip_members_do_not_change_targets(self):
        prepared=self.prepared("valheim")
        build,pkgs,zips,old,owned=self.sample("valheim")
        result=stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        self.assertEqual(prepared.destination_rows,result.destination_rows)
        self.assertEqual(prepared.incoming,result.incoming)

    def test_all_files_are_only_staged_inside_owned_tmp(self):
        build,pkgs,zips,old,owned=self.sample("valheim")
        original=bepinex.archive_plan
        seen=[]
        def spy(path,recipe):
            seen.append(path)
            self.assertTrue(str(path).startswith("/tmp/nanners-dev5d3n-stage-"))
            self.assertEqual(path.name,"synthetic-pinned-package.zip")
            self.assertFalse(path.is_symlink())
            return original(path,recipe)
        with mock.patch.object(bepinex,"archive_plan",side_effect=spy):
            result=stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        self.assertEqual(len(seen),2)
        self.assertTrue(all(not path.exists() for path in seen))
        self.assertFalse(result.authorized)

    def test_no_live_installer_or_real_hub_reads_are_possible_through_stage(self):
        from vrhub import hub, profile_safety
        with (mock.patch.object(bepinex,"install",
                                side_effect=AssertionError("real installer")),
              mock.patch.object(hub,"install",
                                side_effect=AssertionError("real installer")),
              mock.patch.object(profile_safety,"install",
                                side_effect=AssertionError("real installer")),
              mock.patch.object(hub,"state",
                                side_effect=AssertionError("real state"))):
            result=stage.rehearse_pinned_packages()
            self.assertFalse(result["live_update_authorized"])

    def test_user_data_is_unchanged_by_build(self):
        build,pkgs,zips,old,owned=self.sample()
        before=(copy.deepcopy(pkgs),dict(zips),dict(old),owned)
        stage.prepare_fixture("valheim",build,pkgs,zips,old,managed=owned)
        self.assertEqual((pkgs,zips,old,owned),before)


if __name__=="__main__":
    unittest.main()
