# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-K — deliberately fixture-only transactional update rehearsal.

THIS IS NOT A LIVE GAME INSTALLER. It can modify only private 0700 temporary
sandboxes created by fixture_sandbox(). No recipe/game/prefix path is accepted.
A persistent, sealed journal and verified fresh backups support recovery from
an interrupted multi-file update, including an interruption before the last
journal step. Unexpected user modifications block rollback rather than being
silently overwritten. Never call this from the real installation backend.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import shutil
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

PREFIX = "nanners-dev5d3k-fixture-"
MAX_FILES = 64
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


class TransactionBlocked(RuntimeError):
    """No verified authorization to change even the disposable fixture."""


class RecoveryBlocked(TransactionBlocked):
    """A file, recovery copy or journal changed; protect the user edit."""


class SimulatedCrash(RuntimeError):
    """Rehearsal-only injected interruption; recovery must run separately."""


@dataclass(frozen=True)
class Fixture:
    root: Path
    token: str


@dataclass(frozen=True)
class Plan:
    fixture_root: str
    rows: tuple[dict, ...]
    before: dict
    after: dict
    fingerprint: str

    @property
    def authorized_live_install(self) -> bool:
        return False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _relative(value):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise TransactionBlocked("Unsafe or absent fixture-relative file name.")
    if (chr(92) in value or ":" in value or any(ord(c) < 32 for c in value)
            or value.startswith("/") or any(x in ("", ".", "..") for x in value.split("/"))):
        raise TransactionBlocked("Noncanonical or escaping fixture path refused.")
    return PurePosixPath(value)


def _check_names(names):
    if not isinstance(names, (tuple, list, dict)) or len(names) > MAX_FILES:
        raise TransactionBlocked("Fixture file inventory exceeds bounded limit.")
    keys = list(names)
    for name in keys:
        _relative(name)
    if len({n.casefold() for n in keys}) != len(keys):
        raise TransactionBlocked("Case-insensitive fixture destination collision.")


def _assert_fixture(fixture: Fixture):
    if not isinstance(fixture, Fixture):
        raise TransactionBlocked("Only a newly created fixture handle is accepted.")
    root = fixture.root
    if (not isinstance(root, Path) or not root.is_absolute() or
            root.parent != Path("/tmp").resolve() or
            not root.name.startswith(PREFIX) or root.is_symlink()):
        raise TransactionBlocked("Transaction engine refuses real game directories.")
    try:
        st = os.lstat(root)
        marker = root / ".nanners-offline-fixture.json"
        ms = os.lstat(marker)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or
                stat.S_IMODE(st.st_mode) != 0o700 or
                not stat.S_ISREG(ms.st_mode) or ms.st_uid != os.geteuid() or
                stat.S_IMODE(ms.st_mode) & 0o077):
            raise TransactionBlocked("Fixture root or marker is unsafe.")
        with marker.open("rb") as stream:
            content = json.load(stream)
        if content != {"schema": 1, "token": fixture.token, "purpose": "dev5d3k-offline-only"}:
            raise TransactionBlocked("Fixture token or marker mismatch.")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise TransactionBlocked("Fixture marker is unavailable or invalid.") from exc
    return root


def _target(fixture, section, rel):
    root = _assert_fixture(fixture)
    if section not in ("installed", "incoming", "transaction"):
        raise TransactionBlocked("Unsafe sandbox section.")
    section_root = root / section
    try:
        head = os.lstat(section_root)
    except OSError as exc:
        raise TransactionBlocked("Fixture section is missing or unsafe.") from exc
    if not stat.S_ISDIR(head.st_mode):
        raise TransactionBlocked("Fixture section cannot be a symlink.")
    parts = _relative(rel).parts
    path = section_root
    for part in parts[:-1]:
        path = path / part
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(st.st_mode):
            raise TransactionBlocked("Unsafe fixture path ancestor.")
    target = path / parts[-1]
    try:
        st = os.lstat(target)
    except FileNotFoundError:
        return target
    if not stat.S_ISREG(st.st_mode):
        raise TransactionBlocked("Fixture destination must be a regular file.")
    return target


