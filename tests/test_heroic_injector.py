"""Secondary executable launch isolation; no Windows code or game is executed."""
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import test_heroic_epic as discovery
from vrhub import heroic_epic, heroic_injector as injector, hub


class HeroicInjectorTests(unittest.TestCase):
    setUp = discovery.HeroicDiscoveryTests.setUp
    fixture = discovery.HeroicDiscoveryTests.fixture

    def setup_launch(self, **kwargs):
        root, game, prefix, files = self.fixture(**kwargs)
        exe = prefix / "drive_c/uevr/UEVRInjector.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"fixture: never executed")
        info = heroic_epic.context(self.recipe)
        Path(info["wine"]["bin"]).chmod(0o755)
        return info, exe, files

    def test_umu_pins_runner_prefix_and_argument_with_spaces(self):
        info, exe, files = self.setup_launch(nested=True)
        before = {f: f.read_bytes() for f in files}
        info["settings"].update(enableEsync=True, enableFsync=False, enviromentOptions=[
            {"key": "VR_TEST_LITERAL", "value": "'spaces; $(never-run)'"},
            {"key": "WINEPREFIX", "value": "/wrong-prefix"},
            {"key": "SteamAppId", "value": "990080"},
            {"key": "UMU_NO_PROTON", "value": "1"}])
        with mock.patch.dict(os.environ, {"WINEPREFIX": "/another-game", "STEAM_COMPAT_DATA_PATH": "/another-game",
                  "STEAM_COMPAT_TOOL_PATHS": "/other-runner", "PROTON_NO_ESYNC": "1", "SteamAppId": "611670"}), \
                mock.patch.object(injector.shutil, "which", return_value="/usr/bin/umu-run"):
            args, env = injector.plan(info, exe)
        self.assertEqual(args, ["/usr/bin/umu-run", str(exe)])
        self.assertEqual(env["WINEPREFIX"], info["settings"]["winePrefix"])
        self.assertEqual(env["UMU_CONTAINER_NSENTER"], "1")
        self.assertEqual(env["PROTONPATH"], str(Path(info["wine"]["bin"]).parent))
        self.assertEqual(env["STEAM_COMPAT_DATA_PATH"], info["settings"]["winePrefix"])
        self.assertEqual(env["SteamAppId"], "0")
        self.assertEqual(env["PROTON_VERB"], "runinprefix")
        self.assertEqual(env["UMU_RUNTIME_UPDATE"], "0")
        self.assertNotIn("UMU_NO_PROTON", env)
        self.assertNotIn("STEAM_COMPAT_TOOL_PATHS", env)
        self.assertNotIn("PROTON_NO_ESYNC", env)
        self.assertEqual(env["PROTON_NO_FSYNC"], "1")
        self.assertEqual(env["VR_TEST_LITERAL"], "spaces; $(never-run)")
        self.assertEqual(env["PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES"], "1")
        for f, data in before.items():
            self.assertEqual(f.read_bytes(), data)

    def test_bundled_umu_and_direct_proton_use_existing_layout_only(self):
        info, exe, _ = self.setup_launch()
        bundled = info["root"] / "tools/runtimes/umu/umu_run.py"
        bundled.parent.mkdir(parents=True)
        bundled.write_text("fixture")
        bundled.chmod(0o755)
        with mock.patch.object(injector.shutil, "which", return_value=None):
            self.assertEqual(injector.plan(info, exe)[0][0], str(bundled))
            info["settings"]["disableUMU"] = True
            with self.assertRaisesRegex(RuntimeError, "nested prefix"):
                injector.plan(info, exe)
            self.assertFalse((exe.parents[2] / "pfx").exists())
            (exe.parents[2] / "pfx").symlink_to(".", target_is_directory=True)
            args, env = injector.plan(info, exe)
        self.assertEqual(args, [info["wine"]["bin"], "runinprefix", str(exe)])
        self.assertEqual(env["WINEPREFIX"], str(exe.parents[2]))

    def test_flatpak_unknown_runner_and_invalid_environment_do_not_spawn(self):
        info, exe, _ = self.setup_launch()
        with mock.patch.object(injector.subprocess, "Popen") as spawn:
            info["flatpak"] = True
            with self.assertRaisesRegex(RuntimeError, "Flatpak"):
                injector.launch(info, exe)
            info["flatpak"] = False
            info["wine"]["type"] = "unknown"
            with self.assertRaisesRegex(RuntimeError, "runner is unavailable"):
                injector.launch(info, exe)
            info["wine"]["type"] = "wine"
            info["settings"]["enviromentOptions"] = [{"key": "bad=key", "value": "x"}]
            with self.assertRaisesRegex(RuntimeError, "environment settings"):
                injector.launch(info, exe)
        spawn.assert_not_called()

    def test_native_wine_real_spawn_preserves_literals_and_reports_failure(self):
        info, exe, _ = self.setup_launch(runner_type="wine")
        runner = Path(info["wine"]["bin"])
        runner.write_text("#!" + sys.executable + "\nimport os,sys,json\nprint(json.dumps({'args':sys.argv[1:], 'prefix':os.environ['WINEPREFIX'], 'cwd':os.getcwd()}))\nprint('fixture launch failed',file=sys.stderr)\nsys.exit(7)\n")
        result = injector.launch(info, exe)
        deadline = time.monotonic() + 5
        while result.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(result.poll(), 7)
        data = json.loads(next(line for line in result.output_tail().splitlines() if line.startswith("{")))
        self.assertEqual(data, {"args": [str(exe)], "prefix": str(exe.parents[2]), "cwd": str(exe.parent)})
        self.assertIn("fixture launch failed", result.output_tail())

    def test_live_launcher_is_reused_and_output_is_bounded(self):
        info, exe, _ = self.setup_launch(runner_type="wine")
        with mock.patch.object(injector, "InjectorLaunch") as create:
            create.return_value.poll.return_value = None
            first = injector.launch(info, exe)
            self.assertIs(injector.launch(info, exe), first)
            create.assert_called_once()
            first.poll.return_value = 0
            injector.launch(info, exe)
            self.assertEqual(create.call_count, 2)
        result = injector.InjectorLaunch([sys.executable, "-c", "print('x' * 200000); print('end')"], dict(os.environ), str(self.home))
        deadline = time.monotonic() + 5
        while result.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(result.poll(), 0)
        self.assertLessEqual(len(result.output_tail().encode()), injector.TAIL_LIMIT)
        self.assertTrue(result.output_tail().endswith("end\n"))

    def tearDown(self):
        injector._launches.clear()
