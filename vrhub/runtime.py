"""Check which OpenXR runtime is active (we want WiVRn)."""
import json
import os
from pathlib import Path


def active_runtime() -> tuple[Path | None, str]:
    """Return (active_runtime.json path, runtime library path)."""
    cands = []
    if os.environ.get("XR_RUNTIME_JSON"):
        cands.append(Path(os.environ["XR_RUNTIME_JSON"]))
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    cands += [cfg / "openxr/1/active_runtime.json",
              Path("/etc/xdg/openxr/1/active_runtime.json")]
    for c in cands:
        if c.is_file():
            try:
                lib = json.loads(c.read_text())["runtime"]["library_path"]
            except (ValueError, KeyError, TypeError):
                lib = ""
            return c, lib
    return None, ""


def is_wivrn() -> bool:
    path, lib = active_runtime()
    return bool(path) and "wivrn" in f"{path.resolve()} {lib}".lower()
