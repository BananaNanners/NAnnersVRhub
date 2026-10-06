"""Small Heroic/GOG discovery helpers.

The Hub deliberately reads Heroic's own metadata and asks Heroic to launch games;
it does not try to reproduce Heroic's Wine/Proton command line.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def config_root() -> Path:
    return Path(os.environ.get("NANNERS_HEROIC_CONFIG", "~/.config/heroic")).expanduser()


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def gog_install(appid: str | int) -> dict | None:
    appid = str(appid)
    data = _json(config_root() / "gog_store" / "installed.json")
    for row in data.get("installed", []):
        if str(row.get("appName", "")) == appid:
            return row
    return None


def game_settings(appid: str | int) -> dict:
    appid = str(appid)
    data = _json(config_root() / "GamesConfig" / f"{appid}.json")
    row = data.get(appid, {})
    return row if isinstance(row, dict) else {}


def gog_game_path(appid: str | int) -> Path | None:
    row = gog_install(appid)
    if not row:
        return None
    raw = str(row.get("install_path", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path.resolve() if path.is_dir() else path


def heroic_command(appid: str | int, runner: str = "gog") -> list[str]:
    """Return the same URI-style launch form Heroic uses for shortcuts."""
    uri = f"heroic://launch?appName={appid}&runner={runner}"
    exe = shutil.which("heroic")
    if exe:
        return [exe, "--no-gui", "--no-sandbox", uri]
    # Native Heroic packages normally expose `heroic`.  Keep Flatpak as a
    # fallback for other machines without making it the primary path.
    flatpak = shutil.which("flatpak")
    if flatpak:
        return [flatpak, "run", "com.heroicgameslauncher.hgl", "--no-gui", "--no-sandbox", uri]
    raise RuntimeError("Heroic Games Launcher command was not found in PATH.")
