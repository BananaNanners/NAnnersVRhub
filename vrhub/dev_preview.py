# SPDX-License-Identifier: GPL-3.0-only
"""Explicit, isolated development review entry point."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    from . import fatekeeper_commit
    if fatekeeper_commit.live_install_authorized():
        raise RuntimeError("Preview requires the closed production gate.")
    root = Path(__file__).resolve().parent.parent
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args],
                                       text=True).strip()
    checkpoint = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    if dirty:
        raise RuntimeError("Commit or review working tree changes before preview.")
    from .dev_preview_storage import activate_desktop_preview
    storage = activate_desktop_preview()
    from .preview_policy import ReadOnlyPreview
    from PySide6.QtWidgets import QApplication
    app = QApplication([sys.argv[0]])
    win = ReadOnlyPreview()
    win.setWindowTitle("NAnnersVRhub — Development — READ-ONLY PREVIEW")
    win.show()
    win.apply_preview_policy()
    print(f"PREVIEW PID={os.getpid()} CHECKPOINT={checkpoint} "
          f"STATE={storage['state']}", flush=True)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Preview not started: {exc}", file=sys.stderr)
        sys.exit(1)
