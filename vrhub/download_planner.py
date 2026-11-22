# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A local archive inventory, pinned hash verification and download locations.

No network calls, archive extraction, download, mod installation or game writes.
Archive matches based on filename alone are NEVER described as verified.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from . import hub, self_install

MAX_DIRS = 300
MAX_FILES = 1800
MAX_CANDIDATES = 16
MAX_HASH_BYTES = 3 * 1024 * 1024 * 1024
GAME_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
EXTS = (".zip", ".rar", ".7z", ".pak", ".tar.gz")
_HASH_MEMO = {}


@dataclass(frozen=True)
class InventoryFile:
    path: Path
    size: int


def _rid(recipe_or_id):
    rid = recipe_or_id.get("id") if isinstance(recipe_or_id, dict) else recipe_or_id
    if not isinstance(rid, str) or not GAME_ID.fullmatch(rid):
        raise ValueError("Invalid game profile identifier")
    return rid


def preferences_file() -> Path:
    return hub.state_file().parent / "download-folders.json"


def _checked_directory(value, *, must_exist=False) -> Path:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError("Folder location must be an absolute normal filesystem path.")
    path = Path(value).expanduser()
    if not path.is_absolute() or str(path) == "/":
        raise ValueError("Select an absolute folder, not the entire filesystem.")
    if must_exist and not path.is_dir():
        raise ValueError("The selected download folder does not exist.")
    return path


def _empty_prefs():
    return {"schema": 1, "global": None, "games": {}}


def load_preferences() -> dict:
    location = preferences_file()
    if not location.exists() and not location.is_symlink():
        return _empty_prefs()
    if location.is_symlink() or not location.is_file() or location.stat().st_size > 64_000:
        raise RuntimeError("Download preferences need manual review; existing file preserved.")
    try:
        data = json.loads(location.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or set(data) != {"schema", "global", "games"}
                or data["schema"] != 1 or type(data["games"]) is not dict
                or len(data["games"]) > 128):
            raise ValueError("invalid preference structure")
        if data["global"] is not None:
            _checked_directory(data["global"])
        for rid, path in data["games"].items():
            _rid(rid)
            _checked_directory(path)
        return data
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        raise RuntimeError("Download preferences need manual review; existing file preserved.") from exc


def set_location(scope: str, path: str | None, rid: str | None = None):
    if scope not in ("global", "game"):
        raise ValueError("Unknown download location scope.")
    if scope == "game":
        rid = _rid(rid)
    resolved = str(_checked_directory(path, must_exist=True).resolve()) if path else None
    dest = preferences_file()
    dest.parent.mkdir(parents=True, exist_ok=True)
    lockpath = dest.with_name(dest.name + ".lock")
    fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prefs = load_preferences()
        if scope == "global":
            prefs["global"] = resolved
        elif resolved:
            prefs["games"][rid] = resolved
        else:
            prefs["games"].pop(rid, None)
        self_install._atomic(dest, (json.dumps(prefs, indent=2) + "\n").encode("utf-8"))


def default_library() -> Path:
    organized = Path.home() / "Downloads/Organized/Archive-Library/VR-Mods"
    return organized if organized.is_dir() else Path.home() / "Downloads"


def folder_for(recipe: dict, prefs: dict | None = None) -> tuple[Path, str]:
    rid = _rid(recipe)
    prefs = load_preferences() if prefs is None else prefs
    selected = prefs["games"].get(rid)
    if selected:
        return Path(selected), "Per-game override"
    if prefs["global"]:
        return Path(prefs["global"]), "Global preference"
    return default_library(), "Auto-discovered archive library"


def source_url(value):
    if not isinstance(value, str):
        return ""
    p = urlparse(value)
    return value if p.scheme == "https" and p.hostname and not p.username and not p.password else ""


