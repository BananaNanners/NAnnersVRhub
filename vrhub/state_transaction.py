# SPDX-License-Identifier: GPL-3.0-only
"""Shared cooperative lock for Hub installation records and their transactions."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
from threading import local

_local = local()


@contextmanager
def locked(state_path):
    """Serialize writers across processes; allow same-thread nested dispatch.

    Do not unlink lock files. Fail promptly on competing operations rather
    than blocking the desktop. Every participant must use this protocol.
    """
    path = Path(state_path).absolute()
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("Unsafe Hub state path.")
    directory = path.parent.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ("." + path.name + ".transaction.lock")
    held = getattr(_local, "held", None)
    if held is None:
        held = _local.held = set()
    key = (os.getpid(), lock)
    if key in held:
        yield
        return
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise RuntimeError("Unsafe Hub transaction lock.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Hub installation or state operation is active. Retry after it finishes.") from exc
        held.add(key)
        try:
            yield
        finally:
            held.remove(key)
    finally:
        os.close(fd)
