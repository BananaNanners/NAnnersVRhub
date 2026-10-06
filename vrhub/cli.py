import argparse
import os
import sys
import zipfile
from pathlib import Path

from . import hub, runtime, updates
from .steam import find_game


def _roots():
    v = os.environ.get("VRHUB_STEAM_ROOTS")
    return v.split(":") if v else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="nannersvrhub", description="NAnnersVRhub: Linux VR mod hub (WiVRn / Quest)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="check the OpenXR runtime and list games")
    sub.add_parser("gui", help="open the Qt window")
    sub.add_parser("updates", help="check for newer releases")
    k = sub.add_parser("nexus-key", help="save or clear your Nexus API key (for automatic Nexus update checks)")
    k.add_argument("--clear", action="store_true", help="remove the saved key")
    k.add_argument("--status", action="store_true", help="say whether a key is set")
    v = sub.add_parser("verify", help="check that every required mod is installed (exit 1 if not)")
    v.add_argument("game")
    v.add_argument("--quiet", action="store_true", help="print only problems/notices (used by the launch guard)")
    v.add_argument("--names", action="store_true", help="look up the real mod names on Nexus first (needs an API key)")
    sub.add_parser("info", help="show the setup checklist for a game").add_argument("game")
    sub.add_parser("diagnose", help="print a paste-friendly local diagnostic summary").add_argument("game")
    sub.add_parser("preflight", help="check game/runtime/mod readiness without changing anything").add_argument("game")
    ins = sub.add_parser("inspect", help="inspect a game-root mod archive without installing it")
    ins.add_argument("game")
    ins.add_argument("--file", type=Path, required=True)
    i = sub.add_parser("install", help="install a mod file (.pak/.zip, or the UEVR zip)")
    i.add_argument("game")
    i.add_argument("--file", type=Path, required=True, nargs="+",
                   help="the file(s) you downloaded (several allowed for games like Cyberpunk 2077)")
    sub.add_parser("uninstall", help="remove the mod").add_argument("game")
    p = sub.add_parser("install-profile", help="install a UEVR game profile zip")
    p.add_argument("game")
    p.add_argument("--file", type=Path, required=True)
    sub.add_parser("uninstall-profile", help="remove the profile (restores the backup)").add_argument("game")
    sub.add_parser("mark-current", help="record that your install is the latest release").add_argument("game")
    sub.add_parser("launch-injector", help="run the UEVR injector for a game").add_argument("game")
    sub.add_parser("launch-tool", help="launch a game-specific tool such as MO2").add_argument("game")
    sub.add_parser("launch-game", help="launch the handler-configured modded game path").add_argument("game")
    a = ap.parse_args(argv)
    recipes = hub.load_recipes()

    try:
        if a.cmd == "gui":
            from .gui import main as gui_main
            return gui_main()
        if a.cmd == "status":
            print("NAnnersVRhub")
            path, lib = runtime.active_runtime()
            print(f"OpenXR runtime: {'WiVRn OK' if runtime.is_wivrn() else 'NOT WiVRn'} ({lib or 'none found'})")
            for r in recipes.values():
                g = hub.game_path(r, _roots())
                mod = "mod installed" if hub.is_installed(r["id"]) else "mod not installed"
                prof = ""
                if "profile" in r:
                    prof = ", profile installed" if hub.profile_installed(r["id"]) else ", profile not installed"
                print(f"- {r['id']}: {'game found' if g else 'game not found'}, {mod}{prof}")
            return 0
        if a.cmd == "nexus-key":
            if a.clear:
                updates.clear_key()
                print("Saved Nexus API key removed.")
            elif a.status:
                print("Nexus API key: set" if updates.get_key() else "Nexus API key: not set")
            else:
                import getpass
                key = getpass.getpass("Paste your Nexus personal API key (input is hidden): ").strip()
                name = updates.validate_key(key)  # raises OSError if invalid or unreachable
                updates.set_key(key)
                print(f"Key accepted for Nexus account '{name}'. Saved to {updates.key_path()} (readable only by you).")
            return 0
        if a.cmd == "updates":
            for rid, items in updates.check_all(recipes, hub.state()).items():
                print(f"{recipes[rid]['name']}")
                for it in items:
                    print(f"  - {it['name']}: {it['detail']}")
            return 0
        if a.game not in recipes:
            raise RuntimeError(f"Unknown game '{a.game}'. Known: {', '.join(recipes)}")
        r = recipes[a.game]
        if a.cmd == "verify":
            if not r.get("components"):
                raise RuntimeError(f"{r['name']} has no component checklist.")
            if a.names:
                hub.refresh_component_names(r)
            rep = hub.verify(r)
            text = hub.verify_text(rep, quiet=a.quiet)
            if not (a.quiet and rep["ready"] and not rep["later_bad"]):
                print(text)
            return 0 if rep["ready"] else 1
        if a.cmd == "info":
            print(hub.details_text(r))
        elif a.cmd == "diagnose":
            print(hub.diagnostics(r, _roots()))
        elif a.cmd == "preflight":
            rep = hub.preflight(r, _roots())
            print(hub.preflight_text(rep))
            return 0 if rep["ready"] else 1
        elif a.cmd == "inspect":
            print(hub.inspect_text(hub.inspect_archive(r, a.file)))
        elif a.cmd == "install":
            done = hub.install_many(r, a.file, _roots())
            if len(done) > 5:
                print(f"Installed {len(done)} files from {len(a.file)} archive(s).")
            else:
                for f in done:
                    print(f"Installed {f}")
            print("\nSet this as the game's Steam launch options:\n  " + hub.launch_options(r))
            rep = hub.verify(r)
            if rep:
                print("\n" + hub.verify_text(rep))
            print(f"\nFull checklist: python -m vrhub.cli info {a.game}")
        elif a.cmd == "install-profile":
            files = hub.install_profile(r, a.file, _roots())
            print(f"Installed profile ({len(files)} files) into {Path(files[0]).parent if files else '?'}")
        elif a.cmd == "uninstall-profile":
            print(f"Removed {len(hub.uninstall(a.game + ':profile'))} profile files (backup restored if there was one)")
        elif a.cmd == "mark-current":
            done = hub.mark_current(r)
            print(f"Marked as up to date: {', '.join(done)}" if done else "Nothing installed through the hub to mark.")
        elif a.cmd == "launch-injector":
            hub.launch_injector(r, _roots())
            print("Injector started. Pick the game process, tick OpenXR, Inject.")
        elif a.cmd == "launch-tool":
            hub.launch_game_tool(r, _roots())
            print(f"{hub.game_launcher_label(r) or 'Tool'} request sent through Steam.")
        elif a.cmd == "launch-game":
            hub.launch_game_play(r, _roots())
            print(f"{hub.game_play_label(r) or 'Game'} request sent through Steam/MO2.")
        elif a.cmd == "uninstall":
            for f in hub.uninstall(a.game):
                print(f"Removed {f}")
    except (RuntimeError, OSError, zipfile.BadZipFile) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
