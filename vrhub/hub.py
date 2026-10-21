"""NAnnersVRhub core: recipes, install/uninstall bookkeeping, UEVR + profile handling."""
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import time
import tomllib
import zipfile
from pathlib import Path

from . import runtime, updates
from .paths import guard_path
from .handlers import get_handler
from .schema import RecipeError, validate_recipe
from .steam import find_game

HUB_DIR = Path(__file__).resolve().parent.parent
RECIPE_DIR = Path(__file__).resolve().parent / "recipes"
APPDATA = Path("drive_c/users/steamuser/AppData")


def log_file() -> Path:
    return state_file().parent / "vrhub.log"


def _log(event: str, **data) -> None:
    """Append one small JSON event to the local hub log. Never log secrets."""
    try:
        p = log_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        record = {"time": int(time.time()), "event": event, **data}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass  # diagnostics must never break an install


def _zip_members(z: zipfile.ZipFile) -> dict[str, str]:
    """Return original->normalized regular-file names for ZIPs from either OS.

    Some Windows-created archives use backslashes even for directory entries.
    Normalize first, then decide whether the member is a directory. Duplicate
    normalized file names are rejected instead of silently overwriting each other.
    """
    members: dict[str, str] = {}
    seen: set[str] = set()
    for info in z.infolist():
        orig = info.filename
        norm = orig.replace("\\", "/")
        if info.is_dir() or norm.endswith("/"):
            continue
        if norm in seen:
            raise RuntimeError(f"Archive contains the same path more than once: {norm}")
        seen.add(norm)
        members[orig] = norm
    return members


def state_file() -> Path:
    return Path(os.environ.get("VRHUB_STATE", "~/.local/share/vrhub/state.json")).expanduser()




def game_path(recipe: dict, steam_roots=None) -> Path | None:
    """Resolve a recipe's install folder through its owning storefront."""
    if recipe.get("store", "steam") == "steam":
        return find_game(recipe["steam_appid"], steam_roots)
    handler = get_handler(recipe)
    finder = getattr(handler, "game_path", None)
    return finder(recipe) if finder else None

def load_recipes() -> dict[str, dict]:
    out = {}
    for f in sorted(RECIPE_DIR.glob("*.toml")):
        try:
            r = tomllib.loads(f.read_text())
        except tomllib.TOMLDecodeError as e:
            raise RecipeError(f"{f.name}: invalid TOML: {e}") from e
        validate_recipe(r, f.name)
        if r["id"] in out:
            raise RecipeError(f"{f.name}: duplicate recipe id '{r['id']}'")
        out[r["id"]] = r
    if 'doom-2016-gog' in out:
        from . import kharvox_bridge
        kharvox_bridge.require_binaries()
    return out


def _load_state() -> dict:
    f = state_file()
    return json.loads(f.read_text()) if f.is_file() else {}


def _save_state(s: dict) -> None:
    f = state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s, indent=2))


def is_installed(recipe_id: str) -> bool:
    return recipe_id in _load_state()


def profile_installed(recipe_id: str) -> bool:
    return f"{recipe_id}:profile" in _load_state()


def _extract(z: zipfile.ZipFile, anchor: str, base: Path) -> list[Path]:
    """Extract everything at/below the folder that holds `anchor` (shallowest match),
    stripping any wrapper folder. Validates all paths before writing anything."""
    base = base.resolve()
    names = _zip_members(z)
    hits = sorted((n for n in names.values() if n.rsplit("/", 1)[-1] == anchor), key=len)
    if not hits:
        raise RuntimeError(f"No {anchor} found anywhere in that zip.")
    prefix = hits[0][: -len(anchor)]  # "" or e.g. "SomeFolder/"
    targets = {orig: (base / norm[len(prefix):]).resolve()
               for orig, norm in names.items() if norm.startswith(prefix)}
    for orig, t in targets.items():
        if not t.is_relative_to(base):
            raise RuntimeError(f"Unsafe path inside zip: {orig}")
    written = []
    for orig, t in targets.items():
        t.parent.mkdir(parents=True, exist_ok=True)
        with z.open(orig) as src, open(t, "wb") as out:
            shutil.copyfileobj(src, out)
        written.append(t)
    return written


def _pfx(recipe: dict, steam_roots=None) -> Path:
    if recipe.get("store") == "heroic-epic" or recipe.get("handler") == "kharvox-gog":
        return get_handler(recipe).prefix(recipe)
    game = find_game(recipe["steam_appid"], steam_roots)
    if not game:
        raise RuntimeError(f"{recipe['name']}: not found in any Steam library.")
    pfx = game.parents[1] / "compatdata" / str(recipe["steam_appid"]) / "pfx"
    if not pfx.is_dir():
        raise RuntimeError("Proton prefix not found. Launch the game once from Steam "
                           "(with Proton enabled) so it gets created, then try again.")
    return pfx


def _uevr_dir(recipe: dict, steam_roots=None) -> Path:
    prefix = _pfx(recipe, steam_roots)
    target = prefix / "drive_c" / "uevr"
    if not target.resolve().is_relative_to(prefix.resolve()):
        raise RuntimeError("UEVR folder resolves outside this game's prefix; installation was stopped.")
    return target


