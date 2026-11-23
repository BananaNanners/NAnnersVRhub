"""Regression checks for the pinned Fatekeeper dependency workflow."""
import unittest

from vrhub import download_planner, hub
from vrhub.uevr_dependency_review import FATEKEEPER_BACKEND_SHA256, FATEKEEPER_BACKEND_URL


class FatekeeperSourceTests(unittest.TestCase):
    def setUp(self):
        self.recipe = hub.load_recipes()["fatekeeper"]

    def test_release_identity_and_pins(self):
        rows = download_planner.plan_components(self.recipe)
        self.assertEqual([r["id"] for r in rows], ["uevr", "profile"])
        self.assertIn("/praydog/UEVR-nightly/releases/tag/nightly-01133-", rows[0]["url"])
        self.assertTrue(rows[1]["url"].endswith("/FK_UEVR/releases/tag/v1.0.4"))
        self.assertEqual(rows[0]["sha256"], "a230efac51be0f7eaec77e08add970a89a0513a490ec1a130bfaaa5725f302e3")
        self.assertEqual(rows[1]["sha256"], "a4abe6e99f9eb9c1822163431c6eb20933f2baa2cc9dc497ed067b8aa5da129b")
        self.assertTrue(FATEKEEPER_BACKEND_URL.endswith("/100526UE58_6RefreshUpdate/UEVRBackend.dll"))
        self.assertEqual(FATEKEEPER_BACKEND_SHA256, "b883dd7f0b5e06bff74b42b4fabc66fc7c39c6baff57634d5132abe5b05ed6fc")

    def test_legacy_filename_does_not_match_new_component(self):
        injector, _ = download_planner.plan_components(self.recipe)
        for name in ("uevr.zip", "uevr (2).zip"):
            self.assertTrue(download_planner._candidate_filename_match(name, injector, "fatekeeper"))
        self.assertFalse(download_planner._candidate_filename_match("UEVR_FK.zip", injector, "fatekeeper"))
