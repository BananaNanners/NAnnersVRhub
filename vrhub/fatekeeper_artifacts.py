# SPDX-License-Identifier: GPL-3.0-only
"""Read-only recovery artifact inventory; names and types are not authority.

This diagnostic never provisions storage, adopts files, or grants permission
to install/recover. The caller must independently validate active provenance.
Historical byte verification and maintenance policy are separate stages.
"""
from dataclasses import dataclass
import os
import re
import stat
from pathlib import Path

_BACKUP = re.compile(r"fk4-backup(?:-[0-9a-f]{32})?\Z")
_HISTORY = re.compile(r"history-[0-9a-f]{32}\Z")
_ROW = re.compile(r"(?:0|[1-9][0-9]*|state-new)\Z")
_TEMP = re.compile(r"\.(?:[0-9]+|state-new|fk4-journal\.json)-[a-zA-Z0-9_]+\Z")
_MAX_ENTRIES = 20000
_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@dataclass(frozen=True)
class Artifact:
    name: str
    kind: str


def inventory(directory, *, active_backup=None, staging=False):
    """Classify observed shapes using caller-supplied provenance hints.

    'history-candidate' means structurally plausible, NOT complete or trusted.
    A staging candidate is not proof of origin. No file contents are opened.
    Refuse unsafe ancestor traversal and bound the total enumeration.
    """
    directory = Path(directory)
    if not directory.is_absolute() or ".." in directory.parts:
        raise RuntimeError("Recovery inventory requires an absolute canonical path.")
    if active_backup is not None and (not isinstance(active_backup, str) or not _BACKUP.fullmatch(active_backup)):
        raise RuntimeError("Invalid active backup hint.")
    rows = []
    remaining = _MAX_ENTRIES

    def entries(fd):
        nonlocal remaining
        result = []
        with os.scandir(fd) as scan:
            for item in scan:
                remaining -= 1
                if remaining < 0:
                    raise RuntimeError("Recovery artifact inventory limit exceeded.")
                result.append((item.name, item.stat(follow_symlinks=False)))
        return sorted(result)

    def safe_file(info, private=True):
        return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and info.st_nlink == 1 and (not private or stat.S_IMODE(info.st_mode) == 0o600))

    def safe_dir(info):
        return (stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o700)

    def open_child(fd, name, info):
        child = os.open(name, _FLAGS, dir_fd=fd)
        now = os.fstat(child)
        if not safe_dir(now) or (now.st_dev, now.st_ino) != (info.st_dev, info.st_ino):
            os.close(child)
            raise RuntimeError("Recovery artifact directory changed during inventory.")
        return child

    def backup_shape(fd, name, info, path):
        child = open_child(fd, name, info)
        safe = True
        try:
            for leaf, meta in entries(child):
                kind = ("backup-file" if safe_file(meta) and _ROW.fullmatch(leaf) else
                        "atomic-residue" if safe_file(meta) and _TEMP.fullmatch(leaf) else "unsafe-or-unknown")
                rows.append(Artifact(path + "/" + leaf, kind))
                safe &= kind == "backup-file"
        finally:
            os.close(child)
        return safe

    # Walk every ancestor using directory descriptors, never following links.
    fd = os.open("/", _FLAGS)
    try:
        for part in directory.parts[1:]:
            try:
                child = os.open(part, _FLAGS, dir_fd=fd)
            except FileNotFoundError:
                return ()
            os.close(fd)
            fd = child
        if not safe_dir(os.fstat(fd)):
            raise RuntimeError("Unsafe recovery inventory directory.")
        for name, info in entries(fd):
            if name == "fk4.lock" and safe_file(info, private=False):
                kind = "lock"
            elif name == "fk4-journal.json" and safe_file(info):
                kind = "journal-candidate"
            elif _BACKUP.fullmatch(name) and safe_dir(info):
                safe = backup_shape(fd, name, info, name)
                kind = ("active-backup-candidate" if name == active_backup else
                        "staging-candidate" if staging and active_backup is None else "orphan-backup-candidate")
                if not safe:
                    kind = "unsafe-backup"
            elif _HISTORY.fullmatch(name) and safe_dir(info):
                child = open_child(fd, name, info)
                try:
                    items = entries(child)
                    journals = backups = 0
                    safe = True
                    for leaf, meta in items:
                        path = name + "/" + leaf
                        if leaf == "fk4-journal.json" and safe_file(meta):
                            journals += 1
                            subtype = "historical-journal-candidate"
                        elif _BACKUP.fullmatch(leaf) and safe_dir(meta):
                            backups += 1
                            good = backup_shape(child, leaf, meta, path)
                            safe &= good
                            subtype = "historical-backup-candidate" if good else "unsafe-backup"
                        else:
                            safe = False
                            subtype = "atomic-residue" if safe_file(meta) and _TEMP.fullmatch(leaf) else "unsafe-or-unknown"
                        rows.append(Artifact(path, subtype))
                    kind = "history-candidate" if safe and journals == backups == 1 else "incomplete-or-unsafe-history"
                finally:
                    os.close(child)
            elif safe_file(info) and _TEMP.fullmatch(name):
                kind = "atomic-residue"
            else:
                kind = "unsafe-or-unknown"
            rows.append(Artifact(name, kind))
        return tuple(sorted(rows, key=lambda row: row.name))
    finally:
        os.close(fd)


@dataclass(frozen=True)
class HistoryEvidence:
    name: str
    backup: str
    journal_sha256: str
    phase: str


