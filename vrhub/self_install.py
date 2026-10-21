"""Offline per-user application deployment. Game data and Hub state are never copied.

Only installation.json selects the active release. Launchers resolve its immutable
release directory once per process, so switching versions cannot mix Python files.
This module is also copied outside releases as the independent rollback manager.
"""
import argparse
import ast
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

SCHEMA = 1
OWNER = "NAnnersVRhub managed application files; schema=1\n"
CORE_RECIPES = {"skyrim-vr-mgo", "fatekeeper", "ready-or-not", "cyberpunk-2077"}
EXPECTED_RECIPES = CORE_RECIPES | {"hogwarts-legacy", "subnautica", "valheim", "elden-ring", "doom-2016-gog"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}-[a-f0-9]{16}\Z")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

BOOTSTRAP = '''"""Stable managed launcher: resolve one complete release before importing it."""
import json, os, sys
from pathlib import Path

root = Path(__file__).resolve().parent
mode, args = sys.argv[1], sys.argv[2:]
os.environ["_NANNERSVRHUB_ROOT"] = str(root)
try:
    data = json.loads((root / "installation.json").read_text())
    if data.get("schema") != 1:
        raise RuntimeError("Unsupported installation record")
    release = (root / "releases" / data["current"]).resolve(strict=True)
    if release.parent != (root / "releases").resolve():
        raise RuntimeError("Invalid active release path")
    sys.path.insert(0, str(release))
    if mode == "guard" and args and args[0] == "elden-ring":
        # An older release's generic guard may pass unknown games through.
        # Resolve this adapter explicitly so rollback cannot start EAC instead.
        from vrhub.elden_ring import main as launch_elden_ring
        def main():
            return launch_elden_ring(args[1:])
    elif mode == "guard":
        from vrhub.guard import main
    else:
        from vrhub.launcher import main
except Exception as exc:
    print(f"NAnnersVRhub launcher unavailable: {exc}", file=sys.stderr)
    if mode == "guard" and len(args) >= 2 and args[0] != "elden-ring":
        os.execvp(args[1], args[1:])
    print("Use nannersvrhub-manage status or rollback from a terminal.", file=sys.stderr)
    raise SystemExit(1)
sys.argv = ["nannersvrhub-check" if mode == "guard" else "nannersvrhub", *args]
raise SystemExit(main())
'''

PROBE = '''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from vrhub import __version__, hub
from vrhub.theme import LOGO_PATH
from PySide6 import __version__ as qt_version
from PySide6.QtWidgets import QApplication
from vrhub.gui import HubWindow
assert LOGO_PATH.is_file(), "Packaged icon is missing"
if (Path(sys.argv[1]) / "vrhub/controller_bindings.py").is_file():
    from vrhub import controller_bindings
    for rid in hub.load_recipes():
        assert controller_bindings.load(rid), "Packaged controller guide is missing: " + rid
print(json.dumps({"version":__version__, "recipes":sorted(hub.load_recipes()), "qt":qt_version}))
'''


def data_home() -> Path:
    value = os.environ.get("XDG_DATA_HOME", "")
    return Path(value) if value and Path(value).is_absolute() else Path.home() / ".local/share"


def default_root() -> Path:
    return Path(os.environ.get("_NANNERSVRHUB_ROOT") or data_home() / "nannersvrhub")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic(path: Path, data: bytes, mode=0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), mode)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def _read_record(root: Path) -> dict | None:
    path = root / "installation.json"
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        raise RuntimeError("Installation record must not be a symlink.")
    try:
        record = json.loads(path.read_text())
        if record["schema"] != SCHEMA or not ID.fullmatch(record["current"]):
            raise ValueError("unsupported schema or active release")
        if record.get("previous") is not None and not ID.fullmatch(record["previous"]):
            raise ValueError("invalid previous release")
        if not isinstance(record["artifacts"], dict) or not Path(record["python"]).is_absolute():
            raise ValueError("invalid installation metadata")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Cannot read installation record; preserved unchanged: {exc}") from exc
    return record


