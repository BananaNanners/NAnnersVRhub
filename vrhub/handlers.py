"""Per-game behavior hooks.

Recipes stay declarative for most games.  A handler is only needed when a game
has readiness checks or guidance that cannot be expressed by the generic
installer yet.  Keeping those hooks here prevents hub.py/gui.py from growing
one-off game branches.
"""
from __future__ import annotations

import configparser
import os
import re
import shutil
import shlex
import struct
import subprocess
import sys
from pathlib import Path

from . import heroic


class GameHandler:
    name = "generic"

    def preflight_rows(self, recipe: dict, game: Path | None) -> list[dict]:
        return []

    def compatibility_rows(self, recipe: dict, game: Path | None) -> list[dict]:
        return []

    def detail_notes(self, recipe: dict) -> list[str]:
        return []

    def install_supported(self, recipe: dict) -> bool:
        return recipe.get("method", "file") != "guide"

    def launcher_label(self, recipe: dict) -> str | None:
        return None

    def play_label(self, recipe: dict) -> str | None:
        return "Launch game"

    def launch(self, recipe: dict, game: Path | None) -> subprocess.Popen:
        raise RuntimeError(f"{recipe['name']} has no game-specific launcher.")

    def launch_play(self, recipe: dict, game: Path | None) -> subprocess.Popen:
        if not game:
            raise RuntimeError(f"{recipe['name']} was not found in Steam.")
        steam = shutil.which("steam")
        if not steam:
            raise RuntimeError("Steam command was not found in PATH.")
        # Use Steam's launch-dialog URI rather than rungameid.  This mirrors
        # launching from the Steam Library more closely: games configured as
        # "Ask when starting" can present their launch-choice dialog, while a
        # saved/default launch choice is respected.  Do not inject renderer or
        # other game-specific arguments here; Steam remains the source of truth.
        uri = f"steam://launch/{recipe['steam_appid']}/dialog"
        return subprocess.Popen([steam, uri], start_new_session=True)

    def diagnostics(self, recipe: dict, game: Path | None) -> list[str]:
        return []

    def live_status(self, recipe: dict, game: Path | None) -> dict:
        return {}

    def bridge_log(self, recipe: dict) -> Path | None:
        return None

    def bridge_log_label(self, recipe: dict) -> str:
        return "Open bridge log"


