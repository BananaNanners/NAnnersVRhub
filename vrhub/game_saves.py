# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Development-only save recovery adapters. No cloud sync or progress guessing."""
import hashlib
import json
import os
import stat
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, doom_saves, hub, self_install, save_locations
from .recovery_discovery import recent_recovery_folders, selection_notes

FLAG = "NANNERS_DEV_SAVE_RECOVERY"
# Save-only roots; settings folders are deliberately excluded.
LAYOUTS = {
    "cyberpunk-2077": ("Saved Games/CD Projekt Red/Cyberpunk 2077",),
    "fatekeeper": ("AppData/Local/SLASHER/Saved/SaveGames",),
    "ready-or-not": ("AppData/Local/ReadyOrNot/Saved/SaveGames",),
    "hogwarts-legacy": ("AppData/Local/Hogwarts Legacy/Saved/SaveGames",),
    "elden-ring": ("AppData/Roaming/EldenRing",),
    "skyrim-vr-mgo": ("Documents/My Games/Skyrim VR/Saves",),
    "valheim": ("AppData/LocalLow/IronGate/Valheim/characters_local",
                "AppData/LocalLow/IronGate/Valheim/worlds_local"),
    "subnautica": (), "doom-2016-gog": (),
}
PROCESSES = ("doomx64", "kharvox", "heroic", "steam", "steamwebhelper", "uevr", "modorganizer",
             "skyrimvr", "sksevr", "slasher", "readyornot", "cyberpunk2077", "hogwartslegacy",
             "subnautica", "valheim", "eldenring", "start_protected")


def enabled():
    return os.environ.get(FLAG) == "1"


def file_observations(root, *, max_entries=8192):
    """Bounded, stat-only diagnostics. Never makes an invalid set restorable."""
    root = Path(root)
    newest, count, entries, issues = None, 0, 0, []
    pending = [root]
    try:
        if not stat.S_ISDIR(root.lstat().st_mode):
            raise OSError("Folder is missing, linked or not a directory.")
        while pending:
            folder = pending.pop()
            try:
                with os.scandir(folder) as children:
                    for child in children:
                        entries += 1
                        if entries > max_entries:
                            issues.append("File scan limit reached.")
                            pending.clear()
                            break
                        try:
                            info = child.stat(follow_symlinks=False)
                            if stat.S_ISLNK(info.st_mode):
                                issues.append("Linked entries were skipped.")
                            elif stat.S_ISDIR(info.st_mode):
                                pending.append(Path(child.path))
                            elif stat.S_ISREG(info.st_mode):
                                count += 1
                                if doom_saves._stamp(info.st_mtime) is not None:
                                    newest = info.st_mtime if newest is None else max(newest, info.st_mtime)
                                else:
                                    issues.append("A file timestamp could not be represented.")
                            else:
                                issues.append("Non-regular entries were skipped.")
                        except OSError as exc:
                            issues.append(f"File metadata unavailable: {exc}")
            except OSError as exc:
                issues.append(f"Folder metadata unavailable: {exc}")
    except OSError as exc:
        issues.append(str(exc))
    partial = bool(issues)
    reason = "; ".join(dict.fromkeys(issues))[:1000]
    if newest is None:
        reason = reason or "No regular files were found in this folder."
    return dict(file_modified_at=doom_saves._stamp(newest) if newest is not None else None,
                observed_file_count=count, observation_partial=partial,
                date_reason=reason, date_source="Observed folder file modification time")


def compare_files(source, target):
    """Describe whole-folder replacement from the target's point of view.

    Inputs are scanned relative-path -> SHA-256 inventories. No disk writes or
    interpretation of gameplay progress, timestamps or file contents occur.
    """
    source_paths, target_paths = set(source), set(target)
    common = source_paths & target_paths
    return {"added": sorted(source_paths - target_paths),
            "changed": sorted(path for path in common if source[path] != target[path]),
            "removed": sorted(target_paths - source_paths),
            "unchanged": sorted(path for path in common if source[path] == target[path])}


class BackupVerificationError(RuntimeError):
    """A backup cannot be authorized by a manual confirmation."""


