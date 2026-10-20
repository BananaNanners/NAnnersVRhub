"""Hogwarts fixtures are installation evidence only, never gameplay results."""
import json
import zipfile
import unittest
from pathlib import Path
from unittest import mock

from tests import test_workflow_compatibility as fixtures
from vrhub import compatibility, heroic_epic, hub, log_diagnostics


def heroic_fixture(base, recipe, *, nested=False, user="steamuser", runner_type="proton", config=None):
    root = config or base / "config/heroic"
    game = base / "Games/Hogwarts Legacy"
    game.mkdir(parents=True, exist_ok=True)
    outer = base / "Prefixes/Hogwarts Legacy"
    prefix = outer / "pfx" if nested else outer
    (prefix / f"drive_c/users/{user}/AppData").mkdir(parents=True, exist_ok=True)
    runner = base / "Tools/Selected Runner" / ("proton" if runner_type == "proton" else "bin/wine")
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text("fixture, never executed")
    appid = "Phoenix-epic-fixture"
    metadata = root / "legendaryConfig/legendary/installed.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps({appid: {"app_name": appid, "title": "Hogwarts Legacy", "install_path": str(game)}}))
    settings = root / "GamesConfig" / f"{appid}.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({appid: {"winePrefix": str(outer), "wineVersion": {
        "type": runner_type, "name": "Existing Heroic Runner", "bin": str(runner)}}}))
    return root, game, prefix, (metadata, settings)


class HogwartsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SteamWorkflowCompatibilityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.recipe = self.fixture.recipes["hogwarts-legacy"]
        root, self.game, self.prefix, files = heroic_fixture(self.fixture.home, self.recipe)
        env = mock.patch.dict("os.environ", {"NANNERS_HEROIC_CONFIG": str(root), "HOME": str(self.fixture.home),
                                             "XDG_CONFIG_HOME": str(self.fixture.home / "config")})
        env.start(); self.addCleanup(env.stop)
        self.metadata = {p: p.read_bytes() for p in files}
        self.dest = hub.profile_dir(self.recipe)
        self.saves = self.prefix / hub.APPDATA / "Local/Hogwarts Legacy/Saved/SaveGames/fixture.sav"
        self.saves.parent.mkdir(parents=True)
        self.saves.write_bytes(b"saved game: preserve exactly")
        self.fixture.record("fatekeeper", {"files": [], "installed_at": 1234})
        self.previous = json.loads(self.fixture.state.read_text())["fatekeeper"]
        self.injector = self.archive("UEVR.zip", {"UEVRInjector.exe": b"exe", "UEVRBackend.dll": b"backend",
                                                "LuaVR.dll": b"lua", "openxr_loader.dll": b"loader"})
        self.profile = self.archive("HogwartsLegacy.zip", {"config.txt": b"fixture", "scripts/main.lua": b"script",
            "plugins/uevr_utils.dll": b"plugin", "plugins/gesture/model.onnx": b"gesture model",
            "plugins/voice/models/Lumos.onnx": b"voice model", "data/hogwarts_legacy_config.json": b"{}"})

    def tearDown(self):
        self.assertEqual(self.saves.read_bytes(), b"saved game: preserve exactly")
        self.assertEqual(json.loads(self.fixture.state.read_text())["fatekeeper"], self.previous)
        for path, data in self.metadata.items():
            self.assertEqual(path.read_bytes(), data)

    def archive(self, name, entries):
        path = self.fixture.home / name
        with zipfile.ZipFile(path, "w") as z:
            for name, content in entries.items():
                z.writestr(name, content)
        return path

    def install(self):
        hub.install(self.recipe, self.injector, [self.fixture.steam])
        return hub.install_profile(self.recipe, self.profile, [self.fixture.steam])

    def report(self):
        return compatibility.report(self.recipe, [self.fixture.steam])

    def test_complete_install_keeps_review_separate_from_bundled_reference(self):
        files = self.install()
        self.assertEqual(len(files), 6)
        self.assertEqual((self.dest / "plugins/voice/models/Lumos.onnx").read_bytes(), b"voice model")
        self.assertFalse((self.dest / "HogwartsLegacy").exists())
        report = self.report()
        self.assertEqual(report["status"], "REVIEW REQUIRED")
        self.assertEqual(report["local_test_count"], 0)
        text = compatibility.report_text(report)
        self.assertIn("Gameplay evidence: USER-REPORTED LIVE TEST", text)
        self.assertIn("2026-10-19", text)
        self.assertIn("one-click injector button", text)
        self.assertIn("wrist-flick activation", text)
        self.assertIn("longer-session stability remain unverified", text)

    def test_old_profile_is_backed_up_replaced_and_restored(self):
        old = self.dest / "plugins/ue4ss/old.ini"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"old profile")
        self.install()
        self.assertFalse(old.exists())
        record = json.loads(self.fixture.state.read_text())["hogwarts-legacy:profile"]
        self.assertEqual((Path(record["backup"]) / "plugins/ue4ss/old.ini").read_bytes(), b"old profile")
        hub.uninstall("hogwarts-legacy:profile")
        self.assertEqual(old.read_bytes(), b"old profile")
        self.assertFalse((self.dest / "plugins/uevr_utils.dll").exists())

    def test_wrapped_windows_archive_retains_plugins_and_models(self):
        self.profile = self.archive("wrapped.zip", {"HogwartsLegacy\\config.txt": b"fixture",
            "HogwartsLegacy\\scripts\\main.lua": b"script", "HogwartsLegacy\\plugins\\uevr_utils.dll": b"plugin",
            "HogwartsLegacy\\plugins\\voice\\models\\Lumos.onnx": b"model"})
        self.install()
        self.assertTrue((self.dest / "scripts/main.lua").is_file())
        self.assertTrue((self.dest / "plugins/voice/models/Lumos.onnx").is_file())

    def test_missing_recorded_plugin_or_model_is_not_ready(self):
        self.install()
        for relative in ("plugins/uevr_utils.dll", "plugins/voice/models/Lumos.onnx"):
            path = self.dest / relative
            before = path.read_bytes()
            path.unlink()
            with self.subTest(relative=relative):
                self.assertEqual(self.report()["status"], "NOT READY")
            path.write_bytes(before)

    def test_missing_paired_backend_file_is_not_ready(self):
        self.install()
        (self.prefix / "drive_c/uevr/LuaVR.dll").unlink()
        self.assertEqual(self.report()["status"], "NOT READY")

    def test_manual_files_without_hub_inventory_stay_incomplete(self):
        self.install()
        state = json.loads(self.fixture.state.read_text())
        state.pop("hogwarts-legacy:profile")
        self.fixture.state.write_text(json.dumps(state))
        self.assertEqual(self.report()["status"], "INCOMPLETE")

    def test_unsafe_archive_preserves_existing_profile(self):
        self.dest.mkdir(parents=True)
        old = self.dest / "config.txt"
        old.write_bytes(b"old")
        bad = self.archive("unsafe.zip", {"config.txt": b"new", "../escape.txt": b"bad"})
        before = self.fixture.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Unsafe path"):
            hub.install_profile(self.recipe, bad, [self.fixture.steam])
        self.assertEqual(old.read_bytes(), b"old")
        self.assertEqual(self.fixture.state.read_bytes(), before)
        self.assertFalse((self.fixture.home / "escape.txt").exists())

    def test_unavailable_runner_cannot_fall_back_to_steam_protontricks(self):
        self.install()
        with mock.patch("vrhub.hub.subprocess.Popen") as launch:
            with self.assertRaisesRegex(RuntimeError, "runner is unavailable"):
                hub.launch_injector(self.recipe)
        launch.assert_not_called()
        self.assertEqual(hub.injector_path(self.recipe), self.prefix / "drive_c/uevr/UEVRInjector.exe")
        self.assertNotIn("Steam launch options:", hub.details_text(self.recipe))

    def test_game_launch_uses_the_discovered_epic_identity_and_heroic(self):
        with mock.patch("vrhub.heroic_epic.shutil.which", return_value="/usr/bin/heroic"), \
                mock.patch("vrhub.handlers.subprocess.Popen") as launch:
            launch.return_value.pid = 1234
            hub.launch_game_play(self.recipe)
        args = launch.call_args.args[0]
        self.assertEqual(args[:2], ["/usr/bin/heroic", "--no-gui"])
        self.assertIn("appName=Phoenix-epic-fixture&runner=legendary", args[-1])

    def test_expected_log_uses_hogwarts_profile_and_generic_uevr_advice(self):
        self.install()
        log = self.dest / "log.txt"
        log.write_text("OpenXR: xrEndFrame failed (res=-39)\n")
        report = log_diagnostics.report(self.recipe, [self.fixture.steam])
        text = log_diagnostics.report_text(report)
        self.assertIn(str(log), text)
        self.assertIn("XR_ERROR_POSE_INVALID", text)
        self.assertNotIn("Cyberpunk workaround", text)
        self.assertNotIn("SLASHER-Win64-Shipping", text)

    def test_update_tracking_covers_matching_injector_and_profile(self):
        update = self.recipe["updates"][0]
        self.assertEqual(update["github"], "jbusfield/HL_UEVR")
        self.assertEqual(set(update["tracks"]), {"hogwarts-legacy", "hogwarts-legacy:profile"})
        self.assertIn("/v2.0.6", self.recipe["mod_page"])
