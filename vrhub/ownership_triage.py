# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-S: non-destructive installed-file and ownership evidence triage.

Consumes ONLY an already completed, user-triggered read-only integrity result,
existing Hub records and the previous R audit. Never opens a local file,
trusts an unverified legacy manifest, attributes a cause to SHA differences,
or constructs a state migration, repair, update or rollback operation.
"""
from __future__ import annotations

from . import download_planner, installed_integrity

SCHEMA = 1
MAX_COMPONENTS = 32
CATEGORIES = frozenset(("possible_customization", "binary_drift",
                         "other_modified", "missing", "unsafe", "unknown"))
CONFIG_SUFFIXES = frozenset((".cfg", ".ini", ".json", ".toml", ".yaml", ".yml", ".xml"))
BINARY_SUFFIXES = frozenset((".dll", ".exe", ".asi", ".so", ".bin", ".pdb"))
MANUAL = frozenset(("manual", "uevr_injector"))


def _category(status, filename):
    if status == "Modified":
        suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix in CONFIG_SUFFIXES:
            return "possible_customization"
        if suffix in BINARY_SUFFIXES:
            return "binary_drift"
        return "other_modified"
    return {"Missing": "missing", "Unsafe": "unsafe", "Unknown": "unknown"}[status]


def _next_for(category):
    return {
        "possible_customization": (
            "Possible local configuration change; compare with documented mod defaults "
            "and existing saved copies manually. Preserve both versions; do not reset."),
        "binary_drift": (
            "Binary bytes differ. Review installed package provenance and compatible "
            "game/mod versions before any replacement. Cause is NOT established."),
        "other_modified": (
            "Recorded bytes differ. Check source, intended modifications and backups "
            "manually before deciding whether a new ownership record is justified."),
        "missing": (
            "Previously recorded file is missing. Confirm the expected installation "
            "and mod status manually; do not reinstall or restore automatically."),
        "unsafe": (
            "Unsafe file or path detected. Do not follow symlinks or trust this "
            "component's ownership; review it outside automated update workflows."),
        "unknown": (
            "Integrity could not be established safely. Repeat the existing on-demand "
            "verification only after checking the evidence limits."),
    }[category]


def _integrity_rows(integrity, game_id, expected):
    """Treat missing or partial integrity results as no evidence, not as clean."""
    if integrity is None:
        return {}
    if (not isinstance(integrity, dict) or integrity.get("game_id") != game_id or
            not isinstance(integrity.get("rows"), list) or
            len(integrity["rows"]) > MAX_COMPONENTS):
        raise ValueError("Cross-game or malformed integrity result.")
    found = {}
    for row in integrity["rows"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Malformed integrity component.")
        cid = row["id"]
        if cid not in expected or cid in found:
            raise ValueError("Duplicated or foreign integrity component.")
        if row.get("status") not in ("Verified", "Review", "Unknown"):
            raise ValueError("Unrecognized integrity verdict.")
        issues = row.get("issues", [])
        if not isinstance(issues, list) or len(issues) > installed_integrity.MAX_ISSUES_PER_COMPONENT:
            raise ValueError("Invalid bounded issue inventory.")
        if row["status"] == "Verified":
            if issues or type(row.get("files")) is not int or row["files"] < 1 or (
                    type(row.get("checked")) is not int or row["checked"] != row["files"]):
                raise ValueError("False verified integrity result.")
        if row["status"] == "Review":
            if (type(row.get("files")) is not int or row["files"] < 1 or
                    type(row.get("checked")) is not int or
                    not 0 <= row["checked"] < row["files"]):
                raise ValueError("Invalid partial integrity count.")
        if row["status"] == "Unknown" and issues:
            if type(row.get("files")) is not int or row["files"] < len(issues):
                raise ValueError("Unknown integrity count is incomplete.")
        seen = set()
        normalized = []
        for issue in issues:
            if (not isinstance(issue, dict) or
                    issue.get("status") not in ("Modified", "Missing", "Unsafe", "Unknown")
                    or not installed_integrity._relative(issue.get("file"))):
                raise ValueError("Unsafe or unsupported relative file issue.")
            relative = issue["file"]
            if relative.casefold() in seen:
                raise ValueError("Duplicate or differently cased integrity issue.")
            seen.add(relative.casefold())
            normalized.append({"relative_file": relative,
                               "observed_status": issue["status"],
                               "category": _category(issue["status"], relative),
                               "next_step": _next_for(_category(issue["status"], relative)),
                               "cause_confirmed": False,
                               "permitted_mutation": False})
        found[cid] = (row, normalized)
    return found


def assess(recipe, state, audit, *, integrity=None):
    """Normalize point-in-time observations without creating an ownership plan."""
    if (not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str) or
            not isinstance(state, dict) or not isinstance(audit, dict) or
            audit.get("game_id") != recipe["id"] or
            audit.get("authorized") is not False or
            audit.get("real_installer_connected") is not False):
        raise ValueError("Missing or cross-game read-only audit.")
    components = download_planner.plan_components(recipe)
    ids = [str(c["id"]) for c in components]
    if not 0 < len(ids) <= MAX_COMPONENTS or len(set(ids)) != len(ids):
        raise ValueError("Invalid expected dependency identity.")
    audited_rows = audit.get("rows")
    if not isinstance(audited_rows, list) or len(audited_rows) != len(ids):
        raise ValueError("Incomplete real-installation audit.")
    observed = {}
    for item in audited_rows:
        if (not isinstance(item, dict) or
                not isinstance(item.get("id"), str) or
                item["id"] not in ids or item["id"] in observed or
                item.get("authorized") is not False or
                item.get("live_executor_connected") is not False or
                item.get("real_compatibility_verified") is not False or
                item.get("fresh_preupdate_backup") is not False or
                item.get("production_recovery_verified") is not False or
                item.get("exclusive_game_lock_verified") is not False):
            raise ValueError("Contradictory or unsafe installation audit component.")
        observed[item["id"]] = item
    history = _integrity_rows(integrity, recipe["id"], set(ids))
    results = []
    totals = {key: 0 for key in CATEGORIES}
    for component in components:
        cid = str(component["id"])
        source = observed[cid]
        details = history.get(cid)
        hash_row, issues = details if details is not None else (None, [])
        status = hash_row.get("status") if hash_row is not None else "Not checked"
        expected_files = hash_row.get("files") if hash_row is not None else 0
        matched_files = hash_row.get("checked") if hash_row is not None else 0
        issue_counts = {key: sum(item["category"] == key for item in issues)
                        for key in CATEGORIES}
        for key in CATEGORIES:
            totals[key] += issue_counts[key]
        if status == "Review":
            remainder = expected_files - matched_files - len(issues)
            if remainder < 0:
                raise ValueError("Integrity issue inventory exceeds unmatched count.")
        elif status == "Unknown":
            remainder = max(0, expected_files - matched_files - len(issues)) if (
                type(expected_files) is int and type(matched_files) is int) else 0
        else:
            remainder = 0
        if source.get("verdict") == "blocked" and (
                source.get("location") != "directory" or
                (source.get("adapter") not in MANUAL and
                 not source.get("root_identity_matches", False))):
            classification = "root_or_location_blocked"
            advice = "Reconcile the game/profile location and Hub record first; never adopt or migrate automatically."
        elif source.get("adapter") in MANUAL:
            classification = "manual"
            advice = "Continue the existing manual workflow; no automatic ownership adoption."
        elif not source.get("root_bound_ownership"):
            classification = "ownership_unverified"
            advice = (
                "Review the legacy/manual file ownership record and installation source. "
                "Do not auto-adopt paths or rewrite recorded SHA values.")
        elif issues or status == "Review":
            classification = "file_differences"
            advice = (
                "Review each changed, missing or unsafe recorded file without repair. "
                "An intentional customization must be confirmed manually; preserve original evidence.")
        elif status == "Verified":
            classification = "historical_match_only"
            advice = (
                "Historical SHA checks matched at scan time, not now. Fresh backup, "
                "runtime lock, verified compatibility, recovery and authorization remain required.")
        else:
            classification = "integrity_not_established"
            advice = "Run Verify installed files on demand; a missing result is not a clean scan."
        results.append({
            "id": cid, "name": str(component.get("name", cid)),
            "adapter": source.get("adapter"), "classification": classification,
            "status": status, "matched": matched_files if isinstance(matched_files, int) else 0,
            "tracked": expected_files if isinstance(expected_files, int) else 0,
            "reported_issues": issues,
            "unreported_issues": remainder,
            "counts": issue_counts, "next_step": advice,
            "owned_by_hub": source.get("root_bound_ownership") is True,
            "recorded_file_hashes_rewritten": False,
            "legacy_state_migrated": False,
            "manual_files_adopted": False,
            "live_update_authorized": False,
        })
    return {
        "schema": SCHEMA, "game_id": recipe["id"],
        "summary": (
            f"{len(results)} dependencies · "
            f"{totals['possible_customization']} possible config changes · "
            f"{totals['binary_drift']} binary differences · "
            f"{totals['missing']} missing · {totals['unsafe']} unsafe"),
        "issue_counts": totals, "rows": results,
        "files_read_or_hashed_by_triage": False,
        "provided_integrity_is_point_in_time": True,
        "recorded_file_hashes_rewritten": False, "legacy_state_migrated": False,
        "manual_files_adopted": False, "live_update_authorized": False,
        "real_compatibility_verified": False,
        "requires_separate_approval": True,
    }
