"""Bounded, read-only log evidence. This module never certifies a live session."""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import stat

from . import __version__, hub
from .display_time import local_time

MAX_BYTES = 512 * 1024
MAX_FILES = 4
MAX_LINES = 10000
MAX_LINE_CHARS = 4096
STALE_SECONDS = 24 * 60 * 60
XR_RESULTS = "https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrResult.html"
CP_SOURCE = "https://github.com/dariulone/cyberpunk-vr-port"

_RULES = (
    ("xr-validation-failure", "XR_ERROR_VALIDATION_FAILURE", -1,
     "An OpenXR call failed validation. Repeated xrEndFrame validation failures show that frame submission is being rejected; this log does not identify the invalid parameter or establish which component caused it.",
     "Preserve the full application log and capture runtime-side validation details from the same test. Compare a single VR/overlay setting at a time; do not infer a runtime-import failure or replace the working Proton build from this code alone."),
    ("xr-pose-invalid", "XR_ERROR_POSE_INVALID", -39,
     "OpenXR rejected a submitted pose. This can prevent a frame from reaching the headset; the log alone does not identify the faulty layer or component.",
     "Reproduce in loaded gameplay and capture a fresh log. Check the game's VR overlays and the runtime's tracking state."),
    ("xr-runtime-unavailable", "XR_ERROR_RUNTIME_UNAVAILABLE", -51,
     "The OpenXR loader reported that a runtime was unavailable at this point in the log.",
     "Connect through WiVRn, review the selected OpenXR runtime and the game's actual Steam runtime-import option, then retry."),
    ("xr-extension-missing", "XR_ERROR_EXTENSION_NOT_PRESENT", -9,
     "The application requested an OpenXR extension that was unavailable.",
     "Capture the requested extension name from the surrounding log and compare the mod's requirements with the selected runtime. Do not replace a working Proton build based on this finding alone."),
    ("xr-graphics-requirements", "XR_ERROR_GRAPHICS_REQUIREMENTS_CALL_MISSING", -50,
     "OpenXR reported a missing graphics-requirements call during setup.",
     "Review the mod/backend and graphics API configuration, and retain the surrounding initialization log for investigation."),
)
_XR_CALL = re.compile(r"\bxr\w+\b", re.I)
_FAILURE = re.compile(r"\b(?:failed|failure)\b", re.I)
_RESULT = re.compile(r"\b(?:res|result)\s*[:=]\s*(-\d+)(?![\d.])", re.I)
_MENU_GATE = re.compile(r"\bDepth gate\b[^\r\n]*\bmenu\s*=\s*1\b", re.I)
_FRAME_DISCARDED = re.compile(r"\bxrBeginFrame\b[^\r\n]*\bXR_FRAME_DISCARDED\b", re.I)
_LOG_TIMESTAMP = re.compile(r"^\s*\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)(?=\]|\s|$)")


def _occurrence(line_number, line):
    match = _LOG_TIMESTAMP.match(line)
    stamp = match.group(1) if match else None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None
    except ValueError:
        stamp = parsed = None
    return {"tail_line": line_number, "timestamp": stamp,
            "timezone_recorded": parsed.utcoffset() is not None if parsed else None}


def _clean(value):
    # Keep pasted excerpts readable, including logs with ANSI/control sequences.
    value = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    return "".join(c if c.isprintable() or c == "\t" else " " for c in value)


def _sources(recipe, steam_roots):
    rid = recipe["id"]
    if recipe.get('handler') == 'kharvox-gog':
        from . import kharvox
        try:
            root = kharvox.prefix(recipe)
            from . import kharvox_bridge
            prefix_logs = kharvox.logs(recipe)
            candidates = [(prefix_logs[key],root) for key in ('main','errors')]
            candidates += [(path,kharvox_bridge.state_dir()) for key,path in kharvox_bridge.log_paths().items() if key in {'launch','probe'}]
            return candidates, 'KHARVOX main/error logs plus isolated runner launch/probe logs. Audit, intro and renderer logs can be selected explicitly. Historical evidence only; nativeAttempt=False is a legacy renderer flag.'
        except RuntimeError as exc:
            return [], str(exc)
    if rid not in {"cyberpunk-2077", "subnautica", "valheim", "elden-ring"} and not (recipe.get("method") == "uevr" and recipe.get("profile")):
        return [], "Automatic log paths are not configured for this game. Choose a log file to inspect OpenXR error signatures."
    game = hub.game_path(recipe, steam_roots)
    if not game:
        return [], "Game directory was not found. Choose a log file, or check the game's storefront installation."
    if rid == "cyberpunk-2077":
        return [(game / "bin/x64/cyberpunkvrport.log", game)], "CyberpunkVR Port plugin log; other loader/CET logs require explicit file selection."
    if rid == "elden-ring":
        return [(game / "Game/ERVR/ERVR.log", game), (game / "Game/ReShade.log", game)], "ERVR and ReShade logs. Menu/cinema fallback is expected; file presence or recognized log text does not verify current stereo gameplay."
    if rid in {"subnautica", "valheim"}:
        return [(game / "BepInEx/LogOutput.log", game)], "Expected BepInEx loader/plugin log. A missing or clean log does not verify VR rendering or input."
    try:
        prefix = hub._pfx(recipe, steam_roots)
        profile = hub.profile_dir(recipe, steam_roots)
    except RuntimeError as exc:
        return [], str(exc)
    return [(profile / "log.txt", prefix)], (
        "Expected UEVR per-game log path. Community builds may log elsewhere; choose that file explicitly if needed.")


