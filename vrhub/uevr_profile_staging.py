# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-O: whole-directory UEVR profile staging and recovery, FIXTURE ONLY.

This is not a live profile installer. Inputs are freshly supplied SYNTHETIC
bytes and version declarations; no API accepts a real game/prefix/ZIP path.
All writes occur under offline_transaction.fixture_sandbox() in private /tmp
and no live execution or mod-update permission is ever produced.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import install_review, offline_transaction as tx, profile_safety

SUPPORTED = frozenset(("fatekeeper", "hogwarts-legacy"))
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_PROFILE_BYTES = tx.MAX_TOTAL_BYTES
MAX_PROFILE_FILES = tx.MAX_FILES
MAX_PROFILE_DIRS = tx.MAX_DIRECTORIES
VERSION_RE = re.compile(r"v?(0|[1-9]\d*)(?:\.(0|[1-9]\d*))*\Z")


class ProfileStageBlocked(RuntimeError):
    """Synthetic profile review or staging failed closed."""


class ProfileRecoveryBlocked(ProfileStageBlocked):
    """Fixture changed, backup invalid or unsafe; do not overwrite user data."""


@dataclass(frozen=True)
class StagedProfile:
    game_id: str
    current_version: str
    future_version: str
    game_build: str
    archive_sha256: str
    current: dict[str, bytes]
    recorded_sha256: dict[str, str]
    current_dirs: tuple[str, ...]
    candidate: dict[str, bytes]
    explicit_removals: tuple[str, ...]
    replacements: tuple[str, ...]
    additions: tuple[str, ...]
    review_fingerprint: str
    status: str = "Synthetic UEVR profile reviewed — LIVE UPDATE BLOCKED"
    authorized: bool = False
    real_game_compatibility_verified: bool = False
    injector_installation_authorized: bool = False
    live_executor_connected: bool = False


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _bytes_map(data, *, require_config):
    if not isinstance(data, dict) or not data or len(data) > MAX_PROFILE_FILES:
        raise ProfileStageBlocked("Missing, empty, or excessive synthetic profile files.")
    try:
        tx._check_names(data)
    except tx.TransactionBlocked as exc:
        raise ProfileStageBlocked("Unsafe or case-colliding profile path.") from exc
    if (require_config and "config.txt" not in data) or not all(
            isinstance(v, bytes) and len(v) <= tx.MAX_FILE_BYTES for v in data.values()):
        raise ProfileStageBlocked("Profile config.txt or bounded byte data is missing.")
    if sum(map(len, data.values())) > MAX_PROFILE_BYTES:
        raise ProfileStageBlocked("Profile exceeds synthetic byte limit.")


def _directory_names(dirs, file_names):
    if not isinstance(dirs, (tuple, list)) or len(dirs) > MAX_PROFILE_DIRS:
        raise ProfileStageBlocked("Profile directory inventory exceeds limit.")
    if len(dirs) != len(set(dirs)):
        raise ProfileStageBlocked("Duplicate original profile directory.")
    try:
        for directory in dirs:
            tx._relative(directory)
    except tx.TransactionBlocked as exc:
        raise ProfileStageBlocked("Unsafe original profile directory.") from exc
    all_dirs = set(dirs)
    for rel in file_names:
        parts = rel.split("/")
        all_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
    for directory in list(all_dirs):
        parts = directory.split("/")
        all_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
    if len(all_dirs) > MAX_PROFILE_DIRS:
        raise ProfileStageBlocked("Original profile has too many directories.")
    combined = [*all_dirs, *file_names]
    if len({name.casefold() for name in combined}) != len(combined):
        raise ProfileStageBlocked("Profile contains case-colliding files or directories.")
    if any(
            any(part == file for file in file_names)
            for name in file_names for part in (
                "/".join(name.split("/")[:i]) for i in range(1, len(name.split("/"))))
    ):
        raise ProfileStageBlocked("Profile contains a file/directory collision.")
    return tuple(sorted(all_dirs))


def _version(value):
    if not isinstance(value, str) or len(value) > 80 or not VERSION_RE.fullmatch(value):
        raise ProfileStageBlocked("Synthetic profile versions must have numeric release labels.")
    return tuple(int(part) for part in value.removeprefix("v").split("."))


