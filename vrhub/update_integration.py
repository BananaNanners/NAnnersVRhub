# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-M — read-only installer integration contracts.

This is NOT an update adapter, install preflight, permission token or an
executor. Normalize the different existing installer records into evidence
requirements. All live operations stay blocked, including if every recorded
field appears valid. No filesystem, network, download or state mutation.
"""
from __future__ import annotations

from . import download_planner

SCHEMA_VERSION = 1
MAX_COMPONENTS = 32
MAX_OWNED = 2500
_HASH_CHARS = frozenset("0123456789abcdef")

ADAPTERS = {
    "pinned_package": ("Pinned package / game-root files", "game-root-files", "pinned-package"),
    "uevr_profile": ("UEVR profile / whole directory", "wine-prefix-profile", "uevr-profile-2"),
    "uevr_injector": ("UEVR injector / manual", "manual-injector", "manual"),
    "gameroot": ("Nexus component / game-root", "game-root-files", "gameroot-2"),
    "manual": ("Existing guided/manual workflow", "manual-only", "manual"),
}
EXPECTED_PACKAGE_MARKERS = {
    "valheim": "vhvr-1",
    "subnautica": "submersed-vr-1",
    "elden-ring": "ervr-1",
}
STATIC_BLOCKERS = (
    ("live_executor", "No live transactional replacement adapter is connected."),
    ("fresh_backup", "No freshly created and independently verified pre-update backup."),
    ("runtime_lock", "Game-stopped identity and a shared update/restore lock are not proven."),
    ("compatibility", "Target game/mod versions and dependency order have not been approved."),
    ("recovery", "Real target topology, permissions, rollback and recovery rehearsal are unverified."),
    ("consent", "No separate reviewed, game-specific replacement authorization exists."),
)


def _sha(value):
    return (isinstance(value, str) and len(value) == 64 and
            set(value) <= _HASH_CHARS)


def _relative(value):
    return (isinstance(value, str) and 0 < len(value) <= 4096 and
            not value.startswith("/") and chr(92) not in value and
            ":" not in value and
            all(part not in ("", ".", "..") for part in value.split("/")) and
            all(ord(char) >= 32 for char in value))


def _root(value):
    return (isinstance(value, str) and value.startswith("/") and
            value != "/" and not value.endswith("/") and
            len(value) <= 4096 and chr(92) not in value and
            all(part not in ("", ".", "..") for part in value[1:].split("/")) and
            all(ord(char) >= 32 for char in value))


def _owned_relative(root, full):
    if not isinstance(full, str) or not full.startswith(root + "/"):
        return None
    rel = full[len(root)+1:]
    return rel if _relative(rel) else None


def _files(value):
    return (isinstance(value, list) and 0 < len(value) <= MAX_OWNED and
            all(isinstance(x, str) and _root(x) for x in value) and
            len(value) == len(set(value)) and
            len({x.casefold() for x in value}) == len(value))


def _adapter(recipe, cid):
    method = recipe.get("method")
    if method in ("bepinex", "ervr") and recipe.get("packages"):
        return "pinned_package"
    if method == "uevr":
        return "uevr_profile" if cid == "profile" and recipe.get("profile") else "uevr_injector"
    if method == "gameroot" and recipe.get("components"):
        return "gameroot"
    return "manual"


def _ownership(recipe, comp, state, adapter):
    """Analyze schema only; no path existence claim or manual file adoption."""
    cid = str(comp["id"])
    rid = recipe["id"]
    if adapter == "pinned_package":
        record = state.get(rid)
        if not isinstance(record, dict) or record.get("installer") != EXPECTED_PACKAGE_MARKERS.get(rid):
            return False, "Pinned-package ownership marker missing or legacy."
        packages = record.get("packages")
        item = packages.get(cid) if isinstance(packages, dict) else None
        declared = next(
            (p for p in recipe.get("packages", [])
             if isinstance(p, dict) and str(p.get("id")) == cid), None)
        if not isinstance(item, dict) or not isinstance(declared, dict):
            return False, "Per-package recorded ownership or current recipe pin missing."
        hashes = record.get("file_hashes")
        if (not _sha(item.get("sha256")) or
                item["sha256"] != declared.get("sha256") or
                not _files(item.get("files")) or
                not isinstance(hashes, dict)):
            return False, "Pinned package hash/owned-file evidence incomplete or pin changed."
        root = record.get("keep")
        if not _root(root):
            return False, "Recorded game-root identity is missing or noncanonical."
        relative = [_owned_relative(root, full) for full in item["files"]]
        if (any(rel is None or not _sha(hashes.get(rel)) for rel in relative)
                or len({rel.casefold() for rel in relative}) != len(relative)):
            return False, "Pinned-package recorded paths/hashes disagree with game-root ownership."
        # The actual root and file digests must still be verified on demand.
        return True, f"{len(item['files'])} recorded package files; pin matches recipe (not rehashed)."
    if adapter == "gameroot":
        record = state.get(rid)
        if not isinstance(record, dict) or record.get("installer") != "gameroot-2":
            return False, "Game-root v2 ownership marker missing or legacy."
        all_sha = record.get("installed_sha256")
        item = record.get("components", {}).get(cid) if isinstance(record.get("components"), dict) else None
        if not isinstance(item, dict) or not _files(item.get("files")):
            return False, "Per-component game-root file manifest missing."
        if not isinstance(all_sha, dict) or not all_sha:
            return False, "Game-root recorded SHA-256 inventory missing."
        base = record.get("keep")
        if not _root(base):
            return False, "Recorded game-root identity missing or noncanonical."
        # Manifest uses relative keys while per-component file lists are absolute.
        relative = [_owned_relative(base, p) for p in item["files"]]
        if any(rel is None for rel in relative):
            return False, "Recorded component files are not safely under their root."
        if (any(r not in all_sha or not _sha(all_sha[r]) for r in relative) or
                len({r.casefold() for r in relative}) != len(relative)):
            return False, "Component file hashes are absent or inconsistent."
        return True, f"{len(item['files'])} recorded game-root files (not rehashed)."
    if adapter == "uevr_profile":
        item = state.get(rid + ":profile")
        if not isinstance(item, dict) or item.get("installer") != "uevr-profile-2":
            return False, "Complete UEVR profile snapshot/ownership marker missing or legacy."
        snapshot = item.get("installed")
        file_map = snapshot.get("files") if isinstance(snapshot, dict) else None
        if (not _root(item.get("root")) or
                not isinstance(snapshot, dict) or snapshot.get("exists") is not True or
                not isinstance(file_map, dict) or not file_map or len(file_map) > MAX_OWNED or
                any(not _relative(name) or not isinstance(meta, dict) or
                    not _sha(meta.get("sha256")) or
                    type(meta.get("size")) is not int or meta["size"] < 0
                    for name, meta in file_map.items())):
            return False, "Profile whole-directory installed SHA manifest missing or invalid."
        dirs = snapshot.get("dirs")
        sizes = sum(meta["size"] for meta in file_map.values())
        if (len({str(x).casefold() for x in file_map}) != len(file_map) or
                not isinstance(dirs, list) or len(dirs) > MAX_OWNED or
                any(not _relative(d) for d in dirs) or
                len({x.casefold() for x in dirs}) != len(dirs) or
                any(d.casefold() in {f.casefold() for f in file_map} for d in dirs) or
                type(snapshot.get("bytes")) is not int or
                snapshot["bytes"] != sizes):
            return False, "Profile snapshot topology/size evidence incomplete."
        return True, f"{len(file_map)} recorded profile files and whole-directory snapshot (not rehashed)."
    return False, "No Hub-owned transactional installation inventory for this manual dependency."


def _integrity(comp, integrity, game_id):
    if not isinstance(integrity, dict) or integrity.get("game_id") != game_id:
        return False, "No current game's on-demand integrity result."
    rows = integrity.get("rows")
    if not isinstance(rows, list):
        return False, "Installed-file integrity inventory is incomplete."
    matches = [r for r in rows if isinstance(r, dict) and str(r.get("id")) == str(comp["id"])]
    if len(matches) != 1:
        return False, "No unique per-component installed-file integrity result."
    r = matches[0]
    n = r.get("files")
    if (r.get("status") != "Verified" or type(n) is not int or n < 1 or
            type(r.get("checked")) is not int or r["checked"] != n):
        return False, "Installed files were not completely SHA-256 verified."
    presence = integrity.get("presence")
    if (not isinstance(presence, dict) or presence.get("status") != "Ready" or
            presence.get("required_bad")):
        return False, "Required-mod presence remains unknown/review required."
    return True, f"{n} tracked installed files matched at last on-demand check."


def _safety(comp, safety, game_id):
    if not isinstance(safety, dict) or safety.get("game_id") != game_id:
        return None, False, "No current-game pre-update impact review."
    rows = safety.get("rows")
    if not isinstance(rows, list):
        return None, False, "Pre-update impact inventory is incomplete."
    matches = [r for r in rows if isinstance(r, dict) and str(r.get("id")) == str(comp["id"])]
    if len(matches) != 1:
        return None, False, "No unique per-component prospective destination review."
    row = matches[0]
    target_count = row.get("future_destinations")
    collisions = row.get("ownership_conflicts")
    untracked = row.get("untracked_collisions")
    mapped = (type(target_count) is int and 0 < target_count <= MAX_OWNED and
              isinstance(collisions, list) and isinstance(untracked, list) and
              not collisions and not untracked and
              row.get("eligible") is False and row.get("backups_verified_for_update") is False)
    if not mapped:
        return None, False, "Target mapping is missing, colliding, or not safely supported."
    return target_count, True, (
        f"{target_count} proposed destinations inspected read-only; "
        "a future staging transaction must revalidate every path.")


def _handoff(kind):
    if kind == "pinned_package":
        return (
            "Signed-off recipe pin for every replacement SHA-256; do not silently upgrade.",
            "Revalidate every ZIP member with the existing pinned-package mapper.",
            "Whole-package dependency ordering and retired-plugin directories require new backup/rollback handling.")
    if kind == "uevr_profile":
        return (
            "Prove the Windows/Wine prefix and exact profile destination; reject any game currently running.",
            "Back up the complete current profile tree, including empty directories and permissions.",
            "Stage a whole-directory swap and verify recovery of the original tree.")
    if kind == "uevr_injector":
        return (
            "UEVR injector is not represented by the profile's installation record.",
            "Establish separate installer ownership, file destination rules and recovery policy.")
    if kind == "gameroot":
        return (
            "Resolve Nexus ZIP wrappers and component-specific target mapping before staging.",
            "Protect overlaps and untracked mods across all selected components and versions.",
            "Revalidate each recorded game-root hash and preserve the game's original backup chain.")
    return ("Manual/guide workflow cannot be adopted into transactional update ownership automatically.",)


def assess(recipe, state=None, readiness=None, integrity=None, safety=None):
    """Return purely descriptive, *never executable* versioned contracts.

    Offline callers may pass fixture dicts. The function does no I/O and does
    not accept a destination directory, authorization callback or executor.
    """
    if not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str):
        raise ValueError("Invalid recipe.")
    rid = recipe["id"]
    state = state if isinstance(state, dict) else {}
    parts = download_planner.plan_components(recipe)
    if len(parts) > MAX_COMPONENTS:
        raise ValueError("Too many dependencies for a bounded integration review.")
    decisions = {}
    duplicate_decisions = set()
    if isinstance(readiness, list):
        for entry in readiness:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                continue
            cid = entry["id"]
            if cid in decisions:
                duplicate_decisions.add(cid)
            else:
                decisions[cid] = entry
    for cid in duplicate_decisions:
        decisions.pop(cid, None)
    contracts = []
    for comp in parts:
        cid = str(comp["id"])
        kind = _adapter(recipe, cid)
        name, scope, expected = ADAPTERS[kind]
        owned, ownership = _ownership(recipe, comp, state, kind)
        integrity_ok, integrity_detail = _integrity(comp, integrity, rid)
        targets, mapping_ok, mapping_detail = _safety(comp, safety, rid)
        decision = decisions.get(cid, {})
        archive_ok = decision.get("code") == "candidate"
        gaps = []
        if kind in ("manual", "uevr_injector"):
            gaps.append("No supported Hub-managed update adapter for this dependency.")
        if not owned:
            gaps.append(ownership)
        if not archive_ok:
            gaps.append("Verified newer local release / online version comparison is not established.")
        if not integrity_ok:
            gaps.append(integrity_detail)
        if not mapping_ok:
            gaps.append(mapping_detail)
        gaps.extend(text for _, text in STATIC_BLOCKERS)
        contracts.append({
            "schema": SCHEMA_VERSION,
            "id": cid, "name": str(comp.get("name", cid)), "game_id": rid,
            "phase": int(comp.get("phase", 1)),
            "adapter": kind, "adapter_label": name, "target_scope": scope,
            "expected_installer": (EXPECTED_PACKAGE_MARKERS.get(rid, "unmanaged")
                                   if kind == "pinned_package" else expected),
            "contract_stage": "Draft — not executable" if kind in
                              ("pinned_package", "gameroot", "uevr_profile")
                              else "Manual integration required",
            "recorded_ownership": owned, "ownership_note": ownership,
            "integrity_observed": integrity_ok, "integrity_note": integrity_detail,
            "verified_future_candidate": archive_ok,
            "mapped_destinations": targets, "mapping_note": mapping_detail,
            "requirements": [
                {"id":"ownership", "observed": owned, "detail": ownership},
                {"id":"integrity", "observed": integrity_ok, "detail": integrity_detail},
                {"id":"candidate", "observed": archive_ok,
                 "detail": "Latest version and source archive were reconciled only for planning."
                           if archive_ok else "No uniquely verified newer source release."},
                {"id":"prospective_mapping", "observed": mapping_ok, "detail": mapping_detail},
                *({"id": gate, "observed": False, "detail": text}
                  for gate, text in STATIC_BLOCKERS)
            ],
            "handoff": list(_handoff(kind)), "blockers": gaps,
            "authorized": False, "live_executor_connected": False,
            "replacement_supported": False, "requires_explicit_future_approval": True,
        })
    return {
        "schema": SCHEMA_VERSION, "game_id": rid,
        "status": "Planning only — all live update integrations blocked",
        "contracts": contracts, "drafts": sum(
            c["contract_stage"].startswith("Draft") for c in contracts),
        "manual": sum(c["contract_stage"].startswith("Manual") for c in contracts),
        "authorized": False, "live_executor_connected": False,
        "requires_explicit_future_approval": True,
    }


def fixture_adapter_rehearsal():
    """Execute strictly synthetic byte fixtures for each *draft* adapter.

    The actual installer functions are intentionally neither imported nor
    called. The fixture engine accepts no real game paths or mod archives.
    These prove only the normalized contract's transaction needs, not runtime
    or real-format compatibility.
    """
    from . import offline_transaction as tx
    examples = (
        ("pinned_package",
         {"BepInEx/core/loader.dll":b"pinned-old", "BepInEx/config/mod.ini":b"manual-owned"},
         {"BepInEx/core/loader.dll":b"pinned-new", "BepInEx/plugins/vrrender.dll":b"new-plugin"}),
        ("uevr_profile",
         {"profile/config.txt":b"old-profile", "profile/empty/retained.txt":b"original"},
         {"profile/config.txt":b"new-profile", "profile/extra/gesture.ini":b"gesture"}),
        ("gameroot",
         {"bin/x64/plugin.dll":b"component-old", "red4ext/config.ini":b"original-config"},
         {"bin/x64/plugin.dll":b"component-new", "r6/scripts/addon.lua":b"addon"}),
    )
    rows = []
    for label, installed, incoming in examples:
        with tx.fixture_sandbox(installed, incoming) as fixture:
            plan = tx.build_plan(fixture)
            try:
                tx.execute(fixture, plan, fault="after_replace:2")
            except tx.SimulatedCrash:
                pass
            else:
                raise AssertionError("The planned interruption did not occur.")
            if tx.status(fixture)["phase"] != "applying":
                raise AssertionError("Expected interrupted fixture journal.")
            recovered = tx.recover(fixture)
            if (tx._inventory(fixture) != plan.before or
                tx._snapshot_dirs(fixture) != tx._journal(fixture)["dirs_before"] or
                any(tx._read(fixture, "installed", name) != content
                    for name, content in installed.items()) or
                any(tx._read(fixture, "installed", name, optional=True) is not None
                    for name in incoming if name not in installed)):
                raise AssertionError("Fixture rollback did not recover original state.")
            rows.append({
                "adapter": label, "fixture_recovered": True,
                "fresh_backups_verified": recovered["checked"],
                "directory_topology_restored": True, "authorized": False,
            })
    return {
        "fixture_only": True, "tests": rows, "live_executor_connected": False,
        "authorized": False, "real_game_files_modified": False,
        "temporary_fixtures_discarded": True,
    }
