"""Fatekeeper bundle and profile remain separate; source display is read-only."""
import unittest
from vrhub import hub, updates, download_planner

BASE = "https://github.com/jbusfield/FK_UEVR/releases"
MOD = BASE + "/tag/1.0.0"
PROFILE = BASE + "/tag/v1.0.4"


class FatekeeperSourceTests(unittest.TestCase):
    def setUp(self):
        self.recipe = hub.load_recipes()["fatekeeper"]

    def test_independent_bundle_and_profile_sources(self):
        mod, profile = self.recipe["updates"]
        self.assertEqual(mod["manual"], MOD)
        self.assertEqual(mod["tracks"], ["fatekeeper"])
        self.assertEqual(mod["available_version"], "1.0.0")
        self.assertEqual(profile["github"], "jbusfield/FK_UEVR")
        self.assertEqual(profile["tracks"], ["fatekeeper:profile"])

    def test_profile_refresh_does_not_reclassify_mod_bundle(self):
        seen = []
        def fetch(repo):
            seen.append(repo)
            return {"tag": "v1.0.4", "published": "2026-11-20T00:00:00Z",
                    "url": BASE+"/tag/v1.0.4"}
        rows = updates.check_recipe(self.recipe, {
            "fatekeeper": {"installed_at": 9999999999},
            "fatekeeper:profile": {"installed_at": 1}}, fetch=fetch)
        self.assertEqual(seen, ["jbusfield/FK_UEVR"])
        self.assertEqual(rows[0]["page"], MOD)
        self.assertEqual(rows[0]["latest_version"], "1.0.0")
        self.assertEqual(rows[0]["status"], "unknown")
        self.assertNotIn("installed_version", rows[0])
        self.assertEqual(rows[1]["status"], "update")
        self.assertEqual(rows[1]["latest_version"], "v1.0.4")
        rows = updates.check_recipe(self.recipe, {"fatekeeper:profile":{"installed_at":1}}, fetch=fetch)
        self.assertEqual(rows[0]["status"], "not_installed")

    def test_guide_has_exactly_two_named_release_pages(self):
        self.assertEqual(self.recipe["links"], [
            {"label": "UEVR FK Mod", "url": MOD},
            {"label": "Fatekeeper VR Profile", "url": PROFILE},
        ])
        for guide in (hub.details_text(self.recipe), hub.details_html(self.recipe)):
            for url in (MOD, PROFILE):
                self.assertIn(url, guide)
            self.assertNotIn("praydog/UEVR-nightly", guide)
            self.assertNotIn("joeyhodge/UEVR/releases", guide)
            self.assertNotIn("OneStepLauncher", guide)
            self.assertNotIn("/releases/download/", guide)

    def test_historical_archive_sources_and_hints_unchanged(self):
        rows = download_planner.plan_components(self.recipe)
        self.assertEqual([(r["id"], r["hint"]) for r in rows],
                         [("uevr", "uevr_fk"), ("profile", "slasher")])
        self.assertTrue(all(r["url"] == BASE+"/tag/1.0.0" for r in rows))
        self.assertEqual(self.recipe["archive_display"]["uevr"]["url"], MOD)
        self.assertEqual(self.recipe["archive_display"]["profile"]["url"], PROFILE)
        self.assertNotIn("archive_release_link", self.recipe)
