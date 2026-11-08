# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Explicit DOOM save discovery and verified, whole-directory recovery.

Scanning and previews are read-only. A restore never selects by newest mtime,
merges individual files, changes graphics settings, or rewrites Hub history.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from . import hub, kharvox, self_install
from .recovery_discovery import recent_recovery_folders, selection_notes

MAX_FILES = 2048
MAX_FILE = 32 * 1024**2
MAX_TOTAL = 128 * 1024**2


def _stamp(value):
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def directory_identity(root):
    """Identify the reviewed directory without following a replacement link."""
    root = Path(root)
    if root.resolve(strict=True) != root or root.is_symlink():
        raise RuntimeError("Save folder location changed. Scan and review it again.")
    info = root.stat()
    return [info.st_dev, info.st_ino]


def check_reviewed_location(expected):
    root = Path(expected["root"])
    identity = directory_identity(root)
    if identity != expected.get("directory_identity"):
        raise RuntimeError("Save folder identity changed since review. Scan and review it again.")


def snapshot(root):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError(f"Not a save folder: {root}")
    identity = directory_identity(root)
    files, total = {}, 0
    for index, path in enumerate(root.rglob("*")):
        if index >= MAX_FILES * 2 or path.is_symlink():
            raise RuntimeError("Save tree is too large or contains linked entries; review it manually.")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"Save entry is not a regular file: {path}")
        size = path.stat().st_size
        total += size
        if size > MAX_FILE or total > MAX_TOTAL or len(files) >= MAX_FILES:
            raise RuntimeError("Save data exceeds the recovery size limits.")
        with path.open("rb") as stream:
            files[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    details = []
    for name in files:
        if not re.fullmatch(r"GAME-AUTOSAVE\d+/game\.details", name):
            continue
        checkpoint = str(Path(name).parent / "checkpoint.dat")
        if checkpoint not in files:
            continue
        raw = (root / name).read_bytes()[:4096]
        values = {k.decode("ascii"): v.decode("utf-8", errors="replace")
                  for k, v in re.findall(rb"(?:^|[\r\n\x00])([A-Za-z]\w*)=([^\r\n\x00]*)", raw)}
        try:
            date = int(values.get("date", "0"))
        except ValueError:
            date = 0
        details.append((date, name, checkpoint, values))
    if not details or "PROFILE/profile.bin" not in files:
        raise RuntimeError("Choose the complete savegame folder containing an autosave checkpoint and PROFILE/profile.bin.")
    date, name, checkpoint, values = max(details, key=lambda item: (item[0], item[1]))
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    if directory_identity(root) != identity:
        raise RuntimeError("Save folder changed during scan. Scan and review it again.")
    return {"root": str(root), "directory_identity": identity, "files": files, "fingerprint": fingerprint, "file_count": len(files),
            "total_bytes": total, "mission": values.get("mapDesc", "Unknown")[:200],
            "map": values.get("mapName", "Unknown")[:300], "saved_at": _stamp(date) if date else None,
            "time_value": values.get("time", "Unknown")[:40], "game_version": values.get("gameVersion", "")[:80],
            "checkpoint_modified": _stamp((root / checkpoint).stat().st_mtime)}


def _roots_in_prefix(prefix):
    users = Path(prefix) / "drive_c/users"
    if not users.is_dir():
        return []
    roots = set()
    for saved in users.glob("*/Saved Games"):
        if not saved.is_dir():
            continue
        for vendor in saved.iterdir():
            if vendor.name.casefold() != "id software" or not vendor.is_dir():
                continue
            for game in vendor.iterdir():
                candidate = game / "base/savegame"
                if game.name.casefold() == "doom" and candidate.is_dir():
                    roots.add(candidate.resolve())
    return sorted(roots)


def current_target(recipe):
    if recipe.get("id") != "doom-2016-gog" or recipe.get("handler") != "kharvox-gog":
        raise RuntimeError("Save recovery is available for Heroic/GOG DOOM (2016) only.")
    roots = _roots_in_prefix(kharvox.prefix(recipe))
    if len(roots) != 1:
        raise RuntimeError("Heroic's DOOM save folder is missing or ambiguous. Review the prefix and Windows user before restoring.")
    return roots[0]


def discover(recipe, extra_roots=(), *, include_backups=True):
    """Bound discovery to the active prefix, known experiment area and backups."""
    candidates, notes = {}, []
    target = None
    try:
        target = current_target(recipe)
        candidates[target] = "Current Heroic save"
    except (RuntimeError, OSError) as exc:
        notes.append(str(exc))
    lab = Path.home() / ".local/share/nanners-kharvox-lab"
    if lab.is_dir():
        for count, (folder, dirs, _files) in enumerate(os.walk(lab, followlinks=False)):
            if count >= 5000:
                notes.append("Experiment scan limit reached; use Choose save folder for other locations.")
                break
            if "drive_c" in dirs:
                try:
                    for root in _roots_in_prefix(Path(folder)):
                        candidates.setdefault(root, "Experiment: " + str(Path(folder).relative_to(lab)))
                except OSError as exc:
                    notes.append(f"Could not inspect {folder}: {exc}")
            dirs[:] = [d for d in dirs if d not in {"drive_c", "dosdevices", "components", "logs", "cache", "downloads", ".git"}
                       and "runner" not in d.casefold()]
    for path in extra_roots:
        candidates.setdefault(Path(path).expanduser().resolve(), "Selected folder")
    if len(candidates) > 256:
        notes.append("Ordinary save location scan limit reached; recovery sets are listed separately. No saves were deleted.")
        explicit = {Path(p).expanduser().resolve() for p in extra_roots}
        ordered = sorted(candidates, key=lambda p: (p != target, p not in explicit))
        candidates = {p: candidates[p] for p in ordered[:256]}
    backups = hub.state_file().parent / "backups"
    folders, omitted, undated = recent_recovery_folders(
        backups, ("doom-save-restore-*", "doom-saves-*")) if include_backups else ([], 0, 0)
    notes.extend(selection_notes(omitted, undated))
    for backup in folders:
        for name in ("experimental-savegame", "heroic-before-savegame", "source-savegame", "target-before-savegame"):
            path = backup / name
            if path.is_dir():
                candidates.setdefault(path.resolve(), f"Backup: {backup.name}/{name}")
    if len(candidates) > 1024:
        notes.append("Save scan limit reached; use Choose save folder for additional locations.")
    rows = []
    for path, label in list(candidates.items())[:1024]:
        try:
            row = snapshot(path)
            row.update(label=label, current=path == target, usable=True)
        except (RuntimeError, OSError) as exc:
            row = {"root": str(path), "label": label, "current": path == target, "usable": False, "error": str(exc)}
        rows.append(row)
    return {"target": str(target) if target else None, "rows": rows, "notes": notes}


def preview(source, target):
    source, target = Path(source).resolve(strict=True), Path(target).resolve(strict=True)
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise RuntimeError("Choose a source separate from the active Heroic save folder.")
    before_source, before_target = snapshot(source), snapshot(target)
    if before_source["fingerprint"] == before_target["fingerprint"]:
        raise RuntimeError("The selected save set already matches the active Heroic saves.")
    if (before_source["game_version"] and before_target["game_version"]
            and before_source["game_version"] != before_target["game_version"]):
        raise RuntimeError("Source and target report different game versions; review compatibility before restoring.")
    return {"source": before_source, "target": before_target}


def ensure_closed():
    for process in Path("/proc").glob("[0-9]*"):
        try:
            name = (process / "comm").read_text().strip().casefold()
        except OSError:
            continue
        if name.startswith(("doomx64", "kharvoxlauncher", "heroic")):
            raise RuntimeError("Close DOOM, KHARVOX and Heroic before restoring saves.")


@contextmanager
def _locked():
    path = hub.state_file().parent / "doom-save-restore.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another save recovery is running. Wait for it to finish.") from exc
        yield


