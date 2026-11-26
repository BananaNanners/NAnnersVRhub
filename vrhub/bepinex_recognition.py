# SPDX-License-Identifier: GPL-3.0-only
"""Read-only current-byte evidence for the two pinned BepInEx VR pairs."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import stat
import zipfile

from . import bepinex, hub

SUPPORTED = frozenset(("subnautica", "valheim"))
SETTINGS = frozenset((".cfg", ".ini", ".json", ".txt"))


def _identity(path):
    s = path.lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def _sample(recipe, archives, steam_roots):
    game = hub.game_path(recipe, steam_roots)
    cfg = bepinex.policy(recipe)
    if not game or game.is_symlink() or not game.is_dir():
        raise RuntimeError("Windows game directory not verified.")
    base = game.resolve()
    root_identity = _identity(base)
    exe = bepinex.target(base, cfg["exe"])
    data = bepinex.target(base, cfg["data"])
    if not exe.is_file() or not data.is_dir():
        raise RuntimeError("Windows game layout not verified.")
    state = hub.state()
    if not isinstance(state, dict):
        raise RuntimeError("Invalid installation records.")
    record = state.get(recipe["id"])
    wanted = {p["id"] for p in recipe["packages"]}
    seen_roles, seen_names, rows = set(), set(), []
    for archive in archives:
        identity = _identity(archive)
        if not stat.S_ISREG(identity[2]):
            raise RuntimeError("Archive must be a regular file.")
        package, members = bepinex.archive_plan(archive, recipe)
        role = package["id"]
        if role in seen_roles:
            raise RuntimeError("Duplicate dependency package.")
        seen_roles.add(role)
        with zipfile.ZipFile(archive) as z:
            for origin, name in sorted(members.items()):
                key = name.casefold()
                if key in seen_names:
                    raise RuntimeError("Overlapping dependency paths.")
                seen_names.add(key)
                with z.open(origin) as stream:
                    expected = hashlib.file_digest(stream, "sha256").hexdigest()
                path = bepinex.target(base, name)
                try:
                    before = _identity(path)
                except FileNotFoundError:
                    before = None
                actual = None
                if before is None:
                    status = "missing"
                elif not stat.S_ISREG(before[2]) or before[3] != 1 or before[4] > bepinex.MAX_FILE:
                    raise RuntimeError("Unsafe dependency target: " + name)
                else:
                    actual = bepinex.digest(path)
                    if _identity(path) != before:
                        raise RuntimeError("Dependency changed during sampling.")
                    status = ("matching" if actual == expected else
                              "modified-settings" if path.suffix.lower() in SETTINGS else
                              "different")
                rows.append((role, name, status, expected, actual, before))
        if _identity(archive) != identity or bepinex.digest(archive) != package["sha256"]:
            raise RuntimeError("Archive changed during sampling.")
    if seen_roles != wanted or not rows:
        raise RuntimeError("Complete pinned package pair required.")
    if _identity(base) != root_identity:
        raise RuntimeError("Game root changed during sampling.")
    return (str(base), root_identity, record, tuple(sorted(rows)),
            tuple(sorted(str(p) for p in bepinex.conflicts(base, recipe))))


def recognize(recipe, archives, steam_roots=None):
    """No ownership adoption, repair, state writes or readiness authorization."""
    result = dict(status="Unknown", rows=(), counts={}, ownership_established=False,
                  gameplay_verified=False, write_authorized=False)
    if recipe.get("id") not in SUPPORTED:
        return dict(result, detail="Unsupported recognition recipe.")
    try:
        paths = tuple(Path(p) for p in archives)
        if len(paths) != 2:
            raise RuntimeError("Scan both verified local ZIP archives first.")
        if steam_roots is None:
            steam_roots = [Path(p).expanduser() for p in os.environ.get("VRHUB_STEAM_ROOTS", "").split(":") if p] or None
        before = _sample(recipe, paths, steam_roots)
        after = _sample(recipe, paths, steam_roots)
        if before != after:
            raise RuntimeError("Evidence changed during sampling.")
        base, _, record, rows, conflicts = before
        counts = Counter(row[2] for row in rows)
        return dict(result, status="Review" if conflicts or any(row[2] != "matching" for row in rows) else "Pinned bytes match",
                    sampled_at=datetime.now(timezone.utc).isoformat(), root=base,
                    record_present=record is not None, conflicts=conflicts,
                    rows=tuple(dict(component=r[0], path=r[1], status=r[2],
                                    expected_sha256=r[3], actual_sha256=r[4]) for r in rows),
                    counts={k: counts[k] for k in ("matching", "missing", "different", "modified-settings")},
                    detail="Current sampled bytes only. Modified settings need review; ownership and gameplay are not established.")
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, zipfile.BadZipFile, EOFError) as exc:
        return dict(result, detail=str(exc))


def archives_from_rows(recipe, rows):
    """Use only the complete current pinned selection; the worker rehashes."""
    if recipe.get("id") not in SUPPORTED or len(rows) != 2:
        return ()
    packages = recipe.get("packages", ())
    by_id = {r.get("id"): r for r in rows}
    if len(packages) != 2 or len(by_id) != 2:
        return ()
    result = []
    for package in packages:
        row = by_id.get(package["id"], {})
        if (row.get("status") != "Pinned SHA-256 verified" or
                row.get("sha256") != package["sha256"] or
                row.get("ambiguous") or row.get("candidate_incomplete") or
                not row.get("file")):
            return ()
        result.append(Path(row["file"]))
    return tuple(result)


def summary_text(result):
    if result.get("status") == "Unknown":
        return "Current dependency check: Unknown. " + result.get("detail", "")
    c = result["counts"]
    return (f"Current dependency check: {result['status']}. "
            f"{c['matching']} matching, {c['missing']} missing, "
            f"{c['different']} different, {c['modified-settings']} modified settings. "
            f"{len(result['conflicts'])} known conflicting plugin(s). "
            "Current bytes only; ownership, compatibility and gameplay are not verified. "
            "Repair and update are not authorized.")