def _fingerprint(plan):
    body = {
        "game_id": plan.game_id, "current_version": plan.current_version,
        "future_version": plan.future_version, "game_build": plan.game_build,
        "archive_sha256": plan.archive_sha256,
        "current": {key: _sha(value) for key, value in sorted(plan.current.items())},
        "recorded": plan.recorded_sha256,
        "current_dirs": plan.current_dirs,
        "candidate": {key: _sha(value) for key, value in sorted(plan.candidate.items())},
        "removals": plan.explicit_removals,
        "replacements": plan.replacements, "additions": plan.additions,
    }
    return _sha(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())


def _archive(raw, expected_sha):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ZIP_BYTES:
        raise ProfileStageBlocked("Only bounded synthetic ZIP bytes are supported.")
    if not isinstance(expected_sha, str) or _sha(raw) != expected_sha:
        raise ProfileStageBlocked("Synthetic ZIP SHA-256 pin missing or mismatched.")
    with tempfile.TemporaryDirectory(prefix="nanners-dev5d3o-profile-", dir="/tmp") as folder:
        archive = Path(folder) / "synthetic-profile.zip"
        archive.write_bytes(raw)
        archive.chmod(0o600)
        try:
            install_review._zip_preflight(archive)
            with zipfile.ZipFile(archive) as z:
                entries = profile_safety._archive_entries(z)
                all_files = {info.filename for info in z.infolist() if not info.is_dir()}
                used = {info.filename for info, _ in entries}
                if all_files != used:
                    raise ProfileStageBlocked(
                        "Unexpected files outside the selected UEVR profile wrapper.")
                data = {}
                for info, rel in entries:
                    try:
                        tx._relative(rel)
                    except tx.TransactionBlocked as exc:
                        raise ProfileStageBlocked("Unsafe profile-relative archive member.") from exc
                    if rel in data:
                        raise ProfileStageBlocked("Duplicate profile target.")
                    with z.open(info) as stream:
                        payload = stream.read(tx.MAX_FILE_BYTES + 1)
                    if len(payload) != info.file_size or len(payload) > tx.MAX_FILE_BYTES:
                        raise ProfileStageBlocked("Profile member is incomplete or oversized.")
                    data[rel] = payload
                    if sum(len(v) for v in data.values()) > MAX_PROFILE_BYTES:
                        raise ProfileStageBlocked("Staged profile exceeds synthetic byte limit.")
                _bytes_map(data, require_config=True)
                _directory_names([], list(data))
            if profile_safety._digest(archive) != expected_sha:
                raise ProfileStageBlocked("Synthetic ZIP changed during staging.")
            return data
        except (zipfile.BadZipFile, EOFError, install_review.PlanRejected,
                RuntimeError, OSError, ValueError, KeyError) as exc:
            if isinstance(exc, ProfileStageBlocked):
                raise
            raise ProfileStageBlocked("UEVR archive mapping failed its existing safety checks.") from exc


