# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Isolated KDE preview for Dev5A's guided local archive inventory.

Game installs, app updates, removals, launches and save recovery are DISABLED.
Folder preferences and custom banners write ONLY inside isolated test data.
Uses VRHUB_STATE pointing at a private copy of production state.
--verify exercises real Qt navigation and saves a screenshot to a test path.
--desktop opens the preview for human layout acceptance.
"""
import argparse
import os
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QHeaderView

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vrhub import gui, hub, updates, table_columns
from vrhub.app_update_gui import HubUpdateController


class LauncherPreview(gui.HubWindow):
    def show_details(self):
        super().show_details()
        self.disable_mutations()

    def disable_mutations(self):
        allow = {
            self.sidebar.games_button,
            self.sidebar.system_button,
            self.library_toggle,
            self.more_tools_toggle,
            self.sidebar.future_toggle,
            self.check_btn,
            self.mod_updates.refresh_button,
            self.change_banner_btn,
            self.restore_banner_btn,
            self.downloads.set_global, self.downloads.set_game,
            self.downloads.clear_game, self.downloads.reset_global,
            self.downloads.scan, self.downloads.inspect,
        }
        for button in self.findChildren(QPushButton):
            if button not in allow and button.objectName() not in ("modSourceButton", "downloadsSourceButton"):
                button.setEnabled(False)
        self.development_tools_action.setEnabled(False)
        self.hub_update_btn.setEnabled(False)


def main():
    args = argparse.ArgumentParser()
    group = args.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify", action="store_true")
    group.add_argument("--desktop", action="store_true")
    opts = args.parse_args()

    data = Path(os.environ.get("VRHUB_STATE", "")).resolve()
    original = (Path.home() / ".local/share/vrhub/state.json").resolve()
    if not data.is_file() or data == original:
        raise SystemExit("Specify an existing private VRHUB_STATE test copy")
    if not os.environ.get("VRHUB_NEXUS_KEY_FILE"):
        raise SystemExit("Nexus API key location must be explicitly configured")

    # Prevent the app self-updater and expensive/unrelated runtime scans.
    HubUpdateController.startup = lambda self: None
    gui.HubWindow.scan_setup = lambda self, *a, **kw: None
    app = QApplication([sys.argv[0]])
    win = LauncherPreview()
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5A — GUIDED DOWNLOADS PREVIEW (ISOLATED)")
    # The installed app's version remains 0.5.4. Label only this isolated
    # Dev4 preview so screenshots cannot be mistaken for the released app.
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev5A · PREVIEW")
    # Use the real HubWindow desktop default, including the smaller-screen
    # fallback. Avoid overriding the very launch size under review.
    expected_open_size = (
        gui.preferred_launcher_size(
            app.primaryScreen().availableGeometry().width(),
            app.primaryScreen().availableGeometry().height())
        if app.primaryScreen() else (1630, 1060))
    win.tabs.setCurrentIndex(1)
    target = next(i for i, row in enumerate(win.rows)
                  if row["recipe"]["id"] == "cyberpunk-2077")
    win.sidebar.game_list.setCurrentRow(target)
    win.game_details_tabs.setCurrentIndex(4)
    win.show()
    win.disable_mutations()
    completed = [False]

    def verify():
        if completed[0] or not win.update_results.get("cyberpunk-2077"):
            return
        completed[0] = True
        win.sidebar.game_list.setCurrentRow(target)
        win.game_details_tabs.setCurrentIndex(4)
        app.processEvents()
        win.disable_mutations()
        summary = win.table.item(target, 4).text()
        components = win.rows[target]["components"]
        checks = {
            "opening_size_matches_screen_aware_default":
                (win.width(), win.height()) == expected_open_size,
            "nine_library_games": len(win.rows) == 9 and win.sidebar.game_list.count() == 9,
            "cyberpunk_selected": win.current()["id"] == "cyberpunk-2077",
            "correct_header": win.game_banner.heading.text() == "Cyberpunk 2077",
            "real_mod_status": (
                components is not None and
                f"{components[0]} / {components[1]}" in win.game_banner.status.text()),
            "updates_loaded": len(win.update_results["cyberpunk-2077"]) == 15,
            "yellow_brand": "#FFD21A" in win.styleSheet(),
            "blue_brand": "#23B7FF" in win.styleSheet(),
            "action_buttons_disabled": all(
                not getattr(win, x).isEnabled()
                for x in ("install_btn", "uninstall_btn", "hub_update_btn", "game_play_btn")),
            "game_nav_enabled": win.sidebar.games_button.isEnabled(),
            "future_nav_disabled": all(not b.isEnabled()
                                       for b in win.sidebar.planned_buttons.values()),
            "summary_in_table": summary == updates.summarize(
                win.update_results["cyberpunk-2077"]),
            "dashboard_four_cards": set(win.game_dashboard.cards) ==
                {"game", "mods", "updates", "vr"},
            "install_status_is_real": win.game_dashboard.cards["game"].value.text() ==
                ("Game detected" if win.rows[target]["game_found"] else "Not detected"),
            "mod_count_matches_existing_hub": win.game_dashboard.cards["mods"].value.text() ==
                f"{components[0]} / {components[1]} installed",
            "updates_card_matches_live_data": win.game_dashboard.cards["updates"].value.text() ==
                f"{sum(r['status']=='update' for r in win.update_results['cyberpunk-2077'])} updates",
            "vr_not_assumed_ready": win.game_dashboard.cards["vr"].value.text() == "Not run",
            "actual_hero_is_tall": win.game_banner.height() >= 140,
            "no_gameplay_claim": "VR Ready" not in win.game_banner.status.text(),
            "fourth_tab_is_native_updates":
                win.game_details_tabs.widget(3) is win.mod_updates,
            "updates_tab_retained_at_original_index":
                win.game_details_tabs.widget(3) is win.mod_updates,
            "setup_guide_compact":
                "See the Mod updates tab" in win.details.toPlainText()
                and "Cyber Engine Tweaks —" not in win.details.toPlainText(),
            "four_status_groups_populated":
                sum(x.table.rowCount() for x in win.mod_updates.sections.values()) == 15,
            "updates_rows_match_nexus":
                win.mod_updates.sections["update"].table.rowCount() ==
                    sum(x["status"] == "update" for x in win.update_results["cyberpunk-2077"]),
            "current_rows_collapsed_by_default":
                not win.mod_updates.sections["current"].table.isVisible(),
            "uncertain_rows_not_marked_current":
                all(x["status"] != "current" for x in win.update_results["cyberpunk-2077"]
                    if x["name"] in ("Visible Bullets (Projectile Restoration)",)),
            "tab_summary_matches_live":
                f"{sum(x['status']=='update' for x in win.update_results['cyberpunk-2077'])} updates available"
                    in win.mod_updates.summary.text(),
            "read_only_refresh_button":
                win.mod_updates.refresh_button.isEnabled(),
            "default_opening_size_retained":
                gui.preferred_launcher_size(2327, 1309) == (1630, 1060),
            "fifth_tab_guided_downloads":
                win.game_details_tabs.widget(4) is win.downloads,
            "downloads_tab_selected": win.game_details_tabs.currentIndex() == 4,
            "download_folder_isolated":
                str(gui.download_planner.preferences_file()).startswith(
                    str(Path(os.environ["VRHUB_STATE"]).parent.resolve())),
            "real_download_library_auto_discovered":
                "Archive-Library/VR-Mods" in win.downloads.location.text(),
            "cyberpunk_15_components_in_plan":
                win.downloads.table.rowCount() == 15,
            "stage2_not_silently_installed":
                "Later" in win.downloads.table.item(14, 1).text(),
            "all_library_columns_draggable":
                all(win.table.horizontalHeader().sectionResizeMode(j) ==
                    QHeaderView.Interactive for j in range(5)),
            "all_download_columns_draggable":
                all(win.downloads.table.horizontalHeader().sectionResizeMode(j) ==
                    QHeaderView.Interactive for j in range(5)),
            "all_mod_updates_columns_draggable":
                all(win.mod_updates.sections["update"].table.horizontalHeader()
                    .sectionResizeMode(j) == QHeaderView.Interactive for j in range(5)),
            "column_preference_state_isolated":
                str(table_columns.preferences_file()).startswith(
                    str(Path(os.environ["VRHUB_STATE"]).parent.resolve())),
            "custom_banner_button_available": win.change_banner_btn.isEnabled(),
            "artwork_choice_matches_game":
                win.artwork_label.text().endswith(win.game_banner.artwork_choice.source),
            "artwork_storage_is_test_scoped":
                str(gui.artwork.artwork_directory()).startswith(
                    str(Path(os.environ["XDG_DATA_HOME"]).resolve())),
        }
        if opts.verify:
            # Verify actual geometry, not just the ability to call resize().
            # Old Dev2 had a hard Qt minimum HEIGHT >1000px, so a bare
            # resize(1100, 700) call previously did not shrink its window.
            win.resize(920, 600)
            app.processEvents()
            checks["compact_actual_window_size"] = (win.width(), win.height()) == (920, 600)
            checks["compact_cards_two_columns"] = win.game_dashboard._columns == 2
            checks["compact_actions_two_columns"] = win.quick_actions._columns == 2
            checks["compact_vertical_scroll"] = win.game_page_scroll.verticalScrollBar().maximum() > 0
            checks["compact_no_horizontal_scroll"] = win.game_page_scroll.horizontalScrollBar().maximum() == 0
            checks["vr_system_button_visible"] = win.sidebar.system_button.isVisible()
            win.sidebar.system_button.click()
            checks["vr_system_navigation"] = win.tabs.currentIndex() == 0
            win.sidebar.games_button.click()
            checks["games_navigation"] = win.tabs.currentIndex() == 1

            win.resize(2200, 1200)
            app.processEvents()
            checks["maximized_content_width_capped"] = (
                win.game_page_scroll.widget().width() <= 1420
                and max(c.width() for c in win.game_dashboard.cards.values()) <= 360)
            # The simulated 800px offscreen Qt display can report a larger
            # minimum width after a fully populated Nexus update result.
            # Use a realistic restored width for the post-maximize check,
            # while testing actual screen-aware startup separately above.
            restored_target = (max(1120, expected_open_size[0]),
                               max(720, expected_open_size[1]))
            win.resize(*restored_target)
            app.processEvents()
            checks["restored_actual_window_size"] = (
                (win.width(), win.height()) == restored_target)
            # Offscreen Qt reports a tiny 800px simulated display. Save an
            # additional fixed-size full dashboard rendering for design QA.
            # Check Heroic art in the isolated preview, then show it to the
            # user instead of requiring any Steam/Heroic write.
            art_game = next(i for i, r in enumerate(win.rows)
                            if r["recipe"]["id"] == "hogwarts-legacy")
            win.sidebar.game_list.setCurrentRow(art_game)
            app.processEvents()
            # Read-only full archive scan uses the same native Qt worker.
            win.sidebar.game_list.setCurrentRow(target)
            win.game_details_tabs.setCurrentIndex(4)
            win.downloads.start_scan()
            runner = win.downloads.worker
            checks["local_scan_worker_completed"] = bool(
                runner and runner.wait(25000))
            app.processEvents()
            checks["real_archive_inventory_found"] = (
                win.downloads._last_plan is not None
                and win.downloads._last_plan["scanned"] >= 20)
            checks["cyberpunk_archives_not_falsely_verified"] = (
                win.downloads._last_plan is not None
                and win.downloads._last_plan["verified"] == 0
                and win.downloads._last_plan["possible"] >= 14)
            win.sidebar.game_list.setCurrentRow(art_game)
            app.processEvents()
            checks["heroic_art_auto_detected"] = (
                win.game_banner.artwork_choice.source == "Heroic local cover artwork"
                and not win.game_banner._local_art.isNull())
            checks["restore_disabled_without_custom"] = (
                not win.restore_banner_btn.isEnabled())
            win.resize(1630, 1060)
            win.sidebar.game_list.setCurrentRow(target)
            win.game_details_tabs.setCurrentIndex(4)
            win.library_toggle.setChecked(True)
            win.game_page_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            checks["library_game_column_balanced"] = (
                150 <= win.table.columnWidth(0) <= 780
                and win.table.columnWidth(0) < win.table.viewport().width() * .65)
            capture = Path.home() / ".cache/nannersvrhub-055-dev5-preview.png"
            table_capture = Path.home() / ".cache/nannersvrhub-055-dev5-plan-tab.png"
            checks["render_snapshot"] = bool(win.grab().save(str(capture), "PNG"))
            checks["render_native_tab"] = bool(
                win.downloads.grab().save(str(table_capture), "PNG"))
            print("SNAPSHOT", capture, flush=True)
            print("TAB_SNAPSHOT", table_capture, flush=True)
        for name, ok in checks.items():
            print("DEV5_CHECK", name, "PASS" if ok else "FAIL", flush=True)
        print("DEV5_GUI_RESULT", "PASS" if all(checks.values()) else "FAIL", flush=True)
        if opts.verify:
            QTimer.singleShot(800, lambda: app.exit(0 if all(checks.values()) else 1))
        else:
            # Open on Cyberpunk's fifteen-stage installation plan with the
            # detailed library table expanded for column drag acceptance.
            win.sidebar.game_list.setCurrentRow(target)
            win.game_details_tabs.setCurrentIndex(4)
            win.library_toggle.setChecked(True)
            win.game_page_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            win.disable_mutations()
            print(f"KDE GUIDED DOWNLOADS PREVIEW READY at {win.width()}x{win.height()}. "
                  "Downloads & install plan tab is selected. Use Scan local archives, "
                  "Set default folder, Set this game's folder and Use default. "
                  "Pinned SHA-256 matches are green; filename-only matches need inspection. "
                  "All settings saved only in private test data; downloads, installation, "
                  "game launches and rollback are disabled. Drag headers between "
                  "Game/Game install and other column names, or double-click to autofit. "
                  "Column widths remember your choices within this test preview.", flush=True)

    polling = QTimer()
    polling.timeout.connect(verify)
    polling.start(300)
    if opts.verify:
        QTimer.singleShot(60000, lambda: app.exit(2) if not completed[0] else None)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
