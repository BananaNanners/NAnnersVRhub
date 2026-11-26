# SPDX-License-Identifier: GPL-3.0-only
"""Read-only candidate manifest. Never an execution plan or ownership grant."""
from collections import Counter
from . import bepinex_recognition as recognition


def review(recipe, archives, steam_roots=None):
    result = dict(game_id=recipe.get("id"), status="Blocked", rows=(),
                  counts={}, blockers=(), conflicts=(), write_authorized=False,
                  ownership_established=False, gameplay_verified=False,
                  outside_inventory="Leave untouched; not inventoried or certified.",
                  detail="Review only. No files will be changed.")
    evidence = recognition.recognize(recipe, archives, steam_roots)
    if evidence["status"] == "Unknown":
        return dict(result, blockers=(evidence["detail"],))
    blockers = []
    if evidence["ownership_record"] != "consistent-record":
        blockers.append("Complete matching Hub installation record required.")
    if evidence["backup_status"] != "originals-match":
        blockers.append("Recorded original backup evidence is incomplete or unsafe.")
    if evidence["conflicts"]:
        blockers.append("Known conflicting plugins require manual review.")
    if any(r["status"] == "missing" and r["protected_setting"] for r in evidence["rows"]):
        blockers.append("Missing protected settings or bindings require manual review.")
    rows = []
    for row in sorted(evidence["rows"], key=lambda r: (r["path"].casefold(), r["path"])):
        status = row["status"]
        if status == "matching":
            action, reason = "Preserve", "Matches pinned dependency bytes."
        elif row["protected_setting"]:
            if status == "missing":
                action, reason = "Manual review", "Protected file absent; do not recreate automatically."
            else:
                action, reason = "Preserve", "Possible player customization; do not overwrite."
        elif blockers:
            action, reason = "Blocked", "Resolve review blockers before considering repair."
        elif status == "missing":
            action, reason = "Proposed restore", "Recorded pinned file absent."
        else:
            action, reason = "Proposed replacement", "Recorded file differs from pinned bytes."
        rows.append(dict(row, action=action, reason=reason))
    counts = dict(Counter(r["action"] for r in rows))
    status = ("Blocked" if blockers else "Review required" if
              any(r["action"].startswith("Proposed") for r in rows) else "No repair proposed")
    return dict(result, status=status, rows=tuple(rows), counts=counts,
                blockers=tuple(blockers), conflicts=evidence["conflicts"],
                root=evidence["root"], sampled_at=evidence["sampled_at"],
                ownership_record=evidence["ownership_record"],
                backup_status=evidence["backup_status"],
                package_pins={p["id"]:p["sha256"] for p in recipe["packages"]})
