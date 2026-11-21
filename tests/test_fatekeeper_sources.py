"""Fatekeeper's upstream injector and game profile are different dependencies."""
import unittest
from vrhub import hub, updates, download_planner


class FatekeeperSourceTests(unittest.TestCase):
    def setUp(self):
        self.recipe = hub.load_recipes()["fatekeeper"]

    def test_distinct_release_sources_and_state_keys(self):
        mod, profile = self.recipe["updates"]
        self.assertEqual(mod["github"], "praydog/UEVR-nightly")
        self.assertEqual(mod["tracks"], ["fatekeeper"])
        self.assertTrue(mod["upstream_reference"])
        self.assertEqual(profile["github"], "jbusfield/FK_UEVR")
        self.assertEqual(profile["tracks"], ["fatekeeper:profile"])

    def test_latest_mod_is_not_assumed_installed_or_compatible(self):
        seen = []
        def fetch(repo):
            seen.append(repo)
            return {"tag": "nightly-01143-test" if repo.startswith("praydog/") else "v1.0.4",
                    "published": "2026-11-20T00:00:00Z",
                    "url": "https://github.com/" + repo + "/releases"}
        rows = updates.check_recipe(self.recipe, {
            "fatekeeper": {"installed_at": 9999999999},
            "fatekeeper:profile": {"installed_at": 1}}, fetch=fetch)
        self.assertEqual(seen, ["praydog/UEVR-nightly", "jbusfield/FK_UEVR"])
        self.assertEqual(rows[0]["status"], "unknown")
        self.assertNotIn("installed_version", rows[0])
        self.assertEqual(rows[1]["status"], "update")
        self.assertEqual(rows[1]["latest_version"], "v1.0.4")
        only_mod = updates.check_recipe(self.recipe,
                  {"fatekeeper": {"installed_at": 9999999999}}, fetch=fetch)
        self.assertEqual(only_mod[1]["status"], "not_installed")

    def test_guide_explicitly_labels_both_requested_links(self):
        for guide in (hub.details_text(self.recipe), hub.details_html(self.recipe)):
            self.assertIn("https://github.com/praydog/UEVR-nightly/releases", guide)
            self.assertIn("https://github.com/jbusfield/FK_UEVR/releases", guide)
            self.assertIn("UEVR mod / injector (Praydog Nightly)", guide)
            self.assertIn("Fatekeeper VR profile (jbusfield)", guide)
            self.assertIn("1133", guide)
            self.assertIn("JoeyHodge", guide)
            self.assertNotIn(">Mod page</a>", guide)
            self.assertNotIn(">Profile page</a>", guide)

    def test_historical_archive_sources_and_hints_unchanged(self):
        rows = download_planner.plan_components(self.recipe)
        self.assertEqual([(r["id"], r["hint"]) for r in rows],
                         [("uevr", "uevr_fk"), ("profile", "slasher")])
        self.assertTrue(all(r["url"] ==
            "https://github.com/jbusfield/FK_UEVR/releases/tag/1.0.0"
            for r in rows))
