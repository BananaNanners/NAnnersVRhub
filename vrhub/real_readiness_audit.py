# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-R: read-only evidence audit of located game installations.

No game-file contents are opened or hashed here. This module reads only
existing Hub state passed by the caller and filesystem *directory metadata*
from known, recipe-discovered locations. It never trusts a stored game path
as an instruction to inspect that path. The report is advisory, cannot be
saved as authorization, and cannot initiate a real update or restore.
"""
from __future__ import annotations

import stat
from pathlib import Path

from . import download_planner, hub, update_integration

SCHEMA = 1
MAX_COMPONENTS = 32
MANUAL = frozenset(("manual", "uevr_injector"))
LOCATION_STATUS = frozenset(("directory", "missing", "symlink", "not_directory", "unresolved", "unavailable"))
LIVE_GATES = (
    ("fresh_backup", "New complete backup of current installed mod files, verified and recoverable"),
    ("exclusive_lock", "Target game stopped and exclusive real-install update/restore lock"),
    ("real_candidate", "Exact newer source release and ZIP-to-target compatibility with the real game"),
    ("live_recovery", "Verified full real-install transaction, permissions and rollback procedure"),
    ("explicit_approval", "Separate game-specific, user-reviewed update authorization"),
    ("live_executor", "No production replacement executor is connected"),
)


def _location(path):
    """Read only lstat of a recipe-derived location, with no path disclosure."""
    if path is None:
        return "unresolved"
    try:
        target = Path(path)
        if not target.is_absolute():
            return "unavailable"
        mode = target.lstat().st_mode
        if stat.S_ISLNK(mode):
            return "symlink"
        if stat.S_ISDIR(mode):
            return "directory"
        return "not_directory"
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError, TypeError):
        return "unavailable"


def _identity(expected, recorded):
    """Match only a canonical-looking recorded root against a recipe locator.

    Never open a directory specified by a state record. Resolve neither its
    user-supplied path nor any state-supplied file name. A missing/mismatched
    location is not adopted even if some files happen to be present.
    """
    if not isinstance(recorded, str) or not recorded or len(recorded) > 4096:
        return False
    try:
        rp = Path(recorded)
        xp = Path(expected)
        if not rp.is_absolute() or not xp.is_absolute():
            return False
        if (str(rp) == "/" or
                any(part in (".", "..") for part in recorded[1:].split("/")) or
                "//" in recorded or chr(92) in recorded or
                any(ord(ch) < 32 for ch in recorded)):
            return False
        return rp == xp
    except (TypeError, OSError, ValueError):
        return False


def _reported_integrity(integrity, game_id, cid):
    """Summarize a prior user-triggered SHA check, never assert current hashes."""
    if (not isinstance(integrity, dict) or
            integrity.get("game_id") != game_id or
            not isinstance(integrity.get("rows"), list)):
        return "not_checked"
    rows = [r for r in integrity["rows"]
            if isinstance(r, dict) and str(r.get("id")) == cid]
    if len(rows) != 1:
        return "not_checked"
    row = rows[0]
    if (row.get("status") == "Verified" and
            type(row.get("checked")) is int and
            type(row.get("files")) is int and
            row["files"] > 0 and row["checked"] == row["files"]):
        return "verified_at_prior_check"
    if row.get("status") == "Review":
        return "needs_review_at_prior_check"
    return "unknown_at_prior_check"


def _unique_contracts(recipe, integration):
    from . import download_planner as planner
    expected = {str(c["id"]) for c in planner.plan_components(recipe)}
    if (not isinstance(integration, dict) or integration.get("game_id") != recipe["id"]
            or integration.get("authorized") is not False
            or integration.get("live_executor_connected") is not False):
        raise ValueError("Missing or untrusted current-game integration evidence.")
    rows = integration.get("contracts")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Incomplete installed dependency evidence.")
    found = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Malformed integration record.")
        cid = row["id"]
        if (cid in found or cid not in expected or
                row.get("game_id") != recipe["id"] or
                row.get("authorized") is not False or
                row.get("live_executor_connected") is not False or
                row.get("replacement_supported") is not False):
            raise ValueError("Contradictory or cross-game integration record.")
        found[cid] = row
    return found


def audit_game(recipe, state, *, integrity=None, safety=None, integration=None,
               game_locator=None, profile_locator=None):
    """Inspect known game/profile DIRECTORY metadata and recorded ownership.

    Callable from a worker after the existing, explicit read-only safety
    review, or directly for a per-game audit. A separately triggered SHA
    integrity check can be summarized but is never run automatically.
    """
    if (not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str)
            or not recipe["id"] or not isinstance(state, dict)):
        raise ValueError("Invalid read-only audit inputs.")
    rid = recipe["id"]
    components = download_planner.plan_components(recipe)
    if not 0 < len(components) <= MAX_COMPONENTS:
        raise ValueError("Unsupported dependency count for audit.")
    if integration is None:
        integration = update_integration.assess(recipe, state=state)
    contracts = _unique_contracts(recipe, integration)
    # The supplied adapter report is advisory evidence, never permission.
    # Recheck recorded ownership directly against the source state without
    # launching another update planner or duplicating network/GUI side effects.
    # This is pure validation; no current game file is opened.
    for comp in components:
        cid = str(comp["id"])
        contract = contracts[cid]
        adapter = contract.get("adapter")
        expected_adapter = update_integration._adapter(recipe, cid)
        if adapter != expected_adapter or adapter not in (
                "pinned_package", "uevr_profile", "uevr_injector", "gameroot", "manual"):
            raise ValueError("Unknown updater identity in audit.")
        true_owner, _ = update_integration._ownership(recipe, comp, state, adapter)
        if (contract.get("recorded_ownership") is True) != (true_owner is True):
            raise ValueError("Stale or contradictory recorded ownership evidence.")
    if safety is not None and (not isinstance(safety, dict) or
                               safety.get("game_id") != rid or
                               safety.get("authorized") is not False or
                               safety.get("has_live_install_plan") is not False):
        raise ValueError("Cross-game or live-authorized safety evidence rejected.")

    game_locator = game_locator if game_locator is not None else hub.game_path
    profile_locator = profile_locator if profile_locator is not None else hub.profile_dir
    try:
        game_root = game_locator(recipe)
        game_location = _location(game_root)
    except (OSError, RuntimeError, ValueError, KeyError):
        game_root = None
        game_location = "unavailable"
    profile_root = None
    profile_location = "not_applicable"
    if recipe.get("method") == "uevr" and recipe.get("profile"):
        try:
            profile_root = profile_locator(recipe)
            profile_location = _location(profile_root)
        except (OSError, RuntimeError, ValueError, KeyError):
            profile_location = "unavailable"

    game_rec = state.get(rid)
    profile_rec = state.get(rid + ":profile")
    recognized_markers = {"vhvr-1", "submersed-vr-1", "ervr-1",
                          "gameroot-2", "uevr-profile-2"}
    raw_game_marker = game_rec.get("installer") if isinstance(game_rec, dict) else None
    raw_profile_marker = profile_rec.get("installer") if isinstance(profile_rec, dict) else None
    game_marker = (raw_game_marker if (isinstance(raw_game_marker, str)
                                       and raw_game_marker in recognized_markers)
                   else "legacy_or_unclassified" if isinstance(game_rec, dict) else None)
    profile_marker = (raw_profile_marker if (isinstance(raw_profile_marker, str)
                                             and raw_profile_marker in recognized_markers)
                      else "legacy_or_unclassified" if isinstance(profile_rec, dict) else None)
    root_matches = (
        game_location == "directory" and isinstance(game_rec, dict)
        and _identity(game_root, game_rec.get("keep"))
    )
    profile_matches = (
        profile_location == "directory" and isinstance(profile_rec, dict)
        and _identity(profile_root, profile_rec.get("root"))
    )
    retained = "not_checked"
    if safety is not None:
        backup = safety.get("existing_backup")
        if isinstance(backup, dict):
            retained = (
                "prior_originals_verified" if backup.get("status") == "Recorded originals matched" else
                "no_prior_originals" if backup.get("status") == "No prior originals" else
                "needs_review"
            )
    rows = []
    for comp in components:
        cid = str(comp["id"])
        record = contracts[cid]
        adapter = record.get("adapter")
        if adapter not in ("pinned_package", "uevr_profile", "uevr_injector",
                           "gameroot", "manual"):
            raise ValueError("Unknown updater identity in audit.")
        location = (
            profile_location if adapter == "uevr_profile" else game_location
        )
        if adapter == "uevr_profile":
            identity_match = profile_matches
        elif adapter in ("pinned_package", "gameroot"):
            identity_match = root_matches
        else:
            identity_match = False
        recorded = record.get("recorded_ownership") is True
        tracked = recorded and identity_match
        integrity_status = _reported_integrity(integrity, rid, cid)
        obstacles = []
        if game_location != "directory" or (
                adapter == "uevr_profile" and location != "directory"):
            verdict = "blocked"
            next_step = ("Reconcile the game's storefront or UEVR profile directory "
                         "without creating or adopting files.")
            obstacles.append("target_location_unconfirmed")
        elif adapter in MANUAL:
            verdict = "manual"
            next_step = ("Keep this dependency manual; establish exact installer ownership "
                         "and recovery rules before any automated update.")
        elif (
            (adapter in ("pinned_package", "gameroot") and
             isinstance(game_rec, dict) and isinstance(game_rec.get("keep"), str) and
             not root_matches)
            or (adapter == "uevr_profile" and isinstance(profile_rec, dict) and
                isinstance(profile_rec.get("root"), str) and not profile_matches)
        ):
            # A path mismatch is an explicit hard stop even when the record's
            # internal schema also fails its ownership validation.
            verdict = "blocked"
            next_step = "Reconcile the recorded installation root with the game/profile locator."
            obstacles.append("root_identity_mismatch")
        elif not recorded:
            verdict = "needs_evidence"
            next_step = "Review legacy/manual installed-file ownership; never auto-adopt mod files."
            obstacles.append("recorded_ownership_missing")
        elif not identity_match:
            verdict = "blocked"
            next_step = "Reconcile the recorded installation root with the game/profile locator."
            obstacles.append("root_identity_mismatch")
        elif integrity_status == "needs_review_at_prior_check":
            verdict = "blocked"
            next_step = "Inspect modified/missing files using the existing Verify installed files workflow."
            obstacles.append("prior_integrity_needs_review")
        elif integrity_status != "verified_at_prior_check":
            verdict = "needs_evidence"
            next_step = "Run Verify installed files on demand and review the results; no repair is permitted."
            obstacles.append("integrity_not_verified")
        else:
            verdict = "blocked"
            next_step = ("File hashes matched at the prior check, but fresh backup, live lock, "
                         "real compatibility and recovery proof are still missing.")
        if adapter not in MANUAL:
            obstacles += [key for key, _ in LIVE_GATES]
        rows.append({
            "id": cid, "name": str(comp.get("name", cid)),
            "adapter": adapter,
            "phase": int(comp.get("phase", 1)),
            "location": location,
            "root_identity_matches": identity_match,
            "hub_recorded_ownership": recorded,
            "root_bound_ownership": tracked,
            "integrity": integrity_status,
            "prior_retained_backup": retained,
            "fresh_preupdate_backup": False,
            "exclusive_game_lock_verified": False,
            "real_compatibility_verified": False,
            "production_recovery_verified": False,
            "verdict": verdict,
            "next_step": next_step,
            "blockers": obstacles,
            "authorized": False,
            "live_executor_connected": False,
        })
    counts = {s: sum(item["verdict"] == s for item in rows)
              for s in ("blocked", "needs_evidence", "manual")}
    return {
        "schema": SCHEMA, "game_id": rid,
        "status": "Read-only, point-in-time evidence audit — LIVE UPDATE DISABLED",
        "game_location": game_location, "profile_location": profile_location,
        "game_record_present": isinstance(game_rec, dict),
        "game_record_marker": game_marker,
        "profile_record_present": isinstance(profile_rec, dict),
        "profile_record_marker": profile_marker,
        "retained_originals": retained,
        "summary": (
            f'{len(rows)} dependencies · {counts["blocked"]} blocked · '
            f'{counts["needs_evidence"]} need evidence · {counts["manual"]} manual'
        ),
        "counts": counts, "rows": rows,
        "live_gates": [{"id": key, "verified": False, "detail": explanation}
                       for key, explanation in LIVE_GATES],
        "observation_scope": (
            "Recipe-discovered directory metadata and supplied Hub records only; "
            "no live file contents were opened or hashed by this audit. "
            "Prior integrity and retained-original results are separate, point-in-time checks."
        ),
        "real_installer_connected": False,
        "authorized": False,
        "requires_separate_live_approval": True,
    }


def audit_all(recipes, state, *, game_locator=None, profile_locator=None):
    """Summarize every recipe with no writes and no saved evidence mutation."""
    if not isinstance(recipes, dict) or not isinstance(state, dict):
        raise ValueError("Invalid audit collection.")
    results = {}
    for rid, recipe in sorted(recipes.items()):
        if rid != recipe.get("id"):
            raise ValueError("Recipe key mismatch.")
        results[rid] = audit_game(
            recipe, state, game_locator=game_locator,
            profile_locator=profile_locator)
    return {"schema": SCHEMA, "games": results,
            "games_audited": len(results),
            "dependencies_audited": sum(len(r["rows"]) for r in results.values()),
            "authorized": False, "read_only": True,
            "live_update_enabled": False}
