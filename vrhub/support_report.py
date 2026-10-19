"""Fresh, independent diagnostic sections; export only on an explicit request."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

from . import __version__, compatibility, live_tests, log_diagnostics, system_scan
from .display_time import local_time

NOTICE = ("Sources are sampled sequentially, not atomically. Host/configuration checks, historical log evidence, "
          "and user-reported gameplay results have separate meanings and timestamps. "
          "This report does not certify a current gameplay session or infer that an old error is still occurring.")


def _section(collect):
    started = datetime.now(timezone.utc).isoformat()
    try:
        data = deepcopy(collect())
        return {"availability": "AVAILABLE", "collection_started_at": started,
                "collection_finished_at": datetime.now(timezone.utc).isoformat(), "data": data, "error": ""}
    except Exception as exc:
        # A diagnostic source failing must not hide the other sources.
        return {"availability": "UNAVAILABLE", "collection_started_at": started,
                "collection_finished_at": datetime.now(timezone.utc).isoformat(), "data": None,
                "error": type(exc).__name__ + ": " + str(exc)}


def collect(recipe, steam_roots=None, log_files=None):
    if log_files is not None:
        log_files = list(log_files)
        if not 1 <= len(log_files) <= log_diagnostics.MAX_FILES:
            raise RuntimeError("Choose between one and four log files.")
    started = datetime.now(timezone.utc).isoformat()
    sections = {}
    sections["system"] = _section(system_scan.scan)
    sections["compatibility"] = _section(lambda: compatibility.report(recipe, steam_roots))
    sections["logs"] = _section(lambda: log_diagnostics.report(recipe, steam_roots, files=log_files))

    def gameplay():
        config = sections["compatibility"]["data"]
        if config is not None:
            if config.get("local_test_error"):
                raise RuntimeError(config["local_test_error"])
            return {"latest_test": deepcopy(config.get("local_test")), "record_count": config.get("local_test_count", 0)}
        entries = live_tests.history(recipe["id"])
        return {"latest_test": entries[0] if entries else None, "record_count": len(entries)}

    sections["gameplay"] = _section(gameplay)
    return {"schema_version": 1, "hub_version": __version__, "recipe_id": recipe["id"], "game": recipe["name"],
            "collection_started_at": started, "collection_finished_at": datetime.now(timezone.utc).isoformat(),
            "collection_status": "COMPLETE" if all(s["availability"] == "AVAILABLE" for s in sections.values()) else "PARTIAL",
            "notice": NOTICE, "sections": sections}


def export_view(snapshot, include_excerpts=True, replace_home=True):
    """Prepare exactly the content that preview/copy/save will share; never mutate the snapshot."""
    result = deepcopy(snapshot)
    if not include_excerpts:
        logs = result["sections"]["logs"]["data"]
        if logs:
            for item in logs["logs"]:
                for finding in item["findings"]:
                    finding["excerpts"] = []
    home = str(Path.home()).rstrip("/")
    replaced = bool(replace_home and home and home != "/")
    if replaced:
        # Replace this Linux home prefix, not similarly named sibling homes.
        patterns = [re.compile(re.escape(prefix) + r"(?=$|[/\\\s'\"<>)\],;:])")
                    for prefix in {home, home.replace("/", "\\")}]

        def redact(value):
            if isinstance(value, str):
                for pattern in patterns:
                    value = pattern.sub("~", value)
                return value
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        result = redact(result)
    result["export_options"] = {"include_log_excerpts": bool(include_excerpts), "replace_linux_home_path": replaced}
    return result


def _compatibility_text(data):
    recipe = {"compatibility": data["profile"]} if data["profile"] is not None else {}
    lines = ["Local configuration: " + data["status"], "Sampled: " + local_time(data["sampled_at"]),
             "", "Bundled compatibility reference (separate from local test history):", compatibility.summary_text(recipe),
             "", "Current local configuration findings:"]
    lines += [f"[{row['status'].upper()}] {row['name']}: {row['detail']}" for row in data["checks"]]
    lines += ["", data["limitation"]]
    return "\n".join(lines)


def report_text(view):
    sections = view["sections"]
    options = view["export_options"]
    lines = [f"NAnnersVRhub {view['hub_version']} — Combined support report", "Game: " + view["game"],
             "Recipe: " + view["recipe_id"], "Collection started: " + local_time(view["collection_started_at"]),
             "Collection finished: " + local_time(view["collection_finished_at"]),
             "Captured snapshot: Copy/Save export this captured evidence. Collect new snapshot reads the sources again; closing a game does not refresh this report or remove its old logs.",
             "Section collection: " + view["collection_status"] + " (availability only; not a gameplay verdict)",
             "Log excerpts: " + ("included" if options["include_log_excerpts"] else "omitted"),
             "This Linux home path: " + ("replaced with ~" if options["replace_linux_home_path"] else "included"),
             "Review before sharing: game paths, test notes, relevant Hub environment values, headset name and any retained excerpts may contain personal information.",
             view["notice"]]
    titles = {"system": "1. VR system scan", "compatibility": "2. Game compatibility and current configuration",
              "logs": "3. Game log evidence", "gameplay": "4. Latest local gameplay test (historical, user reported)"}
    for key, section in sections.items():
        lines += ["", titles[key], "Availability: " + section["availability"],
                  "Section collection: " + local_time(section["collection_started_at"]) + " -> " + local_time(section["collection_finished_at"])]
        if section["availability"] != "AVAILABLE":
            lines += ["Unavailable: " + section["error"]]
            continue
        data = section["data"]
        if key == "system":
            lines += [system_scan.report_text(data)]
        elif key == "compatibility":
            lines += [_compatibility_text(data)]
        elif key == "logs":
            lines += [log_diagnostics.report_text(data)]
        else:
            lines += ["Local test records: " + str(data["record_count"])]
            lines += [live_tests.record_text(data["latest_test"], include_setup=True) if data["latest_test"] else
                      "No local gameplay tests recorded. Bundled references are not local tests."]
    # Literal text preview/copy; strip terminal control sequences in supplied notes/logs.
    text = "\n".join(lines)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return "".join(c if c.isprintable() or c in "\n\t" else " " for c in text)


def serialize(view, json_format=False):
    return (json.dumps(view, indent=2, ensure_ascii=False) if json_format else report_text(view)) + "\n"


def save(path, view, json_format=False):
    """Atomically create a private, new report. Never overwrite an existing file."""
    path = Path(path).expanduser()
    content = serialize(view, json_format)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".vrhub-support-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        # Linking within the destination directory is atomic and refuses existing destinations.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
