# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""UEVR profile-2: whole-directory snapshots, stale-plan rejection and safe restores.

Never adopt a legacy profile inventory, overwrite changed files, or treat an
offline fixture run as a real-game install. All mutations require explicit
backend confirmation plus a plan that is revalidated under an exclusive lock.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

MAX_PROFILE_FILES = 2500
MAX_PROFILE_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class ProfilePlan:
    game_id: str
    game_name: str
    archive: str
    archive_sha256: str
    destination: str
    file_names: tuple[str, ...]
    profile_files: int
    profile_bytes: int
    existing_files: int
    existing_bytes: int
    existing_dirs: int
    previous_exists: bool
    blocked: tuple[str, ...]
    fingerprint: str

    @property
    def ready(self) -> bool:
        return bool(self.file_names) and not self.blocked


def _digest(path: Path) -> str:
    """No-follow regular-file digest to avoid opening a swapped-in symlink."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as f:
        before = os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"Expected an ordinary file: {path}")
        sha = hashlib.file_digest(f, "sha256").hexdigest()
        after = os.fstat(f.fileno())
        if (before.st_ino, before.st_dev, before.st_size) != (
                after.st_ino, after.st_dev, after.st_size):
            raise RuntimeError(f"File changed while it was being hashed: {path}")
        return sha


def _snapshot(root: Path) -> dict:
    """Full regular-file + empty-directory manifest. Never follow symlinks."""
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise RuntimeError(f"Profile path is not a safe directory: {root}")
    files: dict[str, dict] = {}
    dirs: list[str] = []
    total = 0
    if not root.exists():
        return {"exists": False, "files": files, "dirs": dirs, "bytes": 0}
    for parent, subdirs, filenames in os.walk(root, followlinks=False):
        base = Path(parent)
        for dirname in subdirs:
            path = base / dirname
            if path.is_symlink() or not path.is_dir():
                raise RuntimeError(f"Profile contains an unsafe directory: {path}")
            dirs.append(path.relative_to(root).as_posix())
        for filename in filenames:
            path = base / filename
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode):
                raise RuntimeError(f"Profile contains a nonregular file: {path}")
            rel = path.relative_to(root).as_posix()
            size = path.stat().st_size
            if size > MAX_PROFILE_BYTES:
                raise RuntimeError(f"Individual profile file exceeds limit: {rel}")
            total += size
            if total > MAX_PROFILE_BYTES:
                raise RuntimeError("Profile directory exceeds the 2 GiB safety limit.")
            files[rel] = {"size": size, "sha256": _digest(path)}
            if len(files) > MAX_PROFILE_FILES:
                raise RuntimeError("Profile directory exceeds 2500 files.")
    if len({name.casefold() for name in (*files, *dirs)}) != len(files) + len(dirs):
        raise RuntimeError("Profile contains ambiguous case-insensitive paths.")
    return {"exists": True, "files": files, "dirs": sorted(dirs), "bytes": total}


def _safe_destination(dest: Path, prefix: Path) -> None:
    if not dest.is_absolute() or not prefix.is_absolute():
        raise RuntimeError("Profile path must be absolute.")
    if not dest.is_relative_to(prefix):
        raise RuntimeError("Profile destination leaves its game's Proton prefix.")
    # No symlink parent, profile root, or path component between prefix and root.
    p = dest
    while True:
        if p.is_symlink():
            raise RuntimeError(f"Symbolic link in profile destination: {p}")
        if p == prefix:
            break
        if p == p.parent or not p.is_relative_to(prefix):
            raise RuntimeError("Profile destination path escapes the prefix.")
        p = p.parent
    if dest.exists() and not dest.is_dir():
        raise RuntimeError("Existing profile destination is not a directory.")
    if dest.parent.exists() and not dest.parent.is_dir():
        raise RuntimeError("Profile parent is not a directory.")


def _archive_entries(z: zipfile.ZipFile) -> tuple[tuple[zipfile.ZipInfo, str], ...]:
    # All ZIP metadata is validated by the caller before this function.
    infos = [i for i in z.infolist() if not i.is_dir() and not i.filename.replace("\\", "/").endswith("/")]
    normalized = [(i, i.filename.replace("\\", "/")) for i in infos]
    anchors = [name for _, name in normalized if name.rsplit("/", 1)[-1].casefold() == "config.txt"]
    if not anchors:
        raise RuntimeError("The archive has no UEVR config.txt.")
    shortest = min(len(name) for name in anchors)
    if sum(len(name) == shortest for name in anchors) != 1:
        raise RuntimeError("Ambiguous UEVR profile config.txt layout.")
    anchor = next(name for name in anchors if len(name) == shortest)
    wrapper = anchor[:-len("config.txt")]
    selected = [(info, name[len(wrapper):]) for info, name in normalized if name.startswith(wrapper)]
    if len({rel.casefold() for _, rel in selected}) != len(selected):
        raise RuntimeError("Profile archive contains colliding file names.")
    rels = [rel for _, rel in selected]
    paths = {p.casefold() for p in rels}
    for rel in rels:
        parts = rel.casefold().split("/")
        if any("/".join(parts[:n]) in paths for n in range(1, len(parts))):
            raise RuntimeError("Profile archive contains file/directory collision.")
    if not selected or len(selected) > MAX_PROFILE_FILES:
        raise RuntimeError("UEVR profile archive has too many files.")
    return tuple(selected)


def _read_archive(path: Path, prefix: Path) -> tuple[str, tuple[str, ...], int]:
    from .install_review import _zip_preflight
    if path.is_symlink() or not path.is_file() or path.suffix.casefold() != ".zip":
        raise RuntimeError("A regular ZIP archive is required.")
    if path.resolve().is_relative_to(prefix.resolve()):
        raise RuntimeError("Choose an archive outside the game's prefix.")
    try:
        _zip_preflight(path)
        with zipfile.ZipFile(path) as z:
            entries = _archive_entries(z)
            return _digest(path), tuple(sorted(name for _, name in entries)), sum(i.file_size for i, _ in entries)
    except (zipfile.BadZipFile, EOFError) as exc:
        raise RuntimeError(f"Invalid UEVR ZIP archive: {exc}") from exc


def _payload(archive, archive_sha, dest, snap, files, state_marker) -> str:
    raw = {
        "archive": str(archive), "zip_sha": archive_sha, "dest": str(dest),
        "current": snap, "files": files, "existing_record": state_marker,
    }
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def build_plan(recipe: dict, zip_file: Path, steam_roots=None) -> ProfilePlan:
    from . import hub
    if not recipe.get("profile") or recipe.get("method") != "uevr":
        raise RuntimeError("This game has no supported UEVR profile step.")
    dest = hub.profile_dir(recipe, steam_roots)
    prefix = hub._pfx(recipe, steam_roots)
    _safe_destination(dest, prefix)
    zip_file = Path(zip_file)
    sha, names, archive_bytes = _read_archive(zip_file, prefix)
    snap = _snapshot(dest)
    key = f"{recipe['id']}:profile"
    record = hub._load_state().get(key)
    blocked = []
    if record is not None:
        blocked.append(
            "An existing Hub profile record (including legacy installs) requires a "
            "separate recovery review. No replacement or adoption is allowed.")
    fingerprint = _payload(zip_file.resolve(), sha, dest, snap, names, record)
    return ProfilePlan(
        game_id=recipe["id"], game_name=recipe["name"], archive=str(zip_file.resolve()),
        archive_sha256=sha, destination=str(dest), file_names=names,
        profile_files=len(names), profile_bytes=archive_bytes,
        existing_files=len(snap["files"]), existing_bytes=snap["bytes"],
        existing_dirs=len(snap["dirs"]), previous_exists=snap["exists"],
        blocked=tuple(blocked), fingerprint=fingerprint)


@contextmanager
def _lock():
    from . import hub
    from . import state_transaction
    with state_transaction.locked(hub.state_file()):
        directory = hub.state_file().parent
        if directory.is_symlink():
            raise RuntimeError("Hub state directory is a symbolic link.")
        directory.mkdir(parents=True, exist_ok=True)
        lockpath = directory / ".uevr-profile-install.lock"
        if lockpath.is_symlink():
            raise RuntimeError("UEVR profile lock is a symbolic link.")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lockpath, flags, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _verified_copy(src: Path, dst: Path, expected: dict) -> None:
    if src.is_symlink() or not src.is_dir():
        raise RuntimeError("Source profile directory is unsafe.")
    if dst.exists() or dst.is_symlink():
        raise RuntimeError("Profile backup or staging destination already exists.")
    # Copy symlink entries as links, never dereference; the post-copy inventory
    # will reject them. Also verify the source again after copying.
    if _snapshot(src) != expected:
        raise RuntimeError("Source profile changed before verified copy.")
    shutil.copytree(src, dst, symlinks=True)
    result = _snapshot(dst)
    if result != expected or _snapshot(src) != expected:
        raise RuntimeError("Copied directory failed SHA-256 integrity validation.")


def _backup_path(game_id: str) -> Path:
    from . import hub
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", game_id):
        raise RuntimeError("Unsafe UEVR recipe identifier.")
    base = hub.state_file().parent / "backups"
    if base.is_symlink():
        raise RuntimeError("Hub backup directory is a symbolic link.")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{game_id}-uevr-profile-{uuid.uuid4().hex}"


def _stage_zip(src: Path, dest: Path, expected_names: tuple[str, ...]) -> dict:
    from .install_review import _zip_preflight
    _zip_preflight(src)
    dest.mkdir(parents=False, exist_ok=False)
    with zipfile.ZipFile(src) as z:
        entries = _archive_entries(z)
        for info, rel in entries:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                raise RuntimeError(f"Duplicate profile destination: {rel}")
            with z.open(info) as stream, target.open("xb") as out:
                shutil.copyfileobj(stream, out)
    snap = _snapshot(dest)
    if tuple(sorted(snap["files"])) != expected_names:
        raise RuntimeError("Staged profile file list differed from reviewed ZIP.")
    return snap


def _check_fresh(recipe, zip_file, steam_roots, fingerprint) -> ProfilePlan:
    plan = build_plan(recipe, zip_file, steam_roots)
    if plan.fingerprint != fingerprint:
        raise RuntimeError("UEVR profile changed after review; preview again before installation.")
    if not plan.ready:
        raise RuntimeError("UEVR profile installation blocked: " + "; ".join(plan.blocked))
    return plan


def _assert_execution_gate() -> None:
    """Dev5C3 is an offline-tested milestone. Live writes remain disabled."""
    raise RuntimeError(
        "Dev5C3 LIVE PROFILE EXECUTION IS DISABLED. "
        "Only isolated offline fixtures have been validated. "
        "A separate on-desktop safety acceptance is required before live profile changes.")


def _assert_game_stopped(game_id: str, *, proc: Path | None = None) -> None:
    """Conservative read-only process check; refuse unverified game identities."""
    markers = {
        "fatekeeper": {"slasher-win64-shipping.exe", "slasher-win64-shipping"},
        "hogwarts-legacy": {"hogwartslegacy.exe", "hogwartslegacy"},
    }.get(game_id)
    if not markers:
        raise RuntimeError("No supported game-running check for this UEVR profile.")
    proc = proc if proc is not None else Path("/proc")
    if not proc.is_dir():
        raise RuntimeError("Cannot verify whether the UEVR game is running.")
    try:
        pids = [p for p in proc.iterdir() if p.name.isdecimal()]
    except OSError as exc:
        raise RuntimeError("Cannot inspect active processes safely.") from exc
    for pid in pids:
        try:
            raw = (pid / "cmdline").read_bytes().split(b"\0")
            comm = (pid / "comm").read_text().strip().casefold()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, OSError) as exc:
            raise RuntimeError("Cannot verify that the target game is stopped.") from exc
        # Wine command lines may contain Windows separators, and Linux comm
        # truncates executable names to 15 bytes. Refuse either representation.
        args = {os.fsdecode(item).replace("\\", "/").rsplit("/", 1)[-1].casefold()
                for item in raw if item}
        if comm in markers or comm in {name[:15] for name in markers} or markers.intersection(args):
            raise RuntimeError("Target UEVR game is running; close it before changing the profile.")
        if game_id == "fatekeeper":
            injectors = {"uevrinjector.exe", "uevrinjector"}
            if comm in injectors or comm in {name[:15] for name in injectors} or injectors.intersection(args):
                raise RuntimeError("UEVR injector is running; close it before changing Fatekeeper dependencies.")


def install(recipe: dict, zip_file: Path, steam_roots=None, *,
            approved_fingerprint: str | None = None, confirmed: bool = False) -> list[Path]:
    """Only a fully reviewed and explicitly confirmed plan may mutate a profile.

    All game/profile operations are serialized and re-reviewed under lock.
    Backups persist even after successful restore. Live-game process checks are
    required in addition to this service before a production rollout.
    """
    from . import hub
    if not confirmed or not approved_fingerprint:
        raise RuntimeError("UEVR profile replacement requires explicit reviewed confirmation.")
    # The Dev5C3 preview must never create even a live-state lock file.
    _assert_execution_gate()
    with _lock():
        plan = _check_fresh(recipe, zip_file, steam_roots, approved_fingerprint)
        _assert_game_stopped(plan.game_id)
        dest = Path(plan.destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        old = _snapshot(dest)
        backup = _backup_path(plan.game_id) if old["exists"] else None
        stage = dest.parent / f".{dest.name}.nanners-stage-{uuid.uuid4().hex}"
        displaced = dest.parent / f".{dest.name}.nanners-previous-{uuid.uuid4().hex}"
        saved_stage = False
        recovery_problem = False
        try:
            if backup:
                _verified_copy(dest, backup, old)
            new = _stage_zip(Path(plan.archive), stage, plan.file_names)
            if _digest(Path(plan.archive)) != plan.archive_sha256:
                raise RuntimeError("ZIP changed during staging; no profile modified.")
            _safe_destination(dest, hub._pfx(recipe, steam_roots))
            if _snapshot(dest) != old:
                raise RuntimeError(
                    "Existing UEVR profile changed during staging; no profile replaced.")
            if old["exists"]:
                dest.rename(displaced)
            try:
                stage.rename(dest)
                saved_stage = True
                state = hub._load_state()
                key = plan.game_id + ":profile"
                if key in state:
                    raise RuntimeError("Hub profile record changed during transaction.")
                state[key] = {
                    "installer": "uevr-profile-2",
                    "root": str(dest),
                    "backup": str(backup) if backup else None,
                    "original": old,
                    "installed": new,
                    "archive_sha256": plan.archive_sha256,
                    "installed_at": int(__import__("time").time()),
                    "files": [str(dest / p) for p in new["files"]],
                }
                hub._save_state(state)
            except Exception as exc:
                try:
                    if saved_stage and dest.exists():
                        dest.rename(stage)
                    if old["exists"] and displaced.exists():
                        displaced.rename(dest)
                except OSError as restore_exc:
                    recovery_problem = True
                    raise RuntimeError(
                        "UEVR installation failed and automatic rollback failed. "
                        f"DO NOT DELETE recovery directories: {stage}, {displaced}; "
                        f"reason: {restore_exc}") from exc
                raise
        finally:
            # If a commit/rollback fails, keep every available recovery copy.
            if not recovery_problem:
                if stage.exists():
                    shutil.rmtree(stage)
                if displaced.exists():
                    shutil.rmtree(displaced)
            # Retain verified original backup even on failed installation.
        return [dest / name for name in new["files"]]


def review_restore(recipe_id: str) -> dict:
    """Read-only current-vs-installed and backup checks before confirmation."""
    from . import hub
    state = hub._load_state()
    entry = state.get(recipe_id)
    if not isinstance(entry, dict) or entry.get("installer") != "uevr-profile-2":
        return {"ready": False, "reason": "Legacy or missing profile record needs manual recovery review."}
    try:
        game_id = recipe_id.removesuffix(":profile")
        recipe = hub.load_recipes().get(game_id)
        if not recipe or not recipe.get("profile"):
            raise RuntimeError("Profile recipe unavailable.")
        dest = Path(entry["root"])
        if dest != hub.profile_dir(recipe):
            raise RuntimeError("Recorded destination differs from the current recipe.")
        _safe_destination(dest, hub._pfx(recipe))
        installed = entry["installed"]
        if _snapshot(dest) != installed:
            raise RuntimeError("Installed profile has additions, removals, or modifications.")
        original = entry["original"]
        backup = Path(entry["backup"]) if entry.get("backup") else None
        if original["exists"]:
            base = hub.state_file().parent / "backups"
            if (base.is_symlink() or backup is None or backup.parent != base
                    or backup.is_symlink() or not backup.is_dir()
                    or _snapshot(backup) != original):
                raise RuntimeError("Retained original backup is missing, unsafe, or changed.")
        elif backup:
            raise RuntimeError("Unexpected original backup for a previously absent directory.")
        return {"ready": True, "destination": str(dest),
                "installed_files": len(installed["files"]),
                "original_files": len(original["files"]),
                "original_bytes": original["bytes"], "reason": ""}
    except (RuntimeError, OSError, KeyError, TypeError, ValueError) as exc:
        return {"ready": False, "reason": str(exc)}


def restore(recipe_id: str, *, confirmed: bool = False) -> list[Path]:
    """Restore only unchanged, newly managed profile records, fail closed."""
    from . import hub
    if not confirmed:
        raise RuntimeError("Profile restoration requires explicit confirmation.")
    _assert_execution_gate()
    with _lock():
        state = hub._load_state()
        entry = state.get(recipe_id)
        if not isinstance(entry, dict) or entry.get("installer") != "uevr-profile-2":
            raise RuntimeError("Legacy/missing UEVR profile record: manual recovery review required.")
        game_id = recipe_id.removesuffix(":profile")
        recipe = hub.load_recipes().get(game_id)
        if recipe is None or not recipe.get("profile"):
            raise RuntimeError("Cannot verify this profile's owning game.")
        expected = hub.profile_dir(recipe)
        dest = Path(entry["root"])
        if dest != expected:
            raise RuntimeError("Recorded profile destination differs from the game's current prefix.")
        _safe_destination(dest, hub._pfx(recipe))
        _assert_game_stopped(game_id)
        if dest.is_symlink() or not dest.is_dir():
            raise RuntimeError("Managed profile destination is missing or unsafe; nothing changed.")
        installed = entry["installed"]
        if _snapshot(dest) != installed:
            raise RuntimeError(
                "Installed profile has additions, removals, or modifications. "
                "Automatic restore blocked; preserve customizations and review manually.")
        original = entry["original"]
        backup = Path(entry["backup"]) if entry.get("backup") else None
        if original["exists"]:
            base = hub.state_file().parent / "backups"
            if (base.is_symlink() or backup is None or
                    backup.parent != base or backup.is_symlink()
                    or not backup.is_dir() or _snapshot(backup) != original):
                raise RuntimeError("Original UEVR backup missing, unsafe, or changed; nothing modified.")
        elif backup:
            raise RuntimeError("Unexpected backup for new UEVR profile; manual review required.")
        stage = dest.parent / f".{dest.name}.nanners-restore-{uuid.uuid4().hex}"
        displaced = dest.parent / f".{dest.name}.nanners-current-{uuid.uuid4().hex}"
        committed = False
        recovery_problem = False
        try:
            if backup:
                _verified_copy(backup, stage, original)
            _safe_destination(dest, hub._pfx(recipe))
            if _snapshot(dest) != installed:
                raise RuntimeError("Installed UEVR profile changed during restore staging.")
            dest.rename(displaced)
            try:
                if backup:
                    stage.rename(dest)
                new_state = dict(state)
                new_state.pop(recipe_id)
                hub._save_state(new_state)
                committed = True
            except Exception as exc:
                try:
                    if backup and dest.exists():
                        dest.rename(stage)
                    if displaced.exists():
                        displaced.rename(dest)
                except OSError as restore_exc:
                    recovery_problem = True
                    raise RuntimeError(
                        "UEVR restore failed and recovery copy must be retained: "
                        f"{stage}, {displaced}; {restore_exc}") from exc
                raise
        finally:
            if not recovery_problem:
                if stage.exists():
                    shutil.rmtree(stage)
                if committed and displaced.exists():
                    shutil.rmtree(displaced)
        return [dest / name for name in installed["files"]]
