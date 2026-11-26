# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Persistent, isolated development *preview* data across source worktrees.

This helper is called ONLY by the development preview entry point. It never
redirects the released Hub's storage or grants permission to install mods.
Existing per-version scan files are read, validated and merged once into a
stable private preview directory. Sources are never moved or removed.
"""
from __future__ import annotations

import json
import fcntl
import os
import tempfile
import stat
from datetime import datetime, timezone
from pathlib import Path

from . import archive_scans, download_planner

SHARED_FOLDER = ".local/share/nannersvrhub-development-preview"
LEGACY_GLOB = "nannersvrhub-055-dev*-state-*"
STATE_MAX_BYTES = 4 * 1024 * 1024
COLUMN_MAX_BYTES = 64 * 1024
PREF_MAX_BYTES = 64 * 1024


class PreviewStorageError(RuntimeError):
    """Preview bootstrap failed closed; source records remain untouched."""


def shared_directory(home: Path | None = None) -> Path:
    return (home or Path.home()) / SHARED_FOLDER


def discover_previous(home: Path | None = None) -> list[Path]:
    root = (home or Path.home()) / ".cache"
    # Only explicit Dev0.5.5 private previews; not Steam, Heroic or released
    # ~/.local/share/vrhub/state.json.
    return sorted(
        (d for d in root.glob(LEGACY_GLOB)
         if d.is_dir() and not d.is_symlink()),
        key=lambda d: d.name)


def _regular_bytes(path: Path, max_size: int) -> bytes | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        raise PreviewStorageError(f"Refusing symlinked preview data: {path}")
    try:
        st = path.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > max_size:
            raise PreviewStorageError(f"Unexpected preview data file size/type: {path}")
        return path.read_bytes()
    except OSError as exc:
        raise PreviewStorageError(f"Could not read preview data {path}: {exc}") from exc


def _atomic_new(path: Path, contents: bytes, maximum: int):
    if len(contents) > maximum:
        raise PreviewStorageError(f"Preview data exceeds allowed size: {path.name}")
    if path.exists() or path.is_symlink():
        raise PreviewStorageError(f"Refusing to replace existing preview file: {path}")
    # Stage completely before atomically linking a new file into place.
    # The hard link fails if another preview process already created it.
    fd, temp = tempfile.mkstemp(prefix=".preview-migrate-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise PreviewStorageError(
                f"Preview data was created concurrently: {path}") from exc
    finally:
        Path(temp).unlink(missing_ok=True)


def _read_scans(path: Path) -> dict:
    raw = _regular_bytes(path, archive_scans.MAX_SNAPSHOT_BYTES)
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
        if (not isinstance(parsed, dict)
                or set(parsed) != {"schema", "games"}
                or parsed["schema"] not in (1, 2)
                or not isinstance(parsed["games"], dict)
                or len(parsed["games"]) > archive_scans.MAX_GAMES):
            raise ValueError("Invalid scan file schema")
        records = {}
        for rid, entry in parsed["games"].items():
            if parsed["schema"] == 2:
                if not isinstance(entry, list) or not 1 <= len(entry) <= archive_scans.MAX_SCANS_PER_GAME:
                    raise ValueError("Invalid scan history")
                for rec in entry:
                    archive_scans._validate_record(rid, rec)
                records[rid] = entry[0]
            else:
                records[rid] = archive_scans._validate_record(rid, entry)
        return records
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PreviewStorageError(f"Cannot migrate invalid scan file {path}: {exc}") from exc


def _read_folders(path: Path) -> dict | None:
    raw = _regular_bytes(path, PREF_MAX_BYTES)
    if raw is None:
        return None
    try:
        prefs = json.loads(raw)
        if (not isinstance(prefs, dict)
                or set(prefs) != {"schema", "global", "games"}
                or prefs["schema"] != 1 or not isinstance(prefs["games"], dict)
                or len(prefs["games"]) > 128):
            raise ValueError("Invalid archive-folder preferences")
        if prefs["global"] is not None:
            download_planner._checked_directory(prefs["global"])
        for rid, folder in prefs["games"].items():
            download_planner._rid(rid)
            download_planner._checked_directory(folder)
        return prefs
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise PreviewStorageError(f"Invalid saved folder preferences {path}: {exc}") from exc


def _timestamp(record: dict) -> datetime:
    stamp = datetime.fromisoformat(record["scanned_at"])
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp


def _best_scans(records: dict[str, list[dict]], prefs: dict) -> dict:
    """Prefer the chosen game's archive folder, then the newest valid scan."""
    merged = {}
    for rid, candidates in records.items():
        folder, _ = download_planner.folder_for({"id": rid}, prefs=prefs)
        matching = [rec for rec in candidates if rec["folder"] == str(folder)]
        # Preserve even out-of-folder historical records, but don't claim
        # they're current. The UI checks effective folder before showing one.
        selections = matching or candidates
        merged[rid] = max(selections, key=_timestamp)
    return merged