def prepare_fixture(game_id, raw_zip, expected_sha, *, current, recorded_sha256,
                    current_dirs=(), recorded_dirs=None, current_version, future_version,
                    game_build, compatible_builds, compatible_injector_versions,
                    injector_version, explicit_removals=()):
    """Review synthetic Fatekeeper/Hogwarts profile bytes, never a real path.

    Config files are not auto-merged; replacing them is explicit and
    rollback retains the complete original directory. Missing old files
    require an explicit removal list, and unowned/manual changes block.
    Injector compatibility is a separate *fixture declaration* only.
    """
    if game_id not in SUPPORTED:
        raise ProfileStageBlocked("Only Fatekeeper/Hogwarts UEVR profile fixtures are supported.")
    _bytes_map(current, require_config=True)
    dirs = _directory_names(current_dirs, list(current))
    if (not isinstance(recorded_dirs, (tuple, list)) or
            tuple(sorted(recorded_dirs)) != dirs or
            len(recorded_dirs) != len(dirs)):
        raise ProfileStageBlocked("Current directory inventory diverges from recorded profile ownership.")
    if (not isinstance(recorded_sha256, dict) or
            set(recorded_sha256) != set(current) or
            any(not isinstance(x, str) or len(x) != 64 or
                x != _sha(current[name]) for name, x in recorded_sha256.items())):
        raise ProfileStageBlocked("Untracked or changed installed profile file; manual review required.")
    if _version(future_version) <= _version(current_version):
        raise ProfileStageBlocked("Only genuinely newer numeric synthetic profile versions are eligible.")
    if (not isinstance(game_build, str) or not game_build or len(game_build) > 80 or
            not isinstance(compatible_builds, (list, tuple)) or
            not compatible_builds or len(compatible_builds) > 20 or
            any(not isinstance(v, str) or not v or len(v) > 80 for v in compatible_builds) or
            game_build not in compatible_builds):
        raise ProfileStageBlocked("Synthetic game-build compatibility not declared.")
    if (not isinstance(injector_version, str) or not injector_version or
            not isinstance(compatible_injector_versions, (list, tuple)) or
            not compatible_injector_versions or injector_version not in compatible_injector_versions):
        raise ProfileStageBlocked("Matching UEVR injector compatibility not independently declared.")
    new = _archive(raw_zip, expected_sha)
    missing = set(current) - set(new)
    if (not isinstance(explicit_removals, (tuple, list)) or
            set(explicit_removals) != missing or len(explicit_removals) != len(missing)):
        raise ProfileStageBlocked(
            "Old profile file removal requires an exact explicit review; no silent pruning.")
    if any(current[name] == new[name] for name in set(current) & set(new)):
        raise ProfileStageBlocked("Unchanged profile file requires separate no-op review.")
    replacements = tuple(sorted(set(current) & set(new)))
    additions = tuple(sorted(set(new) - set(current)))
    provisional = StagedProfile(
        game_id, current_version, future_version, game_build,
        expected_sha, dict(current), dict(recorded_sha256), dirs, new,
        tuple(sorted(missing)), replacements, additions, "",
    )
    from dataclasses import replace
    return replace(provisional, review_fingerprint=_fingerprint(provisional))


def _verified_snapshot(path, expected, *, described):
    try:
        actual = profile_safety._snapshot(path)
        if actual != expected:
            raise ProfileRecoveryBlocked(f"{described} directory snapshot changed; preserve evidence.")
        return actual
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, ProfileRecoveryBlocked):
            raise
        raise ProfileRecoveryBlocked(f"Unsafe {described} profile tree.") from exc


def _document(fixture, *, optional=False):
    doc = tx._load_doc(fixture, "transaction", "uevr-profile-journal.json", optional=optional)
    if doc is None:
        return None
    seal = doc.pop("seal", None)
    if (seal != tx._seal(doc, fixture.token) or doc.get("schema") != 1
            or doc.get("kind") != "uevr-profile-fixture"
            or doc.get("root") != str(fixture.root)):
        raise ProfileRecoveryBlocked("Synthetic profile recovery journal is invalid.")
    return doc


def _save_document(fixture, doc):
    tx._save_doc(fixture, "transaction", "uevr-profile-journal.json",
                 {**doc, "seal": tx._seal(doc, fixture.token)})


def _check_modes(root, expected_files, expected_dirs):
    # Only inspect inside a verified private fixture tree. Refuse symlinked
    # entries and unexpected changes to permissions before a rename.
    try:
        if (not isinstance(expected_files, dict) or
                not isinstance(expected_dirs, dict) or
                len(expected_files) > MAX_PROFILE_FILES or
                len(expected_dirs) > MAX_PROFILE_DIRS):
            raise ProfileRecoveryBlocked("Invalid recorded permission inventory.")
        for rel, expected in expected_files.items():
            if type(expected) is not int or not 0 <= expected <= 0o7777:
                raise ProfileRecoveryBlocked("Invalid recorded file mode.")
            path = root / rel
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != expected:
                raise ProfileRecoveryBlocked("Original profile file permission changed.")
        actual_dirs = {}
        for parent, dirs, _ in os.walk(root, followlinks=False):
            for directory in dirs:
                entry = Path(parent) / directory
                st = entry.lstat()
                if not stat.S_ISDIR(st.st_mode):
                    raise ProfileRecoveryBlocked("Original profile directory is unsafe.")
                actual_dirs[entry.relative_to(root).as_posix()] = stat.S_IMODE(st.st_mode)
        if actual_dirs != expected_dirs:
            raise ProfileRecoveryBlocked("Original profile directory permissions changed.")
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, ProfileRecoveryBlocked):
            raise
        raise ProfileRecoveryBlocked("Unable to verify original profile permissions.") from exc


