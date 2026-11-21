# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C read-only installation manifest, conflict and backup safety gates.

The planner never installs or writes to a game/prefix. Existing, validated
installers retain ownership of real installs, backups, and rollback. Review
fingerprints must be revalidated immediately before a user-authorized install.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import bepinex, hub, pak

MAX_ARCHIVES = 15
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ZIP_ENTRIES = 2500
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_UNPACKED_BYTES = 512 * 1024 * 1024
MAX_DESTINATIONS = 2500
MAX_EXISTING_HASH_BYTES = 512 * 1024 * 1024


class PlanRejected(RuntimeError):
    """The archive cannot be safely reviewed; no game files were touched."""


@dataclass(frozen=True)
class Target:
    relative: str
    path: str
    action: str
    current_bytes: int
    current_sha256: str | None
    current_mtime_ns: int | None
    current_ino: int | None
    current_device: int | None


@dataclass(frozen=True)
class InstallPlan:
    game_id: str
    game_name: str
    method: str
    game_root: str
    archives: tuple[str, ...]
    archive_sha256: tuple[str, ...]
    package_labels: tuple[str, ...]
    target_rows: tuple[Target, ...]
    new_files: int
    overwrites: int
    backup_bytes: int
    backup_policy: str
    blocked: tuple[str, ...]
    notes: tuple[str, ...]
    fingerprint: str

    @property
    def approved_for_review(self) -> bool:
        return not self.blocked and bool(self.target_rows)


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _archive(path: Path, game_base: Path) -> tuple[Path, str]:
    if path.is_symlink() or not path.is_file():
        raise PlanRejected(f"Not a regular archive file: {path}")
    p = path.resolve(strict=True)
    if p.is_relative_to(game_base):
        raise PlanRejected("Archives inside the live game directory are not accepted.")
    if p.stat().st_size == 0 or p.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PlanRejected(f"{p.name} is empty or exceeds the 512 MiB planning limit.")
    return p, _hash(p)


def _zip_preflight(path: Path):
    """Bounded ZIP metadata validation before the legacy staging function."""
    if path.suffix.casefold() != ".zip":
        raise PlanRejected("The guided game-root planner currently requires a ZIP archive.")
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            raise PlanRejected("Archive contains too many entries to review safely.")
        total = 0
        seen = set()
        for item in entries:
            if item.flag_bits & 1:
                raise PlanRejected(f"Encrypted archive entry: {item.filename}")
            norm = item.filename.replace(chr(92), "/")
            parts = norm.rstrip("/").split("/")
            if (norm.startswith("/") or ":" in norm or
                    any(p in {"", ".", ".."} for p in parts)):
                raise PlanRejected(f"Unsafe ZIP path: {item.filename}")
            mode = stat.S_IFMT(item.external_attr >> 16)
            if mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise PlanRejected(f"Unsupported ZIP entry type: {item.filename}")
            if item.is_dir() or norm.endswith("/"):
                continue
            key = norm.casefold()
            if key in seen:
                raise PlanRejected(f"Case-insensitive duplicate ZIP path: {norm}")
            seen.add(key)
            if item.file_size > MAX_FILE_BYTES:
                raise PlanRejected(f"Archive entry too large: {norm}")
            total += item.file_size
            if total > MAX_UNPACKED_BYTES:
                raise PlanRejected("Archive expands beyond the 512 MiB review limit.")


def _target(base: Path, relative: str) -> Path:
    # Stronger-than-legacy target handling: reject symlink ancestors,
    # different-case twins, directory destinations, and path traversal.
    if len(relative) > 4096:
        raise PlanRejected("Unreasonably long destination path.")
    try:
        p = bepinex.target(base, relative)
    except (RuntimeError, ValueError) as exc:
        raise PlanRejected(str(exc)) from exc
    if not p.resolve().is_relative_to(base):
        raise PlanRejected(f"Target leaves game directory: {p}")
    return p


def _target_row(base: Path, relative: str, *, max_existing: int) -> Target:
    dest = _target(base, relative)
    if dest.is_symlink():
        raise PlanRejected(f"Target is a symbolic link: {relative}")
    if dest.exists():
        if not dest.is_file():
            raise PlanRejected(f"Install target is not a regular file: {relative}")
        st = dest.stat()
        if st.st_size > max_existing:
            raise PlanRejected(
                f"Cannot safely back up oversized existing file: {relative}")
        return Target(relative, str(dest), "Replace; back up original",
                      st.st_size, _hash(dest), st.st_mtime_ns, st.st_ino, st.st_dev)
    return Target(relative, str(dest), "Add new file", 0, None, None, None, None)


