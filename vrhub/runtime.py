"""Discover the selected Linux OpenXR runtime without starting it."""
import json
import os
import platform
from pathlib import Path


def runtime_candidates() -> list[Path]:
    """Follow loader precedence; a broken explicit override cannot fall back."""
    if os.environ.get("XR_RUNTIME_JSON"):
        return [Path(os.environ["XR_RUNTIME_JSON"])]
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))
    dirs = [cfg, *[Path(p) for p in (os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg").split(":") if p], Path("/etc")]
    arch = {"AMD64": "x86_64", "arm64": "aarch64"}.get(platform.machine(), platform.machine())
    return [base / "openxr/1" / name for base in dict.fromkeys(dirs)
            for name in (f"active_runtime.{arch}.json", "active_runtime.json")]


def selected_manifest() -> Path | None:
    for path in runtime_candidates():
        if os.environ.get("XR_RUNTIME_JSON") or path.exists() or path.is_symlink():
            return path
    return None


def active_runtime() -> tuple[Path | None, str]:
    """Return selected manifest and library; invalid manifests have no library."""
    path = selected_manifest()
    if path is None:
        return None, ""
    try:
        data = json.loads(path.read_text())
        lib = data["runtime"]["library_path"]
        if data.get("file_format_version") != "1.0.0" or not isinstance(lib, str) or not lib.strip():
            lib = ""
    except (OSError, ValueError, KeyError, TypeError):
        lib = ""
    return path, lib


def runtime_name(path: Path | None, lib: str) -> str:
    try:
        target = path.resolve() if path else ""
    except OSError:
        target = path or ""
    # The library's identity wins over a misleading custom manifest directory.
    for hint in (lib.lower(), str(target).lower()):
        for needle, name in (("wivrn", "WiVRn"), ("steamxr", "SteamVR"),
                             ("steamvr", "SteamVR"), ("monado", "Monado")):
            if needle in hint:
                return name
    return "Other OpenXR" if lib else "Not configured"


def is_wivrn() -> bool:
    path, lib = active_runtime()
    return bool(lib) and runtime_name(path, lib) == "WiVRn"