def _restore_modes(fixture, original_modes, original_dir_modes):
    _check_modes(fixture.root / "installed", original_modes, original_dir_modes)


def _tree_modes(root):
    files, directories = {}, {}
    for parent, subdirs, filenames in os.walk(root, followlinks=False):
        for name in subdirs:
            path = Path(parent) / name
            st = path.lstat()
            if not stat.S_ISDIR(st.st_mode):
                raise ProfileRecoveryBlocked("Unsafe staged profile directory.")
            directories[path.relative_to(root).as_posix()] = stat.S_IMODE(st.st_mode)
        for name in filenames:
            path = Path(parent) / name
            st = path.lstat()
            if not stat.S_ISREG(st.st_mode):
                raise ProfileRecoveryBlocked("Unsafe staged profile file.")
            files[path.relative_to(root).as_posix()] = stat.S_IMODE(st.st_mode)
    return files, directories


def _stage_copy(fixture, data):
    stage = fixture.root / "transaction/profile-stage"
    stage.mkdir(mode=0o700)
    for name, content in sorted(data.items()):
        tx._write(fixture, "transaction", "profile-stage/" + name, content)
    return stage


def execute_fixture(fixture, plan, *, fault=None):
    """Serialized, fixture-only profile replacement simulation."""
    tx._assert_fixture(fixture)
    with tx._locked(fixture):
        return _execute_fixture_inner(fixture, plan, fault=fault)


