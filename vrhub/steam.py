"""Find Steam libraries and installed games on Linux."""
import re
from pathlib import Path

STEAM_ROOTS = [
    "~/.local/share/Steam",
    "~/.steam/steam",
    "~/.var/app/com.valvesoftware.Steam/.local/share/Steam",  # Flatpak
]

_TOKEN = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')


def parse_vdf(text: str) -> dict:
    """Minimal parser for Valve's KeyValues (VDF/ACF) format."""
    stack, key = [{}], None
    for s, brace in _TOKEN.findall(text):
        if brace == "{":
            new = {}
            stack[-1][key] = new
            stack.append(new)
            key = None
        elif brace == "}":
            stack.pop()
        else:
            s = s.replace("\\\\", "\\")
            if key is None:
                key = s
            else:
                stack[-1][key] = s
                key = None
    return stack[0]


def steam_libraries(roots=None) -> list[Path]:
    libs: list[Path] = []
    for root in roots or STEAM_ROOTS:
        root = Path(root).expanduser()
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        entries = parse_vdf(vdf.read_text(errors="replace")).get("libraryfolders", {})
        paths = [root] + [
            Path(v["path"] if isinstance(v, dict) else v) for v in entries.values()
            if (v.get("path") if isinstance(v, dict) else v)
        ]
        for p in paths:
            p = p.resolve()
            if p not in libs and (p / "steamapps").is_dir():
                libs.append(p)
    return libs


def find_game(appid: int, roots=None) -> Path | None:
    for lib in steam_libraries(roots):
        manifest = lib / "steamapps" / f"appmanifest_{appid}.acf"
        if manifest.is_file():
            state = parse_vdf(manifest.read_text(errors="replace")).get("AppState", {})
            if state.get("installdir"):
                game = lib / "steamapps" / "common" / state["installdir"]
                if game.is_dir():
                    return game
    return None
