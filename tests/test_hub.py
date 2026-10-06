import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import hub


class Hub030Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.state = self.root / "state.json"
        self.env = mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.state)})
        self.env.start()
        self.find = mock.patch.object(hub, "find_game", return_value=self.game)
        self.find.start()

    def tearDown(self):
        self.find.stop()
        self.env.stop()
        self.tmp.cleanup()

    def make_zip(self, name, entries):
        p = self.root / name
        with zipfile.ZipFile(p, "w") as z:
            for arcname, data in entries:
                z.writestr(arcname, data)
        return p

    def test_windows_backslash_zip_installs_nested_files(self):
        z = self.make_zip("CyberpunkVRPort-30093.zip", [
            ("red4ext\\plugins\\", b""),
            ("red4ext\\plugins\\CyberpunkVR_Stereo\\CyberpunkVR_Stereo.dll", b"dll"),
            ("bin\\x64\\example.ini", b"setting=1"),
        ])
        recipe = {
            "id": "cp",
            "name": "CP",
            "steam_appid": 1,
            "method": "gameroot",
            "components": [{
                "nexus_mod": 30093,
                "name": "CyberpunkVR Port",
                "phase": 2,
                "required_files": ["red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll"],
            }],
        }
        out = hub.install_many(recipe, [z])
        self.assertEqual(len(out), 2)
        self.assertEqual((self.game / "red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll").read_bytes(), b"dll")
        state = json.loads(self.state.read_text())
        self.assertEqual(len(state["cp"]["components"]["30093"]["files"]), 2)

    def test_required_component_file_rejects_incomplete_archive(self):
        z = self.make_zip("CyberpunkVRPort-30093.zip", [("bin\\x64\\only.ini", b"x")])
        recipe = {
            "id": "cp", "name": "CP", "steam_appid": 1, "method": "gameroot",
            "components": [{"nexus_mod": 30093, "name": "CyberpunkVR Port",
                            "required_files": ["red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll"]}],
        }
        with self.assertRaisesRegex(RuntimeError, "Required file"):
            hub.install_many(recipe, [z])
        self.assertFalse(self.state.exists())

    def test_transaction_rolls_back_overwritten_files(self):
        (self.game / "bin/x64").mkdir(parents=True)
        a = self.game / "bin/x64/a.txt"
        b = self.game / "bin/x64/b.txt"
        a.write_text("old-a")
        b.write_text("old-b")
        z = self.make_zip("mod.zip", [("bin/x64/a.txt", b"new-a"), ("bin/x64/b.txt", b"new-b")])
        recipe = {"id": "game", "name": "Game", "steam_appid": 1, "method": "gameroot", "root_dirs": ["bin"]}

        real_copy2 = hub.shutil.copy2
        failed = {"done": False}

        def flaky(src, dst, *args, **kwargs):
            dstp = Path(dst)
            if dstp == b.resolve() and not failed["done"]:
                failed["done"] = True
                raise OSError("simulated disk failure")
            return real_copy2(src, dst, *args, **kwargs)

        with mock.patch.object(hub.shutil, "copy2", side_effect=flaky):
            with self.assertRaisesRegex(OSError, "simulated"):
                hub.install_many(recipe, [z])

        self.assertEqual(a.read_text(), "old-a")
        self.assertEqual(b.read_text(), "old-b")
        self.assertFalse(self.state.exists())

    def test_verify_checks_required_sentinel(self):
        required = self.game / "red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll"
        recorded = self.game / "bin/x64/example.ini"
        recorded.parent.mkdir(parents=True)
        recorded.write_text("x")
        self.state.write_text(json.dumps({
            "cp": {"keep": str(self.game), "components": {"30093": {"files": [str(recorded)]}}}
        }))
        recipe = {"id": "cp", "nexus_game": "cyberpunk2077", "components": [
            {"nexus_mod": 30093, "name": "CyberpunkVR Port", "required_files": [str(required.relative_to(self.game))]}
        ]}
        rep = hub.verify(recipe)
        self.assertEqual(rep["rows"][0]["status"], "damaged")
        required.parent.mkdir(parents=True)
        required.write_bytes(b"dll")
        self.assertEqual(hub.verify(recipe)["rows"][0]["status"], "ok")