def _execute_fixture_inner(fixture, plan, *, fault=None):
    """Only a private synthetic fixture handle is accepted; never live."""
    tx._assert_fixture(fixture)
    if not isinstance(plan, StagedProfile) or plan.game_id not in SUPPORTED:
        raise ProfileStageBlocked("Only verified synthetic UEVR profile plans are allowed.")
    if _fingerprint(plan) != plan.review_fingerprint:
        raise ProfileStageBlocked("Synthetic profile plan was changed after review.")
    if _document(fixture, optional=True) is not None:
        raise ProfileStageBlocked("Existing fixture journal must be recovered first.")
    installed = fixture.root / "installed"
    if not stat.S_ISDIR(os.lstat(installed).st_mode):
        raise ProfileStageBlocked("Current profile root is unsafe.")
    original = profile_safety._snapshot(installed)
    actual_current = {
        name: (len(payload), _sha(payload))
        for name, payload in plan.current.items()
    }
    if (set(original["files"]) != set(actual_current) or
            any(original["files"][name] !=
                {"size": actual_current[name][0], "sha256": actual_current[name][1]}
                for name in actual_current) or
            set(original["dirs"]) != set(plan.current_dirs)):
        raise ProfileStageBlocked("Current synthetic profile changed after staging review.")
    backup = fixture.root / "transaction/profile-backup"
    staged = fixture.root / "transaction/profile-stage"
    displaced = fixture.root / "transaction/profile-displaced"
    rejected = fixture.root / "transaction/profile-rejected"
    if any(path.exists() or path.is_symlink()
           for path in (backup, staged, displaced, rejected)):
        raise ProfileStageBlocked("Staging or recovery paths already exist.")
    try:
        space = shutil.disk_usage(fixture.root).free
    except OSError as exc:
        raise ProfileStageBlocked("Cannot verify temporary profile staging capacity.") from exc
    required = original["bytes"] + sum(map(len, plan.candidate.values())) + 8 * 1024 * 1024
    if space < required:
        raise ProfileStageBlocked("Insufficient temporary space for full backup and staged profile.")
    modes = {name: tx._mode(fixture, "installed", name) for name in plan.current}
    dirs = tx._snapshot_dirs(fixture)
    journal = {
        "schema": 1, "kind": "uevr-profile-fixture", "root": str(fixture.root),
        "phase": "preparing", "game_id": plan.game_id,
        "fingerprint": plan.review_fingerprint,
        "before": original, "after": None,
        "modes_before": modes, "dirs_before": dirs,
    }
    _save_document(fixture, journal)
    if fault == "after_journal":
        raise tx.SimulatedCrash("Interrupted before whole-directory backup.")
    profile_safety._verified_copy(installed, backup, original)
    if fault == "after_backup":
        raise tx.SimulatedCrash("Interrupted after whole-directory backup.")
    _stage_copy(fixture, plan.candidate)
    after = profile_safety._snapshot(staged)
    wanted = {
        "exists": True, "files": {
            name: {"sha256": _sha(payload), "size": len(payload)}
            for name, payload in plan.candidate.items()
        },
        "dirs": after["dirs"], "bytes": sum(len(x) for x in plan.candidate.values()),
    }
    if after != wanted:
        raise ProfileStageBlocked("Staged whole-directory snapshot failed SHA-256 validation.")
    _verified_snapshot(installed, original, described="current")
    _verified_snapshot(backup, original, described="fresh backup")
    if _fingerprint(plan) != plan.review_fingerprint:
        raise ProfileStageBlocked("Synthetic archive inputs changed during staging; no swap.")
    journal["after"] = after
    journal["modes_after"], journal["dirs_after"] = _tree_modes(staged)
    journal["phase"] = "prepared"
    _save_document(fixture, journal)
    if fault == "after_prepare":
        raise tx.SimulatedCrash("Interrupted after complete profile staging.")
    installed.rename(displaced)
    tx._fsync_directory(installed.parent)
    if fault == "after_displace":
        raise tx.SimulatedCrash("Interrupted after moving original profile aside.")
    staged.rename(installed)
    tx._fsync_directory(installed.parent)
    if fault == "after_activate":
        raise tx.SimulatedCrash("Interrupted after new profile activation.")
    _verified_snapshot(installed, after, described="activated")
    journal["phase"] = "committed"
    _save_document(fixture, journal)
    if fault == "after_commit":
        raise tx.SimulatedCrash("Interrupted after fixture commit marker.")
    return {"status": "Committed to disposable UEVR profile fixture",
            "files": len(after["files"]), "authorized": False,
            "real_game_files_modified": False}


def _verify_journal(fixture, journal):
    before = journal.get("before")
    after = journal.get("after")
    if (not isinstance(before, dict) or not isinstance(journal.get("dirs_before"), dict)
            or not isinstance(journal.get("modes_before"), dict)
            or not isinstance(journal.get("fingerprint"), str)
            or not journal["fingerprint"]):
        raise ProfileRecoveryBlocked("Profile recovery snapshot metadata is incomplete.")
    for snapshot in (before, after):
        if snapshot is None:
            continue
        if (snapshot.get("exists") is not True or
                not isinstance(snapshot.get("files"), dict) or
                not isinstance(snapshot.get("dirs"), list) or
                type(snapshot.get("bytes")) is not int):
            raise ProfileRecoveryBlocked("Profile recovery file inventory is inconsistent.")
    if after is not None and (not isinstance(journal.get("modes_after"), dict) or
                              not isinstance(journal.get("dirs_after"), dict)):
        raise ProfileRecoveryBlocked("Staged profile permission inventory is incomplete.")
    return before, after


def recover_fixture(fixture, *, explicit=False, fault=None):
    """Serialized fixture-only whole-profile recovery."""
    tx._assert_fixture(fixture)
    with tx._locked(fixture):
        return _recover_fixture_inner(fixture, explicit=explicit, fault=fault)


