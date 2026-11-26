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
