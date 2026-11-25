"""Player-facing guide regression checks; no game or network writes."""
import html
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit
from vrhub import hub
from vrhub.schema import validate_recipe, RecipeError

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.append(dict(attrs).get("href"))

class SetupGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = hub.load_recipes()

    def test_all_nine_guides_render_every_section_and_step(self):
        self.assertEqual(len(self.recipes), 9)
        for key, recipe in self.recipes.items():
            with self.subTest(game=key):
                rendered = hub.details_html(recipe)
                plain = hub.details_text(recipe)
                for title, section, _ in hub.SECTIONS:
                    self.assertTrue(recipe[section])
                    self.assertIn(title, rendered)
                    self.assertIn(title, plain)
                    for step in recipe[section]:
                        self.assertIn(html.escape(step), rendered)
                        self.assertIn(step, plain)

    def test_named_source_pages_render_once(self):
        for key, recipe in self.recipes.items():
            with self.subTest(game=key):
                links = hub.setup_guide_links(recipe)
                self.assertTrue(links)
                urls = [url for _, url in links]
                self.assertEqual(len(urls), len(set(urls)))
                parser = AnchorParser()
                parser.feed(hub.details_html(recipe))
                for label, url in links:
                    self.assertNotIn(label, ("Mod page", "Profile page"))
                    self.assertEqual(urlsplit(url).scheme, "https")
                    self.assertNotIn("/releases/download/", url)
                    self.assertFalse(urlsplit(url).path.lower().endswith((".zip", ".exe", ".dll")))
                    self.assertEqual(parser.urls.count(url), 1)
                    self.assertIn(label + ": " + url, hub.details_text(recipe))

    def test_skyrim_guide_is_top_level(self):
        r = self.recipes["skyrim-vr-mgo"]
        self.assertTrue(all(k in r for k in ("setup", "play", "good_to_know")))
        self.assertFalse(any("setup" in x for x in r["links"]))
        self.assertIn("Disable Dynamic Resolution", hub.details_text(r))

    def test_existing_recipes_without_guide_links_keep_legacy_links(self):
        r = {"mod_page": "https://example.com/mod", "profile": {"page": "https://example.com/profile"}}
        self.assertEqual(hub.setup_guide_links(r), [
            ("Mod page", r["mod_page"]), ("Profile page", r["profile"]["page"])])

    def test_rejects_invalid_guide_links(self):
        for links in ([], "bad", [{"label": "", "url": "https://example.com"}],
                      [{"label": "Bad", "url": "file:///etc/passwd"}]):
            with self.subTest(links=links), self.assertRaises(RecipeError):
                validate_recipe({"id": "x", "name": "X", "steam_appid": 1,
                                 "guide_links": links})

    def test_gate_and_offline_messages_preserved(self):
        for key in ("fatekeeper", "hogwarts-legacy"):
            self.assertIn("blocked in this preview", hub.details_text(self.recipes[key]))
        self.assertIn("offline-only", hub.details_text(self.recipes["elden-ring"]))
        self.assertIn("No third ZIP or manual DLL copying", hub.details_text(self.recipes["fatekeeper"]))