def _inventory(folder: Path, *, progress=None) -> tuple[list[InventoryFile], str | None]:
    """Inspect up to two subdirectory levels, no symlink directory traversal."""
    if not folder.is_dir():
        return [], "Selected folder is unavailable; choose an existing folder."
    files = []
    queued = [(folder, 0)]
    dirs = 0
    while queued:
        directory, level = queued.pop(0)
        dirs += 1
        if dirs > MAX_DIRS or len(files) >= MAX_FILES:
            return files, "Inventory limit reached; choose a more specific download folder."
        try:
            paths = sorted(directory.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for entry in paths:
            try:
                info = entry.lstat()
            except OSError:
                continue
            if stat.S_ISDIR(info.st_mode):
                if level < 2:
                    queued.append((entry, level + 1))
            elif stat.S_ISREG(info.st_mode) and entry.name.lower().endswith(EXTS):
                if info.st_size > 0:
                    files.append(InventoryFile(entry, info.st_size))
                if len(files) >= MAX_FILES:
                    return files, "Inventory limit reached; choose a more specific download folder."
        if progress:
            progress(min(dirs, MAX_DIRS), MAX_DIRS)
    return files, None


def archive_identity(path: Path):
    """Identity of a regular archive, refusing symlink replacement."""
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or path.resolve() != path:
            return None
        return {"size": st.st_size, "mtime_ns": st.st_mtime_ns,
                "ctime_ns": st.st_ctime_ns, "ino": st.st_ino, "dev": st.st_dev}
    except (OSError, RuntimeError):
        return None


def _pinned_hash(file: InventoryFile, *, remaining: list[int]) -> str | None:
    """Bounded digest of a stable regular file; never trust name or mtime alone."""
    identity = archive_identity(file.path)
    if not identity or identity["size"] != file.size or file.size > remaining[0]:
        return None
    key = (str(file.path), tuple(identity.values()))
    if key in _HASH_MEMO:
        return _HASH_MEMO[key]
    remaining[0] -= file.size
    h = hashlib.sha256()
    try:
        fd = os.open(file.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or (
                    st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino, st.st_dev
                    ) != tuple(identity.values()):
                return None
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
                if stream.tell() > file.size:
                    return None
            if stream.tell() != file.size:
                return None
        if archive_identity(file.path) != identity:
            return None
    except OSError:
        return None
    digest = h.hexdigest()
    if len(_HASH_MEMO) >= 1500:
        _HASH_MEMO.clear()
    _HASH_MEMO[key] = digest
    return digest


def _recognize_candidates(files, catalog, remaining):
    """Choose by official asset identity, then suggest by mtime; dedupe bytes."""
    if len(files) > MAX_CANDIDATES:
        return [], False, True
    expected = catalog.get("expected", "")
    options = []
    for file in files:
        ident = archive_identity(file.path)
        if not ident:
            continue
        digest = _pinned_hash(file, remaining=remaining)
        if archive_identity(file.path) != ident:
            continue
        tags = [a["tag"] for a in catalog.get("assets", [])
                if digest and a["sha256"] == digest and a["size"] == file.size]
        options.append({"file": str(file.path), "identity": ident,
                        "sha256": digest or "", "tags": tags,
                        "expected": bool(expected and expected in tags)})
    rank = {a["tag"]: a["when"] for a in catalog.get("assets", [])}
    options.sort(key=lambda c: (c["expected"], bool(c["tags"]),
                              max((rank[t] for t in c["tags"]), default=0),
                              c["identity"]["mtime_ns"], c["file"]), reverse=True)
    groups = {}
    for option in options:
        key = option["sha256"] or option["file"]
        groups.setdefault(key, []).append(option)
    # Only byte-identical duplicates merge. The representative is newest
    # modified, never inferred to be a newer release from its filename.
    unique = [dict(items[0], copies=len(items)) for items in groups.values()]
    # Only the displayed representative may be reused. Other copies remain
    # untouched. When no unique expected digest exists, ask for consent.
    ambiguous = len(unique) > 1 and sum(c["expected"] for c in unique) != 1
    return unique, ambiguous, len(options) != len(files)


def plan_components(recipe: dict):
    """A plan is descriptive only; phases remain separate and nothing runs."""
    rid = _rid(recipe)
    base = source_url(recipe.get("mod_page", ""))
    method = recipe.get("method", "file")
    if recipe.get("components"):
        return [{
            "id": str(x["nexus_mod"]), "name": x["name"],
            "phase": int(x.get("phase", 1)),
            "sha256": None,
            "url": source_url(f"https://www.nexusmods.com/{recipe['nexus_game']}/mods/{x['nexus_mod']}")
                   if recipe.get("nexus_game") else base,
            "hint": str(x["nexus_mod"]),
        } for x in recipe["components"]]
    if recipe.get("packages"):
        return [{
            "id": str(x["id"]), "name": str(x["name"]),
            "phase": 1, "sha256": str(x.get("sha256", "")).lower() or None,
            "url": source_url(x.get("page")) or base,
            "hint": str(x["id"]),
        } for x in recipe["packages"]]
    if method == "uevr":
        return [
            {"id": "uevr", "name": "Matching UEVR injector package", "phase": 1,
             "sha256": None, "url": base, "hint": ("uevr_fk" if rid == "fatekeeper" else "uevr")},
            {"id": "profile", "name": "Matching game profile", "phase": 1,
             "sha256": None, "url": source_url(recipe.get("profile", {}).get("page")) or base,
             "hint": "slasher" if rid == "fatekeeper" else "hogwartslegacy"},
        ]
    if method == "guide":
        return [{"id": "guide", "name": "Follow existing guided setup instructions",
                 "phase": 1, "sha256": None, "url": base, "hint": ""}]
    mods = [u for u in recipe.get("updates", [])
            if isinstance(u.get("nexus_mod"), int)]
    return [{"id": str(u["nexus_mod"]), "name": u["name"], "phase": 1,
             "sha256": None, "url": base,
             "hint": str(u["nexus_mod"])} for u in mods] or [
        {"id": "manual", "name": "Review mod download from source",
         "phase": 1, "sha256": None, "url": base, "hint": ""}]


def _candidate_filename_match(name: str, component: dict, rid: str) -> bool:
    lower = name.casefold()
    hint = component["hint"].casefold()
    if not hint:
        return False
    if hint.isdecimal():
        # Nexus convention: suffix/between separators, no partial mod ID.
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(hint) + r"(?![a-z0-9])", lower))
    if hint == "loader":
        return "bepinex" in lower or "tobey" in lower
    if hint == "vhvr":
        return "vhvr" in lower
    if hint == "submersedvr":
        return "submersed" in lower
    if hint == "ervr":
        return "ervr" in lower
    if hint == "uevr":
        return "uevr" in lower and "fk" not in lower and "profile" not in lower
    if hint == "uevr_fk":
        return "uevr_fk" in lower
    if hint == "slasher":
        return "slasher" in lower
    if hint == "hogwartslegacy":
        return "hogwartslegacy" in lower
    return len(hint) >= 4 and hint in lower