def profile_dir(recipe: dict, steam_roots=None) -> Path:
    prefix = _pfx(recipe, steam_roots)
    data = get_handler(recipe).appdata(recipe) if recipe.get("store") == "heroic-epic" else prefix / APPDATA
    target = data / recipe["profile"]["dir"]
    if not target.resolve().is_relative_to(prefix.resolve()):
        raise RuntimeError("The VR profile resolves outside this game's prefix; installation was stopped.")
    return target


def install(recipe: dict, mod_file: Path, steam_roots=None) -> list[Path]:
    """Install a mod from a .pak file, or from a .zip containing one (or a UEVR zip)."""
    if not get_handler(recipe).install_supported(recipe):
        raise RuntimeError(f"{recipe['name']} is a guided workflow; it has no direct mod-file install step.")
    game = game_path(recipe, steam_roots)
    if not game:
        raise RuntimeError(f"{recipe['name']}: game installation was not found. Review its setup guide and storefront settings.")
    if not mod_file.is_file():
        raise RuntimeError(f"File not found: {mod_file}")
    if recipe.get("method") == "uevr":
        return _install_uevr(recipe, mod_file, steam_roots)
    if recipe.get("method") == "gameroot":
        return _install_gameroot(recipe, [mod_file], steam_roots)
    if recipe.get("method") in {"bepinex", "ervr"}:
        from . import bepinex
        return bepinex.install(recipe, [mod_file], steam_roots)
    rule = recipe["files"][0]
    ext = f".{rule['kind']}"
    dest_dir = game / rule["dest"]
    if not dest_dir.is_dir():
        raise RuntimeError(f"Game folder layout unexpected, missing: {dest_dir}")

    written: list[Path] = []
    if mod_file.suffix.lower() == ".zip":
        with zipfile.ZipFile(mod_file) as z:
            members = [m for m in z.namelist() if m.lower().endswith(ext)]
            if not members:
                raise RuntimeError(f"No {ext} file found inside {mod_file.name}")
            for m in members:
                dest = dest_dir / Path(m).name  # basename only: no path tricks
                with z.open(m) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
                written.append(dest)
    elif mod_file.suffix.lower() == ext:
        dest = dest_dir / mod_file.name
        shutil.copy2(mod_file, dest)
        written.append(dest)
    else:
        raise RuntimeError(f"Expected a {ext} or .zip file, got: {mod_file.name}")

    state = _load_state()
    state[recipe["id"]] = {"files": [str(w) for w in written], "installed_at": int(time.time())}
    _save_state(state)
    return written


def _install_uevr(recipe: dict, mod_file: Path, steam_roots=None) -> list[Path]:
    """Unpack a UEVR zip into the game's Proton prefix (drive_c/uevr)."""
    if mod_file.suffix.lower() != ".zip":
        raise RuntimeError("Expected a UEVR .zip file.")
    dest = _uevr_dir(recipe, steam_roots)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(mod_file) as z:
        written = _extract(z, "UEVRInjector.exe", dest)
    state = _load_state()
    state[recipe["id"]] = {"files": [str(w) for w in written], "root": str(dest.resolve()),
                           "installed_at": int(time.time())}
    _save_state(state)
    return written


ROOT_DIRS = {"bin", "r6", "red4ext", "archive", "engine", "mods"}  # folders a Cyberpunk mod may write to


