"""Read-only WiVRn connection telemetry, with bounded D-Bus requests.

Upstream interface: WiVRn/dbus/io.github.wivrn.Server.xml. Query only the
HeadsetConnected and SystemName properties; never fetch configuration, pairing
PINs, or keys. Properties.Get is called explicitly because busctl get-property
has not consistently honored --auto-start=no across systemd versions.
"""
import shlex
import shutil
import subprocess
from datetime import datetime, timezone

SERVICE = "io.github.wivrn.Server"
OBJECT = "/io/github/wivrn/Server"
INTERFACE = "io.github.wivrn.Server"


def _property(tool: str, name: str) -> tuple[list[str] | None, str]:
    command = [tool, "--user", "--auto-start=no", "--allow-interactive-authorization=no",
               "--timeout=1", "--no-pager", "call", SERVICE, OBJECT,
               "org.freedesktop.DBus.Properties", "Get", "ss", INTERFACE, name]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=1.5,
                                check=False, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "WiVRn status request timed out."
    except OSError:
        return None, "Could not run busctl to read the user session bus."
    if result.returncode:
        # Classify errors without exporting arbitrary session-bus error contents.
        error = result.stderr.lower()
        if "unknownproperty" in error or "unknown property" in error or "no such property" in error:
            reason = "This WiVRn version does not expose the requested status property."
        elif "accessdenied" in error or "access denied" in error or "permission denied" in error:
            reason = "The user session bus denied access to WiVRn status."
        else:
            reason = "WiVRn status unavailable: server service or user session bus is not accessible."
        return None, reason
    try:
        value = shlex.split(result.stdout)
    except ValueError:
        return None, "WiVRn status reply could not be parsed."
    return value, ""


def read_status() -> dict:
    """Return connected=True/False only for a correctly typed boolean reply.

    Unknown/unavailable service is never converted to 'disconnected'. Starting
    the service, touching its sockets, or opening an XR session is prohibited.
    """
    result = dict(connected=None, system_name="", source="WiVRn D-Bus HeadsetConnected",
                  detail="", sampled_at="")
    tool = shutil.which("busctl")
    if not tool:
        result["detail"] = "busctl is unavailable; WiVRn live connection status cannot be read."
    else:
        value, reason = _property(tool, "HeadsetConnected")
        if value in (["v", "b", "true"], ["v", "b", "false"]):
            result["connected"] = value[-1] == "true"
            result["detail"] = "WiVRn reports a connected headset." if result["connected"] else "WiVRn reports no connected headset."
            if result["connected"]:
                name, _ = _property(tool, "SystemName")
                if name and len(name) == 3 and name[:2] == ["v", "s"]:
                    result["system_name"] = name[2][:160]
        else:
            result["detail"] = reason or "WiVRn status reply was not a boolean; connection remains unknown."
    result["sampled_at"] = datetime.now(timezone.utc).isoformat()
    return result
