# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C exact read-only manifests, retained backups, phases and TOCTOU gates."""
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import hub, install_review as review


class HumanReadableSizeTests(unittest.TestCase):
    def test_decimal_units_are_clear_and_consistent(self):
        cases = (
            (0, "0 B"), (999, "999 B"), (1_000, "1 KB"),
            (12_345, "12.35 KB"), (1_000_000, "1 MB"),
            (24_500_000, "24.5 MB"), (1_000_000_000, "1 GB"),
            (1_200_000_000, "1.2 GB"),
            (2_567_890_123, "2.57 GB"),
        )
        for count, expected in cases:
            with self.subTest(bytes=count):
                self.assertEqual(review.human_file_size(count), expected)
        for bad in (-1, 2.5, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    review.human_file_size(bad)

    def test_summary_is_human_readable_but_plan_retains_exact_byte_count(self):
        from dataclasses import replace
        from vrhub import install_review
        row = install_review.Target(
            "Content/Paks/existing.pak", "/game/Content/Paks/existing.pak",
            "Replace; back up original", 2_500_000_000, "a"*64, 1, 1, 1)
        plan = install_review.InstallPlan(
            "fixture", "Test", "pak", "/game",
            ("/archive/mod.pak",), ("b"*64,), ("Mod",),
            (row,), 0, 1, 2_500_000_000,
            "Persistent original backup", (), ("No files touched",), "c"*64)
        self.assertEqual(plan.backup_bytes, 2_500_000_000)
        self.assertEqual(plan.target_rows[0].current_bytes, 2_500_000_000)
        self.assertIn("2.5 GB", install_review.summary(plan))
        self.assertNotIn("2,500,000,000 bytes", install_review.summary(plan))


class InstallReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.library = self.root / "archives"
        self.library.mkdir()
        self.statefile = self.root / "hub" / "state.json"
        self.statefile.parent.mkdir()
        self.statefile.write_text("{}")
        for p in (
            mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.statefile)}),
            mock.patch.object(hub, "find_game", return_value=self.game),
        ):
            p.start()
            self.addCleanup(p.stop)

    def zip(self, name, members):
        archive = self.library / name
        with zipfile.ZipFile(archive, "w") as z:
            for member, payload in members:
                z.writestr(member, payload)
        return archive

    def file(self, rel, payload=b"old user file"):
        f = self.game / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(payload)
        return f

    def pak_recipe(self):
        return {"id": "ready-or-not", "name": "Ready or Not", "steam_appid": 42,
                "files": [{"kind": "pak", "dest": "Content/Paks"}]}

    def gameroot_recipe(self):
        return {
            "id": "cyberpunk-2077", "name": "Cyberpunk 2077",
            "steam_appid": 42, "method": "gameroot",
            "root_dirs": ["bin", "r6"],
            "components": [
                {"nexus_mod": 107, "name": "Cyber Engine Tweaks", "phase": 1,
                 "required_files": ["bin/x64/plugins/test.dll"]},
                {"nexus_mod": 30093, "name": "CyberpunkVR Port", "phase": 2},
            ],
        }

    def make_cyber(self):
        return self.zip("Cyber Engine Tweaks-107-1-2.zip", [
            ("bin/x64/plugins/test.dll", b"new binary"),
            ("r6/scripts/cet.reds", b"new script"),
        ])

    def pinned(self):
        from vrhub import bepinex
        (self.game / "valheim.exe").write_bytes(b"game")
        (self.game / "valheim_Data").mkdir()
        loader_data = {
            "BepInExPack_Valheim/winhttp.dll": b"loader",
            "BepInExPack_Valheim/doorstop_config.ini": b"setting",
            "BepInExPack_Valheim/BepInEx/config/BepInEx.cfg": b"config",
            "BepInExPack_Valheim/BepInEx/core/BepInEx.dll": b"core",
            "BepInExPack_Valheim/BepInEx/core/BepInEx.Preloader.dll": b"preloader",
        }
        mod_data = {
            "BepInEx/plugins/ValheimVRMod.dll": b"mod",
            "valheim_Data/Managed/SteamVR.dll": b"steamvr",
            "valheim_Data/Managed/Unity.XR.OpenVR.dll": b"openvr",
            "valheim_Data/Managed/Unity.XR.Management.dll": b"xr",
            "valheim_Data/Plugins/x86_64/openvr_api.dll": b"api",
            "valheim_Data/Plugins/x86_64/XRSDKOpenVR.dll": b"sdk",
            "valheim_Data/UnitySubsystems/XRSDKOpenVR/UnitySubsystemsManifest.json": b"manifest",
            "valheim_Data/StreamingAssets/SteamVR/actions.json": b"actions",
            "valheim_Data/StreamingAssets/SteamVR/bindings_oculus_touch.json": b"bindings",
            "valheim_Data/StreamingAssets/steamvr_player_prefabs/a.txt": b"prefab",
            "valheim_Data/StreamingAssets/xrmanager/entry.txt": b"manager",
        }
        loader = self.zip("renamed-pinned1.zip", loader_data.items())
        vhvr = self.zip("renamed-pinned2.zip", mod_data.items())
        data = []
        for key, file in (("loader", loader), ("vhvr", vhvr)):
            required = (["winhttp.dll", "doorstop_config.ini",
                         "BepInEx/config/BepInEx.cfg",
                         "BepInEx/core/BepInEx.dll",
                         "BepInEx/core/BepInEx.Preloader.dll"]
                        if key == "loader" else
                        ["BepInEx/plugins/ValheimVRMod.dll",
                         "valheim_Data/Managed/SteamVR.dll",
                         "valheim_Data/Managed/Unity.XR.OpenVR.dll",
                         "valheim_Data/Unity.XR.Management.dll"])
            if key == "vhvr":
                required = ["BepInEx/plugins/ValheimVRMod.dll"]
            data.append({"id": key, "name": key,
                         "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                         "required_files": required})
        recipe = {"id": "valheim", "name": "Valheim", "steam_appid": 42,
                  "method": "bepinex", "packages": data}
        return recipe, [loader, vhvr]

    def test_pak_read_only_manifest_names_exact_destination(self):
        self.file("Content/Paks/starter.pak", b"existing game mod")
        archive = self.library / "starter.pak"
        archive.write_bytes(b"new selected pak")
        before = (self.game / "Content/Paks/starter.pak").read_bytes()
        snapshot = self.statefile.read_bytes()
        plan = review.build_install_plan(self.pak_recipe(), [archive])
        self.assertTrue(plan.approved_for_review)
        self.assertEqual(plan.overwrites, 1)
        self.assertEqual(plan.new_files, 0)
        self.assertEqual(plan.backup_bytes, len(before))
        self.assertIn("Persistent", plan.backup_policy)
        self.assertEqual(plan.target_rows[0].relative, "Content/Paks/starter.pak")
        self.assertEqual(plan.target_rows[0].current_sha256,
                         hashlib.sha256(before).hexdigest())
        self.assertEqual((self.game / "Content/Paks/starter.pak").read_bytes(), before)
        self.assertEqual(self.statefile.read_bytes(), snapshot)
        self.assertFalse((self.statefile.parent / "backups").exists())

    def test_pak_new_file_and_full_revalidation(self):
        self.file("Content/Paks/anchor.pak")
        p = self.library / "fresh.pak"
        p.write_bytes(b"pinned? no but chosen manually")
        plan = review.build_install_plan(self.pak_recipe(), [p])
        self.assertEqual(plan.new_files, 1)
        self.assertEqual(plan.overwrites, 0)
        self.assertEqual(plan.archive_sha256[0], hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(review.revalidate(plan, self.pak_recipe()).fingerprint,
                         plan.fingerprint)

    def test_pak_stale_existing_original_rejected_before_install(self):
        original = self.file("Content/Paks/mod.pak", b"old")
        archive = self.library / "mod.pak"
        archive.write_bytes(b"new")
        p = review.build_install_plan(self.pak_recipe(), [archive])
        original.write_bytes(b"changed after review")
        with self.assertRaisesRegex(review.PlanRejected, "changed after review"):
            review.revalidate(p, self.pak_recipe())
        self.assertEqual(original.read_bytes(), b"changed after review")

    def test_modified_archive_rejected_after_review(self):
        self.file("Content/Paks/anchor.pak")
        archive = self.library / "new.pak"
        archive.write_bytes(b"version one")
        p = review.build_install_plan(self.pak_recipe(), [archive])
        archive.write_bytes(b"version two")
        with self.assertRaisesRegex(review.PlanRejected, "changed after review"):
            review.revalidate(p, self.pak_recipe())

    def test_game_root_add_only_is_previewable_without_writing(self):
        archive = self.make_cyber()
        before = sorted(x.relative_to(self.game) for x in self.game.rglob("*"))
        plan = review.build_install_plan(self.gameroot_recipe(), [archive])
        self.assertTrue(plan.approved_for_review)
        self.assertEqual(plan.new_files, 2)
        self.assertEqual(plan.overwrites, 0)
        self.assertIn("Persistent", plan.backup_policy)
        self.assertEqual(sorted(x.relative for x in plan.target_rows),
                         ["bin/x64/plugins/test.dll", "r6/scripts/cet.reds"])
        self.assertEqual(
            sorted(x.relative_to(self.game) for x in self.game.rglob("*")), before)
        self.assertFalse((self.statefile.parent / "transactions").exists())

    def test_game_root_existing_replacement_has_persistent_backup_policy(self):
        archive = self.make_cyber()
        self.file("bin/x64/plugins/test.dll", b"protected original")
        plan = review.build_install_plan(self.gameroot_recipe(), [archive])
        self.assertTrue(plan.approved_for_review)
        self.assertEqual(plan.overwrites, 1)
        self.assertEqual(plan.backup_bytes, len(b"protected original"))
        self.assertIn("Persistent", plan.backup_policy)
        self.assertIn("checksum", plan.backup_policy.lower())
        self.assertEqual((self.game / "bin/x64/plugins/test.dll").read_bytes(),
                         b"protected original")
        self.assertEqual(review.revalidate(plan, self.gameroot_recipe()).fingerprint,
                         plan.fingerprint)

    def test_pre_existing_legacy_cyberpunk_record_blocks_new_install(self):
        archive = self.make_cyber()
        original = self.file("bin/x64/plugins/test.dll", b"protected original")
        self.statefile.write_text(json.dumps({"cyberpunk-2077": {
            "keep": str(self.game), "files": [str(original)],
            "components": {"107": {"files": [str(original)]}}
        }}))
        plan = review.build_install_plan(self.gameroot_recipe(), [archive])
        self.assertFalse(plan.approved_for_review)
        self.assertIn("Legacy", " ".join(plan.blocked))
        self.assertEqual(plan.overwrites, 1)
        self.assertIn("Persistent", plan.backup_policy)
        self.assertEqual(original.read_bytes(), b"protected original")

    def test_cyberpunk_later_stage_is_blocked_even_without_existing_targets(self):
        later = self.zip("CyberpunkVR Port-30093-v0.zip", [
            ("bin/x64/plugins/later.dll", b"phase two")])
        plan = review.build_install_plan(self.gameroot_recipe(), [later])
        self.assertFalse(plan.approved_for_review)
        self.assertIn("later-stage", " ".join(plan.blocked))
        self.assertEqual(plan.new_files, 1)

    def test_symlink_target_is_rejected(self):
        self.file("Content/Paks/anchor.pak")
        outside = self.root / "user-private.pak"
        outside.write_bytes(b"keep")
        (self.game / "Content/Paks/evil.pak").symlink_to(outside)
        archive = self.library / "evil.pak"
        archive.write_bytes(b"bad")
        with self.assertRaises(review.PlanRejected):
            review.build_install_plan(self.pak_recipe(), [archive])
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_duplicate_pak_basename_blocked(self):
        self.file("Content/Paks/anchor.pak")
        archive = self.zip("twice.zip", [("a/a.pak", b"one"),
                                         ("b/A.pak", b"two")])
        with self.assertRaisesRegex(review.PlanRejected, "unique"):
            review.build_install_plan(self.pak_recipe(), [archive])

    def test_zip_traversal_rejected_before_staging(self):
        archive = self.zip("Unsafe Mod-107.zip", [("../escape.txt", b"evil"),
                                                   ("bin/x64/plugins/test.dll", b"good")])
        with self.assertRaisesRegex(review.PlanRejected, "Unsafe ZIP path"):
            review.build_install_plan(self.gameroot_recipe(), [archive])
        self.assertFalse((self.root / "escape.txt").exists())

    def test_zip_symlink_and_zipbomb_metadata_rejected(self):
        import stat
        archive = self.zip("Test-107.zip", [("bin/x64/plugins/test.dll", b"dll")])
        with zipfile.ZipFile(archive, "a") as z:
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "../outside")
        with self.assertRaisesRegex(review.PlanRejected, "entry type"):
            review.build_install_plan(self.gameroot_recipe(), [archive])

    def test_pinned_requires_all_releases_and_tracks_target(self):
        recipe, packs = self.pinned()
        with self.assertRaisesRegex(review.PlanRejected, "every required pinned"):
            review.build_install_plan(recipe, packs[:1])
        p = review.build_install_plan(recipe, list(reversed(packs)))
        self.assertTrue(p.approved_for_review)
        self.assertEqual(p.package_labels, ("loader", "vhvr"))
        self.assertEqual(p.overwrites, 0)
        self.assertGreaterEqual(p.new_files, 10)
        self.assertIn("retained", " ".join(p.notes))
        self.assertEqual(review.revalidate(p, recipe).fingerprint, p.fingerprint)
        self.assertFalse((self.statefile.parent / "backups").exists())

    def test_pinned_prior_install_state_blocks_replacement(self):
        recipe, packs = self.pinned()
        self.statefile.write_text(json.dumps({"valheim": {"installer": "vhvr-1"}}))
        with self.assertRaisesRegex(review.PlanRejected, "already has an installation"):
            review.build_install_plan(recipe, packs)

    def test_pinned_unrelated_zip_rejected_without_game_changes(self):
        recipe, packs = self.pinned()
        bogus = self.zip("unrelated.zip", [("a", b"untrusted")])
        before = list(self.game.rglob("*"))
        with self.assertRaisesRegex(review.PlanRejected, "not a recognized pinned"):
            review.build_install_plan(recipe, [packs[0], bogus])
        self.assertEqual(before, list(self.game.rglob("*")))

    def test_guide_and_uevr_methods_cannot_use_unsupported_installer(self):
        for method in ("guide", "uevr"):
            with self.subTest(method=method):
                recipe = {"id": "example", "name": "Example",
                          "steam_appid": 42, "method": method}
                archive = self.library / "package.zip"
                archive.write_bytes(b"data")
                with self.assertRaisesRegex(review.PlanRejected, "not yet supported"):
                    review.build_install_plan(recipe, [archive])

    def test_revalidation_refuses_game_switch(self):
        self.file("Content/Paks/anchor.pak")
        archive = self.library / "new.pak"
        archive.write_bytes(b"selected")
        plan = review.build_install_plan(self.pak_recipe(), [archive])
        with self.assertRaisesRegex(review.PlanRejected, "Selected game changed"):
            review.revalidate(plan, {"id": "other", "name": "Other"})

    def test_choosing_archive_from_game_tree_is_rejected(self):
        self.file("Content/Paks/anchor.pak")
        archive = self.file("Content/Paks/source.pak", b"mod copied in game")
        with self.assertRaisesRegex(review.PlanRejected, "inside the live game"):
            review.build_install_plan(self.pak_recipe(), [archive])


if __name__ == "__main__":
    unittest.main()
