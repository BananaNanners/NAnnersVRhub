# SPDX-License-Identifier: GPL-3.0-only
import os
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path
from unittest.mock import patch

from vrhub import heroic_epic, hub, launch_environment, runtime


class FullPreviewTests(unittest.TestCase):
    def test_host_xdg_for_detection_and_children_only(self):
        with patch.object(launch_environment, "_host", None), patch.dict(os.environ, {
            "XDG_CONFIG_HOME": "/host/config", "XDG_CACHE_HOME": "/host/cache",
        }):
            os.environ.pop("XDG_DATA_HOME", None)
            launch_environment.capture_host_xdg()
            os.environ.update(XDG_CONFIG_HOME="/preview/config", XDG_CACHE_HOME="/preview/cache",
                              XDG_DATA_HOME="/preview/data")
            self.assertIn(Path("/host/config/heroic"), heroic_epic.default_roots())
            env = launch_environment.subprocess_kwargs()["env"]
            self.assertEqual(env["XDG_CONFIG_HOME"], "/host/config")
            self.assertEqual(env["XDG_CACHE_HOME"], "/host/cache")
            self.assertNotIn("XDG_DATA_HOME", env)
            self.assertEqual(os.environ["XDG_CONFIG_HOME"], "/preview/config")


    def test_runtime_follows_host_selection_after_preview_start(self):
        with TemporaryDirectory() as root, patch.object(launch_environment, "_host", None), patch.dict(os.environ):
            host = Path(root) / "host"
            manifests = host / "openxr/1"
            manifests.mkdir(parents=True)
            os.environ["XDG_CONFIG_HOME"] = str(host)
            os.environ.pop("XR_RUNTIME_JSON", None)
            launch_environment.capture_host_xdg()
            os.environ["XDG_CONFIG_HOME"] = str(Path(root) / "isolated")
            selected = manifests / "active_runtime.json"
            for lib, expected in (("steamxr.so", "SteamVR"), ("libopenxr_wivrn.so", "WiVRn")):
                selected.write_text(json.dumps({"file_format_version": "1.0.0",
                                                "runtime": {"library_path": lib}}))
                self.assertEqual(runtime.runtime_name(*runtime.active_runtime()), expected)
            os.environ["XR_RUNTIME_JSON"] = str(manifests / "explicit-missing.json")
            self.assertEqual(runtime.active_runtime()[1], "")

    def test_steam_injector_child_is_reaped(self):
        recipe = {"steam_appid": 2186990}
        child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])
        original_wait = child.wait
        from threading import Event
        reaped = Event()

        def wait():
            code = original_wait(timeout=5)
            reaped.set()
            return code

        with patch.object(hub, "injector_path", return_value=Path("/test/UEVRInjector.exe")), patch.object(
                hub.shutil, "which", return_value="/test/protontricks-launch"), patch.object(
                child, "wait", side_effect=wait), patch.object(hub.subprocess, "Popen", return_value=child) as launch:
            self.assertIs(hub.launch_injector(recipe), child)
            self.assertIn("--no-background-wineserver", launch.call_args.args[0])
            self.assertTrue(reaped.wait(5))
            self.assertEqual(child.returncode, 7)
        self.assertFalse(Path(f"/proc/{child.pid}").exists())
