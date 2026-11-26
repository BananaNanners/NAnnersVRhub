# SPDX-License-Identifier: GPL-3.0-only
"""Read-only current-byte evidence for the two pinned BepInEx VR pairs."""
from collections import Counter
from contextlib import contextmanager
import io
import re
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import stat
import zipfile

from . import bepinex, hub, installed_integrity

SUPPORTED = frozenset(("subnautica", "valheim"))
SETTINGS = frozenset((".cfg", ".ini", ".json", ".txt"))


def _stat_identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def _identity(path):
    return _stat_identity(path.lstat())


def protected_setting(name):
    """Conservative review classification; never an overwrite permission."""
    parts = name.casefold().split("/")
    return (Path(name).suffix.lower() in SETTINGS
            or any(p in {"config", "configs", "settings", "bindings", "steamvr"}
                   for p in parts[:-1])
            or any(word in parts[-1] for word in ("binding", "controller", "actions")))


def _safe_hash(base, name, before):
    """Use bounded descriptor reads, checking every ancestor before and after."""
    rel = installed_integrity._relative(name)
    if rel is None:
        raise RuntimeError("Unsafe dependency path.")
    chain = [base]
    for part in rel.parts[:-1]:
        chain.append(chain[-1] / part)
    identities = tuple(_identity(p) for p in chain)
    if any(not stat.S_ISDIR(i[2]) for i in identities):
        raise RuntimeError("Unsafe dependency directory.")
    fd = os.open(base, installed_integrity.DIR_FLAGS)
    try:
        if _stat_identity(os.fstat(fd)) != identities[0]:
            raise RuntimeError("Game root changed.")
        outcome, value = installed_integrity._read_hash(
            fd, rel, before[4], None, bepinex.MAX_FILE)
        if (outcome != "Hash" or _identity(base / name) != before
                or tuple(_identity(p) for p in chain) != identities):
            raise RuntimeError("Dependency changed or cannot be safely read: " + name)
        return value[0]
    finally:
        os.close(fd)


@contextmanager
def _archive_snapshot(path):
    """Read a bounded immutable ZIP snapshot from a regular single-link file."""
    path = path.absolute()
    if path.suffix.lower() != ".zip" or path.resolve() != path:
        raise RuntimeError("Unsafe archive path.")
    before = _identity(path)
    if not stat.S_ISREG(before[2]) or before[3] != 1 or before[4] > bepinex.MAX_TOTAL:
        raise RuntimeError("Unsafe archive file.")
    fd = os.open(path, installed_integrity.SAFE_FLAGS)
    with os.fdopen(fd, "rb") as source:
        if _stat_identity(os.fstat(source.fileno())) != before:
            raise RuntimeError("Archive changed before read.")
        data = source.read(bepinex.MAX_TOTAL + 1)
        if (len(data) != before[4] or _stat_identity(os.fstat(source.fileno())) != before
                or _identity(path) != before):
            raise RuntimeError("Archive changed during read.")
    yield io.BytesIO(data), hashlib.sha256(data).hexdigest(), before
    if _identity(path) != before:
        raise RuntimeError("Archive changed during review.")


def _backup_evidence(recipe, record, rows):
    """Validate recorded originals; legacy retired trees lack trusted hashes."""
    if not isinstance(record, dict):
        return ("unverified", ())
    try:
        originals = record.get("originals")
        retired = record.get("retired")
        hashes = record.get("original_hashes")
        expected = {r[1] for r in rows}
        if (not isinstance(originals, list) or not all(isinstance(n, str) for n in originals)
                or len(set(originals)) != len(originals) or not set(originals) <= expected
                or not isinstance(hashes, dict) or set(hashes) != set(originals)
                or not isinstance(retired, list) or not all(isinstance(n, str) for n in retired)
                or len(set(retired)) != len(retired)
                or not set(retired) <= set(bepinex.policy(recipe)["retired"])):
            return ("inconsistent", ())
        root = Path(record["backup"])
        parent = (hub.state_file().parent / "backups").resolve()
        if (root.parent != parent or root.resolve() != root
                or not re.fullmatch(re.escape(recipe["id"]) + "-[0-9a-f]{32}", root.name)
                or not stat.S_ISDIR(root.lstat().st_mode)):
            return ("unsafe", ())
        evidence = [(".", _identity(root))]
        for name in sorted(originals):
            path = bepinex.target(root, "files/" + name)
            before = _identity(path)
            if (not stat.S_ISREG(before[2]) or before[3] != 1
                    or before[4] > bepinex.MAX_FILE
                    or _safe_hash(root, "files/" + name, before) != hashes[name]):
                return ("inconsistent", ())
            evidence.append((name, before))
        if _identity(root) != evidence[0][1]:
            return ("unsafe", ())
        return ("retired-unverified" if retired else "originals-match", tuple(evidence))
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        return ("unsafe", ())


def _ownership(recipe, base, record, rows):
    """Exact record consistency only; not proof of authority or backup validity."""
    if record is None:
        return "unrecorded"
    if not isinstance(record, dict):
        return "inconsistent"
    expected = {r[1]: r[3] for r in rows}
    packages = record.get("packages")
    def exact_list(value, wanted):
        return (isinstance(value, list) and all(isinstance(v, str) for v in value)
                and len(value) == len(wanted) and set(value) == wanted)
    if (record.get("installer") != bepinex.policy(recipe)["marker"]
            or record.get("keep") != base
            or record.get("file_hashes") != expected
            or not exact_list(record.get("files"), {str(Path(base)/n) for n in expected})
            or not isinstance(packages, dict)
            or set(packages) != {p["id"] for p in recipe["packages"]}):
        return "inconsistent"
    for pkg in recipe["packages"]:
        role = pkg["id"]
        entry = packages[role]
        wanted = {str(Path(base)/r[1]) for r in rows if r[0] == role}
        if (not isinstance(entry, dict) or entry.get("sha256") != pkg["sha256"]
                or not exact_list(entry.get("files"), wanted)):
            return "inconsistent"
    return "consistent-record"


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
        with _archive_snapshot(archive) as (source, sha, identity):
            package, members = bepinex.archive_plan_stream(source, recipe, sha, archive)
            role = package["id"]
            if role in seen_roles:
                raise RuntimeError("Duplicate dependency package.")
            seen_roles.add(role)
            with zipfile.ZipFile(source) as z:
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
                        actual = _safe_hash(base, name, before)
                        if _identity(path) != before:
                            raise RuntimeError("Dependency changed during sampling.")
                        status = ("matching" if actual == expected else
                                  "modified-settings" if protected_setting(name) else
                                  "different")
                    rows.append((role, name, status, expected, actual, before))
    if seen_roles != wanted or not rows:
        raise RuntimeError("Complete pinned package pair required.")
    if _identity(base) != root_identity:
        raise RuntimeError("Game root changed during sampling.")
    backup = _backup_evidence(recipe, record, rows)
    return (str(base), root_identity, record, tuple(sorted(rows)), backup,
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
        base, _, record, rows, backup, conflicts = before
        counts = Counter(row[2] for row in rows)
        return dict(result, status="Review" if conflicts or any(row[2] != "matching" for row in rows) else "Pinned bytes match",
                    sampled_at=datetime.now(timezone.utc).isoformat(), root=base,
                    record_present=record is not None, conflicts=conflicts,
                    ownership_record=_ownership(recipe, base, record, rows),
                    backup_status=backup[0],
                    rows=tuple(dict(component=r[0], path=r[1], status=r[2],
                                    expected_sha256=r[3], actual_sha256=r[4],
                                    protected_setting=protected_setting(r[1])) for r in rows),
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
