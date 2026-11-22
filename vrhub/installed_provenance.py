# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Installed release provenance from *recorded* evidence only.

This model never reads live game files, parses binaries, performs networking,
or writes state. A recorded archive hash is evidence of what the Hub selected
at installation time, not proof the current payload still matches.
"""
import re
from pathlib import Path
from urllib.parse import urlsplit, unquote

from . import updates


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._+-]{0,99}\Z")
_MARKERS = {"subnautica": "submersed-vr-1", "valheim": "vhvr-1",
            "elden-ring": "ervr-1"}


def _result(label, version=None, source="unknown", detail="", *, identified=False):
    return {"label": label, "version": version, "source": source,
            "detail": detail, "identified": identified}


def _digest(value):
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _source_tag(recipe, package):
    """Explicit recipe release tag, then release page's exact tag segment."""
    rid = package["id"]
    source = recipe.get("archive_releases", {}).get(rid, {})
    raw = source.get("pinned_tag") if isinstance(source, dict) else None
    if isinstance(raw, str) and _RELEASE.fullmatch(raw):
        return raw
    page = package.get("page")
    if not isinstance(page, str):
        return None
    url = urlsplit(page)
    if (url.scheme != "https" or not url.hostname or url.username or url.password):
        return None
    parts = [unquote(part) for part in url.path.strip("/").split("/")]
    if len(parts) >= 2 and parts[-2] in ("tag", "v") and _RELEASE.fullmatch(parts[-1]):
        return parts[-1]
    return None


def _package_evidence(recipe, component, game):
    rid = component["id"]
    packages = [p for p in recipe.get("packages", [])
                if p.get("id") == rid]
    if len(packages) != 1:
        return _result("Unknown", detail="Dependency has no unique recipe package.")
    if not isinstance(game, dict):
        return _result("Unknown", detail="No Hub-managed package record; manual installs may exist.")
    records = game.get("packages")
    record = records.get(rid) if isinstance(records, dict) else None
    if not isinstance(record, dict):
        return _result("Hub record · version unknown", detail=(
            "A game-wide Hub entry exists but has no per-package installation record. "
            "Install dates are not release evidence."))
    if game.get("installer") != _MARKERS.get(recipe["id"]):
        return _result("Hub record · provenance unknown", detail="Installer marker is absent or does not match this game.")
    sha = record.get("sha256")
    if not _digest(sha):
        return _result("Hub package · release unknown", detail="Package record has no valid SHA-256 identity.")
    if sha != packages[0].get("sha256"):
        return _result("Recorded hash · pin differs", source="pin-mismatch", detail=(
            "Installed package archive hash does not match the current recipe pin. "
            "Recipe changes must not rewrite historical release identity."))
    files = record.get("files")
    if not isinstance(files, list) or not files or any(not isinstance(f, str) or not f for f in files):
        return _result("Hub package · files unrecorded", detail=(
            "Package SHA-256 matches the pin, but the record has no valid installed-file inventory."))
    tag = _source_tag(recipe, packages[0])
    if tag is not None:
        return _result("Recorded pin " + tag, tag, "recipe-pinned-hash", (
            "Hub package record archive SHA-256 equals the current recipe's pinned SHA-256. "
            "Release tag comes from the recipe's explicit source. Current installed "
            "file bytes, compatibility and runtime loading are NOT verified."), identified=True)
    return _result("Recorded pinned archive", source="recipe-pinned-hash", detail=(
        "Hub package record SHA-256 matches recipe pin, but no unambiguous "
        "release tag is present. Installed bytes are not rechecked."))