class PublicRecipeSetDev13Tests(unittest.TestCase):
    def test_public_recipe_set_contains_only_verified_workflows(self):
        from vrhub.hub import load_recipes
        self.assertEqual(
            set(load_recipes()),
            {"cyberpunk-2077", "fatekeeper", "ready-or-not", "skyrim-vr-mgo"},
        )

if __name__ == "__main__":
    unittest.main()

class Hub040Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.state = self.root / "state.json"
        self.env = mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.state)})
        self.env.start()
        self.find = mock.patch.object(hub, "find_game", return_value=self.game)
        self.find.start()

    def tearDown(self):
        self.find.stop()
        self.env.stop()
        self.tmp.cleanup()

    def make_zip(self, name, entries):
        p = self.root / name
        with zipfile.ZipFile(p, "w") as z:
            for arcname, data in entries:
                z.writestr(arcname, data)
        return p

    def test_inspect_archive_does_not_touch_game(self):
        z = self.make_zip("CyberpunkVRPort-30093.zip", [
            ("red4ext\\plugins\\CyberpunkVR_Stereo\\CyberpunkVR_Stereo.dll", b"dll"),
            ("bin\\x64\\example.ini", b"x"),
        ])
        recipe = {"id": "cp", "name": "CP", "steam_appid": 1, "method": "gameroot",
                  "components": [{"nexus_mod": 30093, "name": "CyberpunkVR Port",
                                  "required_files": ["red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll"]}]}
        rep = hub.inspect_archive(recipe, z)
        self.assertEqual(rep["install_files"], 2)
        self.assertEqual(rep["nexus_mod"], 30093)
        self.assertFalse((self.game / "red4ext").exists())
        self.assertFalse(self.state.exists())

    def test_preflight_reports_wivrn_and_prefix(self):
        # find_game is mocked to self.game; shape it like <lib>/steamapps/common/Game
        lib = self.root / "lib"
        game = lib / "steamapps/common/Game"
        game.mkdir(parents=True)
        pfx = lib / "steamapps/compatdata/1/pfx"
        pfx.mkdir(parents=True)
        self.find.stop()
        self.find = mock.patch.object(hub, "find_game", return_value=game)
        self.find.start()
        recipe = {"id": "g", "name": "G", "steam_appid": 1,
                  "requirements": {"openxr": "wivrn", "proton_prefix": True}}
        with mock.patch.object(hub.runtime, "active_runtime", return_value=(Path("/tmp/wivrn.json"), "/usr/lib/libopenxr_wivrn.so")), \
             mock.patch.object(hub.runtime, "is_wivrn", return_value=True):
            rep = hub.preflight(recipe)
        self.assertTrue(rep["ready"])
        self.assertEqual([r["name"] for r in rep["rows"]], ["Steam game", "Proton prefix", "OpenXR"])

class SkyrimHandlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "lib/steamapps/common/SkyrimVR"
        self.game.mkdir(parents=True)
        self.pfx = self.root / "lib/steamapps/compatdata/611670/pfx"
        self.pfx.mkdir(parents=True)
        self.find = mock.patch.object(hub, "find_game", return_value=self.game)
        self.find.start()
        self.wivrn = mock.patch.object(hub.runtime, "is_wivrn", return_value=True)
        self.wivrn.start()
        self.runtime = mock.patch.object(hub.runtime, "active_runtime", return_value=(Path("/tmp/wivrn.json"), "libwivrn.so"))
        self.runtime.start()

    def tearDown(self):
        self.runtime.stop()
        self.wivrn.stop()
        self.find.stop()
        self.tmp.cleanup()

    def recipe(self):
        return {"id": "skyrim-vr-mgo", "name": "Skyrim VR", "steam_appid": 611670,
                "method": "guide", "handler": "skyrim-vr",
                "requirements": {"openxr": "wivrn", "proton_prefix": True},
                "handler_config": {"mgo_dir_env": "NANNERS_MGO_DIR",
                                   "opencomposite_mod": "Open Composite XR - Incompatible with VR Performance Kit",
                                   "conflicting_mod_dirs": ["VR Performance Kit"]}}

    def test_guide_is_ready_without_optional_mgo_deep_check(self):
        recipe = self.recipe()
        handler = hub.get_handler(recipe)

        with mock.patch.dict(os.environ, {}, clear=False),              mock.patch.object(handler, "_mgo_dir", return_value=None):
            os.environ.pop("NANNERS_MGO_DIR", None)
            rep = hub.preflight(recipe)

        self.assertTrue(rep["ready"])
        mgo = next(r for r in rep["rows"] if r["name"] == "MGO directory")
        self.assertFalse(mgo["required"])

    def test_mgo_deep_check_finds_opencomposite(self):
        mgo = self.root / "MGO"

    def test_mgo_deep_check_finds_opencomposite(self):
        mgo = self.root / "MGO"
        (mgo / "mods/Open Composite XR - Incompatible with VR Performance Kit").mkdir(parents=True)
        (mgo / "ModOrganizer.exe").write_bytes(b"exe")
        shortcut = {"appname": "SkyrimVRMGO3.8", "gameid": 17404776383439175680}
        with mock.patch.dict(os.environ, {"NANNERS_MGO_DIR": str(mgo)}), \
             mock.patch("vrhub.handlers.SkyrimVRHandler._steam_shortcut", return_value=shortcut):
            rep = hub.preflight(self.recipe())
        self.assertTrue(rep["ready"])
        self.assertTrue(any(r["name"] == "MGO OpenComposite" and r["ok"] for r in rep["rows"]))

    def test_guide_rejects_direct_install(self):
        with self.assertRaisesRegex(RuntimeError, "guided workflow"):
            hub.install_many(self.recipe(), [self.root / "anything.zip"])

class SkyrimLaunchDev4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.game = self.root / "Steam/steamapps/common/SkyrimVR"
        self.game.mkdir(parents=True)
        self.compat = self.root / "Steam/steamapps/compatdata/611670"
        (self.compat / "pfx").mkdir(parents=True)
        self.proton = self.root / "Steam/steamapps/common/Proton - Experimental/proton"
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text("#!/bin/sh\n")
        self.recipe = {"id": "skyrim-vr-mgo", "name": "Skyrim VR", "steam_appid": 611670,
                       "method": "guide", "handler": "skyrim-vr",
                       "requirements": {"openxr": "wivrn", "proton_prefix": True},
                       "handler_config": {"mgo_dir_env": "NANNERS_MGO_DIR",
                                          "mgo_globs": ["SkyrimVR*MGO*"],
                                          "opencomposite_mod": "Open Composite XR - Incompatible with VR Performance Kit",
                                          "conflicting_mod_dirs": []},
                       "launch": {"env": {"PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES": "1"}}}

    def tearDown(self):
        self.tmp.cleanup()

    def _mgo(self):
        mgo = self.home / "SkyrimVRMODMGO3.8"
        (mgo / "mods/Open Composite XR - Incompatible with VR Performance Kit").mkdir(parents=True)
        (mgo / "ModOrganizer.exe").write_bytes(b"exe")
        return mgo

    def test_auto_detects_mgo_in_home(self):
        from vrhub.handlers import SkyrimVRHandler
        mgo = self._mgo()
        with mock.patch("pathlib.Path.home", return_value=self.home), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NANNERS_MGO_DIR", None)
            found = SkyrimVRHandler()._mgo_dir(self.recipe)
        self.assertEqual(found, mgo.resolve())

    def _shortcuts_vdf(self, mgo, appid=0xF18A2FE8):
        import struct
        vdf = self.home / ".local/share/Steam/userdata/841069681/config/shortcuts.vdf"
        vdf.parent.mkdir(parents=True)
        def z(s): return str(s).encode() + b"\0"
        data = bytearray()
        data += b"\x00" + z("shortcuts")
        data += b"\x00" + z("0")
        data += b"\x02" + z("appid") + struct.pack("<I", appid)
        data += b"\x01" + z("AppName") + z("SkyrimVRMGO3.8")
        data += b"\x01" + z("Exe") + z(f'"{mgo / "ModOrganizer.exe"}"')
        data += b"\x01" + z("StartDir") + z(f'"{mgo}"')
        data += b"\x00" + z("tags") + b"\x01" + z("0") + z("Jackify") + b"\x08"
        data += b"\x08\x08"
        vdf.write_bytes(data)
        return vdf

    def test_finds_jackify_shortcut_and_converts_gameid(self):
        from vrhub.handlers import SkyrimVRHandler
        mgo = self._mgo()
        self._shortcuts_vdf(mgo)
        with mock.patch("pathlib.Path.home", return_value=self.home):
            row = SkyrimVRHandler()._steam_shortcut(self.recipe, mgo)
        self.assertIsNotNone(row)
        self.assertEqual(row["appid"], 4052365288)
        self.assertEqual(row["gameid"], 17404776383439175680)
        self.assertEqual(row["appname"], "SkyrimVRMGO3.8")

    def test_launch_mo2_uses_steam_shortcut_uri(self):
        from vrhub.handlers import SkyrimVRHandler
        mgo = self._mgo()
        self._shortcuts_vdf(mgo)
        fake_proc = mock.Mock(pid=4242)
        with mock.patch("pathlib.Path.home", return_value=self.home), \
             mock.patch.dict(os.environ, {"NANNERS_MGO_DIR": str(mgo)}), \
             mock.patch("vrhub.handlers.shutil.which", return_value="/usr/bin/steam"), \
             mock.patch("vrhub.handlers.subprocess.Popen", return_value=fake_proc) as popen:
            proc = SkyrimVRHandler().launch(self.recipe, self.game)
        self.assertEqual(proc.pid, 4242)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], ["/usr/bin/steam", "steam://rungameid/17404776383439175680"])
        self.assertTrue(kwargs["start_new_session"])

    def test_preflight_requires_matching_mo2_shortcut(self):
        from vrhub.handlers import SkyrimVRHandler
        mgo = self._mgo()
        with mock.patch("pathlib.Path.home", return_value=self.home), \
             mock.patch.dict(os.environ, {"NANNERS_MGO_DIR": str(mgo)}):
            rows = SkyrimVRHandler().preflight_rows(self.recipe, self.game)
        row = next(r for r in rows if r["name"] == "MO2 Steam shortcut")
        self.assertFalse(row["ok"])
        self._shortcuts_vdf(mgo)
        with mock.patch("pathlib.Path.home", return_value=self.home), \
             mock.patch.dict(os.environ, {"NANNERS_MGO_DIR": str(mgo)}):
            rows = SkyrimVRHandler().preflight_rows(self.recipe, self.game)
        row = next(r for r in rows if r["name"] == "MO2 Steam shortcut")
        self.assertTrue(row["ok"])
        self.assertIn("SkyrimVRMGO3.8", row["detail"])