def _stage_archive(archive: Path, stage: Path) -> list[Path]:
    """Unpack .zip (built in) or .7z/.rar (via bsdtar) into `stage`; return the regular files found."""
    if archive.suffix.lower() == ".zip":
        base = stage.resolve()
        with zipfile.ZipFile(archive) as z:
            members = _zip_members(z)
            targets = {n: (base / norm).resolve() for n, norm in members.items()}
            for n, t in targets.items():  # validate everything before writing anything
                if not t.is_relative_to(base):
                    raise RuntimeError(f"Unsafe path inside {archive.name}: {n}")
            for n, t in targets.items():
                t.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(t, "wb") as out:
                    shutil.copyfileobj(src, out)
    else:
        tool = shutil.which("bsdtar")
        if not tool:
            raise RuntimeError(f"{archive.name}: opening .7z/.rar files needs bsdtar "
                               "(sudo pacman -S libarchive), or extract it to a .zip yourself.")
        r = subprocess.run([tool, "-xf", str(archive), "-C", str(stage)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"Couldn't open {archive.name}: {r.stderr.strip()[:200]}")
    files = []
    for dirpath, _dirs, names in os.walk(stage, followlinks=False):
        for n in names:
            p = Path(dirpath) / n
            if not p.is_symlink():
                files.append(p.relative_to(stage))
    return files


def _plan_gameroot(rels: list[Path], label: str, root_dirs=None) -> list[tuple[Path, Path]]:
    """Map archive files to game-folder paths. Strips one wrapper folder, fixes the case of the
    top-level folder (Linux is case-sensitive), and ignores readmes/anything outside ROOT_DIRS."""
    roots = {x.lower() for x in (root_dirs or ROOT_DIRS)}
    def is_root(part: str) -> bool:
        return part.lower() in roots
    strip = 0
    if not any(len(r.parts) > 1 and is_root(r.parts[0]) for r in rels):
        tops = {r.parts[0] for r in rels if len(r.parts) > 1}
        if len(tops) == 1 and any(len(r.parts) > 2 and is_root(r.parts[1]) for r in rels):
            strip = 1
        else:
            expected = " / ".join(sorted(roots))
            raise RuntimeError(f"{label} doesn't look like a supported game-root archive "
                               f"(none of these folders were found: {expected}).")
    plan = []
    for r in rels:
        parts = r.parts[strip:]
        if len(parts) >= 2 and is_root(parts[0]):
            plan.append((r, Path(parts[0].lower(), *parts[1:])))
    return plan


def _component_for(recipe: dict, filename: str) -> dict | None:
    """Nexus file names carry the mod number ('Cyber Engine Tweaks-107-1-37-1-1759….zip')."""
    ids = {str(c["nexus_mod"]): c for c in recipe.get("components", [])}
    hits = [ids[t] for t in re.split(r"[^0-9A-Za-z]+", filename) if t in ids]
    return hits[0] if len({h["nexus_mod"] for h in hits}) == 1 else None


def _component_required_files(comp: dict) -> list[Path]:
    return [Path(p.replace("\\", "/")) for p in comp.get("required_files", [])]


def _validate_component_plan(comp: dict | None, plan: list[tuple[Path, Path]], archive_name: str) -> None:
    if not plan:
        raise RuntimeError(f"{archive_name}: no installable game files were found.")
    if not comp:
        return
    required = _component_required_files(comp)
    if not required:
        return
    destinations = {str(dest).replace("\\", "/").lower() for _src, dest in plan}
    missing = [str(p) for p in required if str(p).replace("\\", "/").lower() not in destinations]
    if missing:
        raise RuntimeError(
            f"{archive_name}: this doesn't look like the complete {comp['name']} archive. "
            f"Required file(s) missing: {', '.join(missing)}"
        )


def _install_gameroot(recipe: dict, mod_files: list[Path], steam_roots=None) -> list[Path]:
    """Stage/validate all archives, then install transactionally into the game root."""
    game = find_game(recipe["steam_appid"], steam_roots)
    if not game:
        raise RuntimeError(f"{recipe['name']}: not found in any Steam library.")
    for f in mod_files:
        if not f.is_file():
            raise RuntimeError(f"File not found: {f}")

    comp_of: list[dict | None] = [None] * len(mod_files)
    comps = recipe.get("components")
    if comps:
        mapped: dict[str, tuple[dict, Path]] = {}
        for f in mod_files:
            c = _component_for(recipe, f.name)
            if c is None:
                known = ", ".join(str(x["nexus_mod"]) for x in comps)
                raise RuntimeError(f"{f.name}: can't tell which mod this is. Nexus puts the mod number in the "
                                   f"file name (like 'Cyber Engine Tweaks-107-1-37-1-….zip'), so keep it. "
                                   f"Known mod numbers: {known}")
            key = str(c["nexus_mod"])
            if key in mapped:
                raise RuntimeError(f"Two files for {c['name']}: {mapped[key][1].name} and {f.name}. Pick one.")
            mapped[key] = (c, f)
        index = {str(c["nexus_mod"]): i for i, c in enumerate(comps)}
        ordered = sorted(mapped.values(), key=lambda cf: index[str(cf[0]["nexus_mod"])])
        mod_files = [f for _, f in ordered]
        comp_of = [c for c, _ in ordered]

    base = game.resolve()
    token = f"{recipe['id']}-{time.time_ns()}"
    app_root = state_file().parent
    stage_root = app_root / "staging" / token
    txn_root = app_root / "transactions" / token
    backup_root = txn_root / "backup"
    written_by: list[list[Path]] = []
    original_backups: dict[Path, Path] = {}
    originally_missing: set[Path] = set()

    try:
        plans = []
        root_dirs = recipe.get("root_dirs")
        for i, (f, comp) in enumerate(zip(mod_files, comp_of)):
            stage = stage_root / str(i)
            stage.mkdir(parents=True)
            rels = _stage_archive(f, stage)
            plan = _plan_gameroot(rels, f.name, root_dirs)
            _validate_component_plan(comp, plan, f.name)
            plans.append((stage, plan))

        # Back up every destination that existed before this transaction exactly once.
        all_targets: list[Path] = []
        for _stage, plan in plans:
            for _src, dest in plan:
                target = (base / dest).resolve()
                if not target.is_relative_to(base):
                    raise RuntimeError(f"Unsafe path: {dest}")
                all_targets.append(target)
        for target in dict.fromkeys(all_targets):
            if target.exists():
                if not target.is_file():
                    raise RuntimeError(f"Install target is not a regular file: {target}")
                rel = target.relative_to(base)
                backup = backup_root / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                original_backups[target] = backup
            else:
                originally_missing.add(target)

        for stage, plan in plans:
            written: list[Path] = []
            for src, dest in plan:
                target = (base / dest).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stage / src, target)
                written.append(target)
            written_by.append(written)

    except Exception as e:
        # Roll back the game tree to exactly how it looked before this transaction.
        for target in originally_missing:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        for target, backup in original_backups.items():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            except OSError:
                pass
        _log("install_rollback", recipe=recipe["id"], error=str(e), archives=[f.name for f in mod_files])
        raise
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
        shutil.rmtree(txn_root, ignore_errors=True)

    now = int(time.time())
    st = _load_state()
    entry = st.get(recipe["id"], {})
    comp_state = entry.get("components", {})
    all_new = [str(w) for ws in written_by for w in ws]
    for c, f, ws in zip(comp_of, mod_files, written_by):
        if c is not None:
            comp_state[str(c["nexus_mod"])] = {
                "files": [str(w) for w in ws], "installed_at": now, "archive": f.name
            }
    st[recipe["id"]] = {"files": list(dict.fromkeys(entry.get("files", []) + all_new)),
                        "keep": str(base), "installed_at": now, "components": comp_state}
    _save_state(st)
    _log("install_ok", recipe=recipe["id"], files=len(all_new), archives=[f.name for f in mod_files])
    return [w for ws in written_by for w in ws]


