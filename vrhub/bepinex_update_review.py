# SPDX-License-Identifier: GPL-3.0-only
"""Read-only managed update foundation; no candidate pin substitution."""
from pathlib import Path
from . import (archive_releases, archive_update_comparison, download_planner,
               installed_provenance, bepinex_recognition, updates)


def review(recipe, folder, state, *, fetch=None, online=None):
    """Use existing scan and comparison contracts; metadata is not approval."""
    if recipe.get("id") not in bepinex_recognition.SUPPORTED:
        raise ValueError("Unsupported managed update recipe.")
    catalogs, errors = archive_releases.catalogs_for(recipe, fetch=fetch)
    plan = download_planner.build_plan(recipe, folder, release_catalogs=catalogs,
                                      release_errors=errors)
    comparison = archive_update_comparison.compare(recipe, plan, state, online)
    rows = {r["id"]: r for r in plan["rows"]}
    result = []
    for item in comparison:
        role = item["id"]
        package = next(p for p in recipe["packages"] if p["id"] == role)
        pin = installed_provenance._source_tag(recipe, package)
        catalog = catalogs.get(role, {})
        expected = catalog.get("expected")
        assets = [a for a in catalog.get("assets", []) if a["tag"] == expected]
        row = rows[role]
        candidate = None
        status = "No candidate identified"
        if role not in recipe.get("archive_releases", {}):
            status = "Manual release review"
        elif role in errors:
            status = "Release metadata unavailable"
        elif plan.get("warning") or row.get("ambiguous") or row.get("candidate_incomplete"):
            status = "Scan incomplete — review required"
        elif expected and len(assets) != 1:
            status = "Ambiguous release metadata"
        elif expected and not assets[0].get("sha256"):
            status = "Official digest unavailable"
        elif expected:
            asset = assets[0]
            old, new = updates._release_version(pin), updates._release_version(expected)
            order = updates._ordered_numeric(old, new) if old and new else None
            if asset["sha256"] == package["sha256"]:
                status = "Pinned archive identity — no new payload"
            elif expected == pin or order == 0:
                status = "Same release label — different digest; review required"
            elif order == 1:
                status = "Older release — review required"
            elif not catalog.get("newer_than_pin"):
                status = "Release ordering unverified"
            else:
                status = "New release — download or review"
                matches = [c for c in row.get("candidates", []) if
                           c.get("file") == row.get("file") and
                           c.get("sha256") == asset["sha256"] and
                           c.get("tags") == [expected] and c.get("expected")]
                if row.get("release_review") and len(matches) == 1:
                    # Re-read bounded immutable bytes, not filename/mtime.
                    try:
                        with bepinex_recognition._archive_snapshot(Path(row["file"])) as (_, sha, ident):
                            if sha != asset["sha256"] or ident[4] != asset["size"]:
                                raise RuntimeError("Candidate identity changed.")
                        candidate = {"tag": expected, "sha256": sha, "path": row["file"]}
                        status = "Candidate identity matched — pin blocked"
                    except (OSError, RuntimeError, ValueError):
                        status = "Candidate changed — rescan required"
        result.append({**item, "pinned_version": pin, "pinned_sha256": package["sha256"],
                       "official_release": expected, "candidate": candidate,
                       "candidate_status": status, "write_authorized": False,
                       "compatibility_verified": False, "installed_bytes_verified": False})
    return {"game_id": recipe["id"], "rows": tuple(result), "write_authorized": False}