class SkyrimLaunchDev5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.game = self.root / "Steam/steamapps/common/SkyrimVR"
        self.game.mkdir(parents=True)
        (self.root / "Steam/steamapps/compatdata/611670/pfx").mkdir(parents=True)
        self.mgo = self.home / "SkyrimVRMODMGO3.8"
        (self.mgo / "mods/Open Composite XR - Incompatible with VR Performance Kit").mkdir(parents=True)
        (self.mgo / "ModOrganizer.exe").write_bytes(b"exe")
        self.recipe = {"id": "skyrim-vr-mgo", "name": "Skyrim VR", "steam_appid": 611670,
                       "method": "guide", "handler": "skyrim-vr",
                       "requirements": {"openxr": "wivrn", "proton_prefix": True},
                       "handler_config": {"mgo_dir_env": "NANNERS_MGO_DIR",
                                          "mgo_globs": ["SkyrimVR*MGO*"],
                                          "opencomposite_mod": "Open Composite XR - Incompatible with VR Performance Kit",
                                          "conflicting_mod_dirs": []}}

    def tearDown(self):
        self.tmp.cleanup()

    def _write_ini(self):
        (self.mgo / "ModOrganizer.ini").write_text(
            "[General]\nselected_profile=@ByteArray(Mad God Classic)\n\n"
            "[customExecutables]\n"
            "1\\title=Skyrim VR\n"
            "1\\binary=C:/Games/SkyrimVR/SkyrimVR.exe\n"
            "2\\title=SKSEVR\n"
            "2\\binary=C:/Games/SkyrimVR/sksevr_loader.exe\n"
            "2\\arguments=\n",
            encoding="utf-8")

    def test_reads_profile_and_prefers_sksevr_loader(self):
        from vrhub.handlers import SkyrimVRHandler
        self._write_ini()
        h = SkyrimVRHandler()
        state = h._mo2_state(self.mgo)
        self.assertEqual(state["profile"], "Mad God Classic")
        entry = h._skse_entry(self.mgo)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "SKSEVR")
        self.assertTrue(entry["binary"].lower().endswith("sksevr_loader.exe"))

    def test_launch_skyrim_uses_dev6_bridge_with_shortcut_prefix(self):
        from vrhub.handlers import SkyrimVRHandler
        self._write_ini()
        steam_root = self.root / "Steam"
        vdf = steam_root / "userdata/841069681/config/shortcuts.vdf"
        vdf.parent.mkdir(parents=True, exist_ok=True)
        vdf.write_bytes(b"x")
        compat = steam_root / "steamapps/compatdata/4052365288"
        (compat / "pfx").mkdir(parents=True)
        proton_root = steam_root / "steamapps/common/Proton - Experimental"
        proton_root.mkdir(parents=True, exist_ok=True)
        proton = proton_root / "proton"
        proton.write_text("#!/bin/sh\n")
        (compat / "config_info").write_text(str(proton_root / "files/share/fonts") + "\n")
        shortcut = {"appid": 4052365288, "gameid": 17404776383439175680,
                    "appname": "SkyrimVRMGO3.8", "vdf": str(vdf)}
        fake_proc = mock.Mock(pid=5150)
        with mock.patch.dict(os.environ, {"NANNERS_MGO_DIR": str(self.mgo)}), \
             mock.patch("vrhub.handlers.SkyrimVRHandler._steam_shortcut", return_value=shortcut), \
             mock.patch("vrhub.handlers.shutil.which", return_value="/usr/bin/steam"), \
             mock.patch("vrhub.handlers.subprocess.Popen", return_value=fake_proc) as popen:
            proc = SkyrimVRHandler().launch_play(self.recipe, self.game)
        self.assertEqual(proc.pid, 5150)
        args, kwargs = popen.call_args
        self.assertIn("vrhub.mo2_bridge", args[0])
        self.assertIn("steam://rungameid/17404776383439175680", args[0])
        self.assertIn("SKSEVR", args[0])
        self.assertIn(str(compat), args[0])
        self.assertTrue(kwargs["start_new_session"])

    def test_shortcut_compat_uses_prefix_configured_proton(self):
        from vrhub.handlers import SkyrimVRHandler
        steam_root = self.root / "Steam"
        vdf = steam_root / "userdata/841069681/config/shortcuts.vdf"
        vdf.parent.mkdir(parents=True, exist_ok=True)
        vdf.write_bytes(b"x")
        compat = steam_root / "steamapps/compatdata/4052365288"
        (compat / "pfx").mkdir(parents=True)
        proton_root = steam_root / "steamapps/common/Proton - Experimental"
        (proton_root / "files/share/fonts").mkdir(parents=True)
        proton = proton_root / "proton"
        proton.write_text("#!/bin/sh\n")
        (compat / "config_info").write_text(str(proton_root / "files/share/fonts") + "\n")
        row = {"appid": 4052365288, "vdf": str(vdf)}
        got = SkyrimVRHandler()._shortcut_compat(row)
        self.assertIsNotNone(got)
        self.assertEqual(got[0], steam_root.resolve())
        self.assertEqual(got[1], compat)
        self.assertEqual(got[2], proton.resolve())

    def test_diagnostics_include_profile_shortcut_and_skse(self):
        from vrhub.handlers import SkyrimVRHandler
        self._write_ini()
        shortcut = {"appid": 4052365288, "gameid": 17404776383439175680,
                    "appname": "SkyrimVRMGO3.8"}
        with mock.patch.dict(os.environ, {"NANNERS_MGO_DIR": str(self.mgo)}), \
             mock.patch("vrhub.handlers.SkyrimVRHandler._steam_shortcut", return_value=shortcut):
            text = "\n".join(SkyrimVRHandler().diagnostics(self.recipe, self.game))
        self.assertIn("MO2 active profile: Mad God Classic", text)
        self.assertIn("MO2 Steam shortcut: SkyrimVRMGO3.8", text)
        self.assertIn("MO2 shortcut AppID: 4052365288", text)
        self.assertIn("MO2 Skyrim executable: SKSEVR", text)


