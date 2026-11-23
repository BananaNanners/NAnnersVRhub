# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-J advisory pre-update impact and rollback review.

Runs only after a user action. Reads local release/backup evidence but NEVER
writes game files, stages an install, repairs, downloads, restores, or grants
installation approval. Historical retained originals are NOT a fresh backup
of the installed mods which a future update would replace.
"""
import os
import re
from pathlib import Path, PurePosixPath
from threading import Event

from . import hub, bepinex, installed_integrity, install_review, profile_safety, download_planner, cyberpunk_archive_mapping, payload_evidence

MAX_ITEMS = 2500
MAX_TOTAL_BACKUP_BYTES = 2 * 1024 * 1024 * 1024
MAX_DETAIL = 12
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _rel(value):
    return installed_integrity._relative(value)


def _untrusted(message):
    return {"status": "Needs review", "verified": 0, "expected": 0,
            "bytes": 0, "reason": message}


def _safe_backup_root(record):
    """User-state metadata may NOT redirect reads outside the Hub backup root."""
    base = hub.state_file().parent
    store = base / "backups"
    supplied = record.get("backup")
    if not isinstance(supplied, str) or not supplied:
        return None
    candidate = Path(supplied)
    if (not candidate.is_absolute() or candidate.parent != store or
            installed_integrity._root(store) is None or
            installed_integrity._root(candidate) is None):
        return None
    return candidate


def _check_backup_files(root, expected, cancel):
    """Verify stored originals using read-only nofollow dirfd hashing."""
    if not isinstance(expected, dict) or len(expected) > MAX_ITEMS:
        return _untrusted("Retained original inventory is missing or exceeds limits.")
    if not expected:
        return {"status": "No prior originals", "verified": 0, "expected": 0,
                "bytes": 0, "reason": (
                    "No original files were recorded as overwritten. This does not "
                    "provide the NEW pre-update backup of current installed mod files.")}
    if installed_integrity._root(root) is None:
        return _untrusted("Retained backup directory missing, unsafe or symlinked.")
    total = 0
    verified = 0
    try:
        fd = os.open(root, installed_integrity.DIR_FLAGS)
        with installed_integrity._close_fd(fd):
            for name, meta in expected.items():
                if cancel.is_set():
                    raise installed_integrity.Cancelled()
                rel = _rel(name)
                if rel is None or not isinstance(meta, dict):
                    return _untrusted("Retained original inventory contains unsafe paths.")
                digest = meta.get("sha256")
                size = meta.get("size")
                if (not isinstance(digest, str) or not _HASH.fullmatch(digest)
                        or (size is not None and (type(size) is not int or size < 0))):
                    return _untrusted("Original backup SHA or size record is invalid.")
                result, value = installed_integrity._read_hash(
                    fd, rel, size, cancel, MAX_TOTAL_BACKUP_BYTES - total)
                if result != "Hash":
                    return _untrusted(
                        f"Original backup {rel}: {result}. Safe verification incomplete.")
                current, count = value
                total += count
                if current != digest:
                    return _untrusted(f"Original backup {rel} differs from the saved SHA-256.")
                verified += 1
    except (OSError, ValueError):
        return _untrusted("Retained original backup cannot be safely read.")
    return {"status": "Recorded originals matched", "verified": verified,
            "expected": len(expected), "bytes": total,
            "reason": ("Retained prior-game originals matched recorded SHA-256. "
                       "Current mod files still need their own NEW pre-update backup.")}


def _backup_evidence(recipe, state, cancel):
    """Only validate backups the current ownership record actually describes."""
    rid = recipe["id"]
    game = state.get(rid)
    if recipe.get("method") == "uevr" and recipe.get("profile"):
        entry = state.get(rid + ":profile")
        if not isinstance(entry, dict) or entry.get("installer") != "uevr-profile-2":
            return _untrusted("Legacy/manual UEVR profile has no verifiable recovery manifest.")
        try:
            original = entry.get("original")
            if not isinstance(original, dict) or type(original.get("exists")) is not bool:
                return _untrusted("UEVR profile original snapshot missing.")
            if not original["exists"]:
                if entry.get("backup"):
                    return _untrusted("Unexpected backup for originally absent UEVR profile.")
                return {"status": "No prior originals", "verified": 0, "expected": 0,
                        "bytes": 0, "reason": (
                            "Original profile did not exist. Future replacement still needs "
                            "a NEW, verified backup of the current profile directory.")}
            root = _safe_backup_root(entry)
            if root is None:
                return _untrusted("UEVR profile recovery directory missing or outside Hub storage.")
            # The existing profile recovery checker knows how to verify the
            # COMPLETE snapshot (including empty directories and additions).
            if cancel.is_set():
                raise installed_integrity.Cancelled()
            actual = profile_safety._snapshot(root)
            if actual != original:
                return _untrusted("Retained UEVR originals differ from the saved whole-directory snapshot.")
            return {"status": "Recorded originals matched",
                    "verified": len(actual["files"]), "expected": len(actual["files"]),
                    "bytes": actual["bytes"], "reason": (
                        "Retained UEVR originals match the full recorded directory snapshot. "
                        "A NEW whole-directory backup of the current profile is still required.")}
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            return _untrusted("Retained UEVR original snapshot cannot be verified safely.")
    if not isinstance(game, dict):
        return _untrusted("No Hub-owned installation state for this game.")
    mode = game.get("installer")
    if mode == "gameroot-2":
        originals = game.get("originals")
        hashes = game.get("installed_sha256")
        if (not isinstance(originals, dict) or not isinstance(hashes, dict)
                or not originals or set(originals) != set(hashes)):
            return _untrusted("Game-root originals and installed manifest disagree.")
        wanted = {}
        for name, original in originals.items():
            if original is not None:
                wanted["files/" + name] = original
        root = _safe_backup_root(game)
        if root is None:
            return _untrusted("Game-root retained backup path missing or outside Hub storage.")
        return _check_backup_files(root, wanted, cancel)
    if mode in ("vhvr-1", "submersed-vr-1", "ervr-1"):
        originals = game.get("originals")
        hashes = game.get("original_hashes")
        if not isinstance(originals, list) or not isinstance(hashes, dict):
            return _untrusted("Pinned-package original backup manifest missing.")
        if len(set(originals)) != len(originals) or set(originals) != set(hashes):
            return _untrusted("Pinned-package original file list and SHA records disagree.")
        wanted = {"files/" + name: {"sha256": hashes[name]} for name in originals}
        root = _safe_backup_root(game)
        if root is None:
            return _untrusted("Pinned-package retained backup path missing or outside Hub storage.")
        checked = _check_backup_files(root, wanted, cancel)
        if game.get("retired"):
            return _untrusted(
                "Retired plugin directories require additional full-directory recovery review.")
        return checked
    return _untrusted("Legacy or manual install has no verified backup ownership record.")


def _managed_files(recipe, component, state):
    """Current *recorded* ownership, not predicted new ZIP destinations."""
    rid = recipe["id"]
    cid = str(component["id"])
    game = state.get(rid)
    if recipe.get("method") == "uevr" and cid == "profile":
        rec = state.get(rid + ":profile")
        base = rec.get("root") if isinstance(rec, dict) else None
        snap = rec.get("installed", {}) if isinstance(rec, dict) else {}
        files = snap.get("files") if isinstance(snap, dict) else None
        if not isinstance(base, str) or not isinstance(files, dict):
            return ()
        paths = [str(Path(base) / name) for name in files]
    elif isinstance(game, dict) and isinstance(game.get("packages"), dict):
        rec = game["packages"].get(cid, {})
        paths = rec.get("files", []) if isinstance(rec, dict) else []
    elif isinstance(game, dict) and isinstance(game.get("components"), dict):
        rec = game["components"].get(cid, {})
        paths = rec.get("files", []) if isinstance(rec, dict) else []
    else:
        return ()
    if (not isinstance(paths, list) or len(paths) > MAX_ITEMS
            or any(not isinstance(p, str) or len(p) > 4096 for p in paths)):
        return ()
    return tuple(sorted(set(paths)))


def _prospective(recipe, component, row, cancel, *, payload_details=None):
    """Determine destinations only when the existing bounded archive parser can.

    Gameroot ZIPs may contain wrappers and install-specific remapping; never
    claim raw ZIP entries are the final game paths.
    """
    if (not isinstance(row, dict) or row.get("candidate_incomplete") or
            row.get("ambiguous") or row.get("release_review") or
            row.get("status") not in ("Pinned SHA-256 verified", "Possible archive — inspect first")
            or not isinstance(row.get("file"), str) or not row["file"]):
        return (), "Candidate identity incomplete, missing, or recipe-pin blocked."
    path = Path(row["file"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        return (), "Candidate archive absent or unsafe; rescan."
    if any(parent.is_symlink() for parent in path.parents):
        return (), "Candidate ZIP is inside a symlinked directory; rescan safely."
    if cancel.is_set():
        raise installed_integrity.Cancelled()
    if path.suffix.casefold() != ".zip":
        return (), "Non-ZIP archive target mapping is unsupported."
    try:
        # Independently re-hash the candidate at review time. Saved scan
        # metadata can become stale after a ZIP is replaced in Downloads.
        before = path.stat()
        if before.st_size > install_review.MAX_ARCHIVE_BYTES:
            return (), "Candidate exceeds bounded archive review limit."
        candidate_sha = profile_safety._digest(path)
        after = path.stat()
        if (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns,
                before.st_ctime_ns) != (after.st_ino, after.st_dev, after.st_size,
                                       after.st_mtime_ns, after.st_ctime_ns):
            return (), "Candidate changed during review; rescan."
        if row.get("status") == "Pinned SHA-256 verified":
            expected = component.get("sha256")
        else:
            matches = [entry for entry in row.get("candidates", [])
                       if (isinstance(entry, dict) and
                           entry.get("file") == str(path) and entry.get("tags"))]
            expected = matches[0].get("sha256") if len(matches) == 1 else None
        # Cyberpunk single-candidate scans do not normally retain a known
        # Nexus SHA. Bind this review to the checked scan's file size and a
        # *fresh* stable digest without calling that proof of source identity.
        single_unpinned_cyberpunk = (
            recipe.get("id") == "cyberpunk-2077"
            and row.get("status") == "Possible archive — inspect first"
            and expected is None and row.get("matches") == 1
            and type(row.get("size")) is int
            and row["size"] == before.st_size
        )
        if (not single_unpinned_cyberpunk and
                (not isinstance(expected, str) or candidate_sha != expected)):
            return (), "Candidate digest no longer matches recorded scan; rescan."
        # X: classify Cyberpunk ZIP member *metadata* before strict W mapping.
        # A recognized README is advisory evidence, never permission to drop
        # it from a complete install-target list or install anything.
        if recipe.get("id") == "cyberpunk-2077":
            evidence = payload_evidence.classify_zip(recipe, component, path)
            if payload_details is not None:
                payload_details.update(evidence)
            if not evidence["metadata_preflight_passed"]:
                return (), "Cyberpunk ZIP payload safety preflight failed; review required."
            # The advisory report must refer to the same stable archive hash
            # verified above. Never show a classification of changed bytes.
            if profile_safety._digest(path) != candidate_sha:
                if payload_details is not None:
                    payload_details.clear()
                return (), "Candidate digest changed during payload classification; rescan."
        else:
            install_review._zip_preflight(path)
        selected = ()
        mapping = "Exact future destinations require a separately approved staging/mapping design."
        if recipe.get("packages") and row.get("status") == "Pinned SHA-256 verified":
            package, members = bepinex.archive_plan(path, recipe)
            if str(package.get("id")) != str(component["id"]):
                return (), "Pinned ZIP maps to another package; no target plan."
            selected = tuple(sorted(members.values()))
            mapping = "Mapped by existing pinned-package archive parser."
        elif recipe.get("method") == "uevr" and component["id"] == "profile":
            # Does not extract the ZIP or read/modify the destination.
            from zipfile import ZipFile
            with ZipFile(path) as z:
                entries = profile_safety._archive_entries(z)
                selected = tuple(sorted(rel for _, rel in entries))
                mapping = "Mapped as profile-relative ZIP entries; current files still need protection."
        elif recipe.get("id") == "cyberpunk-2077" and recipe.get("method") == "gameroot":
            # Nexus component identity is filename-based, not source proof.
            # Single-candidate scans may lack SHA metadata: only accept the
            # stable, freshly hashed ZIP when exact scan size and uniqueness
            # are established. This is NOT an authenticated Nexus release.
            if row.get("status") != "Possible archive — inspect first":
                return (), "Cyberpunk candidate is not a uniquely reviewed ZIP."
            if (not isinstance(row.get("matches"), int) or row["matches"] < 1
                    or type(row.get("size")) is not int
                    or row["size"] != before.st_size):
                return (), "Cyberpunk archive scan size or candidate identity is stale."
            selected, _ = cyberpunk_archive_mapping.map_checked_zip(
                recipe, component, path)
            mapping = (
                "Mapped by strict Cyberpunk game-root ZIP parser; "
                "all regular members accounted for, source version unverified.")
        if selected:
            # A ZIP changed between SHA validation and reading its central
            # directory is never accepted as a stable target map or a
            # Cyberpunk payload-classification report.
            if profile_safety._digest(path) != candidate_sha:
                if payload_details is not None:
                    payload_details.clear()
                return (), "Candidate digest changed during mapping; rescan."
            return selected, mapping
    except cyberpunk_archive_mapping.MappingBlocked as exc:
        # The strict W mapping may refuse safe documentation/optional members
        # which X classified. Keep that classification only if the reviewed
        # ZIP's digest is still identical.
        if payload_details is not None and payload_details:
            try:
                if profile_safety._digest(path) != candidate_sha:
                    payload_details.clear()
                    return (), "Candidate digest changed during strict mapping; rescan."
            except (OSError, RuntimeError, ValueError):
                payload_details.clear()
                return (), "Candidate cannot be reverified after mapping; rescan."
        return (), "Cyberpunk ZIP review blocked: " + str(exc)
    except (OSError, RuntimeError, ValueError, install_review.PlanRejected):
        # Incomplete or changed metadata never leaves a stale advisory payload.
        if payload_details is not None:
            payload_details.clear()
        # Do not surface raw path content or untrusted archive metadata in GUI.
        return (), "Archive metadata could not be safely inspected for a replacement map."
    return (), "Exact future destinations require a separately approved staging/mapping design."


def _duplicate_owners(recipe, component, state):
    cid = str(component["id"])
    owned = _managed_files(recipe, component, state)
    conflicts = []
    for other in download_planner.plan_components(recipe):
        if str(other["id"]) == cid or other["id"] == "guide":
            continue
        theirs = {x.casefold() for x in _managed_files(recipe, other, state)}
        conflicts += [str(Path(x).name) for x in owned if x.casefold() in theirs]
    return sorted(set(conflicts))[:MAX_DETAIL]


def _untracked_destinations(recipe, component, proposed, recorded):
    """Bounded, read-only collision hints; never a clearance certificate."""
    if not proposed:
        return []
    if recipe.get("method") == "uevr":
        root = hub.profile_dir(recipe)
    else:
        root = hub.game_path(recipe)
    if installed_integrity._root(root) is None:
        return ["Destination directory missing or unsafe."]
    tracked = {str(Path(x)).casefold() for x in recorded}
    collisions = []
    for rel in proposed[:MAX_ITEMS]:
        path = _rel(rel)
        if path is None:
            return ["Archive contains an unsafe target path."]
        try:
            target = bepinex.target(root, path.as_posix())
        except (RuntimeError, OSError, ValueError):
            return ["Archive destination collides with a symlink or different-case path."]
        if (target.is_symlink() or target.exists()) and str(target).casefold() not in tracked:
            collisions.append(path.as_posix())
        if len(collisions) >= MAX_DETAIL:
            break
    return collisions


def review(recipe, scan, state, decisions, integrity=None, *, cancel=None):
    """Build read-only advisory report. Never grants installation authorization."""
    if cancel is None:
        cancel = Event()
    if not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str):
        raise ValueError("Invalid recipe for safety review.")
    components = [c for c in download_planner.plan_components(recipe) if c["id"] != "guide"]
    if not isinstance(state, dict):
        state = {}
    by_decision = {str(x.get("id")): x for x in decisions or [] if isinstance(x, dict)}
    rows = scan.get("rows", []) if isinstance(scan, dict) else []
    by_archive = {str(x.get("id")): x for x in rows if isinstance(x, dict)}
    warning = scan.get("warning") if isinstance(scan, dict) else None
    backup = _backup_evidence(recipe, state, cancel)
    result_rows = []
    for comp in components:
        if cancel.is_set():
            raise installed_integrity.Cancelled()
        cid = str(comp["id"])
        readiness = by_decision.get(cid, {})
        old = _managed_files(recipe, comp, state)
        safe_map = False
        proposed = ()
        note = "No current candidate ZIP or archive plan."
        current = by_archive.get(cid)
        classified_payload = {}
        # W: a single unambiguous Cyberpunk ZIP may be inspected for its
        # target layout even when the UPDATE-readiness gate is blocked by
        # missing installed-version or Nexus release proof. Mapping is never
        # permission to install: the existing readiness remains unchanged.
        cyberpunk_layout_only = (
            recipe.get("id") == "cyberpunk-2077"
            and recipe.get("method") == "gameroot"
            and isinstance(current, dict)
            and current.get("status") == "Possible archive — inspect first"
            and current.get("matches") == 1
            and current.get("ambiguous") is not True
            and current.get("candidate_incomplete") is not True
            and current.get("release_review") is not True
        )
        if not warning and (readiness.get("code") == "candidate"
                            or cyberpunk_layout_only):
            proposed, note = _prospective(
                recipe, comp, current, cancel,
                payload_details=classified_payload)
            safe_map = bool(proposed)
        # Dev5D3-V: preserve the complete bounded, already-mapped *relative*
        # install-target list in this one-shot read-only result. The public
        # sample remains unchanged; this is never a reusable install plan.
        provenance = (
            "pinned_package" if (
                safe_map and note == "Mapped by existing pinned-package archive parser.")
            else "uevr_profile" if (
                safe_map and note.startswith("Mapped as profile-relative ZIP entries;"))
            else "cyberpunk_gameroot" if (
                safe_map and note.startswith("Mapped by strict Cyberpunk game-root ZIP parser;"))
            else None
        )
        target_list = tuple(str(p) for p in proposed) if (
            safe_map and provenance and len(proposed) <= MAX_ITEMS) else ()
        if target_list and (
                len({p.casefold() for p in target_list}) != len(target_list)
                or any(_rel(p) is None for p in target_list)):
            target_list = ()
            provenance = None
        duplicates = _duplicate_owners(recipe, comp, state)
        untracked = (
            _untracked_destinations(recipe, comp, proposed, old)
            if safe_map else [])
        file_status = next((
            x.get("status") for x in integrity.get("rows", [])
            if str(x.get("id")) == cid
        ), "Not checked") if isinstance(integrity, dict) and integrity.get("game_id") == recipe["id"] else "Not checked"
        # Ownership overlap with another component is never an allowed replacement.
        issue = (
            "Overlapping current mod ownership needs manual review." if duplicates else
            "Untracked or unsafe candidate destinations need manual review." if untracked else
            "Current tracked files need integrity review before replacement." if file_status != "Verified" else
            "Exact new target mapping has not been established." if not safe_map else
            "Candidate targets still need dependency/backup compatibility approval.")
        stages = []
        if len(components) > 1:
            stages.append("Dependencies must be reviewed in recipe order; do not infer install order from ZIP names.")
        if int(comp.get("phase", 1)) > 1:
            stages.append("Later-stage dependency requires its game's first-launch acceptance.")
        result_rows.append({
            "id": cid, "name": str(comp.get("name", cid)),
            "readiness": readiness.get("label", "No update readiness evidence"),
            "current_managed": len(old),
            "current_sample": [str(Path(x).name) for x in old[:MAX_DETAIL]],
            "future_destinations": len(proposed) if safe_map else None,
            "future_sample": list(proposed[:MAX_DETAIL]) if safe_map else [],
            "full_target_list": list(target_list),
            "full_target_provenance": provenance,
            "mapping": note,
            "payload_evidence": classified_payload or None,
            "ownership_conflicts": duplicates,
            "untracked_collisions": untracked,
            "integrity": file_status,
            "file_issue": issue, "order": stages,
            "eligible": False, "backups_verified_for_update": False,
        })
    # A historical backup is never the new snapshot needed before replacing
    # today's installed files. Hence no green "safe to replace" verdict.
    return {
        "game_id": recipe["id"], "status": "Planning only — replacement blocked",
        "rows": result_rows, "existing_backup": backup,
        "new_backup": "A fresh, verified backup of current installed files is required for any future update.",
        "compatibility": "Game/runtime compatibility and dependency ordering have NOT been validated.",
        "recovery": "Rollback simulation has NOT been performed. No replacement or restore is authorized.",
        "authorized": False, "has_live_install_plan": False,
    }