class GameSaves:
    def __init__(self, recipe, *, development_enabled=None):
        self.development_enabled = development_enabled
        self.recipe = recipe
        self.rid = recipe["id"]
        if self.rid not in LAYOUTS:
            raise RuntimeError("No save recovery adapter for this game.")
        self.target = None
        self.manual_target = False
        self.target_roles = {}
        self.backup_prefix = f"game-saves-{self.rid}-"

    def validate_target_folder(self, path):
        """Read-only validation; a rejected choice must not change the target."""
        try:
            root = Path(path).expanduser().resolve(strict=True)
            if root.is_relative_to((hub.state_file().parent / "backups").resolve()):
                raise RuntimeError("This is a recovery backup. Use it as a source; choose the game's save folder as the target.")
            if not root.is_dir():
                raise RuntimeError("This location is not a folder. Choose the game's save folder.")
            if next(root.iterdir(), None) is None:
                raise RuntimeError("This folder is empty. Choose a folder that already contains this game's saves.")
            self.snapshot(root)
            return str(root)
        except PermissionError as exc:
            raise RuntimeError("Access denied while reading this folder or its saves. Choose a readable save folder or check its permissions.") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("The folder or a save file no longer exists. Rescan or choose its current location.") from exc
        except NotADirectoryError as exc:
            raise RuntimeError("This location is not a folder. Choose the game's save folder.") from exc

    def remember_folder(self, role, path):
        if not (enabled() if self.development_enabled is None else self.development_enabled):
            raise RuntimeError("Development save recovery is disabled.")
        if role not in {"sources", "targets"}:
            raise RuntimeError("Unknown remembered-folder role.")
        if role == "targets":
            root = Path(self.validate_target_folder(path))
        else:
            root = Path(path).expanduser().resolve(strict=True)
            self.snapshot(root)
        save_locations.remember(self.rid, role, str(root))
        return str(root)

    def forget_folders(self):
        if not (enabled() if self.development_enabled is None else self.development_enabled):
            raise RuntimeError("Development save recovery is disabled.")
        save_locations.forget(self.rid)

    def _prefix_roots(self, prefix):
        users = Path(prefix) / "drive_c/users"
        roots = set()
        for relative in LAYOUTS[self.rid]:
            for user in users.glob("*"):
                candidate = user / relative
                if candidate.is_dir():
                    roots.add(candidate.resolve())
        return roots

    def targets(self):
        if self.rid == "doom-2016-gog":
            return [doom_saves.current_target(self.recipe)]
        if self.rid == "subnautica":
            game = hub.game_path(self.recipe)
            root = game / "SNAppData/SavedGames" if game else None
            return sorted(p.resolve() for p in root.glob("slot*") if p.is_dir()) if root else []
        roots = set()
        self.target_roles = {}
        try:
            roots.update(self._prefix_roots(hub._pfx(self.recipe)))
            if self.rid == "skyrim-vr-mgo":
                self.target_roles.update({p: "Base-game Proton prefix (candidate)" for p in roots})
        except RuntimeError:
            if self.rid != "skyrim-vr-mgo":
                raise
        if self.rid == "skyrim-vr-mgo":
            from .handlers import get_handler
            handler = get_handler(self.recipe)
            mgo = handler._mgo_dir(self.recipe)
            if mgo:
                shortcut = handler._steam_shortcut(self.recipe, mgo)
                if shortcut:
                    steam_root = handler._steam_root_from_shortcut(shortcut)
                    appid = shortcut.get("appid")
                    if steam_root and type(appid) is int and 0 <= appid <= 0xFFFFFFFF:
                        prefix = steam_root / "steamapps/compatdata" / str(appid) / "pfx"
                        for path in self._prefix_roots(prefix):
                            roots.add(path)
                            self.target_roles[path] = "MO2 shortcut Proton prefix (candidate)"
                for path in (mgo / "profiles").glob("*/saves"):
                    if path.is_dir():
                        resolved = path.resolve()
                        roots.add(resolved)
                        self.target_roles[resolved] = "MO2 profile-local saves: " + path.parent.name
        return sorted(roots)

    def snapshot(self, root):
        if self.rid == "doom-2016-gog":
            row = doom_saves.snapshot(root)
            row["date_source"] = "DOOM save metadata" if row.get("saved_at") else "Checkpoint file modification time"
            if not row.get("saved_at"):
                row["saved_at"] = row.get("checkpoint_modified")
            return row
        root = Path(root).expanduser().resolve(strict=True)
        identity = doom_saves.directory_identity(root)
        files, total, newest, skyrim_newest = {}, 0, 0, None
        if not root.is_dir():
            raise RuntimeError("Choose an existing save directory.")
        for index, path in enumerate(root.rglob("*")):
            if index >= 8192 or path.is_symlink():
                raise RuntimeError("Save tree too large or contains linked entries.")
            if path.is_dir():
                continue
            if not path.is_file():
                raise RuntimeError("Non-regular save entry.")
            size = path.stat().st_size
            total += size
            if size > 256 * 1024**2 or total > 1024**3 or len(files) >= 4096:
                raise RuntimeError("Save set exceeds development recovery limits.")
            name = path.relative_to(root).as_posix()
            # Configuration files do not belong in these adapters' save roots.
            if path.suffix.casefold() in {".ini", ".cfg", ".exe", ".dll", ".so"}:
                raise RuntimeError("Folder contains configuration or executable files; choose a save-only folder.")
            with path.open("rb") as stream:
                files[name] = hashlib.file_digest(stream, "sha256").hexdigest()
            modified = path.stat().st_mtime
            newest = max(newest, modified)
            if self.rid == "skyrim-vr-mgo" and path.suffix.casefold() == ".ess":
                skyrim_newest = modified if skyrim_newest is None else max(skyrim_newest, modified)
        names = list(files)
        account = ""
        component = self.rid
        if self.rid in {"fatekeeper", "ready-or-not", "hogwarts-legacy"}:
            valid = any(n.casefold().endswith(".sav") and "/" not in n for n in names)
            if self.rid == "hogwarts-legacy":
                account = ",".join(sorted({n.split("/")[0] for n in names if n.count("/") == 1 and n.endswith(".sav")}))
                valid = bool(account) and all(n.count("/") == 1 for n in names if n.endswith(".sav"))
        elif self.rid == "cyberpunk-2077":
            valid = any(n.endswith("/sav.dat") and n.count("/") == 1 for n in names)
        elif self.rid == "elden-ring":
            accounts = {n.split("/")[0] for n in names if n.endswith("/ER0000.sl2") and n.count("/") == 1}
            valid = bool(accounts) and all(a.isdecimal() for a in accounts)
            account = ",".join(sorted(accounts))
        elif self.rid == "skyrim-vr-mgo":
            valid = any(n.casefold().endswith(".ess") for n in names)
            valid = valid and all("/" not in n and (n.casefold().endswith((".ess", ".skse", ".bak"))
                                                   or n.casefold() == "steam_autocloud.vdf") for n in names)
            # Preserve the complete folder, including Steam metadata, but use only
            # main save files for the displayed save timestamp.
            if skyrim_newest is not None:
                newest = skyrim_newest
        elif self.rid == "subnautica":
            valid = "gameinfo.json" in files and "global-objects.bin" in files
        elif self.rid == "valheim":
            chars = any(n.endswith(".fch") for n in names)
            worlds = any(n.endswith((".fwl", ".fwl2")) for n in names)
            component = "characters" if chars else "worlds"
            valid = chars != worlds
            if worlds:
                # Every world descriptor needs its corresponding database.
                valid = valid and all((n[:-4] + ".db" in files) if n.endswith(".fwl")
                                      else str(Path(n).with_suffix(".db2")) in files
                                      for n in names if n.endswith((".fwl", ".fwl2")))
        else:
            valid = False
        if not valid:
            raise RuntimeError("No recognized complete save set for this game. Do not select a prefix, game root or settings directory.")
        if doom_saves.directory_identity(root) != identity:
            raise RuntimeError("Save folder changed during scan. Scan and review it again.")
        return dict(root=str(root), directory_identity=identity, files=files, fingerprint=hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                    file_count=len(files), total_bytes=total, mission="Not parsed", saved_at=doom_saves._stamp(newest),
                    time_value="Unknown", game_version="", component=component, account=account,
                    date_source=("Skyrim .ess file modification time; Steam metadata excluded from date"
                                 if self.rid == "skyrim-vr-mgo" else "File modification time"))

    def current_target(self, recipe):
        if not self.target:
            raise RuntimeError("Select an active save target first.")
        path = Path(self.target).resolve(strict=True)
        if path.is_relative_to((hub.state_file().parent / "backups").resolve()):
            raise RuntimeError("A Hub backup cannot be the active save target; select the game save folder.")
        self.snapshot(path)
        if not self.manual_target and path not in self.targets():
            raise RuntimeError("The launcher or profile save location changed. Scan and select the target again.")
        return path

    def preview(self, source, target):
        source, target = Path(source).resolve(strict=True), Path(target).resolve(strict=True)
        if source == target or source.is_relative_to(target) or target.is_relative_to(source):
            raise RuntimeError("Source and target must be separate, non-overlapping save directories.")
        a, b = self.snapshot(source), self.snapshot(target)
        self.check_snapshot_source(source, a)
        if a["fingerprint"] == b["fingerprint"]:
            raise RuntimeError("Save sets already match.")
        if (a.get("component"), a.get("account")) != (b.get("component"), b.get("account")):
            raise RuntimeError("Save type or account differs. Account conversion is not supported.")
        if a.get("game_version") and b.get("game_version") and a["game_version"] != b["game_version"]:
            raise RuntimeError("Game versions differ.")
        return {"source": a, "target": b}

    def ensure_closed(self):
        for process in Path("/proc").glob("[0-9]*"):
            try:
                name = (process / "comm").read_text().strip().casefold()
            except OSError:
                continue
            if name.startswith(PROCESSES):
                raise RuntimeError("Close games, injectors, MO2, Steam and Heroic before restoring; cloud sync must be stopped.")

    def discover(self, recipe, extra_roots=()):
        notes, candidates, recovery_groups = [], {}, {}
        try:
            remembered = save_locations.load(self.rid)
        except (RuntimeError, OSError) as exc:
            remembered = {"sources": [], "targets": []}
            notes.append(str(exc))
        try:
            targets = self.targets()
        except (RuntimeError, OSError) as exc:
            targets = []
            notes.append(str(exc))
        if self.target:
            targets = sorted(set(targets + [Path(self.target).resolve()]))
        if not self.target and len(targets) == 1:
            self.target = str(targets[0])
        for path in targets:
            candidates[path] = "Active save location"
        for saved in remembered["targets"]:
            path = Path(saved)
            candidates.setdefault(path, "Active save location")
            self.target_roles.setdefault(path, "Remembered custom target (select to use)")
        for saved in remembered["sources"]:
            candidates.setdefault(Path(saved), "Remembered custom source")
        if self.rid == "doom-2016-gog":
            old = doom_saves.discover(recipe, extra_roots, include_backups=False)
            notes.extend(old["notes"])
            for row in old["rows"]:
                candidates[Path(row["root"])] = row["label"]
        else:
            # Only scan known lab prefixes, not the user's entire home or game libraries.
            lab = Path.home() / ".local/share/nanners-kharvox-lab"
            for count, (folder, dirs, _) in enumerate(os.walk(lab, followlinks=False)):
                if count >= 5000:
                    notes.append("Experiment scan limit reached; select other save folders manually.")
                    break
                if "drive_c" in dirs:
                    for root in self._prefix_roots(Path(folder)):
                        candidates.setdefault(root, "Experiment save")
                dirs[:] = [d for d in dirs if d not in {"drive_c", "dosdevices", "components", "logs", ".git"} and "runner" not in d.casefold()]
        # Bound ordinary locations separately so they cannot crowd out the
        # selected recent recovery sets (up to four copies per set).
        for path in extra_roots:
            candidates.setdefault(Path(path).expanduser().resolve(), "Selected folder")
        if len(candidates) > 256:
            notes.append("Save location scan limit: only 256 ordinary locations are shown; recovery sets are listed separately. No saves were deleted.")
            explicit = {Path(p).expanduser().resolve() for p in extra_roots}
            ordered = sorted(candidates, key=lambda p: (str(p) != self.target, p not in explicit))
            candidates = {p: candidates[p] for p in ordered[:256]}
        backup_root = hub.state_file().parent / "backups"
        patterns = [self.backup_prefix + "*"]
        if self.rid == "doom-2016-gog":
            patterns.extend(("doom-save-restore-*", "doom-saves-*"))
        recovery_folders, omitted, undated = recent_recovery_folders(backup_root, patterns)
        notes.extend(selection_notes(omitted, undated))
        for backup in recovery_folders:
            # Presentation metadata only; restore and undo retain their own verification.
            operation, created_at = "Recovery backup", None
            record_path = backup / "restore.json"
            try:
                if backup.is_symlink() or record_path.is_symlink() or record_path.stat().st_size > 8 * 1024 * 1024:
                    raise ValueError("Untrusted recovery metadata")
                record = json.loads(record_path.read_text())
                if record.get("schema") != 1 or record.get("game_id", self.rid) != self.rid:
                    raise ValueError("Unknown recovery metadata")
                operation = {"restore": "Restore", "undo": "Undo"}.get(record.get("operation", "restore"), "Recovery backup")
                stamp = datetime.fromisoformat(record["created_at"])
                if stamp.tzinfo is None:
                    raise ValueError("Missing timestamp timezone")
                created_at = stamp.astimezone(timezone.utc).isoformat()
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                operation, created_at = "Recovery backup", None
            for name in ("source-savegame", "target-before-savegame", "experimental-savegame", "heroic-before-savegame"):
                path = backup / name
                if path.is_dir():
                    label = ("Selected source" if name in {"source-savegame", "experimental-savegame"} else
                             {"Restore": "Original saves before restore", "Undo": "Saves preserved before undo"}.get(operation, "Original target saves"))
                    candidates[path.resolve()] = label
                    recovery_groups[path.resolve()] = dict(recovery_group=str(backup), recovery_operation=operation,
                                                          recovery_created_at=created_at)
        history = self.backup_history()
        snapshots = {Path(row["save_path"]): row for row in history if row.get("status") == "complete"}
        if len(snapshots) > 64:
            notes.append("Snapshot list limit: only 64 recent snapshots are shown here. Open Backup history for more records; no snapshots were deleted.")
        for path, record in list(snapshots.items())[:64]:
            candidates.setdefault(path, "Snapshot: " + record["created_at"] + (" — " + record["note"] if record["note"] else ""))
        if len(candidates) > 1024:
            notes.append("Save location list limit reached (1024 copies). Browse for another source folder to inspect an omitted location; no saves were deleted.")
        rows = []
        for path, label in list(candidates.items())[:1024]:
            try:
                if str(path) in remembered["sources"] + remembered["targets"] and path.resolve() != path:
                    raise RuntimeError("Remembered path now resolves elsewhere. Choose the folder again to review it.")
                row = self.snapshot(path)
                self.check_snapshot_source(path, row)
                row.update(usable=True)
            except (RuntimeError, OSError) as exc:
                row = dict(root=str(path), usable=False, error=str(exc),
                           backup_verification_needed=isinstance(exc, BackupVerificationError))
                row.update(file_observations(path))
            row.update(label=label, current=str(path) == self.target)
            row.update(recovery_groups.get(path, {}))
            if path in self.target_roles:
                row["location_role"] = self.target_roles[path]
            rows.append(row)
        date_note = ("Dates use DOOM save metadata when available; otherwise, file modification times."
                     if self.rid == "doom-2016-gog" else
                     "Dates show file modification times and do not confirm gameplay progress.")
        notes.append("Development recovery: " + date_note + " Progress and game/mod compatibility are not verified. Close launchers and disable cloud sync before restore.")
        try:
            undo_plan, undo_reason = self.undo_preview(), ""
        except (RuntimeError, OSError, ValueError) as exc:
            undo_plan, undo_reason = None, str(exc)
        return dict(target=self.target, rows=rows, notes=notes, undo_plan=undo_plan, undo_reason=undo_reason,
                    remembered_targets=remembered["targets"], remembered_sources=remembered["sources"])

    def restore(self, plan, recipe=None):
        if not (enabled() if self.development_enabled is None else self.development_enabled):
            raise RuntimeError("Development save recovery is disabled.")
        self.preview(plan["source"]["root"], plan["target"]["root"])
        transaction = {"source": plan["source"], "target": plan["target"], "game_id": self.rid,
                       "hub_version": __version__, "operation": "restore"}
        return doom_saves.restore(transaction, recipe or self.recipe, backend=self)

    def backup_current(self, expected, note=""):
        """Copy a reviewed target; never rename or write into that target."""
        if not (enabled() if self.development_enabled is None else self.development_enabled):
            raise RuntimeError("Development save recovery is disabled.")
        if not isinstance(note, str) or len(note) > 300 or any(ord(c) < 32 for c in note):
            raise RuntimeError("Use a single-line backup note of at most 300 characters.")
        self.ensure_closed()
        target = self.current_target(self.recipe)
        fresh = self.snapshot(target)
        if str(target) != expected.get("root") or fresh["fingerprint"] != expected.get("fingerprint"):
            raise RuntimeError("Save target changed since the scan. Scan and review it again.")
        backup_root = (hub.state_file().parent / "backups").resolve()
        if backup_root == target or backup_root.is_relative_to(target):
            raise RuntimeError("Backup storage must be outside the save folder.")
        with doom_saves._locked():
            backup_root.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc)
            folder = Path(tempfile.mkdtemp(prefix=f"game-snapshot-{self.rid}-{now:%Y%m%dT%H%M%SZ}-", dir=backup_root))
            record = {"schema": 1, "kind": "save-snapshot", "status": "preparing", "game_id": self.rid,
                      "game_name": self.recipe["name"], "hub_version": __version__, "created_at": now.isoformat(),
                      "note": note.strip(), "source": str(target), "fingerprint": fresh["fingerprint"],
                      "file_count": fresh["file_count"], "total_bytes": fresh["total_bytes"]}
            def save_record():
                self_install._atomic(folder / "snapshot.json", (json.dumps(record, indent=2) + "\n").encode())
            try:
                save_record()
                shutil.copytree(target, folder / "savegame", copy_function=shutil.copy2)
                if self.snapshot(folder / "savegame")["fingerprint"] != fresh["fingerprint"]:
                    raise RuntimeError("Backup copy verification failed.")
                self.ensure_closed()
                if self.current_target(self.recipe) != target or self.snapshot(target)["fingerprint"] != fresh["fingerprint"]:
                    raise RuntimeError("Save files or target changed during backup; this snapshot is incomplete.")
                record["status"] = "complete"
                save_record()
            except Exception as exc:
                record.update(status="incomplete", error=str(exc))
                try:
                    save_record()
                except OSError:
                    pass
                raise RuntimeError(f"Backup stopped; active saves were not replaced. Incomplete copy retained at {folder}: {exc}") from exc
            return {"backup": str(folder), "file_count": fresh["file_count"], "created_at": record["created_at"], "note": record["note"]}

    def check_snapshot_source(self, path, snapshot):
        self.check_recovery_source(path, snapshot)
        path = Path(path)
        if path.name == "savegame" and ((path.parent / "snapshot.json").exists()
                                        or path.parent.name.startswith("game-snapshot-")):
            record = self.backup_history(_folders=[path.parent])[0]
            if record["status"] != "complete" or record.get("fingerprint") != snapshot["fingerprint"]:
                raise BackupVerificationError("Snapshot verification needed: the backup is incomplete, invalid or no longer matches its recorded hash. "
                                              "There is no manual approval button. Keep this backup and use another verified source.")

    def check_recovery_source(self, path, snapshot):
        """Bind managed recovery copies to their original transaction evidence."""
        path = Path(path)
        keys = {"source-savegame": "source", "target-before-savegame": "target",
                "experimental-savegame": "source", "heroic-before-savegame": "target"}
        if path.name not in keys:
            return
        folder = path.parent
        record_path = folder / "restore.json"
        managed = folder.name.startswith((self.backup_prefix, "doom-saves-", "doom-save-restore-"))
        if not managed and not record_path.exists() and not record_path.is_symlink():
            return
        try:
            if folder.is_symlink() or record_path.is_symlink() or record_path.stat().st_size > 8 * 1024**2:
                raise ValueError("Linked or oversized recovery record.")
            record = json.loads(record_path.read_text())
            if not isinstance(record, dict) or record.get("schema") != 1:
                raise ValueError("The original backup record has an unsupported format.")
            if record.get("status") not in {"ready", "restored"}:
                raise ValueError("The original backup record does not confirm that preparation completed.")
            if record.get("game_id", self.rid) != self.rid:
                raise ValueError("The backup record belongs to a different game.")
            expected = record[keys[path.name]]["fingerprint"]
            if (not isinstance(expected, str) or len(expected) != 64
                    or any(c not in "0123456789abcdef" for c in expected)):
                raise ValueError("The original backup record has no valid verification hash.")
            if expected != snapshot["fingerprint"]:
                raise ValueError("The backup files no longer match their originally recorded hash.")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            if isinstance(exc, FileNotFoundError):
                reason = "The original backup verification record is missing."
            elif isinstance(exc, (json.JSONDecodeError, UnicodeError)):
                reason = "The original backup verification record cannot be read."
            elif isinstance(exc, (KeyError, TypeError)):
                reason = "The original backup record is missing valid verification information."
            else:
                reason = str(exc)
            raise BackupVerificationError("Backup verification needed: " + reason + " "
                                          "There is no manual approval button. Keep this backup and use another verified source.") from exc

    def backup_history(self, *, _folders=None):
        """Read bounded metadata only; payloads are checked when used as sources."""
        root = hub.state_file().parent / "backups"
        rows = []
        # Timestamped names sort newest first; the bound is explicit in the UI.
        import heapq
        folders = _folders if _folders is not None else heapq.nlargest(128, root.glob(f"game-snapshot-{self.rid}-*"))
        for folder in folders:
            row = {"folder": str(folder), "status": "review required", "note": "", "created_at": "", "hub_version": "", "file_count": "—", "game_name": self.recipe["name"]}
            try:
                path = folder / "snapshot.json"
                if folder.is_symlink() or path.is_symlink() or path.stat().st_size > 65536:
                    raise ValueError("Linked or oversized snapshot record.")
                data = json.loads(path.read_text(encoding="utf-8"))
                if (not isinstance(data, dict) or data.get("schema") != 1 or data.get("kind") != "save-snapshot"
                        or data.get("game_id") != self.rid or data.get("status") not in {"complete", "preparing", "incomplete"}):
                    raise ValueError("Unrecognized snapshot record.")
                for key in ("created_at", "note", "hub_version", "game_name", "fingerprint"):
                    if not isinstance(data.get(key), str) or len(data[key]) > 500:
                        raise ValueError("Invalid snapshot metadata.")
                parsed_date = datetime.fromisoformat(data["created_at"])
                if parsed_date.tzinfo is None or doom_saves._stamp(parsed_date.timestamp()) is None:
                    raise ValueError("Invalid snapshot date.")
                if len(data["fingerprint"]) != 64 or any(c not in "0123456789abcdef" for c in data["fingerprint"]):
                    raise ValueError("Invalid snapshot fingerprint.")
                if type(data.get("file_count")) is not int or data["file_count"] < 1:
                    raise ValueError("Invalid snapshot file count.")
                row.update({key: data[key] for key in ("status", "created_at", "note", "hub_version", "game_name", "file_count", "fingerprint")})
                row["save_path"] = str(folder / "savegame")
                if (folder / "savegame").is_symlink() or not (folder / "savegame").is_dir():
                    raise ValueError("Snapshot payload missing or linked.")
            except (OSError, ValueError, TypeError, OverflowError) as exc:
                row.update(status="review required", error=str(exc))
            rows.append(row)
        rows.sort(key=lambda row: (datetime.fromisoformat(row["created_at"]).timestamp()
                                  if row.get("created_at") and row["status"] != "review required" else float("-inf")), reverse=True)
        return rows

    def latest_restore_record(self, target, *, ignore_token=None):
        """Fail closed on unreadable/oversized history, never guess an older undo."""
        import heapq
        folders = heapq.nlargest(257, (hub.state_file().parent / "backups").glob(self.backup_prefix + "*"))
        if len(folders) > 256:
            raise RuntimeError("Undo history exceeds 256 records; review recovery copies manually.")
        candidates = []
        for folder in folders:
            path = folder / "restore.json"
            try:
                if folder.is_symlink() or path.is_symlink() or path.stat().st_size > 8 * 1024**2:
                    raise ValueError("Linked or oversized restore record.")
                raw = path.read_bytes()
                record = json.loads(raw)
                if not isinstance(record, dict) or record.get("schema") != 1:
                    raise ValueError("Invalid restore record.")
                if record.get("game_id", self.rid) != self.rid:
                    raise ValueError("Restore record belongs to another game.")
                if ignore_token and record.get("operation") == "undo" and record.get("undo_token") == ignore_token:
                    continue
                if not isinstance(record.get("target"), dict) or not isinstance(record["target"].get("root"), str):
                    raise ValueError("Restore target is missing.")
                if record["target"]["root"] != str(target):
                    continue
                when = datetime.fromisoformat(record["created_at"])
                if when.tzinfo is None:
                    raise ValueError("Restore time lacks a timezone.")
                candidates.append((when.timestamp(), str(folder), path, hashlib.sha256(raw).hexdigest(), record))
            except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
                raise RuntimeError(f"Cannot safely inspect undo history: {path}: {exc}") from exc
        if not candidates:
            raise RuntimeError("No recorded restore for this selected target. Standalone snapshots are available in Backup history.")
        return max(candidates, key=lambda item: (item[0], item[1]))

    def undo_preview(self):
        target = self.current_target(self.recipe)
        _time, _folder, path, digest, record = self.latest_restore_record(target)
        if record.get("status") != "restored":
            raise RuntimeError("The latest restore is incomplete or unconfirmed. Review its recovery copies manually.")
        if record.get("operation", "restore") == "undo":
            raise RuntimeError("The last restore for this target has already been undone. No further undo is offered.")
        if record.get("operation", "restore") != "restore":
            raise RuntimeError("Unrecognized restore operation; manual recovery review required.")
        original = path.parent / "target-before-savegame"
        if original.is_symlink():
            raise RuntimeError("Original-save backup is linked; undo blocked.")
        plan = self.preview(original, target)
        expected = record.get("target", {}).get("fingerprint")
        restored = record.get("source", {}).get("fingerprint") if isinstance(record.get("source"), dict) else None
        for fingerprint in (expected, restored):
            if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                raise RuntimeError("Restore record fingerprint is invalid; undo blocked.")
        if plan["source"]["fingerprint"] != expected:
            raise RuntimeError("Original-save backup changed since the restore. Undo blocked.")
        plan.update(undo_record=str(path), undo_record_sha256=digest, restore_created_at=record["created_at"],
                    current_changed_since_restore=plan["target"]["fingerprint"] != restored)
        return plan

    def validate_transaction(self, plan):
        if plan.get("operation") != "undo":
            return
        target = self.current_target(self.recipe)
        _time, _folder, path, digest, record = self.latest_restore_record(target, ignore_token=plan["undo_token"])
        if str(path) != plan["undo_record"] or digest != plan["undo_record_sha256"] or record.get("status") != "restored":
            raise RuntimeError("Undo history changed after review. Scan and preview again.")

    def undo(self, plan):
        if not (enabled() if self.development_enabled is None else self.development_enabled):
            raise RuntimeError("Development save recovery is disabled.")
        fresh = self.undo_preview()
        for key in ("undo_record", "undo_record_sha256"):
            if fresh[key] != plan.get(key):
                raise RuntimeError("Undo history changed after review. Scan and preview again.")
        for key in ("source", "target"):
            if fresh[key]["fingerprint"] != plan[key]["fingerprint"] or fresh[key]["root"] != plan[key]["root"]:
                raise RuntimeError("Save files changed after undo preview. Scan and review again.")
        transaction = dict(fresh, game_id=self.rid, hub_version=__version__, operation="undo", undo_token=uuid.uuid4().hex)
        return doom_saves.restore(transaction, self.recipe, backend=self)
