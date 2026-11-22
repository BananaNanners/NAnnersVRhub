# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-E2 isolated preview: Downloads + optional game folder, no game writes."""
import argparse
import os
import sys
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from PySide6.QtWidgets import QApplication, QLabel, QDialog
from vrhub import gui, hub, archive_scans, download_planner as planner
from vrhub.app_update_gui import HubUpdateController
from tests.manual_launcher_dev5d3e1_preview import CleanupPreview


def main():
    args=argparse.ArgumentParser()
    mode=args.add_mutually_exclusive_group(required=True)
    mode.add_argument("--show",action="store_true")
    mode.add_argument("--verify",action="store_true")
    opts=args.parse_args()
    if opts.show:
        from vrhub.dev_preview_storage import shared_directory
        store=shared_directory()
        supplied=Path(os.environ.get("VRHUB_STATE","")).resolve()
        state=(store/"state.json").resolve()
        if supplied != state or not state.is_file() or state.is_symlink():
            raise SystemExit("Refusing non-shared or symlinked desktop preview state.")
        # Never migrate/restore older scans on preview startup.
    state=Path(os.environ.get("VRHUB_STATE","")).resolve()
    if (not state.is_file() or not os.environ.get("VRHUB_NEXUS_KEY_FILE") or
            state==Path.home()/".local/share/vrhub/state.json"):
        raise SystemExit("Existing isolated preview state required.")
    if opts.verify and not state.parent.name.startswith("nanners-dev5d3e2-gui."):
        raise SystemExit("GUI verification requires a disposable private fixture.")

    HubUpdateController.startup=lambda self: None
    gui.HubWindow.scan_setup=lambda self,*a,**kw: None
    if opts.verify:
        gui.HubWindow.check_updates=lambda self: None
    app=QApplication([sys.argv[0]])
    win=CleanupPreview()
    win.allow_guided_installs=False
    win.downloads.allow_transfers=False
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3e2 — MULTI-FOLDER PREVIEW (NO GAME WRITES)")
    brand=win.findChild(QLabel,"brandTitle")
    if brand: brand.setText("NAnnersVRhub  0.5.5-dev5D3e2 · PREVIEW")
    win.tabs.setCurrentIndex(1)

    def select(rid):
        win.sidebar.game_list.setCurrentRow(next(
            i for i,row in enumerate(win.rows) if row["recipe"]["id"]==rid))
        win.game_details_tabs.setCurrentWidget(win.downloads)
        win.install_tools_toggle.setChecked(False)
        win.library_toggle.setChecked(False)
        win.game_page_scroll.verticalScrollBar().setValue(0)
        app.processEvents()
        win.disable_mutations()

    select("fatekeeper")
    win.show()
    app.processEvents()
    win.disable_mutations()
    if opts.show:
        print("DEV5D3E2 DESKTOP READY — current preferences and scans preserved; no game writes.",flush=True)
        return app.exec()

    win.resize(1630,1060)
    app.processEvents()
    checks={}
    imgs=state.parent/"renders"
    imgs.mkdir(exist_ok=True)
    saved=archive_scans.load_saved()
    previous_bytes=archive_scans.snapshot_file().read_bytes()
    checks["legacy_snapshot_original"] = bool(saved)
    checks["default_downloads"] = planner.default_library()==Path.home()/"Downloads"
    for rid,rec in saved.items():
        if rid not in hub.load_recipes(): continue
        select(rid)
        # Inactive legacy records are retained, not automatically authorized.
        if rec["folder"]!=str(Path.home()/"Downloads"):
            checks[rid+"_legacy_inactive"] = (
                win.downloads._last_plan is None or
                archive_scans.matching_record(rid,planner.scan_folders(hub.load_recipes()[rid])) is not None)
    checks["no_automatic_import"] = previous_bytes==archive_scans.snapshot_file().read_bytes()

    # All following changes are to the disposable *copied* test fixture only.
    for rid, rec in saved.items():
        if rid not in hub.load_recipes(): continue
        old_roots=archive_scans.plan_folders(rec["plan"])
        custom=old_roots[-1]
        if custom!=Path.home()/"Downloads" and custom.is_dir():
            planner.set_location("game",str(custom),rid)
        recipe=hub.load_recipes()[rid]
        roots=planner.scan_folders(recipe)
        if all(root.is_dir() and not root.is_symlink() for root in roots):
            try:
                archive_scans.persist(planner.build_plan(recipe,roots))
            except (OSError, ValueError) as exc:
                print("SCAN FIXTURE REFUSED",rid,str(exc),flush=True)
    checks["saved_legacy_history_kept"] = all(
        len(archive_scans.load_histories().get(rid,[]))>=1
        for rid in saved if rid in hub.load_recipes())
    checks["explicit_scans_version2"] = archive_scans.snapshot_file().read_text().find('"schema":2')!=-1

    for item in win.rows:
        recipe=item["recipe"]
        rid=recipe["id"]
        select(rid)
        roots=planner.scan_folders(recipe)
        checks[rid+"_downloads_included"] = roots[0]==Path.home()/"Downloads"
        checks[rid+"_additional_at_most_one"] = len(roots) in (1,2)
        checks[rid+"_five_columns"] = win.downloads.table.columnCount()==5
        checks[rid+"_scan_enabled"] = win.downloads.scan.isEnabled()
        checks[rid+"_install_blocked"] = not win.allow_guided_installs and not win.downloads.allow_transfers
        checks[rid+"_location_label"] = "Always scanned:" in win.downloads.location.text()
        checks[rid+"_no_game_mutation"] = win.install_btn.isHidden() and win.profile_btn.isHidden()
        checks[rid+"_current_folder_label"] = (
            ("Additional folder" in win.downloads.location.text()) and
            ("Downloads" in win.downloads.location.text()))
        checks[rid+"_render"] = win.grab().save(str(imgs/(rid+"-multi.png")))
        if rid in saved:
            current=archive_scans.matching_record(rid,roots)
            checks[rid+"_scan_record"] = current is not None
            checks[rid+"_active_plan"] = win.downloads._last_plan is not None
            checks[rid+"_folders_in_plan"] = (
                bool(current) and archive_scans.plan_folders(current["plan"])==roots)
            checks[rid+"_paths_within_roots"] = bool(current) and all(
                not r["file"] or any(Path(r["file"]).is_relative_to(root) for root in roots)
                for r in current["plan"]["rows"])
    for name,passed in checks.items():
        print("DEV5D3E2_CHECK",name,"PASS" if passed else "FAIL",flush=True)
    print("DEV5D3E2_GUI_RESULT",sum(bool(x) for x in checks.values()),"/",len(checks),flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1

if __name__=="__main__":
    raise SystemExit(main())
