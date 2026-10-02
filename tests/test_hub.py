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


if __name__ == "__main__":
    unittest.main()
