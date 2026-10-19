"""Installed entry point: GUI with no arguments, CLI when arguments are supplied."""
import shutil
import subprocess
import sys

from . import __version__


def main() -> int:
    args = sys.argv[1:]
    desktop = args == ["--desktop"]
    if desktop:
        sys.argv[1:] = []
    if args == ["--version"]:
        print("NAnnersVRhub " + __version__)
        return 0
    if args and not desktop:
        from .cli import main as cli_main
        return cli_main(args)
    try:
        from PySide6.QtWidgets import QApplication  # check Qt before importing the application
    except (ImportError, OSError) as exc:
        message = "NAnnersVRhub GUI needs working PySide6 (on CachyOS/Arch: sudo pacman -S pyside6)."
        print(message + "\n" + str(exc), file=sys.stderr)
        if desktop and (notify := shutil.which("notify-send")):
            try:
                subprocess.run([notify, "NAnnersVRhub dependency missing", message], timeout=2, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return 1
    from .gui import main as gui_main
    return gui_main()

if __name__ == "__main__":
    raise SystemExit(main())