class SkyrimVRHandler(GameHandler):
    """Checks for the Linux MGO/OpenComposite layout without owning the modlist.

    Jackify/MGO remain responsible for installing and updating the modlist.  The
    hub verifies the pieces that matter to the Linux VR launch path and keeps
    those checks isolated from the generic installer.
    """

    name = "skyrim-vr"

    def _mgo_dir(self, recipe: dict) -> Path | None:
        cfg = recipe.get("handler_config", {})
        env_name = cfg.get("mgo_dir_env", "NANNERS_MGO_DIR")
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value).expanduser().resolve()

        # Auto-detect common Jackify/MGO layouts.  Only accept a directory that
        # actually contains ModOrganizer.exe so a similarly named folder is not
        # mistaken for a working MGO install.
        home = Path.home()
        candidates = []
        for pattern in cfg.get("mgo_globs", [
            "SkyrimVR*MGO*", "*Skyrim*MGO*", "MGO*",
            "Games/SkyrimVR*MGO*", "Games/*MGO*",
            "Applications/SkyrimVR*MGO*", "Applications/*MGO*",
        ]):
            candidates.extend(home.glob(pattern))
        valid = sorted({p.resolve() for p in candidates if (p / "ModOrganizer.exe").is_file()},
                       key=lambda p: (len(p.parts), str(p).lower()))
        return valid[0] if valid else None

    def _proton(self, game: Path) -> Path | None:
        # Prefer the Proton version recorded for this compatdata prefix when
        # Steam has written config_info, then fall back to installed tools.
        steamapps = game.parents[1]
        compat = steamapps / "compatdata" / "611670"
        info = compat / "config_info"
        if info.is_file():
            for raw in info.read_text(errors="replace").splitlines():
                p = Path(raw.strip()).expanduser()
                if p.name == "proton" and p.is_file():
                    return p.resolve()
                if p.is_dir() and (p / "proton").is_file():
                    return (p / "proton").resolve()

        roots = [steamapps.parent, Path.home() / ".local/share/Steam", Path.home() / ".steam/steam"]
        candidates = []
        for root in roots:
            common = root / "steamapps/common"
            candidates += [common / "Proton - Experimental/proton"]
            candidates += sorted(common.glob("GE-Proton*/proton"), reverse=True)
            candidates += sorted((root / "compatibilitytools.d").glob("*/proton"), reverse=True)
        for p in candidates:
            if p.is_file():
                return p.resolve()
        return None

    def launcher_label(self, recipe: dict) -> str | None:
        # Say exactly what the action launches; MGO is the modlist, MO2 is the program.
        return "Launch MO2"

    def play_label(self, recipe: dict) -> str | None:
        return "Launch Skyrim VR"

    @staticmethod
    def _clean_qbytearray(value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        m = re.fullmatch(r"@ByteArray\((.*)\)", value)
        return m.group(1) if m else value

    def _mo2_ini(self, mgo: Path) -> Path | None:
        candidates = [mgo / "ModOrganizer.ini", mgo / "modorganizer.ini"]
        for p in candidates:
            if p.is_file():
                return p
        return None

    def _mo2_state(self, mgo: Path) -> dict:
        """Read only the MO2 settings we need for status/launch decisions.

        MO2 keeps portable-instance configuration in ModOrganizer.ini.  We do not
        edit it; this parser only reports the selected profile and configured
        executables so the Hub can choose the modlist's SKSEVR entry.
        """
        ini = self._mo2_ini(mgo)
        result = {"ini": str(ini) if ini else None, "profile": None, "executables": []}
        if not ini:
            return result
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        try:
            cp.read(ini, encoding="utf-8")
        except (OSError, configparser.Error, UnicodeError):
            return result

        for section in cp.sections():
            for key, value in cp.items(section):
                if key.lower() in {"selected_profile", "selectedprofile", "profile"}:
                    cleaned = self._clean_qbytearray(value)
                    if cleaned:
                        result["profile"] = cleaned
                        break
            if result["profile"]:
                break

        if cp.has_section("customExecutables"):
            grouped: dict[str, dict] = {}
            for key, value in cp.items("customExecutables"):
                m = re.match(r"(\d+)\\(.+)", key)
                if not m:
                    continue
                idx, field = m.group(1), m.group(2).lower()
                grouped.setdefault(idx, {})[field] = value.strip()
            def nkey(x):
                try: return int(x[0])
                except ValueError: return 10**9
            for _, row in sorted(grouped.items(), key=nkey):
                title = row.get("title") or row.get("name")
                binary = row.get("binary") or row.get("executable")
                if title or binary:
                    result["executables"].append({"title": title or "", "binary": binary or "",
                                                   "arguments": row.get("arguments", "")})
        return result

    def _skse_entry(self, mgo: Path) -> dict | None:
        state = self._mo2_state(mgo)
        rows = state.get("executables", [])
        # Prefer the VR-specific loader, then an explicit SKSEVR title, then a
        # generic SKSE title.  Never silently fall back to SkyrimVR.exe.
        def score(row: dict) -> int:
            title = row.get("title", "").lower()
            binary = row.get("binary", "").replace("\\", "/").lower()
            if binary.endswith("/sksevr_loader.exe") or binary == "sksevr_loader.exe": return 0
            if "sksevr" in title: return 1
            if re.search(r"\bskse\b", title): return 2
            return 99
        candidates = sorted((r for r in rows if score(r) < 99), key=score)
        return candidates[0] if candidates else None

    @staticmethod
    def _parse_shortcuts_vdf(path: Path) -> list[dict]:
        """Parse the small subset of Valve's binary VDF used by shortcuts.vdf.

        We only need top-level shortcut records and their scalar fields. Unknown
        field types are rejected rather than guessed so a Steam format change does
        not silently launch the wrong shortcut.
        """
        data = path.read_bytes()
        out: list[dict] = []

        def cstr(pos: int) -> tuple[str, int]:
            end = data.find(b"\0", pos)
            if end < 0:
                raise ValueError("unterminated VDF string")
            return data[pos:end].decode("utf-8", "replace"), end + 1

        # Binary VDF starts with an object field named 'shortcuts'.  Find each
        # numbered child object (0, 1, 2, ...), then parse scalar fields until its
        # end marker. This intentionally ignores nested 'tags' content.
        pos = 0
        try:
            t = data[pos]; pos += 1
            if t != 0:
                return []
            root, pos = cstr(pos)
            if root != "shortcuts":
                return []
            while pos < len(data):
                typ = data[pos]; pos += 1
                if typ == 8:
                    break
                if typ != 0:
                    return []
                _index, pos = cstr(pos)
                row: dict = {}
                while pos < len(data):
                    typ = data[pos]; pos += 1
                    if typ == 8:
                        break
                    key, pos = cstr(pos)
                    if typ == 1:  # string
                        value, pos = cstr(pos)
                        row[key] = value
                    elif typ == 2:  # uint32/int32 scalar
                        if pos + 4 > len(data):
                            raise ValueError("truncated VDF integer")
                        row[key] = struct.unpack_from("<I", data, pos)[0]
                        pos += 4
                    elif typ == 0:  # nested object (normally tags)
                        depth = 1
                        while pos < len(data) and depth:
                            st = data[pos]; pos += 1
                            if st == 8:
                                depth -= 1
                                continue
                            _k, pos = cstr(pos)
                            if st == 0:
                                depth += 1
                            elif st == 1:
                                _v, pos = cstr(pos)
                            elif st == 2:
                                pos += 4
                            else:
                                raise ValueError(f"unsupported nested VDF type {st}")
                    else:
                        raise ValueError(f"unsupported VDF type {typ}")
                out.append(row)
        except (IndexError, ValueError, struct.error):
            return []
        return out

    def _steam_shortcut(self, recipe: dict, mgo: Path) -> dict | None:
        target = (mgo / "ModOrganizer.exe").resolve()
        roots = [Path.home() / ".local/share/Steam", Path.home() / ".steam/steam"]
        seen: set[Path] = set()
        for root in roots:
            userdata = root / "userdata"
            if not userdata.is_dir():
                continue
            for vdf in sorted(userdata.glob("*/config/shortcuts.vdf")):
                real = vdf.resolve()
                if real in seen:
                    continue
                seen.add(real)
                for row in self._parse_shortcuts_vdf(real):
                    exe = str(row.get("Exe", "")).strip().strip('"')
                    try:
                        exe_path = Path(exe).expanduser().resolve()
                    except (OSError, RuntimeError):
                        continue
                    if exe_path != target:
                        continue
                    appid = row.get("appid")
                    if not isinstance(appid, int):
                        continue
                    gameid = ((appid & 0xFFFFFFFF) << 32) | 0x02000000
                    return {
                        "appid": appid & 0xFFFFFFFF,
                        "gameid": gameid,
                        "appname": row.get("AppName", "MO2"),
                        "exe": exe,
                        "vdf": str(real),
                        "launch_options": row.get("LaunchOptions", ""),
                    }
        return None

    def launch(self, recipe: dict, game: Path | None) -> subprocess.Popen:
        if not game:
            raise RuntimeError("Skyrim VR was not found in Steam.")
        mgo = self._mgo_dir(recipe)
        if not mgo or not (mgo / "ModOrganizer.exe").is_file():
            env_name = recipe.get("handler_config", {}).get("mgo_dir_env", "NANNERS_MGO_DIR")
            raise RuntimeError(f"MGO was not found automatically. Set {env_name} to the MGO folder and try again.")
        shortcut = self._steam_shortcut(recipe, mgo)
        if not shortcut:
            raise RuntimeError(
                "MO2 Steam shortcut not found. Run Jackify's Steam shortcut setup first, "
                "then restart Steam/NAnnersVRhub and retry."
            )
        steam = shutil.which("steam")
        if not steam:
            raise RuntimeError("Steam command was not found in PATH.")
        uri = f"steam://rungameid/{shortcut['gameid']}"
        return subprocess.Popen([steam, uri], start_new_session=True)

    @staticmethod
    def _steam_root_from_shortcut(shortcut: dict) -> Path | None:
        try:
            vdf = Path(shortcut["vdf"]).resolve()
        except (KeyError, OSError, RuntimeError):
            return None
        # <steam>/userdata/<user>/config/shortcuts.vdf
        try:
            return vdf.parents[3]
        except IndexError:
            return None

    def _shortcut_compat(self, shortcut: dict) -> tuple[Path, Path, Path] | None:
        """Return (steam_root, compatdata, proton) for a non-Steam shortcut.

        Steam stores non-Steam Proton prefixes under compatdata/<shortcut appid>.
        config_info records the Proton build that created/last updated the prefix.
        We only use this prefix for a short-lived *second* MO2 process whose sole
        purpose is to forward a moshortcut request to the already-running primary
        MO2 instance. The primary itself is still started by Steam/Jackify.
        """
        steam_root = self._steam_root_from_shortcut(shortcut)
        if not steam_root:
            return None
        compat = steam_root / "steamapps/compatdata" / str(shortcut["appid"])
        info = compat / "config_info"
        if not (compat / "pfx").is_dir() or not info.is_file():
            return None
        proton = None
        try:
            lines = info.read_text(errors="replace").splitlines()
        except OSError:
            return None
        for raw in lines:
            item = raw.strip()
            if not item:
                continue
            p = Path(item).expanduser()
            if p.name == "proton" and p.is_file():
                proton = p.resolve()
                break
            if p.is_dir() and (p / "proton").is_file():
                proton = (p / "proton").resolve()
                break
        if not proton:
            # config_info commonly stores a path inside Proton's files/ tree.
            # Recover the tool root without guessing a version name.
            for raw in lines:
                item = raw.strip()
                marker = "/files/"
                if marker not in item:
                    continue
                root = Path(item.split(marker, 1)[0])
                if (root / "proton").is_file():
                    proton = (root / "proton").resolve()
                    break
        return (steam_root, compat, proton) if proton else None

    def launch_play(self, recipe: dict, game: Path | None) -> subprocess.Popen:
        if not game:
            raise RuntimeError("Skyrim VR was not found in Steam.")
        mgo = self._mgo_dir(recipe)
        if not mgo:
            raise RuntimeError("MGO directory was not found.")
        shortcut = self._steam_shortcut(recipe, mgo)
        if not shortcut:
            raise RuntimeError("MO2 Steam shortcut not found. Run Jackify's Steam shortcut setup first.")
        entry = self._skse_entry(mgo)
        if not entry:
            raise RuntimeError(
                "No SKSEVR executable entry was found in ModOrganizer.ini. Open MO2 and confirm the "
                "SKSEVR/SKSE executable is configured before using Launch Skyrim VR."
            )
        steam = shutil.which("steam")
        if not steam:
            raise RuntimeError("Steam command was not found in PATH.")
        compat = self._shortcut_compat(shortcut)
        if not compat:
            raise RuntimeError(
                "The Jackify MO2 Proton prefix could not be found. Launch MO2 once from its Steam "
                "shortcut, close it, then retry so Steam can create/update the shortcut prefix."
            )
        steam_root, compatdata, proton = compat
        bridge_log = Path.home() / ".local/share/vrhub/mo2-bridge.log"
        args = [
            sys.executable, "-m", "vrhub.mo2_bridge",
            "--steam", steam,
            "--uri", f"steam://rungameid/{shortcut['gameid']}",
            "--proton", str(proton),
            "--compatdata", str(compatdata),
            "--steam-root", str(steam_root),
            "--mo2", str((mgo / "ModOrganizer.exe").resolve()),
            "--appid", str(shortcut["appid"]),
            "--entry", entry["title"],
            "--log", str(bridge_log),
        ]
        return subprocess.Popen(args, start_new_session=True)


    @staticmethod
    def _process_cmdlines() -> list[str]:
        rows: list[str] = []
        proc = Path("/proc")
        if not proc.is_dir():
            return rows
        for child in proc.iterdir():
            if not child.name.isdigit():
                continue
            try:
                raw = (child / "cmdline").read_bytes()
            except (OSError, PermissionError):
                continue
            if raw:
                rows.append(raw.replace(b"\0", b" ").decode("utf-8", "replace").lower())
        return rows

    def live_status(self, recipe: dict, game: Path | None) -> dict:
        cmds = self._process_cmdlines()
        mo2 = any("modorganizer.exe" in x for x in cmds)
        skyrim = any(("skyrimvr.exe" in x or "sksevr_loader.exe" in x) for x in cmds)
        return {"mo2": mo2, "game": skyrim}

    def bridge_log(self, recipe: dict) -> Path | None:
        return Path.home() / ".local/share/vrhub/mo2-bridge.log"
    def diagnostics(self, recipe: dict, game: Path | None) -> list[str]:
        mgo = self._mgo_dir(recipe)
        if not mgo:
            return ["MGO directory: not found"]
        shortcut = self._steam_shortcut(recipe, mgo)
        state = self._mo2_state(mgo)
        skse = self._skse_entry(mgo)
        lines = [f"MGO directory: {mgo}",
                 f"MO2 config: {state.get('ini') or 'not found'}",
                 f"MO2 active profile: {state.get('profile') or 'not detected'}"]
        if shortcut:
            lines += [f"MO2 Steam shortcut: {shortcut['appname']}",
                      f"MO2 shortcut AppID: {shortcut['appid']}",
                      f"MO2 shortcut game ID: {shortcut['gameid']}"]
            compat = self._shortcut_compat(shortcut)
            if compat:
                _, compatdata, proton = compat
                lines += [f"MO2 shortcut Proton prefix: {compatdata}",
                          f"MO2 shortcut Proton: {proton}"]
            else:
                lines.append("MO2 shortcut Proton prefix: not detected")
        else:
            lines.append("MO2 Steam shortcut: not found")
        if skse:
            lines.append(f"MO2 Skyrim executable: {skse['title']} ({skse.get('binary') or 'binary path not recorded'})")
        else:
            lines.append("MO2 Skyrim executable: SKSEVR/SKSE entry not detected")
        return lines

    @staticmethod
    def _is_opencomposite_mod(recipe: dict, name: str) -> bool:
        """Match named adapter variants; alternatives may carry version tokens."""
        cfg = recipe.get("handler_config", {})
        primary = cfg.get("opencomposite_mod", "Open Composite XR - Incompatible with VR Performance Kit")
        if name == primary:
            return True
        for base in cfg.get("opencomposite_alternatives", []):
            if name == base or re.fullmatch(re.escape(base) + r"(?: [0-9][0-9A-Za-z.+_-]*)+", name):
                return True
        return False

    def _opencomposite_dirs(self, recipe: dict, mgo: Path) -> list[Path]:
        try:
            return sorted((p for p in (mgo / "mods").iterdir()
                           if self._is_opencomposite_mod(recipe, p.name) and p.is_dir()),
                          key=lambda p: p.name)
        except OSError:
            return []

    def _profile_mods(self, mgo: Path | None) -> tuple[dict | None, Path | None, str]:
        """Read enabled mods using the same rules for both report views."""
        state = self._mo2_state(mgo) if mgo and mgo.is_dir() else {}
        profile = state.get("profile")
        modlist = None
        reason = "MO2 active profile is not available."
        if mgo and profile and Path(profile).name == profile and profile not in {".", ".."}:
            modlist = mgo / "profiles" / profile / "modlist.txt"
            ini = state.get("ini")
            if ini:
                cp = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    cp.read(ini, encoding="utf-8")
                    # Custom profile roots need explicit resolution; never report
                    # a default-folder modlist as evidence for a redirected root.
                    if any(key.lower() in {"profiles_directory", "profilesdirectory", "base_directory"}
                           and value.strip() for section in cp.sections() for key, value in cp.items(section)):
                        modlist = None
                        reason = "Custom MO2 base/profile directory: enabled mod state is unverified; review it in MO2."
                except (OSError, configparser.Error, UnicodeError):
                    modlist = None
                    reason = "MO2 profile directory settings could not be read."
        enabled = None
        if modlist:
            try:
                entries = {}
                for line in modlist.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip()
                    if line.startswith(("+", "-")):
                        name = line[1:].strip()
                        if name in entries:
                            raise ValueError("duplicate mod entries")
                        entries[name] = line[0] == "+"
                enabled = entries
            except (OSError, UnicodeError, ValueError):
                reason = f"Cannot read an unambiguous active-profile modlist: {modlist}. Check enabled mods in MO2."
        return enabled, modlist, reason

    def compatibility_rows(self, recipe: dict, game: Path | None) -> list[dict]:
        rows = []
        def add(name, status, detail):
            rows.append({"name": name, "status": status, "detail": detail})

        mgo = self._mgo_dir(recipe)
        shortcut = self._steam_shortcut(recipe, mgo) if mgo and mgo.is_dir() else None
        compat = self._shortcut_compat(shortcut) if shortcut else None
        if compat:
            _, prefix, proton = compat
            add("MO2 shortcut prefix", "ok", str(prefix / "pfx"))
            reference = recipe.get("compatibility", {}).get("reference", {}).get("proton", "")
            version = proton.parent.name
            same = reference == version or reference.startswith(version + " (")
            add("MO2 shortcut Proton", "ok" if same or not reference else "warning",
                f"{proton}; recorded by prefix config_info, not a running-process check. " +
                ("Matches dated reference." if same else
                 "Differs from the dated reference; retest this build before treating it as validated." if reference else
                 "No dated Proton reference recorded."))
        else:
            add("MO2 shortcut prefix/Proton", "error",
                "Cannot resolve the MO2 shortcut's own prefix and recorded Proton. Launch MO2 once through its Steam shortcut and retry.")

        key = "PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES"
        import_value = None
        options = shortcut.get("launch_options", "") if shortcut else ""
        try:
            tokens = shlex.split(options)
        except ValueError:
            tokens = []
        # Recognize only leading shell/env assignments. Do not infer environment
        # from text buried in an echo, quoted script, or shell control expression.
        simple = not any(char in options for char in ";|&`\n") and "$" not in options
        if simple:
            for token in tokens:
                if token == "env" and import_value is None:
                    continue
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
                    break
                name, value = token.split("=", 1)
                if name == key:
                    import_value = value
        import_ok = import_value == "1" and "%command%" in tokens
        add("Shortcut runtime import", "ok" if import_ok else "warning",
            f"{key}=1 recorded in MO2 shortcut launch options; Steam execution is unverified." if import_ok else
            f"No unambiguous leading {key}=1 found in MO2 shortcut launch options. Review in Steam; the Hub environment does not prove shortcut configuration.")
        enabled, modlist, reason = self._profile_mods(mgo)
        cfg = recipe.get("handler_config", {})
        if enabled is None:
            add("Active-profile OpenComposite", "unknown", reason)
            add("Active-profile VR Performance Kit", "unknown", reason)
        else:
            selected = [name for name, on in enabled.items() if on and self._is_opencomposite_mod(recipe, name)]
            if len(selected) > 1:
                add("Active-profile OpenComposite", "error",
                    "Multiple recognized OpenComposite variants enabled: " + ", ".join(selected) +
                    ". Review their MO2 priorities and select one adapter variant.")
            elif selected:
                name = selected[0]
                folder = mgo / "mods" / name
                present = folder.is_dir()
                add("Active-profile OpenComposite", "ok" if present else "error",
                    f"Enabled: {name} in {modlist}; folder: {folder}" +
                    (" (present; DLL loading unverified)." if present else " (missing or inaccessible)."))
            else:
                disabled = [name for name in enabled if self._is_opencomposite_mod(recipe, name)]
                add("Active-profile OpenComposite", "error",
                    ("Recognized variants are disabled: " + ", ".join(disabled) if disabled else
                     "No recognized OpenComposite variant listed") + f" in {modlist}.")
            conflicts = [name for name in cfg.get("conflicting_mod_dirs", []) if enabled.get(name)]
            add("Active-profile VR Performance Kit", "error" if conflicts else "ok",
                "Enabled conflicts: " + ", ".join(conflicts) if conflicts else f"No configured VR Performance Kit variants enabled in {modlist}.")
        return rows

    def preflight_rows(self, recipe: dict, game: Path | None) -> list[dict]:
        cfg = recipe.get("handler_config", {})
        env_name = cfg.get("mgo_dir_env", "NANNERS_MGO_DIR")
        mgo = self._mgo_dir(recipe)
        rows: list[dict] = []
        if not mgo:
            rows.append({
                "name": "MGO directory",
                "ok": False,
                "required": False,
                "detail": f"not auto-detected; set {env_name} to your MGO folder for deep checks and launching",
            })
            return rows

        rows.append({"name": "MGO directory", "ok": mgo.is_dir(), "required": True,
                     "detail": str(mgo) if mgo.is_dir() else f"not found: {mgo}"})
        if not mgo.is_dir():
            return rows

        mo2 = mgo / "ModOrganizer.exe"
        rows.append({"name": "MGO Mod Organizer", "ok": mo2.is_file(), "required": True,
                     "detail": str(mo2) if mo2.is_file() else "ModOrganizer.exe not found in MGO directory"})

        adapters = self._opencomposite_dirs(recipe, mgo)
        rows.append({"name": "MGO OpenComposite", "ok": bool(adapters), "required": True,
                     "detail": ("Installed adapter folders: " + "; ".join(str(p) for p in adapters)
                                + ". Enabled state is checked in Compatibility profile.") if adapters else
                               "No recognized MGO OpenComposite variant folder found."})

        shortcut = self._steam_shortcut(recipe, mgo)
        rows.append({
            "name": "MO2 Steam shortcut",
            "ok": bool(shortcut),
            "required": True,
            "detail": (f"{shortcut['appname']} (game ID {shortcut['gameid']})" if shortcut else
                       "not found for this ModOrganizer.exe; run Jackify's Steam shortcut setup"),
        })

        state = self._mo2_state(mgo)
        profile = state.get("profile")
        rows.append({
            "name": "MO2 active profile",
            "ok": bool(profile),
            "required": False,
            "detail": profile or "not detected from ModOrganizer.ini (MO2 can still be launched)",
        })
        skse = self._skse_entry(mgo)
        rows.append({
            "name": "MO2 Skyrim executable",
            "ok": bool(skse),
            "required": False,
            "detail": (f"{skse['title']} -> {skse.get('binary') or 'configured executable'}" if skse else
                       "SKSEVR/SKSE entry not detected; Launch Skyrim VR will stay unavailable until configured"),
        })

        # Presence is informational: whether a mod is enabled is profile-specific.
        perf = [mgo / "mods" / n for n in cfg.get("conflicting_mod_dirs", [])]
        present = [p.name for p in perf if p.exists()]
        enabled, modlist, reason = self._profile_mods(mgo)
        if enabled is not None:
            conflicts = [name for name in cfg.get("conflicting_mod_dirs", []) if enabled.get(name)]
            rows.append({"name": "VR Performance Kit", "ok": not conflicts, "required": False,
                         "detail": ("Enabled conflicts: " + ", ".join(conflicts)) if conflicts else
                                   f"No configured VR Performance Kit variants enabled in {modlist}."})
        else:
            rows.append({"name": "VR Performance Kit", "ok": not present, "required": False,
                         "detail": ("Folders present; enabled state unverified: " + ", ".join(present) + ". " + reason)
                                   if present else "No configured conflicting mod folders found; enabled state is unverified."})
        return rows

    def detail_notes(self, recipe: dict) -> list[str]:
        env_name = recipe.get("handler_config", {}).get("mgo_dir_env", "NANNERS_MGO_DIR")
        return [
            f"MGO is auto-detected when possible; {env_name} remains available as an explicit override.",
            "Launch MO2 uses the Jackify-created non-Steam shortcut so Steam keeps Jackify's Proton prefix and launch options intact.",
            "Launch Skyrim VR starts/focuses MO2 through Steam, then forwards MO2's configured SKSEVR/SKSE entry through the Jackify shortcut's own Proton prefix.",
            "The bridge never edits Steam shortcuts or ModOrganizer.ini; status is written to ~/.local/share/vrhub/mo2-bridge.log.",
            "NAnnersVRhub does not replace Jackify/Wabbajack for MGO installation or updating.",
        ]


class HeroicGOGHandler(GameHandler):
    """Heroic/GOG workflow that keeps Heroic as the runner source of truth.

    Normal play is handed back to Heroic.  Optional external VR launchers can
    reuse Heroic's configured prefix/Proton through umu-run without modifying
    Heroic's game settings.
    """

    name = "heroic-gog"

    def _appid(self, recipe: dict) -> str:
        return str(recipe["heroic_appid"])

    def game_path(self, recipe: dict) -> Path | None:
        return heroic.gog_game_path(self._appid(recipe))

    def _settings(self, recipe: dict) -> dict:
        return heroic.game_settings(self._appid(recipe))

    def _exe(self, recipe: dict, game: Path | None) -> Path | None:
        if not game:
            return None
        rel = recipe.get("handler_config", {}).get("executable", "")
        return game / rel if rel else None

    def _kharvox_dir(self, recipe: dict) -> Path | None:
        cfg = recipe.get("handler_config", {})
        env_name = cfg.get("kharvox_dir_env", "NANNERS_KHARVOX_DIR")
        raw = os.environ.get(env_name, "").strip()
        if raw:
            p = Path(raw).expanduser().resolve()
            if (p / "KharvoxLauncher.exe").is_file():
                return p

        home = Path.home()
        patterns = cfg.get("kharvox_globs", [
            "Games/KHARVOX*", "Games/Kharvox*",
            "Applications/KHARVOX*", "Applications/Kharvox*",
            "Downloads/KHARVOX*", "Downloads/Kharvox*",
            "KHARVOX*", "Kharvox*",
        ])
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(home.glob(pattern))
        # Versioned folders are normal (for example KHARVOX-v1.11).  Prefer
        # the highest version-looking directory rather than an older unversioned
        # extraction that may happen to exist beside it.  Also tolerate one
        # wrapper directory produced by some archive tools.
        expanded: set[Path] = set()
        for p in candidates:
            if not p.is_dir():
                continue
            if (p / "KharvoxLauncher.exe").is_file():
                expanded.add(p.resolve())
            try:
                for child in p.iterdir():
                    if child.is_dir() and (child / "KharvoxLauncher.exe").is_file():
                        expanded.add(child.resolve())
            except OSError:
                pass

        def version_key(path: Path):
            nums = tuple(int(x) for x in re.findall(r"\d+", path.name))
            return (bool(nums), nums, -len(path.parts), str(path).lower())

        valid = sorted(expanded, key=version_key, reverse=True)
        return valid[0] if valid else None

    def _kharvox_launcher(self, recipe: dict) -> Path | None:
        root = self._kharvox_dir(recipe)
        return root / "KharvoxLauncher.exe" if root else None

    def _prefix_temp_dir(self, recipe: dict) -> Path | None:
        settings = self._settings(recipe)
        raw = str(settings.get("winePrefix", "")).strip()
        if not raw:
            return None
        prefix = Path(raw).expanduser()
        # Heroic/Proton prefixes normally use steamuser.  Fall back to the
        # first Windows user directory if a runner uses another user name.
        preferred = prefix / "drive_c/users/steamuser/AppData/Local/Temp"
        if preferred.is_dir():
            return preferred
        users = prefix / "drive_c/users"
        if users.is_dir():
            for user in sorted(users.iterdir()):
                candidate = user / "AppData/Local/Temp"
                if candidate.is_dir():
                    return candidate
        return preferred

    def _kharvox_logs(self, recipe: dict) -> dict[str, Path]:
        temp = self._prefix_temp_dir(recipe)
        if not temp:
            return {}
        return {
            "main": temp / "KHARVOX.log",
            "previous": temp / "KHARVOX-previous-launch.log",
            "errors": temp / "KHARVOX-launcher-errors.log",
            "intro": temp / "KHARVOX-VR-INTRO.log",
            "native": temp / "KHARVOX-NATIVE-STEREO.log",
        }

    def _read_small(self, path: Path | None, limit: int = 262144) -> str:
        if not path or not path.is_file():
            return ""
        try:
            return path.read_bytes()[-limit:].decode("utf-8", "replace")
        except OSError:
            return ""

    def _kharvox_native_state(self, recipe: dict) -> tuple[str, str]:
        logs = self._kharvox_logs(recipe)
        native = logs.get("native")
        if native and native.is_file():
            return "detected", str(native)
        text = self._read_small(logs.get("main")) + "\n" + self._read_small(logs.get("previous"))
        if "nativeAttempt=False" in text:
            return "not-attempted", "KHARVOX reported nativeAttempt=False; no native stereo log was created"
        if "stable VR frame stream" in self._read_small(logs.get("errors")):
            return "unconfirmed", "DOOM launched, but KHARVOX did not confirm a stable VR frame stream"
        return "unknown", "no KHARVOX native-stereo evidence yet"

    def _kharvox_registry_state(self, recipe: dict) -> tuple[str, str]:
        """Inspect Wine's user.reg without spawning Wine during Preflight.

        KHARVOX v1.11 was observed registering its layer beneath the Windows
        Vulkan ImplicitLayers key and toggling the DWORD back to 1 during the
        unsupported GOG/Proton path.  Wine stores that data in user.reg.
        """
        settings = self._settings(recipe)
        raw = str(settings.get("winePrefix", "")).strip()
        root = self._kharvox_dir(recipe)
        if not raw or not root:
            return "unknown", "prefix or KHARVOX directory not detected"
        reg = Path(raw).expanduser() / "user.reg"
        text = self._read_small(reg, 2 * 1024 * 1024)
        if not text:
            return "unknown", f"registry file not readable: {reg}"
        manifest_name = "KharvoxLayer.json"
        # Restrict the lookup to the Vulkan ImplicitLayers section when
        # possible, then accept Wine's dword:0000000N representation.
        m = re.search(r'\[Software\\Khronos\\Vulkan\\ImplicitLayers\].*?(?=\n\[|\Z)', text, re.S | re.I)
        section = m.group(0) if m else text
        line = next((ln for ln in section.splitlines() if manifest_name.lower() in ln.lower()), "")
        if not line:
            return "missing", "KHARVOX Vulkan manifest is not registered in the prefix"
        dm = re.search(r'dword:([0-9a-fA-F]{8})', line)
        if not dm:
            return "present", line.strip()
        value = int(dm.group(1), 16)
        if value == 0:
            return "enabled", "KHARVOX Vulkan manifest DWORD is 0 (enabled)"
        return "disabled", f"KHARVOX Vulkan manifest DWORD is 0x{value:x} (disabled)"

    def _clean_kharvox_host_vulkan_env(self, env: dict[str, str], root: Path) -> dict[str, str]:
        """Do not force the Windows KHARVOX layer into Linux Vulkan.

        Pressure Vessel's host Vulkan loader cannot resolve KharvoxLayer.dll.
        Preserve unrelated user layers while removing only stale KHARVOX host
        overrides from previous troubleshooting sessions.
        """
        env = env.copy()
        env.pop("KHARVOX_ENABLE_LAYER", None)
        layers = [x for x in env.get("VK_INSTANCE_LAYERS", "").split(":") if x and x != "VK_LAYER_KHARVOX_OPENXR"]
        if layers:
            env["VK_INSTANCE_LAYERS"] = ":".join(layers)
        else:
            env.pop("VK_INSTANCE_LAYERS", None)
        for key in ("VK_LAYER_PATH", "VK_IMPLICIT_LAYER_PATH"):
            value = env.get(key, "")
            if value and Path(value).expanduser() == root:
                env.pop(key, None)
        return env

    def play_label(self, recipe: dict) -> str | None:
        return recipe.get("handler_config", {}).get("play_label", "Launch game")

    def launcher_label(self, recipe: dict) -> str | None:
        return recipe.get("handler_config", {}).get("launcher_label")

    def launch_play(self, recipe: dict, game: Path | None) -> subprocess.Popen:
        if not game:
            raise RuntimeError(f"{recipe['name']} was not found in Heroic's GOG installs.")
        exe = self._exe(recipe, game)
        if exe and not exe.is_file():
            raise RuntimeError(f"Configured game executable was not found: {exe}")
        return subprocess.Popen(heroic.heroic_command(self._appid(recipe), "gog"), start_new_session=True)

    def launch(self, recipe: dict, game: Path | None) -> subprocess.Popen:
        """Launch KHARVOX experimentally using Heroic's prefix and Proton.

        Heroic currently cannot launch an arbitrary alternate executable via
        its heroic:// protocol.  umu-run is the supported Linux mechanism for
        running an external Windows executable with an existing WINEPREFIX and
        Proton build, so use it without altering Heroic's saved configuration.
        """
        launcher = self._kharvox_launcher(recipe)
        if not launcher:
            env_name = recipe.get("handler_config", {}).get("kharvox_dir_env", "NANNERS_KHARVOX_DIR")
            raise RuntimeError(
                "KHARVOX was not detected. Extract the complete KHARVOX release outside the DOOM folder "
                f"and set {env_name} to that folder if auto-detection does not find it."
            )

        settings = self._settings(recipe)
        prefix_raw = str(settings.get("winePrefix", "")).strip()
        wine = settings.get("wineVersion") if isinstance(settings.get("wineVersion"), dict) else {}
        runner_raw = str(wine.get("bin", "")).strip()
        prefix = Path(prefix_raw).expanduser() if prefix_raw else None
        runner = Path(runner_raw).expanduser() if runner_raw else None
        umu = shutil.which("umu-run")
        if not prefix or not prefix.is_dir():
            raise RuntimeError("Heroic's configured DOOM prefix could not be found.")
        if not runner or not runner.is_file():
            raise RuntimeError("Heroic's configured Proton runner could not be found.")
        if not umu:
            raise RuntimeError("umu-run was not found in PATH. KHARVOX needs umu-run to reuse Heroic's Proton prefix safely.")

        env = self._clean_kharvox_host_vulkan_env(os.environ.copy(), launcher.parent)
        env.update({
            "WINEPREFIX": str(prefix.resolve()),
            "PROTONPATH": str(runner.parent.resolve()),
            "GAMEID": "0",
            "STORE": "gog",
        })
        return subprocess.Popen([umu, str(launcher)], cwd=str(launcher.parent), env=env, start_new_session=True)

    def bridge_log(self, recipe: dict) -> Path | None:
        logs = self._kharvox_logs(recipe)
        return logs.get("main")

    def bridge_log_label(self, recipe: dict) -> str:
        return "Open KHARVOX log"

    def live_status(self, recipe: dict, game: Path | None) -> dict:
        exe = recipe.get("handler_config", {}).get("executable", "")
        needle = Path(exe).name.lower() if exe else ""
        launcher_running = False
        game_running = False
        proc = Path("/proc")
        for p in proc.iterdir() if proc.is_dir() else []:
            if not p.name.isdigit():
                continue
            try:
                cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore").lower()
            except (OSError, PermissionError):
                continue
            if needle and needle in cmd:
                game_running = True
            if "kharvoxlauncher.exe" in cmd:
                launcher_running = True
        return {
            "label": recipe.get("handler_config", {}).get("status_label", recipe["name"]),
            "game": game_running,
            "tool": launcher_running,
        }

    def preflight_rows(self, recipe: dict, game: Path | None) -> list[dict]:
        appid = self._appid(recipe)
        cfg = recipe.get("handler_config", {})
        settings = self._settings(recipe)
        exe = self._exe(recipe, game)
        prefix_raw = str(settings.get("winePrefix", "")).strip()
        prefix = Path(prefix_raw).expanduser() if prefix_raw else None
        wine = settings.get("wineVersion") if isinstance(settings.get("wineVersion"), dict) else {}
        runner_bin_raw = str(wine.get("bin", "")).strip()
        runner_bin = Path(runner_bin_raw).expanduser() if runner_bin_raw else None
        kharvox = self._kharvox_launcher(recipe)
        rows = [
            {"name": "Heroic GOG metadata", "ok": bool(heroic.gog_install(appid)), "required": True,
             "detail": f"GOG app {appid}" if heroic.gog_install(appid) else f"GOG app {appid} not listed as installed"},
            {"name": "Game executable", "ok": bool(exe and exe.is_file()), "required": True,
             "detail": str(exe) if exe and exe.is_file() else f"missing: {exe or cfg.get('executable', 'not configured')}"},
            {"name": "Heroic prefix", "ok": bool(prefix and prefix.is_dir()), "required": True,
             "detail": str(prefix) if prefix and prefix.is_dir() else "winePrefix missing from Heroic game settings"},
            {"name": "Heroic runner", "ok": bool(runner_bin and runner_bin.is_file()), "required": True,
             "detail": f"{wine.get('name', 'runner')} ({runner_bin})" if runner_bin and runner_bin.is_file()
                       else "configured Proton/Wine runner was not found"},
        ]
        if cfg.get("launcher_label"):
            native_state, native_detail = self._kharvox_native_state(recipe)
            registry_state, registry_detail = self._kharvox_registry_state(recipe)
            logs = self._kharvox_logs(recipe)
            intro = logs.get("intro")
            rows.extend([
                {"name": "KHARVOX launcher", "ok": bool(kharvox and kharvox.is_file()), "required": False,
                 "detail": str(kharvox) if kharvox else "not detected; extract KHARVOX outside the DOOM install"},
                {"name": "umu-run", "ok": bool(shutil.which("umu-run")), "required": False,
                 "detail": shutil.which("umu-run") or "not found in PATH"},
                {"name": "KHARVOX VR intro", "ok": bool(intro and intro.is_file()), "required": False,
                 "detail": str(intro) if intro and intro.is_file() else "no VR-intro log detected yet"},
                {"name": "KHARVOX native stereo", "ok": native_state == "detected", "required": False,
                 "detail": native_detail},
                {"name": "KHARVOX Vulkan registration", "ok": registry_state == "enabled", "required": False,
                 "detail": registry_detail},
                {"name": "KHARVOX compatibility", "ok": False, "required": False,
                 "detail": cfg.get("vr_mod_status", "GOG/Heroic compatibility is experimental and not validated upstream.")},
            ])
        elif cfg.get("vr_mod_status"):
            rows.append({"name": cfg.get("vr_mod_name", "VR mod"), "ok": False, "required": False,
                         "detail": cfg["vr_mod_status"]})
        return rows

    def diagnostics(self, recipe: dict, game: Path | None) -> list[str]:
        settings = self._settings(recipe)
        wine = settings.get("wineVersion") if isinstance(settings.get("wineVersion"), dict) else {}
        exe = self._exe(recipe, game)
        kharvox = self._kharvox_launcher(recipe)
        return [
            "Store: Heroic / GOG",
            f"GOG app ID: {self._appid(recipe)}",
            f"Heroic config: {heroic.config_root()}",
            f"Game executable: {exe or 'not detected'}",
            f"Heroic prefix: {settings.get('winePrefix') or 'not configured'}",
            f"Heroic runner: {wine.get('name') or 'not configured'}",
            f"Heroic runner binary: {wine.get('bin') or 'not configured'}",
            f"KHARVOX directory: {self._kharvox_dir(recipe) or 'not detected'}",
            f"KHARVOX launcher: {kharvox or 'not detected'}",
            f"KHARVOX native stereo: {self._kharvox_native_state(recipe)[0]} — {self._kharvox_native_state(recipe)[1]}",
            f"KHARVOX Vulkan registration: {self._kharvox_registry_state(recipe)[0]} — {self._kharvox_registry_state(recipe)[1]}",
            f"KHARVOX main log: {self._kharvox_logs(recipe).get('main') or 'not detected'}",
            f"KHARVOX native log: {self._kharvox_logs(recipe).get('native') or 'not detected'}",
            f"umu-run: {shutil.which('umu-run') or 'not found'}",
        ]

    def detail_notes(self, recipe: dict) -> list[str]:
        return [
            "This game is discovered from Heroic's GOG metadata, not from Steam.",
            "Launch DOOM asks Heroic to launch the GOG app so Heroic keeps ownership of the configured Proton prefix, runner and environment.",
            "Launch DOOM VR is experimental: it starts KharvoxLauncher.exe with umu-run while reusing Heroic's existing DOOM prefix and Proton build.",
            "The Hub deliberately does not force VK_LAYER_KHARVOX_OPENXR into Linux VK_INSTANCE_LAYERS; Pressure Vessel's host Vulkan loader cannot load KHARVOX's Windows layer DLL.",
            "On the tested GOG/Proton path KHARVOX reaches its VR intro and launches DOOM, but reports nativeAttempt=False and does not create KHARVOX-NATIVE-STEREO.log.",
            "KHARVOX upstream currently documents the Steam release of DOOM (2016) as supported, so GOG compatibility remains experimental.",
        ]


_HANDLERS: dict[str, GameHandler] = {
    "generic": GameHandler(),
    "skyrim-vr": SkyrimVRHandler(),
    "heroic-gog": HeroicGOGHandler(),
}


def get_handler(recipe: dict) -> GameHandler:
    name = recipe.get("handler", "generic")
    try:
        return _HANDLERS[name]
    except KeyError as e:
        raise RuntimeError(f"Unknown game handler '{name}'") from e


def handler_names() -> set[str]:
    return set(_HANDLERS)