def inspect_archive(recipe: dict, archive: Path) -> dict:
    """Stage one archive without touching the game and report what would be installed."""
    if not archive.is_file():
        raise RuntimeError(f"File not found: {archive}")
    if recipe.get("method") in {"bepinex", "ervr"}:
        from . import bepinex
        package, names = bepinex.inventory(archive, recipe)
        with zipfile.ZipFile(archive) as z:
            archive_files = sum(not item.is_dir() for item in z.infolist())
        return {"archive": archive.name, "component": package["name"], "nexus_mod": None,
                "archive_files": archive_files, "install_files": len(names),
                "required_files": package["required_files"], "sample": names[:12]}
    if recipe.get("method") != "gameroot":
        raise RuntimeError("Archive inspection is currently available for game-root recipes.")
    comp = _component_for(recipe, archive.name) if recipe.get("components") else None
    token = f"inspect-{recipe['id']}-{time.time_ns()}"
    stage = state_file().parent / "staging" / token
    stage.mkdir(parents=True)
    try:
        rels = _stage_archive(archive, stage)
        plan = _plan_gameroot(rels, archive.name, recipe.get("root_dirs"))
        _validate_component_plan(comp, plan, archive.name)
        roots: dict[str, int] = {}
        for _src, dest in plan:
            roots[dest.parts[0]] = roots.get(dest.parts[0], 0) + 1
        return {
            "archive": archive.name,
            "component": component_label(comp) if comp else None,
            "nexus_mod": comp.get("nexus_mod") if comp else None,
            "archive_files": len(rels),
            "install_files": len(plan),
            "roots": roots,
            "required_files": [str(p) for p in _component_required_files(comp or {})],
            "sample": [str(dest) for _src, dest in plan[:12]],
        }
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def inspect_text(report: dict) -> str:
    lines = [f"Archive: {report['archive']}"]
    if report.get("component"):
        lines.append(f"Component: {report['component']}" + (f" (#{report['nexus_mod']})" if report.get("nexus_mod") else ""))
    lines += [f"Files in archive: {report['archive_files']}",
              f"Files that would be installed: {report['install_files']}"]
    if report.get("roots"):
        lines.append("Game-root destinations: " + ", ".join(f"{k} ({v})" for k, v in sorted(report["roots"].items())))
    if report.get("required_files"):
        lines.append("Required sentinel(s): " + ", ".join(report["required_files"]))
    if report.get("sample"):
        lines.append("Sample destinations:")
        lines.extend(f"  {x}" for x in report["sample"])
    return "\n".join(lines)


def preflight(recipe: dict, steam_roots=None) -> dict:
    """Return recipe-driven readiness checks without changing the system."""
    rows = []
    game = game_path(recipe, steam_roots)
    store = recipe.get("store", "steam")
    game_label = {"steam": "Steam game", "heroic-epic": "Heroic/Epic game", "heroic-gog": "Heroic/GOG game"}[store]
    missing = "not found in any Steam library" if store == "steam" else "not found in Heroic's configured game installation"
    rows.append({"name": game_label, "ok": bool(game),
                 "detail": str(game) if game else missing})
    req = recipe.get("requirements", {})
    if req.get("proton_prefix"):
        if store == "heroic-epic" or recipe.get("handler") == "kharvox-gog":
            try:
                prefix = _pfx(recipe, steam_roots)
                rows.append({"name": "Heroic Wine/Proton prefix", "ok": True, "detail": str(prefix)})
            except RuntimeError as exc:
                rows.append({"name": "Heroic Wine/Proton prefix", "ok": False, "detail": str(exc)})
        elif store != "steam":
            rows.append({"name": "Proton prefix", "ok": False,
                         "detail": "store-specific handler must validate this prefix"})
        elif game:
            pfx = game.parents[1] / "compatdata" / str(recipe["steam_appid"]) / "pfx"
            rows.append({"name": "Proton prefix", "ok": pfx.is_dir(),
                         "detail": str(pfx) if pfx.is_dir() else "missing; launch the game once with Proton"})
        else:
            rows.append({"name": "Proton prefix", "ok": False, "detail": "game not found"})
    xr = req.get("openxr")
    if xr:
        path, lib = runtime.active_runtime()
        if xr == "wivrn":
            ok = runtime.is_wivrn()
            detail = f"WiVRn active ({lib or path or 'runtime path unavailable'})" if ok else "WiVRn is not the active OpenXR runtime"
        else:
            ok = bool(path and lib)
            detail = f"{lib or path}" if ok else "no active OpenXR runtime found"
        rows.append({"name": "OpenXR", "ok": ok, "detail": detail})
    rep = verify(recipe, steam_roots)
    if rep:
        rows.append({"name": "Required mods", "ok": rep["ready"], "required": True,
                     "detail": f"{rep['ok']}/{rep['total']} components OK"})
    rows.extend(get_handler(recipe).preflight_rows(recipe, game))
    for r in rows:
        r.setdefault("required", True)
    return {"ready": all(r["ok"] or not r["required"] for r in rows), "rows": rows}


