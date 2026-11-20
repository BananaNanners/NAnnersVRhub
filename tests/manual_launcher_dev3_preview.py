# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only KDE preview for Dev3's mod update dashboard.

Game installs, app updates, removals, launches and save recovery are DISABLED.
Uses VRHUB_STATE pointing at a private copy of production state.
--verify exercises real Qt navigation and saves a screenshot to a test path.
--desktop opens the preview for human layout acceptance.
"""
import argparse
import os
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QLabel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vrhub import gui, hub, updates
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
        }
        for button in self.findChildren(QPushButton):
            if button not in allow and button.objectName() != "modSourceButton":
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
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev3 — MOD UPDATES PREVIEW (READ ONLY)")
    # The installed app's version remains 0.5.4. Label only this isolated
    # Dev2 preview so screenshots cannot be mistaken for the released app.
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev3 · PREVIEW")
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
    win.game_details_tabs.setCurrentIndex(3)
    win.show()
    win.disable_mutations()
    completed = [False]

    def verify():
        if completed[0] or not win.update_results.get("cyberpunk-2077"):
            return
        completed[0] = True
        win.sidebar.game_list.setCurrentRow(target)
        win.game_details_tabs.setCurrentIndex(3)
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
            "updates_tab_is_selected": win.game_details_tabs.currentIndex() == 3,
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
            win.resize(1630, 1060)
            win.game_details_tabs.setCurrentIndex(3)
            win.game_page_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            capture = Path.home() / ".cache/nannersvrhub-055-dev3-preview.png"
            table_capture = Path.home() / ".cache/nannersvrhub-055-dev3-mod-tab.png"
            checks["render_snapshot"] = bool(win.grab().save(str(capture), "PNG"))
            checks["render_native_tab"] = bool(
                win.mod_updates.grab().save(str(table_capture), "PNG"))
            print("SNAPSHOT", capture, flush=True)
            print("TAB_SNAPSHOT", table_capture, flush=True)
        for name, ok in checks.items():
            print("DEV3_CHECK", name, "PASS" if ok else "FAIL", flush=True)
        print("DEV3_GUI_RESULT", "PASS" if all(checks.values()) else "FAIL", flush=True)
        if opts.verify:
            QTimer.singleShot(800, lambda: app.exit(0 if all(checks.values()) else 1))
        else:
            print(f"KDE MOD UPDATES PREVIEW READY at {win.width()}x{win.height()}. "
                  "The Mod updates tab is selected. Expand Up to date, select other games "
                  "and use Refresh update status (read-only). The source buttons open "
                  "external release pages; no game files will change. Close when finished.", flush=True)

    polling = QTimer()
    polling.timeout.connect(verify)
    polling.start(300)
    if opts.verify:
        QTimer.singleShot(60000, lambda: app.exit(2) if not completed[0] else None)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
