# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Isolated development recovery fixtures; no live game saves or cloud writes."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from vrhub import game_saves as saves, hub, self_install

FIXTURES = {
    "cyberpunk-2077": {"ManualSave-0/sav.dat": b"save", "ManualSave-0/metadata.9.json": b"{}"},
    "fatekeeper": {"Slot0.sav": b"save"},
    "ready-or-not": {"Player.sav": b"save"},
    "hogwarts-legacy": {"123/HL-00-00.sav": b"save"},
    "elden-ring": {"76561198000000000/ER0000.sl2": b"save"},
    "skyrim-vr-mgo": {"Save1.ess": b"save", "Save1.skse": b"cosave"},
    "valheim": {"Viking.fch": b"save", "Viking.fch.old": b"old"},
    "subnautica": {"gameinfo.json": b"{}", "global-objects.bin": b"save"},
    "doom-2016-gog": {"GAME-AUTOSAVE0/game.details": b"mapDesc=Resource Operations\ndate=1793338236\ngameVersion=1\n", "GAME-AUTOSAVE0/checkpoint.dat": b"save", "PROFILE/profile.bin": b"profile"},
}


def write(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return root


class SaveFixtures:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        patch = mock.patch.dict(os.environ, {saves.FLAG: "1", "VRHUB_STATE": str(self.home / "hub/state.json")})
        patch.start(); self.addCleanup(patch.stop)
        patch = mock.patch("pathlib.Path.home", return_value=self.home)
        patch.start(); self.addCleanup(patch.stop)
        self.recipes = hub.load_recipes()

    def backend(self, rid):
        return saves.GameSaves(self.recipes[rid])

    def pair(self, rid):
        source = write(self.home / rid / "source", FIXTURES[rid])
        target = write(self.home / rid / "target", {k: v + b"old" for k, v in FIXTURES[rid].items()})
        backend = self.backend(rid)
        backend.target = str(target)
        backend.manual_target = True
        return backend, source, target



class GameSavesTests(SaveFixtures, unittest.TestCase):
    def test_all_nine_adapters_restore_and_keep_originals(self):
        self.assertEqual(set(FIXTURES), set(self.recipes))
        for rid in FIXTURES:
            with self.subTest(rid=rid):
                backend, source, target = self.pair(rid)
                before = backend.snapshot(target)
                plan = backend.preview(source, target)
                with mock.patch.object(backend, "ensure_closed"):
                    result = backend.restore(plan)
                self.assertEqual(backend.snapshot(target)["fingerprint"], backend.snapshot(source)["fingerprint"])
                self.assertEqual(backend.snapshot(result["previous"])["fingerprint"], before["fingerprint"])
                self.assertTrue((Path(result["backup"]) / "restore.json").is_file())
                self.assertTrue(Path(result["backup"]).name.startswith(backend.backup_prefix))

    def test_date_explanation_matches_each_game(self):
        for rid in FIXTURES:
            with self.subTest(rid=rid):
                backend = self.backend(rid)
                with mock.patch.object(backend, "targets", return_value=[]), \
                     mock.patch.object(saves.doom_saves, "discover", return_value={"notes": [], "rows": []}):
                    report = backend.discover(backend.recipe)
                note = next(n for n in report["notes"] if n.startswith("Development recovery:"))
                self.assertEqual("DOOM" in note, rid == "doom-2016-gog")
                self.assertIn("game/mod compatibility are not verified", note)
                self.assertIn("disable cloud sync", note)
                if rid == "doom-2016-gog":
                    self.assertIn("save metadata", note)
                else:
                    self.assertIn("file modification times", note)
                    self.assertIn("do not confirm gameplay progress", note)

    def test_failed_scan_keeps_diagnostic_date_without_allowing_restore(self):
        backend = self.backend("fatekeeper")
        root = write(self.home / "unrecognized", {"notes.txt": b"not a save"})
        os.utime(root / "notes.txt", (1700000000, 1700000000))
        backend.target = str(root)
        with mock.patch.object(backend, "targets", return_value=[root]):
            row = backend.discover(backend.recipe)["rows"][0]
        self.assertFalse(row["usable"])
        self.assertTrue(row["current"])
        self.assertIn("No recognized", row["error"])
        self.assertEqual(row["file_modified_at"], saves.doom_saves._stamp(1700000000))
        self.assertEqual(row["observed_file_count"], 1)
        self.assertNotIn("fingerprint", row)
        self.assertNotIn("saved_at", row)
        self.assertFalse((self.home / "hub").exists())

    def test_empty_missing_and_denied_folder_explain_date_unavailable(self):
        root = self.home / "empty"; root.mkdir()
        result = saves.file_observations(root)
        self.assertIsNone(result["file_modified_at"])
        self.assertIn("No regular files", result["date_reason"])
        result = saves.file_observations(root / "missing")
        self.assertIsNone(result["file_modified_at"])
        self.assertTrue(result["date_reason"])
        with mock.patch.object(saves.os, "scandir", side_effect=PermissionError("permission denied")):
            result = saves.file_observations(root)
        self.assertIsNone(result["file_modified_at"])
        self.assertIn("permission denied", result["date_reason"])

    def test_stat_only_fallback_skips_links_and_reports_partial(self):
        root = write(self.home / "observed", {"file.txt": b"diagnostic"})
        elsewhere = write(self.home / "outside", {"secret.txt": b"not scanned"})
        (root / "link").symlink_to(elsewhere, target_is_directory=True)
        with mock.patch("pathlib.Path.open", side_effect=AssertionError("metadata fallback must not read file contents")):
            result = saves.file_observations(root)
        self.assertEqual(result["observed_file_count"], 1)
        self.assertTrue(result["observation_partial"])
        self.assertIn("Linked", result["date_reason"])

    def test_stat_fallback_limit_and_epoch_timestamp(self):
        root = write(self.home / "bounded", {"a": b"1", "b": b"2"})
        result = saves.file_observations(root, max_entries=1)
        self.assertTrue(result["observation_partial"])
        self.assertEqual(result["observed_file_count"], 1)
        single = write(self.home / "epoch", {"a": b"1"})
        os.utime(single / "a", (0, 0))
        self.assertEqual(saves.file_observations(single)["file_modified_at"], saves.doom_saves._stamp(0))

    def test_doom_missing_metadata_date_uses_checkpoint_mtime(self):
        backend, source, target = self.pair("doom-2016-gog")
        (source / "GAME-AUTOSAVE0/game.details").write_text("mapDesc=Resource Operations\ndate=invalid\ngameVersion=1\n")
        os.utime(source / "GAME-AUTOSAVE0/checkpoint.dat", (1700000000, 1700000000))
        row = backend.snapshot(source)
        self.assertEqual(row["saved_at"], saves.doom_saves._stamp(1700000000))
        self.assertEqual(row["date_source"], "Checkpoint file modification time")

    def test_hidden_unless_exact_opt_in(self):
        for value in ("", "0", "true", "yes"):
            with mock.patch.dict(os.environ, {saves.FLAG: value}):
                self.assertFalse(saves.enabled())
        self.assertTrue(saves.enabled())

    def test_explicit_session_restore_without_environment(self):
        backend, source, target = self.pair("fatekeeper")
        backend.development_enabled = True
        with mock.patch.dict(os.environ, {saves.FLAG: "0"}), mock.patch.object(backend, "ensure_closed"):
            backend.restore(backend.preview(source, target))
        self.assertEqual(backend.snapshot(source)["fingerprint"], backend.snapshot(target)["fingerprint"])

    def test_explicit_disabled_session_overrides_environment(self):
        backend, source, target = self.pair("fatekeeper")
        backend.development_enabled = False
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            backend.restore(backend.preview(source, target))
        self.assertFalse((self.home / "hub").exists())

    def test_disabled_restore_writes_nothing(self):
        backend, source, target = self.pair("subnautica")
        with mock.patch.dict(os.environ, {saves.FLAG: "0"}):
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                backend.restore(backend.preview(source, target))
        self.assertFalse((self.home / "hub").exists())

    def test_account_conversion_blocked(self):
        for rid in ("elden-ring", "hogwarts-legacy"):
            backend, source, target = self.pair(rid)
            account = next(source.iterdir())
            account.rename(source / "999")
            with self.assertRaisesRegex(RuntimeError, "account"):
                backend.preview(source, target)

    def test_characters_cannot_replace_worlds(self):
        backend, source, target = self.pair("valheim")
        world = write(self.home / "worlds", {"World.fwl": b"map", "World.db": b"database"})
        with self.assertRaisesRegex(RuntimeError, "Save type"):
            backend.preview(source, world)
        self.assertEqual(backend.snapshot(world)["component"], "worlds")
        (world / "World.db").unlink()
        with self.assertRaises(RuntimeError):
            backend.snapshot(world)

    def test_all_adapters_reject_wrong_folder_and_symlinks(self):
        for rid in FIXTURES:
            backend, source, target = self.pair(rid)
            junk = write(self.home / rid / "junk", {"readme.txt": b"not a save"})
            with self.assertRaises(RuntimeError):
                backend.snapshot(junk)
            (source / "linked").symlink_to(target)
            with self.assertRaises(RuntimeError):
                backend.snapshot(source)

    def test_prefix_wrapper_not_accepted_as_unreal_save_folder(self):
        backend = self.backend("fatekeeper")
        prefix = write(self.home / "wrapped-prefix", {"drive_c/users/steamuser/AppData/Local/SLASHER/Saved/SaveGames/Slot.sav": b"save"})
        with self.assertRaises(RuntimeError):
            backend.snapshot(prefix)

    def test_configs_are_not_accepted_as_save_roots(self):
        backend, source, target = self.pair("cyberpunk-2077")
        (source / "UserSettings.ini").write_text("graphics")
        with self.assertRaisesRegex(RuntimeError, "configuration"):
            backend.snapshot(source)

    def test_subnautica_slots_exclude_options(self):
        game = self.home / "game"
        base = game / "SNAppData/SavedGames"
        slot = write(base / "slot0000", FIXTURES["subnautica"])
        write(base / "options", {"options.bin": b"settings"})
        with mock.patch.object(hub, "game_path", return_value=game):
            self.assertEqual(self.backend("subnautica").targets(), [slot])

    def test_prefix_discovery_and_alias_dedup(self):
        for rid, layouts in saves.LAYOUTS.items():
            if not layouts:
                continue
            prefix = self.home / rid
            user = prefix / "drive_c/users/steamuser"
            for layout in layouts:
                write(user / layout, FIXTURES[rid])
            (user.parent / "alias").symlink_to(user, target_is_directory=True)
            self.assertEqual(len(self.backend(rid)._prefix_roots(prefix)), len(layouts))

    def test_discovery_read_only_and_backup_scope(self):
        backend, source, target = self.pair("subnautica")
        with mock.patch.object(backend, "targets", return_value=[target]):
            report = backend.discover(backend.recipe, [source])
        self.assertEqual(len(report["rows"]), 2)
        self.assertFalse((self.home / "hub").exists())
        self.assertTrue(next(r for r in report["rows"] if r["current"])["usable"])

    def test_stale_preview_blocked_before_backup(self):
        backend, source, target = self.pair("fatekeeper")
        plan = backend.preview(source, target)
        (source / "Slot0.sav").write_bytes(b"changed")
        with mock.patch.object(backend, "ensure_closed"), self.assertRaisesRegex(RuntimeError, "changed"):
            backend.restore(plan)
        self.assertFalse((self.home / "hub").exists())

    def test_launcher_target_change_blocks_restore(self):
        backend, source, target = self.pair("fatekeeper")
        backend.manual_target = False
        with mock.patch.object(backend, "ensure_closed"), mock.patch.object(backend, "targets", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "location changed"):
                backend.restore(backend.preview(source, target))
        self.assertFalse((self.home / "hub").exists())

    def test_failure_rolls_back_for_generic_adapter(self):
        backend, source, target = self.pair("fatekeeper")
        before = backend.snapshot(target)["fingerprint"]
        replace = os.replace
        def fail_replacement(src, dst):
            if Path(src).name == "replacement-savegame":
                raise OSError("injected rename failure")
            return replace(src, dst)
        with mock.patch.object(backend, "ensure_closed"), mock.patch("os.replace", side_effect=fail_replacement):
            with self.assertRaisesRegex(RuntimeError, "original target was restored"):
                backend.restore(backend.preview(source, target))
        self.assertEqual(backend.snapshot(target)["fingerprint"], before)

    def test_process_guard_blocks_launchers(self):
        for process in ("steam", "steamwebhelper", "heroic", "ModOrganizer.exe", "SLASHER-Win64", "UEVRInjector"):
            fake = self.home / process
            write(fake, {"comm": process.encode()})
            with mock.patch("pathlib.Path.glob", return_value=[fake]), self.assertRaisesRegex(RuntimeError, "Close games"):
                self.backend("fatekeeper").ensure_closed()

    def test_skyrim_cloud_metadata_is_preserved_but_not_used_for_date(self):
        backend, source, target = self.pair("skyrim-vr-mgo")
        (source / "steam_autocloud.vdf").write_text("source cloud metadata")
        (target / "steam_autocloud.vdf").write_text("target cloud metadata")
        os.utime(source / "Save1.ess", (1700000000, 1700000000))
        os.utime(source / "steam_autocloud.vdf", (1800000000, 1800000000))
        row = backend.snapshot(source)
        self.assertIn("steam_autocloud.vdf", row["files"])
        self.assertEqual(row["saved_at"], saves.doom_saves._stamp(1700000000))
        self.assertIn(".ess", row["date_source"])
        with mock.patch.object(backend, "ensure_closed"):
            result = backend.restore(backend.preview(source, target))
        self.assertEqual((target / "steam_autocloud.vdf").read_text(), "source cloud metadata")
        self.assertEqual((Path(result["previous"]) / "steam_autocloud.vdf").read_text(), "target cloud metadata")
        self.assertTrue((target / "Save1.skse").is_file())

    def test_skyrim_cloud_only_and_foreign_files_still_blocked(self):
        backend = self.backend("skyrim-vr-mgo")
        cloud = write(self.home / "cloud-only", {"steam_autocloud.vdf": b"metadata"})
        with self.assertRaises(RuntimeError):
            backend.snapshot(cloud)
        root = write(self.home / "foreign", {**FIXTURES[backend.rid], "other.vdf": b"unknown"})
        with self.assertRaises(RuntimeError):
            backend.snapshot(root)
        (root / "other.vdf").unlink()
        write(root, {"nested/steam_autocloud.vdf": b"wrong layout"})
        with self.assertRaises(RuntimeError):
            backend.snapshot(root)

    def test_skyrim_discovers_real_shortcut_prefix_without_proton_config(self):
        import struct
        backend = self.backend("skyrim-vr-mgo")
        mgo = self.home / "SkyrimVRMODMGO3.8"
        write(mgo, {"ModOrganizer.exe": b"fixture"})
        steam = self.home / ".local/share/Steam"
        appid = 4052365288
        z = lambda value: value.encode() + b"\0"
        data = b"\0shortcuts\0\0" + z("0")
        data += b"\x02" + z("appid") + struct.pack("<I", appid)
        data += b"\x01" + z("Exe") + z(str(mgo / "ModOrganizer.exe"))
        data += b"\x01" + z("AppName") + z("SkyrimVRMGO") + b"\x08\x08\x08"
        write(steam, {"userdata/123/config/shortcuts.vdf": data})
        suffix = "drive_c/users/steamuser/Documents/My Games/Skyrim VR/Saves"
        base = steam / "steamapps/compatdata/611670/pfx"
        shortcut = steam / f"steamapps/compatdata/{appid}/pfx"
        base_saves = write(base / suffix, {**FIXTURES[backend.rid], "steam_autocloud.vdf": b"metadata"})
        shortcut_saves = write(shortcut / suffix, FIXTURES[backend.rid])
        with mock.patch.object(hub, "_pfx", return_value=base):
            report = backend.discover(backend.recipe)
        self.assertIsNone(report["target"])
        self.assertEqual({r["root"] for r in report["rows"]}, {str(base_saves), str(shortcut_saves)})
        self.assertTrue(all(r["usable"] for r in report["rows"]))
        self.assertTrue(any("MO2 shortcut" in r.get("location_role", "") for r in report["rows"]))
        self.assertTrue(any("Base-game" in r.get("location_role", "") for r in report["rows"]))
        self.assertFalse((shortcut.parent / "config_info").exists())
        self.assertFalse((self.home / "hub").exists())

    def test_skyrim_profile_local_saves(self):
        backend = self.backend("skyrim-vr-mgo")
        mgo = self.home / "MGO"
        root = write(mgo / "profiles/Active/saves", FIXTURES[backend.rid])
        from vrhub.handlers import get_handler
        with mock.patch.object(hub, "_pfx", side_effect=RuntimeError("no base prefix")), \
             mock.patch.object(get_handler(backend.recipe), "_mgo_dir", return_value=mgo):
            self.assertEqual(backend.targets(), [root])


try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "Qt unavailable")
class GameSavesQtTests(SaveFixtures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hub_hidden_normally_and_all_nine_when_enabled(self):
        from vrhub.gui import HubWindow
        with mock.patch.object(HubWindow, "check_updates"), mock.patch.object(HubWindow, "scan_setup"), \
             mock.patch("vrhub.app_update_gui.HubUpdateController.startup"):
            window = HubWindow()
            try:
                # Inherited dev3 environment must no longer reveal the GUI button.
                for flag in ("0", "1"):
                    with mock.patch.dict(os.environ, {saves.FLAG: flag}):
                        for i in range(window.table.rowCount()):
                            window.table.selectRow(i); window.show_details()
                            self.assertTrue(window.doom_saves_btn.isHidden())
                window.development_tools_action.trigger()
                self.assertTrue(window.development_tools_action.isChecked())
                for i in range(window.table.rowCount()):
                    window.table.selectRow(i); window.show_details()
                    self.assertFalse(window.doom_saves_btn.isHidden())
                with mock.patch.dict(os.environ, {saves.FLAG: "0"}), mock.patch("vrhub.game_save_gui.GameSavesDialog") as dialog:
                    window.doom_saves_btn.click()
                    dialog.assert_called_once_with(window.current(), window, development_enabled=True)
                    dialog.return_value.exec.assert_called_once()
                window.development_tools_action.trigger()
                self.assertFalse(window.development_tools_action.isChecked())
                for i in range(window.table.rowCount()):
                    window.table.selectRow(i); window.show_details()
                    self.assertTrue(window.doom_saves_btn.isHidden())
                with mock.patch("vrhub.game_save_gui.GameSavesDialog") as dialog:
                    window.show_doom_saves()
                    dialog.assert_not_called()
            finally:
                window.close()
                window.deleteLater()
                self.app.processEvents()

    def test_generic_restore_worker_and_rescan(self):
        import time
        from vrhub.game_save_gui import GameSavesDialog
        backend, source, target = self.pair("fatekeeper")
        d = GameSavesDialog(backend.recipe, auto_scan=False)
        d.backend = backend
        d.extra_roots = [str(source)]
        with mock.patch.object(backend, "targets", return_value=[target]), mock.patch.object(backend, "ensure_closed"):
            d.scanned(backend.discover(backend.recipe, [source]))
            index = next(i for i,r in enumerate(d.report["rows"]) if r["root"] == str(source))
            d.table.selectRow(index)
            with mock.patch.object(d, "confirm_restore", return_value=True):
                d.restore_button.click()
            deadline = time.monotonic() + 10
            while d.worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(d.worker)
            self.assertIn("verification passed", d.result.text())
            self.assertEqual(backend.snapshot(source)["fingerprint"], backend.snapshot(target)["fingerprint"])
        d.close(); d.deleteLater(); self.app.processEvents()

    def test_menu_permission_opens_without_environment_flag(self):
        from vrhub.game_save_gui import GameSavesDialog
        with mock.patch.dict(os.environ, {saves.FLAG: "0"}):
            d = GameSavesDialog(self.recipes["fatekeeper"], auto_scan=False, development_enabled=True)
            self.assertTrue(d.backend.development_enabled)
            d.close(); d.deleteLater(); self.app.processEvents()

    def test_menu_permission_resets_for_new_window(self):
        from vrhub.gui import HubWindow
        with mock.patch.object(HubWindow, "check_updates"), mock.patch.object(HubWindow, "scan_setup"), \
             mock.patch("vrhub.app_update_gui.HubUpdateController.startup"):
            first = HubWindow()
            first.development_tools_action.trigger()
            self.assertTrue(first.development_tools_enabled)
            first.close(); first.deleteLater(); self.app.processEvents()
            second = HubWindow()
            self.assertFalse(second.development_tools_enabled)
            self.assertFalse(second.development_tools_action.isChecked())
            self.assertTrue(second.doom_saves_btn.isHidden())
            second.close(); second.deleteLater(); self.app.processEvents()

    def test_invalid_current_row_displays_error_date_and_blocks_restore(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend = self.backend("fatekeeper")
        root = write(self.home / "invalid-current", {"notes.txt": b"not save data"})
        backend.target = str(root)
        with mock.patch.object(backend, "targets", return_value=[root]):
            report = backend.discover(backend.recipe)
        d = GameSavesDialog(backend.recipe, auto_scan=False, development_enabled=True)
        d.scanned(report)
        self.assertIn("Current target — restore blocked", d.table.item(0, 5).text())
        self.assertIn("folder files", d.table.item(0, 2).text())
        self.assertIn("No recognized", d.status.text())
        self.assertIn("SCAN ISSUES", d.details.toPlainText())
        self.assertFalse(d.restore_button.isEnabled())
        d.table.selectRow(0)
        self.assertIn("not validated save data", d.details.toPlainText())
        self.assertIsNone(d.plan)
        d.close(); d.deleteLater(); self.app.processEvents()

    def test_empty_current_row_explains_date_without_selection(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend = self.backend("fatekeeper")
        root = self.home / "empty-current"; root.mkdir(); backend.target = str(root)
        with mock.patch.object(backend, "targets", return_value=[root]):
            report = backend.discover(backend.recipe)
        d = GameSavesDialog(backend.recipe, auto_scan=False, development_enabled=True)
        d.scanned(report)
        self.assertEqual(d.table.item(0, 2).text(), "Date unavailable")
        self.assertIn("No regular files", d.details.toPlainText())
        self.assertFalse(d.restore_button.isEnabled())
        d.close(); d.deleteLater(); self.app.processEvents()

    def test_hidden_handler_cannot_be_invoked(self):
        from vrhub.game_save_gui import GameSavesDialog
        with mock.patch.dict(os.environ, {saves.FLAG: "0"}), self.assertRaisesRegex(RuntimeError, "Enable development"):
            GameSavesDialog(self.recipes["fatekeeper"], auto_scan=False)

    def test_target_selection_and_type_guard(self):
        from vrhub.game_save_gui import GameSavesDialog
        backend, source, target = self.pair("valheim")
        d = GameSavesDialog(backend.recipe, auto_scan=False)
        d.backend = backend
        with mock.patch.object(backend, "targets", return_value=[target]):
            report = backend.discover(backend.recipe, [source])
        d.scanned(report)
        self.assertEqual(d.target_combo.currentData(), str(target))
        self.assertFalse(d.restore_button.isEnabled())
        source_index = next(i for i,r in enumerate(report["rows"]) if r["root"] == str(source))
        d.table.selectRow(source_index)
        self.assertTrue(d.restore_button.isEnabled())
        self.assertIn(str(target), d.target_details.toPlainText())
        d.close()
        d.deleteLater()
        self.app.processEvents()