def _read(fixture, section, rel, *, optional=False):
    path = _target(fixture, section, rel)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        if optional:
            return None
        raise TransactionBlocked("Required fixture file is missing.")
    except OSError as exc:
        raise TransactionBlocked("Unsafe fixture file read refused.") from exc
    with os.fdopen(fd, "rb", buffering=0) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise TransactionBlocked("Nonregular or oversized fixture file.")
        data = stream.read(MAX_FILE_BYTES + 1)
        after = os.fstat(stream.fileno())
        if (len(data) != before.st_size or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                 before.st_ctime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise TransactionBlocked("Fixture file changed during read.")
    return data


def _mkdir_for(fixture, section, rel):
    root = _assert_fixture(fixture)
    parts = _relative(rel).parts[:-1]
    path = root / section
    if section not in ("installed", "incoming", "transaction"):
        raise TransactionBlocked("Unsafe sandbox section.")
    if not stat.S_ISDIR(os.lstat(path).st_mode):
        raise TransactionBlocked("Fixture section is not a regular directory.")
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise TransactionBlocked("Symlinked fixture destination directory.")
        if not path.exists():
            path.mkdir(mode=0o700)
        if not path.is_dir() or path.is_symlink():
            raise TransactionBlocked("Unsafe fixture directory.")
    return path


def _write(fixture, section, rel, data):
    if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
        raise TransactionBlocked("Only bounded fixture bytes can be written.")
    parent = _mkdir_for(fixture, section, rel)
    dest = _target(fixture, section, rel)
    fd, tmp = tempfile.mkstemp(prefix=".offline-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        _target(fixture, section, rel)
        os.replace(tmp, dest)
        _fsync_directory(parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _save_doc(fixture, section, rel, data):
    _write(fixture, section, rel, _json(data))


def _load_doc(fixture, section, rel, optional=False):
    data = _read(fixture, section, rel, optional=optional)
    if data is None:
        return None
    try:
        parsed = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise TransactionBlocked("Fixture journal or inventory JSON is invalid.") from exc
    if not isinstance(parsed, dict):
        raise TransactionBlocked("Invalid fixture document.")
    return parsed


def _seal(data, token):
    return _sha(_json({"data": data, "token": token}))


def _save_journal(fixture, data):
    copy = dict(data)
    copy["seal"] = _seal(data, fixture.token)
    _save_doc(fixture, "transaction", "journal.json", copy)


def _journal(fixture):
    doc = _load_doc(fixture, "transaction", "journal.json", optional=True)
    if doc is None:
        return None
    seal = doc.pop("seal", None)
    if seal != _seal(doc, fixture.token) or doc.get("schema") != 1:
        raise RecoveryBlocked("Recovery journal failed its integrity seal.")
    return doc


@contextmanager
def fixture_sandbox(installed: dict[str, bytes], incoming: dict[str, bytes],
                    *, managed: tuple[str, ...] | None = None):
    """Create and destroy an explicitly synthetic, private temporary game."""
    _check_names(installed)
    _check_names(incoming)
    if not incoming:
        raise TransactionBlocked("Fixture needs at least one proposed payload.")
    owned = tuple(installed) if managed is None else tuple(managed)
    _check_names(owned)
    if not set(owned).issubset(installed):
        raise TransactionBlocked("Owned file list is not present in fixture.")
    if any(not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES
           for data in [*installed.values(), *incoming.values()]):
        raise TransactionBlocked("Only small, synthetic file bytes are accepted.")
    if sum(map(len, installed.values())) + sum(map(len, incoming.values())) > MAX_TOTAL_BYTES:
        raise TransactionBlocked("Fixture exceeds safe rehearsal byte limits.")
    # Fixed Linux-only /tmp boundary: never honor TMPDIR pointing into a
    # Steam/Heroic installation or another user-controlled game directory.
    with tempfile.TemporaryDirectory(prefix=PREFIX, dir="/tmp") as temp:
        root = Path(temp).resolve()
        token = secrets.token_hex(32)
        marker = root / ".nanners-offline-fixture.json"
        marker.write_bytes(_json(
            {"schema": 1, "token": token, "purpose": "dev5d3k-offline-only"}))
        marker.chmod(0o600)
        for folder in ("installed", "incoming", "transaction"):
            (root / folder).mkdir(mode=0o700)
        fixture = Fixture(root, token)
        for name, data in installed.items():
            _write(fixture, "installed", name, data)
        for name, data in incoming.items():
            _write(fixture, "incoming", name, data)
        inventory = {name: _sha(installed[name]) for name in sorted(owned)}
        _save_doc(fixture, "transaction", "inventory.json",
                  {"schema": 1, "managed": inventory})
        yield fixture


def _inventory(fixture):
    doc = _load_doc(fixture, "transaction", "inventory.json")
    if doc.get("schema") != 1 or not isinstance(doc.get("managed"), dict):
        raise TransactionBlocked("Fixture ownership inventory invalid.")
    _check_names(doc["managed"])
    if any(not isinstance(value, str) or len(value) != 64
           or any(ch not in "0123456789abcdef" for ch in value)
           for value in doc["managed"].values()):
        raise TransactionBlocked("Fixture ownership SHA-256 invalid.")
    return doc["managed"]


def _check_live(fixture, inventory):
    total = 0
    for rel, expected in inventory.items():
        data = _read(fixture, "installed", rel)
        total += len(data)
        if total > MAX_TOTAL_BYTES or _sha(data) != expected:
            raise TransactionBlocked("Tracked installed fixture was manually modified.")
    return total


def _plan_body(fixture):
    before = _inventory(fixture)
    _check_live(fixture, before)
    incoming_dir = fixture.root / "incoming"
    names = []
    for parent, dirs, files in os.walk(incoming_dir, followlinks=False):
        for directory in dirs:
            full = Path(parent) / directory
            if full.is_symlink() or not full.is_dir():
                raise TransactionBlocked("Unsafe incoming directory.")
        for filename in files:
            rel = (Path(parent) / filename).relative_to(incoming_dir).as_posix()
            names.append(rel)
    _check_names(names)
    if not names:
        raise TransactionBlocked("No synthetic incoming files.")
    if len(before) + len(names) > MAX_FILES:
        raise TransactionBlocked("Too many fixture files.")
    # Windows/Proton deployments are not case-sensitive everywhere. A new
    # path that only differs in case from ANY existing owned file is unsafe,
    # even on a Linux host where both paths can coexist.
    occupied = {}
    installed_dir = fixture.root / "installed"
    existing = []
    for parent, dirs, files in os.walk(installed_dir, followlinks=False):
        for name in dirs:
            folder = Path(parent) / name
            if folder.is_symlink() or not folder.is_dir():
                raise TransactionBlocked("Unsafe installed fixture directory.")
        existing.extend(
            (Path(parent) / name).relative_to(installed_dir).as_posix()
            for name in files)
    _check_names(existing)
    for current in existing:
        key = current.casefold()
        if key in occupied:
            raise TransactionBlocked("Existing case-insensitive collision.")
        occupied[key] = current
    for proposed in names:
        previous = occupied.get(proposed.casefold())
        if previous is not None and previous != proposed:
            raise TransactionBlocked("Existing file differs only in letter case.")
    rows = []
    total = 0
    after = dict(before)
    for rel in sorted(names):
        current = _read(fixture, "installed", rel, optional=True)
        incoming = _read(fixture, "incoming", rel)
        if current is not None and rel not in before:
            raise TransactionBlocked("Untracked existing file collision; preserve manual files.")
        old = before.get(rel)
        new = _sha(incoming)
        total += len(incoming) + (len(current) if current else 0)
        if total > MAX_TOTAL_BYTES:
            raise TransactionBlocked("Update fixture exceeds safety byte limits.")
        if old == new:
            raise TransactionBlocked("Incoming payload has no recorded change.")
        rows.append({"path": rel, "old": old, "new": new,
                     "new_size": len(incoming), "action": "replace" if old else "add"})
        after[rel] = new
    if len({x["path"].casefold() for x in rows}) != len(rows):
        raise TransactionBlocked("Overlapping case-folded destinations.")
    body = {"root": str(fixture.root), "before": before, "after": after, "rows": rows}
    return body


def build_plan(fixture):
    """No filesystem mutations or live paths; fingerprint binds exact fixture."""
    _assert_fixture(fixture)
    if _journal(fixture) is not None:
        raise TransactionBlocked("Unresolved or finished transaction journal already exists.")
    body = _plan_body(fixture)
    return Plan(str(fixture.root), tuple(body["rows"]), body["before"], body["after"],
                _seal(body, fixture.token))


def _verify_plan(fixture, plan):
    if not isinstance(plan, Plan) or plan.fixture_root != str(fixture.root):
        raise TransactionBlocked("Plan belongs to another sandbox.")
    actual = _plan_body(fixture)
    if (plan.fingerprint != _seal(actual, fixture.token) or
            plan.before != actual["before"] or plan.after != actual["after"] or
            tuple(actual["rows"]) != plan.rows):
        raise TransactionBlocked("Stale fixture plan, source ZIP or installed content.")
    return actual


def _prepare(fixture, body):
    """Fresh backups include ALL owned files, not just proposed replacements."""
    if _journal(fixture) is not None:
        raise TransactionBlocked("Another fixture transaction already exists.")
    # Estimate all new snapshot, staged and replacement bytes BEFORE any
    # fixture update; a failure cannot affect real game files.
    backup_required = sum(len(_read(fixture, "installed", rel))
                          for rel in body["before"])
    stage_required = sum(row["new_size"] for row in body["rows"])
    try:
        available = shutil.disk_usage(fixture.root).free
    except OSError as exc:
        raise TransactionBlocked("Cannot check temporary fixture disk space.") from exc
    if available < backup_required + 2 * stage_required + 8 * 1024 * 1024:
        raise TransactionBlocked("Insufficient temporary fixture disk space.")
    saved_total = 0
    for rel, expected in sorted(body["before"].items()):
        data = _read(fixture, "installed", rel)
        saved_total += len(data)
        if saved_total > MAX_TOTAL_BYTES or _sha(data) != expected:
            raise TransactionBlocked("Cannot back up changed/oversized installed fixture.")
        _write(fixture, "transaction", "backup/" + rel, data)
        if _sha(_read(fixture, "transaction", "backup/" + rel)) != expected:
            raise TransactionBlocked("Fresh fixture backup failed its SHA-256 verification.")
    for row in body["rows"]:
        data = _read(fixture, "incoming", row["path"])
        if len(data) != row["new_size"] or _sha(data) != row["new"]:
            raise TransactionBlocked("Incoming fixture changed during staging.")
        _write(fixture, "transaction", "stage/" + row["path"], data)
        if _sha(_read(fixture, "transaction", "stage/" + row["path"])) != row["new"]:
            raise TransactionBlocked("Staged payload SHA-256 mismatch.")
    journal = {"schema": 1, "phase": "prepared", **body,
               "progress": 0, "fresh_backup_bytes": saved_total}
    _save_journal(fixture, journal)
    return journal


def _verify_journal(fixture, journal):
    if journal.get("root") != str(fixture.root):
        raise RecoveryBlocked("Recovery journal refers to another fixture.")
    before, after, rows = journal.get("before"), journal.get("after"), journal.get("rows")
    if not isinstance(before, dict) or not isinstance(after, dict) or not isinstance(rows, list):
        raise RecoveryBlocked("Incomplete recovery inventory.")
    try:
        _check_names(before)
        _check_names(after)
        _check_names([r["path"] for r in rows])
        for rel, sha in before.items():
            if not isinstance(sha, str) or len(sha) != 64:
                raise RecoveryBlocked("Invalid backup hash.")
            data = _read(fixture, "transaction", "backup/" + rel)
            if _sha(data) != sha:
                raise RecoveryBlocked("Fresh backup modified; recovery blocked.")
        if len(rows) < 1 or len(rows) > MAX_FILES:
            raise RecoveryBlocked("Invalid journal entry count.")
        for row in rows:
            if (row.get("old") != before.get(row["path"]) or
                row.get("new") != after.get(row["path"]) or
                row.get("action") not in ("replace", "add")):
                raise RecoveryBlocked("Journal ownership inconsistent.")
    except (TransactionBlocked, KeyError, TypeError) as exc:
        raise RecoveryBlocked("Unsafe or incomplete recovery manifest.") from exc
    return before, after, rows


def _restore(fixture, journal, fault=None):
    before, after, rows = _verify_journal(fixture, journal)
    # Preflight EVERY recorded file before any restoration writes. An edit made
    # during interruption is not discarded just because backups exist.
    for rel in after:
        data = _read(fixture, "installed", rel, optional=True)
        current = None if data is None else _sha(data)
        allowed = {before.get(rel), after[rel]}
        if current not in allowed:
            raise RecoveryBlocked("Unexpected manual modification; recovery preserves file.")
    journal["phase"] = "rolling_back"
    _save_journal(fixture, journal)
    count = 0
    for row in reversed(rows):
        rel = row["path"]
        original = before.get(rel)
        data = _read(fixture, "installed", rel, optional=True)
        current = None if data is None else _sha(data)
        if current == original:
            continue
        if original is None:
            _target(fixture, "installed", rel).unlink()
        else:
            restored = _read(fixture, "transaction", "backup/" + rel)
            if _sha(restored) != original:
                raise RecoveryBlocked("Fresh backup changed during rollback.")
            _write(fixture, "installed", rel, restored)
        count += 1
        if fault == f"after_rollback:{count}":
            raise SimulatedCrash("Simulated interruption during rollback.")
    for rel, expected in before.items():
        if _sha(_read(fixture, "installed", rel)) != expected:
            raise RecoveryBlocked("Restored files do not match initial fixture hashes.")
    _save_doc(fixture, "transaction", "inventory.json",
              {"schema": 1, "managed": before})
    journal["phase"] = "rolled_back"
    journal["progress"] = 0
    _save_journal(fixture, journal)
    return {"status": "Rolled back to recorded pre-update files",
            "checked": len(before), "authorized_live_install": False}


def execute(fixture, plan, *, fault=None):
    """Fixture-only update, crash injection and self-contained safety rollback."""
    _assert_fixture(fixture)
    with _locked(fixture):
        if _journal(fixture) is not None:
            raise TransactionBlocked("Existing transaction must not be overwritten.")
        body = _verify_plan(fixture, plan)
        journal = _prepare(fixture, body)
        if fault == "after_backup":
            raise SimulatedCrash("Simulated interruption after verified fresh backup.")
        try:
            journal["phase"] = "applying"
            _save_journal(fixture, journal)
            for i, row in enumerate(body["rows"], 1):
                rel = row["path"]
                current = _read(fixture, "installed", rel, optional=True)
                expected = row["old"]
                if (None if current is None else _sha(current)) != expected:
                    raise TransactionBlocked("Installed fixture changed during update.")
                staged = _read(fixture, "transaction", "stage/" + rel)
                if _sha(staged) != row["new"]:
                    raise TransactionBlocked("Staged fixture payload changed.")
                _write(fixture, "installed", rel, staged)
                journal["progress"] = i
                _save_journal(fixture, journal)
                if fault == f"after_replace:{i}":
                    raise SimulatedCrash("Simulated interrupted replacement.")
            if fault == "after_all_files":
                raise SimulatedCrash("Simulated interruption before inventory commit.")
            _save_doc(fixture, "transaction", "inventory.json",
                      {"schema": 1, "managed": body["after"]})
            if fault == "after_inventory":
                raise SimulatedCrash("Simulated interruption during commit.")
            journal["phase"] = "committed"
            _save_journal(fixture, journal)
        except SimulatedCrash:
            raise
        except Exception as exc:
            try:
                _restore(fixture, journal)
            except RecoveryBlocked as recover_exc:
                raise RecoveryBlocked(
                    "Fixture failed during update; verified recovery blocked. "
                    "Manual fixture review needed.") from recover_exc
            raise TransactionBlocked(
                "Fixture update failed and was rolled back automatically.") from exc
    return {"status": "Committed in disposable fixture", "replaced": len(plan.rows),
            "fresh_backup_verified": len(plan.before),
            "authorized_live_install": False}


@contextmanager
def _locked(fixture):
    root = _assert_fixture(fixture)
    path = root / "transaction" / "fixture.lock"
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "rb+", buffering=0) as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise TransactionBlocked("Unsafe fixture lock.")
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield
    finally:
        pass


def recover(fixture, *, fault=None):
    """Recover only an incomplete fixture transaction; never a real game."""
    _assert_fixture(fixture)
    with _locked(fixture):
        journal = _journal(fixture)
        if journal is None:
            raise RecoveryBlocked("No fixture journal available.")
        if journal.get("phase") == "rolled_back":
            before, _, _ = _verify_journal(fixture, journal)
            if _inventory(fixture) != before:
                raise RecoveryBlocked("Post-rollback owner inventory changed.")
            try:
                _check_live(fixture, before)
            except TransactionBlocked as exc:
                raise RecoveryBlocked("Post-rollback files changed.") from exc
            return {"status": "Already rolled back", "checked": len(before),
                    "authorized_live_install": False}
        if journal.get("phase") == "committed":
            raise RecoveryBlocked("Completed transaction needs explicit rollback, not crash recovery.")
        if journal.get("phase") not in ("prepared", "applying", "rolling_back"):
            raise RecoveryBlocked("Unknown transaction state.")
        return _restore(fixture, journal, fault)


def rollback(fixture):
    """Explicit rollback of one fully committed *fixture* update."""
    _assert_fixture(fixture)
    with _locked(fixture):
        journal = _journal(fixture)
        if journal is None or journal.get("phase") != "committed":
            raise RecoveryBlocked("Only a committed fixture update can be rolled back explicitly.")
        return _restore(fixture, journal)


def status(fixture):
    """Read-only state inspection; no real filesystem path accepted."""
    _assert_fixture(fixture)
    journal = _journal(fixture)
    return {"phase": journal.get("phase") if journal else "unstarted",
            "managed_files": len(_inventory(fixture)),
            "authorized_live_install": False}


def demo():
    """User-invoked, tiny self-contained transaction and crash/recovery demo."""
    with fixture_sandbox(
        {"mods/VR.dll": b"owned-original", "config/settings.ini": b"original-config"},
        {"mods/VR.dll": b"verified-new-build", "mods/helper.dll": b"new-helper"},
    ) as sandbox:
        plan = build_plan(sandbox)
        try:
            execute(sandbox, plan, fault="after_replace:1")
        except SimulatedCrash:
            pass
        else:
            raise AssertionError("Expected injected interruption.")
        pending = status(sandbox)["phase"]
        recovered = recover(sandbox)
        if (_read(sandbox, "installed", "mods/VR.dll") != b"owned-original"
                or _read(sandbox, "installed", "config/settings.ini") != b"original-config"
                or _read(sandbox, "installed", "mods/helper.dll", optional=True) is not None):
            raise AssertionError("Disposable fixture recovery failed.")
        return {"fixture_only": True, "interruption": pending,
                "result": recovered["status"],
                "backups_checked": recovered["checked"],
                "real_game_files_modified": False,
                "authorized_live_install": False}
