# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-H: one-shot, strictly read-only installed file integrity checks.

This module does not repair, install, adopt, migrate, or save state. A verified
result means only recorded file bytes matched their historical SHA-256 values
at scan time, NOT that the mod works or its release is compatible.
"""
import errno
from contextlib import contextmanager
import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath

from . import hub
from .installed_provenance import _MARKERS

MAX_FILES = 2500
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_SCAN_BYTES = 2 * 1024 * 1024 * 1024
MAX_ISSUES_PER_COMPONENT = 12
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_FLAGS = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
DIR_FLAGS = SAFE_FLAGS | os.O_DIRECTORY



@contextmanager
def _close_fd(fd):
    """Own a directory descriptor without ever trying to read it as a file."""
    try:
        yield fd
    finally:
        os.close(fd)


class Cancelled(Exception):
    """Explicit user cancellation; never a successful scan."""


def _relative(value):
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    # Windows-style strings or relative escapes are not Unix manifest paths.
    if chr(92) in value or ":" in value or any(ord(ch) < 32 for ch in value):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(x in ("", ".", "..") for x in value.split("/")):
        return None
    return path


def _root(path):
    """Only recorded canonical directories. Never traverse a symlink root."""
    if not isinstance(path, (str, Path)):
        return None
    root = Path(path)
    if (not root.is_absolute() or str(root) == "/" or root.is_symlink()
            or not root.is_dir() or root.resolve(strict=False) != root):
        return None
    return root


def _manifest_from_package(recipe, game):
    """Map package file lists to the existing global post-install SHA map."""
    if not isinstance(game, dict) or game.get("installer") != _MARKERS.get(recipe["id"]):
        return None, "No trusted Hub-managed package installation record."
    packages = game.get("packages")
    hashes = game.get("file_hashes")
    if not isinstance(packages, dict) or not isinstance(hashes, dict) or not hashes:
        return None, "Legacy package record has no post-install file hash manifest."
    keep = game.get("keep")
    if not isinstance(keep, str):
        return None, "No recorded game root."
    base = Path(keep)
    if _root(base) is None:
        return None, "Recorded game root is absent or unsafe."
    roots = [Path(p).expanduser() for p in os.environ.get("VRHUB_STEAM_ROOTS", "").split(":") if p] or None
    actual = hub.game_path(recipe, roots)
    if not isinstance(actual, Path) or actual.resolve(strict=False) != base:
        return None, "Game root no longer matches the Hub installation record."
    found = {}
    global_files = game.get("files")
    if not isinstance(global_files, list) or len(set(global_files)) != len(global_files):
        return None, "Global file inventory is inconsistent."
    globally_assigned = set()
    for pkg in recipe.get("packages", []):
        pid = pkg["id"]
        record = packages.get(pid)
        if not isinstance(record, dict) or record.get("sha256") != pkg.get("sha256"):
            found[pid] = (None, "Package not attributable to the current pinned recipe.")
            continue
        paths = record.get("files")
        if not isinstance(paths, list) or not paths or len(set(paths)) != len(paths):
            found[pid] = (None, "Package installed-file list is missing or inconsistent.")
            continue
        subset = {}
        for path in paths:
            if not isinstance(path, str):
                subset = None
                break
            target = Path(path)
            if not target.is_absolute() or not target.is_relative_to(base):
                subset = None
                break
            rel = _relative(target.relative_to(base).as_posix())
            if rel is None or path not in global_files:
                subset = None
                break
            key = rel.as_posix()
            sha = hashes.get(key)
            if not isinstance(sha, str) or not SHA256.fullmatch(sha) or key in subset:
                subset = None
                break
            subset[key] = (sha, None)
        if subset and globally_assigned.intersection(subset):
            return None, "Overlapping package file inventories require manual review."
        if subset:
            globally_assigned.update(subset)
        found[pid] = (subset, "" if subset else "Missing or invalid per-package file hashes.")
    return (base, found), ""


def _manifest_from_gameroot(recipe, game):
    if not isinstance(game, dict) or game.get("installer") != "gameroot-2":
        return None, "Legacy/manual game-root installation; no trusted post-install manifest."
    base = _root(game.get("keep"))
    if base is None:
        return None, "Recorded game root missing or unsafe."
    actual = hub.game_path(recipe)
    if not isinstance(actual, Path) or actual.resolve(strict=False) != base:
        return None, "Game root no longer matches recorded installation."
    hashes, components = game.get("installed_sha256"), game.get("components")
    if not isinstance(hashes, dict) or not isinstance(components, dict):
        return None, "Missing post-install file hashes or component inventory."
    found = {}
    global_files = game.get("files")
    if not isinstance(global_files, list) or len(set(global_files)) != len(global_files):
        return None, "Global file inventory is inconsistent."
    for comp in recipe.get("components", []):
        cid = str(comp["nexus_mod"])
        rec = components.get(cid)
        if not isinstance(rec, dict):
            found[cid] = (None, "No Hub install record for this component.")
            continue
        paths = rec.get("files")
        if not isinstance(paths, list) or not paths or len(set(paths)) != len(paths):
            found[cid] = (None, "Component file inventory missing or inconsistent.")
            continue
        subset = {}
        for path in paths:
            if not isinstance(path, str) or path not in global_files:
                subset = None
                break
            target = Path(path)
            if not target.is_absolute() or not target.is_relative_to(base):
                subset = None
                break
            rel = _relative(target.relative_to(base).as_posix())
            if rel is None:
                subset = None
                break
            key = rel.as_posix()
            sha = hashes.get(key)
            if not isinstance(sha, str) or not SHA256.fullmatch(sha) or key in subset:
                subset = None
                break
            subset[key] = (sha, None)
        found[cid] = (subset, "" if subset else "Recorded files/hashes are incomplete.")
    return (base, found), ""



def _manifest_from_fatekeeper(recipe, state):
    """Reviewed package bytes, not ownership; use the existing bounded hash reader."""
    from .uevr_dependency_review import FATEKEEPER_LOCAL_PROFILE_FILES, FATEKEEPER_BACKEND_SHA256
    try:
        prefix = _root(hub._pfx(recipe))
        destinations = {"uevr": hub._uevr_dir(recipe), "profile": hub.profile_dir(recipe)}
    except (OSError, RuntimeError, ValueError):
        return None, "Fatekeeper prefix unavailable."
    if prefix is None:
        return None, "Fatekeeper prefix unavailable or unsafe."
    group = {}
    for cid, folder in destinations.items():
        record = state.get("fatekeeper" + (":profile" if cid == "profile" else ""))
        reason = "No complete reviewed dependency evidence for this prefix and pin."
        if (not isinstance(record, dict) or record.get("installer") != "fatekeeper-pair-fk4"
                or record.get("root") != str(folder) or not isinstance(folder, Path)
                or not folder.is_relative_to(prefix) or folder == prefix
                or record.get("archive_sha256") != recipe.get("archive_pins", {}).get(cid)
                or not isinstance(record.get("reviewed_dependencies"), dict)):
            group[cid] = (None, reason)
            continue
        manifest = record["reviewed_dependencies"]
        required = {"UEVRBackend.dll", "UEVRInjector.exe"} if cid == "uevr" else {"config.txt"}
        if not required.issubset(manifest) or len(manifest) > MAX_FILES:
            group[cid] = (None, reason)
            continue
        subset = {}
        for name, meta in manifest.items():
            rel = _relative(name)
            if (rel is None or not isinstance(meta, dict) or not isinstance(meta.get("sha256"), str)
                    or not SHA256.fullmatch(meta["sha256"]) or type(meta.get("size")) is not int
                    or meta["size"] < 0):
                subset = None
                break
            if cid == "uevr" and name == "UEVRBackend.dll" and meta["sha256"] != FATEKEEPER_BACKEND_SHA256:
                subset = None
                break
            # Mutable settings are presence checked separately; do not compare
            # their bytes with factory defaults or certify them as unmodified.
            if cid == "profile" and name in FATEKEEPER_LOCAL_PROFILE_FILES:
                continue
            subset[(folder.relative_to(prefix) / rel).as_posix()] = (meta["sha256"], meta["size"])
        group[cid] = (subset or None, reason)
    return (prefix, group), ""


def _manifest_from_profile(recipe, state):
    rec = state.get(recipe["id"] + ":profile")
    if not isinstance(rec, dict) or rec.get("installer") != "uevr-profile-2":
        return None, "Legacy/manual profile; no complete Hub SHA snapshot."
    base = _root(rec.get("root"))
    if base is None:
        return None, "Profile root missing or unsafe."
    # Distinguish a tracked profile from a random path supplied in state.
    expected = hub.profile_dir(recipe)
    if not isinstance(expected, Path) or expected != base:
        return None, "Profile destination differs from the current game prefix."
    installed = rec.get("installed")
    if not isinstance(installed, dict) or installed.get("exists") is not True:
        return None, "Profile installation snapshot is incomplete."
    files = installed.get("files")
    if not isinstance(files, dict) or not files:
        return None, "Profile hash snapshot missing."
    if (not isinstance(rec.get("files"), list) or
            set(rec["files"]) != {str(base / p) for p in files}):
        return None, "Profile file list differs from the recorded snapshot."
    subset = {}
    for rel, value in files.items():
        key = _relative(rel)
        if key is None or not isinstance(value, dict):
            return None, "Unsafe or invalid profile file path."
        sha, size = value.get("sha256"), value.get("size")
        if not isinstance(sha, str) or not SHA256.fullmatch(sha):
            return None, "Invalid recorded profile file SHA-256."
        if type(size) is not int or size < 0:
            return None, "Invalid recorded profile file size."
        subset[key.as_posix()] = (sha, size)
    return (base, {"profile": (subset, "")}), ""


def _read_hash(base_fd, rel, expected_size, cancel, remaining):
    """Open each component via dirfd with nofollow; refuse races and large files."""
    opened = []
    try:
        fd = base_fd
        for item in rel.parts[:-1]:
            fd = os.open(item, DIR_FLAGS, dir_fd=fd)
            opened.append(fd)
        filefd = os.open(rel.parts[-1], SAFE_FLAGS, dir_fd=fd)
        opened.append(filefd)
        st = os.fstat(filefd)
        if not stat.S_ISREG(st.st_mode):
            return "Unsafe", "File is not regular."
        if st.st_size > MAX_FILE_BYTES or st.st_size > remaining:
            return "Unknown", "File exceeds the remaining safe read limit."
        if expected_size is not None and st.st_size != expected_size:
            return "Modified", "File size differs from recorded installation."
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(os.dup(filefd), "rb", buffering=0) as source:
            while True:
                if cancel and cancel.is_set():
                    raise Cancelled()
                block = source.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_FILE_BYTES or total > remaining:
                    return "Unknown", "File exceeded the safe read limit."
                digest.update(block)
        after = os.fstat(filefd)
        try:
            current = os.stat(rel.parts[-1], dir_fd=fd, follow_symlinks=False)
        except OSError:
            return "Unknown", "File path changed during verification."
        if ((st.st_ino, st.st_dev, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
                != (after.st_ino, after.st_dev, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns)
                or (st.st_ino, st.st_dev) != (current.st_ino, current.st_dev)):
            return "Unknown", "File changed while it was being checked."
        return "Hash", (digest.hexdigest(), total)
    except FileNotFoundError:
        return "Missing", "Previously recorded file not found."
    except (OSError, ValueError) as exc:
        if isinstance(exc, OSError) and exc.errno in (errno.ELOOP, errno.ENOTDIR):
            return "Unsafe", "Symlink or non-directory path refused."
        return "Unknown", "File cannot be safely opened for read-only verification."
    finally:
        for fd in reversed(opened):
            os.close(fd)


def _row(cid, name, status, checked=0, files=0, issues=None, reason=""):
    return {"id": cid, "name": name, "status": status,
            "checked": checked, "files": files, "issues": issues or [],
            "reason": reason}


def verify(recipe, *, state=None, cancel=None):
    """Run on demand; no network, save operation, or game-file modification."""
    if not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str):
        raise ValueError("Invalid game recipe.")
    if state is None:
        state = hub.state()
    if not isinstance(state, dict):
        raise ValueError("Invalid Hub state.")
    rid = recipe["id"]
    if recipe.get("packages"):
        inventory, unavailable = _manifest_from_package(recipe, state.get(rid))
        components = [(p["id"], p["name"]) for p in recipe["packages"]]
    elif recipe.get("components"):
        inventory, unavailable = _manifest_from_gameroot(recipe, state.get(rid))
        components = [(str(c["nexus_mod"]), c["name"]) for c in recipe["components"]]
    elif rid == "fatekeeper" and any(isinstance(state.get(key), dict) and state[key].get("installer") == "fatekeeper-pair-fk4" for key in (rid, rid + ":profile")):
        inventory, unavailable = _manifest_from_fatekeeper(recipe, state)
        components = [("profile", "Matching game profile"), ("uevr", "UEVR injector")]
    elif recipe.get("method") == "uevr" and recipe.get("profile"):
        inventory, unavailable = _manifest_from_profile(recipe, state)
        components = [("profile", "Matching game profile"), ("uevr", "UEVR injector")]
    else:
        return {"game_id":rid, "status":"Unknown", "checked":0,
                "rows":[], "message":"This game has no supported Hub file-hash manifest."}
    if inventory is None:
        rows = [_row(cid, name, "Unknown", reason=unavailable) for cid, name in components]
        return {"game_id":rid, "status":"Unknown", "checked":0,
                "rows":rows, "message":unavailable}
    root, group = inventory
    requests = sum(len(items[0]) for items in group.values() if items[0])
    if requests > MAX_FILES:
        return {"game_id":rid, "status":"Unknown", "checked":0,
                "rows":[_row(cid,name,"Unknown",reason="File count limit exceeded.")
                        for cid,name in components],
                "message":"Tracked file count exceeds safe scan limit."}
    rows = []
    checked, total_bytes = 0, 0
    try:
        rootfd = os.open(root, DIR_FLAGS)
        with _close_fd(rootfd):
            for cid, name in components:
                if cancel and cancel.is_set():
                    raise Cancelled()
                group_rec = group.get(cid)
                if group_rec is None or group_rec[0] is None:
                    why = group_rec[1] if group_rec else "No post-install hashes for this dependency."
                    rows.append(_row(cid,name,"Unknown",reason=why))
                    continue
                manifest = group_rec[0]
                results = []
                row_count = 0
                for rel, (expected, size) in manifest.items():
                    if cancel and cancel.is_set():
                        raise Cancelled()
                    outcome, value = _read_hash(rootfd, PurePosixPath(rel), size, cancel,
                                                MAX_SCAN_BYTES - total_bytes)
                    if outcome == "Hash":
                        # Aggregate size is charged for every recorded entry;
                        # cap high-cardinality manifests without implicit trust.
                        digest, filesize = value
                        total_bytes += filesize
                        outcome = "Verified" if digest == expected else "Modified"
                        value = "" if outcome == "Verified" else "SHA-256 differs from recorded installation."
                    if outcome == "Verified":
                        checked += 1
                    else:
                        results.append({"file":rel, "status":outcome, "detail":value})
                    row_count += 1
                if results:
                    if any(item["status"] in ("Modified","Missing","Unsafe") for item in results):
                        status = "Review"
                    else:
                        status = "Unknown"
                    rows.append(_row(cid,name,status,checked=row_count-len(results),files=row_count,
                                     issues=results[:MAX_ISSUES_PER_COMPONENT],
                                     reason=(f"{len(results)} file(s) need attention.")))
                else:
                    rows.append(_row(cid,name,"Verified",checked=row_count,files=row_count,
                                     reason=("Reviewed immutable dependency hashes matched; customizable settings excluded." if rid == "fatekeeper" and any(isinstance(state.get(k), dict) and state[k].get("installer") == "fatekeeper-pair-fk4" for k in (rid, rid + ":profile")) else "All recorded SHA-256 values matched at scan time.")))
    except (OSError, Cancelled) as exc:
        if isinstance(exc, Cancelled):
            raise
        return {"game_id":rid,"status":"Unknown","checked":0,
                "rows":[_row(cid,name,"Unknown",reason="Cannot safely open recorded root.")
                        for cid,name in components],
                "message":"Cannot safely open recorded root."}
    statuses = [r["status"] for r in rows]
    status = "Review" if "Review" in statuses else "Unknown" if "Unknown" in statuses else "Verified"
    return {"game_id":rid,"status":status,"checked":checked,"rows":rows,
            "message":("Only recorded SHA-256 evidence was checked; no mod was repaired, "
                       "and VR compatibility was not tested.")}