def _archive_group(files, base):
    if not isinstance(files, (tuple, list)) or not 1 <= len(files) <= MAX_ARCHIVES:
        raise PlanRejected("Select one to fifteen archive files.")
    paths = []
    seen = set()
    hashes = []
    for file in files:
        p, sha = _archive(Path(file), base)
        if p in seen:
            raise PlanRejected("The same archive was selected twice.")
        seen.add(p)
        paths.append(p)
        hashes.append(sha)
    return tuple(paths), tuple(hashes)


def _pinned_package_plan(recipe, files, base):
    cfg = bepinex.policy(recipe)
    if not (base / cfg["exe"]).is_file() or not (base / cfg["data"]).is_dir():
        raise PlanRejected(
            "Launch the Windows game with Proton once and confirm its EXE/data folder.")
    if hub._load_state().get(recipe["id"]):
        raise PlanRejected(
            "The Hub already has an installation inventory. Remove/review it "
            "with the existing rollback workflow before replacing anything.")
    conflicts = bepinex.conflicts(base, recipe)
    if conflicts:
        raise PlanRejected(
            "Existing conflicting VR plugins require manual review: " +
            ", ".join(str(p) for p in conflicts[:8]))
    packs = []
    for f in files:
        package, members = bepinex.archive_plan(f, recipe)
        packs.append((package, members, f))
    wanted = {p["id"] for p in recipe["packages"]}
    found = [p["id"] for p, _, _ in packs]
    if len(packs) != len(wanted) or set(found) != wanted or len(set(found)) != len(found):
        raise PlanRejected(
            "Select every required pinned package together. " +
            ", ".join(p["name"] for p in recipe["packages"]))
    order = {p["id"]: i for i, p in enumerate(recipe["packages"])}
    packs.sort(key=lambda item: order[item[0]["id"]])
    names = [name for _pkg, members, _file in packs for name in members.values()]
    if len(names) > MAX_DESTINATIONS or len(names) != len({n.casefold() for n in names}):
        raise PlanRejected("Packages contain overlapping or excessive destination files.")
    rows = tuple(_target_row(base, name, max_existing=bepinex.MAX_FILE)
                 for name in names)
    retired = []
    for rel in cfg["retired"]:
        old = _target(base, rel)
        if old.exists():
            if not old.is_dir() or any(x.is_symlink() for x in old.rglob("*")):
                raise PlanRejected(f"Old plugin directory needs manual review: {rel}")
            retired.append(rel)
    notes = [
        "Both pinned package digests and required files validated against the recipe.",
        "Original files are backed up and retained for the existing installer rollback.",
        "Restoring or removing mods must still use the Hub's recorded inventory.",
    ]
    if retired:
        notes.append(
            "Existing retired plugin directories moved into a retained backup: "
            + ", ".join(retired))
    return rows, tuple(p["name"] for p, _, _ in packs), (
        "Persistent, Hub-managed original-file backups"), (), tuple(notes)


def _pak_plan(recipe, files, base):
    if len(files) != 1:
        raise PlanRejected("This game installs exactly one PAK archive at a time.")
    rule = recipe.get("files", [{}])[0]
    if rule.get("kind") != "pak":
        raise PlanRejected("This game has no reviewed PAK installation rule.")
    if hub._load_state().get(recipe["id"]):
        raise PlanRejected(
            "A PAK install is already recorded. Review/restore its existing backup first.")
    folder = _target(base, rule["dest"])
    if not folder.is_dir() or folder.is_symlink():
        raise PlanRejected("Required game PAK folder does not exist or is unsafe.")
    archive = files[0]
    if archive.suffix.casefold() == ".pak":
        names = [archive.name]
    elif archive.suffix.casefold() == ".zip":
        _zip_preflight(archive)
        with zipfile.ZipFile(archive) as z:
            names = [item.filename.replace(chr(92), "/").rsplit("/", 1)[-1]
                     for item in z.infolist() if not item.is_dir()
                     and item.filename.lower().endswith(".pak")]
    else:
        raise PlanRejected("This game accepts only .pak or .zip archive files.")
    if not names or len(names) > MAX_DESTINATIONS or len(names) != len({
            n.casefold() for n in names}):
        raise PlanRejected("No valid, unique PAK payload files found.")
    rows = []
    for name in names:
        try:
            pak._target(folder, name)
        except RuntimeError as exc:
            raise PlanRejected(str(exc)) from exc
        rel = str(Path(rule["dest"]) / name)
        rows.append(_target_row(base, rel, max_existing=MAX_EXISTING_HASH_BYTES))
    notes = (
        "PAK package has no recipe-pinned hash; this is a manual user-selected archive.",
        "The existing transactional PAK installer retains original-file backups.",
    )
    return tuple(rows), (archive.name,), (
        "Persistent, Hub-managed original PAK backups"), (), notes


