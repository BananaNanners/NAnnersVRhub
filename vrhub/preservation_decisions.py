# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-T: pure, non-persistent preservation decision worksheet.

Never reads/writes files, copies backups, adopts ownership, changes installed
hash records, or grants game update authorization. Explicit choices, if
provided by a future UI, are session-only *draft intentions*, not consent
to any live action. No decision can be executed by this module.
"""
from __future__ import annotations

from . import download_planner, installed_integrity, ownership_triage

SCHEMA = 1
MAX_ISSUES = 32 * installed_integrity.MAX_ISSUES_PER_COMPONENT
PRESERVE = "preserve_existing"
INVESTIGATE = "investigate_unknown"
CONSIDER = "consider_future_replacement"
DECISIONS = frozenset((PRESERVE, INVESTIGATE, CONSIDER))
MODIFIED_CATEGORIES = frozenset(("possible_customization", "binary_drift", "other_modified"))
UNSAFE_CATEGORIES = frozenset(("missing", "unsafe", "unknown"))
LIVE_GAPS = (
    "Existing file and any deliberate customization must remain intact",
    "Fresh complete pre-update backup verified and recoverable",
    "Exact future ZIP, installation target and dependency compatibility verified",
    "Exclusive game/process lock and tested live rollback",
    "User review of exact proposed replacement and separate explicit authorization",
    "No live update executor connected",
)


def _validate(recipe, triage):
    if (not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str)
            or not isinstance(triage, dict) or
            triage.get("game_id") != recipe["id"] or
            triage.get("live_update_authorized") is not False or
            triage.get("manual_files_adopted") is not False or
            triage.get("recorded_file_hashes_rewritten") is not False or
            triage.get("legacy_state_migrated") is not False or
            triage.get("files_read_or_hashed_by_triage") is not False or
            triage.get("real_compatibility_verified") is not False):
        raise ValueError("Untrusted or live-authorized triage evidence.")
    components = download_planner.plan_components(recipe)
    expected = [str(c["id"]) for c in components]
    rows = triage.get("rows")
    if (len(expected) > 32 or not isinstance(rows, list)
            or len(rows) != len(expected) or len(set(expected)) != len(expected)):
        raise ValueError("Incomplete or duplicate dependency inventory.")
    seen = set()
    indexed = {}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or row["id"] not in expected or row["id"] in indexed
                or row.get("live_update_authorized") is not False
                or row.get("manual_files_adopted") is not False
                or row.get("recorded_file_hashes_rewritten") is not False
                or row.get("legacy_state_migrated") is not False
                or type(row.get("unreported_issues")) is not int
                or row["unreported_issues"] < 0):
            raise ValueError("Malformed or untrusted component triage.")
        found = row.get("reported_issues")
        if not isinstance(found, list) or len(found) > installed_integrity.MAX_ISSUES_PER_COMPONENT:
            raise ValueError("Excessive or missing bounded per-file triage.")
        for issue in found:
            if (not isinstance(issue, dict) or
                    not isinstance(issue.get("relative_file"), str) or
                    not installed_integrity._relative(issue["relative_file"])
                    or issue.get("observed_status") not in (
                        "Modified", "Missing", "Unsafe", "Unknown")
                    or issue.get("category") not in ownership_triage.CATEGORIES
                    or issue.get("category") != ownership_triage._category(
                        issue["observed_status"], issue["relative_file"])
                    or issue.get("cause_confirmed") is not False
                    or issue.get("permitted_mutation") is not False):
                raise ValueError("Unsupported, unsafe or falsely confirmed file difference.")
            key = issue["relative_file"].casefold()
            # A filename claimed by multiple components is ambiguous even if
            # the component IDs differ; require independent ownership review.
            if key in seen:
                raise ValueError("Cross-component file ownership collision.")
            seen.add(key)
        indexed[row["id"]] = row
    if len(seen) > MAX_ISSUES:
        raise ValueError("Excessive file decisions.")
    return expected, indexed


def _validate_choices(choices, indexed):
    if choices is None:
        return {}
    if not isinstance(choices, dict) or len(choices) > len(indexed):
        raise ValueError("Invalid non-persistent draft decision list.")
    normalized = {}
    for cid, per_file in choices.items():
        if (not isinstance(cid, str) or cid not in indexed or
                not isinstance(per_file, dict) or
                len(per_file) > installed_integrity.MAX_ISSUES_PER_COMPONENT):
            raise ValueError("Unknown component or unbounded draft decisions.")
        known = {x["relative_file"]: x
                 for x in indexed[cid]["reported_issues"]}
        for name, choice in per_file.items():
            if (not isinstance(name, str) or name not in known
                    or not isinstance(choice, str) or choice not in DECISIONS):
                raise ValueError("Unknown file or unsupported decision.")
            issue = known[name]
            if choice in (PRESERVE, CONSIDER):
                if issue["category"] not in MODIFIED_CATEGORIES:
                    raise ValueError("Cannot preserve or replace missing/unsafe/unknown evidence.")
                if (choice == CONSIDER and
                        (indexed[cid].get("owned_by_hub") is not True or
                         indexed[cid].get("classification") != "file_differences")):
                    raise ValueError("Potential replacement requires trusted installed ownership.")
            normalized[(cid, name)] = choice
    return normalized


def assess(recipe, triage, *, choices=None):
    """Create a read-only worksheet; options never trigger any action.

    No user selection is persisted and no default becomes a user approval.
    A future-replacement draft means *investigate a candidate* and is blocked
    pending all live gates regardless of existing evidence.
    """
    expected, indexed = _validate(recipe, triage)
    selected = _validate_choices(choices, indexed)
    rows, totals, unresolved = [], {name: 0 for name in DECISIONS}, 0
    for cid in expected:
        component = indexed[cid]
        for issue in component["reported_issues"]:
            name, category = issue["relative_file"], issue["category"]
            recommended = PRESERVE if category == "possible_customization" else INVESTIGATE
            choice = selected.get((cid, name))
            decision = choice if choice is not None else recommended
            totals[decision] += 1
            if decision == PRESERVE:
                guidance = (
                    "Preserve the installed version as-is; compare configuration and saved "
                    "defaults manually. This worksheet does not enforce preservation.")
            elif decision == INVESTIGATE:
                guidance = (
                    "Keep the installed version untouched; establish source, purpose "
                    "and compatibility before making a replacement decision.")
            else:
                guidance = (
                    "Future replacement is only a review candidate; preserve the current "
                    "file until source compatibility, a fresh backup and an explicit "
                    "separate update authorization are verified.")
            rows.append({
                "component_id": cid, "component_name": str(component.get("name", cid)),
                "relative_file": name, "category": category,
                "observed_status": issue["observed_status"],
                "recommendation": recommended, "draft_decision": decision,
                "selected_in_this_review": choice is not None,
                "selection_saved": False, "reason_confirmed": False,
                "root_bound_ownership": component.get("owned_by_hub") is True,
                "next_step": guidance,
                "fresh_verified_backup": False,
                "real_compatibility_verified": False,
                "current_file_preserved_by_executor": False,
                "replacement_authorized": False,
                "recorded_sha_rewritten": False,
            })
        unresolved += component["unreported_issues"]
    return {
        "schema": SCHEMA, "game_id": recipe["id"],
        "status": "Advisory decision worksheet — NO UPDATE OR REPAIR AUTHORIZED",
        "rows": rows, "counts": totals,
        "unreported_differences": unresolved,
        "summary": (
            f"{len(rows)} reported difference(s) · "
            f"{totals[PRESERVE]} preserve recommendations/drafts · "
            f"{totals[INVESTIGATE]} investigate · "
            f"{totals[CONSIDER]} future replacement reviews · "
            f"{unresolved} unlisted difference(s)"
        ),
        "session_only": True, "user_confirmed_any_choice": bool(selected),
        "choices_saved": False, "manual_files_adopted": False,
        "recorded_file_hashes_rewritten": False,
        "real_backup_created": False, "live_update_authorized": False,
        "real_compatibility_verified": False,
        "all_live_gates_unresolved": list(LIVE_GAPS),
        "requires_separate_live_approval": True,
    }
