# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-L — hardened fixture-only transaction and recovery rehearsal.

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
MAX_DIRECTORIES = 256


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


def _check_sha(sha):
    return (isinstance(sha, str) and len(sha) == 64 and
            all(ch in "0123456789abcdef" for ch in sha))


def _snapshot_dirs(fixture):
    """Preserve every synthetic installed directory, including empty ones."""
    top = _assert_fixture(fixture) / "installed"
    if not stat.S_ISDIR(os.lstat(top).st_mode):
        raise TransactionBlocked("Installed fixture section is unsafe.")
    result = {}
    for parent, dirs, files in os.walk(top, followlinks=False):
        dirs.sort()
        for name in dirs:
            path = Path(parent) / name
            st = os.lstat(path)
            if not stat.S_ISDIR(st.st_mode):
                raise TransactionBlocked("Unsafe fixture directory or symlink.")
            rel = path.relative_to(top).as_posix()
            _relative(rel)
            if len(result) >= MAX_DIRECTORIES:
                raise TransactionBlocked("Too many fixture directories.")
            result[rel] = stat.S_IMODE(st.st_mode)
    if len({d.casefold() for d in result}) != len(result):
        raise TransactionBlocked("Case-insensitive fixture directory collision.")
    return dict(sorted(result.items()))


