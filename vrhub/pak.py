# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""PAK installation with persistent originals and failure rollback."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import time
import uuid
import zipfile


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def _locked():
    from . import hub
    from . import state_transaction
    with state_transaction.locked(hub.state_file()):
        path = hub.state_file().parent / "pak-install.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield


def _target(directory, name):
    if (not name or name in {".", ".."} or "/" in name or "\\" in name
            or Path(name).suffix.lower() != ".pak"):
        raise RuntimeError("Invalid PAK inventory filename.")
    path = directory / name
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise RuntimeError(f"PAK target must not be a symlink or leave its directory: {path}")
    if path.exists() and not path.is_file():
        raise RuntimeError(f"PAK target is not a regular file: {path}")
    return path


def _restore(paths, snapshots):
    errors = []
    for name, original in snapshots.items():
        try:
            if original is None:
                paths[name].unlink(missing_ok=True)
            else:
                shutil.copy2(original, paths[name])
        except OSError as exc:
            errors.append(f"{paths[name]}: {exc}")
    return errors


def install(recipe, archive, game):
    from . import hub
    with _locked():
        state = hub._load_state()
        if recipe["id"] in state:
            raise RuntimeError("A mod install is already recorded. Uninstall it before replacing the PAK files so its backups are preserved.")
        base = game.resolve()
        directory = (base / recipe["files"][0]["dest"]).resolve()
        if not directory.is_relative_to(base) or not directory.is_dir():
            raise RuntimeError(f"Game PAK directory is missing or outside the game: {directory}")
        backup = hub.state_file().parent / "backups" / (recipe["id"] + "-pak-" + uuid.uuid4().hex)
        stage = backup / "new"
        stage.mkdir(parents=True)
        paths, originals, written = {}, {}, {}
        preserve = False
        try:
            if archive.suffix.lower() == ".zip":
                with zipfile.ZipFile(archive) as z:
                    members = [(info, info.filename.replace("\\", "/").rsplit("/", 1)[-1])
                               for info in z.infolist() if not info.is_dir()
                               and info.filename.lower().endswith(".pak")]
                    if not members:
                        raise RuntimeError(f"No .pak file found inside {archive.name}")
                    if len({name.casefold() for _, name in members}) != len(members):
                        raise RuntimeError("The archive contains duplicate PAK basenames.")
                    for info, name in members:
                        paths[name] = _target(directory, name)
                        with z.open(info) as src, (stage / name).open("xb") as out:
                            shutil.copyfileobj(src, out)
            elif archive.suffix.lower() == ".pak":
                paths[archive.name] = _target(directory, archive.name)
                shutil.copy2(archive, stage / archive.name)
            else:
                raise RuntimeError(f"Expected a .pak or .zip file, got: {archive.name}")

            for name, path in paths.items():
                originals[name] = None
                if path.exists():
                    saved = backup / "files" / name
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, saved)
                    originals[name] = saved
            original_hashes = {n: _digest(p) for n, p in originals.items() if p is not None}
            hashes = {n: _digest(stage / n) for n in paths}
            for name, path in paths.items():
                written[name] = originals[name]  # Also roll back a partially written file.
                shutil.copy2(stage / name, path)
            state[recipe["id"]] = {"installer": "pak-1", "files": [str(p) for p in paths.values()],
                                   "pak_dir": str(directory), "keep": str(base),
                                   "backup": str(backup.resolve()), "file_hashes": hashes,
                                   "original_hashes": original_hashes, "installed_at": int(time.time())}
            hub._save_state(state)
            preserve = True  # Originals survive the commit for a future uninstall.
        except Exception as exc:
            errors = _restore(paths, written)
            if errors:
                preserve = True
                raise RuntimeError(f"PAK installation failed and rollback was incomplete. Recovery files preserved at {backup}: "
                                   + "; ".join(errors)) from exc
            raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            if not preserve:
                shutil.rmtree(backup, ignore_errors=True)
        return list(paths.values())


def uninstall(recipe_id):
    from . import hub
    with _locked():
        state = hub._load_state()
        entry = state[recipe_id]
        directory, base = Path(entry["pak_dir"]), Path(entry["keep"])
        backup = Path(entry["backup"])
        if (entry.get("installer") != "pak-1" or not directory.is_dir() or directory.is_symlink()
                or not directory.resolve().is_relative_to(base.resolve())
                or backup.is_symlink() or not backup.is_dir()
                or backup.resolve().parent != (hub.state_file().parent / "backups").resolve()):
            raise RuntimeError("PAK installation/backup directory cannot be verified; nothing was removed.")
        hashes, originals = entry["file_hashes"], entry["original_hashes"]
        paths = {name: _target(directory, name) for name in hashes}
        if not paths or set(entry["files"]) != {str(p) for p in paths.values()} or set(originals) - paths.keys():
            raise RuntimeError("PAK inventory is inconsistent; nothing was removed.")
        for name, expected in hashes.items():
            if paths[name].exists() and _digest(paths[name]) != expected:
                raise RuntimeError(f"PAK changed since installation; preserve/review it before removal: {paths[name]}")
        for name, expected in originals.items():
            saved = _target(backup / "files", name)
            if not saved.is_file() or _digest(saved) != expected:
                raise RuntimeError("An original PAK backup is missing or changed; nothing was removed.")

        recovery = backup / ("uninstall-" + uuid.uuid4().hex)
        recovery.mkdir()
        snapshots, changed = {}, {}
        preserve = False
        try:
            # Snapshot every current PAK before touching any of them.
            for name, path in paths.items():
                snapshots[name] = None
                if path.exists():
                    shutil.copy2(path, recovery / name)
                    snapshots[name] = recovery / name
            for name, path in paths.items():
                changed[name] = snapshots[name]
                if name in originals:
                    shutil.copy2(backup / "files" / name, path)
                else:
                    path.unlink(missing_ok=True)
            del state[recipe_id]
            hub._save_state(state)
        except Exception as exc:
            errors = _restore(paths, changed)
            if errors:
                preserve = True
                raise RuntimeError(f"PAK removal rollback was incomplete. Recovery files preserved at {recovery}: "
                                   + "; ".join(errors)) from exc
            raise
        finally:
            if not preserve:
                shutil.rmtree(recovery, ignore_errors=True)
        return list(paths.values())
