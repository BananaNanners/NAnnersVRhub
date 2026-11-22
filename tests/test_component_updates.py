# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Offline tests for independent Cyberpunk dependency update checks."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import hub, updates
from vrhub.schema import RecipeError, validate_recipe


class CyberpunkComponentUpdates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.recipe = hub.load_recipes()["cyberpunk-2077"]
        self.state = {"cyberpunk-2077": {"installed_at": 9999999999, "components": {}}}
        self.invocations = []

    def install(self, mod_id=2380, archive="RED4ext-2380-1-30-0-1773082858.zip"):
        p = Path(self.tmp.name) / str(mod_id)
        p.write_bytes(b"mock-only")
        self.state["cyberpunk-2077"]["components"][str(mod_id)] = {
            "files": [str(p)], "installed_at": 9999999999, "archive": archive
        }
        return p

    def fetch(self, game, mod_id, key):
        self.invocations.append(mod_id)
        return {"tag": "1.31.1", "published": "2026-11-11T08:00:00Z",
                "url": f"https://www.nexusmods.com/{game}/mods/{mod_id}"}

    def result(self, mod_id=2380, nexus_key="test-key"):
        rows = updates.check_recipe(self.recipe, self.state, nexus_fetch=self.fetch, nexus_key=nexus_key)
        self.assertEqual(len(rows), 15)
        return next(row for row in rows if row["page"].endswith(f"/{mod_id}"))

    def test_all_15_components_checked_once(self):
        targets = updates._update_targets(self.recipe, self.state)
        ids = [t["nexus_mod"] for t in targets]
        self.assertEqual(len(ids), 15)
        self.assertEqual(set(ids), {c["nexus_mod"] for c in self.recipe["components"]})
        self.assertEqual(ids.count(30093), 1)

    def test_missing_components_not_claimed_current(self):
        rows = updates.check_recipe(self.recipe, self.state, nexus_fetch=self.fetch, nexus_key="test-key")
        self.assertEqual({x["status"] for x in rows}, {"not_installed"})
        self.assertEqual(self.invocations, [])

    def test_old_archive_installed_today_still_reports_update(self):
        self.install()
        row = self.result()
        self.assertEqual(row["status"], "update")
        self.assertIn("1.30.0", row["detail"])
        self.assertIn("1.31.1", row["detail"])
        self.assertEqual(row["installed_version"], "1.30.0")
        self.assertEqual(row["latest_version"], "1.31.1")
        self.assertEqual(row["mod_id"], 2380)
        self.assertEqual(self.invocations, [2380])

    def test_current_version_uses_per_mod_archive(self):
        self.install(archive="RED4ext 2380 1.31.1 2026-11-11T07-28Z aI50IA8dZ.zip")
        self.assertEqual(self.result()["status"], "current")

    def test_nonstandard_archive_cannot_be_marked_current(self):
        self.install(archive="unversioned-package-2380.zip")
        self.assertEqual(self.result()["status"], "unknown")

    def test_remote_nonstandard_version_cannot_be_marked_current(self):
        self.install()
        self.fetch = lambda game, mod_id, key: {
            "tag": "release-candidate-a", "published": "2026-11-11T08:00:00Z"}
        self.assertEqual(self.result()["status"], "unknown")

    def test_newer_installed_than_nexus_is_unknown_not_current(self):
        self.install(archive="RED4ext 2380 1.32.0 2026-11-11T07-28Z xx.zip")
        self.assertEqual(self.result()["status"], "unknown")

    def test_deleted_installed_files_do_not_query_nexus(self):
        p = self.install()
        p.unlink()
        self.assertEqual(self.result()["status"], "unknown")
        self.assertEqual(self.invocations, [])

    def test_no_api_key_is_explained_for_installed_mod(self):
        self.install()
        self.assertEqual(self.result(nexus_key=None)["status"], "no_key")
        self.assertEqual(self.invocations, [])

    def test_archive_version_formats_cover_saved_mods(self):
        samples = {
            107: ("CET 1.37.1 - Scripting fixes-107-1-37-1-1759193708.zip", (1, 37, 1)),
            1511: ("redscript-1511-0-5-31-1757113888.zip", (0, 5, 31)),
            2380: ("RED4ext-2380-1-30-0-1773082858.zip", (1, 30, 0)),
            4197: ("TweakXL 4197 1.12.2 2026-11-13T09-01Z bWY.zip", (1, 12, 2)),
            4198: ("ArchiveXL 4198 1.27.3 2026-09-07T10-15Z.zip", (1, 27, 3)),
            4575: ("input_loader_v0.2.3.zip-4575-0-2-3-1752939429.zip", (0, 2, 3)),
            7780: ("Codeware 7780 1.20.5 2026-09-20T08-20Z.zip", (1, 20, 5)),
            29190: ("Nova Optics 29190 1.4.2 2026-10-26T04-18Z.zip", (1, 4, 2)),
            6945: ("Equipment-EX 6945 1.3.1 2026-11-13T09-03Z.zip", (1, 3, 1)),
            21936: ("Visual Holsters-21936-1-2-1751235859.zip", (1, 2)),
            18002: ("Military Pistol Holsters-18002-1-5-1757023050.zip", (1, 5)),
            22071: ("hip katana-22071-1-4-1770525462.zip", (1, 4)),
            22251: ("Visible Bullets 2.31-22251-2-31-1757609845.zip", (2, 31)),
            33136: ("More Occluders (ArchiveXL) 33136 0.4 2026-08-28T02-58Z.rar", (0, 4)),
            30093: ("CyberpunkVRPort 30093 0.2.45 2026-11-14T16-48Z.zip", (0, 2, 45)),
        }
        for mod_id, (archive, wanted) in samples.items():
            with self.subTest(mod=mod_id):
                self.assertEqual(updates._installed_archive_version(archive, mod_id), wanted)
                self.assertIsNone(updates._installed_archive_version(archive, mod_id + 1))

    def test_numeric_version_sorting_and_padding(self):
        self.assertEqual(updates._ordered_numeric((1, 2, 10), (1, 2, 9)), 1)
        self.assertEqual(updates._ordered_numeric((1, 2), (1, 2, 0)), 0)
        self.assertEqual(updates._ordered_numeric((1, 2, 3), (1, 2, 4)), -1)
        self.assertIsNone(updates._release_version("something else"))

    def test_legacy_recipes_still_use_existing_date_comparison(self):
        legacy = {"id": "old", "updates": [{"name": "A", "nexus_game": "cyberpunk2077",
                                           "nexus_mod": 2380}]}
        state = {"old": {"installed_at": 1}}
        rows = updates.check_recipe(legacy, state, nexus_fetch=self.fetch, nexus_key="test-key")
        self.assertEqual(rows[0]["status"], "update")

    def test_grouped_ui_separates_outdated_from_current(self):
        def item(name, status, detail):
            return {"name": name, "status": status, "detail": detail,
                    "page": "https://www.nexusmods.com/cyberpunk2077/mods/1"}
        rows = [
            item("Newest Mod", "current", "Version matches Nexus: 1.2"),
            item("Old Mod", "update", "Update available: 1.0 → 1.2"),
            item("Unverified Mod", "unknown", "Version not comparable"),
            item("VR Port", "not_installed", "Not installed through the hub"),
        ]
        body = hub.details_html(self.recipe, rows)
        self.assertIn("Update status", body)
        self.assertIn("1 updates available</b> out of 4 tracked dependencies", body)
        self.assertIn("1 up to date; 1", body)
        self.assertIn("Read-only check.", body)
        self.assertIn("It does not download, install, remove", body)
        self.assertIn("Updates available (1)", body)
        self.assertIn("Up to date (1)", body)
        self.assertIn("Needs manual review (1)", body)
        self.assertIn("Not installed (1)", body)
        self.assertLess(body.index("Old Mod"), body.index("Newest Mod"))
        self.assertLess(body.index("Newest Mod"), body.index("Unverified Mod"))
        self.assertLess(body.index("<li><b>Unverified Mod</b>"), body.index("<li><b>VR Port</b>"))

    def test_legacy_update_ui_is_unchanged(self):
        older = dict(self.recipe)
        older.pop("track_component_updates")
        body = hub.details_html(older, [{
            "name": "Legacy", "status": "update",
            "detail": "Update available", "page": "https://example.com/mod",
        }])
        self.assertIn("<h3>Updates</h3>", body)
        self.assertNotIn("Update status", body)

    def test_mark_current_does_not_hide_component_updates_or_write_state(self):
        state = Path(self.tmp.name) / "state.json"
        state.write_text(json.dumps(self.state))
        before = state.read_bytes()
        with mock.patch.dict(os.environ, {"VRHUB_STATE": str(state)}):
            self.assertEqual(hub.mark_current(self.recipe), [])
        self.assertEqual(state.read_bytes(), before)

    def test_invalid_tracking_flag_fails_recipe_validation(self):
        recipe = dict(self.recipe, track_component_updates="yes")
        with self.assertRaisesRegex(RecipeError, "track_component_updates"):
            validate_recipe(recipe)

    def test_non_gameroot_tracking_flag_fails_recipe_validation(self):
        recipe = dict(self.recipe, method="guide")
        with self.assertRaisesRegex(RecipeError, "components are currently supported"):
            validate_recipe(recipe)


if __name__ == "__main__":
    unittest.main()
