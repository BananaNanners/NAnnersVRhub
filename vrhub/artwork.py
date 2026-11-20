# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Local-only per-game artwork selection, independent of game installation.

Priority: user-imported hub copy > Steam local override > Steam's existing
library art > Heroic's existing local art > original generated Hub banner.
Neither Steam nor Heroic are modified, and nothing is downloaded.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QIODevice, QSaveFile
from PySide6.QtGui import QImageReader

from .heroic_epic import config_roots as heroic_config_roots

MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 45_000_000
MAX_BANNER_WIDTH = 1920
MAX_BANNER_HEIGHT = 1080
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_GAME_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
_HEROIC_ID = re.compile(r"[A-Za-z0-9_-]{1,200}\Z")


@dataclass(frozen=True)
class ArtworkChoice:
    path: Path | None
    source: str
    custom: bool = False


def _game_id(recipe: dict) -> str:
    value = recipe.get("id") if isinstance(recipe, dict) else None
    if not isinstance(value, str) or not _GAME_ID.fullmatch(value):
        raise ValueError("The selected game has an invalid recipe identifier.")
    return value


def artwork_directory() -> Path:
    configured = os.environ.get("XDG_DATA_HOME", "").strip()
    if configured and Path(configured).is_absolute():
        root = Path(configured)
    else:
        root = Path.home() / ".local/share"
    return root / "nannersvrhub" / "artwork"


def custom_artwork_path(recipe: dict) -> Path:
    return artwork_directory() / f"{_game_id(recipe)}.png"


def _valid_local_image(path: Path) -> bool:
    """Check candidate without parsing arbitrary Heroic metadata or writing."""
    try:
        if (not path.is_file() or path.stat().st_size < 100
                or path.stat().st_size > MAX_IMAGE_BYTES):
            return False
        image = QImageReader(str(path))
        if not image.canRead():
            return False
        size = image.size()
        return (size.isValid() and 0 < size.width() * size.height()
                <= MAX_IMAGE_PIXELS)
    except OSError:
        return False


def _steam_candidates(recipe: dict):
    appid = recipe.get("steam_appid")
    if type(appid) is not int or appid <= 0:
        return
    # The built-in Steam art can live in either of these locations. These
    # paths are read-only, and don't require Steam or a connected network.
    roots = (
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
    )
    seen = set()
    for root in roots:
        # User-supplied Steam grid overrides are preferred to Steam defaults.
        userdata = root / "userdata"
        if userdata.is_dir():
            for entry in sorted(userdata.iterdir()):
                if not entry.name.isdecimal():
                    continue
                for suffix in ("png", "jpg", "jpeg", "webp"):
                    path = entry / "config/grid" / f"{appid}_hero.{suffix}"
                    if path not in seen:
                        seen.add(path)
                        yield path, "Steam custom grid artwork"
        cache = root / "appcache/librarycache" / str(appid)
        for filename in ("library_hero.jpg", "library_hero.png",
                         "library_hero.webp", "header.jpg", "header.png"):
            path = cache / filename
            if path not in seen:
                seen.add(path)
                yield path, "Steam library artwork"


def _heroic_art_roots():
    """Search local Heroic artwork even when Hub test XDG paths are isolated.

    Explicit Heroic override roots remain first; the usual native path and
    Flatpak path are only read, never changed.
    """
    candidates = (
        *heroic_config_roots(),
        Path.home() / ".config/heroic",
        Path.home() / ".var/app/com.heroicgameslauncher.hgl/config/heroic",
    )
    return list(dict.fromkeys(candidates))


def _heroic_candidates(recipe: dict):
    store = recipe.get("store", "steam")
    if store not in ("heroic-epic", "heroic-gog"):
        return
    appid = recipe.get("heroic_appid")
    if not appid and store == "heroic-epic":
        # Discover the Epic ID from Heroic's installed games by exact
        # title, as the original game recipe does. No credentials needed.
        import json
        requested_title = recipe.get("heroic_title")
        if isinstance(requested_title, str) and requested_title:
            for root in _heroic_art_roots():
                installed = root / "legendaryConfig/legendary/installed.json"
                try:
                    if not installed.is_file() or installed.stat().st_size > 4 * 1024 * 1024:
                        continue
                    games = json.loads(installed.read_text(encoding="utf-8"))
                    if not isinstance(games, dict):
                        continue
                    matches = [
                        key for key, value in games.items()
                        if isinstance(value, dict) and value.get("title") == requested_title
                        and _HEROIC_ID.fullmatch(str(key))
                    ]
                    if len(matches) == 1:
                        appid = matches[0]
                        break
                except (OSError, UnicodeError, ValueError):
                    continue
    if not isinstance(appid, (str, int)) or not _HEROIC_ID.fullmatch(str(appid)):
        return
    for root in _heroic_art_roots():
        for suffix in ("jpg", "png", "webp", "jpeg"):
            path = root / "icons" / f"{appid}.{suffix}"
            yield path, "Heroic local cover artwork"


def locate_artwork(recipe: dict) -> ArtworkChoice:
    """Resolve only a known local, decodable file; fallback is original art."""
    imported = custom_artwork_path(recipe)
    if _valid_local_image(imported):
        return ArtworkChoice(imported, "Your custom banner", True)
    for path, source in _steam_candidates(recipe):
        if _valid_local_image(path):
            return ArtworkChoice(path, source)
    for path, source in _heroic_candidates(recipe):
        if _valid_local_image(path):
            return ArtworkChoice(path, source)
    return ArtworkChoice(None, "NAnnersVRhub original banner")


def import_banner(recipe: dict, selected: str | Path) -> Path:
    """Copy a validated image into the Hub's own folder, atomically.

    The source is never renamed, edited, removed, or otherwise modified.
    No image can escape the Hub's per-game target via a recipe ID.
    """
    _game_id(recipe)
    src = Path(selected).expanduser()
    if src.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Choose a JPG, PNG or WebP artwork image.")
    try:
        if not src.is_file():
            raise ValueError("The selected artwork file does not exist.")
        if src.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("Artwork file is too large (25 MB limit).")
        reader = QImageReader(str(src))
        reader.setAutoTransform(True)
        if not reader.canRead():
            raise ValueError("That image is not supported or cannot be decoded.")
        dimensions = reader.size()
        if (not dimensions.isValid()
                or dimensions.width() * dimensions.height() > MAX_IMAGE_PIXELS):
            raise ValueError("Artwork dimensions are invalid or too large.")
        image = reader.read()
        if image.isNull():
            raise ValueError("Could not decode the selected artwork.")
        image = image.scaled(
            MAX_BANNER_WIDTH, MAX_BANNER_HEIGHT,
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if image.isNull():
            raise ValueError("Artwork scaling failed.")

        dest = custom_artwork_path(recipe)
        dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = QSaveFile(str(dest))
        target.setDirectWriteFallback(False)
        if not target.open(QIODevice.WriteOnly):
            raise OSError(f"Cannot save custom artwork to the Hub's data folder: {target.errorString()}")
        if not image.save(target, "PNG"):
            target.cancelWriting()
            raise OSError("Could not encode the artwork as PNG.")
        if not target.commit():
            raise OSError(f"Could not save the artwork: {target.errorString()}")
        os.chmod(dest, 0o600)
        return dest
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not import artwork: {exc}") from exc


def restore_default(recipe: dict) -> bool:
    """Remove only this game's Hub-owned custom copy, not the source image."""
    dest = custom_artwork_path(recipe)
    if not dest.is_symlink() and not dest.is_file():
        return False
    dest.unlink()
    return True
