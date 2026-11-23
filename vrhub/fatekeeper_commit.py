# SPDX-License-Identifier: GPL-3.0-only
"""Journaled Fatekeeper commit and recovery, gated to disposable prefixes."""
import fcntl
import json
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from . import hub, profile_safety
from .self_install import _atomic


def _sync(directory):
    fd = os.open(directory, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, data, mode=0o600):
    missing = [parent for parent in path.parents if not parent.exists()]
    _atomic(path, data, mode)
    _sync(path.parent)
    for parent in missing:
        _sync(parent.parent)


def _read(path):
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024 * 1024:
                raise RuntimeError("Unsafe Fatekeeper transaction file.")
            return stream.read(64 * 1024 * 1024 + 1), stat.S_IMODE(info.st_mode)
    except FileNotFoundError:
        return None, None


def _digest(data):
    return None if data is None else sha256(data).hexdigest()


def _roots(root):
    if (root.parent != Path("/tmp").resolve() or root.resolve() != root or
            not root.name.startswith("nanners-fk4-") or not root.is_dir() or
            root.stat().st_uid != os.getuid() or stat.S_IMODE(root.stat().st_mode) != 0o700):
        raise RuntimeError("Live Fatekeeper execution is disabled. Use a private FK4 fixture.")
    prefix = root / "pfx"
    recipe = hub.load_recipes()["fatekeeper"]
    profile = prefix / "drive_c/users/steamuser/AppData" / recipe["profile"]["dir"]
    return prefix, prefix / "drive_c/uevr", profile, root / "state.json"


@dataclass(frozen=True)
class Destination:
    root: Path
    prefix: Path
    injector: Path
    profile: Path
    state: Path
    journal_dir: Path


def _fixture_destination(root):
    return Destination(root, *_roots(root), root)


def live_install_authorized():
    """Release gate. FK5 has no live execution authorization."""
    return False


def _live_destination(steam_roots):
    if not live_install_authorized():
        raise RuntimeError("Explicit live Fatekeeper authorization is required.")
    recipe = hub.load_recipes()["fatekeeper"]
    prefix = hub._pfx(recipe, steam_roots)
    injector = hub._uevr_dir(recipe, steam_roots)
    profile = hub.profile_dir(recipe, steam_roots)
    state = hub.state_file()
    root = Path(os.path.commonpath((prefix, state.parent)))
    journal_dir = state.parent / "fatekeeper-recovery"
    for path in (prefix, injector, profile, state.parent, journal_dir):
        profile_safety._safe_destination(path, root)
    if (injector.is_relative_to(profile) or profile.is_relative_to(injector)
            or state.is_relative_to(prefix) or journal_dir.is_relative_to(prefix)):
        raise RuntimeError("Fatekeeper transaction destinations overlap.")
    profile_safety._assert_game_stopped("fatekeeper")
    return Destination(root, prefix, injector, profile, state, journal_dir)


def _target(destination, name):
    root = destination.root
    injector, profile, state = destination.injector, destination.profile, destination.state
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts or not (
        path == state or any(path != folder and path.is_relative_to(folder)
                             for folder in (injector, profile))
    ):
        raise RuntimeError("Fatekeeper journal destination is outside the reviewed roots.")
    profile_safety._safe_destination(path.parent, root)
    return path


@contextmanager
def _locked(destination):
    root = destination.journal_dir
    profile_safety._safe_destination(root, destination.root)
    root.mkdir(mode=0o700, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(root / "fk4.lock", flags, 0o600), "rb") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise RuntimeError("Unsafe Fatekeeper lock.")
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _journal(path, phase, rows, directories):
    _write(path, json.dumps({"phase": phase, "rows": rows, "directories": directories}).encode())


def commit(root, prepared, *, interrupt_after_files=False):
    """Commit the reviewed write set and Hub records under a verified backup journal."""
    _commit(_fixture_destination(root), prepared, interrupt_after_files=interrupt_after_files)


