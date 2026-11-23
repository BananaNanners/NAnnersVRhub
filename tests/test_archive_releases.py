# SPDX-License-Identifier: GPL-3.0-only
"""Release identity is evidence, not permission or recipe pin substitution."""
import copy
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from vrhub import archive_releases as releases, archive_scans as scans
from vrhub import download_planner as planner, hub


def release(tag, day, payload, name="SLASHER-Win64-Shipping.zip"):
    return {"tag_name": tag, "published_at": f"2026-10-{day:02}T00:00:00Z",
            "draft": False, "prerelease": False,
            "assets": [{"name": name, "size": len(payload),
                        "digest": "sha256:" + hashlib.sha256(payload).hexdigest()}]}


from tests.fatekeeper_fixtures import recipes as fixture_recipes


class ReleaseRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.recipe = fixture_recipes()["fatekeeper"]
        self.source = self.recipe["archive_releases"]["profile"]
        self.old = release("1.0.0", 1, b"old")
        self.latest = release("v1.0.4", 4, b"new")

    def put(self, name, payload, stamp=100):
        p = self.folder / name
        p.write_bytes(payload)
        os.utime(p, (stamp, stamp))
        return p

    def plan(self, history=None):
        catalog = releases.asset_catalog(self.source, history or [self.old, self.latest])
        return planner.build_plan(self.recipe, self.folder, release_catalogs={"profile": catalog})

    def test_expected_release_wins_over_alphabet_and_mtime(self):
        self.put("SLASHER-Win64-Shipping (1).zip", b"old", 900)
        newest_release = self.put("SLASHER-Win64-Shipping (2).zip", b"new", 100)
        self.put("SLASHER-Win64-Shipping (3).zip", b"unknown", 999)
        row = self.plan()["rows"][1]
        self.assertEqual(row["file"], str(newest_release))
        self.assertEqual(row["status"], "Possible archive — inspect first")
        self.assertEqual(row["release_expected"], "v1.0.4")
        self.assertTrue(row["candidates"][0]["expected"])
        self.assertFalse(row["ambiguous"])
        self.assertEqual(self.plan()["verified"], 0)

    def test_identical_copies_are_one_candidate_newest_modified(self):
        self.put("SLASHER-Win64-Shipping (1).zip", b"new", 100)
        recent = self.put("SLASHER-Win64-Shipping (2).zip", b"new", 900)
        row = self.plan()["rows"][1]
        self.assertEqual(row["file"], str(recent))
        self.assertEqual(row["matches"], 2)
        self.assertEqual(len(row["candidates"]), 1)
        self.assertEqual(row["candidates"][0]["copies"], 2)

    def test_no_matching_expected_release_requires_choice_for_distinct_files(self):
        older = self.put("SLASHER-Win64-Shipping.zip", b"old", 100)
        self.put("SLASHER-Win64-Shipping (1).zip", b"unknown", 900)
        row = self.plan()["rows"][1]
        self.assertEqual(row["file"], str(older))
        self.assertTrue(row["ambiguous"])
        self.assertFalse(any(c["expected"] for c in row["candidates"]))

    def test_offline_newest_modified_is_suggestion_only(self):
        self.put("SLASHER-Win64-Shipping (1).zip", b"old", 100)
        recent = self.put("SLASHER-Win64-Shipping (2).zip", b"new", 900)
        row = planner.build_plan(self.recipe, self.folder,
                                 release_errors={"profile": "Offline"})["rows"][1]
        self.assertEqual(row["file"], str(recent))
        self.assertTrue(row["ambiguous"])
        self.assertEqual(row["release_notice"], "Offline")
        self.assertEqual(row["candidates"][0]["tags"], [])

    def test_missing_latest_digest_does_not_promote_old_release(self):
        latest = copy.deepcopy(self.latest)
        latest["assets"][0]["digest"] = None
        self.put("SLASHER-Win64-Shipping.zip", b"old")
        row = self.plan([self.old, latest])["rows"][1]
        self.assertEqual(row["release_expected"], "v1.0.4")
        self.assertEqual(row["candidates"][0]["tags"], ["1.0.0"])
        self.assertFalse(row["candidates"][0]["expected"])

    def test_only_exact_stable_assets_and_fixed_bundle_policy(self):
        draft = release("v2", 7, b"draft"); draft["draft"] = True
        pre = release("v3", 8, b"pre"); pre["prerelease"] = True
        wrong = release("v4", 9, b"wrong", "Other.zip")
        cat = releases.asset_catalog(dict(self.source, fixed_tag="1.0.0"),
                                     [self.latest, draft, pre, wrong, self.old])
        self.assertEqual(cat["expected"], "1.0.0")
        self.assertEqual([x["tag"] for x in cat["assets"]], ["v1.0.4", "1.0.0"])
        self.assertTrue(cat["fixed"])

    def test_metadata_fetch_one_per_repo_and_fail_soft(self):
        with mock.patch.object(releases, "fetch_history", return_value=[]) as fetch:
            result, errors = releases.catalogs_for(self.recipe)
        fetch.assert_called_once_with("jbusfield/FK_UEVR")
        self.assertEqual(set(result), {"profile", "uevr"})
        self.assertFalse(errors)
        with mock.patch.object(releases, "fetch_history", side_effect=OSError("offline")) as fetch:
            result, errors = releases.catalogs_for(self.recipe)
        fetch.assert_called_once()
        self.assertEqual(set(errors), {"profile", "uevr"})
        self.assertFalse(result)

    def test_pinned_rule_still_blocks_wrong_hash(self):
        self.put("vhvr.zip", b"new")
        recipe = {"id": "test", "method": "bepinex", "packages": [
            {"id":"vhvr", "name":"VHVR", "sha256": "a"*64}]}
        row = planner.build_plan(recipe, self.folder,
                                 release_catalogs={"vhvr": releases.asset_catalog(self.source,[self.latest])})["rows"][0]
        self.assertEqual(row["status"], "Hash mismatch — do not install")

    def test_changed_alternate_candidate_invalidates_saved_selection(self):
        old = self.put("SLASHER-Win64-Shipping.zip", b"old")
        self.put("SLASHER-Win64-Shipping (1).zip", b"new")
        plan = self.plan()
        with mock.patch.object(scans, "snapshot_file", return_value=self.folder / "scans.json"):
            record = scans.persist(plan)
            before = (self.folder / "scans.json").read_bytes()
            old.write_bytes(b"tampered")
            shown = scans.displayed_record(scans.load_saved()["fatekeeper"])["plan"]["rows"][1]
            self.assertEqual(shown["status"], "Archive changed — rescan required")
            self.assertFalse(shown["candidates"])
            self.assertEqual((self.folder / "scans.json").read_bytes(), before)

    def test_same_size_and_mtime_replacement_cannot_reuse_cached_hash(self):
        p = self.put("SLASHER-Win64-Shipping.zip", b"new", 100)
        self.assertTrue(self.plan()["rows"][1]["candidates"][0]["expected"])
        p.write_bytes(b"old")
        os.utime(p, (100,100))
        row = self.plan()["rows"][1]
        self.assertEqual(row["candidates"][0]["tags"], ["1.0.0"])
        self.assertFalse(row["candidates"][0]["expected"])

    def test_candidate_limit_fails_closed(self):
        for i in range(planner.MAX_CANDIDATES+1):
            self.put(f"SLASHER-Win64-Shipping ({i}).zip", str(i).encode())
        row = self.plan()["rows"][1]
        self.assertTrue(row["candidate_incomplete"])
        self.assertFalse(row["file"])