class SkyrimDev7StatusTests(unittest.TestCase):
    def test_live_status_detects_mo2_and_skyrim(self):
        from vrhub.handlers import SkyrimVRHandler
        h = SkyrimVRHandler()
        with mock.patch.object(h, "_process_cmdlines", return_value=[
            "wine64 z:/home/user/mgo/modorganizer.exe",
            "wine64 z:/steam/skyrimvr/skyrimvr.exe",
        ]):
            status = h.live_status({}, None)
        self.assertTrue(status["mo2"])
        self.assertTrue(status["game"])

    def test_bridge_log_path_is_user_local_state(self):
        from vrhub.handlers import SkyrimVRHandler
        with mock.patch("pathlib.Path.home", return_value=Path("/tmp/nanners-home")):
            path = SkyrimVRHandler().bridge_log({})
        self.assertEqual(path, Path("/tmp/nanners-home/.local/share/vrhub/mo2-bridge.log"))

class GenericLaunchTests(unittest.TestCase):
    def test_generic_handler_exposes_launch_game_and_uses_steam_appid(self):
        from unittest.mock import patch
        from vrhub.handlers import GameHandler
        recipe = {"id": "demo", "name": "Demo Game", "steam_appid": 123456}
        handler = GameHandler()
        self.assertEqual(handler.play_label(recipe), "Launch game")
        with patch("vrhub.handlers.shutil.which", return_value="/usr/bin/steam"), \
             patch("vrhub.handlers.subprocess.Popen") as popen:
            handler.launch_play(recipe, Path("/tmp/demo"))
        popen.assert_called_once_with(
            ["/usr/bin/steam", "steam://launch/123456/dialog"], start_new_session=True
        )

class HeroicGOGHandlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = self.root / "heroic"
        (self.cfg / "gog_store").mkdir(parents=True)
        (self.cfg / "GamesConfig").mkdir(parents=True)
        self.game = self.root / "Games/Heroic/DOOM (2016)"
        self.game.mkdir(parents=True)
        (self.game / "DOOMx64.exe").write_bytes(b"exe")
        self.prefix = self.root / "Games/Heroic/Prefixes/DOOM (2016)"
        self.prefix.mkdir(parents=True)
        self.proton = self.root / "Proton-CachyOS-latest/proton"
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text("#!/bin/sh\n")
        (self.cfg / "gog_store/installed.json").write_text(json.dumps({"installed": [{
            "appName": "1390579243", "install_path": str(self.game), "platform": "windows"
        }]}))
        (self.cfg / "GamesConfig/1390579243.json").write_text(json.dumps({
            "1390579243": {"winePrefix": str(self.prefix), "wineVersion": {
                "bin": str(self.proton), "name": "Proton-CachyOS-latest", "type": "proton"
            }}
        }))
        self.recipe = {"id": "doom-2016-gog", "name": "DOOM (2016)", "store": "heroic-gog",
                       "heroic_appid": "1390579243", "method": "guide", "handler": "heroic-gog",
                       "handler_config": {"executable": "DOOMx64.exe", "play_label": "Launch DOOM"}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_discovers_game_prefix_and_runner(self):
        from vrhub.handlers import HeroicGOGHandler
        with mock.patch.dict(os.environ, {"NANNERS_HEROIC_CONFIG": str(self.cfg)}):
            h = HeroicGOGHandler()
            self.assertEqual(h.game_path(self.recipe), self.game.resolve())
            rows = h.preflight_rows(self.recipe, self.game)
        by_name = {r["name"]: r for r in rows}
        self.assertTrue(by_name["Heroic GOG metadata"]["ok"])
        self.assertTrue(by_name["Game executable"]["ok"])
        self.assertTrue(by_name["Heroic prefix"]["ok"])
        self.assertTrue(by_name["Heroic runner"]["ok"])

    def test_launch_uses_heroic_uri_not_direct_proton(self):
        from vrhub.handlers import HeroicGOGHandler
        fake_proc = mock.Mock(pid=77)
        with mock.patch.dict(os.environ, {"NANNERS_HEROIC_CONFIG": str(self.cfg)}), \
             mock.patch("vrhub.heroic.shutil.which", side_effect=lambda x: "/usr/bin/heroic" if x == "heroic" else None), \
             mock.patch("vrhub.handlers.subprocess.Popen", return_value=fake_proc) as popen:
            proc = HeroicGOGHandler().launch_play(self.recipe, self.game)
        self.assertEqual(proc.pid, 77)
        popen.assert_called_once_with([
            "/usr/bin/heroic", "--no-gui", "--no-sandbox",
            "heroic://launch?appName=1390579243&runner=gog"
        ], start_new_session=True)

class HeroicGOGKharvoxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = self.root / "heroic"
        (self.cfg / "gog_store").mkdir(parents=True)
        (self.cfg / "GamesConfig").mkdir(parents=True)
        self.game = self.root / "Games/Heroic/DOOM (2016)"
        self.game.mkdir(parents=True)
        (self.game / "DOOMx64.exe").write_bytes(b"exe")
        self.prefix = self.root / "Games/Heroic/Prefixes/DOOM (2016)"
        self.prefix.mkdir(parents=True)
        self.proton_dir = self.root / "Proton-CachyOS-latest"
        self.proton_dir.mkdir(parents=True)
        self.proton = self.proton_dir / "proton"
        self.proton.write_text("#!/bin/sh\n")
        self.kharvox = self.root / "Games/KHARVOX-0.9"
        self.kharvox.mkdir(parents=True)
        (self.kharvox / "KharvoxLauncher.exe").write_bytes(b"exe")
        (self.cfg / "gog_store/installed.json").write_text(json.dumps({"installed": [{
            "appName": "1390579243", "install_path": str(self.game), "platform": "windows"
        }]}))
        (self.cfg / "GamesConfig/1390579243.json").write_text(json.dumps({
            "1390579243": {"winePrefix": str(self.prefix), "wineVersion": {
                "bin": str(self.proton), "name": "Proton-CachyOS-latest", "type": "proton"
            }}
        }))
        self.recipe = {
            "id": "doom-2016-gog", "name": "DOOM (2016)", "store": "heroic-gog",
            "heroic_appid": "1390579243", "method": "guide", "handler": "heroic-gog",
            "handler_config": {
                "executable": "DOOMx64.exe", "play_label": "Launch DOOM",
                "launcher_label": "Launch DOOM VR", "kharvox_dir_env": "NANNERS_KHARVOX_DIR"
            }
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_kharvox_env_detection(self):
        from vrhub.handlers import HeroicGOGHandler
        with mock.patch.dict(os.environ, {"NANNERS_KHARVOX_DIR": str(self.kharvox)}):
            h = HeroicGOGHandler()
            self.assertEqual(h._kharvox_dir(self.recipe), self.kharvox.resolve())
            self.assertEqual(h.launcher_label(self.recipe), "Launch DOOM VR")

    def test_kharvox_launch_reuses_heroic_prefix_and_proton_with_umu(self):
        from vrhub.handlers import HeroicGOGHandler
        fake_proc = mock.Mock(pid=88)
        env = {
            "NANNERS_HEROIC_CONFIG": str(self.cfg),
            "NANNERS_KHARVOX_DIR": str(self.kharvox),
        }
        with mock.patch.dict(os.environ, env), \
             mock.patch("vrhub.handlers.shutil.which", side_effect=lambda x: "/usr/bin/umu-run" if x == "umu-run" else None), \
             mock.patch("vrhub.handlers.subprocess.Popen", return_value=fake_proc) as popen:
            proc = HeroicGOGHandler().launch(self.recipe, self.game)
        self.assertEqual(proc.pid, 88)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], ["/usr/bin/umu-run", str(self.kharvox / "KharvoxLauncher.exe")])
        self.assertEqual(kwargs["cwd"], str(self.kharvox))
        self.assertEqual(kwargs["env"]["WINEPREFIX"], str(self.prefix.resolve()))
        self.assertEqual(kwargs["env"]["PROTONPATH"], str(self.proton_dir.resolve()))
        self.assertEqual(kwargs["env"]["STORE"], "gog")
        self.assertEqual(kwargs["env"]["GAMEID"], "0")
        self.assertTrue(kwargs["start_new_session"])
    def test_versioned_kharvox_folder_is_preferred(self):
        from vrhub.handlers import HeroicGOGHandler
        newer = self.root / "Games/KHARVOX-v1.11"
        newer.mkdir(parents=True)
        (newer / "KharvoxLauncher.exe").write_bytes(b"exe")
        with mock.patch.dict(os.environ, {"NANNERS_KHARVOX_DIR": ""}, clear=False), \
             mock.patch("vrhub.handlers.Path.home", return_value=self.root):
            self.assertEqual(HeroicGOGHandler()._kharvox_dir(self.recipe), newer.resolve())

    def test_launch_removes_only_stale_kharvox_host_vulkan_override(self):
        from vrhub.handlers import HeroicGOGHandler
        fake_proc = mock.Mock(pid=89)
        env = {
            "NANNERS_HEROIC_CONFIG": str(self.cfg),
            "NANNERS_KHARVOX_DIR": str(self.kharvox),
            "KHARVOX_ENABLE_LAYER": "1",
            "VK_INSTANCE_LAYERS": "VK_LAYER_KHARVOX_OPENXR:VK_LAYER_NV_dlssnr:VK_LAYER_NV_present",
            "VK_LAYER_PATH": str(self.kharvox),
        }
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch("vrhub.handlers.shutil.which", side_effect=lambda x: "/usr/bin/umu-run" if x == "umu-run" else None), \
             mock.patch("vrhub.handlers.subprocess.Popen", return_value=fake_proc) as popen:
            HeroicGOGHandler().launch(self.recipe, self.game)
        child = popen.call_args.kwargs["env"]
        self.assertNotIn("KHARVOX_ENABLE_LAYER", child)
        self.assertEqual(child["VK_INSTANCE_LAYERS"], "VK_LAYER_NV_dlssnr:VK_LAYER_NV_present")
        self.assertNotIn("VK_LAYER_PATH", child)

    def test_kharvox_diagnostics_detect_native_attempt_false_and_disabled_registry(self):
        from vrhub.handlers import HeroicGOGHandler
        temp = self.prefix / "drive_c/users/steamuser/AppData/Local/Temp"
        temp.mkdir(parents=True)
        (temp / "KHARVOX-VR-INTRO.log").write_text("Standalone intro ready; DOOM has not been launched\n")
        (temp / "KHARVOX.log").write_text("[KHARVOX][LAUNCHER] nativeAttempt=False renderer=VULKAN_SFS\n")
        self.prefix.joinpath("user.reg").write_text(
            '[Software\\Khronos\\Vulkan\\ImplicitLayers]\n'
            '"X:\\Games\\KHARVOX-v1.11\\KharvoxLayer.json"=dword:00000001\n'
        )
        env = {"NANNERS_HEROIC_CONFIG": str(self.cfg), "NANNERS_KHARVOX_DIR": str(self.kharvox)}
        with mock.patch.dict(os.environ, env):
            h = HeroicGOGHandler()
            self.assertEqual(h._kharvox_native_state(self.recipe)[0], "not-attempted")
            self.assertEqual(h._kharvox_registry_state(self.recipe)[0], "disabled")
            rows = {r["name"]: r for r in h.preflight_rows(self.recipe, self.game)}
        self.assertTrue(rows["KHARVOX VR intro"]["ok"])
        self.assertFalse(rows["KHARVOX native stereo"]["ok"])
        self.assertIn("nativeAttempt=False", rows["KHARVOX native stereo"]["detail"])
        self.assertFalse(rows["KHARVOX Vulkan registration"]["ok"])
        self.assertIn("disabled", rows["KHARVOX Vulkan registration"]["detail"])

    def test_kharvox_native_log_marks_native_stereo_detected(self):
        from vrhub.handlers import HeroicGOGHandler
        temp = self.prefix / "drive_c/users/steamuser/AppData/Local/Temp"
        temp.mkdir(parents=True)
        native = temp / "KHARVOX-NATIVE-STEREO.log"
        native.write_text("native stereo initialized\n")
        env = {"NANNERS_HEROIC_CONFIG": str(self.cfg), "NANNERS_KHARVOX_DIR": str(self.kharvox)}
        with mock.patch.dict(os.environ, env):
            state, detail = HeroicGOGHandler()._kharvox_native_state(self.recipe)
        self.assertEqual(state, "detected")
        self.assertEqual(detail, str(native))
