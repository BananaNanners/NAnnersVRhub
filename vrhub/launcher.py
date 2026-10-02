"""Installed entry point: GUI with no arguments, CLI when arguments are supplied."""
import sys


def main() -> int:
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        return cli_main(sys.argv[1:])
    try:
        from .gui import main as gui_main
    except ImportError as e:
        if e.name == "PySide6":
            print("NAnnersVRhub GUI needs PySide6 (on CachyOS/Arch: sudo pacman -S pyside6).", file=sys.stderr)
            return 1
        raise
    return gui_main()

if __name__ == "__main__":
    raise SystemExit(main())
