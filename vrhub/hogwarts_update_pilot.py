# SPDX-License-Identifier: GPL-3.0-only
"""Read-only review of the pinned Hogwarts Legacy profile update."""
from collections import Counter
from dataclasses import replace
from hashlib import file_digest
from importlib.resources import files
import json
from pathlib import Path
from zipfile import ZipFile

from . import hub, profile_safety

ARCHIVE_SHA256 = "d2fb2b74db85dc2bab039063b367016a4a30fe5dfd509bb3480da0a0cde87efb"
SOURCE = "https://github.com/jbusfield/HL_UEVR/releases/tag/v2.1.0"
BASELINE = "30d7e626882bb3a7e1d04d8a42fd4f4bbcda9011054c4b12bf9e6e722dab06a3"
LOCAL_FILES = {
    "cache/sdk_discovery.json", "config.txt", "data/config_default.json",
    "data/hogwarts_legacy_config.json", "imgui.ini",
}
COMPATIBILITY_BLOCK = (
    "The v2.1.0 maintainer recommends a clean profile. Compatibility of the updated Lua, "
    "plugins and input files with the preserved v2.0.6 settings has not been established. "
    "The update adds settings for stick drift and flick casting. "
    "Installation is disabled. config.txt stays active and config_AFW.txt stays separate."
)


def applies(recipe, archive):
    return (recipe["id"] == "hogwarts-legacy"
            and Path(archive).name.casefold() == "hogwartslegacy.zip")


def classify(current, baseline, incoming, owned):
    if (len(owned) != len(baseline) or set(owned) != set(baseline)
            or set(current) != set(baseline) | {"log.txt"}):
        raise RuntimeError("The installed files or Hub ownership differ from the reviewed v2.0.6 profile.")
    if not baseline.keys() <= incoming.keys() or "log.txt" in incoming:
        raise RuntimeError("The update changes the reviewed profile ownership boundary.")
    modified = {name for name in baseline if current[name] != baseline[name]}
    if modified != LOCAL_FILES:
        raise RuntimeError("Local modifications differ from the reviewed Hogwarts profile.")
    names = current.keys() | incoming.keys()
    if len({name.casefold() for name in names}) != len(names):
        raise RuntimeError("The installed and incoming paths conflict on Windows.")
    rows = []
    for name in sorted(names):
        if name == "log.txt":
            action, reason = "Preserve", "Existing player log"
        elif name in modified:
            action, reason = "Preserve", "Locally modified"
        elif name not in current:
            action, reason = "Install", "New v2.1.0 file"
        elif current[name] == incoming[name]:
            action, reason = "Preserve", "Already matches v2.1.0"
        else:
            action, reason = "Replace", "Matches the official v2.0.6 baseline"
        rows.append((action, name, reason))
    return tuple(rows)


def build_review(recipe, archive, steam_roots=None):
    base = profile_safety.build_plan(recipe, archive, steam_roots)
    if base.archive_sha256 != ARCHIVE_SHA256:
        raise RuntimeError(f"HogwartsLegacy.zip failed the pinned v2.1.0 SHA-256 check. Approved source: {SOURCE}")
    reference = json.loads(files("vrhub").joinpath("recipes", "hogwarts-profile-v2.0.6.json").read_text())
    if reference["archive_sha256"] != BASELINE:
        raise RuntimeError("The official v2.0.6 baseline identity could not be verified.")
    dest = Path(base.destination)
    snapshot = profile_safety._snapshot(dest)
    record = hub.state().get(f'{recipe["id"]}:profile') or {}
    try:
        owned = tuple(Path(name).relative_to(dest).as_posix() for name in record.get("files", ()))
    except ValueError as exc:
        raise RuntimeError("The Hub ownership record contains paths outside the reviewed profile.") from exc
    with ZipFile(archive) as data:
        incoming = {}
        for info, name in profile_safety._archive_entries(data):
            with data.open(info) as stream:
                incoming[name] = file_digest(stream, "sha256").hexdigest()
    dirs = {name.casefold() for name in snapshot["dirs"]}
    if any(name.casefold() in dirs for name in incoming):
        raise RuntimeError("An incoming file conflicts with an installed directory.")
    if profile_safety._digest(Path(archive)) != ARCHIVE_SHA256:
        raise RuntimeError("The archive changed while generating the review.")
    current = {name: item["sha256"] for name, item in snapshot["files"].items()}
    rows = classify(current, reference["files"], incoming, owned)
    if Counter(action for action, _, _ in rows) != {"Install": 36, "Replace": 53, "Preserve": 140}:
        raise RuntimeError("The installation actions differ from the reviewed update pilot.")
    return replace(base, blocked=(COMPATIBILITY_BLOCK,)), rows
