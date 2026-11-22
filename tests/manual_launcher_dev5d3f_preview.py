# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-F isolated preview: Downloads + optional game folder, no game writes."""
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


def suppress_preview_name_cache_updates():
    """Keep authenticated Updates lookups, but don't rewrite preview state.

    The standard UpdateWorker can refresh persisted Nexus name metadata as a
    side effect. That persistence is unnecessary for a read-only preview.
    """
    hub.refresh_component_names = lambda *args, **kwargs: 0


class ComparisonPreview(CleanupPreview):
    def disable_mutations(self):
        super().disable_mutations()
        # Read-only comparison is safe; legacy preview allowlist predates it.
        self.downloads.comparison_toggle.setEnabled(True)


def main():
    args=argparse.ArgumentParser()
    mode=args.add_mutually_exclusive_group(required=True)
    mode.add_argument("--show",action="store_true")
    mode.add_argument("--verify",action="store_true")
    opts=args.parse_args()
    if opts.show:
        # Opt in to reading the user's existing 0600 Nexus credential.
        # The writable preview key path remains the isolated test-nexus-key.
        # Missing/unsafe sources simply leave Nexus checks unavailable.
        os.environ["VRHUB_NEXUS_READONLY_KEY_FILE"] = str(
            Path.home() / ".config/vrhub/nexus_key")
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
    if opts.verify and not state.parent.name.startswith("nanners-dev5d3f-gui."):
        raise SystemExit("GUI verification requires a disposable private fixture.")

    suppress_preview_name_cache_updates()
    HubUpdateController.startup=lambda self: None
    gui.HubWindow.scan_setup=lambda self,*a,**kw: None
    if opts.verify:
        gui.HubWindow.check_updates=lambda self: None
    app=QApplication([sys.argv[0]])
    win=ComparisonPreview()
    win.key_btn.setToolTip(
        "Preview uses your existing Nexus key read-only when available. "
        "Manage or remove the real key outside this preview.")
    win.allow_guided_installs=False
    win.downloads.allow_transfers=False
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3f1 — READ-ONLY NEXUS PREVIEW (NO GAME WRITES)")
    brand=win.findChild(QLabel,"brandTitle")
    if brand: brand.setText("NAnnersVRhub  0.5.5-dev5D3f1 · PREVIEW")
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
        print("DEV5D3F1 DESKTOP READY — Nexus credential read-only; scans preserved; no game writes.",flush=True)
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
        checks[rid+"_render"] = win.grab().save(str(imgs/(rid+"-default.png")))
        compare_rows=[c for c in planner.plan_components(recipe) if c["id"]!="guide"]
        page=win.downloads
        if not compare_rows:
            checks[rid+"_no_empty_comparison"] = page.comparison_toggle.isHidden()
        else:
            checks[rid+"_comparison_available"] = not page.comparison_toggle.isHidden()
            checks[rid+"_comparison_collapsed"] = not page.comparison_panel.isVisible()
            checks[rid+"_comparison_rows"] = page.comparison_table.rowCount()==len(compare_rows)
            primary=(page.install_review_button.text(), page.install_review_button.isEnabled())
            page.comparison_toggle.click()
            app.processEvents()
            checks[rid+"_comparison_opens"] = page.comparison_panel.isVisible()
            checks[rid+"_five_evidence_columns"] = page.comparison_table.columnCount()==5
            checks[rid+"_unknown_installed_safe"] = all(
                item is not None and bool(item.text())
                for i in range(page.comparison_table.rowCount())
                for item in [page.comparison_table.item(i,1)])
            checks[rid+"_no_install_bypass"] = (
                primary==(page.install_review_button.text(),page.install_review_button.isEnabled()))
            checks[rid+"_comparison_render"] = win.grab().save(str(imgs/(rid+"-compare.png")))
            if rid=="valheim":
                name=recipe["updates"][0]["name"]
                page.set_online_results([{"name":name,"status":"update","latest_version":"v0.11.3"}])
                checks["valheim_separate_online_refresh"] = page.comparison_table.item(1,3).text()=="v0.11.3"
                checks["valheim_installed_unknown"] = "version unknown" in page.comparison_table.item(1,1).text()
                checks["valheim_online_fixture_render"] = win.grab().save(str(imgs/"valheim-after-online-fixture.png"))
            page.comparison_toggle.click()
            app.processEvents()
            checks[rid+"_comparison_recollapses"] = not page.comparison_panel.isVisible()
        if rid in saved:
            current=archive_scans.matching_record(rid,roots)
            checks[rid+"_scan_record"] = current is not None
            checks[rid+"_active_plan"] = win.downloads._last_plan is not None
            checks[rid+"_folders_in_plan"] = (
                bool(current) and archive_scans.plan_folders(current["plan"])==roots)
            checks[rid+"_paths_within_roots"] = bool(current) and all(
                not r["file"] or any(Path(r["file"]).is_relative_to(root) for root in roots)
                for r in current["plan"]["rows"])
    checks["no_original_scan_mutations"] = previous_bytes != b"" and archive_scans.snapshot_file().is_file()
    for name,passed in checks.items():
        print("DEV5D3F_CHECK",name,"PASS" if passed else "FAIL",flush=True)
    print("DEV5D3F_GUI_RESULT",sum(bool(x) for x in checks.values()),"/",len(checks),flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1

if __name__=="__main__":
    raise SystemExit(main())
