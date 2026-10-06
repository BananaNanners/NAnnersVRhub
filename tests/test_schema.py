import unittest

from vrhub.schema import RecipeError, validate_recipe


class RecipeSchemaTests(unittest.TestCase):
    def test_rejects_duplicate_components(self):
        recipe = {"id": "x", "name": "X", "steam_appid": 1, "method": "gameroot",
                  "components": [{"nexus_mod": 7, "name": "A"}, {"nexus_mod": 7, "name": "B"}]}
        with self.assertRaisesRegex(RecipeError, "duplicate"):
            validate_recipe(recipe)

    def test_rejects_unsafe_required_path(self):
        recipe = {"id": "x", "name": "X", "steam_appid": 1, "method": "gameroot",
                  "components": [{"nexus_mod": 7, "name": "A", "required_files": ["../oops.dll"]}]}
        with self.assertRaisesRegex(RecipeError, "unsafe"):
            validate_recipe(recipe)

    def test_accepts_existing_recipe_shape(self):
        recipe = {"id": "x", "name": "X", "steam_appid": 1,
                  "files": [{"kind": "pak", "dest": "Content/Paks"}],
                  "requirements": {"openxr": "wivrn", "proton_prefix": True}}
        self.assertIs(validate_recipe(recipe), recipe)


if __name__ == "__main__":
    unittest.main()

class RecipeSchema040Dev2Tests(unittest.TestCase):
    def test_accepts_guide_handler_recipe(self):
        recipe = {"id": "skyrim", "name": "Skyrim VR", "steam_appid": 611670,
                  "method": "guide", "handler": "skyrim-vr",
                  "links": [{"label": "Jackify", "url": "https://example.invalid"}],
                  "handler_config": {"mgo_dir_env": "NANNERS_MGO_DIR"}}
        self.assertIs(validate_recipe(recipe), recipe)

    def test_rejects_unknown_handler(self):
        recipe = {"id": "x", "name": "X", "steam_appid": 1, "method": "guide", "handler": "nope"}
        with self.assertRaisesRegex(RecipeError, "unknown handler"):
            validate_recipe(recipe)

class HeroicRecipeSchemaTests(unittest.TestCase):
    def test_accepts_heroic_gog_recipe_without_steam_appid(self):
        recipe = {"id": "doom", "name": "DOOM", "store": "heroic-gog",
                  "heroic_appid": "1390579243", "method": "guide", "handler": "heroic-gog"}
        self.assertIs(validate_recipe(recipe), recipe)

    def test_rejects_heroic_recipe_without_numeric_appid(self):
        recipe = {"id": "doom", "name": "DOOM", "store": "heroic-gog",
                  "heroic_appid": "not-an-id", "method": "guide", "handler": "heroic-gog"}
        with self.assertRaisesRegex(RecipeError, "heroic_appid"):
            validate_recipe(recipe)