def _recover_fixture_inner(fixture, *, explicit=False, fault=None):
    """Rehearse whole-profile rollback. Never touch a real prefix/profile."""
    tx._assert_fixture(fixture)
    doc = _document(fixture)
    if doc is None:
        raise ProfileRecoveryBlocked("No UEVR profile fixture journal exists.")
    before, after = _verify_journal(fixture, doc)
    phase = doc.get("phase")
    if phase == "restored":
        _verified_snapshot(fixture.root / "installed", before, described="already restored")
        _restore_modes(fixture, doc["modes_before"], doc["dirs_before"])
        return {"status": "Already restored original fixture profile",
                "authorized": False}
    if phase == "committed" and not explicit:
        raise ProfileRecoveryBlocked("Committed fixture requires explicit rollback.")
    if phase not in ("preparing", "prepared", "committed", "restoring"):
        raise ProfileRecoveryBlocked("Unknown fixture recovery phase.")
    installed = fixture.root / "installed"
    displaced = fixture.root / "transaction/profile-displaced"
    backup = fixture.root / "transaction/profile-backup"
    rejected = fixture.root / "transaction/profile-rejected"
    # An interrupted incomplete backup/stage cannot be certified as a
    # recovery copy. No directory swap was attempted before prepared, so
    # safely abort by proving the ORIGINAL tree is still completely intact.
    if phase == "preparing" and after is None:
        if (displaced.exists() or displaced.is_symlink() or
                rejected.exists() or rejected.is_symlink()):
            raise ProfileRecoveryBlocked("Displacement during incomplete preparation is unsafe.")
        _verified_snapshot(installed, before, described="original preparation")
        _check_modes(installed, doc["modes_before"], doc["dirs_before"])
        doc["phase"] = "restored"
        _save_document(fixture, doc)
        return {"status": "Aborted incomplete profile preparation; partial backup untrusted",
                "restored_files": len(before["files"]), "authorized": False,
                "partial_backup_trusted": False}
    # Refuse ANY tampered complete backup or unexpected active/displaced
    # directory BEFORE moving or deleting any profile data.
    if backup.exists() or backup.is_symlink():
        _verified_snapshot(backup, before, described="fresh backup")
        _check_modes(backup, doc["modes_before"], doc["dirs_before"])
    elif phase != "preparing":
        raise ProfileRecoveryBlocked("Complete whole-directory backup is missing.")
    if displaced.exists() or displaced.is_symlink():
        _verified_snapshot(displaced, before, described="displaced original")
        _check_modes(displaced, doc["modes_before"], doc["dirs_before"])
    if rejected.exists() or rejected.is_symlink():
        if after is None:
            raise ProfileRecoveryBlocked("Unexpected staged profile recovery copy.")
        _verified_snapshot(rejected, after, described="rejected staged profile")
        _check_modes(rejected, doc["modes_after"], doc["dirs_after"])
    if installed.exists() or installed.is_symlink():
        current = profile_safety._snapshot(installed)
        if current not in (before, after):
            raise ProfileRecoveryBlocked("Unexpected user-edited active profile; refuse rollback.")
        if current == before:
            _check_modes(installed, doc["modes_before"], doc["dirs_before"])
        elif current == after:
            _check_modes(installed, doc["modes_after"], doc["dirs_after"])
    else:
        current = None
    if phase in ("prepared", "committed", "restoring") and after is None:
        raise ProfileRecoveryBlocked("Committed fixture has no verified staged snapshot.")
    if phase == "preparing" and after is None and displaced.exists():
        raise ProfileRecoveryBlocked("An incomplete backup cannot authorize a profile swap.")
    if current is None and not displaced.exists():
        raise ProfileRecoveryBlocked("Both original and activated profile trees are missing.")
    if displaced.exists() and current == before:
        raise ProfileRecoveryBlocked("Two different original copies occupy recovery paths.")
    if rejected.exists() and current == after:
        raise ProfileRecoveryBlocked("Two active replacement copies occupy recovery paths.")
    # An aborted preparation or completed rollback is idempotent, but still
    # requires complete backup/permission validation where available.
    if current == before and not displaced.exists():
        _restore_modes(fixture, doc["modes_before"], doc["dirs_before"])
        doc["phase"] = "restored"
        _save_document(fixture, doc)
        return {"status": "Original UEVR fixture profile intact or restored",
                "restored_files": len(before["files"]), "authorized": False}
    if current is None and not displaced.exists():
        raise ProfileRecoveryBlocked("No verified displaced profile remains to restore.")
    doc["phase"] = "restoring"
    _save_document(fixture, doc)
    if current == after:
        if rejected.exists() or rejected.is_symlink():
            raise ProfileRecoveryBlocked("Rejection destination already contains recovery data.")
        installed.rename(rejected)
        tx._fsync_directory(installed.parent)
        if fault == "after_reject":
            raise tx.SimulatedCrash("Interrupted while setting aside staged profile.")
    if not displaced.exists():
        raise ProfileRecoveryBlocked("Verified displaced original is missing.")
    displaced.rename(installed)
    tx._fsync_directory(installed.parent)
    if fault == "after_restore":
        raise tx.SimulatedCrash("Interrupted just after original profile restoration.")
    _verified_snapshot(installed, before, described="restored")
    _restore_modes(fixture, doc["modes_before"], doc["dirs_before"])
    doc["phase"] = "restored"
    _save_document(fixture, doc)
    return {"status": "Restored complete original UEVR fixture profile",
            "restored_files": len(before["files"]),
            "restored_directories": len(before["dirs"]),
            "authorized": False, "live_executor_connected": False}