def _game_root_plan(recipe, files, base):
    if recipe.get("method") != "gameroot":
        raise PlanRejected("Unsupported game-root install method.")
    comps = recipe.get("components", [])
    mapped = {}
    for archive in files:
        _zip_preflight(archive)
        component = hub._component_for(recipe, archive.name) if comps else None
        if comps and not component:
            raise PlanRejected(
                f"{archive.name}: cannot identify a unique recipe component by its Nexus ID.")
        key = str(component["nexus_mod"]) if component else archive.name
        if key in mapped:
            raise PlanRejected(f"Duplicate component archive: {key}")
        mapped[key] = (component, archive)
    index = {str(c["nexus_mod"]): i for i,c in enumerate(comps)}
    ordered = sorted(mapped.values(),
                     key=lambda item: index.get(str(item[0]["nexus_mod"]), 999)
                     if item[0] else 999)
    rows = []
    packages = []
    blocked = []
    notes = ["The existing game-root installer restores temporary backups after failure.",
             "It does not retain originals after success. Existing destinations are blocked."]
    with tempfile.TemporaryDirectory(prefix="nannersvrhub-install-review-") as tmp:
        for i, (comp, archive) in enumerate(ordered):
            if comp and int(comp.get("phase", 1)) > 1:
                blocked.append(
                    f"{comp['name']} is a later-stage mod. First flat launch "
                    "must be confirmed in its dedicated setup procedure.")
            stage = Path(tmp) / str(i)
            stage.mkdir()
            rels = hub._stage_archive(archive, stage)
            mappings = hub._plan_gameroot(rels, archive.name, recipe.get("root_dirs"))
            hub._validate_component_plan(comp, mappings, archive.name)
            packages.append(comp["name"] if comp else archive.name)
            for _, dest in mappings:
                rows.append(_target_row(base, str(dest), max_existing=MAX_EXISTING_HASH_BYTES))
    if not rows or len(rows) > MAX_DESTINATIONS or len({r.relative.casefold() for r in rows}) != len(rows):
        raise PlanRejected("No destinations or overlapping destinations; install blocked.")
    if any(r.current_sha256 is not None for r in rows):
        blocked.append(
            "One or more existing game files would be replaced, but this "
            "installer does not retain their backups after success. "
            "Installation remains blocked until a supported backup policy exists.")
    return tuple(rows), tuple(packages), (
        "Failure-only rollback; existing-file replacement is BLOCKED"), tuple(blocked), tuple(notes)


def _storage_check(backup_bytes):
    # A backup estimate is read-only; do not create any directory or reserve
    # space. The actual installer will perform its own backups transactionally.
    directory = hub.state_file().parent
    while not directory.exists() and directory != directory.parent:
        directory = directory.parent
    try:
        free = shutil.disk_usage(directory).free
    except OSError:
        return "Cannot determine backup disk space; review manually."
    # Require a 32 MiB margin in addition to exact existing-original bytes.
    if free < backup_bytes + 32 * 1024 * 1024:
        return "Insufficient free space for originals and a safety margin."
    return None


