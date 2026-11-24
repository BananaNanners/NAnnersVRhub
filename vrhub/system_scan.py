# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only host VR inventory. Never starts a runtime or an OpenXR session."""
import ctypes.util
import copy
import html
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, runtime, wivrn_status, steamvr_status
from .display_time import local_time
from .steam import STEAM_ROOTS

# Only these relevant settings are included; never export the entire environment.
ENV_KEYS = ("XR_RUNTIME_JSON", "VR_OVERRIDE", "PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES",
            "PRESSURE_VESSEL_FILESYSTEMS_RW", "STEAM_COMPAT_MOUNTS")


def _process_names(proc: Path = Path("/proc")) -> set[str] | None:
    """Inspect this user's process names, without collecting command lines."""
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    names = set()
    readable = False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            names.add((entry / "comm").read_text().strip())
            readable = True
            try:
                names.add((entry / "exe").readlink().name)
            except OSError:
                pass
        except OSError:
            continue
    return names if readable else None


def _adapter_paths() -> tuple[list[Path], str]:
    """Configured OpenVR paths plus a small inventory of known host locations."""
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))
    override = os.environ.get("VR_OVERRIDE")
    if override:
        return [Path(override).expanduser()], "VR_OVERRIDE"
    paths = []
    try:
        data = json.loads((cfg / "openvr/openvrpaths.vrpath").read_text())
        runtimes = data["runtime"]
        paths = [Path(p) for p in runtimes if isinstance(p, str) and p] if isinstance(runtimes, list) else []
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return paths, "openvrpaths.vrpath"


def _adapter_name(path: Path) -> str:
    try:
        hint = str(path.resolve()).lower()
    except OSError:
        hint = str(path).lower()
    if "xrizer" in hint:
        return "xrizer"
    if "opencomposite" in hint or "open-composite" in hint or "openovr" in hint:
        return "OpenComposite"
    return "OpenVR runtime"


def _has_adapter(path: Path) -> bool:
    return any((path / suffix).is_file() for suffix in
               ("bin/linux64/vrclient.so", "lib/vrclient.so", "vrclient.so"))



def _live_snapshot(name: str, selected: bool, path=None, lib="") -> tuple[dict, list[dict]]:
    """Sample connection evidence independently of runtime-selection evidence."""
    rows = []

    def add(key, label, status, detail, action=""):
        rows.append(dict(id=key, name=label, status=status, detail=detail, action=action, required=False))

    names = _process_names()
    expected = {"WiVRn": {"wivrn-server"}, "Monado": {"monado-service"},
                "SteamVR": {"vrserver", "vrcompositor"}}.get(name)
    running = bool(names & expected) if names is not None and expected else None
    headset = dict(connected=None, system_name="", source="unavailable",
                   detail="Headset connection telemetry is unavailable for the selected runtime.")
    if selected and name == "SteamVR":
        headset = steamvr_status.read_status(path, lib, server_observed=bool(running))
    if selected and name == "WiVRn":
        headset = wivrn_status.read_status()
        if headset["connected"] is not None:
            running = True  # A typed reply is evidence that the WiVRn service is running.
    # Activity is distinct from the selected OpenXR manifest. Observe both
    # supported servers, but never infer SteamVR headset connectivity.
    steam_running = bool(names & {"vrserver", "vrcompositor"}) if names is not None else None
    wivrn_running = bool(names & {"wivrn-server"}) if names is not None else None
    other = None
    if selected and name == "WiVRn":
        wivrn_running = running
    elif wivrn_running:
        # A running non-selected WiVRn server may have a headset. Query only
        # an observed service, with D-Bus activation disabled.
        other = wivrn_status.read_status()
    wivrn_connected = headset["connected"] if selected and name == "WiVRn" else (
        other["connected"] if wivrn_running and other is not None else None)
    if wivrn_connected is True:
        activity = "WiVRn CONNECTED"
        if steam_running:
            activity = "WiVRn + SteamVR"
    elif steam_running:
        activity = "SteamVR RUNNING"
    elif wivrn_running and wivrn_connected is None:
        activity = "WiVRn RUNNING"
    elif running and name not in {"SteamVR", "WiVRn"}:
        activity = name + " RUNNING"
    elif steam_running is False and (wivrn_running is False or wivrn_connected is False) and name in {"SteamVR", "WiVRn", "Not configured"}:
        activity = "Idle"
    else:
        activity = "UNKNOWN"
    sampled_at = datetime.now(timezone.utc).isoformat()
    detail = f"{name} server running (connection telemetry replied)." if headset["connected"] is not None else (
        f"{name} server process observed." if running else
        "Selected runtime server process not observed; this does not prove the server is stopped." if running is False else
        "Runtime server process state is unknown.")
    add("runtime_process", "Runtime server", "ok" if running else "info" if running is False else "unknown", detail)

    run_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    if name in {"WiVRn", "Monado"}:
        socket_path = run_dir / ("wivrn/comp_ipc" if name == "WiVRn" else "monado_comp_ipc")
        try:
            socket_found = socket_path.is_socket()
        except OSError:
            socket_found = False
        add("ipc", "Compositor IPC socket", "ok" if socket_found else "warning",
            f"{socket_path}: {'socket present; connection not tested' if socket_found else 'not observed'}",
            "Connect the headset in your runtime manager." if not socket_found else "")
    connected = headset["connected"]
    connection_detail = headset["detail"]
    if headset["system_name"] and connected:
        connection_detail += f" Headset: {headset['system_name']}."
    if connected is not None:
        connection_detail += f" Source: {headset['source']}. This does not verify rendering or tracking."
    add("headset", "Headset connection", "ok" if connected else "warning" if connected is False else "unknown",
        connection_detail, f"Connect through {name} and rescan." if connected is False else
        "Check your runtime manager and live status access; no XR session is opened." if connected is None else "")
    add("controllers", "Controller tracking", "unknown",
        "UNVERIFIED: connection telemetry does not report live controller poses or input.",
        "Confirm both controllers in the headset and check input in a VR app.")
    return dict(sampled_at=sampled_at, runtime_selected=selected, runtime=name, server_running=running,
                activity=activity,
                headset_connected=connected, headset_name=headset["system_name"],
                headset_source=headset["source"], headset_connection_verified=connected is not None,
                controllers_verified=False), rows


