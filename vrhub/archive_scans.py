# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5B1: saved per-game archive *snapshots*, never install authorization.

Read-only file inspection; only NAnnersVRhub's own small JSON snapshot file is
updated on a successful, user-requested scan. No game/mod/archive modification.
Saved checks are clearly labeled as historical. Changed files become blocked
until a new scan re-verifies the original pinned recipe hash.
"""
from __future__ import annotations

import copy
import fcntl
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from . import download_planner as planner, hub, self_install

MAX_SNAPSHOT_BYTES = 512 * 1024
MAX_GAMES = 48
MAX_ROWS = 96
MAX_PATH = 4096
STATUSES = {
    "Pinned SHA-256 verified", "Possible archive — inspect first",
    "Hash mismatch — do not install", "Hash not verified — do not install",
    "Not found locally", "Archive changed — rescan required",
}


def snapshot_file() -> Path:
    return hub.state_file().parent / "archive-scan-snapshots.json"


def _empty():
    return {"schema": 1, "games": {}}


def _validate_record(rid, record):
    planner._rid(rid)
    if not isinstance(record, dict) or set(record) != {
        "folder", "scanned_at", "plan", "files",
    }:
        raise ValueError("Invalid scan record")
    folder = planner._checked_directory(record["folder"])
    # A persisted scan is not a source of authority about installed mods.
    if not isinstance(record["scanned_at"], str) or len(record["scanned_at"]) > 40:
        raise ValueError("Invalid scan date")
    try:
        datetime.fromisoformat(record["scanned_at"])
    except ValueError as exc:
        raise ValueError("Invalid scan date") from exc
    plan = record["plan"]
    if (not isinstance(plan, dict) or plan.get("game_id") != rid or
            plan.get("folder") != str(folder) or not isinstance(plan.get("rows"), list)
            or len(plan["rows"]) > MAX_ROWS or
            type(plan.get("scanned")) is not int or plan["scanned"] < 0):
        raise ValueError("Invalid scan plan")
    for row in plan["rows"]:
        if not isinstance(row, dict) or row.get("status") not in STATUSES:
            raise ValueError("Unexpected result status")
        filename = row.get("file", "")
        if (not isinstance(filename, str) or len(filename) > MAX_PATH
                or (filename and (not Path(filename).is_absolute()
                                  or not Path(filename).is_relative_to(folder)))):
            raise ValueError("Invalid scanned archive path")
    if not isinstance(record["files"], dict) or len(record["files"]) > MAX_ROWS:
        raise ValueError("Invalid file identity map")
    for name, info in record["files"].items():
        if (not isinstance(name, str) or len(name) > MAX_PATH or
                not Path(name).is_absolute() or not Path(name).is_relative_to(folder) or
                not isinstance(info, dict) or set(info) != {"size", "mtime_ns", "ino", "dev"} or
                any(type(v) is not int or v < 0 for v in info.values())):
            raise ValueError("Invalid archive identity metadata")
    return record


def load_saved() -> dict:
    path = snapshot_file()
    if not path.exists() and not path.is_symlink():
        return {}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("Saved scan file needs manual review; it has not been overwritten.")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(obj, dict) or set(obj) != {"schema", "games"}
                or obj["schema"] != 1 or not isinstance(obj["games"], dict)
                or len(obj["games"]) > MAX_GAMES):
            raise ValueError("Invalid saved scan file")
        return {rid: _validate_record(rid, rec)
                for rid, rec in obj["games"].items()}
    except (OSError, UnicodeError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Saved scan file needs manual review; it has not been overwritten.") from exc


def _identity(path: Path):
    """Do not follow symlink files, including ones swapped since a scan."""
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode):
            return None
        return {"size": st.st_size, "mtime_ns": st.st_mtime_ns,
                "ino": st.st_ino, "dev": st.st_dev}
    except OSError:
        return None


def _record(plan):
    rid = planner._rid(plan["game_id"])
    folder = str(planner._checked_directory(plan["folder"]))
    files = {}
    for row in plan["rows"]:
        filename = row.get("file")
        if filename:
            path = Path(filename)
            if not path.is_relative_to(Path(folder)):
                raise ValueError("Refusing archive path outside selected folder")
            identity = _identity(path)
            if identity is not None:
                files[str(path)] = identity
    record = {
        "folder": folder,
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plan": copy.deepcopy(plan),
        "files": files,
    }
    _validate_record(rid, record)
    return rid, record


def persist(plan) -> dict:
    """Upsert only this game's scan using locking and atomic, private writes."""
    rid, rec = _record(plan)
    path = snapshot_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path) + ".lock",
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = load_saved()  # reject corrupt existing data, do not clobber
        records[rid] = rec
        encoded = (json.dumps({"schema": 1, "games": records},
                              separators=(",", ":")) + "\n").encode()
        if len(records) > MAX_GAMES or len(encoded) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Scan snapshot limit reached; existing data preserved.")
        self_install._atomic(path, encoded)
    return rec


def remove_changed_folders():
    """Purge only entries whose selected folder no longer matches the recipe.

    Per-game overrides survive a global-folder change. This never touches any
    archive, game or another unrelated saved scan.
    """
    path = snapshot_file()
    if not path.exists() and not path.is_symlink():
        return []
    fd = os.open(str(path) + ".lock",
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = load_saved()
        invalid = []
        for rid, rec in records.items():
            try:
                active, _ = planner.folder_for({"id": rid})
            except (RuntimeError, ValueError, OSError):
                continue  # do not discard valid records because settings cannot load
            if str(active) != rec["folder"]:
                invalid.append(rid)
        if invalid:
            for rid in invalid:
                del records[rid]
            self_install._atomic(
                path, (json.dumps({"schema": 1, "games": records},
                                  separators=(",", ":")) + "\n").encode())
        return invalid


def displayed_record(record) -> dict:
    """Use a saved result only as a historical snapshot.

    If any selected archive changed identity, block that component's prior
    status (including previous SHA verification) until a manual rescan.
    """
    rec = copy.deepcopy(record)
    folder = Path(rec["folder"])
    for row in rec["plan"]["rows"]:
        filename = row.get("file")
        if not filename:
            continue
        prior = rec["files"].get(filename)
        path = Path(filename)
        if (not path.is_relative_to(folder) or prior is None
                or prior != _identity(path)):
            row["status"] = "Archive changed — rescan required"
            row["file"] = ""  # cannot inspect a path whose identity changed
            row["matches"] = 0
    counts = {
        "verified": "Pinned SHA-256 verified",
        "possible": "Possible archive — inspect first",
        "mismatch": "Hash mismatch — do not install",
        "unverified": "Hash not verified — do not install",
        "missing": "Not found locally",
        "changed": "Archive changed — rescan required",
    }
    for key, status in counts.items():
        rec["plan"][key] = sum(r["status"] == status
                               for r in rec["plan"]["rows"])
    return rec
