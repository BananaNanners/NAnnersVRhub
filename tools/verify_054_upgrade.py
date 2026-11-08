# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Isolated real-installer upgrade/rollback check; requires Python with PySide6.

Usage: python tools/verify_054_upgrade.py --stable-source /path/to/v0.5.3
Uses disposable fixtures only; never launches a game or downloads a bridge.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable-source", "--from-source", type=Path, required=True)
    parser.add_argument("--from-version", default="0.5.3")
    args = parser.parse_args()
    candidate = Path(__file__).resolve().parents[1]
    stable = args.stable_source.resolve()
    sys.path.insert(0, str(candidate))
    from vrhub import __version__, hub, self_install, live_tests

    assert self_install._version(stable / "vrhub") == args.from_version
    assert self_install._version(candidate / "vrhub") == __version__
    preserved_paths = ["vrhub/kharvox_bridge.py", "vrhub/kharvox_component.py", "vrhub/bridge_installer.py",
                       "vrhub/kharvox.py", "vrhub/handlers.py"]
    preserved_paths += [p.relative_to(stable).as_posix() for folder in ("recipes", "controls")
                        for p in (stable / "vrhub" / folder).glob("*.toml")]
    license_headers = (b"# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors\n",
                       b"# SPDX-License-Identifier: GPL-3.0-only\n")
    header_only_changes = []
    def without_license_headers(data):
        return b"".join(line for line in data.splitlines(keepends=True) if line not in license_headers)
    for name in preserved_paths:
        before, after = (stable / name).read_bytes(), (candidate / name).read_bytes()
        assert without_license_headers(before) == without_license_headers(after), name
        if before != after:
            header_only_changes.append(name)

    with tempfile.TemporaryDirectory(prefix="nanners-054-upgrade-") as temporary:
        home = Path(temporary) / "Home with spaces"
        state = home / ".local/share/vrhub/state.json"
        state.parent.mkdir(parents=True)
        env = {"HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share"),
               "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
               "VRHUB_STATE": str(state), "_NANNERSVRHUB_ROOT": "",
               "QT_QPA_PLATFORM": "offscreen", "PYTHONDONTWRITEBYTECODE": "1"}
        with patch.dict(os.environ, env):
            recipes = hub.load_recipes()
            assert len(recipes) == 9
            state.write_text(json.dumps({rid: {"files": [], "fixture": "existing record"} for rid in recipes}))
            live_tests.record(recipes["fatekeeper"], "success", "Preserve this fixture history",
                              {key: "passed" for key in live_tests.CHECKS},
                              {"recipe_id": "fatekeeper", "hub_version": args.from_version, "status": "REVIEW REQUIRED",
                               "checks": [], "profile": {}})
            sentinels = {state.parent / "backups/original.pak": b"original mod backup",
                         home / "Games/fixture/save.dat": b"fixture save bytes",
                         home / ".local/share/nanners-kharvox-lab/0.1.0/runner.json": b"existing runner fixture",
                         home / ".local/share/nanners-kharvox-lab/0.1.0/probe-pass.json": b"existing probe fixture",
                         home / ".config/heroic/GamesConfig/fixture.json": b"original Heroic runner selection"}
            for path, data in sentinels.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            sentinels.update({state: state.read_bytes(), live_tests.history_file(): live_tests.history_file().read_bytes()})
            root = self_install.default_root()

            def check_files():
                for path, expected in sentinels.items():
                    assert path.read_bytes() == expected, str(path)

            def command(*arguments):
                run = subprocess.run([str(root / "bin/nannersvrhub"), *arguments], cwd=temporary,
                                     capture_output=True, text=True, timeout=20)
                assert run.returncode == 0, run.stderr
                return run.stdout

            self_install.install(stable, root)
            assert command("--version").strip() == "NAnnersVRhub " + args.from_version
            check_files()
            self_install.install(candidate, root)
            assert command("--version").strip() == "NAnnersVRhub " + __version__
            record = json.loads((root / "installation.json").read_text())
            installed = root / "releases" / record["current"]
            assert (installed / "vrhub/pak.py").is_file()
            assert not (installed / "vrhub/assets/kharvox-lab-0.1.6").exists()
            for recipe in recipes.values():
                assert recipe["name"] in command("info", recipe["id"])
            check_files()
            self_install.rollback(root)
            assert command("--version").strip() == "NAnnersVRhub " + args.from_version
            check_files()
            self_install.rollback(root)
            assert command("--version").strip() == "NAnnersVRhub " + __version__
            check_files()

    print(json.dumps({"status": "passed", "from": args.from_version, "to": __version__, "recipes": 9,
                      "real_dependency_probes": True, "upgrade_and_two_way_rollback": True,
                      "fixture_files_preserved": len(sentinels), "unchanged_bridge_and_recipe_files": {
                          n: hashlib.sha256((candidate / n).read_bytes()).hexdigest() for n in preserved_paths},
                      "license_header_only_changes": header_only_changes, "bridge_download_or_game_launch": False}, indent=2))


if __name__ == "__main__":
    main()