def build_plan(recipe: dict, folder: Path, *, progress=None, release_catalogs=None, release_errors=None) -> dict:
    """Return a bounded read-only snapshot of locally available candidates."""
    rid = _rid(recipe)
    entries, warning = _inventory(folder, progress=progress)
    comps = plan_components(recipe)
    remaining = [MAX_HASH_BYTES]
    needs_hash = any(x.get("sha256") for x in comps)
    digest_map = {}
    # Pinned package recipes can identify renamed ZIP files *only* by digest.
    # No unpinned candidate is labelled verified.
    if needs_hash:
        for i, entry in enumerate(entries):
            if entry.path.name.casefold().endswith((".zip", ".7z", ".rar")):
                digest_map[str(entry.path)] = _pinned_hash(entry, remaining=remaining)
            if progress and i % 10 == 0:
                progress(min(i + 1, len(entries)), max(1, len(entries)))
    rows = []
    release_catalogs = release_catalogs or {}
    release_errors = release_errors or {}
    for c in comps:
        verified = ([f for f in entries
                     if digest_map.get(str(f.path)) == c["sha256"]]
                    if c.get("sha256") else [])
        plausible = [
            f for f in entries
            if f not in verified and _candidate_filename_match(f.path.name, c, rid)]
        # For pinned recipes a matching filename with incorrect hash is NOT
        # a usable archive. It must be explicitly rejected.
        if verified:
            status, selection = "Pinned SHA-256 verified", verified[0]
        elif plausible and c.get("sha256"):
            selection = plausible[0]
            status = ("Hash not verified — do not install"
                      if digest_map.get(str(selection.path)) is None
                      else "Hash mismatch — do not install")
        elif plausible:
            status, selection = "Possible archive — inspect first", plausible[0]
        else:
            status, selection = "Not found locally", None
        extra = {}
        if plausible and not c.get("sha256"):
            catalog = release_catalogs.get(c["id"], {})
            # Hash only multiple candidates or explicitly recognized assets.
            if len(plausible) > 1 or c["id"] in recipe.get("archive_releases", {}):
                options, ambiguous, incomplete = _recognize_candidates(plausible, catalog, remaining)
                extra = {"candidates": options, "ambiguous": ambiguous,
                         "candidate_incomplete": bool(incomplete or warning), "release_expected": catalog.get("expected", ""),
                         "release_fixed": bool(catalog.get("fixed")),
                         "release_notice": release_errors.get(c["id"], "")}
                if options:
                    selection = next(f for f in plausible if str(f.path) == options[0]["file"])
                else:
                    selection = None
        elif c["id"] in recipe.get("archive_releases", {}):
            catalog = release_catalogs.get(c["id"], {})
            extra = {"release_expected": catalog.get("expected", ""),
                     "release_fixed": bool(catalog.get("fixed")),
                     "release_notice": release_errors.get(c["id"], "")}
        rows.append({**c, **extra, "status": status,
                     "file": str(selection.path) if selection else "",
                     "matches": len(verified) + len(plausible),
                     "size": selection.size if selection else 0,
                     "phase_label": "Later: install after first flat launch" if c["phase"] > 1
                                    else "Stage 1: prerequisites"})
    return {"game_id": rid, "folder": str(folder), "rows": rows,
            "scanned": len(entries), "warning": warning,
            "verified": sum(x["status"] == "Pinned SHA-256 verified" for x in rows),
            "possible": sum(x["status"] == "Possible archive — inspect first" for x in rows),
            "mismatch": sum(x["status"] == "Hash mismatch — do not install" for x in rows),
            "unverified": sum(x["status"] == "Hash not verified — do not install" for x in rows),
            "missing": sum(x["status"] == "Not found locally" for x in rows)}
