# SPDX-License-Identifier: GPL-3.0-only
"""Audited presentation inventory, never a permission or readiness decision."""
from types import MappingProxyType

OPERATIONS = ("version_check", "install_review", "install", "integrity",
              "recognition", "repair", "update", "original_restore",
              "latest_rollback", "persistent_recovery")
I, R, N, E = "implemented", "restricted", "unsupported", "external"
_ROWS = {
    "fatekeeper":      (I,I,R,I,I,R,R,N,R,R),
    "hogwarts-legacy": (I,I,R,R,N,N,R,R,N,N),
    "subnautica":     (I,I,I,I,R,N,N,I,N,N),
    "valheim":        (I,I,I,I,R,N,N,I,N,N),
    "elden-ring":     (I,I,R,I,R,N,N,I,N,N),
    "ready-or-not":   (I,I,I,R,N,N,N,I,N,N),
    "cyberpunk-2077": (I,I,I,I,R,N,N,I,N,N),
    "doom-2016-gog":  (I,R,R,R,R,N,N,R,N,N),
    "skyrim-vr-mgo":  (I,E,E,R,R,E,E,E,E,E),
}
CAPABILITIES = MappingProxyType({
    game: MappingProxyType(dict(zip(OPERATIONS, values, strict=True)))
    for game, values in _ROWS.items()
})


def capabilities(game_id):
    """Unknown recipes fail closed; callers must still use handler guards."""
    return CAPABILITIES.get(game_id, MappingProxyType(dict.fromkeys(OPERATIONS, N)))


def restoration_presentation(recipe):
    """Describe existing controls, not authorization or backup readiness."""
    recipe = recipe or {}
    caps = capabilities(recipe.get("id"))
    latest = caps["latest_rollback"] in (I, R) and bool(recipe.get("archive_pins"))
    original = caps["original_restore"] in (I, R)
    profile = original and bool(recipe.get("profile")) and not latest
    generic = original and not profile and recipe.get("method") != "guide"
    return {
        "mod_visible": latest or generic,
        "mod_label": "Restore previous installation" if latest else "Review removal and restoration",
        "mod_tip": ("Review reversal of the latest managed installation, repair or update."
                    if latest else "Remove recorded mod files and restore backed-up originals where available."),
        "profile_visible": profile,
        "profile_label": "Restore original profile",
    }


def maintenance_guidance(game_id):
    caps = capabilities(game_id)
    if caps["original_restore"] == E:
        return "Use your external mod manager for installation and maintenance."
    if caps["latest_rollback"] in (I, R):
        return "Latest-transaction rollback is distinct from a full mod uninstall."
    if caps["original_restore"] in (I, R):
        if game_id == "doom-2016-gog":
            return "Use the existing KHARVOX setup and recovery guidance."
        return "Original restoration depends on the recorded installation and available backups."
    return "No Hub restoration workflow is available for this game."


def update_guidance(game_id):
    """Version discovery is independent of managed update support."""
    status = capabilities(game_id)["update"]
    return {
        I: "Review the proposed update before installing.",
        R: "Managed updates require compatibility and safety review; finding a newer version does not approve installation.",
        N: "The Hub checks versions, but does not yet support managed updates for this game.",
        E: "Apply updates through your external mod manager.",
    }[status]
