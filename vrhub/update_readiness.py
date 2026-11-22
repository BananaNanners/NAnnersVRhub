# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-I — advisory update readiness from independent evidence.

Pure presentation/planning only: no file access, network activity, backups,
installation eligibility, or state changes. A 'candidate' means more safety
review is needed, never that mod replacement is authorized.
"""
from . import archive_update_comparison, download_planner, installed_provenance, updates

ATTRIBUTABLE_SOURCES = frozenset(("recipe-pinned-hash", "official-hash-match"))
BLOCKED_ARCHIVES = frozenset((
    "Hash mismatch — do not install", "Hash not verified — do not install",
    "Archive changed — rescan required",
))


def _answer(code, label, next_step, why, tone="unknown"):
    return {
        "code": code, "label": label, "next": next_step,
        "detail": why, "tone": tone,
        "authorized": False,  # Explicit, invariant; no installation token.
    }


def _ordered(left, right):
    """Compare only plain numeric versions. Unknown/prerelease is not ordered."""
    a, b = updates._release_version(left), updates._release_version(right)
    return updates._ordered_numeric(a, b) if a is not None and b is not None else None


def assess(recipe, plan, state, online=None, integrity=None, comparisons=None):
    """Read-only per-dependency readiness from observed, separate sources.

    Histories may be malformed or incomplete. Never let stale/ambiguous archive
    evidence or a missing integrity snapshot be silently called update-ready.
    The integrity snapshot is transient and must match this game's ID.
    """
    if not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str):
        return []
    if not isinstance(state, dict):
        state = {}
    components = [c for c in download_planner.plan_components(recipe)
                  if c["id"] != "guide"]
    compared = comparisons if comparisons is not None else (
        archive_update_comparison.compare(recipe, plan, state, online))
    by_comp = {str(c.get("id")): c for c in compared if isinstance(c, dict)}
    raw_rows = plan.get("rows", []) if isinstance(plan, dict) else []
    raw = {str(c.get("id")): c for c in raw_rows
           if isinstance(c, dict) and "id" in c}
    scan_warning = plan.get("warning") if isinstance(plan, dict) else None
    matching_integrity = (
        integrity if isinstance(integrity, dict) and
        integrity.get("game_id") == recipe["id"] else None)
    checked_rows = (matching_integrity.get("rows", [])
                    if matching_integrity is not None else [])
    integrity_by_id = {
        str(c.get("id")): c for c in checked_rows
        if isinstance(c, dict) and "id" in c
    }
    presence = matching_integrity.get("presence") if matching_integrity else None
    decisions = []
    for component in components:
        cid = str(component["id"])
        item = by_comp.get(cid, {})
        candidate = raw.get(cid)
        recorded = installed_provenance.evidence(
            recipe, component, state, candidate, scan_warning)
        installed_version = recorded.get("version")
        found = item.get("downloaded", "Not scanned")
        downloaded_version = item.get("download_version")
        online_version = item.get("online_version")
        online_status = item.get("online_status")
        row = integrity_by_id.get(cid)
        checked = row.get("status") if isinstance(row, dict) else None

        if scan_warning or candidate is None or found in ("Not scanned", "Scan incomplete", "Rescan needed"):
            decision = _answer("rescan", "Scan archives first",
                               "Scan Downloads and the selected game's extra archive folder.",
                               "No complete, current-folder local archive scan is available.")
        elif (candidate.get("status") in BLOCKED_ARCHIVES or
              found in ("Hash mismatch · blocked", "Unverified hash") or
              candidate.get("candidate_incomplete") or candidate.get("ambiguous")):
            decision = _answer("blocked", "Archive blocked / ambiguous",
                               "Review archive identity or recipe pins; do not replace files.",
                               "The selected local archive has incomplete, conflicting, or blocked verification.", "danger")
        elif item.get("pin_blocked") or candidate.get("release_review"):
            decision = _answer("pin", "Recipe pin blocks release",
                               "Review pinned compatibility and obtain explicit approval in a future milestone.",
                               "An official upstream SHA match does not override the recipe's pinned SHA-256.", "danger")
        elif not candidate.get("file") or found == "Not found":
            decision = _answer("missing", "No local update archive",
                               "Download a suitable release manually, then rescan.",
                               "No matching local archive was found; no replacement is planned.")
        elif not item.get("matched_release") or not downloaded_version:
            decision = _answer("unverified", "Archive needs release verification",
                               "Check archive provenance and release tag; rescan or inspect.",
                               "A filename suggestion or unknown release cannot establish an update.", "warning")
        elif (recorded.get("source") not in ATTRIBUTABLE_SOURCES or
              not recorded.get("identified") or not installed_version):
            decision = _answer("provenance", "Installed release unconfirmed",
                               "Review the Hub-managed installation record; no version inferred from timestamps.",
                               "Downloaded release is identified, but installed release provenance is insufficient.")
        elif checked is None:
            decision = _answer("integrity-unchecked", "Verify installed files first",
                               "Click Verify installed files for this game.",
                               "Historical archive hashes do not prove current installed-file integrity.")
        elif checked == "Review":
            decision = _answer("integrity-review", "Installed files need review",
                               "Inspect missing/modified/unsafe file details before any update planning.",
                               "At least one recorded file was missing, modified, or unsafe to verify.", "danger")
        elif checked != "Verified":
            decision = _answer("integrity-unknown", "Installed integrity unknown",
                               "Review missing evidence or unsafe paths; do not infer a clean installation.",
                               "The on-demand SHA-256 check did not verify all recorded files.")
        elif (type(row.get("files")) is not int or type(row.get("checked")) is not int
              or row["files"] < 1 or row["checked"] != row["files"]):
            decision = _answer("integrity-unknown", "Installed integrity unknown",
                               "Run a complete on-demand check with recorded per-file hashes.",
                               "A status label without a non-empty, complete file count is not integrity evidence.")
        elif (not isinstance(presence, dict) or presence.get("status") != "Ready"
              or presence.get("required_bad")):
            decision = _answer("presence", "Required mods need review",
                               "Review required-component presence separately from SHA-256 matching.",
                               "Tracked files matched, but required-mod readiness is not established.")
        else:
            relation = _ordered(installed_version, downloaded_version)
            latest_relation = (_ordered(downloaded_version, online_version)
                               if online_version is not None else None)
            online_known = (online_version is not None and
                            online_status not in ("error", "no_key", "manual", "not_installed"))
            if relation is None:
                decision = _answer("versions", "Compare release versions manually",
                                   "Verify exact release ordering, prerequisites, and game compatibility.",
                                   "At least one release uses a non-numeric or non-comparable version.")
            elif relation > 0:
                decision = _answer("older", "Local archive is older",
                                   "Keep the recorded installation; review any downgrade manually.",
                                   "Verified local release label sorts below the recorded installed release.", "warning")
            elif relation == 0:
                if online_known and latest_relation is not None and latest_relation < 0:
                    decision = _answer("online-newer", "Newer release online",
                                       "Download and verify the newer release, then review compatibility.",
                                       "The downloaded archive matches the recorded installed version, but a later online release is listed.")
                else:
                    decision = _answer("same", "No newer local release evidenced",
                                       "No replacement planned; refresh Updates again when needed.",
                                       "Local and installed numeric release labels match. This is not proof of runtime compatibility.")
            elif not online_known:
                decision = _answer("online", "Check latest online version",
                                   "Refresh Updates; a downloaded candidate must be reconciled with its upstream source.",
                                   "A newer local archive is identified, but there is no uniquely matched online release.")
            elif latest_relation is None:
                decision = _answer("online-unknown", "Online version needs review",
                                   "Confirm upstream release ordering and game compatibility manually.",
                                   "A newer downloaded archive is identified, but the online release tag cannot be numerically compared.")
            elif latest_relation > 0:
                decision = _answer("ahead", "Local archive ahead of online",
                                   "Review release identity and upstream metadata; no automatic replacement.",
                                   "The downloaded release compares newer than the last online result; metadata may be stale.", "warning")
            elif latest_relation < 0:
                decision = _answer("online-newer", "Newer release online",
                                   "Download and verify the newer release, then review compatibility.",
                                   "Another release is listed online beyond the downloaded update.", "warning")
            else:
                decision = _answer("candidate", "Future update candidate · review",
                                   "Future safeguarded review must validate game compatibility, dependency order, verified backups and recovery before replacement.",
                                   "Recorded release, on-demand integrity, local archive SHA, and last online version are consistent. "
                                   "These checks are NOT authorization to replace files.", "warning")
        decisions.append({"id": cid, "name": str(component.get("name", cid)),
                          **decision})
    return decisions
