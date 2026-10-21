import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

from . import __version__, compatibility, hub, live_tests, log_diagnostics, runtime, support_report, system_scan, updates
from .steam import find_game


def _roots():
    v = os.environ.get("VRHUB_STEAM_ROOTS")
    return v.split(":") if v else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="nannersvrhub", description="NAnnersVRhub: Linux VR mod hub (WiVRn / Quest)")
    ap.add_argument("--version", action="version", version="NAnnersVRhub " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="check the OpenXR runtime and list games")
    s = sub.add_parser("scan", help="read-only host VR setup scan (hardware remains unverified)")
    s.add_argument("--json", action="store_true", help="print the structured report")
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
    c = sub.add_parser("compatibility", help="show dated compatibility reference and current read-only evidence")
    c.add_argument("game")
    c.add_argument("--json", action="store_true", help="print the structured compatibility report")
    record_test = sub.add_parser("record-test", help="save an explicit local gameplay test report")
    record_test.add_argument("game")
    record_test.add_argument("--result", required=True, choices=list(live_tests.OUTCOMES))
    record_test.add_argument("--notes", default="", help="what worked, failed, and any workaround (max 4000 characters)")
    for key in live_tests.CHECKS:
        record_test.add_argument("--" + key.replace("_", "-"), choices=list(live_tests.STATES), default="not-tested")
    record_test.add_argument("--json", action="store_true", help="print the saved record as JSON")
    test_history = sub.add_parser("test-history", help="read this game's local gameplay test history")
    test_history.add_argument("game")
    test_history.add_argument("--json", action="store_true")
    logs = sub.add_parser("logs", help="inspect bounded game-log tails without changing files or readiness")
    logs.add_argument("game")
    logs.add_argument("--file", type=Path, nargs="+", help="inspect these 1–4 logs instead of the expected automatic path")
    logs.add_argument("--json", action="store_true")
    support = sub.add_parser("support-report", help="collect a fresh combined support report for one game")
    support.add_argument("game")
    support.add_argument("--file", type=Path, nargs="+", help="explicit log files instead of the expected automatic path")
    support.add_argument("--json", action="store_true")
    support.add_argument("--output", type=Path, help="also save to a new file (existing files are preserved)")
    support.add_argument("--no-excerpts", action="store_true", help="omit matching log excerpts")
    support.add_argument("--include-home-path", action="store_true", help="keep this Linux home path instead of replacing it with ~")
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
    try:
        if a.cmd == "scan":
            report = system_scan.scan()
            print(json.dumps(report, indent=2) if a.json else system_scan.report_text(report))
            return 0 if report["status"] == "HOST CHECKS PASSED" else 1
        recipes = hub.load_recipes()
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
        if a.cmd == "support-report":
            snapshot = support_report.collect(r, _roots(), log_files=a.file)
            view = support_report.export_view(snapshot, include_excerpts=not a.no_excerpts,
                                              replace_home=not a.include_home_path)
            if a.output:
                support_report.save(a.output, view, json_format=a.json)
            print(support_report.serialize(view, json_format=a.json), end="")
            return 0 if snapshot["collection_status"] == "COMPLETE" else 1
        if a.cmd == "logs":
            rep = log_diagnostics.report(r, _roots(), files=a.file)
            print(json.dumps(rep, indent=2) if a.json else log_diagnostics.report_text(rep))
            # This is command/read availability, never a gameplay pass/fail code.
            return 0 if any(item["status"] in {"READ", "EMPTY"} for item in rep["logs"]) else 1
        if a.cmd == "compatibility":
            rep = compatibility.report(r, _roots())
            print(json.dumps(rep, indent=2) if a.json else compatibility.report_text(rep))
            return 0 if rep["status"] in {"LOCAL CHECKS PASSED", "REVIEW REQUIRED"} else 1
        if a.cmd == "record-test":
            checks = {key: getattr(a, key) for key in live_tests.CHECKS}
            # Validate before scanning, and never write install bookkeeping.
            live_tests.validate_result(a.result, a.notes, checks)
            report = compatibility.report(r, _roots())
            entry = live_tests.record(r, a.result, a.notes, checks, report)
            print(json.dumps(entry, indent=2) if a.json else live_tests.record_text(entry))
            return 0
        if a.cmd == "test-history":
            entries = live_tests.history(r["id"])
            print(json.dumps({"schema_version": 1, "recipe_id": r["id"], "records": entries}, indent=2)
                  if a.json else live_tests.history_text(r, entries))
            return 0
        if a.cmd == "verify":
            if not (r.get("components") or r.get("packages")):
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