def _mode(fixture, section, rel):
    st = os.lstat(_target(fixture, section, rel))
    if not stat.S_ISREG(st.st_mode):
        raise TransactionBlocked("File mode source is not regular.")
    return stat.S_IMODE(st.st_mode)


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
    original_mode = _mode(fixture, section, rel) if dest.exists() else 0o600
    fd, tmp = tempfile.mkstemp(prefix=".offline-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), original_mode)
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


def _save_inventory(fixture, managed):
    _check_names(managed)
    if any(not _check_sha(sha) for sha in managed.values()):
        raise TransactionBlocked("Cannot save malformed fixture ownership record.")
    body = {"schema": 1, "managed": managed}
    _save_doc(fixture, "transaction", "inventory.json",
              {**body, "seal": _seal(body, fixture.token)})


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
        _save_inventory(fixture, inventory)
        yield fixture


def _inventory(fixture):
    doc = _load_doc(fixture, "transaction", "inventory.json")
    seal = doc.pop("seal", None)
    if (doc.get("schema") != 1 or not isinstance(doc.get("managed"), dict)
            or seal != _seal(doc, fixture.token)):
        raise TransactionBlocked("Fixture ownership inventory missing or seal mismatch.")
    _check_names(doc["managed"])
    if any(not _check_sha(value) for value in doc["managed"].values()):
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
    # The plan fingerprint now binds the entire prior directory layout and
    # modes of owned files, so stale ownership/topology cannot be reused.
    before_dirs = _snapshot_dirs(fixture)
    before_modes = {rel: _mode(fixture, "installed", rel)
                    for rel in sorted(before)}
    new_dirs = set()
    for rel in names:
        parts = _relative(rel).parts
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor not in before_dirs:
                new_dirs.add(ancestor)
    if len(new_dirs) + len(before_dirs) > MAX_DIRECTORIES:
        raise TransactionBlocked("Future fixture directory count exceeds bound.")
    directory_names = [*before_dirs, *new_dirs]
    if len({name.casefold() for name in directory_names}) != len(directory_names):
        raise TransactionBlocked("Future fixture directory differs only in letter case.")
    body = {"root": str(fixture.root), "before": before, "after": after,
            "rows": rows, "dirs_before": before_dirs,
            "new_dirs": sorted(new_dirs), "modes_before": before_modes}
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


def _prepare(fixture, body, fault=None):
    """Persist intent BEFORE writing even the first backup or staged file."""
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
    journal = {"schema": 1, "phase": "preparing", **body,
               "progress": 0, "fresh_backup_bytes": 0}
    _save_journal(fixture, journal)
    if fault == "after_prepare_start":
        raise SimulatedCrash("Interrupted before first fresh backup.")
    saved_total = 0
    for number, (rel, expected) in enumerate(sorted(body["before"].items()), 1):
        data = _read(fixture, "installed", rel)
        saved_total += len(data)
        if saved_total > MAX_TOTAL_BYTES or _sha(data) != expected:
            raise TransactionBlocked("Cannot back up changed/oversized installed fixture.")
        _write(fixture, "transaction", "backup/" + rel, data)
        if _sha(_read(fixture, "transaction", "backup/" + rel)) != expected:
            raise TransactionBlocked("Fresh fixture backup failed its SHA-256 verification.")
        if fault == f"after_backup_file:{number}":
            raise SimulatedCrash("Interrupted during backup creation.")
    for number, row in enumerate(body["rows"], 1):
        data = _read(fixture, "incoming", row["path"])
        if len(data) != row["new_size"] or _sha(data) != row["new"]:
            raise TransactionBlocked("Incoming fixture changed during staging.")
        _write(fixture, "transaction", "stage/" + row["path"], data)
        if _sha(_read(fixture, "transaction", "stage/" + row["path"])) != row["new"]:
            raise TransactionBlocked("Staged payload SHA-256 mismatch.")
        if fault == f"after_stage_file:{number}":
            raise SimulatedCrash("Interrupted during incoming payload staging.")
    journal["phase"] = "prepared"
    journal["fresh_backup_bytes"] = saved_total
    _save_journal(fixture, journal)
    return journal


def _verify_journal(fixture, journal, *, require_backups=True):
    if journal.get("root") != str(fixture.root):
        raise RecoveryBlocked("Recovery journal refers to another fixture.")
    before, after, rows = journal.get("before"), journal.get("after"), journal.get("rows")
    dirs_before = journal.get("dirs_before")
    modes_before = journal.get("modes_before")
    new_dirs = journal.get("new_dirs")
    if (not isinstance(before, dict) or not isinstance(after, dict) or
            not isinstance(rows, list) or not isinstance(dirs_before, dict) or
            not isinstance(modes_before, dict) or not isinstance(new_dirs, list)):
        raise RecoveryBlocked("Incomplete recovery inventory or directory snapshot.")
    try:
        _check_names(before)
        _check_names(after)
        _check_names([r["path"] for r in rows])
        if len(dirs_before) + len(new_dirs) > MAX_DIRECTORIES:
            raise RecoveryBlocked("Directory manifest exceeds rehearsal bounds.")
        for name, mode in dirs_before.items():
            _relative(name)
            if type(mode) is not int or mode < 0 or mode > 0o7777:
                raise RecoveryBlocked("Original directory mode is invalid.")
        for name in new_dirs:
            _relative(name)
        all_dirs = [*dirs_before, *new_dirs]
        if (len(set(new_dirs)) != len(new_dirs) or
                len({name.casefold() for name in all_dirs}) != len(all_dirs) or
                set(new_dirs) & set(dirs_before)):
            raise RecoveryBlocked("New directory inventory is inconsistent.")
        if set(modes_before) != set(before):
            raise RecoveryBlocked("Owned-file mode manifest is incomplete.")
        for mode in modes_before.values():
            if type(mode) is not int or mode < 0 or mode > 0o7777:
                raise RecoveryBlocked("Owned-file mode is invalid.")
        if len(rows) < 1 or len(rows) > MAX_FILES:
            raise RecoveryBlocked("Invalid journal entry count.")
        generated = dict(before)
        for row in rows:
            rel = row["path"]
            if (not _check_sha(row.get("new")) or
                    row.get("old") != before.get(rel) or
                    row.get("action") != ("replace" if rel in before else "add") or
                    type(row.get("new_size")) is not int or
                    not 0 <= row["new_size"] <= MAX_FILE_BYTES):
                raise RecoveryBlocked("Journal ownership inconsistent.")
            generated[rel] = row["new"]
        if generated != after or any(not _check_sha(v) for v in before.values()):
            raise RecoveryBlocked("Journal release ownership diverges.")
        expected_new_dirs = set()
        for row in rows:
            parts = _relative(row["path"]).parts
            for i in range(1, len(parts)):
                parent = "/".join(parts[:i])
                if parent not in dirs_before:
                    expected_new_dirs.add(parent)
        if set(new_dirs) != expected_new_dirs:
            raise RecoveryBlocked("New directory inventory is stale or inconsistent.")
        if require_backups:
            for rel, sha in before.items():
                data = _read(fixture, "transaction", "backup/" + rel)
                if _sha(data) != sha:
                    raise RecoveryBlocked("Fresh backup modified; recovery blocked.")
    except (TransactionBlocked, KeyError, TypeError, ValueError) as exc:
        raise RecoveryBlocked("Unsafe or incomplete recovery manifest.") from exc
    return before, after, rows


def _preflight_recovery(fixture, journal, before, after, rows):
    """Refuse ALL unexpected fixture changes before restoring any file."""
    owned = _inventory(fixture)
    if owned not in (before, after):
        raise RecoveryBlocked("Stale or changed fixture ownership inventory.")
    existing = _snapshot_dirs(fixture)
    prior = journal["dirs_before"]
    planned = set(journal["new_dirs"])
    # Our transaction only creates new_dirs. Any other directory creation,
    # removal or chmod is an external change and cannot be silently undone.
    if not set(prior).issubset(existing):
        raise RecoveryBlocked("Original fixture directory disappeared.")
    if set(existing) - set(prior) - planned:
        raise RecoveryBlocked("Unexpected user-created directory; recovery blocked.")
    for name, mode in prior.items():
        if existing[name] != mode:
            raise RecoveryBlocked("Original directory permissions changed.")
    for name in planned & set(existing):
        if existing[name] != 0o700:
            raise RecoveryBlocked("New fixture directory permissions changed.")
    for rel in after:
        data = _read(fixture, "installed", rel, optional=True)
        current = None if data is None else _sha(data)
        if current not in {before.get(rel), after[rel]}:
            raise RecoveryBlocked("Unexpected manual modification; recovery preserves file.")
        if data is not None:
            expected_mode = journal["modes_before"].get(rel, 0o600)
            if _mode(fixture, "installed", rel) != expected_mode:
                raise RecoveryBlocked("Installed fixture file permissions changed.")
    # Complete directory topology: remove only empty transaction-created dirs
    # that contain no untracked user data. Check before ANY restore writes.
    allowed_additions = {row["path"] for row in rows if row["old"] is None}
    installed_root = fixture.root / "installed"
    for parent, dirs, files in os.walk(installed_root, followlinks=False):
        for name in files:
            rel = (Path(parent) / name).relative_to(installed_root).as_posix()
            if any(rel.startswith(directory + "/") for directory in planned):
                if rel not in allowed_additions:
                    raise RecoveryBlocked("Untracked user file in created directory.")
                _read(fixture, "installed", rel, optional=True)
    return existing


def _abort_incomplete_preparation(fixture, journal):
    """Safe abort of an interrupted backup/stage: no installed-file writes."""
    before, after, rows = _verify_journal(fixture, journal, require_backups=False)
    # The transaction cannot apply until phase=prepared. If anything changed
    # meanwhile, refuse even an apparent successful abort.
    if _inventory(fixture) != before:
        raise RecoveryBlocked("Ownership changed while backup was incomplete.")
    try:
        _check_live(fixture, before)
    except TransactionBlocked as exc:
        raise RecoveryBlocked("Installed files changed during backup preparation.") from exc
    if _snapshot_dirs(fixture) != journal["dirs_before"]:
        raise RecoveryBlocked("Installed directory layout changed during preparation.")
    for rel, expected_mode in journal["modes_before"].items():
        if _mode(fixture, "installed", rel) != expected_mode:
            raise RecoveryBlocked("Installed file permissions changed during preparation.")
    journal["phase"] = "aborted_before_apply"
    journal["progress"] = 0
    journal["fresh_backup_bytes"] = 0
    _save_journal(fixture, journal)
    return {"status": "Aborted incomplete preparation; installed fixture unchanged",
            "checked": len(before), "partial_backup_trusted": False,
            "authorized_live_install": False}


def _restore(fixture, journal, fault=None):
    before, after, rows = _verify_journal(fixture, journal)
    present_dirs = _preflight_recovery(fixture, journal, before, after, rows)
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
            _fsync_directory(_target(fixture, "installed", rel).parent)
        else:
            restored = _read(fixture, "transaction", "backup/" + rel)
            if _sha(restored) != original:
                raise RecoveryBlocked("Fresh backup changed during rollback.")
            _write(fixture, "installed", rel, restored)
        count += 1
        if fault == f"after_rollback:{count}":
            raise SimulatedCrash("Simulated interruption during rollback.")
    # File-level recovery is not sufficient: remove only directories that
    # this transaction actually created, from deepest to shallowest.
    removed = 0
    for rel in sorted(journal["new_dirs"], key=lambda x: (-x.count("/"), x)):
        if rel not in present_dirs:
            continue
        directory = fixture.root / "installed" / rel
        if not stat.S_ISDIR(os.lstat(directory).st_mode):
            raise RecoveryBlocked("Created fixture directory became unsafe.")
        try:
            directory.rmdir()
        except OSError as exc:
            raise RecoveryBlocked("Created directory not empty; preserve user data.") from exc
        _fsync_directory(directory.parent)
        removed += 1
        if fault == f"after_directory_cleanup:{removed}":
            raise SimulatedCrash("Simulated interruption during directory cleanup.")
    if _snapshot_dirs(fixture) != journal["dirs_before"]:
        raise RecoveryBlocked("Directory topology was not fully restored.")
    for rel, expected in before.items():
        if (_sha(_read(fixture, "installed", rel)) != expected or
                _mode(fixture, "installed", rel) != journal["modes_before"][rel]):
            raise RecoveryBlocked("Restored fixture bytes or modes do not match.")
    _save_inventory(fixture, before)
    journal["phase"] = "rolled_back"
    journal["progress"] = 0
    _save_journal(fixture, journal)
    return {"status": "Rolled back to recorded pre-update files",
            "checked": len(before), "directories_restored": removed,
            "authorized_live_install": False}

def execute(fixture, plan, *, fault=None):
    """Fixture-only update, crash injection and self-contained safety rollback."""
    _assert_fixture(fixture)
    with _locked(fixture):
        if _journal(fixture) is not None:
            raise TransactionBlocked("Existing transaction must not be overwritten.")
        body = _verify_plan(fixture, plan)
        try:
            journal = _prepare(fixture, body, fault=fault)
        except SimulatedCrash:
            raise
        except Exception as exc:
            # A preflight refusal has no journal and must retain its precise
            # diagnostic (e.g., insufficient disk space). Once phase=preparing
            # exists, failed copies require explicit safe recovery.
            if _journal(fixture) is None and isinstance(exc, TransactionBlocked):
                raise
            raise TransactionBlocked(
                "Backup preparation failed; inspect/recover fixture before retry."
            ) from exc
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
            _save_inventory(fixture, body["after"])
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
                if (_snapshot_dirs(fixture) != journal["dirs_before"] or
                        any(_mode(fixture, "installed", rel) != mode
                            for rel, mode in journal["modes_before"].items())):
                    raise RecoveryBlocked("Post-rollback topology or file modes changed.")
            except TransactionBlocked as exc:
                raise RecoveryBlocked("Post-rollback files changed.") from exc
            return {"status": "Already rolled back", "checked": len(before),
                    "authorized_live_install": False}
        if journal.get("phase") in ("preparing", "aborted_before_apply"):
            if journal["phase"] == "aborted_before_apply":
                before, _, _ = _verify_journal(fixture, journal, require_backups=False)
                if _inventory(fixture) != before:
                    raise RecoveryBlocked("Ownership changed after incomplete backup was aborted.")
                try:
                    _check_live(fixture, before)
                except TransactionBlocked as exc:
                    raise RecoveryBlocked("Files changed after backup was aborted.") from exc
                if (_snapshot_dirs(fixture) != journal["dirs_before"] or
                        any(_mode(fixture, "installed", rel) != mode
                            for rel, mode in journal["modes_before"].items())):
                    raise RecoveryBlocked("Directory layout or file modes changed after backup abort.")
                return {"status": "Already aborted incomplete preparation",
                        "checked": len(before), "partial_backup_trusted": False,
                        "authorized_live_install": False}
            return _abort_incomplete_preparation(fixture, journal)
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



def demo_hardened():
    """Dev5D3-L preview-only multi-case recovery, no real-game paths."""
    with fixture_sandbox(
        {"mods/VR.dll": b"old-vr", "config/options.ini": b"user-original"},
        {"mods/VR.dll": b"new-vr", "extra/nested/helper.dll": b"helper"},
    ) as fixture:
        baseline = _snapshot_dirs(fixture)
        try:
            execute(fixture, build_plan(fixture), fault="after_backup_file:1")
        except SimulatedCrash:
            pass
        else:
            raise AssertionError("Missing backup interruption.")
        if status(fixture)["phase"] != "preparing":
            raise AssertionError("Early journal was not durable.")
        prep = recover(fixture)
        if (prep.get("partial_backup_trusted") is not False or
                _read(fixture, "installed", "mods/VR.dll") != b"old-vr" or
                _snapshot_dirs(fixture) != baseline):
            raise AssertionError("Incomplete preparation was not safely aborted.")
        preparation_result = prep["status"]
    with fixture_sandbox(
        {"mods/VR.dll": b"old-vr", "config/options.ini": b"user-original"},
        {"mods/VR.dll": b"new-vr", "extra/nested/helper.dll": b"helper"},
    ) as fixture:
        baseline = _snapshot_dirs(fixture)
        try:
            execute(fixture, build_plan(fixture), fault="after_replace:2")
        except SimulatedCrash:
            pass
        else:
            raise AssertionError("Missing replacement interruption.")
        restored = recover(fixture)
        if (_snapshot_dirs(fixture) != baseline or
                (fixture.root / "installed/extra").exists() or
                _read(fixture, "installed", "mods/VR.dll") != b"old-vr" or
                _read(fixture, "installed", "config/options.ini") != b"user-original" or
                _read(fixture, "installed", "extra/nested/helper.dll", optional=True) is not None):
            raise AssertionError("Interrupted update failed complete topology recovery.")
        directories = restored["directories_restored"]
    with fixture_sandbox({"mods/VR.dll": b"old"},
                         {"mods/VR.dll": b"new"}) as fixture:
        try:
            execute(fixture, build_plan(fixture), fault="after_replace:1")
        except SimulatedCrash:
            pass
        else:
            raise AssertionError("Missing manual-edit scenario interruption.")
        _write(fixture, "installed", "mods/VR.dll", b"manual-user-edit")
        try:
            recover(fixture)
        except RecoveryBlocked:
            protected = _read(fixture, "installed", "mods/VR.dll") == b"manual-user-edit"
        else:
            protected = False
        if not protected:
            raise AssertionError("Unexpected user edit was overwritten.")
    return {
        "fixture_only": True,
        "preparation": preparation_result,
        "rollback": restored["status"],
        "directories_restored": directories,
        "manual_edit_protected": protected,
        "authorized_live_install": False,
        "real_game_files_modified": False,
        "temporary_fixtures_discarded": True,
    }