@contextlib.contextmanager
def _locked(root: Path):
    if root.is_symlink():
        raise RuntimeError("Managed app root must not be a symlink.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    allowed = {".install.lock"}
    owner = root / ".owner"
    if owner.is_symlink() or (owner.exists() and owner.read_text() != OWNER):
        raise RuntimeError("This folder is not a recognized NAnnersVRhub installation.")
    if not owner.exists() and any(p.name not in allowed for p in root.iterdir()):
        raise RuntimeError("Install folder is not empty; existing contents were preserved.")
    fd = os.open(root / ".install.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another NAnnersVRhub install/rollback is running.") from exc
        if not owner.exists():
            _atomic(owner, OWNER.encode())
        yield
    finally:
        os.close(fd)


def _version(package: Path) -> str:
    module = ast.parse((package / "__init__.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and VERSION.fullmatch(version):
                return version
    raise RuntimeError("Missing or invalid application version.")


def _source_files(source: Path) -> tuple[str, dict[str, bytes]]:
    package = source / "vrhub"
    if package.is_symlink() or not package.is_dir():
        raise RuntimeError("Choose an extracted source folder containing vrhub/.")
    files = {}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Source package contains a symlink: {path}")
        if '__pycache__' in path.relative_to(package).parts or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.is_file() and (path.suffix in {".py", ".png", ".toml"}):
            files[path.relative_to(source).as_posix()] = path.read_bytes()
    version = _version(package)
    project = tomllib.loads((source / "pyproject.toml").read_text())
    if project["project"]["version"] != version:
        raise RuntimeError("Project and runtime version labels do not match.")
    # New releases declare their own inventory. Legacy four-game source ZIPs
    # remain downloadable/verifiable, and future recipe additions need no cap.
    tool = project.get("tool", {})
    config = tool.get("nannersvrhub", {}) if isinstance(tool, dict) else None
    if not isinstance(config, dict):
        raise RuntimeError("Invalid packaged recipe inventory.")
    recipes = config.get("required_recipes", sorted(CORE_RECIPES))
    if (not isinstance(recipes, list) or any(not isinstance(rid, str) or not re.fullmatch(r"[a-z0-9-]+", rid) for rid in recipes)
            or not CORE_RECIPES.issubset(recipes) or len(recipes) != len(set(recipes))):
        raise RuntimeError("Invalid packaged recipe inventory.")
    required = {"vrhub/gui.py", "vrhub/cli.py", "vrhub/launcher.py", "vrhub/guard.py", "vrhub/self_install.py",
                "vrhub/assets/bananananners.png", *{f"vrhub/recipes/{rid}.toml" for rid in recipes}}
    guides = config.get("required_controller_guides")
    if guides is not None:
        if not isinstance(guides, list) or any(not isinstance(rid, str) for rid in guides) or sorted(guides) != sorted(recipes):
            raise RuntimeError("Invalid packaged controller guide inventory.")
        required.update({"vrhub/controller_bindings.py", "vrhub/controller_gui.py",
                         *{f"vrhub/controls/{rid}.toml" for rid in guides}})
    if missing := required - files.keys():
        raise RuntimeError("Incomplete source folder: " + ", ".join(sorted(missing)))
    if config.get('required_kharvox_installer'):
        bridge_files = {'vrhub/bridge_installer.py', 'vrhub/kharvox_component.py', 'vrhub/kharvox_bridge.py'}
        if config['required_kharvox_installer'] != '0.2.0' or not bridge_files.issubset(files):
            raise RuntimeError('Incomplete source folder: DOOM bridge installer modules are missing.')
    for name in ("pyproject.toml", "README.md", "INSTALL-0.5.1.md", "TROUBLESHOOTING.md", "UPDATE-TESTING-0.5.2-dev1.md", "HOGWARTS-TESTING-0.5.2-dev2.md", "HOGWARTS-HEROIC-0.5.2-dev3.md", "HOGWARTS-ONECLICK-0.5.2-dev4.md", "RELEASE-NOTES-0.5.2.md", "UPDATE-TESTING-0.5.2.md", "SUBNAUTICA-TESTING-0.5.3-dev1.md", "SUBNAUTICA-SUCCESS-0.5.3-dev2.md", "VALHEIM-TESTING-0.5.3-dev3.md", "CONTROLLER-GUIDES-0.5.3-dev4.md", "ELDEN-RING-TESTING-0.5.3-dev6.md", "DOOM-TESTING-0.5.3-dev8.md", "DOOM-HUB-TESTING-0.5.3-dev9.md", "BRIDGE-INSTALL-TESTING-0.5.3-dev10.md", "RELEASE-NOTES-0.5.3.md", "UPDATE-TESTING-0.5.3-rc1.md", "VALIDATION-0.5.3-rc1.md"):
        path = source / name
        if path.is_symlink():
            raise RuntimeError(f"Source documentation must not be a symlink: {path}")
        if path.is_file():
            files[name] = path.read_bytes()
    return version, files


def _probe(source: Path, python: str) -> dict:
    try:
        result = subprocess.run([python, "-I", "-B", "-c", PROBE, str(source)], capture_output=True,
                                text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Cannot check Python/Qt dependencies: {exc}") from exc
    if result.returncode:
        detail = "\n".join(result.stderr.strip().splitlines()[-3:])
        raise RuntimeError("Application dependency/resource check failed. Python 3.11+ and PySide6 are required.\n"
                           "On CachyOS/Arch: sudo pacman -S pyside6\n"
                           f"Run the installer with the Python that provides PySide6: {python}\n{detail}")
    try:
        info = json.loads(result.stdout)
        expected = {path.stem for path in (source / "vrhub/recipes").glob("*.toml")}
        if not CORE_RECIPES.issubset(expected) or set(info["recipes"]) != expected:
            raise ValueError("Packaged recipe files do not match the loaded game recipes")
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Application resource check failed: {exc}") from exc
    return info


def _desktop_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def _desktop_exec(path: Path) -> str:
    value = str(path).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return _desktop_string('"' + value + '"')


def _artifacts(root: Path, python: str, files: dict[str, bytes]) -> dict[Path, tuple[str, object, int]]:
    # Paths live outside the user's existing ~/.local/share/vrhub data directory.
    artifacts = {
        root / "run.py": ("file", BOOTSTRAP.encode(), 0o644),
        root / "manage.py": ("file", files["vrhub/self_install.py"], 0o644),
        root / "icon.png": ("file", files["vrhub/assets/bananananners.png"], 0o644),
    }
    for name, tail in {"nannersvrhub": "run.py app", "nannersvrhub-check": "run.py guard", "nannersvrhub-manage": "manage.py"}.items():
        script, *args = tail.split()
        content = "#!/bin/sh\nexport _NANNERSVRHUB_ROOT=" + shlex.quote(str(root)) + "\n"
        if name == "nannersvrhub-check":
            content += "if [ ! -x " + shlex.quote(python) + " ]; then\n"
            content += '  if [ "$1" = "elden-ring" ]; then\n'
            content += '    echo "Elden Ring launch stopped: Hub Python unavailable." >&2\n    exit 1\n  fi\n'
            content += '  echo "NAnnersVRhub Python unavailable; starting game without verification." >&2\n'
            content += '  [ "$#" -ge 2 ] || exit 2\n  shift\n  exec "$@"\nfi\n'
        content += "exec "
        content += " ".join(shlex.quote(x) for x in [python, "-I", "-B", str(root / script), *args]) + ' "$@"\n'
        artifacts[root / "bin" / name] = ("file", content.encode(), 0o755)
        artifacts[Path.home() / ".local/bin" / name] = ("link", str(root / "bin" / name), 0)
    desktop = ("[Desktop Entry]\nType=Application\nName=NAnnersVRhub\n"
               "Comment=Linux VR compatibility and mod manager\n"
               # GIO checks the executable before expanding %% field escapes.
               # Put the possibly percent-containing user path in an argument.
               f"Exec=/usr/bin/env -- {_desktop_exec(root / 'bin/nannersvrhub')} --desktop\n"
               f"Icon={_desktop_string(str(root / 'icon.png'))}\n"
               "Terminal=false\nCategories=Game;Utility;\nStartupNotify=false\n"
               "X-NAnnersVRhub-Managed=true\n")
    artifacts[data_home() / "applications/io.github.BananaNanners.NAnnersVRhub.desktop"] = ("file", desktop.encode(), 0o644)
    return artifacts


def _snapshot(path: Path):
    if path.is_symlink():
        return ("link", os.readlink(path), 0)
    if path.exists():
        if not path.is_file():
            raise RuntimeError(f"Cannot replace a non-file: {path}")
        return ("file", path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
    return None


def _signature(snapshot):
    if snapshot is None:
        return None
    kind, value, mode = snapshot
    return {"kind": kind, "value": _sha(value) if kind == "file" else value}


def _apply(path: Path, snapshot) -> None:
    if snapshot is None:
        path.unlink(missing_ok=True)
    elif snapshot[0] == "file":
        _atomic(path, snapshot[1], snapshot[2])
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".link-", dir=path.parent)
        os.close(fd)
        Path(temp).unlink()
        try:
            os.symlink(snapshot[1], temp)
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)


def _activate(root: Path, record: dict, artifacts: dict) -> None:
    old = _read_record(root)
    previous = {p: _snapshot(p) for p in artifacts}
    for path, snapshot in previous.items():
        signature = _signature(snapshot)
        if signature is not None and signature not in (_signature(artifacts[path]), (old or {}).get("artifacts", {}).get(str(path))):
            raise RuntimeError(f"Existing launcher/desktop file was preserved: {path}\nMove or rename it before retrying.")
    record["artifacts"] = {str(p): _signature(value) for p, value in artifacts.items()}
    changed = []
    try:
        for path, value in artifacts.items():
            changed.append(path)
            _apply(path, value)
        _atomic(root / "installation.json", (json.dumps(record, indent=2) + "\n").encode())
    except BaseException:
        for path in reversed(changed):
            _apply(path, previous[path])
        raise


def _release(root: Path, release_id: str) -> tuple[Path, dict]:
    if not ID.fullmatch(release_id):
        raise RuntimeError("Invalid release identifier.")
    directory = root / "releases" / release_id
    if directory.is_symlink() or directory.resolve().parent != (root / "releases").resolve():
        raise RuntimeError("Release folder must stay within this installation.")
    manifest = json.loads((directory / ".release.json").read_text())
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or not isinstance(manifest.get("files"), dict):
        raise RuntimeError("Unsupported release inventory.")
    expected_id = str(manifest.get("version")) + "-" + _sha(json.dumps(manifest["files"], sort_keys=True).encode())[:16]
    if release_id != expected_id or "vrhub/__init__.py" not in manifest["files"]:
        raise RuntimeError("Release inventory does not match its identifier.")
    for name, digest in manifest["files"].items():
        path = directory / name
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise RuntimeError("Invalid path in release inventory.")
        if _sha(path.read_bytes()) != digest:
            raise RuntimeError(f"Installed application file changed; preserved: {path}")
    if _version(directory / "vrhub") != manifest["version"]:
        raise RuntimeError("Release inventory and application version do not match.")
    return directory, manifest


def install(source: Path, root: Path, *, check_only=False, expected_current=None) -> dict:
    source = source.expanduser().resolve()
    root = Path(os.path.abspath(root.expanduser()))
    if root == Path.home() or root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise RuntimeError("Application install folder must be separate from the source folder and home root.")
    state_dir = Path(os.environ.get("VRHUB_STATE", "~/.local/share/vrhub/state.json")).expanduser().resolve().parent
    resolved = root.resolve()
    if resolved == state_dir or resolved.is_relative_to(state_dir) or state_dir.is_relative_to(resolved):
        raise RuntimeError("Application files must stay separate from saved Hub state/history.")
    version, files = _source_files(source)
    python = str(Path(sys.executable).absolute())
    info = _probe(source, python)
    if info["version"] != version:
        raise RuntimeError("Dependency probe loaded a different application version.")
    hashes = {p: _sha(data) for p, data in sorted(files.items())}
    digest = _sha(json.dumps(hashes, sort_keys=True).encode())
    release_id = version + "-" + digest[:16]
    if check_only:
        return {"status": "CHECK PASSED", "version": version, "root": str(root), "python": python, **info}
    with _locked(root):
        old = _read_record(root)
        if expected_current is not None and (not old or old["current"] != expected_current):
            raise RuntimeError("The active Hub version changed. Restart the Hub before installing this update.")
        releases = root / "releases"
        if releases.is_symlink():
            raise RuntimeError("Release storage must not be a symlink.")
        releases.mkdir(exist_ok=True)
        target = releases / release_id
        created = False
        if target.exists() or target.is_symlink():
            _, manifest = _release(root, release_id)
            if manifest["files"] != hashes:
                raise RuntimeError("Release identifier collision; installed files were preserved.")
        else:
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=releases))
            try:
                for name, content in files.items():
                    path = staging / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    path.chmod(0o644)
                if _probe(staging, python)["version"] != version:
                    raise RuntimeError("Copied application version changed during preparation; active version was preserved.")
                manifest = {"schema": SCHEMA, "version": version, "files": hashes}
                _atomic(staging / ".release.json", (json.dumps(manifest, indent=2) + "\n").encode())
                staging.rename(target)
                created = True
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        record = {"schema": SCHEMA, "current": release_id,
                  "previous": old["previous"] if old and old["current"] == release_id else (old["current"] if old else None),
                  "python": python}
        try:
            _activate(root, record, _artifacts(root, python, files))
        except BaseException:
            if created:
                shutil.rmtree(target)
            raise
    return {"status": "INSTALLED", "version": version, "root": str(root), "previous": record["previous"]}


def rollback(root: Path) -> dict:
    root = root.expanduser().absolute()
    if _read_record(root) is None:
        raise RuntimeError("No previous managed app version is available. Saved data was not changed.")
    with _locked(root):
        old = _read_record(root)
        if not old or not old["previous"]:
            raise RuntimeError("No previous managed app version is available. Saved data was not changed.")
        directory, manifest = _release(root, old["previous"])
        _probe(directory, old["python"])
        files = {name: (directory / name).read_bytes() for name in manifest["files"]}
        record = {**old, "current": old["previous"], "previous": old["current"]}
        artifacts = _artifacts(root, old["python"], files)
        # Keep the current independent recovery manager across app rollback.
        # Older managers assumed exactly four recipes and cannot return to five.
        artifacts[root / "manage.py"] = ("file", (root / "manage.py").read_bytes(), 0o644)
        _activate(root, record, artifacts)
    return {"status": "ROLLED BACK", "version": manifest["version"], "root": str(root)}


def status(root: Path) -> dict:
    root = root.expanduser().absolute()
    record = _read_record(root)
    if record is None:
        return {"status": "NOT INSTALLED", "root": str(root)}
    _, manifest = _release(root, record["current"])
    return {"status": "INSTALLED", "version": manifest["version"], "root": str(root),
            "current": record["current"], "previous": record["previous"], "python": record["python"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Install or manage NAnnersVRhub itself; saved game/mod data stays in place.")
    parser.add_argument("--root", type=Path, default=default_root(), help="managed app folder (advanced)")
    sub = parser.add_subparsers(dest="command")
    for command in ("status", "rollback", "install"):
        p = sub.add_parser(command)
        p.add_argument("--root", type=Path, default=argparse.SUPPRESS)
        p.add_argument("--json", action="store_true")
        if command == "install":
            p.add_argument("--source", type=Path, required=True, help="extracted new source folder")
            p.add_argument("--check", action="store_true", help="check dependencies/resources without installing")
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            result = install(args.source, args.root, check_only=args.check)
        elif args.command == "rollback":
            result = rollback(args.root)
        else:
            result = status(args.root)
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            print(f"NAnnersVRhub: {result['status']}" + (f" — {result['version']}" if 'version' in result else ""))
            print(f"Application folder: {result['root']}")
            if args.command == "install" and not args.check:
                print("Launch: " + str(Path(result["root"]) / "bin/nannersvrhub"))
                print("Application menu: NAnnersVRhub")
                print("Steam guard: " + str(Path(result["root"]) / "bin/nannersvrhub-check"))
                if str(Path.home() / ".local/bin") not in os.environ.get("PATH", "").split(os.pathsep):
                    print("Optional fish command for short launch names: fish_add_path ~/.local/bin")
                print("Saved tests, mod records and game settings were left in place.")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, SyntaxError, TypeError) as exc:
        print(f"NAnnersVRhub: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
