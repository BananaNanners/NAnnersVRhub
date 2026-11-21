# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C2 persistent Cyberpunk originals and safe restoring — temp files only."""
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import hub


def sha(data):
    return hashlib.sha256(data).hexdigest()


class GamerootPersistentBackupsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nanners-gameroot-dev5c2-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.hubdir = self.root / "hubstate"
        self.hubdir.mkdir()
        self.state = self.hubdir / "state.json"
        self.initial = '{"other-game": {"files": []}}\n'
        self.state.write_text(self.initial)
        self.recipe = {
            "id": "cyberpunk-2077", "name": "Cyberpunk 2077", "steam_appid": 1091500,
            "method": "gameroot", "root_dirs": ["bin", "r6"],
            "components": [
                {"name": "Cyber Engine Tweaks", "nexus_mod": 107, "phase": 1,
                 "required_files": ["bin/x64/plugins/replace.dll"]},
            ],
        }
        for patcher in (
            mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.state)}),
            mock.patch.object(hub, "find_game", return_value=self.game),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def file(self, rel, data=b"original"):
        path = self.game / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def archive(self, entries=None, name="CET-107-1-0.zip"):
        path = self.root / name
        with zipfile.ZipFile(path, "w") as z:
            for filename, payload in (entries or [
                ("bin/x64/plugins/replace.dll", b"new replacement"),
                ("r6/scripts/addon.reds", b"added"),
            ]):
                z.writestr(filename, payload)
        return path

    def install(self, source=None):
        return hub.install_many(self.recipe, [source or self.archive()])

    def installed_record(self):
        return hub.state()["cyberpunk-2077"]

    def test_success_retains_originals_with_exact_checksums_and_restores(self):
        original = self.file("bin/x64/plugins/replace.dll", b"my existing DLL")
        unrelated = self.file("r6/unrelated.ini", b"leave untouched")
        archive = self.archive()
        paths = self.install(archive)
        self.assertEqual(len(paths), 2)
        self.assertEqual(original.read_bytes(), b"new replacement")
        added = self.game / "r6/scripts/addon.reds"
        self.assertEqual(added.read_bytes(), b"added")
        record = self.installed_record()
        self.assertEqual(record["installer"], "gameroot-2")
        self.assertEqual(record["keep"], str(self.game))
        self.assertEqual(record["originals"]["bin/x64/plugins/replace.dll"]["sha256"],
                         sha(b"my existing DLL"))
        self.assertEqual(record["installed_sha256"]["bin/x64/plugins/replace.dll"],
                         sha(b"new replacement"))
        self.assertIsNone(record["originals"]["r6/scripts/addon.reds"])
        retained = Path(record["backup"])
        self.assertEqual((retained / "files/bin/x64/plugins/replace.dll").read_bytes(),
                         b"my existing DLL")
        self.assertFalse(list((self.hubdir / "transactions").rglob("backup/replace.dll")))
        self.assertEqual(unrelated.read_bytes(), b"leave untouched")
        paths = hub.uninstall("cyberpunk-2077")
        self.assertEqual(len(paths), 2)
        self.assertEqual(original.read_bytes(), b"my existing DLL")
        self.assertFalse(added.exists())
        self.assertEqual(unrelated.read_bytes(), b"leave untouched")
        self.assertNotIn("cyberpunk-2077", hub.state())
        self.assertIn("other-game", hub.state())
        # Leave originals as a manual recovery safety net.
        self.assertEqual((retained / "files/bin/x64/plugins/replace.dll").read_bytes(),
                         b"my existing DLL")

    def test_new_files_only_also_has_valid_record_and_can_restore(self):
        self.file("r6/unrelated.ini", b"unrelated")
        archive = self.archive()
        self.install(archive)
        record = self.installed_record()
        self.assertEqual(set(record["originals"]),
                         {"bin/x64/plugins/replace.dll", "r6/scripts/addon.reds"})
        self.assertTrue(all(value is None for value in record["originals"].values()))
        self.assertTrue(Path(record["backup"]).is_dir())
        hub.uninstall("cyberpunk-2077")
        self.assertFalse((self.game / "bin/x64/plugins/replace.dll").exists())
        self.assertFalse((self.game / "r6/scripts/addon.reds").exists())
        self.assertEqual((self.game / "r6/unrelated.ini").read_bytes(), b"unrelated")

    def test_changed_installed_file_blocks_any_restoration(self):
        original = self.file("bin/x64/plugins/replace.dll", b"original")
        self.install()
        added = self.game / "r6/scripts/addon.reds"
        added.write_bytes(b"personal modifications")
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "changed since install"):
            hub.uninstall("cyberpunk-2077")
        self.assertEqual(original.read_bytes(), b"new replacement")
        self.assertEqual(added.read_bytes(), b"personal modifications")
        self.assertEqual(self.state.read_bytes(), before)

    def test_missing_installed_file_blocks_restoration(self):
        original = self.file("bin/x64/plugins/replace.dll", b"original")
        self.install()
        added = self.game / "r6/scripts/addon.reds"
        added.unlink()
        with self.assertRaisesRegex(RuntimeError, "changed since install"):
            hub.uninstall("cyberpunk-2077")
        self.assertEqual(original.read_bytes(), b"new replacement")
        self.assertIn("cyberpunk-2077", hub.state())

    def test_modified_retained_backup_blocks_restoration(self):
        original = self.file("bin/x64/plugins/replace.dll", b"original")
        self.install()
        record = self.installed_record()
        retained_file = Path(record["backup"]) / "files/bin/x64/plugins/replace.dll"
        retained_file.write_bytes(b"tampered backup")
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Original backup missing or changed"):
            hub.uninstall("cyberpunk-2077")
        self.assertEqual(original.read_bytes(), b"new replacement")
        self.assertEqual(self.state.read_bytes(), before)

    def test_missing_backup_blocks_restoration(self):
        self.file("bin/x64/plugins/replace.dll", b"original")
        self.install()
        record = self.installed_record()
        (Path(record["backup"]) / "files/bin/x64/plugins/replace.dll").unlink()
        with self.assertRaisesRegex(RuntimeError, "Original backup missing or changed"):
            hub.uninstall("cyberpunk-2077")
        self.assertIn("cyberpunk-2077", hub.state())

    def test_legacy_inventory_is_preserved_and_never_auto_removed(self):
        original = self.file("bin/x64/plugins/replace.dll", b"valuable working mod")
        legacy = {
            "keep": str(self.game),
            "files": [str(original)],
            "components": {"107": {"files": [str(original)]}},
        }
        current = {"other-game": {"files": []}, "cyberpunk-2077": legacy}
        self.state.write_text(json.dumps(current))
        before = self.state.read_bytes()
        archive = self.archive()
        with self.assertRaisesRegex(RuntimeError, "already has a Hub installation record"):
            self.install(archive)
        with self.assertRaisesRegex(RuntimeError, "Legacy game-root"):
            hub.uninstall("cyberpunk-2077")
        self.assertEqual(original.read_bytes(), b"valuable working mod")
        self.assertEqual(self.state.read_bytes(), before)
        if (self.hubdir / "backups").exists():
            self.assertEqual(list((self.hubdir / "backups").iterdir()), [])

    def test_second_install_rejected_before_overwriting_first_backup(self):
        original = self.file("bin/x64/plugins/replace.dll", b"first original")
        archive = self.archive()
        self.install(archive)
        before = self.state.read_bytes()
        record = self.installed_record()
        saved = (Path(record["backup"]) / "files/bin/x64/plugins/replace.dll").read_bytes()
        with self.assertRaisesRegex(RuntimeError, "already has a Hub installation record"):
            self.install(archive)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(original.read_bytes(), b"new replacement")
        self.assertEqual((Path(record["backup"]) /
                          "files/bin/x64/plugins/replace.dll").read_bytes(), saved)

    def test_state_commit_failure_restores_original_and_erases_new_only(self):
        original = self.file("bin/x64/plugins/replace.dll", b"original")
        archive = self.archive()
        before = self.state.read_bytes()
        with mock.patch.object(hub, "_save_state", side_effect=OSError("commit failure")):
            with self.assertRaisesRegex(OSError, "commit failure"):
                self.install(archive)
        self.assertEqual(original.read_bytes(), b"original")
        self.assertFalse((self.game / "r6/scripts/addon.reds").exists())
        self.assertEqual(self.state.read_bytes(), before)
        self.assertFalse(list((self.hubdir / "backups").glob("*")))
        self.assertFalse(list((self.hubdir / "transactions").glob("*")))

    def test_persistent_link_failure_occurs_before_game_modification(self):
        original = self.file("bin/x64/plugins/replace.dll", b"my original")
        archive = self.archive()
        before = self.state.read_bytes()
        with mock.patch.object(hub.os, "link",
                               side_effect=OSError("cannot publish durable backup")):
            with self.assertRaisesRegex(OSError, "cannot publish durable backup"):
                self.install(archive)
        self.assertEqual(original.read_bytes(), b"my original")
        self.assertFalse((self.game / "r6/scripts/addon.reds").exists())
        self.assertEqual(self.state.read_bytes(), before)

    def test_game_copy_failure_restores_original(self):
        original = self.file("bin/x64/plugins/replace.dll", b"my original")
        archive = self.archive()
        real_copy = hub.shutil.copy2
        def fail_new(src, dst, *args, **kwargs):
            if Path(dst) == (self.game / "r6/scripts/addon.reds"):
                raise OSError("simulated second game-file copy failure")
            return real_copy(src, dst, *args, **kwargs)
        with mock.patch.object(hub.shutil, "copy2", side_effect=fail_new):
            with self.assertRaisesRegex(OSError, "second game-file copy failure"):
                self.install(archive)
        self.assertEqual(original.read_bytes(), b"my original")
        self.assertFalse((self.game / "r6/scripts/addon.reds").exists())
        self.assertNotIn("cyberpunk-2077", hub.state())

    def test_uninstall_state_commit_failure_restores_installed_bytes(self):
        original = self.file("bin/x64/plugins/replace.dll", b"original")
        self.install()
        before = self.state.read_bytes()
        with mock.patch.object(hub, "_save_state", side_effect=OSError("write fails")):
            with self.assertRaisesRegex(OSError, "write fails"):
                hub.uninstall("cyberpunk-2077")
        self.assertEqual(original.read_bytes(), b"new replacement")
        self.assertEqual((self.game / "r6/scripts/addon.reds").read_bytes(), b"added")
        self.assertEqual(self.state.read_bytes(), before)
        self.assertIn("cyberpunk-2077", hub.state())

    def test_uninstall_copy_failure_rolls_back_partial_restore(self):
        original = self.file("bin/x64/plugins/replace.dll", b"original")
        self.install()
        real_copy = hub.shutil.copy2
        failed = False
        def fail_original_restore(src,dst,*args,**kwargs):
            nonlocal failed
            if (not failed and "files" in Path(src).parts and
                    Path(dst) == original and
                    str(Path(src)).startswith(str(self.hubdir / "backups"))):
                failed=True
                raise OSError("restore original failed")
            return real_copy(src,dst,*args,**kwargs)
        with mock.patch.object(hub.shutil, "copy2", side_effect=fail_original_restore):
            with self.assertRaisesRegex(OSError, "restore original failed"):
                hub.uninstall("cyberpunk-2077")
        self.assertEqual(original.read_bytes(), b"new replacement")
        self.assertEqual((self.game / "r6/scripts/addon.reds").read_bytes(), b"added")
        self.assertIn("cyberpunk-2077", hub.state())

    def test_symlinked_destination_blocks_install_without_touching_outside(self):
        outside = self.root / "outside.dll"
        outside.write_bytes(b"outside untouched")
        path = self.game / "bin/x64/plugins/replace.dll"
        path.parent.mkdir(parents=True)
        path.symlink_to(outside)
        archive = self.archive()
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            self.install(archive)
        self.assertEqual(outside.read_bytes(), b"outside untouched")
        self.assertNotIn("cyberpunk-2077", hub.state())

    def test_symlinked_parent_blocks_install(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.game / "bin").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            self.install(self.archive())
        self.assertFalse((outside / "x64").exists())

    def test_malicious_duplicate_destinations_rejected(self):
        archive = self.archive([
            ("bin/x64/plugins/test.dll", b"first"),
            ("Bin/x64/plugins/TEST.dll", b"duplicate"),
        ])
        # Case-insensitive ZIP entries have been rejected by _zip_preflight.
        with self.assertRaisesRegex(RuntimeError, "duplicate|Duplicate"):
            self.install(archive)
        self.assertNotIn("cyberpunk-2077", hub.state())

    def test_archive_inside_live_game_directory_is_rejected(self):
        archive = self.archive()
        misplaced = self.game / archive.name
        misplaced.write_bytes(archive.read_bytes())
        with self.assertRaisesRegex(RuntimeError, "inside the live game tree"):
            self.install(misplaced)
        self.assertNotIn("cyberpunk-2077", hub.state())

    def test_symlinked_hub_backups_parent_is_rejected(self):
        external = self.root / "external-backups"
        external.mkdir()
        (self.hubdir / "backups").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "Unsafe symlink"):
            self.install(self.archive())
        self.assertNotIn("cyberpunk-2077", hub.state())
        self.assertEqual(list(external.iterdir()), [])

    def test_unreviewed_archive_format_rejected_before_game_changes(self):
        self.file("bin/x64/plugins/replace.dll", b"original")
        path = self.root / "CET-107-file.rar"
        path.write_bytes(b"not a ZIP")
        with self.assertRaisesRegex(RuntimeError, "requires a ZIP"):
            self.install(path)
        self.assertEqual((self.game / "bin/x64/plugins/replace.dll").read_bytes(),
                         b"original")

    def test_post_install_hashes_match_exact_bytes(self):
        self.file("bin/x64/plugins/replace.dll", b"old")
        self.install()
        entry = self.installed_record()
        self.assertEqual(len(entry["installed_sha256"]), 2)
        for relative, digest in entry["installed_sha256"].items():
            self.assertEqual(digest, sha((self.game / relative).read_bytes()))

if __name__ == "__main__":
    unittest.main()
