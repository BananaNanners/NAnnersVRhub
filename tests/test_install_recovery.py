# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regressions for original-file ownership and failed state commits."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from vrhub import hub, pak, self_install


class InstallRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "game"
        self.paks = self.game / "Content/Paks"
        self.paks.mkdir(parents=True)
        self.state = self.root / "state/state.json"
        self.state.parent.mkdir()
        self.before = b'{"other-game": {"files": []}}\n'
        self.state.write_bytes(self.before)
        for patcher in (mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.state)}),
                        mock.patch.object(hub, "find_game", return_value=self.game)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.recipe = {"id": "ready-or-not", "name": "Ready or Not", "steam_appid": 1144200,
                       "files": [{"kind": "pak", "dest": "Content/Paks"}]}
        self.gameroot = {"id": "cp", "name": "CP", "steam_appid": 1,
                         "method": "gameroot", "root_dirs": ["bin"]}

    def archive(self, entries, name="mod.zip"):
        path = self.root / name
        with zipfile.ZipFile(path, "w") as z:
            for filename, content in entries:
                z.writestr(filename, content)
        return path

    def gamefile(self, name, data=b"original"):
        path = self.game / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_direct_pak_restores_original_and_retains_unrelated_state(self):
        original = self.gamefile("Content/Paks/mod.pak")
        mod = self.root / "mod.pak"
        mod.write_bytes(b"replacement")
        hub.install(self.recipe, mod)
        self.assertEqual(original.read_bytes(), b"replacement")
        record = hub.state()[self.recipe["id"]]
        self.assertEqual((Path(record["backup"]) / "files/mod.pak").read_bytes(), b"original")
        hub.uninstall(self.recipe["id"])
        self.assertEqual(original.read_bytes(), b"original")
        self.assertEqual(hub.state(), json.loads(self.before))

    def test_zip_restores_existing_and_removes_only_new_paks(self):
        old = self.gamefile("Content/Paks/old.pak")
        unrelated = self.gamefile("Content/Paks/unrelated.pak", b"keep")
        mod = self.archive([("wrapper/old.pak", b"new"), ("wrapper\\added.pak", b"added")])
        hub.install(self.recipe, mod)
        self.assertEqual((self.paks / "added.pak").read_bytes(), b"added")
        hub.uninstall(self.recipe["id"])
        self.assertEqual(old.read_bytes(), b"original")
        self.assertFalse((self.paks / "added.pak").exists())
        self.assertEqual(unrelated.read_bytes(), b"keep")

    def test_pak_reinstall_refuses_to_discard_original_backup(self):
        self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new")])
        hub.install(self.recipe, mod)
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "already recorded"):
            hub.install(self.recipe, mod)
        self.assertEqual(self.state.read_bytes(), before)
        hub.uninstall(self.recipe["id"])
        self.assertEqual((self.paks / "mod.pak").read_bytes(), b"original")

    def test_legacy_pak_record_also_requires_removal_before_install(self):
        self.state.write_text(json.dumps({self.recipe["id"]: {"files": []}}))
        mod = self.archive([("mod.pak", b"new")])
        with self.assertRaisesRegex(RuntimeError, "already recorded"):
            hub.install(self.recipe, mod)
        self.assertFalse((self.paks / "mod.pak").exists())

    def test_duplicate_zip_basenames_rejected_before_game_changes(self):
        old = self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("a/mod.pak", b"a"), ("b/MOD.pak", b"b")])
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            hub.install(self.recipe, mod)
        self.assertEqual(old.read_bytes(), b"original")
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_symlink_target_is_not_overwritten(self):
        outside = self.root / "outside.pak"
        outside.write_bytes(b"keep")
        (self.paks / "mod.pak").symlink_to(outside)
        mod = self.archive([("mod.pak", b"new")])
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            hub.install(self.recipe, mod)
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_pak_failed_commit_restores_original_and_removes_new_file(self):
        old = self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new"), ("added.pak", b"added")])
        with mock.patch.object(hub, "_save_state", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                hub.install(self.recipe, mod)
        self.assertEqual(old.read_bytes(), b"original")
        self.assertFalse((self.paks / "added.pak").exists())
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_pak_partial_copy_is_rolled_back(self):
        old = self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new")])
        copy = pak.shutil.copy2
        failed = False

        def fail_once(src, dst, *args, **kwargs):
            nonlocal failed
            if Path(dst) == old and not failed:
                failed = True
                old.write_bytes(b"partial")
                raise OSError("copy failed")
            return copy(src, dst, *args, **kwargs)

        with mock.patch.object(pak.shutil, "copy2", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "copy failed"):
                hub.install(self.recipe, mod)
        self.assertEqual(old.read_bytes(), b"original")
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_pak_changed_file_or_backup_blocks_removal(self):
        old = self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new")])
        hub.install(self.recipe, mod)
        before = self.state.read_bytes()
        old.write_bytes(b"user changes")
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            hub.uninstall(self.recipe["id"])
        self.assertEqual(old.read_bytes(), b"user changes")
        old.write_bytes(b"new")
        record = hub.state()[self.recipe["id"]]
        (Path(record["backup"]) / "files/mod.pak").write_bytes(b"bad backup")
        with self.assertRaisesRegex(RuntimeError, "backup is missing or changed"):
            hub.uninstall(self.recipe["id"])
        self.assertEqual(old.read_bytes(), b"new")
        self.assertEqual(self.state.read_bytes(), before)

    def test_pak_uninstall_commit_failure_restores_installed_files(self):
        old = self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new"), ("added.pak", b"added")])
        hub.install(self.recipe, mod)
        before = self.state.read_bytes()
        with mock.patch.object(hub, "_save_state", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                hub.uninstall(self.recipe["id"])
        self.assertEqual(old.read_bytes(), b"new")
        self.assertEqual((self.paks / "added.pak").read_bytes(), b"added")
        self.assertEqual(self.state.read_bytes(), before)
        hub.uninstall(self.recipe["id"])
        self.assertEqual(old.read_bytes(), b"original")

    def test_pak_failed_rollback_preserves_original_for_manual_recovery(self):
        self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new")])
        copy = pak.shutil.copy2

        def fail_restore(src, dst, *args, **kwargs):
            if Path(src).parent.name == "files":
                raise OSError("restore failed")
            return copy(src, dst, *args, **kwargs)

        with mock.patch.object(hub, "_save_state", side_effect=OSError("disk full")), \
                mock.patch.object(pak.shutil, "copy2", side_effect=fail_restore):
            with self.assertRaisesRegex(RuntimeError, "Recovery files preserved"):
                hub.install(self.recipe, mod)
        copies = list((self.state.parent / "backups").rglob("files/mod.pak"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), b"original")
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_missing_original_pak_backup_blocks_uninstall(self):
        old = self.gamefile("Content/Paks/mod.pak")
        mod = self.archive([("mod.pak", b"new")])
        hub.install(self.recipe, mod)
        before = self.state.read_bytes()
        entry = hub.state()[self.recipe["id"]]
        (Path(entry["backup"]) / "files/mod.pak").unlink()
        with self.assertRaisesRegex(RuntimeError, "backup is missing or changed"):
            hub.uninstall(self.recipe["id"])
        self.assertEqual(old.read_bytes(), b"new")
        self.assertEqual(self.state.read_bytes(), before)

    def test_gameroot_commit_failure_rolls_back_game_and_preserves_record(self):
        old = self.gamefile("bin/test.dll")
        mod = self.archive([("bin/test.dll", b"new"), ("bin/added.dll", b"added")])
        with mock.patch.object(hub, "_save_state", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                hub.install(self.gameroot, mod)
        self.assertEqual(old.read_bytes(), b"original")
        self.assertFalse((self.game / "bin/added.dll").exists())
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_gameroot_backups_exist_at_commit_and_clean_up_after_success(self):
        old = self.gamefile("bin/test.dll")
        mod = self.archive([("bin/test.dll", b"new")])
        save = hub._save_state

        def check_and_commit(state):
            copies = list((self.state.parent / "transactions").rglob("backup/bin/test.dll"))
            self.assertEqual(len(copies), 1)
            self.assertEqual(copies[0].read_bytes(), b"original")
            save(state)

        with mock.patch.object(hub, "_save_state", side_effect=check_and_commit):
            hub.install(self.gameroot, mod)
        self.assertEqual(old.read_bytes(), b"new")
        self.assertFalse(list((self.state.parent / "transactions").rglob("test.dll")))

    def test_gameroot_failed_rollback_retains_original_backup(self):
        self.gamefile("bin/test.dll")
        mod = self.archive([("bin/test.dll", b"new")])
        copy = hub.shutil.copy2

        def fail_restore(src, dst, *args, **kwargs):
            if "backup" in Path(src).parts:
                raise OSError("restore failed")
            return copy(src, dst, *args, **kwargs)

        with mock.patch.object(hub, "_save_state", side_effect=OSError("disk full")), \
                mock.patch.object(hub.shutil, "copy2", side_effect=fail_restore):
            with self.assertRaisesRegex(RuntimeError, "Recovery files preserved"):
                hub.install(self.gameroot, mod)
        copies = list((self.state.parent / "transactions").rglob("backup/bin/test.dll"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), b"original")
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_atomic_state_replace_failure_preserves_existing_json(self):
        with mock.patch.object(self_install.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                hub._save_state({"new": {}})
        self.assertEqual(self.state.read_bytes(), self.before)
        self.assertFalse(list(self.state.parent.glob(".state.json-*")))

    def test_real_state_replace_failure_rolls_back_gameroot(self):
        old = self.gamefile("bin/test.dll")
        mod = self.archive([("bin/test.dll", b"new")])
        with mock.patch.object(self_install.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                hub.install(self.gameroot, mod)
        self.assertEqual(old.read_bytes(), b"original")
        self.assertEqual(self.state.read_bytes(), self.before)

    def test_corrupt_state_does_not_allow_game_changes(self):
        old = self.gamefile("bin/test.dll")
        self.state.write_bytes(b"{broken")
        mod = self.archive([("bin/test.dll", b"new")])
        with self.assertRaises(json.JSONDecodeError):
            hub.install(self.gameroot, mod)
        self.assertEqual(old.read_bytes(), b"original")
        self.assertEqual(self.state.read_bytes(), b"{broken")
