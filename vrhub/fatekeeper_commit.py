# SPDX-License-Identifier: GPL-3.0-only
"""Journaled Fatekeeper commit and recovery, gated to disposable prefixes."""
import fcntl
import json
import os
import re
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
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name or Path(name).as_posix() != name:
        raise RuntimeError("Invalid Fatekeeper journal path.")
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
    from . import state_transaction
    with state_transaction.locked(destination.state):
        root = destination.journal_dir
        profile_safety._safe_destination(root, destination.root)
        root.mkdir(mode=0o700, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(root / "fk4.lock", flags, 0o600), "rb") as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise RuntimeError("Unsafe Fatekeeper lock.")
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


def _identity(destination):
    """Bind recovery to the resolved prefix and storage, not just path text."""
    result = {}
    for key in ("root", "prefix", "state", "injector", "profile", "journal_dir"):
        path = getattr(destination, key)
        if not path.is_absolute() or path.resolve() != path:
            raise RuntimeError("Unsafe Fatekeeper destination identity.")
        anchor = path if key in {"root", "prefix", "journal_dir"} else path.parent
        if key in {"injector", "profile"}:
            # These trees may be absent before installation or after rollback.
            anchor = destination.prefix
        if key == "state":
            anchor = destination.state.parent
        info = anchor.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise RuntimeError("Unsafe Fatekeeper destination directory.")
        result[key] = [str(path), info.st_dev, info.st_ino]
    return result


def _assert_identity(destination, expected):
    if _identity(destination) != expected:
        raise RuntimeError("Fatekeeper destination identity changed; recovery blocked.")


def _journal(path, phase, rows, directories, backup_name, identity, *, provenance=None):
    raw = json.dumps({"schema": 2, "phase": phase, "rows": rows,
                      "directories": directories, "backup": backup_name,
                      "identity": identity}).encode()
    digest = _digest(raw)
    previous = _digest(_read(path)[0])
    if provenance is not None:
        provenance('before', previous, digest)
    _write(path, raw)
    if provenance is not None:
        provenance('after', previous, digest)
    return digest


