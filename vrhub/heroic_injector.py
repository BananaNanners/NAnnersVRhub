"""Launch the installed UEVR injector with an existing native Heroic runner.

Heroic's runExe IPC is private. Follow its runWineCommand runner selection,
using runinprefix for this secondary executable, without a game-launch URI.
Sources inspected 2026-10-19: Heroic backend/launcher.ts and
backend/utils/compatibility_layers.ts; umu-launcher docs/umu.1.scd.
"""
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from . import heroic_epic

_launches = {}
_lock = threading.Lock()
TAIL_LIMIT = 65536


def _executable(path):
    return path.is_absolute() and path.is_file() and os.access(path, os.X_OK)


def plan(info, exe):
    """Return argv/environment only; never initialize or repair a prefix."""
    if info["flatpak"] or os.environ.get("FLATPAK_ID"):
        raise RuntimeError("One-click injection currently supports native Heroic. Use Heroic's Run EXE on prefix for this Flatpak installation.")
    pfx = heroic_epic.prefix(info)
    exe = Path(exe).resolve()
    if not exe.is_relative_to(pfx) or not exe.is_file() or exe.name != "UEVRInjector.exe":
        raise RuntimeError("The installed UEVR injector is missing or outside this game's prefix.")
    wine = info["wine"]
    kind, binary = wine.get("type"), wine.get("bin")
    runner = Path(binary).expanduser() if isinstance(binary, str) and binary else Path()
    if kind not in {"wine", "proton"} or not _executable(runner):
        raise RuntimeError("Heroic's selected Wine/Proton runner is unavailable on the host. Review it in Heroic or use Run EXE on prefix.")
    settings = info["settings"]
    env = dict(os.environ)
    # A Hub launched from Steam/another game must not target its prefix or IDs.
    for key in list(env):
        if key.startswith("STEAM_COMPAT_") or key in {
            "WINEPREFIX", "WINEARCH", "WINESERVER", "WINELOADER", "WINEDLLOVERRIDES",
            "WINEESYNC", "WINEFSYNC", "PROTON_NO_ESYNC", "PROTON_NO_FSYNC",
            "PROTONPATH", "PROTON_VERB", "SteamAppId", "SteamGameId", "GAMEID", "STORE",
            "UMU_NO_PROTON",
        }:
            env.pop(key, None)
    options = settings.get("enviromentOptions", [])  # Heroic's spelling
    if not isinstance(options, list):
        raise RuntimeError("Heroic's saved environment settings are invalid. Open/save them in Heroic and retry.")
    for row in options:
        if not isinstance(row, dict) or not isinstance(row.get("key"), str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", row["key"]) or not isinstance(row.get("value"), str) or "\0" in row["value"]:
            raise RuntimeError("Heroic's saved environment settings are invalid. Open/save them in Heroic and retry.")
        value = row["value"]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[row["key"]] = value
    env["WINEPREFIX"] = str(pfx)
    env["STEAM_COMPAT_INSTALL_PATH"] = str(info["game"])
    env.setdefault("PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES", "1")
    for setting, wine_key, proton_key in (("enableEsync", "WINEESYNC", "PROTON_NO_ESYNC"),
                                          ("enableFsync", "WINEFSYNC", "PROTON_NO_FSYNC")):
        if isinstance(settings.get(setting), bool):
            key = proton_key if kind == "proton" else wine_key
            if kind == "proton" and settings[setting]:
                env.pop(key, None)
            else:
                env[key] = "1" if kind == "proton" else str(int(settings[setting]))
    if kind == "wine":
        env["WINEDLLOVERRIDES"] = env.get("WINEDLLOVERRIDES", "").rstrip(";") + ";winemenubuilder.exe=d"
        return [str(runner), str(exe)], env
    # Always pin the recorded build, never an umu auto-download alias.
    # umu hashes WINEPREFIX to locate the game's container. Keep Heroic's
    # configured compatdata root, including when drive_c is inside root/pfx.
    env.update(WINEPREFIX=str(Path(settings["winePrefix"]).expanduser()),
               PROTONPATH=str(runner.parent), PROTON_VERB="runinprefix",
               STEAM_COMPAT_DATA_PATH=str(Path(settings["winePrefix"]).expanduser()),
               STEAM_COMPAT_CLIENT_INSTALL_PATH=str(Path.home() / ".steam/steam"),
               STEAM_COMPAT_APP_ID="0", SteamAppId="0", SteamGameId="0",
               GAMEID="0", STORE="egs", UMU_RUNTIME_UPDATE="0")
    env.pop("UMU_NO_PROTON", None)
    umu = shutil.which("umu-run")
    if not umu:
        bundled = info["root"] / "tools/runtimes/umu/umu_run.py"
        if _executable(bundled):
            umu = str(bundled)
    if settings.get("disableUMU") is not True and umu:
        # Supported umu builds can re-enter the running game's container,
        # allowing the injector to see its process. Older builds ignore this.
        env["UMU_CONTAINER_NSENTER"] = "1"
        return [umu, str(exe)], env
    # Direct Proton needs its established compatdata/pfx mapping. Do not let
    # Proton create a new nested prefix in an existing direct Wine layout.
    data = Path(env["STEAM_COMPAT_DATA_PATH"])
    if not (data / "pfx/drive_c").is_dir() or (data / "pfx").resolve() != pfx:
        raise RuntimeError("This Proton prefix needs Heroic/umu to keep its existing layout. Use Heroic's Run EXE on prefix; the Hub did not create a nested prefix.")
    return [str(runner), "runinprefix", str(exe)], env


class InjectorLaunch:
    """Detached launcher with a bounded output tail, independent of Qt lifetime."""
    def __init__(self, args, env, cwd):
        self.process = subprocess.Popen(args, env=env, cwd=cwd, start_new_session=True,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
        self.pid = self.process.pid
        self._tail = b""
        self._tail_lock = threading.Lock()
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    def _drain(self):
        try:
            while block := self.process.stdout.read1(4096):
                with self._tail_lock:
                    self._tail = (self._tail + block)[-TAIL_LIMIT:]
        finally:
            self.process.stdout.close()
            self.process.wait()

    def poll(self):
        result = self.process.poll()
        return result if result is not None and not self._reader.is_alive() else None

    def output_tail(self):
        with self._tail_lock:
            return self._tail.decode("utf-8", errors="replace")


def launch(info, exe):
    key = str(heroic_epic.prefix(info))
    with _lock:
        previous = _launches.get(key)
        if previous and previous.poll() is None:
            return previous
        args, env = plan(info, exe)
        result = InjectorLaunch(args, env, str(Path(exe).parent))
        _launches[key] = result
        return result