def preflight_text(report: dict) -> str:
    lines = []
    for r in report["rows"]:
        tag = "[ok] " if r["ok"] else ("[!!] " if r.get("required", True) else "[--] ")
        lines.append(tag + f"{r['name']}: {r['detail']}")
    lines.append("READY" if report["ready"] else "NOT READY")
    return "\n".join(lines)


def install_many(recipe: dict, mod_files: list[Path], steam_roots=None) -> list[Path]:
    """Install downloaded files, including paired game-root packages."""
    if not get_handler(recipe).install_supported(recipe):
        raise RuntimeError(f"{recipe['name']} is a guided workflow; it has no direct mod-file install step.")
    if recipe.get("method") == "gameroot":
        return _install_gameroot(recipe, mod_files, steam_roots)
    if recipe.get("method") in {"bepinex", "ervr"}:
        from . import bepinex
        return bepinex.install(recipe, mod_files, steam_roots)
    if len(mod_files) != 1:
        raise RuntimeError(f"{recipe['name']} takes one file at a time.")
    return install(recipe, mod_files[0], steam_roots)


def install_profile(recipe: dict, zip_file: Path, steam_roots=None) -> list[Path]:
    """Unpack a UEVR game profile straight into the game's UnrealVRMod folder.

    (UEVR's in-app 'Import Config' under Wine can silently copy only some files.)
    Anything already in that folder is moved to a backup first."""
    prof = recipe.get("profile")
    if not prof:
        raise RuntimeError(f"{recipe['name']} has no profile step.")
    if zip_file.suffix.lower() != ".zip" or not zip_file.is_file():
        raise RuntimeError("Expected the profile .zip file.")
    key = f"{recipe['id']}:profile"
    if key in _load_state():
        raise RuntimeError("A profile is already installed. Remove it first (uninstall-profile).")
    dest = profile_dir(recipe, steam_roots)

    stage = state_file().parent / "staging" / f"{recipe['id']}-{int(time.time())}"
    stage.mkdir(parents=True)
    try:  # unpack + validate in a staging folder before touching the real one
        with zipfile.ZipFile(zip_file) as z:
            written = _extract(z, "config.txt", stage)
        rel = [p.relative_to(stage.resolve()) for p in written]
        backup = None
        if dest.exists():
            backup = state_file().parent / "backups" / f"{recipe['id']}-{time.strftime('%Y%m%d-%H%M%S')}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(backup))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage), str(dest))
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    state = _load_state()
    state[key] = {"files": [str(dest / r) for r in rel], "root": str(dest),
                  "backup": str(backup) if backup else None,
                  "installed_at": int(time.time())}
    _save_state(state)
    return [dest / r for r in rel]


