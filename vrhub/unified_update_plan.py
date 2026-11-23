# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-Q: unified, non-executable update review for all dependency types.

Combines already captured update readiness, installed integrity and read-only
safety/adapter records. No I/O, no installer imports, no writable plan, and no
authorization token. This is NOT a preflight for real update execution.
"""
from __future__ import annotations

from . import download_planner

SCHEMA = 1
MAX_COMPONENTS = 32
SUPPORTED_DRAFTS = {
    "pinned_package": "Pinned package (offline fixture model only)",
    "uevr_profile": "UEVR whole profile (offline fixture model only)",
    "gameroot": "Game-root components (offline fixture model only)",
}
MANUAL = {"manual", "uevr_injector"}
UNRESOLVED_LIVE_GATES = (
    "Fresh complete pre-update backup",
    "Game stopped and exclusive live update/restore lock",
    "Real archive/dependency/VR runtime compatibility",
    "Verified real destination/recovery strategy",
    "Separate explicit game-specific update authorization",
    "Production live executor not connected",
)


def _unique(rows, expected, what):
    if not isinstance(rows, list) or len(rows) > MAX_COMPONENTS:
        raise ValueError("Missing or excessive " + what + " evidence.")
    indexed = {}
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Malformed " + what + " row.")
        cid = item["id"]
        if cid in indexed or cid not in expected:
            raise ValueError("Duplicate or unexpected " + what + " component.")
        indexed[cid] = item
    return indexed


def _hazards(row):
    if not isinstance(row, dict):
        return ["Read-only destination safety evidence is unavailable."]
    issues = []
    for key, label in (
        ("ownership_conflicts", "Overlapping mod ownership"),
        ("untracked_collisions", "Untracked or unsafe destination collision"),
    ):
        value = row.get(key)
        if not isinstance(value, list):
            issues.append("Incomplete collision inventory")
        elif value:
            issues.append(label)
    return issues


def assess(recipe, safety, integration):
    """Return an explanatory, read-only combined plan, never an executable one.

    Require exact matching IDs and game identity. A corrupt or contradictory
    result raises instead of silently replacing dangerous evidence with an
    optimistic state. No filesystem or live-game operation occurs here.
    """
    if (not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str)
            or not recipe["id"] or not isinstance(safety, dict)
            or not isinstance(integration, dict)):
        raise ValueError("Invalid unified review inputs.")
    rid = recipe["id"]
    if safety.get("game_id") != rid or integration.get("game_id") != rid:
        raise ValueError("Cross-game evidence cannot be reused.")
    if (safety.get("authorized") is not False or
            safety.get("has_live_install_plan") is not False or
            integration.get("authorized") is not False or
            integration.get("live_executor_connected") is not False):
        raise ValueError("Unexpected live update authority in a read-only report.")
    components = download_planner.plan_components(recipe)
    if not 0 < len(components) <= MAX_COMPONENTS:
        raise ValueError("Unrecognized or excessive dependency inventory.")
    ids = [str(c["id"]) for c in components]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate recipe component identity.")
    by_contract = _unique(integration.get("contracts"), set(ids), "integration")
    if set(by_contract) != set(ids):
        raise ValueError("Integration contract coverage is incomplete.")
    safety_components = {str(c["id"]) for c in components if str(c["id"]) != "guide"}
    by_safety = _unique(safety.get("rows"), safety_components, "safety")
    if set(by_safety) != safety_components:
        raise ValueError("Safety review missing dependency evidence.")
    answer = []
    for comp in components:
        cid = str(comp["id"])
        record = by_contract[cid]
        safety_row = by_safety.get(cid)
        if (record.get("game_id") != rid or record.get("id") != cid
                or record.get("authorized") is not False or
                record.get("live_executor_connected") is not False or
                record.get("replacement_supported") is not False):
            raise ValueError("Contradictory adapter state; reject review.")
        adapter = record.get("adapter")
        if adapter not in SUPPORTED_DRAFTS and adapter not in MANUAL:
            raise ValueError("Unknown update adapter; fail closed.")
        warnings = _hazards(safety_row) if safety_row is not None else []
        if safety_row is not None and (
                safety_row.get("eligible") is not False or
                safety_row.get("backups_verified_for_update") is not False):
            raise ValueError("Unapproved replacement safety state.")
        observed = {
            "ownership": record.get("recorded_ownership") is True,
            "installed_integrity": record.get("integrity_observed") is True,
            "future_archive": record.get("verified_future_candidate") is True,
            "target_mapping": (
                type(record.get("mapped_destinations")) is int and
                record["mapped_destinations"] > 0 and not warnings
            ),
        }
        if safety_row is not None:
            mapped = safety_row.get("future_destinations")
            if (type(mapped) is not int or mapped < 1 or
                    mapped != record.get("mapped_destinations")):
                observed["target_mapping"] = False
        if warnings:
            code = "blocked"
            label = "Blocked — unsafe or conflicting destinations"
            next_step = "Resolve overlapping ownership or untracked destination collisions; rescan before review."
        elif adapter in MANUAL:
            code = "manual"
            label = "Manual workflow — no automated replacement"
            next_step = ("Keep the injector or guided installation manual. "
                         "Define separate ownership and recovery rules before automation.")
        elif not observed["ownership"]:
            code = "needs_evidence"
            label = "Needs evidence — installed ownership"
            next_step = "Review Hub-managed installed-file provenance; do not adopt untracked mods."
        elif not observed["installed_integrity"]:
            code = "needs_evidence"
            label = "Needs evidence — installed integrity"
            next_step = "Run Verify installed files, then restart the read-only replacement review."
        elif not observed["future_archive"]:
            code = "needs_evidence"
            label = "Needs evidence — future release"
            next_step = "Scan Downloads and the custom game folder; compare the verified ZIP with online releases."
        elif not observed["target_mapping"]:
            code = "needs_evidence"
            label = "Needs evidence — destination mapping"
            next_step = "Inspect the complete proposed ZIP-to-target map and resolve ambiguities."
        else:
            code = "blocked"
            label = "Evidence reviewed — live replacement disabled"
            next_step = ("A separate future milestone must validate real compatibility, "
                         "fresh backups, locks, full recovery and user authorization.")
        answer.append({
            "id": cid, "name": str(comp.get("name", cid)),
            "adapter": adapter, "phase": int(comp.get("phase", 1)),
            "code": code, "label": label, "next_step": next_step,
            "observed": observed,
            "observed_count": sum(observed.values()),
            "observed_total": 4,
            "hazards": warnings,
            "offline_fixture_model": SUPPORTED_DRAFTS.get(
                adapter, "No supported automated fixture adapter"),
            "fixture_run_on_this_installation": False,
            "real_compatibility_verified": False,
            "authorized": False,
            "live_executor_connected": False,
            "requires_explicit_future_approval": True,
        })
    counts = {code: sum(x["code"] == code for x in answer)
              for code in ("blocked", "needs_evidence", "manual")}
    return {
        "schema": SCHEMA, "game_id": rid,
        "status": "Review only — LIVE UPDATE DISABLED",
        "summary": (
            f'{len(answer)} dependencies · {counts["blocked"]} blocked · '
            f'{counts["needs_evidence"]} need evidence · '
            f'{counts["manual"]} manual'
        ),
        "counts": counts, "rows": answer,
        "outstanding_live_gates": list(UNRESOLVED_LIVE_GATES),
        "synthetic_fixture_results_are_not_live_compatibility": True,
        "authorized": False, "has_live_install_plan": False,
        "live_executor_connected": False,
        "requires_explicit_future_approval": True,
    }


def rehearse_unified_fixtures():
    """Run all three previously validated families on SYNTHETIC fixtures.

    This is a preview/test-only convenience: it does not receive a selected
    game, file path, stored state, actual archives, or Nexus credentials.
    """
    from . import pinned_staging, uevr_profile_staging, cyberpunk_staging
    a = pinned_staging.rehearse_pinned_packages()
    b = uevr_profile_staging.rehearse_uevr_profiles()
    c = cyberpunk_staging.rehearse_cyberpunk_components()
    if (not a.get("fixture_only") or not b.get("fixture_only") or
            not c.get("fixture_only") or
            not a.get("temporary_fixtures_discarded") or
            not b.get("temporary_fixtures_discarded") or
            not c.get("temporary_fixture_discarded") or
            a.get("live_update_authorized") or b.get("authorized") or
            c.get("live_update_authorized") or
            a.get("real_game_files_modified") or
            b.get("real_game_files_modified") or c.get("real_game_files_modified") or
            a.get("real_game_compatibility_verified") or
            b.get("real_game_compatibility_verified") or
            c.get("real_compatibility_verified") or
            len(a.get("results", [])) != 3 or len(b.get("results", [])) != 2 or
            not c.get("multi_component_rollback_passed")):
        raise RuntimeError("A synthetic staging family failed safe offline validation.")
    return {
        "fixture_only": True, "families": {
            "pinned_package": 3, "uevr_profile": 2, "gameroot": 1},
        "game_fixtures": 6, "rollback_rehearsals": 6,
        "preserved_manual_files": True,
        "temporary_fixtures_discarded": True,
        "real_game_files_modified": False,
        "real_game_compatibility_verified": False,
        "live_update_authorized": False,
    }