def _synthetic_zip(wrapper, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            z.writestr(wrapper + "/" + name, body)
    return buf.getvalue()


def _scenario(game):
    wrapper = "SLASHER-Win64-Shipping" if game == "fatekeeper" else "HogwartsLegacy"
    current = {
        "config.txt": b"old-config-" + game.encode(),
        "scripts/input.lua": b"old-script",
        "user-mappings/settings.ini": b"recorded-settings",
    }
    future = {
        "config.txt": b"new-config-" + game.encode(),
        "scripts/input.lua": b"new-script",
        "plugins/gesture.lua": b"new-gesture",
    }
    raw = _synthetic_zip(wrapper, future)
    return prepare_fixture(
        game, raw, _sha(raw),
        current=current, recorded_sha256={k: _sha(v) for k, v in current.items()},
        current_dirs=("empty-preserved", "user-mappings"),
        recorded_dirs=("empty-preserved", "scripts", "user-mappings"),
        current_version="v1.0.0", future_version="v1.1.0",
        game_build="SIMULATED-UEVR-GAME-BUILD",
        compatible_builds=("SIMULATED-UEVR-GAME-BUILD",),
        injector_version="TEST-INJECTOR-1",
        compatible_injector_versions=("TEST-INJECTOR-1",),
        explicit_removals=("user-mappings/settings.ini",),
    )


def rehearse_uevr_profiles():
    """Two self-contained synthetic whole-tree staging/rollback rehearsals."""
    rows = []
    for game in ("fatekeeper", "hogwarts-legacy"):
        plan = _scenario(game)
        with tx.fixture_sandbox(plan.current, plan.candidate,
                                managed=tuple(plan.current)) as fixture:
            for name in plan.current_dirs:
                path = fixture.root / "installed" / name
                path.mkdir(parents=True, exist_ok=True)
            prior = profile_safety._snapshot(fixture.root / "installed")
            try:
                execute_fixture(fixture, plan, fault="after_activate")
            except tx.SimulatedCrash:
                pass
            else:
                raise AssertionError("Expected simulated UEVR swap interruption.")
            restored = recover_fixture(fixture)
            if (profile_safety._snapshot(fixture.root / "installed") != prior or
                    restored["authorized"] or
                    not (fixture.root / "installed/empty-preserved").is_dir() or
                    (fixture.root / "installed/plugins/gesture.lua").exists()):
                raise AssertionError("Original full directory was not restored.")
            rows.append({
                "game": game, "synthetic_archive_verified": True,
                "whole_directory_backup_verified": True,
                "replacement_staging_verified": True,
                "rollback_passed": True,
                "original_directories_restored": True,
                "profile_files_restored": restored["restored_files"],
                "injector_separately_managed": True,
                "real_compatibility_verified": False,
                "authorized": False,
            })
    return {
        "fixture_only": True, "results": rows,
        "temporary_fixtures_discarded": True,
        "live_profile_replacement_enabled": False,
        "injector_installation_enabled": False,
        "real_game_compatibility_verified": False,
        "real_game_files_modified": False,
        "authorized": False,
    }