def uninstall(recipe_id: str) -> list[Path]:
    """Remove what we installed under this key (use '<game>:profile' for a profile)."""
    state = _load_state()
    if state.get(recipe_id, {}).get("installer") in {"submersed-vr-1", "vhvr-1", "ervr-1"}:
        from . import bepinex
        return bepinex.uninstall(recipe_id)
    entry = state.pop(recipe_id, {})
    removed = []
    for p in entry.get("files", []):
        Path(p).unlink(missing_ok=True)
        removed.append(Path(p))
    keep = entry.get("keep")  # game folder: remove folders we emptied, but never this one or above
    if keep:
        keep_p = Path(keep)
        for p in removed:
            for parent in Path(p).parents:
                if parent == keep_p or not parent.is_relative_to(keep_p):
                    break
                try:
                    parent.rmdir()
                except OSError:
                    break
    root = entry.get("root")
    if root and Path(root).is_dir():  # remove empty folders inside our own folder only
        for d in sorted(Path(root).rglob("*"), key=lambda x: len(x.parts), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass
        try:
            Path(root).rmdir()
        except OSError:
            pass
    backup = entry.get("backup")
    if root and backup and Path(backup).is_dir():  # put back what the profile replaced
        shutil.copytree(backup, root, dirs_exist_ok=True)
    _save_state(state)
    return removed


def launch_options(recipe: dict) -> str:
    env = " ".join(f"{k}={v}" for k, v in recipe.get("launch", {}).get("env", {}).items())
    args = recipe.get("launch", {}).get("args", "")
    guard = f'{shlex.quote(str(guard_path()))} {shlex.quote(recipe["id"])}' if recipe.get("components") or recipe.get("packages") else ""
    return " ".join(x for x in (env, guard, "%command%", args) if x)



def game_launcher_label(recipe: dict) -> str | None:
    """Return the game-specific tool launcher label, if the handler provides one."""
    return get_handler(recipe).launcher_label(recipe)


def game_play_label(recipe: dict) -> str | None:
    """Return the handler-owned modded-game launch label, if available."""
    return get_handler(recipe).play_label(recipe)


def game_live_status(recipe: dict, steam_roots=None) -> dict:
    """Return lightweight live process status for handler-owned launch workflows."""
    game = game_path(recipe, steam_roots)
    return get_handler(recipe).live_status(recipe, game)


def game_bridge_log(recipe: dict) -> Path | None:
    """Return a handler-owned bridge/debug log path when one exists."""
    return get_handler(recipe).bridge_log(recipe)


def game_bridge_log_label(recipe: dict) -> str:
    """Return the user-facing label for a handler-owned debug log."""
    return get_handler(recipe).bridge_log_label(recipe)


def launch_game_tool(recipe: dict, steam_roots=None) -> subprocess.Popen:
    """Start a handler-owned launcher such as MGO/Mod Organizer."""
    game = game_path(recipe, steam_roots)
    rep = preflight(recipe, steam_roots)
    bad = [r for r in rep["rows"] if r.get("required", True) and not r["ok"]]
    if bad:
        detail = "; ".join(f"{r['name']}: {r['detail']}" for r in bad)
        raise RuntimeError(f"Preflight is not ready: {detail}")
    proc = get_handler(recipe).launch(recipe, game)
    _log("launch_game_tool", recipe=recipe["id"], pid=proc.pid)
    return proc


def launch_game_play(recipe: dict, steam_roots=None) -> subprocess.Popen:
    """Launch the handler-configured game path through its owning storefront/tool."""
    game = game_path(recipe, steam_roots)
    # The flat DOOM fallback belongs to Heroic and needs no KHARVOX/runtime.
    rep = {"rows": []} if recipe.get("handler") == "kharvox-gog" else preflight(recipe, steam_roots)
    bad = [r for r in rep["rows"] if r.get("required", True) and not r["ok"]]
    if bad:
        detail = "; ".join(f"{r['name']}: {r['detail']}" for r in bad)
        raise RuntimeError(f"Preflight is not ready: {detail}")
    proc = get_handler(recipe).launch_play(recipe, game)
    _log("launch_game_play", recipe=recipe["id"], pid=proc.pid)
    return proc

def component_label(comp: dict, names: dict | None = None) -> str:
    names = _load_state().get("_names", {}) if names is None else names
    return names.get(str(comp["nexus_mod"]), {}).get("name") or comp["name"]


def verify(recipe: dict, steam_roots=None) -> dict | None:
    """Check every listed component: installed through the hub, and its files still on disk.
    Phase-1 components are required to start the game; phase-2 (the VR port) is not."""
    if recipe.get("method") in {"bepinex", "ervr"}:
        from . import bepinex
        return bepinex.verify(recipe, steam_roots)
    comps = recipe.get("components")
    if not comps:
        return None
    st = _load_state()
    names, recs = st.get("_names", {}), st.get(recipe["id"], {}).get("components", {})
    game = recipe.get("nexus_game", "")
    rows = []
    for i, c in enumerate(comps, 1):
        rec = recs.get(str(c["nexus_mod"]))
        if not rec:
            status, detail = "missing", "not installed"
        else:
            gone = [f for f in rec["files"] if not Path(f).exists()]
            keep = st.get(recipe["id"], {}).get("keep")
            required_gone = []
            if keep:
                game_root = Path(keep)
                required_gone = [str(p) for p in _component_required_files(c) if not (game_root / p).is_file()]
            if gone or required_gone:
                status = "damaged"
                bits = []
                if gone:
                    bits.append(f"{len(gone)} of {len(rec['files'])} recorded files missing")
                if required_gone:
                    bits.append("required file(s) missing: " + ", ".join(required_gone))
                detail = "; ".join(bits) + ", reinstall it"
            else:
                status, detail = "ok", f"installed ({len(rec['files'])} files)"
        rows.append({"n": i, "id": c["nexus_mod"], "name": component_label(c, names), "phase": c.get("phase", 1),
                     "status": status, "detail": detail,
                     "page": f"https://www.nexusmods.com/{game}/mods/{c['nexus_mod']}"})
    required = [r for r in rows if r["phase"] == 1 and r["status"] != "ok"]
    later = [r for r in rows if r["phase"] != 1 and r["status"] != "ok"]
    return {"rows": rows, "ready": not required, "required_bad": required, "later_bad": later,
            "ok": sum(r["status"] == "ok" for r in rows), "total": len(rows)}


def verify_text(rep: dict, quiet: bool = False) -> str:
    lines = []
    if not quiet:
        for r in rep["rows"]:
            tag = {"ok": "[ok]     ", "missing": "[MISSING]", "damaged": "[DAMAGED]"}[r["status"]]
            note = "" if r["phase"] == 1 else "  (installed last, after one test launch)"
            label = r["name"] if isinstance(r["id"], str) or f"#{r['id']}" in r["name"] else f"{r['name']} (#{r['id']})"
            lines.append(f"{r['n']:>2}. {tag} {label}: {r['detail']}{note}")
        lines.append("")
    if not rep["ready"]:
        bad = "; ".join(f"{r['name']} ({r['status']})" for r in rep["required_bad"])
        lines.append(f"NOT READY: {len(rep['required_bad'])} required mod(s) need attention: {bad}")
    else:
        lines.append(f"READY: all {rep['total'] - len(rep['later_bad'])} required mods are installed.")
        if rep["later_bad"]:
            names = ", ".join(r["name"] for r in rep["later_bad"])
            lines.append(f"Not installed yet: {names}. The game will start without VR until it is.")
    return "\n".join(lines).rstrip()


def refresh_component_names(recipe: dict, key=None, fetch=None, max_age: int = 86400) -> int:
    """Look up the real mod names on Nexus (needs the API key) and remember them for the checklist."""
    comps, game = recipe.get("components"), recipe.get("nexus_game")
    key = key or updates.get_key()
    if not comps or not game or not key:
        return 0
    fetch = fetch or updates.fetch_mod_info
    cached = _load_state().get("_names", {})
    found = {}
    for c in comps:
        cur = cached.get(str(c["nexus_mod"]))
        if cur and time.time() - cur.get("checked_at", 0) < max_age:
            continue
        try:
            found[str(c["nexus_mod"])] = {**fetch(game, c["nexus_mod"], key), "checked_at": int(time.time())}
        except (OSError, ValueError, KeyError, TypeError):
            continue  # offline or a bad reply: keep whatever name we had
    if found:
        st = _load_state()  # reload so we don't clobber an install that happened meanwhile
        st.setdefault("_names", {}).update(found)
        _save_state(st)
    return len(found)


def game_rows(steam_roots=None) -> list[dict]:
    """One status row per recipe (used by the GUI)."""
    rows = []
    for r in load_recipes().values():
        rep = verify(r)
        rows.append({"recipe": r,
                     "game_found": game_path(r, steam_roots) is not None,
                     "mod_installed": is_installed(r["id"]),
                     "components": (rep["ok"], rep["total"], rep["ready"]) if rep else None,
                     "has_profile": "profile" in r,
                     "profile_installed": profile_installed(r["id"])})
    return rows


def state() -> dict:
    return _load_state()


def mark_current(recipe: dict) -> list[str]:
    """Record 'installed just now' for this game's installs (use after grabbing the latest release by hand)."""
    st = _load_state()
    keys = {k for u in recipe.get("updates", []) for k in u.get("tracks", [])} or {recipe["id"]}
    marked = []
    for k in sorted(keys):
        if k in st:
            st[k]["installed_at"] = int(time.time())
            marked.append(k)
    _save_state(st)
    return marked


def diagnostics(recipe: dict, steam_roots=None) -> str:
    """Human-readable local diagnostic summary; safe to paste into a bug report."""
    game = game_path(recipe, steam_roots)
    rep = verify(recipe)
    store = recipe.get("store", "steam")
    store_line = (f"Steam app: {recipe['steam_appid']}" if store == "steam" else
                  f"Heroic/Epic game: {recipe['heroic_title']}" if store == "heroic-epic" else
                  f"Heroic/GOG app: {recipe['heroic_appid']}")
    lines = [f"Game: {recipe['name']}", f"Recipe: {recipe['id']}",
             store_line, f"Game path: {game or 'not found'}",
             f"State file: {state_file()}", f"Log file: {log_file()}"]
    if rep:
        lines += ["", verify_text(rep)]
    handler_lines = get_handler(recipe).diagnostics(recipe, game)
    if handler_lines:
        lines += ["", "Handler diagnostics:", *handler_lines]
    if "compatibility" in recipe:
        from . import compatibility
        lines += ["", compatibility.report_text(compatibility.report(recipe, steam_roots))]
    return "\n".join(lines)


SECTIONS = (("One-time setup", "setup", True), ("Each time you play", "play", True),
            ("Good to know", "good_to_know", False))


def details_text(recipe: dict) -> str:
    launch = recipe.get("launch", {})
    lines = [recipe["name"], "", f"Mod page: {recipe['mod_page']}"]
    for link in recipe.get("links", []):
        lines.append(f"{link['label']}: {link['url']}")
    if recipe.get("profile", {}).get("page"):
        lines.append(f"Profile:  {recipe['profile']['page']}")
    if recipe.get("store", "steam") == "steam":
        lines += ["", "Steam launch options:", f"  {launch_options(recipe)}"]
    if launch.get("optional_args"):
        lines.append(f"  (optional: add {launch['optional_args']})")
    if recipe.get("components"):
        lines += ["", "Mods, in install order:"]
        for n, c in enumerate(recipe["components"], 1):
            lines.append(f"  {n}. {component_label(c)} (#{c['nexus_mod']})"
                         + ("  - installed last" if c.get("phase", 1) != 1 else ""))
    notes = get_handler(recipe).detail_notes(recipe)
    if notes:
        lines += ["", "Game-specific notes:"] + [f"  - {x}" for x in notes]
    for title, key, numbered in SECTIONS:
        items = recipe.get(key)
        if items:
            lines += ["", f"{title}:"] + [f"  {n}. {t}" if numbered else f"  - {t}"
                                          for n, t in enumerate(items, 1)]
    return "\n".join(lines)


def details_html(recipe: dict, update_items: list[dict] | None = None, report: dict | None = None) -> str:
    """Readable rich-text version for the GUI (headings, numbered steps, code box)."""
    e = html.escape
    launch = recipe.get("launch", {})
    out = [
        "<style>"
        "body{color:#F5F2DE;} h2{color:#FFD21A;} h3{color:#F5F2DE;} "
        "a{color:#23B7FF;} code,pre{color:#FFD21A;background:#0D1115;} "
        "table{border-color:#2A3139;}"
        "</style>",
        f"<h2>{e(recipe['name'])}</h2>"
    ]
    links = [f'<a href="{e(recipe["mod_page"])}">Mod page</a>']
    links += [f'<a href="{e(x["url"])}">{e(x["label"])}</a>' for x in recipe.get("links", [])]
    if recipe.get("profile", {}).get("page"):
        links.append(f'<a href="{e(recipe["profile"]["page"])}">Profile page</a>')
    out.append("<p>" + " &nbsp;|&nbsp; ".join(links) + "</p>")
    if update_items:
        out.append("<h3>Updates</h3><ul>")
        for i in update_items:
            out.append(f"<li><b>{e(i['name'])}:</b> {e(i['detail'])} "
                       f'(<a href="{e(i["page"])}">open</a>)</li>')
        out.append("</ul>")
    if recipe.get("store", "steam") == "steam":
        out.append("<h3>Steam launch options</h3>")
        out.append('<table border="1" cellspacing="0" cellpadding="6"><tr><td><pre>'
                   f"{e(launch_options(recipe))}</pre></td></tr></table>")
        if launch.get("optional_args"):
            out.append(f"<p><i>Optional: also add <code>{e(launch['optional_args'])}</code></i></p>")
    notes = get_handler(recipe).detail_notes(recipe)
    if notes:
        out.append("<h3>Game-specific notes</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in notes) + "</ul>")
    if report:
        colour = {"ok": "#4FE39A", "missing": "#FF5B50", "damaged": "#FFD21A"}
        out.append("<h3>Mods checklist</h3>")
        verdict = ("<b style='color:#4FE39A'>Ready to launch.</b>" if report["ready"] else
                   f"<b style='color:#FF5B50'>Not ready: {len(report['required_bad'])} required mod(s) need attention.</b>")
        if report["ready"] and report["later_bad"]:
            verdict += " The VR port isn't installed yet, so the game would start without VR."
        out.append(f"<p>{verdict} ({report['ok']} of {report['total']} installed)</p>")
        out.append('<table border="1" cellspacing="0" cellpadding="4">')
        for r in report["rows"]:
            tag = {"ok": "OK", "missing": "MISSING", "damaged": "DAMAGED"}[r["status"]]
            out.append(f"<tr><td>{r['n']}</td><td><b style='color:{colour[r['status']]}'>{tag}</b></td>"
                       f"<td><a href=\"{e(r['page'])}\">{e(r['name'])}</a></td><td>{e(r['detail'])}</td></tr>")
        out.append("</table>")
    for title, key, numbered in SECTIONS:
        items = recipe.get(key)
        if items:
            tag = "ol" if numbered else "ul"
            out.append(f"<h3>{title}</h3><{tag}>" + "".join(f"<li>{e(t)}</li>" for t in items) + f"</{tag}>")
    return "".join(out)


def injector_path(recipe: dict, steam_roots=None) -> Path:
    if recipe.get("method") != "uevr":
        raise RuntimeError("This game doesn't use the UEVR injector.")
    exe = _uevr_dir(recipe, steam_roots) / "UEVRInjector.exe"
    if not exe.is_file():
        raise RuntimeError("UEVR isn't installed for this game yet. Install the UEVR zip first.")
    return exe


def launch_injector(recipe: dict, steam_roots=None):
    """Steam uses protontricks; native Heroic reuses its selected runner/prefix."""
    exe = injector_path(recipe, steam_roots)
    if recipe.get("store") == "heroic-epic":
        from . import heroic_epic, heroic_injector
        return heroic_injector.launch(heroic_epic.context(recipe), exe)
    tool = shutil.which("protontricks-launch")
    if not tool:
        raise RuntimeError("protontricks-launch not found. Install protontricks "
                           "(e.g. `sudo pacman -S protontricks`, or `pipx install protontricks`).")
    return subprocess.Popen([tool, "--no-bwrap", "--appid", str(recipe["steam_appid"]),
                             "--no-background-wineserver", str(exe)])