def _profile_evidence(recipe, component, state, row, warning):
    record = state.get(recipe["id"] + ":profile")
    if not isinstance(record, dict):
        return _result("Unknown", detail="No Hub UEVR profile installation record; manual profiles may exist.")
    if record.get("installer") != "uevr-profile-2":
        return _result("Legacy profile · version unknown", detail=(
            "Legacy profile record lacks cryptographically attributed installation evidence."))
    recorded_sha = record.get("archive_sha256")
    if not _digest(recorded_sha):
        return _result("Hub profile · release unknown", detail=(
            "Profile record has no valid source ZIP SHA-256."))
    installed = record.get("installed")
    files = installed.get("files") if isinstance(installed, dict) else None
    if (not isinstance(installed, dict) or installed.get("exists") is not True
            or not isinstance(files, dict) or not files
            or any(not isinstance(path, str) or not path
                   or not isinstance(info, dict) or not _digest(info.get("sha256"))
                   for path, info in files.items())):
        return _result("Recorded profile SHA · inventory unknown", detail=(
            "Source ZIP hash exists, but the installed profile snapshot is incomplete."))
    source = recipe.get("archive_releases", {}).get("profile")
    if not isinstance(source, dict) or not source.get("repo") or not source.get("asset"):
        return _result("Recorded profile SHA · release unknown", source="recorded-archive-hash",
                       detail="No explicit official profile asset configured in the current recipe.")
    # Do not infer a release tag from the active/latest online version, a
    # recipe's tested baseline, or a filename. Only match this exact installed
    # source ZIP digest to a unique official-release-tagged scan candidate.
    if warning or not isinstance(row, dict) or row.get("candidate_incomplete") or row.get("ambiguous"):
        return _result("Recorded profile SHA · release unknown", source="recorded-archive-hash",
                       detail="Profile ZIP hash recorded; active scan is unavailable or incomplete.")
    if row.get("status") not in ("Possible archive — inspect first", "Pinned SHA-256 verified"):
        return _result("Recorded profile SHA · release unknown", source="recorded-archive-hash",
                       detail="Profile ZIP hash recorded; no usable official release candidate.")
    tags = set()
    for candidate in row.get("candidates", []):
        if (not isinstance(candidate, dict) or candidate.get("sha256") != recorded_sha):
            continue
        release_tags = candidate.get("tags")
        if not isinstance(release_tags, list) or len(release_tags) != 1:
            continue
        tag = release_tags[0]
        if isinstance(tag, str) and _RELEASE.fullmatch(tag):
            tags.add(tag)
    if len(tags) == 1:
        tag = next(iter(tags))
        return _result("Recorded profile " + tag, tag, "official-hash-match", (
            "Installed profile record's source ZIP SHA-256 matches an official "
            "release's SHA-256 in the current read-only scan. This attributes "
            "the ORIGINAL profile archive only; current installed profile bytes "
            "and compatibility are NOT verified."), identified=True)
    return _result("Recorded profile SHA · release unknown", source="recorded-archive-hash",
                   detail="Hub has the original profile archive hash but cannot map "
                          "it unambiguously to an official release in the active scan.")


def _cyberpunk_evidence(recipe, component, game):
    rid = str(component["id"])
    components = game.get("components") if isinstance(game, dict) else None
    record = components.get(rid) if isinstance(components, dict) else None
    if not isinstance(record, dict):
        return _result("Unknown", detail="No per-mod Hub record; a manual install may exist.")
    if game.get("installer") not in (None, "gameroot-2"):
        return _result("Hub record · provenance unknown", detail=(
            "The recorded installer does not match the Cyberpunk game-root handler."))
    files = record.get("files")
    if not isinstance(files, list) or not files or any(not isinstance(f, str) or not f for f in files):
        return _result("Hub record · version unknown", detail=(
            "No trustworthy installed-file inventory recorded for this mod."))
    archive = record.get("archive")
    if not isinstance(archive, str) or Path(archive).name != archive:
        return _result("Hub record · version unknown", detail=(
            "No recognizable source archive filename in the per-mod Hub record."))
    parsed = updates._installed_archive_version(archive, int(rid))
    if parsed:
        label = ".".join(map(str, parsed))
        hashes = game.get("installed_sha256")
        manifest = bool(game.get("installer") == "gameroot-2" and
                        isinstance(hashes, dict) and hashes)
        detail = ("Version parsed from the archive filename recorded for this Nexus mod ID. "
                  "No cryptographic release identity or current installed byte verification. "
                  + ("A post-install file hash manifest is stored, but has not been rechecked."
                     if manifest else "No current file-hash evidence has been checked."))
        return _result("Recorded filename " + label, label, "filename-only", detail)
    return _result("Hub record · version unknown", detail=(
        "Per-mod Hub archive recorded, but its filename does not establish a version."))


def evidence(recipe, component, state, row=None, warning=None):
    """Return a non-authorizing, provenance-labelled view of installed state."""
    if not isinstance(state, dict):
        return _result("Unknown", detail="Hub installation state cannot be interpreted.")
    rid = str(component["id"])
    if recipe.get("packages"):
        return _package_evidence(recipe, component, state.get(recipe["id"]))
    if recipe.get("components") and rid.isdecimal():
        return _cyberpunk_evidence(recipe, component, state.get(recipe["id"]))
    if (recipe.get("method") == "uevr" and rid == "profile" and recipe.get("profile")):
        return _profile_evidence(recipe, component, state, row, warning)
    game = state.get(recipe["id"])
    if not isinstance(game, dict):
        return _result("Unknown", detail="No Hub record for this dependency; manual installations may exist.")
    return _result("Hub record · version unknown", detail=(
        "A game-level Hub record exists, but this dependency has no recorded "
        "release hash. Installation dates and online releases are not version evidence."))