def _selection_target(path) -> str | None:
    """Observe a selected symlink target; never rewrite or switch it."""
    if path is None:
        return None
    try:
        return str(path.resolve())
    except (OSError, RuntimeError):
        return str(path)


def _scope_for_runtime(name: str) -> str:
    if name == "WiVRn":
        evidence = "read-only WiVRn headset connection telemetry"
    elif name == "SteamVR":
        evidence = ("SteamVR server-process observation and optional OpenVR background headset connection telemetry")
    else:
        evidence = "limited read-only runtime and server-process evidence"
    return ("Host checks plus " + evidence + ". Controller tracking, graphics "
            "rendering, Proton access and per-game VR readiness require "
            "separate live verification.")


def refresh_live(report: dict) -> dict:
    """Refresh selected runtime and connection state; never switch runtimes.

    Re-read manifest contents AND symlink targets: users may select SteamVR
    for a test, then switch back to WiVRn without restarting the Hub.
    """
    path, lib = runtime.active_runtime()
    current = [str(path) if path else None, lib]
    if (current != report.get("selection")
            or _selection_target(path) != report.get("selection_target")):
        return scan()
    result = copy.deepcopy(report)
    live, rows = _live_snapshot(report["runtime"], bool(path and lib), path, lib)
    keys = {"runtime_process", "ipc", "headset", "controllers"}
    result["rows"] = [r for r in result["rows"] if r["id"] not in keys]
    index = next((i for i, r in enumerate(result["rows"]) if r["id"] == "adapter"), len(result["rows"]))
    result["rows"][index:index] = rows
    result["live"] = live
    return result


def hardware_summary(report: dict) -> str:
    connected = report["live"]["headset_connected"]
    state = "CONNECTED" if connected else "DISCONNECTED" if connected is False else "UNKNOWN"
    return f"HEADSET {state} · CONTROLLERS UNVERIFIED"

