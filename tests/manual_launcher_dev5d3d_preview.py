# SPDX-License-Identifier: GPL-3.0-only
"""Isolated KDE cleanup preview and nine-game rendered widget verification."""
import argparse
import os
import sys
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication, QLabel, QDialog
from vrhub import gui, hub, verified_download, download_planner as planner
from vrhub.app_update_gui import HubUpdateController
from vrhub.uevr_dependency_review_gui import DependencyReviewDialog
from tests.manual_launcher_dev5d3b_preview import LauncherPreview


class CleanupPreview(LauncherPreview):
    def disable_mutations(self):
        super().disable_mutations()
        # Manual fallback opens the same read-only review handlers.
        button = self.downloads.manual_review_button
        button.setEnabled(not button.isHidden() and self.downloads.worker is None
                          and self.downloads.download_worker is None)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--show", action="store_true")
    group.add_argument("--verify", action="store_true")
    opts = parser.parse_args()
    state = Path(os.environ.get("VRHUB_STATE", "")).resolve()
    production = (Path.home() / ".local/share/vrhub/state.json").resolve()
    if not state.is_file() or state == production or not os.environ.get("VRHUB_NEXUS_KEY_FILE"):
        raise SystemExit("Private preview state and key path required.")
    HubUpdateController.startup = lambda self: None
    gui.HubWindow.scan_setup = lambda self, *a, **kw: None
    if opts.verify:
        gui.HubWindow.check_updates = lambda self: None
    app = QApplication([sys.argv[0]])
    win = CleanupPreview()
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3d — INSTALLATION CLEANUP (NO GAME WRITES)")
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev5D3d · PREVIEW")
    win.tabs.setCurrentIndex(1)
    def select(rid):
        win.sidebar.game_list.setCurrentRow(next(
            i for i, row in enumerate(win.rows) if row["recipe"]["id"] == rid))
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
        print("DEV5D3D DESKTOP READY — Fatekeeper selected; no game writes or transfers.", flush=True)
        return app.exec()

    win.resize(1630, 1060)
    app.processEvents()
    checks = {}
    screenshots = state.parent / "renders"
    screenshots.mkdir(exist_ok=True)
    page = win.downloads
    for item in win.rows:
        recipe = item["recipe"]
        rid = recipe["id"]
        method = recipe.get("method", "file")
        select(rid)
        route, label = page._primary_action()
        checks[rid + "_scan"] = page.scan.isVisible() and page.scan.isEnabled()
        checks[rid + "_archive_columns"] = page.table.columnCount() == 5 and [
            page.table.horizontalHeader().logicalIndex(i) for i in range(5)] == [2,0,3,1,4]
        checks[rid + "_primary"] = (page.install_review_button.text() == label
            and page.install_review_button.isHidden() == (route in ("scan","idle"))
            and page.install_review_button.isEnabled() == (route not in ("scan","idle","blocked","select")))
        checks[rid + "_legacy_controls_hidden"] = win.install_btn.isHidden() and win.profile_btn.isHidden()
        checks[rid + "_idle_transfer_hidden"] = all(w.isHidden() for w in (
            page.download_cancel, page.download_progress, page.download_status))
        checks[rid + "_gates"] = (not win.allow_guided_installs and not page.allow_transfers
            and not win.install_btn.isEnabled() and not win.game_play_btn.isEnabled())
        checks[rid + "_advanced_collapsed"] = not win.install_tools_panel.isVisible()
        checks[rid + "_render"] = win.grab().save(str(screenshots / (rid + "-default.png")))
        if page.table.rowCount():
            page.table.selectRow(0)
            app.processEvents()
            win.disable_mutations()
        component, status = page._selected_component()
        eligible = bool(component and verified_download.source_support(recipe, component)[0]
                        and status != "Pinned SHA-256 verified")
        checks[rid + "_download_eligibility"] = page.download_button.isHidden() == (not eligible)
        checks[rid + "_transfer_advanced_only"] = (page.download_button.parent() is win.install_tools_panel
            and not page.download_button.isEnabled())
        checks[rid + "_verify_relevant"] = win.verify_btn.isHidden() == (not bool(recipe.get("components") or recipe.get("packages")))
        checks[rid + "_doom_only"] = all(b.isHidden() == (rid != "doom-2016-gog") for b in (
            win.kharvox_folder_btn, win.doom_prepare_btn, win.doom_import_btn))
        controls = (page.manual_review_button, page.download_button, win.verify_btn, win.inspect_btn,
                    page.inspect, win.kharvox_folder_btn, win.doom_prepare_btn, win.doom_import_btn)
        checks[rid + "_no_empty_advanced"] = win.install_tools_toggle.isHidden() == all(b.isHidden() for b in controls)
        if not win.install_tools_toggle.isHidden():
            win.install_tools_toggle.click()
            app.processEvents()
            checks[rid + "_advanced_open"] = win.install_tools_panel.isVisible()
            win.game_page_scroll.verticalScrollBar().setValue(
                win.game_page_scroll.verticalScrollBar().maximum())
            app.processEvents()
            checks[rid + "_advanced_render"] = win.grab().save(str(screenshots / (rid + "-advanced.png")))
        if method == "guide":
            checks[rid + "_guide_primary"] = page.install_review_button.text() == "Open Setup Guide"
        if page._has_uevr_pair() and page._primary_action()[0] == "uevr-pair" and page.install_review_button.text() == "Review installation":
            checks[rid + "_no_manual_fallback"] = page.manual_review_button.isHidden()
            with mock.patch.object(DependencyReviewDialog, "exec", return_value=QDialog.Rejected) as dialog, mock.patch.object(
                win, "_pick") as picker, mock.patch.object(win, "_pick_many") as many, mock.patch.object(
                page, "_choose_archive_candidate") as chooser:
                page.install_review_button.click()
                checks[rid + "_direct_pair_review"] = dialog.call_count == 1 and not picker.called and not many.called and not chooser.called
    for name, ok in checks.items():
        print("DEV5D3D_CHECK", name, "PASS" if ok else "FAIL", flush=True)
    print("DEV5D3D_GUI_RESULT", sum(bool(ok) for ok in checks.values()), "/", len(checks), flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
