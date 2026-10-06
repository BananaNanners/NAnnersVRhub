"""Small helper for forwarding a launch request into Jackify's running MO2.

Steam remains responsible for starting the primary MO2 process through the
Jackify-created non-Steam shortcut.  Once that process is visible, this helper
starts a short-lived second ModOrganizer.exe in the *same shortcut Proton
prefix*.  MO2's normal single-instance IPC forwards the moshortcut request to
the primary process, which then launches the configured SKSEVR entry.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def _write(log: Path, message: str) -> None:
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with log.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _mo2_running(mo2: Path) -> bool:
    """Best-effort Linux-side process check for the target ModOrganizer.exe."""
    target = str(mo2).lower()
    target_name = mo2.name.lower()
    proc = Path("/proc")
    if not proc.is_dir():
        return False
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        try:
            raw = (p / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        if not raw:
            continue
        text = raw.replace(b"\0", b" ").decode("utf-8", "replace").lower()
        # Proton/Wine may expose the path as Z:\home\... or as the Linux path.
        normalized = text.replace("\\", "/")
        if target in normalized or (target_name in normalized and "modorganizer" in normalized):
            return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steam", required=True)
    ap.add_argument("--uri", required=True)
    ap.add_argument("--proton", required=True)
    ap.add_argument("--compatdata", required=True)
    ap.add_argument("--steam-root", required=True)
    ap.add_argument("--mo2", required=True)
    ap.add_argument("--appid", required=True)
    ap.add_argument("--entry", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--timeout", type=float, default=45.0)
    a = ap.parse_args(argv)

    log = Path(a.log)
    mo2 = Path(a.mo2)
    _write(log, f"launch requested entry={a.entry!r} mo2={mo2}")

    if not _mo2_running(mo2):
        _write(log, f"MO2 not running; asking Steam to start {a.uri}")
        try:
            subprocess.Popen([a.steam, a.uri], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            _write(log, f"Steam launch failed: {e}")
            return 2
        deadline = time.monotonic() + a.timeout
        while time.monotonic() < deadline:
            if _mo2_running(mo2):
                break
            time.sleep(0.5)
        else:
            _write(log, f"MO2 did not appear within {a.timeout:.0f}s")
            return 3
        # Give the primary process a short moment to finish its single-instance
        # IPC setup before we launch the forwarding process.
        time.sleep(1.5)
    else:
        _write(log, "MO2 is already running")

    env = os.environ.copy()
    env.update({
        "STEAM_COMPAT_DATA_PATH": a.compatdata,
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": a.steam_root,
        "SteamAppId": a.appid,
        "SteamGameId": a.appid,
    })
    cmd = [a.proton, "run", str(mo2), f"moshortcut://:{a.entry}"]
    _write(log, "forwarding moshortcut through shortcut Proton prefix")
    try:
        cp = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired:
        # A forwarded secondary instance normally exits quickly. If it stays
        # alive, do not kill the primary MO2; just record the anomaly.
        _write(log, "forwarder did not exit within 30s; request may still have been accepted")
        return 4
    except OSError as e:
        _write(log, f"forwarder failed to start: {e}")
        return 5
    _write(log, f"forwarder exited code={cp.returncode}")
    return cp.returncode


if __name__ == "__main__":
    raise SystemExit(main())
