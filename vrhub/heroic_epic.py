"""Read Heroic/Epic install records without credentials or configuration writes."""
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlencode

FLATPAK_ID = "com.heroicgameslauncher.hgl"


def default_roots():
    value = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(value) if value and Path(value).is_absolute() else Path.home() / ".config"
    return list(dict.fromkeys(p.resolve() for p in [base / "heroic", Path.home() / f".var/app/{FLATPAK_ID}/config/heroic"]))


def config_roots():
    override = os.environ.get("NANNERS_HEROIC_CONFIG", "").strip()
    if override:
        path = Path(override).expanduser()
        return [path.resolve()] if path.is_absolute() else []
    return default_roots()


def _read(path):
    try:
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("too large")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"Cannot read Heroic metadata: {path}. Open/save this game's settings in Heroic and retry.") from exc


def _title(value):
    return "".join(c for c in value.casefold() if c.isalnum())


def context(recipe):
    matches, errors = [], []
    for root in config_roots():
        path = root / "legendaryConfig/legendary/installed.json"
        if not path.exists():
            continue
        try:
            installed = _read(path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        for key, row in installed.items():
            if isinstance(row, dict) and isinstance(row.get("title"), str) and _title(row["title"]) == _title(recipe["heroic_title"]):
                appid = row.get("app_name", key)
                if not isinstance(appid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", appid) or appid != key:
                    errors.append(f"Invalid Epic installation identity in {path}.")
                    continue
                matches.append((root, path, appid, row))
    if errors:
        raise RuntimeError(" ".join(errors) + " Select the intended Heroic config with NANNERS_HEROIC_CONFIG if another installation is broken.")
    if len(matches) != 1:
        if matches:
            raise RuntimeError("Multiple Heroic/Epic Hogwarts installs were found. Set NANNERS_HEROIC_CONFIG to the intended Heroic config folder; no prefix was selected.")
        raise RuntimeError("Hogwarts Legacy was not found in Heroic's Epic installed.json. Install/import it in Heroic and launch it once; NANNERS_HEROIC_CONFIG can select a custom Heroic config folder.")
    root, metadata, appid, row = matches[0]
    settings_path = root / "GamesConfig" / f"{appid}.json"
    settings = _read(settings_path).get(appid)
    if not isinstance(settings, dict):
        raise RuntimeError(f"Heroic game settings are missing for Epic app {appid}: {settings_path}")
    raw = row.get("install_path")
    game = Path(raw).expanduser() if isinstance(raw, str) and raw.strip() else None
    if not game or not game.is_absolute() or not game.is_dir():
        raise RuntimeError("Heroic's recorded Hogwarts install folder is missing. Repair/reimport the game in Heroic; no Steam folder will be substituted.")
    wine = settings.get("wineVersion", {})
    return {"root": root, "metadata": metadata, "settings_path": settings_path, "appid": appid,
            "game": game.resolve(), "settings": settings, "wine": wine if isinstance(wine, dict) else {},
            "flatpak": FLATPAK_ID in root.parts}


def prefix(info):
    raw = info["settings"].get("winePrefix")
    path = Path(raw).expanduser() if isinstance(raw, str) and raw.strip() else None
    if not path or not path.is_absolute():
        raise RuntimeError("Set the Hogwarts Wine prefix in Heroic and launch the game once; no prefix was guessed or created.")
    candidates = list(dict.fromkeys(p.resolve() for p in (path, path / "pfx") if (p / "drive_c").is_dir()))
    if len(candidates) != 1:
        raise RuntimeError("Heroic's Hogwarts prefix is missing or ambiguous (drive_c versus pfx/drive_c). Launch once in Heroic and review its Wine prefix setting.")
    return candidates[0].resolve()


def appdata(info):
    pfx = prefix(info)
    users = pfx / "drive_c/users"
    candidates = [p / "AppData" for p in users.iterdir() if p.is_dir() and p.name.casefold() not in {"public", "default", "default user", "all users"}
                  and (p / "AppData").is_dir()] if users.is_dir() else []
    preferred = users / "steamuser/AppData"
    if info["wine"].get("type") == "proton" and preferred in candidates:
        selected = preferred
    elif len(candidates) == 1:
        selected = candidates[0]
    else:
        raise RuntimeError("The active Windows AppData folder cannot be selected safely. Launch Hogwarts once with Heroic's configured runner and review the prefix users.")
    if not selected.resolve().is_relative_to(pfx):
        raise RuntimeError("Heroic's AppData folder resolves outside the selected prefix; profile installation was stopped.")
    return selected.resolve()


def command(info, *, play):
    if info["root"] not in default_roots():
        raise RuntimeError("Open the intended Heroic installation manually. NANNERS_HEROIC_CONFIG selects Hub discovery metadata; it does not change Heroic's launch configuration.")
    args = []
    if play:
        args = ["--no-gui", "heroic://launch?" + urlencode({"appName": info["appid"], "runner": "legendary"})]
    if info["flatpak"]:
        exe = shutil.which("flatpak")
        if not exe:
            raise RuntimeError("This installation belongs to Flatpak Heroic, but flatpak is unavailable.")
        return [exe, "run", FLATPAK_ID, *args]
    exe = shutil.which("heroic")
    if not exe:
        raise RuntimeError("The native Heroic command is unavailable. Open Heroic manually; no other Heroic installation was selected.")
    return [exe, *args]