def _parse_journal(destination, raw):
    """Validate the complete journal before touching recovery destinations."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate journal key")
            result[key] = value
        return result
    try:
        record = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RuntimeError("Invalid Fatekeeper recovery journal.") from exc
    if not isinstance(record, dict) or set(record) != {"schema", "phase", "rows", "directories", "backup", "identity"} or record["schema"] != 2:
        raise RuntimeError("Unbound or invalid Fatekeeper recovery journal; manual review required.")
    if record["phase"] not in ("applying", "committed", "recovering", "rolled-back"):
        raise RuntimeError("Unknown Fatekeeper transaction phase.")
    _assert_identity(destination, record["identity"])
    _backup_location(destination, record)
    rows, directories = record["rows"], record["directories"]
    if not isinstance(rows, list) or not 2 <= len(rows) <= 5001 or not isinstance(directories, list) or len(directories) > 10000:
        raise RuntimeError("Invalid Fatekeeper recovery inventory.")
    seen, allowed = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "old", "new", "mode"}:
            raise RuntimeError("Invalid Fatekeeper recovery row.")
        path = _target(destination, row["path"])
        name = row["path"].casefold()
        if name in seen:
            raise RuntimeError("Duplicate Fatekeeper recovery path.")
        seen.add(name)
        for digest in (row["old"], row["new"]):
            if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise RuntimeError("Invalid Fatekeeper recovery digest.")
        if row["new"] is None or (row["old"] is None and row["mode"] is not None) or (row["old"] is not None and (type(row["mode"]) is not int or not 0 <= row["mode"] <= 0o7777)):
            raise RuntimeError("Invalid Fatekeeper recovery mode or digest.")
        if path != destination.state:
            allowed.update(parent.relative_to(destination.root).as_posix() for parent in path.parents
                           if parent != destination.root and parent.is_relative_to(destination.prefix) and parent != destination.prefix)
    if rows[-1]["path"] != destination.state.relative_to(destination.root).as_posix():
        raise RuntimeError("Fatekeeper recovery state row missing or out of order.")
    if any(not isinstance(name, str) or name not in allowed for name in directories) or len(set(directories)) != len(directories):
        raise RuntimeError("Unexpected Fatekeeper recovery directory.")
    return record


def _backup_location(destination, record):
    name = record.get("backup", "fk4-backup")
    if not isinstance(name, str) or not (name == "fk4-backup" or
            (name.startswith("fk4-backup-") and len(name) == 43 and
             all(c in "0123456789abcdef" for c in name[11:]))):
        raise RuntimeError("Invalid Fatekeeper backup location.")
    path = destination.journal_dir / name
    profile_safety._safe_destination(path, destination.journal_dir)
    return path


def _state_mapping(raw):
    if raw is None:
        return {}
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate state key")
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, RecursionError) as exc:
        raise RuntimeError("Invalid Hub state during recovery.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Invalid Hub state during recovery.")
    return result


def _merged_state(current, original, incoming):
    """Restore only the two transaction-owned records; refuse conflicting edits."""
    before, after, now = map(_state_mapping, (original, incoming, current))
    keys = {"fatekeeper", "fatekeeper:profile"}
    missing = object()
    def subset(mapping):
        return {key: mapping.get(key, missing) for key in keys}
    if subset(now) not in (subset(before), subset(after)):
        raise RuntimeError("Fatekeeper rollback blocked by changed ownership records.")
    if subset(now) == subset(before):
        return current
    for key in keys:
        if key in before:
            now[key] = before[key]
        else:
            now.pop(key, None)
    return (json.dumps(now, indent=2) + "\n").encode()


def recovery_notice(state_path=None):
    """Read-only warning; never authorize recovery or create storage."""
    state_path = hub.state_file() if state_path is None else Path(state_path)
    path = state_path.parent / "fatekeeper-recovery/fk4-journal.json"
    try:
        profile_safety._safe_destination(path.parent, state_path.parent)
        raw, _ = _read(path)
        if raw is None:
            return ""
        record = _state_mapping(raw)
        if record.get("schema") != 2 or record.get("phase") not in ("applying", "recovering", "committed", "rolled-back"):
            raise RuntimeError("Unrecognized recovery journal")
        if record["phase"] in ("applying", "recovering"):
            return "Fatekeeper recovery pending. Installation blocked until the interrupted transaction is recovered."
        return ""
    except (OSError, RuntimeError, ValueError):
        return "Fatekeeper recovery journal needs manual review. Installation blocked."


def _archive_previous(destination, raw, record):
    """Copy and verify history before publishing any replacement journal.

    Leave the active journal and its original backup intact until the new
    applying journal is durably published. A staging failure cannot remove
    the previous recovery entry point.
    """
    backup = _backup_location(destination, record)
    history = destination.journal_dir / ("history-" + uuid4().hex)
    history.mkdir(mode=0o700)
    retained = history / backup.name
    retained.mkdir(mode=0o700)
    for index, row in enumerate(record["rows"]):
        _target(destination, row["path"])
        if row["old"] is None:
            continue
        data, _ = _read(backup / str(index))
        if _digest(data) != row["old"]:
            raise RuntimeError("Previous Fatekeeper backup verification failed; repair blocked.")
        _write(retained / str(index), data)
        if _digest(_read(retained / str(index))[0]) != row["old"]:
            raise RuntimeError("Retained Fatekeeper backup verification failed.")
    incoming, _ = _read(backup / "state-new")
    if _digest(incoming) != record["rows"][-1]["new"]:
        raise RuntimeError("Previous Fatekeeper state evidence verification failed.")
    _write(retained / "state-new", incoming)
    if _digest(_read(retained / "state-new")[0]) != record["rows"][-1]["new"]:
        raise RuntimeError("Retained Fatekeeper state evidence verification failed.")
    _write(history / "fk4-journal.json", raw)
    if _read(history / "fk4-journal.json")[0] != raw:
        raise RuntimeError("Retained Fatekeeper journal verification failed.")
    _sync(history)
    _sync(destination.journal_dir)



def commit(root, prepared, *, interrupt_after_files=False):
    """Commit the reviewed write set and Hub records under a verified backup journal."""
    _commit(_fixture_destination(root), prepared, interrupt_after_files=interrupt_after_files)


def _commit(destination, prepared, *, interrupt_after_files=False, process_guard=None,
            journal_published=None):
    root = destination.root
    prefix, injector, profile, state_path = (
        destination.prefix, destination.injector, destination.profile, destination.state)
    state_name = state_path.relative_to(root).as_posix()
    with _locked(destination):
        if process_guard is not None:
            process_guard()
        if prepared.prefix != prefix:
            raise RuntimeError("Fatekeeper plan targets another prefix.")
        journal = destination.journal_dir / "fk4-journal.json"
        previous_journal, _ = _read(journal)
        identity = _identity(destination)
        previous_record = _parse_journal(destination, previous_journal) if previous_journal is not None else None
        if previous_record is not None and previous_record["phase"] not in {"committed", "rolled-back"}:
            raise RuntimeError("Recover the existing Fatekeeper transaction before retrying.")
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
            snapshot = prepared.injector if folder == injector else prepared.profile
            owned = {name for name in prepared.writes if Path(name).is_relative_to(folder)}
            # Retain prior ownership only from the same canonical destination.
            if isinstance(previous, dict) and previous.get("root") == str(folder):
                prior_files = previous.get("files", [])
                if isinstance(prior_files, list):
                    for name in prior_files:
                        if not isinstance(name, str) or not name.startswith(str(folder) + "/"):
                            continue
                        rel = name[len(str(folder)) + 1:]
                        if rel in snapshot["files"] and str(folder / rel) == name:
                            owned.add(name)
            dependencies = {str(Path(name).relative_to(folder)): meta
                            for name, meta in prepared.dependencies.items()
                            if Path(name).is_relative_to(folder)}
            # Dependency evidence is not ownership. Preserve the old record
            # and exact original state bytes in the existing recovery journal.
            records[key] = {
                "installer": "fatekeeper-pair-fk4",
                "root": str(folder),
                "files": sorted(owned),
                "reviewed_dependencies": dependencies,
                "archive_sha256": prepared.archive_pins.get("uevr" if folder == injector else "profile"),
                "journal": str(journal),
                "previous": previous,
            }
        writes[state_name] = (json.dumps(records, indent=2) + "\n").encode()
        if not prepared.writes:
            return
        if previous_record is not None:
            _archive_previous(destination, previous_journal, previous_record)
        backup_dir = destination.journal_dir / "fk4-backup"
        if backup_dir.exists() or backup_dir.is_symlink() or previous_record is not None:
            backup_dir = destination.journal_dir / ("fk4-backup-" + uuid4().hex)
        backup_name = backup_dir.name
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
        _write(backup_dir / "state-new", writes[state_name])
        if _digest(_read(backup_dir / "state-new")[0]) != rows[-1]["new"]:
            raise RuntimeError("Fatekeeper incoming state backup verification failed.")
        if process_guard is not None:
            process_guard()
        _assert_identity(destination, identity)
        binding = _journal(journal, "applying", rows, sorted(directories), backup_name, identity,
                           provenance=journal_published)
        try:
            for row in rows:
                if process_guard is not None:
                    process_guard()
                _assert_identity(destination, identity)
                if journal_published is not None and _digest(_read(journal)[0]) != binding:
                    raise RuntimeError("Scoped recovery journal changed during commit.")
                path = _target(destination, row["path"])
                if _digest(_read(path)[0]) != row["old"]:
                    raise RuntimeError("Fatekeeper destination changed during commit.")
                if interrupt_after_files and path == state_path:
                    return
                _write(path, writes[row["path"]], row["mode"] if row["mode"] is not None else 0o600)
            if any(_digest(_read(_target(destination, row["path"]))[0]) != row["new"] for row in rows):
                raise RuntimeError("Fatekeeper commit verification failed.")
            if process_guard is not None:
                process_guard()
            _assert_identity(destination, identity)
            if journal_published is not None and _digest(_read(journal)[0]) != binding:
                raise RuntimeError("Scoped recovery journal changed during commit.")
            binding = _journal(journal, "committed", rows, sorted(directories), backup_name, identity,
                               provenance=journal_published)
        except (OSError, RuntimeError, ValueError):
            # Never automatically restore into an active game/injector. The
            # applying journal is durable; recovery can resume after exit.
            _recover(destination, process_guard=process_guard,
                     expected_journal=binding if journal_published is not None else None,
                     journal_published=journal_published)
            raise


def _recover(destination, *, process_guard=None, expected_journal=None,
             journal_published=None):
    if process_guard is not None:
        process_guard()
    root = destination.root
    journal = destination.journal_dir / "fk4-journal.json"
    raw, _ = _read(journal)
    if raw is None:
        raise RuntimeError("No Fatekeeper recovery journal exists.")
    if expected_journal is not None and _digest(raw) != expected_journal:
        raise RuntimeError("Scoped recovery journal changed.")
    record = _parse_journal(destination, raw)
    identity = record["identity"]
    if record["phase"] == "rolled-back":
        return
    if record["phase"] not in {"applying", "committed", "recovering"}:
        raise RuntimeError("Unknown Fatekeeper transaction phase.")
    rows = record["rows"]
    originals = []
    backup = _backup_location(destination, record)
    for index, row in enumerate(rows):
        path = _target(destination, row["path"])
        current, _ = _read(path)
        original = None if row["old"] is None else _read(backup / str(index))[0]
        if _digest(original) != row["old"]:
            raise RuntimeError("Fatekeeper rollback blocked by changed files or backups.")
        mode = row["mode"]
        if path == destination.state:
            incoming, _ = _read(backup / "state-new")
            if _digest(incoming) != row["new"]:
                raise RuntimeError("Fatekeeper rollback blocked by changed incoming state evidence.")
            if _digest(current) not in (row["old"], row["new"]):
                original = _merged_state(current, original, incoming)
                mode = _read(path)[1] if current is not None else mode
        elif _digest(current) not in (row["old"], row["new"]):
            raise RuntimeError("Fatekeeper rollback blocked by changed files or backups.")
        originals.append((path, current, original, mode))
    directories = record["directories"]
    allowed_dirs = {parent.relative_to(root).as_posix() for path, *_ in originals
                    for parent in path.parents if parent != root and parent.is_relative_to(root)}
    if not set(directories).issubset(allowed_dirs):
        raise RuntimeError("Unexpected Fatekeeper recovery directory.")
    _assert_identity(destination, identity)
    if expected_journal is not None and _digest(_read(journal)[0]) != expected_journal:
        raise RuntimeError("Scoped recovery journal changed during validation.")
    binding = _journal(journal, "recovering", rows, directories, backup.name, identity,
                       provenance=journal_published)
    for path, current, original, mode in reversed(originals):
        if current == original:
            continue
        if process_guard is not None:
            process_guard()
        _assert_identity(destination, identity)
        if journal_published is not None and _digest(_read(journal)[0]) != binding:
            raise RuntimeError("Scoped recovery journal changed during recovery.")
        _target(destination, path.relative_to(root).as_posix())
        if _read(path)[0] != current:
            raise RuntimeError("Fatekeeper destination changed during recovery.")
        if original is None:
            path.unlink()
            _sync(path.parent)
        else:
            _write(path, original, mode)
    for name in sorted(directories, key=lambda value: len(Path(value).parts), reverse=True):
        if process_guard is not None:
            process_guard()
        _assert_identity(destination, identity)
        if journal_published is not None and _digest(_read(journal)[0]) != binding:
            raise RuntimeError("Scoped recovery journal changed during recovery.")
        directory = root / name
        profile_safety._safe_destination(directory, root)
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
            _sync(directory.parent)
    _assert_identity(destination, identity)
    if journal_published is not None and _digest(_read(journal)[0]) != binding:
        raise RuntimeError("Scoped recovery journal changed during recovery.")
    binding = _journal(journal, "rolled-back", rows, directories, backup.name, identity,
                       provenance=journal_published)


def recover(root):
    """Restore both files and state after a failed or interrupted commit."""
    destination = _fixture_destination(root)
    with _locked(destination):
        _recover(destination)


def install_reviewed(review, steam_roots=None, *, verified_backend=None,
                     scoped_root=None, scoped_token=None):
    """Apply a confirmed review; scoped development is independent of release gate."""
    from .fatekeeper_install import prepare_reviewed_install
    from . import state_transaction

    if scoped_root is not None or scoped_token is not None:
        from . import fatekeeper_authorization as auth
        if scoped_root is None or scoped_token is None:
            raise RuntimeError("Complete scoped installation authorization required.")
        scope = auth.consume(scoped_token, scoped_root, "install",
                             lambda scope: auth.review_digest(scope, review))
        if steam_roots is not None and tuple(map(Path, steam_roots)) != (scope.steam,):
            raise RuntimeError("Scoped Steam root mismatch.")
        steam_roots = [scope.steam]
        destination = Destination(scope.root, scope.prefix, scope.injector,
                                  scope.profile, scope.state, scope.journal_dir)

        def guard():
            if auth.resolve_scope(scope.root) != scope:
                raise RuntimeError("Scoped destination identity changed.")
            profile_safety._assert_game_stopped("fatekeeper")

        guard()
        auth.assert_fresh(scope)
        with state_transaction.locked(destination.state):
            guard()
            auth.assert_fresh(scope)
            prepared = prepare_reviewed_install(review, steam_roots,
                                                verified_backend=verified_backend)
            guard()
            auth.assert_fresh(scope)
            if not prepared.writes:
                raise RuntimeError("Scoped fresh installation has no writes.")
            auth.begin_staging(scope)
            _commit(destination, prepared, process_guard=guard,
                    journal_published=lambda *args: auth._record_journal(scope, *args))
        return [Path(name) for name in prepared.writes]

    destination = _live_destination(steam_roots)
    prepared = prepare_reviewed_install(review, steam_roots, verified_backend=verified_backend)
    if _live_destination(steam_roots) != destination:
        raise RuntimeError("Fatekeeper paths changed while staging. Reopen the review.")
    if not prepared.writes:
        with state_transaction.locked(destination.state):
            path = destination.journal_dir / "fk4-journal.json"
            profile_safety._safe_destination(path.parent, destination.root)
            raw, _ = _read(path)
            if raw is not None and _parse_journal(destination, raw)["phase"] not in {"committed", "rolled-back"}:
                raise RuntimeError("Recover the existing Fatekeeper transaction before retrying.")
        return []
    _commit(destination, prepared, process_guard=lambda: profile_safety._assert_game_stopped("fatekeeper"))
    return [Path(name) for name in prepared.writes]


def recover_live(steam_roots=None, *, scoped_root=None, scoped_token=None):
    """Restore the exact authorized journal; ordinary recovery stays gated."""
    if scoped_root is not None or scoped_token is not None:
        from . import fatekeeper_authorization as auth
        if scoped_root is None or scoped_token is None:
            raise RuntimeError("Complete scoped recovery authorization required.")
        binding = None

        def capture(scope):
            nonlocal binding
            binding = auth._trusted_recovery_digest(scope)
            return binding

        scope = auth.consume(scoped_token, scoped_root, "recover", capture)
        if steam_roots is not None and tuple(map(Path, steam_roots)) != (scope.steam,):
            raise RuntimeError("Scoped Steam root mismatch.")
        destination = Destination(scope.root, scope.prefix, scope.injector,
                                  scope.profile, scope.state, scope.journal_dir)

        def guard():
            if auth.resolve_scope(scope.root) != scope:
                raise RuntimeError("Scoped destination identity changed.")
            profile_safety._assert_game_stopped("fatekeeper")

        guard()
        with _locked(destination):
            guard()
            _recover(destination, process_guard=guard, expected_journal=binding,
                     journal_published=lambda *args: auth._record_journal(scope, *args))
        return
    destination = _live_destination(steam_roots)
    with _locked(destination):
        _recover(destination, process_guard=lambda: profile_safety._assert_game_stopped("fatekeeper"))
