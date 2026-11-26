# SPDX-License-Identifier: GPL-3.0-only
"""Non-authorizing update review using pinned and candidate archive snapshots."""
from collections import Counter
from pathlib import Path
import copy
import hashlib
import stat
import zipfile
from . import bepinex, bepinex_recognition as recognition, bepinex_update_review, hub


def _inventory(recipe, paths, identities):
    rows = {}
    seen = set()
    roles = set()
    for path in paths:
        path = Path(path)
        with recognition._archive_snapshot(path) as (source, sha, _):
            role = identities.get(sha)
            if role is None or role in roles:
                raise RuntimeError("Missing, duplicate or unrecognized package identity.")
            roles.add(role)
            # Private mapping-only copy: never persist or pass to an installer.
            mapping = copy.deepcopy(recipe)
            pkg = next(p for p in mapping["packages"] if p["id"] == role)
            pkg["sha256"] = sha
            _, members = bepinex.archive_plan_stream(source, mapping, sha, path)
            with zipfile.ZipFile(source) as z:
                for origin, name in members.items():
                    if name.casefold() in seen:
                        raise RuntimeError("Overlapping package destinations.")
                    seen.add(name.casefold())
                    with z.open(origin) as stream:
                        rows[name] = (role, hashlib.file_digest(stream, "sha256").hexdigest())
    if roles != {p["id"] for p in recipe["packages"]}:
        raise RuntimeError("Complete package pair required.")
    folded = {n.casefold() for n in rows}
    if any("/".join(n.casefold().split("/")[:i]) in folded
           for n in rows for i in range(1, len(n.split("/")))):
        raise RuntimeError("Package file/directory collision.")
    return rows


def _target_sample(base, names):
    """Bounded target/ancestor identity sample, including absent targets."""
    result = {}
    for name in sorted(names):
        path = bepinex.target(base, name)
        chain = [base]
        for part in Path(name).parts:
            chain.append(chain[-1] / part)
        for node in chain:
            if node in result:
                continue
            try:
                identity = recognition._identity(node)
            except FileNotFoundError:
                identity = None
            if identity is not None and node != path and not stat.S_ISDIR(identity[2]):
                raise RuntimeError("Unsafe target ancestor.")
            result[node] = identity
    return result


