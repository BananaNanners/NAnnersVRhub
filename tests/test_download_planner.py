# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A: safe preferences, local inventory and pinned archive verification."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import download_planner as planner, hub


class DownloadPlannerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.library = self.root / "library"
        self.library.mkdir()
        self.prefpath = self.root / "prefs.json"
        patcher = mock.patch.object(planner, "preferences_file",
                                    return_value=self.prefpath)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.recipes = hub.load_recipes()
        planner._HASH_MEMO.clear()

    def put(self, name, payload=b"archive fixture", *, directory=None):
        parent = directory or self.library
        parent.mkdir(parents=True, exist_ok=True)
        path = parent / name
        path.write_bytes(payload)
        return path

    def test_no_settings_written_by_plain_read_or_scan(self):
        self.assertEqual(planner.load_preferences(),
                         {"schema": 1, "global": None, "games": {}})
        with mock.patch.object(planner, "default_library",
                               return_value=self.library):
            where, source = planner.folder_for(self.recipes["cyberpunk-2077"])
            self.assertEqual(where, self.library)
            self.assertIn("Downloads default", source)
            planner.build_plan(self.recipes["cyberpunk-2077"], self.library)
        self.assertFalse(self.prefpath.exists())

    def test_global_and_game_folder_preference_round_trip(self):
        other = self.root / "game-specific"
        other.mkdir()
        planner.set_location("global", str(self.library))
        p = planner.load_preferences()
        self.assertEqual(p["global"], str(self.library))
        planner.set_location("game", str(other), "subnautica")
        self.assertEqual(planner.folder_for(self.recipes["subnautica"])[0], other)
        self.assertEqual(planner.folder_for(self.recipes["valheim"])[0], self.library)
        self.assertEqual(planner.folder_for(self.recipes["subnautica"])[1],
                         "Per-game override")
        planner.set_location("game", None, "subnautica")
        self.assertEqual(planner.folder_for(self.recipes["subnautica"])[0], self.library)
        planner.set_location("global", None)
        self.assertIsNone(planner.load_preferences()["global"])
        self.assertEqual(self.prefpath.stat().st_mode & 0o777, 0o600)

    def test_invalid_preferences_cannot_be_overwritten(self):
        self.prefpath.write_text('{"schema":7,"global":"/tmp","games":{}}')
        old = self.prefpath.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "manual review"):
            planner.set_location("global", str(self.library))
        self.assertEqual(self.prefpath.read_bytes(), old)

    def test_symlinked_preferences_blocked(self):
        actual = self.root / "real.json"
        actual.write_text("{}")
        self.prefpath.symlink_to(actual)
        with self.assertRaises(RuntimeError):
            planner.load_preferences()
        with self.assertRaises(RuntimeError):
            planner.set_location("global", str(self.library))
        self.assertEqual(actual.read_text(), "{}")

    def test_invalid_game_and_folder_are_rejected(self):
        for rid in ("../escape", "bad id", "", "/tmp/a"):
            with self.subTest(rid=rid):
                with self.assertRaises(ValueError):
                    planner.set_location("game", str(self.library), rid)
        for loc in ("/", "../relative", "relative", "/tmp/not\nnormal"):
            with self.subTest(path=loc):
                with self.assertRaises(ValueError):
                    planner.set_location("global", loc)
        with self.assertRaises(ValueError):
            planner.set_location("global", str(self.root / "missing"))

    def test_all_nine_recipes_have_a_plan_without_installs(self):
        for rid, recipe in self.recipes.items():
            with self.subTest(game=rid):
                plan = planner.build_plan(recipe, self.library)
                self.assertEqual(plan["game_id"], rid)
                self.assertTrue(plan["rows"])
                self.assertEqual(plan["scanned"], 0)
                self.assertTrue(all(x["status"] == "Not found locally"
                                    for x in plan["rows"]))

    def test_cyberpunk_uses_nexus_id_without_substring_false_match(self):
        self.put("Cyber Engine Tweaks-107-1-37-1.zip")
        self.put("unrelated-1107-1-2-3.zip")
        self.put("RED4ext-2380-1-30-0.zip")
        plan = planner.build_plan(self.recipes["cyberpunk-2077"], self.library)
        rows = {x["id"]: x for x in plan["rows"]}
        self.assertEqual(len(rows), 15)
        self.assertIn("107", rows)
        self.assertTrue(rows["107"]["file"].endswith("Cyber Engine Tweaks-107-1-37-1.zip"))
        self.assertEqual(rows["107"]["status"], "Possible archive — inspect first")
        self.assertEqual(rows["2380"]["status"], "Possible archive — inspect first")
        self.assertEqual(rows["30093"]["phase"], 2)
        self.assertIn("Later", rows["30093"]["phase_label"])
        self.assertEqual(plan["verified"], 0)

    def test_pinned_hash_matches_renamed_archive_not_name(self):
        payload = b"exact byte sequence known by recipe"
        expected = hashlib.sha256(payload).hexdigest()
        recipe = {"id": "testgame", "method": "bepinex", "packages": [
            {"id": "loader", "name": "Loader", "sha256": expected,
             "page": "https://example.org/official", "required_files": ["a"]}
        ]}
        src = self.put("totally-renamed-binary.zip", payload)
        before = src.read_bytes()
        plan = planner.build_plan(recipe, self.library)
        self.assertEqual(plan["verified"], 1)
        self.assertEqual(plan["rows"][0]["file"], str(src))
        self.assertEqual(plan["rows"][0]["status"], "Pinned SHA-256 verified")
        self.assertEqual(src.read_bytes(), before)
        self.assertFalse(self.prefpath.exists())

    def test_pinned_hash_mismatch_is_blocked_not_trusted(self):
        recipe = {"id": "subnautica", "method": "bepinex", "packages": [
            {"id": "submersedvr", "name": "SubmersedVR",
             "sha256": "a" * 64, "required_files": ["x"]},
        ]}
        self.put("SubmersedVR_0.2.1.zip", b"incorrect archive")
        plan = planner.build_plan(recipe, self.library)
        self.assertEqual(plan["mismatch"], 1)
        self.assertEqual(plan["verified"], 0)
        self.assertEqual(plan["rows"][0]["status"], "Hash mismatch — do not install")

    def test_hash_budget_prevents_falsely_claiming_mismatch(self):
        recipe = {"id": "testgame", "method": "bepinex", "packages": [
            {"id": "loader", "name": "Pinned Loader", "sha256": "a" * 64}
        ]}
        self.put("BepInEx-Foo.zip", b"test content")
        with mock.patch.object(planner, "MAX_HASH_BYTES", 2):
            plan = planner.build_plan(recipe, self.library)
        self.assertEqual(plan["verified"], 0)
        self.assertEqual(plan["mismatch"], 0)
        self.assertEqual(plan["unverified"], 1)
        self.assertEqual(plan["rows"][0]["status"],
                         "Hash not verified — do not install")

    def test_game_subfolders_scanned_but_symlink_dirs_not_followed(self):
        other = self.root / "external"
        other.mkdir()
        self.put("RED4ext-2380-1-30.zip", directory=other)
        (self.library / "symlinked").symlink_to(other, target_is_directory=True)
        nested = self.library / "Cyberpunk-2077" / "extra"
        self.put("CET-107-1-37.zip", directory=nested)
        plan = planner.build_plan(self.recipes["cyberpunk-2077"], self.library)
        self.assertEqual(plan["scanned"], 1)
        self.assertEqual(plan["possible"], 1)
        self.assertEqual(plan["missing"], 14)

    def test_missing_library_is_warning_not_error_or_creation(self):
        missing = self.root / "not-here"
        plan = planner.build_plan(self.recipes["valheim"], missing)
        self.assertIn("unavailable", plan["warning"])
        self.assertEqual(plan["scanned"], 0)
        self.assertFalse(missing.exists())

    def test_limit_prevents_unbounded_archive_traversal(self):
        for i in range(16):
            self.put(f"random-{i}.zip")
        with mock.patch.object(planner, "MAX_FILES", 10):
            result = planner.build_plan(self.recipes["valheim"], self.library)
        self.assertEqual(result["scanned"], 10)
        self.assertIn("limit reached", result["warning"])

    def test_external_urls_are_explicit_https_only(self):
        for url in ("file:///etc/passwd", "https://u:p@example.org/test",
                    "javascript:alert(1)", "http://example.org/release"):
            self.assertFalse(planner.source_url(url))
        self.assertEqual(planner.source_url("https://github.com/example/release"),
                         "https://github.com/example/release")

    def test_real_library_pinned_hashes_checked_read_only(self):
        # A real-data test, skipped on other hosts where the archive library is absent.
        library = Path.home() / "Downloads/Organized/Archive-Library/VR-Mods"
        if not library.is_dir() or "VR-Mods" not in str(library):
            self.skipTest("User's existing VR-Mods folder not mounted")
        for rid, expected in (("subnautica", 2), ("valheim", 2), ("elden-ring", 1)):
            with self.subTest(rid=rid):
                report = planner.build_plan(self.recipes[rid], library)
                self.assertEqual(report["verified"], expected)
                self.assertEqual(report["mismatch"], 0)


if __name__ == "__main__":
    unittest.main()