def restore(plan, recipe=None, *, backend=None):
    """Apply only the exact source/target pair reviewed by the caller."""
    snapshot_fn = backend.snapshot if backend else snapshot
    preview_fn = backend.preview if backend else preview
    guard_fn = backend.ensure_closed if backend else ensure_closed
    target_fn = backend.current_target if backend else current_target
    source, target = Path(plan["source"]["root"]), Path(plan["target"]["root"])
    guard_fn()
    for kind in ("source", "target"):
        check_reviewed_location(plan[kind])
    fresh = preview_fn(source, target)
    source, target = Path(fresh["source"]["root"]), Path(fresh["target"]["root"])
    for kind in ("source", "target"):
        if fresh[kind]["fingerprint"] != plan[kind]["fingerprint"]:
            raise RuntimeError("Save files changed since the preview. Scan and review them again.")
    if recipe is not None and target_fn(recipe) != target:
        raise RuntimeError("Heroic's save location changed. Scan and review it again.")
    backup_root = (hub.state_file().parent / "backups").resolve()
    if backup_root.is_relative_to(source) or backup_root.is_relative_to(target):
        raise RuntimeError("The backup directory must be outside both save sets.")
    with _locked():
        for kind in ("source", "target"):
            check_reviewed_location(plan[kind])
        validator = getattr(backend, "validate_transaction", None)
        if validator:
            validator(plan)
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix=(backend.backup_prefix if backend else "doom-saves-"), dir=backup_root))
        record = {"schema": 1, "status": "preparing", "created_at": datetime.now(timezone.utc).isoformat(), **plan}
        record_path = backup / "restore.json"

        def save_record():
            self_install._atomic(record_path, (json.dumps(record, indent=2) + "\n").encode())

        def check(root, expected):
            if snapshot_fn(root)["fingerprint"] != expected["fingerprint"]:
                raise RuntimeError(f"Save verification failed: {root}")

        try:
            save_record()
            shutil.copytree(source, backup / "source-savegame", copy_function=shutil.copy2)
            shutil.copytree(target, backup / "target-before-savegame", copy_function=shutil.copy2)
            check(backup / "source-savegame", plan["source"])
            check(backup / "target-before-savegame", plan["target"])
            staging = Path(tempfile.mkdtemp(prefix=".nanners-save-restore-", dir=target.parent))
            replacement, previous = staging / "replacement-savegame", staging / "previous-savegame"
            shutil.copytree(backup / "source-savegame", replacement, copy_function=shutil.copy2)
            check(replacement, plan["source"])
            guard_fn()
            for kind in ("source", "target"):
                check_reviewed_location(plan[kind])
            check(source, plan["source"])
            check(target, plan["target"])
            if recipe is not None and target_fn(recipe) != target:
                raise RuntimeError("Heroic's save location changed during preparation.")
            if validator:
                validator(plan)
            record.update(status="ready", staging=str(staging))
            save_record()
            for kind in ("source", "target"):
                check_reviewed_location(plan[kind])
            os.replace(target, previous)
            try:
                os.replace(replacement, target)
                check(target, plan["source"])
            except Exception as exc:
                try:
                    if target.exists():
                        os.replace(target, staging / "failed-replacement-savegame")
                    os.replace(previous, target)
                except OSError as recovery_error:
                    raise RuntimeError(f"Restore and rollback failed; originals remain at {backup} and {previous}: {recovery_error}") from exc
                raise RuntimeError("Restore failed; the original target was restored.") from exc
        except Exception as exc:
            raise RuntimeError(f"{exc}\nRecovery copies retained at: {backup}") from exc
        record["status"] = "restored"
        warning = None
        try:
            save_record()
        except OSError:
            warning = "Save files were verified, but the final status record could not be saved. Retain the recovery copies."
        return {"target": str(target), "backup": str(backup), "previous": str(previous),
                "file_count": plan["source"]["file_count"], "warning": warning}
