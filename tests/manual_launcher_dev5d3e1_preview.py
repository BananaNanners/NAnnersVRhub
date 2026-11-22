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
from vrhub import archive_releases, archive_scans, updates, kharvox_archive_review
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
    if opts.show:
        # Use one stable private data location for every future worktree.
        # No legacy import, copy, reset, or replacement on launch.
        from vrhub.dev_preview_storage import shared_directory
        shared = shared_directory()
        state_path = shared / "state.json"
        supplied = os.environ.get("VRHUB_STATE")
        if supplied and Path(supplied).resolve() != state_path.resolve():
            raise SystemExit("Desktop preview must reuse the stable shared preview state.")
        if not state_path.is_file() or state_path.is_symlink():
            raise SystemExit("Existing private preview state is required; nothing restored.")
        os.environ["VRHUB_STATE"] = str(state_path)
        os.environ["VRHUB_NEXUS_KEY_FILE"] = str(shared / "test-nexus-key")
        for key, folder in (("XDG_CONFIG_HOME","config"), ("XDG_DATA_HOME","data"),
                            ("XDG_CACHE_HOME","cache")):
            os.environ[key] = str(shared / folder)
    state = Path(os.environ.get("VRHUB_STATE", "")).resolve()
    production = (Path.home() / ".local/share/vrhub/state.json").resolve()
    if not state.is_file() or state == production or not os.environ.get("VRHUB_NEXUS_KEY_FILE"):
        raise SystemExit("Private preview state and key path required.")
    HubUpdateController.startup = lambda self: None
    gui.HubWindow.scan_setup = lambda self, *a, **kw: None
    if opts.verify:
        gui.HubWindow.check_updates = lambda self: None
    if opts.verify:
        # Only the disposable copied preview state is mutated. Read actual
        # release metadata and the actual downloaded archive; do not extract.
        if not state.parent.name.startswith("nanners-dev5d3e1-gui."):
            raise SystemExit("Verification requires an isolated Dev5D3-E fixture.")
        recipe = hub.load_recipes()["doom-2016-gog"]
        planner.set_location("game", str(Path.home() / "Downloads"), recipe["id"])
        catalogs, errors = archive_releases.catalogs_for(recipe)
        if errors:
            raise SystemExit(f"Official metadata unavailable: {errors}")
        archive_scans.persist(planner.build_plan(recipe, Path.home() / "Downloads",
                            release_catalogs=catalogs, release_errors=errors))
        original_scan = archive_scans.snapshot_file().read_bytes()
        doom_updates = updates.check_recipe(recipe, {})
    app = QApplication([sys.argv[0]])
    win = CleanupPreview()
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3e1 — ARCHIVE PERSISTENCE (NO GAME WRITES)")
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev5D3e1 · PREVIEW")
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

    select("doom-2016-gog")
    win.show()
    app.processEvents()
    win.disable_mutations()
    if opts.show:
        print("DEV5D3E1 DESKTOP READY — DOOM selected; no game writes or archive transfers.", flush=True)
        return app.exec()

    win.resize(1630, 1060)
    app.processEvents()
    checks = {}
    checks["downloads_default"] = planner.default_library() == Path.home() / "Downloads"
    # Restore the active folder for any currently existing saved scan only
    # through the same explicit menu action a user would use, in this fixture.
    for rid, saved in archive_scans.load_saved().items():
        if rid not in hub.load_recipes():
            continue
        select(rid)
        if str(win.downloads._last_folder) != saved["folder"] and Path(saved["folder"]).is_dir():
            win.downloads._sync_folder_actions()
            checks[rid+"_saved_history_visible"] = "Saved scan retained" in win.downloads.scan_age.text()
            checks[rid+"_saved_folder_menu"] = win.downloads.saved_folder_action.isVisible()
            win.downloads.saved_folder_action.trigger()
            app.processEvents()
            checks[rid+"_folder_reused"] = str(win.downloads._last_folder) == saved["folder"]
            checks[rid+"_scan_reused"] = win.downloads._last_plan is not None
    checks["scan_history_bytes_unchanged_by_folder_selection"] = archive_scans.snapshot_file().read_bytes() == original_scan
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
            and page.install_review_button.isEnabled() == (route not in ("scan","idle","blocked","select","kharvox-wait")))
        checks[rid + "_saved_folder_preserved"] = str(page._last_folder) == str(planner.folder_for(recipe)[0])
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
        if method == "guide" and rid != "doom-2016-gog":
            checks[rid + "_guide_primary"] = page.install_review_button.text() == "Open Setup Guide"
        if rid == "doom-2016-gog":
            checks["doom_official_archive"] = "v1.1.1" in page.table.item(0,3).text()
            checks["doom_review_label"] = page.install_review_button.text() == "Review installation"
            checks["doom_review_enabled"] = page.install_review_button.isEnabled()
            def inspect(dialog):
                dialog.show()
                app.processEvents()
                checks["doom_disabled_apply"] = not dialog.apply_button.isEnabled()
                checks["doom_old_release_blocked"] = not dialog.plan.tested_archive and "COMPATIBILITY BLOCKED" in dialog.compatibility.text()
                checks["doom_exact_release"] = dialog.plan.tags == ("v1.1.1",) and dialog.plan.latest == "v1.4a"
                checks["doom_review_render"] = dialog.grab().save(str(screenshots / "doom-review.png"))
                dialog.close()
                return QDialog.Rejected
            with mock.patch.object(kharvox_archive_review.ReviewDialog,"exec",inspect), mock.patch.object(
                    page,"_choose_archive_candidate") as picker, mock.patch.object(hub,"install") as install, mock.patch.object(
                    hub,"install_many") as many:
                page.install_review_button.click()
                checks["doom_no_picker_or_install"] = not picker.called and not install.called and not many.called
            checks["doom_new_release"] = updates.release_count(doom_updates) == 1 and doom_updates[0].get("latest_version") == "v1.4a"
            checks["doom_no_installed_claim"] = "installed_version" not in doom_updates[0]
            win.update_results[rid] = doom_updates
            win.show_details()
            win.game_details_tabs.setCurrentWidget(win.mod_updates)
            app.processEvents()
            win.game_page_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            checks["doom_updates_render"] = win.grab().save(str(screenshots / "doom-updates.png"))
        if page._has_uevr_pair() and page._primary_action()[0] == "uevr-pair" and page.install_review_button.text() == "Review installation":
            checks[rid + "_no_manual_fallback"] = page.manual_review_button.isHidden()
            with mock.patch.object(DependencyReviewDialog, "exec", return_value=QDialog.Rejected) as dialog, mock.patch.object(
                win, "_pick") as picker, mock.patch.object(win, "_pick_many") as many, mock.patch.object(
                page, "_choose_archive_candidate") as chooser:
                page.install_review_button.click()
                checks[rid + "_direct_pair_review"] = dialog.call_count == 1 and not picker.called and not many.called and not chooser.called
    for name, ok in checks.items():
        print("DEV5D3E1_CHECK", name, "PASS" if ok else "FAIL", flush=True)
    print("DEV5D3E1_GUI_RESULT", sum(bool(ok) for ok in checks.values()), "/", len(checks), flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