def scan() -> dict:
    """Return JSON-safe checks with evidence and next steps.

    'required' covers host prerequisites only. Hardware/session and game checks
    require separate verification even when every required check passes.
    """
    rows = []

    def add(key, name, status, detail, action="", required=False):
        rows.append(dict(id=key, name=name, status=status, detail=detail,
                         action=action, required=required))

    system = platform.system()
    add("platform", "Operating system", "ok" if system == "Linux" else "error",
        f"{system} {platform.release()} ({platform.machine()})",
        "Run the Hub on Linux." if system != "Linux" else "", True)
    path, lib = runtime.active_runtime()
    name = runtime.runtime_name(path, lib)
    valid = bool(path and lib)
    add("openxr", "Selected OpenXR runtime", "ok" if valid else "error",
        f"{name}: {path}; library: {lib}" if valid else
        (f"Selected manifest is missing, unreadable, or invalid: {path}" if path else "No selected OpenXR manifest found."),
        "Open WiVRn or your runtime manager, connect the headset, then rescan. Check XR_RUNTIME_JSON if set." if not valid else "", True)
    library_status = "unknown"
    library_detail = "Runtime library cannot be checked without a valid manifest."
    if valid:
        library = Path(lib)
        if library.is_absolute() or "/" in lib:
            try:
                library = (library if library.is_absolute() else path.resolve().parent / library).resolve()
                exists = library.is_file()
            except OSError:
                exists = False
            library_status = "ok" if exists else "error"
            library_detail = str(library) + (" (file present; not loaded)" if exists else " (missing or inaccessible)")
        else:
            library_detail = f"{lib} uses the dynamic linker search path; loading is unverified."
    add("runtime_library", "Runtime library", library_status, library_detail,
        "Check the runtime installation and its library path." if library_status != "ok" else "", True)

    for key, label, soname in (("openxr_loader", "OpenXR loader", "openxr_loader"),
                               ("vulkan", "Vulkan loader", "vulkan")):
        found = ctypes.util.find_library(soname)
        add(key, label, "ok" if found else "warning", found or "Not found by the host library lookup.",
            "Check your runtime/graphics packages; sandboxed installations may need a separate check." if not found else "",
            True)

    live, live_rows = _live_snapshot(name, valid, path, lib)
    rows.extend(live_rows)

    configured, source = _adapter_paths()
    active = [p for p in configured if _has_adapter(p)]
    add("adapter", "Configured OpenVR adapter", "ok" if active else "warning",
        "; ".join(f"{_adapter_name(p)}: {p}" for p in active) if active else
        (f"{source} points to missing/unrecognized adapter files: " + "; ".join(map(str, configured)) if configured else "No host OpenVR adapter path found."),
        "Check xrizer/OpenComposite selection in your runtime manager. Game-local Windows adapters require per-game checks." if not active else "")
    for label, paths in (("xrizer", (Path("/usr/lib/xrizer"), Path("/opt/xrizer"), Path.home() / ".local/share/xrizer")),
                         ("OpenComposite", (Path("/usr/lib/opencomposite"), Path("/opt/opencomposite"), Path.home() / ".local/share/OpenComposite"))):
        # Custom configured paths must also appear in inventory, not just common paths.
        candidates = [p for p in active if _adapter_name(p) == label] + list(paths)
        found = list(dict.fromkeys(p.resolve() for p in candidates if _has_adapter(p)))
        add(label.lower(), f"{label} host inventory", "ok" if found else "unknown",
            "; ".join(map(str, found)) if found else "Not found in common host locations; custom, Flatpak, and game-local copies may exist.")

    roots = [Path(p).expanduser() for p in os.environ.get("VRHUB_STEAM_ROOTS", "").split(":") if p] or [Path(p).expanduser() for p in STEAM_ROOTS]
    installs = list(dict.fromkeys(str(p.resolve()) for p in roots if (p / "steamapps").is_dir()))
    add("steam", "Steam installation", "ok" if installs else "warning", "; ".join(installs) or "Not found in common Steam locations.",
        "Open Steam or set VRHUB_STEAM_ROOTS for a custom install." if not installs else "")
    for key, label, commands in (("wivrn", "WiVRn tools", ("wivrn-dashboard", "wivrn-server")),
                                  ("monado", "Monado tools", ("monado-service",)),
                                  ("tools", "Integration tools", ("jackify", "envision", "heroic", "gamemoderun", "7z", "umu-run"))):
        found = [f"{cmd}: {shutil.which(cmd)}" for cmd in commands if shutil.which(cmd)]
        add(key, label, "info", "; ".join(found) or "No matching commands on PATH; standalone/Flatpak installs are not ruled out.")
    add("steam_environment", "Steam container runtime import", "info",
        "Set in the Hub process: " + os.environ.get("PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES", "not set") + "; game-specific Steam launch options are not inspected.",
        "For WiVRn Steam/Proton workflows, review the game's launch options for PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1.")
    required = [r for r in rows if r["required"]]
    status = "NOT READY" if any(r["status"] == "error" for r in required) else (
        "NEEDS CHECKS" if any(r["status"] != "ok" for r in required) else "HOST CHECKS PASSED")
    return dict(schema_version=2, hub_version=__version__, scanned_at=datetime.now(timezone.utc).isoformat(),
                status=status, runtime=name, hardware_verified=False, rows=rows, live=live,
                selection=[str(path) if path else None, lib],
                selection_target=_selection_target(path),
                environment={k: os.environ[k] for k in ENV_KEYS if k in os.environ},
                scope=_scope_for_runtime(name))


def report_text(report: dict) -> str:
    lines = [f"NAnnersVRhub {report['hub_version']} — VR System Scan", "Scanned: " + local_time(report["scanned_at"]),
             report["status"] + " — " + hardware_summary(report), report["scope"], f"Live status sampled: {local_time(report['live']['sampled_at'])}", ""]
    for row in report["rows"]:
        lines.append(f"[{row['status'].upper()}] {row['name']}: {row['detail']}")
        if row["action"]:
            lines.append(f"  Next: {row['action']}")
    lines += ["", "Relevant environment (Hub process only):"]
    lines += [f"{k}={v}" for k, v in report["environment"].items()] or ["No relevant overrides set."]
    return "\n".join(lines)


def report_html(report: dict) -> str:
    e = html.escape
    colours = dict(ok="#63D69B", warning="#FFD447", error="#FF6B6B", unknown="#AAB3C0", info="#46B7FF")
    parts = [f"<h2>{e(report['status'])}</h2><p><b>{e(hardware_summary(report))}</b></p>",
             f"<p>{e(report['scope'])}</p><p>Host scan: {e(local_time(report['scanned_at']))}<br>Live status: {e(local_time(report['live']['sampled_at']))}</p>"]
    for row in report["rows"]:
        parts.append(f"<p><b style='color:{colours[row['status']]}'>{e(row['status'].upper())} · {e(row['name'])}</b><br>{e(row['detail'])}")
        if row["action"]:
            parts.append(f"<br><i>Next: {e(row['action'])}</i>")
        parts.append("</p>")
    return "".join(parts)
