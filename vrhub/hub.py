"""NAnnersVRhub core: recipes, install/uninstall bookkeeping, UEVR + profile handling."""
import html
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
import zipfile
from pathlib import Path

from . import updates
from .steam import find_game

HUB_DIR = Path(__file__).resolve().parent.parent
RECIPE_DIR = HUB_DIR / "recipes"
APPDATA = Path("drive_c/users/steamuser/AppData")


def state_file() -> Path:
    return Path(os.environ.get("VRHUB_STATE", "~/.local/share/vrhub/state.json")).expanduser()


def load_recipes() -> dict[str, dict]:
    out = {}
    for f in sorted(RECIPE_DIR.glob("*.toml")):
        r = tomllib.loads(f.read_text())
        out[r["id"]] = r
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
    names = {n: n.replace("\\", "/") for n in z.namelist() if not n.endswith("/")}
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
    game = find_game(recipe["steam_appid"], steam_roots)
    if not game:
        raise RuntimeError(f"{recipe['name']}: not found in any Steam library.")
    pfx = game.parents[1] / "compatdata" / str(recipe["steam_appid"]) / "pfx"
    if not pfx.is_dir():
        raise RuntimeError("Proton prefix not found. Launch the game once from Steam "
                           "(with Proton enabled) so it gets created, then try again.")
    return pfx


def _uevr_dir(recipe: dict, steam_roots=None) -> Path:
    return _pfx(recipe, steam_roots) / "drive_c" / "uevr"


def install(recipe: dict, mod_file: Path, steam_roots=None) -> list[Path]:
    """Install a mod from a .pak file, or from a .zip containing one (or a UEVR zip)."""
    game = find_game(recipe["steam_appid"], steam_roots)
    if not game:
        raise RuntimeError(f"{recipe['name']}: not found in any Steam library.")
    if not mod_file.is_file():
        raise RuntimeError(f"File not found: {mod_file}")
    if recipe.get("method") == "uevr":
        return _install_uevr(recipe, mod_file, steam_roots)
    if recipe.get("method") == "gameroot":
        return _install_gameroot(recipe, [mod_file], steam_roots)
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
            members = {n: n.replace("\\", "/") for n in z.namelist() if not n.replace("\\", "/").endswith("/")}
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


def _plan_gameroot(rels: list[Path], label: str) -> list[tuple[Path, Path]]:
    """Map archive files to game-folder paths. Strips one wrapper folder, fixes the case of the
    top-level folder (Linux is case-sensitive), and ignores readmes/anything outside ROOT_DIRS."""
    def is_root(part: str) -> bool:
        return part.lower() in ROOT_DIRS
    strip = 0
    if not any(len(r.parts) > 1 and is_root(r.parts[0]) for r in rels):
        tops = {r.parts[0] for r in rels if len(r.parts) > 1}
        if len(tops) == 1 and any(len(r.parts) > 2 and is_root(r.parts[1]) for r in rels):
            strip = 1
        else:
            raise RuntimeError(f"{label} doesn't look like a Cyberpunk mod archive "
                               "(no bin / r6 / red4ext / archive folder inside).")
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


