"""Recipe validation for NAnnersVRhub.

Recipes are intentionally simple TOML, but validating them at load time keeps a
bad/new recipe from failing halfway through an install.
"""
from __future__ import annotations

from pathlib import Path


class RecipeError(RuntimeError):
    pass


def _need(recipe: dict, key: str, source: str) -> object:
    value = recipe.get(key)
    if value in (None, ""):
        raise RecipeError(f"{source}: missing required recipe field '{key}'")
    return value


def validate_recipe(recipe: dict, source: str = "recipe") -> dict:
    """Validate one parsed recipe and return it unchanged."""
    _need(recipe, "id", source)
    _need(recipe, "name", source)
    store = recipe.get("store", "steam")
    if store not in {"steam", "heroic-gog"}:
        raise RecipeError(f"{source}: unsupported store '{store}'")
    if store == "steam":
        appid = _need(recipe, "steam_appid", source)
        if not isinstance(appid, int) or appid <= 0:
            raise RecipeError(f"{source}: steam_appid must be a positive integer")
    else:
        appid = _need(recipe, "heroic_appid", source)
        if not str(appid).isdigit():
            raise RecipeError(f"{source}: heroic_appid must be a numeric GOG app id")

    method = recipe.get("method", "file")
    if method not in {"file", "gameroot", "uevr", "guide"}:
        raise RecipeError(f"{source}: unsupported method '{method}'")

    if method == "file":
        files = recipe.get("files")
        if not isinstance(files, list) or not files:
            raise RecipeError(f"{source}: file installs need at least one [[files]] rule")
        for i, rule in enumerate(files, 1):
            if not isinstance(rule, dict) or not rule.get("kind") or not rule.get("dest"):
                raise RecipeError(f"{source}: [[files]] #{i} needs kind and dest")


    handler = recipe.get("handler", "generic")
    if not isinstance(handler, str) or not handler:
        raise RecipeError(f"{source}: handler must be a non-empty string")
    # Imported lazily so schema.py stays lightweight and handlers can use Path/runtime helpers.
    from .handlers import handler_names
    if handler not in handler_names():
        raise RecipeError(f"{source}: unknown handler '{handler}'")

    links = recipe.get("links", [])
    if links and (not isinstance(links, list) or any(
            not isinstance(x, dict) or not x.get("label") or not x.get("url") for x in links)):
        raise RecipeError(f"{source}: [[links]] entries need label and url")

    handler_config = recipe.get("handler_config", {})
    if not isinstance(handler_config, dict):
        raise RecipeError(f"{source}: [handler_config] must be a table")

    components = recipe.get("components", [])
    if components and method != "gameroot":
        raise RecipeError(f"{source}: components are currently supported only with method='gameroot'")
    seen: set[int] = set()
    for i, comp in enumerate(components, 1):
        if not isinstance(comp, dict):
            raise RecipeError(f"{source}: component #{i} is not a table")
        mod = comp.get("nexus_mod")
        if not isinstance(mod, int) or mod <= 0:
            raise RecipeError(f"{source}: component #{i} needs a positive nexus_mod")
        if mod in seen:
            raise RecipeError(f"{source}: duplicate component nexus_mod {mod}")
        seen.add(mod)
        if not comp.get("name"):
            raise RecipeError(f"{source}: component #{i} needs a name")
        required = comp.get("required_files", [])
        if not isinstance(required, list) or any(not isinstance(p, str) or not p.strip() for p in required):
            raise RecipeError(f"{source}: component {mod} required_files must be a list of paths")
        for p in required:
            q = Path(p.replace("\\", "/"))
            if q.is_absolute() or ".." in q.parts:
                raise RecipeError(f"{source}: unsafe required_files path for component {mod}: {p}")

    root_dirs = recipe.get("root_dirs", [])
    if root_dirs and (not isinstance(root_dirs, list) or any(not isinstance(x, str) or not x for x in root_dirs)):
        raise RecipeError(f"{source}: root_dirs must be a list of directory names")

    profile = recipe.get("profile")
    if profile is not None and (not isinstance(profile, dict) or not profile.get("dir")):
        raise RecipeError(f"{source}: [profile] needs dir")

    requirements = recipe.get("requirements", {})
    if not isinstance(requirements, dict):
        raise RecipeError(f"{source}: [requirements] must be a table")
    if "openxr" in requirements and requirements["openxr"] not in {"any", "wivrn"}:
        raise RecipeError(f"{source}: requirements.openxr must be 'any' or 'wivrn'")
    if "proton_prefix" in requirements and not isinstance(requirements["proton_prefix"], bool):
        raise RecipeError(f"{source}: requirements.proton_prefix must be true/false")

    if "compatibility" in recipe:
        from .compatibility import validate
        validate(recipe["compatibility"], source)
        checks = recipe["compatibility"].get("checks", {})
        if checks and store != "steam":
            raise RecipeError(f"{source}: compatibility.checks currently require a Steam recipe")
        if checks.get("tracked_profile"):
            if not recipe.get("profile"):
                raise RecipeError(f"{source}: tracked_profile requires a recipe profile")
            profile_dir = Path(recipe["profile"]["dir"].replace("\\", "/"))
            if profile_dir.is_absolute() or ".." in profile_dir.parts or ":" in str(profile_dir):
                raise RecipeError(f"{source}: unsafe compatibility profile directory")
        expected = recipe["compatibility"]["runtime"]
        required = requirements.get("openxr")
        if (required == "wivrn" and expected not in {"WiVRn", "any"}):
            raise RecipeError(f"{source}: compatibility.runtime contradicts requirements.openxr")

    return recipe