def _commit(destination, prepared, *, interrupt_after_files=False):
    root = destination.root
    prefix, injector, profile, state_path = (
        destination.prefix, destination.injector, destination.profile, destination.state)
    state_name = state_path.relative_to(root).as_posix()
    with _locked(destination):
        if prepared.prefix != prefix:
            raise RuntimeError("Fatekeeper plan targets another prefix.")
        journal = destination.journal_dir / "fk4-journal.json"
        previous_journal, _ = _read(journal)
        backup_dir = destination.journal_dir / "fk4-backup"
        if previous_journal is not None and json.loads(previous_journal)["phase"] != "rolled-back":
            raise RuntimeError("Recover the existing Fatekeeper transaction before retrying.")
        if previous_journal is not None or backup_dir.exists() or backup_dir.is_symlink():
            profile_safety._safe_destination(backup_dir, destination.journal_dir)
            history = destination.journal_dir / ("history-" + uuid4().hex)
            history.mkdir(mode=0o700)
            if previous_journal is not None:
                journal.rename(history / journal.name)
            if backup_dir.exists():
                backup_dir.rename(history / backup_dir.name)
            _sync(history)
            _sync(destination.journal_dir)
        _target(destination, state_name)
        state_before = _read(state_path)[0]
        if (profile_safety._snapshot(injector) != prepared.injector or
                profile_safety._snapshot(profile) != prepared.profile or
                (json.loads(state_before) if state_before is not None else {}) != prepared.state):
            raise RuntimeError("Fatekeeper target changed after preflight.")
        writes = {Path(name).relative_to(root).as_posix(): data for name, data in prepared.writes.items()}
        records = dict(prepared.state)
        for key, folder in (("fatekeeper", injector), ("fatekeeper:profile", profile)):
            previous = records.get(key, {})
            # Fixture records explicitly reference this transaction, and retain
            # earlier recovery metadata as part of the backed-up state file.
            records[key] = {
                "installer": "fatekeeper-pair-fk4",
                "root": str(folder),
                "files": sorted(name for name in prepared.writes if Path(name).is_relative_to(folder)),
                "journal": str(journal),
                "previous": previous,
            }
        writes[state_name] = (json.dumps(records, indent=2) + "\n").encode()
        backup_dir.mkdir(mode=0o700, exist_ok=False)
        _sync(destination.journal_dir)
        rows = []
        directories = set()
        for index, (name, data) in enumerate(writes.items()):
            path = _target(destination, name)
            before, mode = _read(path)
            snapshot = prepared.injector if path.is_relative_to(injector) else prepared.profile
            folder = injector if path.is_relative_to(injector) else profile
            expected = (_digest(state_before) if path == state_path else
                        snapshot["files"].get(path.relative_to(folder).as_posix(), {}).get("sha256"))
            if _digest(before) != expected:
                raise RuntimeError("Fatekeeper destination changed during backup.")
            if before is not None:
                copy = backup_dir / str(index)
                _write(copy, before)
                if _digest(_read(copy)[0]) != expected:
                    raise RuntimeError("Fatekeeper backup verification failed.")
            rows.append({"path": name, "old": expected, "new": _digest(data), "mode": mode})
            directories.update(parent.relative_to(root).as_posix() for parent in path.parents
                               if parent != root and parent.is_relative_to(root) and not parent.exists())
        _journal(journal, "applying", rows, sorted(directories))
        try:
            for row in rows:
                path = _target(destination, row["path"])
                if _digest(_read(path)[0]) != row["old"]:
                    raise RuntimeError("Fatekeeper destination changed during commit.")
                if interrupt_after_files and path == state_path:
                    return
                _write(path, writes[row["path"]], row["mode"] if row["mode"] is not None else 0o600)
            if any(_digest(_read(_target(destination, row["path"]))[0]) != row["new"] for row in rows):
                raise RuntimeError("Fatekeeper commit verification failed.")
            _journal(journal, "committed", rows, sorted(directories))
        except (OSError, RuntimeError, ValueError):
            _recover(destination)
            raise


def _recover(destination):
    root = destination.root
    journal = destination.journal_dir / "fk4-journal.json"
    raw, _ = _read(journal)
    if raw is None:
        raise RuntimeError("No Fatekeeper recovery journal exists.")
    record = json.loads(raw)
    if record["phase"] == "rolled-back":
        return
    if record["phase"] not in {"applying", "committed", "recovering"}:
        raise RuntimeError("Unknown Fatekeeper transaction phase.")
    rows = record["rows"]
    originals = []
    backup = destination.journal_dir / "fk4-backup"
    profile_safety._safe_destination(backup, root)
    for index, row in enumerate(rows):
        path = _target(destination, row["path"])
        current, _ = _read(path)
        original = None if row["old"] is None else _read(backup / str(index))[0]
        if _digest(original) != row["old"] or _digest(current) not in (row["old"], row["new"]):
            raise RuntimeError("Fatekeeper rollback blocked by changed files or backups.")
        originals.append((path, current, original, row["mode"]))
    directories = record["directories"]
    allowed_dirs = {parent.relative_to(root).as_posix() for path, *_ in originals
                    for parent in path.parents if parent != root and parent.is_relative_to(root)}
    if not set(directories).issubset(allowed_dirs):
        raise RuntimeError("Unexpected Fatekeeper recovery directory.")
    _journal(journal, "recovering", rows, directories)
    for path, current, original, mode in reversed(originals):
        if current == original:
            continue
        _target(destination, path.relative_to(root).as_posix())
        if _read(path)[0] != current:
            raise RuntimeError("Fatekeeper destination changed during recovery.")
        if original is None:
            path.unlink()
            _sync(path.parent)
        else:
            _write(path, original, mode)
    for name in sorted(directories, key=lambda value: len(Path(value).parts), reverse=True):
        directory = root / name
        profile_safety._safe_destination(directory, root)
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
            _sync(directory.parent)
    _journal(journal, "rolled-back", rows, directories)


def recover(root):
    """Restore both files and state after a failed or interrupted commit."""
    destination = _fixture_destination(root)
    with _locked(destination):
        _recover(destination)


def install_reviewed(review, steam_roots=None, *, verified_backend=None):
    """Apply a player-confirmed Fatekeeper review after the live gate permits it."""
    from .fatekeeper_install import prepare_reviewed_install

    destination = _live_destination(steam_roots)
    prepared = prepare_reviewed_install(review, steam_roots, verified_backend=verified_backend)
    if _live_destination(steam_roots) != destination:
        raise RuntimeError("Fatekeeper paths changed while staging. Reopen the review.")
    _commit(destination, prepared)
    return [Path(name) for name in prepared.writes]


def recover_live(steam_roots=None):
    """Restore the journal for the currently resolved Fatekeeper installation."""
    destination = _live_destination(steam_roots)
    with _locked(destination):
        _recover(destination)