def prepare_shared_preview(home: Path | None = None, *,
                           previous_state: Path | None = None,
                           source_roots: list[Path] | None = None) -> dict:
    """Create/reuse stable dev-preview storage and migrate legacy scans once.

    Never copies state from production unless the caller explicitly supplies
    a separate existing private source. No writes occur to legacy directories.
    """
    home = (home or Path.home()).resolve()
    stable = shared_directory(home)
    production = home / ".local/share/vrhub/state.json"
    sources = (source_roots if source_roots is not None
               else discover_previous(home))
    sources = [Path(s) for s in sources
               if Path(s).is_dir() and not Path(s).is_symlink()]
    if stable.is_symlink():
        raise PreviewStorageError("Stable preview directory is a symlink; refusing it.")
    stable.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stable.resolve() == production.parent.resolve():
        raise PreviewStorageError("Preview must not share the released Hub data folder.")
    for dirname in ("config", "cache", "data"):
        dirpath = stable / dirname
        if dirpath.is_symlink():
            raise PreviewStorageError(f"Unsafe preview settings directory: {dirpath}")
        dirpath.mkdir(mode=0o700, exist_ok=True)
    os.chmod(stable, 0o700)

    state = stable / "state.json"
    if _regular_bytes(state, STATE_MAX_BYTES) is None:
        options = []
        if previous_state:
            prev = Path(previous_state).expanduser()
            if prev.resolve() != production.resolve() and prev.parent in sources:
                options.append(prev)
        options.extend(p / "state.json" for p in reversed(sources))
        chosen = next(((candidate, raw) for candidate in options
                       if (raw := _regular_bytes(candidate, STATE_MAX_BYTES))
                       is not None), None)
        if chosen is None:
            raise PreviewStorageError("No previous private Hub preview state to preserve.")
        _atomic_new(state, chosen[1], STATE_MAX_BYTES)

    # Existing shared folder choice wins; otherwise restore the latest
    # manually configured development preference. No source is rewritten.
    folders = stable / "download-folders.json"
    prefs = _read_folders(folders)
    if prefs is None:
        prior = [(p / "download-folders.json",
                  _read_folders(p / "download-folders.json")) for p in sources]
        configured = [(path, obj) for path, obj in prior if obj is not None]
        if configured:
            latest_path, prefs = max(configured,
                                     key=lambda item: item[0].stat().st_mtime_ns)
            _atomic_new(folders, _regular_bytes(latest_path, PREF_MAX_BYTES), PREF_MAX_BYTES)
        else:
            prefs = download_planner._empty_prefs()

    # The scan migration happens only when there isn't already a shared
    # snapshot. Future scans from this same shared location must win.
    target = stable / "archive-scan-snapshots.json"
    saved = _read_scans(target)
    imported = False
    if not target.exists() and not target.is_symlink():
        collected: dict[str, list[dict]] = {}
        for src in sources:
            data = _read_scans(src / "archive-scan-snapshots.json")
            for rid, rec in data.items():
                collected.setdefault(rid, []).append(rec)
        if collected:
            saved = _best_scans(collected, prefs)
            raw = (json.dumps({"schema": 1, "games": saved},
                              separators=(",", ":")) + "\n").encode()
            _atomic_new(target, raw, archive_scans.MAX_SNAPSHOT_BYTES)
            imported = True

    columns = stable / "table-column-layouts.json"
    if not columns.exists() and not columns.is_symlink():
        candidates = [
            p / "table-column-layouts.json" for p in sources
            if (p / "table-column-layouts.json").is_file()
        ]
        if candidates:
            recent = max(candidates, key=lambda p: p.stat().st_mtime_ns)
            raw = _regular_bytes(recent, COLUMN_MAX_BYTES)
            # Only migrate known schema after validating it structurally.
            try:
                obj = json.loads(raw)
                if (not isinstance(obj, dict) or obj.get("schema") != 1
                        or not isinstance(obj.get("tables"), dict)):
                    raise ValueError("Unsupported column layout")
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                raise PreviewStorageError(f"Cannot preserve column widths: {exc}") from exc
            _atomic_new(columns, raw, COLUMN_MAX_BYTES)

    return {
        "root": stable,
        "state": state,
        "scans": saved,
        "imported": imported,
        "count": len(saved),
        "source_count": len(sources),
    }


# All desktop entry points using shared storage participate in the same
# lifetime lock, including older launchers in this worktree.
_desktop_locks = {}


def acquire_desktop_preview_lock(home: Path | None = None):
    path = (home or Path.home()) / ".cache/nannersvrhub-preview-lifecycle.lock"
    path = path.absolute()
    if path in _desktop_locks:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise PreviewStorageError("Unsafe development preview lock.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PreviewStorageError("A development preview is already running.") from None
    except BaseException:
        os.close(fd)
        raise
    _desktop_locks[path] = fd


def activate_desktop_preview(*, home: Path | None = None):
    """Point only this explicitly invoked dev preview at the shared store."""
    acquire_desktop_preview_lock(home)
    prior_state = os.environ.get("VRHUB_STATE")
    result = prepare_shared_preview(
        home, previous_state=Path(prior_state) if prior_state else None)
    # Discovery and game-launch subprocesses must retain host XDG paths.
    # Repeated activation must never capture the redirected preview paths.
    from . import launch_environment
    launch_environment.capture_host_xdg()
    stable = result["root"]
    # Desktop previews may read the existing private host credential, but
    # must never direct credential writes at the host configuration.
    # Use captured host XDG on every activation, not the redirected value.
    host_config = launch_environment.host_config_home()
    host_key = (Path(host_config).expanduser() if host_config else
                (home or Path.home()) / ".config") / "vrhub" / "nexus_key"
    os.environ["VRHUB_NEXUS_READONLY_KEY_FILE"] = str(host_key)
    os.environ["VRHUB_NEXUS_KEY_FILE"] = str(stable / "config/vrhub/nexus_key")
    os.environ["VRHUB_STATE"] = str(result["state"])
    for key, sub in (("XDG_CONFIG_HOME", "config"),
                     ("XDG_CACHE_HOME", "cache"),
                     ("XDG_DATA_HOME", "data")):
        os.environ[key] = str(stable / sub)
    return result
