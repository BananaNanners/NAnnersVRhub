# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Local folder preferences only: never select a target or store save contents."""
import fcntl
import json
import os
from pathlib import Path
from . import hub, self_install

LIMIT = 8


def preferences_file():
    return hub.state_file().parent / 'development-save-locations.json'


def _load():
    path = preferences_file()
    if not path.exists() and not path.is_symlink():
        return {'schema': 1, 'games': {}}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
        raise RuntimeError('Remembered save folders need review: invalid preferences file.')
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('games'), dict) or len(data['games']) > 128:
            raise ValueError('Invalid preference structure')
        for rid, entry in data['games'].items():
            if not isinstance(rid, str) or not isinstance(entry, dict) or set(entry) != {'sources', 'targets'}:
                raise ValueError('Invalid game entry')
            for paths in entry.values():
                if not isinstance(paths, list) or len(paths) > LIMIT:
                    raise ValueError('Invalid folder list')
                if any(not isinstance(p, str) or len(p) > 4096 or not Path(p).is_absolute() or any(ord(c) < 32 for c in p) for p in paths):
                    raise ValueError('Invalid folder path')
        return data
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RuntimeError('Remembered save folders need review: unreadable preferences. Existing preferences were not replaced.') from exc


def load(rid):
    entry = _load()['games'].get(rid, {'sources': [], 'targets': []})
    return {key: list(paths) for key, paths in entry.items()}


def _update(rid, role=None, path=None):
    dest = preferences_file()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(dest) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load()
        if role is None:
            data['games'].pop(rid, None)
        else:
            if role not in {'sources', 'targets'}:
                raise ValueError('Unknown remembered-folder role')
            if not isinstance(path, str) or len(path) > 4096 or not Path(path).is_absolute() or any(ord(c) < 32 for c in path):
                raise ValueError('Invalid folder path')
            entry = data['games'].setdefault(rid, {'sources': [], 'targets': []})
            entry[role] = ([p for p in entry[role] if p != path] + [path])[-LIMIT:]
        self_install._atomic(dest, (json.dumps(data, indent=2) + '\n').encode())


def remember(rid, role, path):
    _update(rid, role, path)


def forget(rid):
    _update(rid)
