"""Runtime paths for source, wheel and managed installations."""
import os
import sysconfig
from pathlib import Path


def guard_path() -> Path:
    managed = os.environ.get("_NANNERSVRHUB_ROOT")
    if managed:
        path = Path(managed) / "bin/nannersvrhub-check"
        if path.is_file():
            return path
    source_guard = Path(__file__).resolve().parent.parent / "vrhub-check"
    if source_guard.is_file():
        return source_guard
    return Path(sysconfig.get_path("scripts")) / "nannersvrhub-check"