def _seal(recipe, base, files, hashes, packages, rows, backup_policy, blocked, notes):
    snapshot = {
        "id": recipe["id"],
        "method": recipe.get("method", "file"),
        "base": str(base), "archives": [str(f) for f in files],
        "archive_hashes": hashes, "packages": packages,
        "targets": [r.__dict__ for r in rows],
        "backup_policy": backup_policy, "blocked": blocked,
        "notes": notes,
    }
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_install_plan(recipe: dict, archives, steam_roots=None) -> InstallPlan:
    """Inspect the *exact* selected archive files and live targets, read-only."""
    if not recipe or "id" not in recipe or "name" not in recipe:
        raise PlanRejected("Select a valid game profile.")
    method = recipe.get("method", "file")
    if method not in {"bepinex", "ervr", "gameroot"} and not (
            recipe.get("files") and recipe["files"][0].get("kind") == "pak"):
        raise PlanRejected(
            "Guided installation review is not yet supported for this "
            "UEVR/guide-only profile. Follow its existing manual setup guide.")
    base = hub.game_path(recipe, steam_roots)
    if not base or base.is_symlink() or not base.is_dir():
        raise PlanRejected("Game installation not found, or target directory is a symlink.")
    base = base.resolve()
    files, hashes = _archive_group(archives, base)
    try:
        if method in {"bepinex", "ervr"}:
            rows, labels, backup_policy, blockers, notes = _pinned_package_plan(
                recipe, files, base)
        elif method == "gameroot":
            rows, labels, backup_policy, blockers, notes = _game_root_plan(
                recipe, files, base)
        else:
            rows, labels, backup_policy, blockers, notes = _pak_plan(
                recipe, files, base)
    except (RuntimeError, ValueError, OSError, zipfile.BadZipFile,
            zipfile.LargeZipFile) as exc:
        if isinstance(exc, PlanRejected):
            raise
        raise PlanRejected(str(exc)) from exc
    blocked = list(blockers)
    backup_bytes = sum(t.current_bytes for t in rows if t.current_sha256 is not None)
    if method in {"bepinex", "ervr"} or backup_policy.startswith("Persistent"):
        storage_issue = _storage_check(backup_bytes)
        if storage_issue:
            blocked.append(storage_issue)
    new_count = sum(t.current_sha256 is None for t in rows)
    overwritten = len(rows) - new_count
    seal = _seal(recipe, base, files, hashes, labels, rows, backup_policy, blocked, notes)
    return InstallPlan(
        recipe["id"], recipe["name"], method, str(base),
        tuple(str(f) for f in files), hashes, labels, rows, new_count,
        overwritten, backup_bytes, backup_policy, tuple(blocked),
        tuple(notes), seal)


def revalidate(plan: InstallPlan, recipe: dict, steam_roots=None) -> InstallPlan:
    """Fail closed if an archive, target or recipe has changed after review."""
    if recipe["id"] != plan.game_id:
        raise PlanRejected("Selected game changed; installation review must restart.")
    fresh = build_install_plan(recipe, plan.archives, steam_roots)
    if fresh.fingerprint != plan.fingerprint or not fresh.approved_for_review:
        raise PlanRejected(
            "Files, destinations, selected archives or installation rules "
            "changed after review. No installation started; review again.")
    return fresh


def human_file_size(size_bytes: int) -> str:
    """Friendly decimal units for the UI only; safety math stays in bytes.

    MB = 1,000,000 bytes; GB = 1,000,000,000 bytes.
    """
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError("File size must be a non-negative integer")
    for unit, scale in (("GB", 1_000_000_000), ("MB", 1_000_000),
                        ("KB", 1_000)):
        if size_bytes >= scale:
            number = f"{size_bytes / scale:.2f}".rstrip("0").rstrip(".")
            return f"{number} {unit}"
    return f"{size_bytes} B"


def summary(plan: InstallPlan) -> str:
    state = "BLOCKED" if plan.blocked else "READY FOR EXPLICIT CONFIRMATION"
    lines = [
        f"Game: {plan.game_name}", f"Status: {state}",
        f"Game folder: {plan.game_root}",
        f"Packages: {', '.join(plan.package_labels)}",
        f"New files: {plan.new_files}",
        f"Existing files to replace: {plan.overwrites}",
        f"Original backup size estimate: {human_file_size(plan.backup_bytes)}",
        f"Backup policy: {plan.backup_policy}",
    ]
    if plan.blocked:
        lines += ["", "Install blocked:"] + [f"- {r}" for r in plan.blocked]
    lines += ["", "Notes:"] + [f"- {r}" for r in plan.notes]
    return "\n".join(lines)
