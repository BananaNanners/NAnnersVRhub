"""Pinned Windows VR packages with transactional game-file backups."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import uuid
import zipfile

from . import self_install

MARKER = "submersed-vr-1"
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
ROOT_FILES = {".doorstop_version", "changelog.txt", "doorstop_config.ini", "winhttp.dll", "steam_appid.txt"}
OTHER_PLATFORM = {"libdoorstop.dylib", "run_bepinex.sh"}
CONFLICTS = {"vrenhancements.dll", "sn1mc.dll"}
POLICIES = {
    "subnautica": {"title": "Subnautica", "exe": "Subnautica.exe", "data": "Subnautica_Data",
                   "marker": MARKER, "retired": ["BepInEx/patchers/Tobey"]},
    "valheim": {"title": "Valheim", "exe": "valheim.exe", "data": "valheim_Data",
                "marker": "vhvr-1", "retired": []},
    "elden-ring": {"title": "Elden Ring", "exe": "Game/eldenring.exe", "data": "Game",
                   "marker": "ervr-1", "retired": []},
}
ERVR_FILES = {"Game/" + name for name in ("dxgi.dll", "dinput8.dll", "ReShade.ini", "LICENSE-ReShade.txt",
    "ERVR/ERVR.dll", "ERVR/ERVR.ini", "ERVR/README.md", "ERVR/CHANGELOG.md", "ERVR/LICENSE.txt", "ERVR/THIRD_PARTY.md")}


def policy(recipe):
    rid = recipe["id"] if isinstance(recipe, dict) else recipe
    if rid not in POLICIES:
        raise RuntimeError("Unsupported pinned VR package game.")
    return POLICIES[rid]



def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _ervr_residue(path):
    """An empty/log-only directory left by removal is not an installed mod."""
    if path.name != "ERVR" or path.is_symlink() or not path.is_dir():
        return False
    return all(p.name == "ERVR.log" and not p.is_symlink() and p.is_file()
               for p in path.iterdir())


def conflicts(game, recipe=None):
    if recipe and recipe["id"] == "elden-ring":
        from . import hub
        folder = game / "Game"
        if not folder.is_dir():
            return []
        entry = hub.state().get("elden-ring", {})
        owned = set(entry.get("files", [])) if entry.get("installer") == "ervr-1" and entry.get("keep") == str(game.resolve()) else set()
        blocked = {"dxgi.dll", "dinput8.dll", "reshade.ini", "ervr", "realrepo", "realrepo_", "realvr64.dll", "realvr.ini", "openvr_api.dll", "cudart64_12.dll"}
        return [p for p in folder.iterdir() if p.name.casefold() in blocked
                and not (str(p) in owned or p.name == "ERVR" and str(p / "ERVR.dll") in owned
                         or _ervr_residue(p))]
    plugins = game / "BepInEx/plugins"
    if not plugins.is_dir():
        return []
    if recipe and recipe["id"] == "valheim":
        return [p for p in plugins.rglob("*") if p.name.casefold() == "valheimvrmod.dll"
                and p != plugins / "ValheimVRMod.dll"]
    return [p for p in plugins.rglob("*") if p.name.casefold() in CONFLICTS]


def target(base, relative):
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts or ":" in relative or "\\" in relative:
        raise RuntimeError("Unsafe VR mod installation path.")
    path = base / p
    for item in (path, *path.parents):
        if item == base:
            break
        if item.is_symlink():
            raise RuntimeError(f"VR mod target is a symlink: {path}. Review it manually.")
    # Refuse differently-cased twins before creating differently-cased game/mod folders.
    parent = base
    for part in p.parts:
        if parent.is_dir() and any(c.name.casefold() == part.casefold() and c.name != part for c in parent.iterdir()):
            raise RuntimeError(f"VR mod path has a case collision: {path}. Review the existing mod layout.")
        parent /= part
    return path


def payload_path(name, recipe_id="subnautica"):
    if recipe_id == "elden-ring":
        return name in ERVR_FILES
    p = PurePosixPath(name)
    return name in ROOT_FILES or len(p.parts) > 1 and p.parts[0] in {"BepInEx", policy(recipe_id)["data"]}


def inventory(archive, recipe):
    package, plan = archive_plan(archive, recipe)
    return package, list(plan.values())


def archive_plan(archive, recipe):
    if not archive.is_file() or archive.suffix.lower() != ".zip" or archive.stat().st_size > MAX_TOTAL:
        raise RuntimeError("Choose the downloaded pinned VR release ZIP(s).")
    sha = digest(archive)
    matches = [p for p in recipe["packages"] if p["sha256"] == sha]
    if len(matches) != 1:
        raise RuntimeError(f"{archive.name}: not a recognized pinned VR mod release ZIP. Download the exact version(s) linked in the guide; renamed files are accepted, modified or newer archives need recipe review.")
    package = matches[0]
    members, seen, total = {}, set(), 0
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) > 1000:
            raise RuntimeError("VR mod archive contains too many entries.")
        for item in z.infolist():
            origin = item.filename
            name = origin.replace("\\", "/") if recipe["id"] == "elden-ring" else origin
            p = PurePosixPath(name)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (name.startswith("/") or "\\" in name or ":" in name or
                    any(part in {"", ".", ".."} for part in name.rstrip("/").split("/")) or
                    mode not in {0, stat.S_IFREG, stat.S_IFDIR} or item.flag_bits & 1):
                raise RuntimeError(f"Unsafe VR mod archive path: {name}")
            if item.is_dir():
                continue
            key = name.casefold()
            if key in seen:
                raise RuntimeError(f"Duplicate VR mod archive path: {name}")
            seen.add(key)
            total += item.file_size
            if item.file_size > MAX_FILE or total > MAX_TOTAL:
                raise RuntimeError("VR mod archive exceeds extraction limits.")
            dest = name
            if recipe["id"] == "elden-ring":
                dest = "Game/" + name
            elif recipe["id"] == "valheim":
                if package["id"] == "loader":
                    if name in {"CHANGELOG.md", "README.md", "icon.png", "manifest.json"}:
                        continue
                    prefix = "BepInExPack_Valheim/"
                    if not name.startswith(prefix):
                        raise RuntimeError(f"Unexpected Valheim loader payload: {name}")
                    dest = name[len(prefix):]
                    if dest in {"start_game_bepinex.sh", "start_server_bepinex.sh"} or dest.startswith("doorstop_libs/"):
                        continue
                elif name.startswith("Valheim_Data/"):
                    dest = "valheim_Data/" + name[len("Valheim_Data/"):]
            elif name in OTHER_PLATFORM:
                continue
            if not payload_path(dest, recipe["id"]):
                raise RuntimeError(f"Unexpected VR mod payload path: {name}")
            if dest.casefold() in {n.casefold() for n in members.values()}:
                raise RuntimeError(f"Duplicate VR mod target path: {dest}")
            members[origin] = dest
    missing = set(package["required_files"]) - set(members.values())
    if missing:
        raise RuntimeError("Incomplete VR mod archive: " + ", ".join(sorted(missing)))
    return package, members


@contextmanager
def locked():
    from . import hub
    path = hub.state_file().parent / "bepinex-install.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _save(state):
    from . import hub
    self_install._atomic(hub.state_file(), (json.dumps(state, indent=2) + "\n").encode())


def install(recipe, archives, steam_roots=None):
    from . import hub
    cfg = policy(recipe)
    with locked():
        state = hub._load_state()
        if recipe["id"] in state:
            raise RuntimeError("A VR mod Hub install is already recorded. Remove it first to restore its backups before replacing it.")
        game = hub.game_path(recipe, steam_roots)
        if not game or not (game / cfg["exe"]).is_file() or not (game / cfg["data"]).is_dir():
            raise RuntimeError(f"Launch the Windows Steam copy of {cfg['title']} once with Proton; {cfg['exe']} and {cfg['data']} must be present.")
        base = game.resolve()
        bad = conflicts(base, recipe)
        if bad:
            raise RuntimeError("Remove the conflicting or duplicate VR plugin using its existing installer before continuing: incompatible install at " + ", ".join(str(p) for p in bad))
        packs = [(*archive_plan(Path(p), recipe), Path(p)) for p in archives]
        if len(packs) != len(recipe["packages"]) or {p[0]["id"] for p in packs} != {p["id"] for p in recipe["packages"]}:
            instruction = "Select the pinned release ZIP: " if recipe["id"] == "elden-ring" else "Select BOTH release ZIPs together: "
            raise RuntimeError(instruction + " and ".join(p["name"] for p in recipe["packages"]) + ". No files were installed.")
        order = {p["id"]: i for i, p in enumerate(recipe["packages"])}
        packs.sort(key=lambda p: order[p[0]["id"]])
        names = [name for _p, members, _a in packs for name in members.values()]
        if len({name.casefold() for name in names}) != len(names):
            raise RuntimeError("The two VR mod packages overlap unexpectedly.")
        paths = {name: target(base, name) for name in names}
        for path in paths.values():
            if path.exists() and (not path.is_file() or path.stat().st_size > MAX_FILE):
                raise RuntimeError(f"Cannot back up VR mod target safely: {path}")
        for name in cfg["retired"]:
            old = target(base, name)
            if old.exists() and (not old.is_dir() or any(p.is_symlink() for p in old.rglob("*"))):
                raise RuntimeError(f"Review the old {name} layout manually before installation.")
        backup = hub.state_file().parent / "backups" / (recipe["id"] + "-" + uuid.uuid4().hex)
        backup.mkdir(parents=True)
        originals, retired, written = [], [], []
        original_hashes = {}
        try:
            # Keep these original files after commit, for explicit removal.
            for name, path in paths.items():
                if path.exists():
                    copy = backup / "files" / name
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, copy)
                    originals.append(name)
                    original_hashes[name] = digest(copy)
            for name in cfg["retired"]:
                old = base / name
                if old.is_dir():
                    dest = backup / "retired" / name
                    dest.parent.mkdir(parents=True)
                    shutil.move(str(old), str(dest))
                    retired.append(name)
            with tempfile.TemporaryDirectory(prefix="bepinex-stage-") as temp:
                stage = Path(temp)
                for _p, members, archive in packs:
                    with zipfile.ZipFile(archive) as z:
                        for origin, name in members.items():
                            p = stage / name
                            p.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(origin) as src, p.open("wb") as out:
                                shutil.copyfileobj(src, out)
                hashes = {name: digest(stage / name) for name in names}
                for name, path in paths.items():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    written.append(name)
                    shutil.copy2(stage / name, path)
            now = int(time.time())
            state[recipe["id"]] = {"installer": cfg["marker"], "files": [str(paths[n]) for n in names],
                "keep": str(base), "backup": str(backup.resolve()), "originals": originals,
                "retired": retired, "original_hashes": original_hashes, "file_hashes": hashes, "installed_at": now,
                "packages": {p["id"]: {"archive": a.name, "sha256": p["sha256"],
                    "files": [str(paths[n]) for n in members.values()], "installed_at": now} for p, members, a in packs}}
            _save(state)
        except Exception:
            for name in reversed(written):
                path = paths[name]
                if name in originals:
                    shutil.copyfile(backup / "files" / name, path)
                else:
                    path.unlink(missing_ok=True)
            for name in retired:
                shutil.move(str(backup / "retired" / name), str(base / name))
            raise
        return list(paths.values())


def uninstall(recipe_id):
    from . import hub
    cfg = policy(recipe_id)
    with locked():
        state = hub._load_state()
        entry = state[recipe_id]
        if entry.get("installer") != cfg["marker"]:
            raise RuntimeError("The VR mod installer inventory cannot be verified; nothing was removed.")
        base = Path(entry["keep"])
        backup = Path(entry["backup"])
        expected = (hub.state_file().parent / "backups").resolve()
        if backup.is_symlink() or backup.resolve().parent != expected or not base.is_dir() or base.is_symlink():
            raise RuntimeError("VR mod backup/game directory cannot be verified; installation was preserved.")
        hashes = entry["file_hashes"]
        if not hashes or any(not payload_path(name, recipe_id) for name in hashes):
            raise RuntimeError("VR mod inventory paths cannot be verified; installation was preserved.")
        paths = {name: target(base, name) for name in hashes}
        if set(entry["files"]) != {str(p) for p in paths.values()}:
            raise RuntimeError("VR mod inventory is inconsistent; installation was preserved.")
        originals, retired = entry["originals"], entry["retired"]
        if any(name not in cfg["retired"] for name in retired):
            raise RuntimeError("VR mod retired-folder inventory cannot be verified; installation was preserved.")
        for name in originals:
            if name not in paths or not target(backup, "files/" + name).is_file():
                raise RuntimeError("A required VR mod original backup is missing; nothing was removed.")
            if digest(backup / "files" / name) != entry.get("original_hashes", {}).get(name):
                raise RuntimeError("A VR mod original backup changed; nothing was removed.")
        for name in retired:
            if target(base, name).exists() or not target(backup, "retired/" + name).is_dir():
                raise RuntimeError("The old Tobey patcher folder cannot be restored safely; nothing was removed.")
        changed = [name for name, path in paths.items() if path.exists() and (not path.is_file() or digest(path) != hashes[name])]
        mutable = [name for name in changed if paths[name].is_file() and paths[name].stat().st_size <= MAX_FILE
                   and Path(name).suffix.lower() in {".cfg", ".ini", ".json", ".txt"}]
        blocked = [name for name in changed if name not in mutable]
        if blocked:
            raise RuntimeError("VR mod binary files changed since installation. Preserve/review them before removal; nothing was removed: " + ", ".join(blocked))
        # Keep user/runtime edits to settings, while protecting changed game DLLs.
        for name in mutable:
            saved = target(backup, "user-modified/" + name)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths[name], saved)
        snapshots = {name: p.read_bytes() if p.is_file() else None for name, p in paths.items()}
        restored = []
        try:
            for name, path in paths.items():
                if name in originals:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup / "files" / name, path)
                else:
                    path.unlink(missing_ok=True)
            for name in retired:
                shutil.copytree(backup / "retired" / name, base / name)
                restored.append(name)
            del state[recipe_id]
            _save(state)
        except Exception:
            for name in restored:
                shutil.rmtree(base / name)
            for name, data in snapshots.items():
                if data is None:
                    paths[name].unlink(missing_ok=True)
                else:
                    paths[name].write_bytes(data)
            raise
        return list(paths.values())


def verify(recipe, steam_roots=None, *, game=None):
    from . import hub
    if steam_roots is None:
        steam_roots = [Path(p).expanduser() for p in os.environ.get("VRHUB_STEAM_ROOTS", "").split(":") if p] or None
    game = game if game is not None else hub.game_path(recipe, steam_roots)
    entry = hub.state().get(recipe["id"], {})
    rows = []
    for i, package in enumerate(recipe["packages"], 1):
        records = entry.get("packages", {})
        record = records.get(package["id"]) if isinstance(records, dict) else None
        status, detail = "missing", "No Hub package inventory recorded."
        if isinstance(record, dict) and game:
            files = record.get("files", [])
            if not isinstance(files, list) or any(not isinstance(p, str) for p in files):
                files = []
            valid = entry.get("installer") == policy(recipe)["marker"] and Path(entry.get("keep", "")).resolve() == game.resolve()
            gone = [p for p in files if not Path(p).is_file() or not Path(p).resolve().is_relative_to(game.resolve())]
            required = [n for n in package["required_files"] if str(game / n) not in files or not (game / n).is_file()]
            ok = valid and bool(files) and not gone and not required and record.get("sha256") == package["sha256"]
            status = "ok" if ok else "damaged"
            detail = (f"All {len(files)} recorded files present; archive digest matched at install; loading/current file versions unverified."
                      if ok else "Package files/inventory are missing or do not match this Steam installation; review before reinstalling.")
        rows.append({"n": i, "id": package["id"], "name": package["name"], "phase": 1,
                     "status": status, "detail": detail, "page": package["page"]})
    bad = [r for r in rows if r["status"] != "ok"]
    return {"rows": rows, "ready": not bad, "required_bad": bad, "later_bad": [],
            "ok": len(rows) - len(bad), "total": len(rows)}
