#!/usr/bin/env python3
"""Offline per-user source installer. Does not install Python or Qt packages."""
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print("NAnnersVRhub needs Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(1)

from vrhub.self_install import main

raise SystemExit(main(["install", "--source", str(Path(__file__).resolve().parent), *sys.argv[1:]]))
