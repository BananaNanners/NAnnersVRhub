# SPDX-License-Identifier: GPL-3.0-only
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from vrhub import heroic_epic, launch_environment


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
