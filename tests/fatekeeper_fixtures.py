from pathlib import Path
import tomllib

from vrhub import hub


def recipes():
    """Historical, unpinned recipe for old archive and saved-scan regression cases."""
    result = hub.load_recipes()
    with Path(__file__).with_name("fatekeeper_legacy_recipe.toml").open("rb") as stream:
        result["fatekeeper"] = tomllib.load(stream)
    return result
