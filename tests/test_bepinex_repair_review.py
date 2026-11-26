# SPDX-License-Identifier: GPL-3.0-only
"""Disposable review tests; no execution or adoption."""
import unittest
from pathlib import Path
from vrhub import bepinex_repair_review as review, bepinex, hub
from tests import test_subnautica, test_valheim


class Cases:
    def setUp(self):
        self.f = self.fixture_class()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.game = self.f.game
        self.recipe = self.f.recipe

    def scan(self, archives=None):
        before = {str(p): (p.stat().st_mode, p.read_bytes()) for p in
                  self.f.fixture.home.rglob("*") if p.is_file()}
        result = review.review(self.recipe, self.f.archives if archives is None else archives,
                               [self.f.fixture.steam])
        self.assertEqual(before, {str(p): (p.stat().st_mode, p.read_bytes()) for p in
                         self.f.fixture.home.rglob("*") if p.is_file()})
        for key in ("write_authorized", "ownership_established", "gameplay_verified"):
            self.assertFalse(result[key])
        self.assertEqual(sum(result["counts"].values()), len(result["rows"]))
        return result

    def test_clean_and_exact_candidates(self):
        self.f.install()
        result = self.scan()
        self.assertEqual(result["status"], "No repair proposed")
        self.assertEqual(result["counts"], {"Preserve":len(result["rows"])})
        (self.game/"winhttp.dll").write_bytes(b"changed")
        (self.game/"BepInEx/core/BepInEx.dll").unlink()
        cfg = self.game/"BepInEx/config/BepInEx.cfg"
        cfg.write_bytes(b"custom")
        binding = bepinex.policy(self.recipe)["data"]+"/StreamingAssets/SteamVR/bindings_oculus_touch.json"
        (self.game/binding).write_bytes(b"custom binding")
        self.f.fixture.file(self.game/"BepInEx/plugins/foreign.dll")
        result = self.scan()
        self.assertEqual(result["status"], "Review required")
        rows = {r["path"]:r for r in result["rows"]}
        self.assertEqual(rows["winhttp.dll"]["action"], "Proposed replacement")
        self.assertEqual(rows["BepInEx/core/BepInEx.dll"]["action"], "Proposed restore")
        self.assertEqual(rows[binding]["action"], "Preserve")
        self.assertEqual(rows["BepInEx/config/BepInEx.cfg"]["action"], "Preserve")
        self.assertNotIn("BepInEx/plugins/foreign.dll", rows)
        self.assertEqual(result["rows"], self.scan(list(reversed(self.f.archives)))["rows"])
        self.f.assert_preserved()

    def test_missing_protected_blocks_other_candidates(self):
        self.f.install()
        (self.game/"BepInEx/config/BepInEx.cfg").unlink()
        (self.game/"winhttp.dll").unlink()
        result = self.scan()
        self.assertEqual(result["status"], "Blocked")
        rows = {r["path"]:r["action"] for r in result["rows"]}
        self.assertEqual(rows["BepInEx/config/BepInEx.cfg"], "Manual review")
        self.assertEqual(rows["winhttp.dll"], "Blocked")

    def test_unrecorded_and_inconsistent(self):
        self.f.install()
        state = hub.state()
        original = state.pop(self.recipe["id"])
        hub._save_state(state)
        self.assertEqual(self.scan()["status"], "Blocked")
        original["file_hashes"]["winhttp.dll"] = "0"*64
        state[self.recipe["id"]] = original
        hub._save_state(state)
        (self.game/"winhttp.dll").unlink()
        result = self.scan()
        self.assertEqual(result["status"], "Blocked")
        self.assertNotIn("Proposed restore", result["counts"])

    def test_backup_and_conflict_block(self):
        self.f.fixture.file(self.game/"winhttp.dll").write_bytes(b"original")
        self.f.install()
        rec = hub.state()[self.recipe["id"]]
        (Path(rec["backup"])/"files/winhttp.dll").write_bytes(b"damaged")
        (self.game/"winhttp.dll").unlink()
        result = self.scan()
        self.assertEqual(result["status"], "Blocked")
        self.assertNotIn("Proposed restore", result["counts"])
        (Path(rec["backup"])/"files/winhttp.dll").write_bytes(b"original")
        conflict = ("BepInEx/plugins/VREnhancements.dll" if self.recipe["id"]=="subnautica"
                    else "BepInEx/plugins/duplicate/ValheimVRMod.dll")
        self.f.fixture.file(self.game/conflict)
        result = self.scan()
        self.assertTrue(result["conflicts"])
        self.assertEqual(result["status"], "Blocked")

    def test_unknown_archive_has_no_partial_manifest(self):
        result = self.scan(self.f.archives[:1])
        self.assertEqual(result["status"], "Blocked")
        self.assertFalse(result["rows"])
        self.assertTrue(result["blockers"])


class Subnautica(Cases, unittest.TestCase):
    fixture_class = test_subnautica.SubnauticaTests


class Valheim(Cases, unittest.TestCase):
    fixture_class = test_valheim.ValheimTests


class Scope(unittest.TestCase):
    def test_ervr_excluded(self):
        result = review.review({"id":"elden-ring"}, [])
        self.assertEqual(result["status"], "Blocked")
        self.assertFalse(result["rows"])