def verify_history(destination, *, active_backup=None):
    """Check historical copies and originals, not historical authority.

    Caller must hold the transaction lock for a maintenance decision.
    Existing active provenance and storage checks are independent. Returns
    evidence of consistency only; a mutually rewritten history and original
    cannot be authenticated by this legacy format.
    """
    from . import fatekeeper_commit as tx
    from hashlib import sha256
    from contextlib import ExitStack

    directory = destination.journal_dir
    observed = inventory(directory, active_backup=active_backup)
    kinds = {row.name: row.kind for row in observed}
    histories = [row.name for row in observed if "/" not in row.name
                 and row.kind == "history-candidate"]
    if any(_HISTORY.fullmatch(row.name) and row.kind != "history-candidate"
           for row in observed):
        raise RuntimeError("Incomplete or unsafe Fatekeeper historical evidence.")
    if not histories:
        return ()
    remaining = 2 * 1024**3

    def open_dir(stack, parent, name, private=True):
        fd = os.open(name, _FLAGS, dir_fd=parent)
        stack.callback(os.close, fd)
        info = os.fstat(fd)
        if private and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise RuntimeError("Unsafe historical evidence directory.")
        return fd

    def read_file(fd, name, *, capture=False):
        nonlocal remaining
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        with os.fdopen(os.open(name, flags, dir_fd=fd), "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                    or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600
                    or before.st_size > 64 * 1024**2 or before.st_size > remaining):
                raise RuntimeError("Unsafe or oversized historical evidence file.")
            digest = sha256()
            data = bytearray()
            total = 0
            while block := stream.read(1024**2):
                total += len(block)
                if total > before.st_size or total > remaining:
                    raise RuntimeError("Historical evidence file changed or exceeded limit.")
                digest.update(block)
                if capture:
                    data.extend(block)
            remaining -= total
            after = os.fstat(stream.fileno())
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            def identity(info):
                return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
                        info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            if total != before.st_size or identity(before) != identity(after) or identity(after) != identity(current):
                raise RuntimeError("Historical evidence changed during verification.")
            return digest.hexdigest(), bytes(data)

    def exact_members(fd, expected):
        with os.scandir(fd) as scan:
            seen = set()
            for item in scan:
                if item.name not in expected or len(seen) >= len(expected):
                    raise RuntimeError("Unexpected historical backup membership.")
                seen.add(item.name)
        if seen != expected:
            raise RuntimeError("Missing historical backup evidence.")

    result = []
    by_backup = {}
    with ExitStack() as stack:
        root = open_dir(stack, None, "/", private=False)
        for part in directory.parts[1:]:
            root = open_dir(stack, root, part, private=False)
        info = os.fstat(root)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError("Unsafe recovery evidence directory.")
        for name in histories:
            with ExitStack() as local:
                history = open_dir(local, root, name)
                digest, raw = read_file(history, "fk4-journal.json", capture=True)
                record = tx._parse_journal(destination, raw)
                if record["phase"] not in {"committed", "rolled-back"}:
                    raise RuntimeError("Nonterminal historical Fatekeeper journal.")
                backup = record["backup"]
                exact_members(history, {"fk4-journal.json", backup})
                if kinds.get(backup) not in {"active-backup-candidate", "orphan-backup-candidate"}:
                    raise RuntimeError("Missing or unsafe retained original backup.")
                if backup in by_backup and by_backup[backup] != digest:
                    raise RuntimeError("Conflicting historical journals for retained backup.")
                by_backup[backup] = digest
                expected = {str(i): row["old"] for i, row in enumerate(record["rows"])
                            if row["old"] is not None}
                expected["state-new"] = record["rows"][-1]["new"]
                for parent in (history, root):
                    folder = open_dir(local, parent, backup)
                    exact_members(folder, set(expected))
                    for leaf, wanted in expected.items():
                        actual, _ = read_file(folder, leaf)
                        if actual != wanted:
                            raise RuntimeError("Historical backup SHA-256 verification failed.")
                result.append(HistoryEvidence(name, backup, digest, record["phase"]))
        if inventory(directory, active_backup=active_backup) != observed:
            raise RuntimeError("Recovery artifact inventory changed during history verification.")
    return tuple(result)


def validate_maintenance(destination, record):
    """Refuse unresolved artifacts before new writes or a managed no-op.

    Active journal provenance must already be checked by the caller under
    the state lock. Never use this policy to authorize active recovery.
    """
    from . import fatekeeper_commit as tx
    active = record["backup"]
    rows = inventory(destination.journal_dir, active_backup=active)
    kinds = {row.name: row.kind for row in rows}
    if kinds.get("fk4-journal.json") != "journal-candidate":
        raise RuntimeError("Unsafe active Fatekeeper journal evidence.")
    if kinds.get(active) != "active-backup-candidate":
        raise RuntimeError("Unsafe active Fatekeeper backup evidence.")
    expected = {str(i): row["old"] for i, row in enumerate(record["rows"])
                if row["old"] is not None}
    expected["state-new"] = record["rows"][-1]["new"]
    actual = {row.name.split("/", 1)[1] for row in rows
              if row.name.startswith(active + "/")}
    if actual != set(expected):
        raise RuntimeError("Unexpected or missing active Fatekeeper backup membership.")
    for name, digest in expected.items():
        data, mode = tx._read(destination.journal_dir / active / name)
        if mode != 0o600 or tx._digest(data) != digest:
            raise RuntimeError("Previous Fatekeeper backup verification failed; maintenance blocked.")
    histories = verify_history(destination, active_backup=active)
    retained = {h.backup for h in histories}
    for row in rows:
        if "/" in row.name:
            continue
        if row.kind in {"lock", "journal-candidate", "active-backup-candidate", "history-candidate"}:
            continue
        if row.kind == "orphan-backup-candidate" and row.name in retained:
            continue
        raise RuntimeError("Unresolved production recovery evidence; manual review required.")
    if inventory(destination.journal_dir, active_backup=active) != rows:
        raise RuntimeError("Recovery artifact inventory changed during maintenance verification.")