def _install_gameroot(recipe: dict, mod_files: list[Path], steam_roots=None) -> list[Path]:
    """Extract one or more mod archives into the game folder (in recipe order if it lists components)."""
    game = find_game(recipe["steam_appid"], steam_roots)
    if not game:
        raise RuntimeError(f"{recipe['name']}: not found in any Steam library.")
    for f in mod_files:
        if not f.is_file():
            raise RuntimeError(f"File not found: {f}")
    comp_of: list[dict | None] = [None] * len(mod_files)
    comps = recipe.get("components")
    if comps:  # work out which mod each file is, reject unknowns/duplicates, sort into install order
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
    stage_root = state_file().parent / "staging" / f"{recipe['id']}-{int(time.time())}"
    written_by: list[list[Path]] = []
    try:
        plans = []
        for i, f in enumerate(mod_files):  # stage + check EVERY archive before touching the game
            stage = stage_root / str(i)
            stage.mkdir(parents=True)
            plans.append((stage, _plan_gameroot(_stage_archive(f, stage), f.name)))
        for stage, plan in plans:
            written: list[Path] = []
            for src, dest in plan:
                target = (base / dest).resolve()
                if not target.is_relative_to(base):
                    raise RuntimeError(f"Unsafe path: {dest}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stage / src, target)
                written.append(target)
            written_by.append(written)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

    now = int(time.time())
    st = _load_state()
    entry = st.get(recipe["id"], {})
    comp_state = entry.get("components", {})
    all_new = [str(w) for ws in written_by for w in ws]
    for c, f, ws in zip(comp_of, mod_files, written_by):
        if c is not None:
            comp_state[str(c["nexus_mod"])] = {"files": [str(w) for w in ws], "installed_at": now, "archive": f.name}
    st[recipe["id"]] = {"files": list(dict.fromkeys(entry.get("files", []) + all_new)),
                        "keep": str(base), "installed_at": now, "components": comp_state}
    _save_state(st)
    return [w for ws in written_by for w in ws]


def install_many(recipe: dict, mod_files: list[Path], steam_roots=None) -> list[Path]:
    """Install one or several downloaded files (several only for 'gameroot' games)."""
    if recipe.get("method") == "gameroot":
        return _install_gameroot(recipe, mod_files, steam_roots)
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
    dest = _pfx(recipe, steam_roots) / APPDATA / prof["dir"]

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
    guard = f'"{HUB_DIR / "vrhub-check"}" {recipe["id"]}' if recipe.get("components") else ""
    return " ".join(x for x in (env, guard, "%command%", args) if x)


def component_label(comp: dict, names: dict | None = None) -> str:
    names = _load_state().get("_names", {}) if names is None else names
    return names.get(str(comp["nexus_mod"]), {}).get("name") or comp["name"]


def verify(recipe: dict) -> dict | None:
    """Check every listed component: installed through the hub, and its files still on disk.
    Phase-1 components are required to start the game; phase-2 (the VR port) is not."""
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
            status = "damaged" if gone else "ok"
            detail = f"{len(gone)} of {len(rec['files'])} files missing, reinstall it" if gone else \
                f"installed ({len(rec['files'])} files)"
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
            label = r["name"] if f"#{r['id']}" in r["name"] else f"{r['name']} (#{r['id']})"
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
                     "game_found": find_game(r["steam_appid"], steam_roots) is not None,
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


SECTIONS = (("One-time setup", "setup", True), ("Each time you play", "play", True),
            ("Good to know", "good_to_know", False))


def details_text(recipe: dict) -> str:
    launch = recipe.get("launch", {})
    lines = [recipe["name"], "", f"Mod page: {recipe['mod_page']}"]
    if recipe.get("profile", {}).get("page"):
        lines.append(f"Profile:  {recipe['profile']['page']}")
    lines += ["", "Steam launch options:", f"  {launch_options(recipe)}"]
    if launch.get("optional_args"):
        lines.append(f"  (optional: add {launch['optional_args']})")
    if recipe.get("components"):
        lines += ["", "Mods, in install order:"]
        for n, c in enumerate(recipe["components"], 1):
            lines.append(f"  {n}. {component_label(c)} (#{c['nexus_mod']})"
                         + ("  - installed last" if c.get("phase", 1) != 1 else ""))
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
    out = [f"<h2>{e(recipe['name'])}</h2>"]
    links = [f'<a href="{e(recipe["mod_page"])}">Mod page</a>']
    if recipe.get("profile", {}).get("page"):
        links.append(f'<a href="{e(recipe["profile"]["page"])}">Profile page</a>')
    out.append("<p>" + " &nbsp;|&nbsp; ".join(links) + "</p>")
    if update_items:
        out.append("<h3>Updates</h3><ul>")
        for i in update_items:
            out.append(f"<li><b>{e(i['name'])}:</b> {e(i['detail'])} "
                       f'(<a href="{e(i["page"])}">open</a>)</li>')
        out.append("</ul>")
    out.append("<h3>Steam launch options</h3>")
    out.append('<table border="1" cellspacing="0" cellpadding="6"><tr><td><pre>'
               f"{e(launch_options(recipe))}</pre></td></tr></table>")
    if launch.get("optional_args"):
        out.append(f"<p><i>Optional: also add <code>{e(launch['optional_args'])}</code></i></p>")
    if report:
        colour = {"ok": "#2e9e4f", "missing": "#c0392b", "damaged": "#d68910"}
        out.append("<h3>Mods checklist</h3>")
        verdict = ("<b style='color:#2e9e4f'>Ready to launch.</b>" if report["ready"] else
                   f"<b style='color:#c0392b'>Not ready: {len(report['required_bad'])} required mod(s) need attention.</b>")
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


def launch_injector(recipe: dict, steam_roots=None) -> subprocess.Popen:
    """Start UEVRInjector.exe inside the game's Proton prefix via protontricks-launch."""
    if recipe.get("method") != "uevr":
        raise RuntimeError("This game doesn't use the UEVR injector.")
    exe = _uevr_dir(recipe, steam_roots) / "UEVRInjector.exe"
    if not exe.is_file():
        raise RuntimeError("UEVR isn't installed for this game yet. Install the UEVR zip first.")
    tool = shutil.which("protontricks-launch")
    if not tool:
        raise RuntimeError("protontricks-launch not found. Install protontricks "
                           "(e.g. `sudo pacman -S protontricks`, or `pipx install protontricks`).")
    return subprocess.Popen([tool, "--no-bwrap", "--appid", str(recipe["steam_appid"]),
                             "--no-background-wineserver", str(exe)])
