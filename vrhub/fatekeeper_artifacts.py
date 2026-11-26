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
