# SPDX-License-Identifier: GPL-3.0-only
import tempfile
import subprocess
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from vrhub import dev_preview, dev_preview_storage as storage


class PreviewLauncherTests(unittest.TestCase):
    def test_shared_lock_cross_process_and_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / ".cache/nannersvrhub-preview-lifecycle.lock"
            code = (
                "import sys; from pathlib import Path; from vrhub.dev_preview_storage "
                "import acquire_desktop_preview_lock; "
                "acquire_desktop_preview_lock(Path(sys.argv[1]))"
            )
            storage.acquire_desktop_preview_lock(home)
            try:
                storage.acquire_desktop_preview_lock(home)
                blocked = subprocess.run([sys.executable, "-B", "-c", code, directory],
                                         capture_output=True, text=True)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn("already running", blocked.stderr)
            finally:
                os.close(storage._desktop_locks.pop(path))
            released = subprocess.run([sys.executable, "-B", "-c", code, directory],
                                      capture_output=True, text=True)
            self.assertEqual(released.returncode, 0, released.stderr)

    def test_legacy_activation_refuses_before_storage_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(storage, "acquire_desktop_preview_lock",
                              side_effect=storage.PreviewStorageError("already running")):
                with patch.object(storage, "prepare_shared_preview") as prepare:
                    with self.assertRaisesRegex(RuntimeError, "already running"):
                        storage.activate_desktop_preview(home=home)
                    prepare.assert_not_called()

    def test_open_gate_refused_before_storage_activation(self):
        with patch("vrhub.fatekeeper_commit.live_install_authorized", return_value=True):
            with patch("vrhub.dev_preview_storage.activate_desktop_preview") as activate:
                with self.assertRaisesRegex(RuntimeError, "closed production gate"):
                    dev_preview.main()
                activate.assert_not_called()

    def test_dirty_tree_refused(self):
        with patch("vrhub.fatekeeper_commit.live_install_authorized", return_value=False):
            with patch("vrhub.dev_preview.subprocess.check_output",
                       side_effect=["checkpoint", " M tracked.py"]):
                with patch("vrhub.dev_preview_storage.activate_desktop_preview") as activate:
                    with self.assertRaisesRegex(RuntimeError, "working tree"):
                        dev_preview.main()
                    activate.assert_not_called()
