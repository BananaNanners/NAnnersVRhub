# SPDX-License-Identifier: GPL-3.0-only
"""Bounded OpenVR background-client telemetry; no rendering or runtime launch."""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__:
    from . import launch_environment

SOURCE = "SteamVR OpenVR IsTrackedDeviceConnected"
# Valve openvr_capi.h IVRSystem_026. Never guess another interface layout.
INTERFACE = b"FnTable:IVRSystem_026"
BACKGROUND = 3


def _unknown(detail):
    return dict(connected=None, system_name="", source=SOURCE, detail=detail)


def _query(library):
    """Executed only in a disposable child; native failures stay out of Qt."""
    api = C.CDLL(str(library))
    init = api.VR_InitInternal2
    init.argtypes = [C.POINTER(C.c_int), C.c_int, C.c_char_p]
    init.restype = C.c_uint32
    shutdown = api.VR_ShutdownInternal
    shutdown.argtypes = []
    shutdown.restype = None
    get = api.VR_GetGenericInterface
    get.argtypes = [C.c_char_p, C.POINTER(C.c_int)]
    get.restype = C.c_void_p
    err = C.c_int()
    init(C.byref(err), BACKGROUND, None)
    if err.value:
        return _unknown(f"SteamVR background client unavailable (OpenVR error {err.value}).")
    try:
        ptr = get(INTERFACE, C.byref(err))
        if err.value or not ptr:
            return _unknown("SteamVR does not expose the supported OpenVR system interface.")
        table = C.cast(ptr, C.POINTER(C.c_void_p))
        if not table[21]:
            return _unknown("SteamVR connection query is unavailable.")
        connected = bool(C.CFUNCTYPE(C.c_bool, C.c_uint32)(table[21])(0))
        name = ""
        if connected and table[28]:
            prop = C.CFUNCTYPE(C.c_uint32, C.c_uint32, C.c_int, C.c_void_p, C.c_uint32, C.POINTER(C.c_int))(table[28])
            buf = C.create_string_buffer(256)
            error = C.c_int()
            n = prop(0, 1001, buf, len(buf), C.byref(error))
            if not error.value and 0 < n <= len(buf):
                name = "".join(c for c in buf.value.decode("utf-8", errors="replace") if c.isprintable())[:160]
        return dict(connected=connected, system_name=name, source=SOURCE,
                    detail="SteamVR reports a connected headset." if connected else "SteamVR reports no connected headset.")
    finally:
        shutdown()


def read_status(manifest, library, *, server_observed=False):
    """Only use the selected SteamVR installation, never an arbitrary OpenVR adapter."""
    if not server_observed:
        return _unknown("SteamVR server not observed; headset connection was not queried.")
    try:
        client = Path(library)
        if not client.is_absolute():
            client = Path(manifest).resolve().parent / client
        client = client.resolve(strict=True)
        root = client.parents[2]
        if (client.name != "vrclient.so" or client.parent.name != "linux64"
                or client.parent.parent.name != "bin" or root.name != "SteamVR"):
            return _unknown("Selected SteamVR client path could not be validated.")
        api = client.parent / "libopenvr_api.so"
        if not api.is_file() or api.resolve().parent != client.parent:
            return _unknown("SteamVR OpenVR client library is unavailable.")
        env = launch_environment.child_environment()
        # Force this exact runtime for this child only; do not modify registry.
        env["VR_OVERRIDE"] = str(root)
        env.pop("VR_PATHREG_OVERRIDE", None)
        proc = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), str(api)],
                              env=env, capture_output=True, text=True, timeout=2.5, check=False)
        if proc.returncode or len(proc.stdout) > 4096:
            return _unknown("SteamVR background query failed; connection remains unknown.")
        value = json.loads(proc.stdout)
        if (not isinstance(value, dict) or set(value) != {"connected", "system_name", "source", "detail"}
                or (value["connected"] is not None and type(value["connected"]) is not bool)
                or value["source"] != SOURCE or not all(isinstance(value[k], str) for k in ("system_name", "detail"))):
            return _unknown("SteamVR status reply was invalid.")
        return value
    except (OSError, ValueError, TypeError, IndexError, subprocess.TimeoutExpired):
        return _unknown("SteamVR background query unavailable or timed out.")


if __name__ == "__main__":
    try:
        print(json.dumps(_query(Path(sys.argv[1]))))
    except (OSError, AttributeError, ValueError, IndexError):
        print(json.dumps(_unknown("SteamVR native client unavailable.")))