def _read(path, root, now):
    item = {"path": str(path), "selection": "automatic" if root else "user-selected",
            "status": "UNREADABLE", "modified_at": None, "age_seconds": None,
            "freshness": "UNKNOWN", "bytes_read": 0, "size_bytes": None,
            "truncated": False, "lines_omitted": 0, "long_lines_clipped": 0,
            "findings": [], "detail": ""}
    try:
        # Automatic candidates must remain inside the selected game/prefix.
        if root and not path.resolve().is_relative_to(root.resolve()):
            raise OSError("Automatic log path escapes the game/prefix; choose the file explicitly to review it.")
        if path.is_symlink():
            raise OSError("Log symlinks are not read. Choose the real log file explicitly.")
        # O_NONBLOCK avoids hanging on FIFOs; fstat rejects all non-regular files.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise OSError("Only regular log files can be inspected.")
            item["size_bytes"] = info.st_size
            item["modified_at"] = datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()
            age = now.timestamp() - info.st_mtime
            item["age_seconds"] = round(age, 1)
            item["freshness"] = "FUTURE TIMESTAMP" if age < -300 else "STALE" if age > STALE_SECONDS else "RECENT"
            bom = stream.read(2)
            start = max(0, info.st_size - MAX_BYTES)
            utf16 = bom in (b"\xff\xfe", b"\xfe\xff")
            if utf16:
                start += start % 2
            stream.seek(start)
            data = stream.read(MAX_BYTES)
            item["bytes_read"] = len(data)
            item["truncated"] = start > 0
            if utf16:
                text = data.decode("utf-16-le" if bom == b"\xff\xfe" else "utf-16-be", errors="replace").lstrip("\ufeff")
            else:
                if b"\x00" in data:
                    raise OSError("File appears binary; select a text log instead.")
                text = data.decode("utf-8-sig", errors="replace")
            if start:
                # Discard the partial leading line; line numbers below are tail-relative.
                text = text.partition("\n")[2]
            changed = os.fstat(stream.fileno())
            if (changed.st_size, changed.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                item["detail"] = "Log changed while being read; this is a bounded snapshot. Refresh after reproducing the problem."
    except FileNotFoundError:
        item.update(status="MISSING", detail="Log not found. A missing log does not prove the mod failed to load.")
        return item
    except (OSError, ValueError, OverflowError) as exc:
        item["detail"] = str(exc)
        return item
    lines = text.splitlines()
    item["lines_omitted"] = max(0, len(lines) - MAX_LINES)
    lines = lines[-MAX_LINES:]
    item["long_lines_clipped"] = sum(len(line) > MAX_LINE_CHARS for line in lines)
    item["status"] = "READ" if data else "EMPTY"
    return item, [line[:MAX_LINE_CHARS] for line in lines]


def _analyze(lines, recipe):
    numeric = {}
    for i, line in enumerate(lines, 1):
        call = _XR_CALL.search(line)
        failure = _FAILURE.search(line, call.end()) if call else None
        result = _RESULT.search(line, failure.end()) if failure else None
        if result:
            numeric[i] = int(result.group(1))
    found = []
    for key, symbol, code, explanation, action in _RULES:
        hits = [(i, line) for i, line in enumerate(lines, 1)
                if re.search(r"\b" + symbol + r"\b", line) or numeric.get(i) == code]
        if not hits:
            continue
        if key == "xr-pose-invalid" and recipe["id"] == "cyberpunk-2077":
            action = ("User-tested Cyberpunk workaround: F10 -> General -> VR menu quad OFF; "
                      "F10 -> HUD -> Enable HUD panel OFF; World-space interactions / dialogs OFF. "
                      "Close F10 completely before checking immersion. Opening the game menu caused passthrough in the October 18 test; exiting it restored full VR. "
                      "The exact cause is unconfirmed; this does not verify your current settings or fix the menu limitation.")
        found.append({"id": key, "severity": "ERROR", "title": f"{symbol} ({code})",
                      "count": len(hits), "explanation": explanation, "action": action,
                      "sources": [XR_RESULTS] + ([CP_SOURCE] if recipe["id"] == "cyberpunk-2077" else []),
                      "excerpts": [{"tail_line": i, "text": _clean(line)[:300]} for i, line in hits[-3:]]})
    discarded = [(i, line) for i, line in enumerate(lines, 1) if _FRAME_DISCARDED.search(line)]
    if discarded:
        found.append({"id": "xr-frame-discarded", "severity": "INFO", "title": "xrBeginFrame: XR_FRAME_DISCARDED (+9)",
                      "count": len(discarded),
                      "explanation": "XR_FRAME_DISCARDED is a non-negative OpenXR success status, even if the application labels it failed/error. It indicates that a prior begun frame was discarded. It is not an independent validation failure or proof of a broken session.",
                      "action": "Check adjacent xrEndFrame failures first. If these messages alternate with validation failures, investigate the rejected submissions; the log alone does not prove the exact cause or a timing-setting fix.",
                      "sources": ["https://registry.khronos.org/OpenXR/specs/1.1/man/html/xrBeginFrame.html"],
                      "excerpts": [{"tail_line": i, "text": _clean(line)[:300]} for i, line in discarded[-3:]]})
    if recipe["id"] == "cyberpunk-2077":
        hits = [(i, line) for i, line in enumerate(lines, 1) if _MENU_GATE.search(line)]
        if hits:
            found.append({"id": "cp-menu-depth-gate", "severity": "INFO", "title": "Menu-related depth gate recorded",
                          "count": len(hits), "explanation": "The plugin recorded menu=1 in its depth gate. The in-game menu or VR menu quad can contribute; this does not prove which setting is enabled or establish a rendering failure.",
                          "action": "Close both the game menu and F10 before evaluating loaded gameplay. Compare a fresh log if passthrough persists.",
                          "sources": [CP_SOURCE],
                          "excerpts": [{"tail_line": i, "text": _clean(line)[:300]} for i, line in hits[-3:]]})
    if recipe.get('handler') == 'kharvox-gog':
        rules = [
            ('kh-sfs-command-state','ERROR',r'\[SFS\].*invalid unordered_map.*key','SFS state lookup failed',
             'SFS reported missing tracked state. The lab 0.1.5 DOOM run saw this after queue acquisition; a command allocation bypass was corrected in lab 0.1.6. The line alone does not identify which map failed.',
             'Use the bundled lab 0.1.6 runner and matching full bridge test. Compare fresh logs if errors persist; historical matches do not invalidate a later successful session.'),
            ('kh-legacy-native','INFO',r'\bnativeAttempt=False\b','Legacy Native renderer flag',
             'The launcher did not select the retired Native renderer. SFS and AER can use this value; it does not establish a rendering failure or success.',
             'Review the selected SFS/AER renderer and a fresh gameplay log, then test actual headset output in a loaded campaign.'),
            ('kh-cvar-identity','ERROR',r'native render CVar identity changed','KHARVOX CVar identity guard refusal',
             'The runtime refused an engine control-variable identity. Upstream documents this GOG failure in the initial 1.4 builds.',
             'Use the complete final 1.4 package with launcher 1.4.0.1404 and runtime 1.4.0.1402 in a fresh folder. Preserve the log if the refusal persists.'),
            ('kh-layer-not-loaded','ERROR',r'KHARVOX layer was not loaded','KHARVOX Vulkan layer not loaded',
             'The launcher reported that its Windows Vulkan layer was not loaded. This line does not establish the Wine/Proton cause.',
             'Keep the launcher/runtime pair together and capture its Vulkan-loader log. Do not force the Windows DLL into the host Linux Vulkan layer chain.'),
        ]
        for key,severity,pattern,title,explanation,action in rules:
            hits = [(i,line) for i,line in enumerate(lines,1) if re.search(pattern,line)]
            if hits:
                found.append({'id':key,'severity':severity,'title':title,'count':len(hits),
                              'explanation':explanation,'action':action,
                              'sources':['https://github.com/CactusVRStudios/KHARVOX/blob/main/Docs/RELEASE_1_4_GOG_FIX2.md',
                                         'https://github.com/CactusVRStudios/KHARVOX/blob/main/launcher/KharvoxLauncher/RendererSelection.cs'],
                              'excerpts':[{'tail_line':i,'text':_clean(line)[:300]} for i,line in hits[-3:]]})
    # These refer to file order within the inspected tail, not chronological
    # sorting or proof of a current session. Missing zones are never guessed.
    by_number = dict(enumerate(lines, 1))
    for finding in found:
        # All findings keep the last three hits. The last hit is available even
        # when its original line has no timestamp; do not substitute an older time.
        last = finding["excerpts"][-1]["tail_line"]
        finding["last_occurrence"] = _occurrence(last, by_number[last])
    return found


def report(recipe, steam_roots=None, files=None, now=None):
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("Log sampling time must include a timezone.")
    if files is not None:
        files = list(files)
        if not 1 <= len(files) <= MAX_FILES:
            raise RuntimeError(f"Choose between 1 and {MAX_FILES} log files.")
        candidates = [(Path(p).expanduser().absolute(), None) for p in files]
        note = "Explicitly selected files replace automatic discovery. Their association with this game/session is user-supplied."
    else:
        candidates, note = _sources(recipe, steam_roots)
    logs = []
    seen = set()
    for path, root in candidates:
        if str(path) in seen:
            continue
        seen.add(str(path))
        read = _read(path, root, now)
        if isinstance(read, tuple):
            item, lines = read
            item["findings"] = _analyze(lines, recipe)
        else:
            item = read
        logs.append(item)
    if any(item["findings"] for item in logs):
        status = "RECOGNIZED LOG EVIDENCE"
    elif any(item["status"] == "READ" for item in logs):
        status = "NO KNOWN SIGNATURES FOUND"
    else:
        status = "NO READABLE LOG EVIDENCE"
    return {"schema_version": 1, "hub_version": __version__, "recipe_id": recipe["id"],
            "game": recipe["name"], "sampled_at": now.isoformat(), "status": status,
            "discovery_note": note, "logs": logs,
            "limits": {"max_files": MAX_FILES, "tail_bytes_per_file": MAX_BYTES,
                       "max_lines": MAX_LINES, "max_line_chars": MAX_LINE_CHARS, "stale_after_seconds": STALE_SECONDS},
            "notice": "Historical log evidence only. File modification time is not a session identifier. No matching error does not verify rendering, tracking, controls or stereo depth. Configuration checks and recorded gameplay tests are unchanged."}


def report_text(rep):
    lines = [f"NAnnersVRhub {rep['hub_version']} — Game log diagnostics", f"Game: {rep['game']}",
             f"Recipe: {rep['recipe_id']}", f"Sampled: {local_time(rep['sampled_at'])}", rep["status"], "",
             rep["discovery_note"], rep["notice"],
             f"Read limits: last {MAX_BYTES} bytes / {MAX_LINES} lines per file; first {MAX_LINE_CHARS} characters per line."]
    for item in rep["logs"]:
        lines += ["", f"Log: {_clean(item['path'])}", f"Selection: {item['selection']}; file status: {item['status']}",
                  f"File modified: {local_time(item['modified_at'])}; age at sampling: {item['age_seconds']} seconds; {item['freshness']}",
                  f"Read: {item['bytes_read']} bytes of {item['size_bytes']}; tail truncated: {item['truncated']}; earlier lines omitted: {item['lines_omitted']}; long lines clipped: {item['long_lines_clipped']}"]
        if item["freshness"] == "STALE":
            lines += ["STALE: last modified more than 24 hours ago. Reproduce and refresh before relating these errors to a new test."]
        elif item["freshness"] == "FUTURE TIMESTAMP":
            lines += ["Future modification time: check the system clock; freshness is uncertain."]
        if item["detail"]:
            lines += [_clean(item["detail"])]
        for finding in item["findings"]:
            last = finding.get("last_occurrence", {})
            lines += [f"[{finding['severity']}] {finding['title']} — {finding['count']} occurrence(s) in inspected tail",
                      "Historical log finding; this count does not establish that the error is still occurring.",
                      "Last matching entry in inspected tail: " + local_time(last.get("timestamp")) +
                      (f"; tail line {last['tail_line']}" if last.get("tail_line") else ""),
                      finding["explanation"], "Next step: " + finding["action"]]
            lines += [f"  Tail line {e['tail_line']}: {e['text']}" for e in finding["excerpts"]]
            lines += ["Sources: " + " ; ".join(finding["sources"])]
        if item["status"] == "READ" and not item["findings"]:
            lines += ["No known signatures found in the inspected tail. Unrecognized errors may still be present."]
    return "\n".join(lines)