def review(recipe, pinned_archives, folder, *, fetch=None, steam_roots=None):
    """Fresh candidate discovery, exact inventory and current target evidence.

    Never executes a manifest. Obsolete files with historical originals need
    restoration review; unknown new targets are not adopted.
    """
    result = dict(game_id=recipe.get("id"), status="Blocked", rows=(), counts={},
                  blockers=(), candidates=(), write_authorized=False, compatibility_verified=False)
    try:
        if recipe.get("id") not in recognition.SUPPORTED:
            raise RuntimeError("Unsupported managed update recipe.")
        pins = {p["sha256"]:p["id"] for p in recipe["packages"]}
        pinned_archives = tuple(Path(p) for p in pinned_archives)
        state = copy.deepcopy(hub.state())
        discovery = bepinex_update_review.review(recipe, folder, state, fetch=fetch)
        result["candidates"] = discovery["rows"]
        candidates = {r["id"]:r["candidate"] for r in discovery["rows"] if r["candidate"]}
        if not candidates:
            raise RuntimeError("No digest-matched update candidate.")
        if len(pinned_archives) != len(recipe["packages"]):
            raise RuntimeError("Keep both previously supported ZIP archives in your scan folders, then review again.")
        old = _inventory(recipe, pinned_archives, pins)
        paths = {}
        for path in pinned_archives:
            with recognition._archive_snapshot(path) as (_, sha, _):
                paths[pins[sha]] = path
        ids = {sha:role for sha,role in pins.items() if role not in candidates}
        for role, candidate in candidates.items():
            paths[role] = Path(candidate["path"])
            if candidate["sha256"] in pins or candidate["sha256"] in ids:
                raise RuntimeError("Candidate digest overlaps a package identity.")
            ids[candidate["sha256"]] = role
        new = _inventory(recipe, paths.values(), ids)
        names = old.keys() | new.keys()
        prefixes = {"/".join(n.split("/")[:i]) for n in names
                    for i in range(1, len(n.split("/"))+1)}
        if len({n.casefold() for n in prefixes}) != len(prefixes):
            raise RuntimeError("Case-only target rename requires manual review.")
        # Existing mapper is role/hash bound; also require exact candidate hash
        # per selected role on a second read, not a fallback to pinned bytes.
        for role, path in paths.items():
            with recognition._archive_snapshot(path) as (_, sha, _):
                expected = candidates[role]["sha256"] if role in candidates else next(
                    p["sha256"] for p in recipe["packages"] if p["id"] == role)
                if sha != expected:
                    raise RuntimeError("Selected package changed.")
        evidence = recognition.recognize(recipe, pinned_archives, steam_roots)
        if evidence["status"] == "Unknown":
            raise RuntimeError(evidence["detail"])
        if hub.state() != state:
            raise RuntimeError("Ownership records changed during review.")
        sampled = {r["path"]:r for r in evidence["rows"]}
        if {n:(r["component"],r["expected_sha256"]) for n,r in sampled.items()} != old:
            raise RuntimeError("Pinned inventory changed.")
        blockers = []
        if evidence["ownership_record"] != "consistent-record" or evidence["backup_status"] != "originals-match":
            blockers.append("Consistent ownership and original backup evidence required.")
        if evidence["conflicts"]:
            blockers.append("Conflicting plugins require review.")
        base = Path(evidence["root"])
        before_targets = _target_sample(base, names)
        archive_samples = {}
        for role, path in paths.items():
            with recognition._archive_snapshot(path) as (_, sha, ident):
                expected = candidates[role]["sha256"] if role in candidates else next(
                    p["sha256"] for p in recipe["packages"] if p["id"] == role)
                if sha != expected:
                    raise RuntimeError("Selected package changed.")
                archive_samples[path] = (sha, ident)
        originals = set(state.get(recipe["id"], {}).get("originals", [])) if not blockers else set()
        rows = []
        for name in sorted(old.keys() | new.keys(), key=lambda n:(n.casefold(),n)):
            prior, incoming = old.get(name), new.get(name)
            protected = recognition.protected_setting(name)
            current = sampled[name]["actual_sha256"] if prior else None
            action, reason = "Block", "Unsafe or inconsistent target."
            if prior and incoming and prior[0] != incoming[0]:
                reason = "Package ownership transfer requires review."
            elif prior and current is None:
                reason = "Missing managed file; review repair first."
            elif protected and prior:
                action, reason = "Preserve", "Protected setting or binding; migration needs review."
                if incoming != prior:
                    blockers.append("Protected payload migration requires explicit review: " + name)
            elif prior and current != prior[1]:
                reason = "Managed binary differs from pinned bytes."
            elif prior and not incoming and name in originals:
                reason = "Historical original requires restoration review."
            elif prior and not incoming:
                action, reason = "Remove", "Obsolete matching managed file; review only."
            elif prior and incoming:
                action, reason = ("Preserve","Identical payload.") if prior == incoming else ("Replace","Changed matching managed file.")
            elif incoming:
                path = bepinex.target(base,name)
                if path.exists() or path.is_symlink():
                    reason = "Unowned target already exists."
                elif protected:
                    reason = "New protected setting requires migration review."
                elif any(p.exists() and not p.is_dir() for p in path.parents if p != base and base in p.parents):
                    reason = "Parent path is not a directory."
                else:
                    action, reason = "Install", "New absent target; review only."
            rows.append(dict(path=name, component=(incoming or prior)[0], action=action,
                             reason=reason, old_sha256=prior[1] if prior else None,
                             current_sha256=current, new_sha256=incoming[1] if incoming else None))
        if any(r["action"]=="Block" for r in rows):
            blockers.append("One or more file changes require manual review.")
        # Re-sample actual bytes/ownership and all proposed target identities.
        after = recognition.recognize(recipe, pinned_archives, steam_roots)
        keys = ("status", "root", "ownership_record", "backup_status", "conflicts", "rows")
        if any(after.get(k) != evidence.get(k) for k in keys) or hub.state() != state:
            blockers.append("Installed or ownership evidence changed during review.")
        for path, expected in archive_samples.items():
            with recognition._archive_snapshot(path) as (_, sha, ident):
                if (sha, ident) != expected:
                    blockers.append("Selected archive changed during review.")
        if _target_sample(base, names) != before_targets:
            blockers.append("Target identities changed during review.")
        if blockers:
            for row in rows:
                if row["action"] in ("Install", "Replace", "Remove"):
                    row.update(action="Block", reason="Global manifest blocker: " + row["reason"])
        return dict(result, rows=tuple(rows), counts=dict(Counter(r["action"] for r in rows)),
                    blockers=tuple(blockers), status="Blocked" if blockers else "Review required",
                    outside_inventory="Leave untouched; not inventoried or certified.")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, zipfile.BadZipFile, EOFError) as exc:
        return dict(result, blockers=(str(exc),))
