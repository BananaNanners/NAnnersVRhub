# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D2 KDE preview: archive-first installation review (read-only).

Live game installs, downloads, updates, launch and recovery are DISABLED.
--desktop uses one persistent, isolated development preview store, restores
the previously saved per-game scans and remains independent of production.
--verify uses only its caller-supplied throwaway test copy.
"""
import argparse
import os
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QHeaderView

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Configure the shared private preview store BEFORE importing the Hub GUI.
# This applies ONLY to --desktop. Automated --verify tests must never
# update the human preview's saved scan timestamps or folder preferences.
if "--desktop" in sys.argv:
    from vrhub import dev_preview_storage
    try:
        persistence = dev_preview_storage.activate_desktop_preview()
    except dev_preview_storage.PreviewStorageError as exc:
        raise SystemExit(f"Preview storage migration stopped safely: {exc}")
    print(
        "STABLE DEV PREVIEW STORAGE:", persistence["root"],
        "| previously saved game scans:", persistence["count"],
        "| restored this launch:", persistence["imported"],
        "| earlier development sources:", persistence["source_count"],
        flush=True)

from vrhub import gui, hub, updates, table_columns, archive_scans, install_review
from vrhub.downloads_gui import GuidedDownloadsPage
from vrhub.install_review_gui import InstallReviewDialog
from vrhub.profile_review_gui import ProfileReviewDialog
from vrhub.profile_safety import ProfilePlan
from vrhub.app_update_gui import HubUpdateController


class LauncherPreview(gui.HubWindow):
    def install_profile(self):
        """Read-only archive and destination review; apply is NEVER enabled."""
        from PySide6.QtWidgets import QMessageBox
        recipe = self.current()
        if not recipe or "profile" not in recipe:
            return
        path = self._pick("Read-only UEVR profile ZIP review")
        if not path:
            return
        try:
            plan = hub.review_profile_install(recipe, path, gui._roots())
        except (RuntimeError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "UEVR profile review", str(exc))
            return
        dialog = ProfileReviewDialog(plan, self, allow_install=False)
        dialog.exec()

    def show_details(self):
        super().show_details()
        self.disable_mutations()

    def disable_mutations(self):
        allow = {
            self.sidebar.games_button,
            self.sidebar.system_button,
            self.library_toggle,
            self.more_tools_toggle,
            self.install_tools_toggle,
            self.update_tools_toggle,
            self.downloads.folder_menu_button,
            self.sidebar.future_toggle,
            self.check_btn,
            self.mod_updates.refresh_button,
            self.change_banner_btn,
            self.restore_banner_btn,
            self.downloads.set_global, self.downloads.set_game,
            self.downloads.clear_game, self.downloads.reset_global,
            self.downloads.scan, self.downloads.inspect,
            self.downloads.install_review_button,
            self.profile_btn,
        }
        # The test window may preview all manifests but is never permitted to
        # download, install, remove or modify a live game or its mods/saves.
        self.allow_guided_installs = False
        self.downloads.allow_transfers = False
        for button in self.findChildren(QPushButton):
            if button not in allow and button.objectName() not in ("modSourceButton", "downloadsSourceButton"):
                button.setEnabled(False)
        self.downloads.download_button.setEnabled(False)
        self.downloads.download_cancel.setEnabled(False)
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
    win.allow_guided_installs = False
    win.downloads.allow_transfers = False
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D2d Game Actions — ARCHIVE-FIRST PREVIEW (NO GAME WRITES)")
    # The installed app's version remains 0.5.4. Label only this isolated
    # Dev4 preview so screenshots cannot be mistaken for the released app.
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev5D2d · PREVIEW")
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
    win.game_details_tabs.setCurrentIndex(2)
    win.show()
    win.disable_mutations()
    completed = [False]

    def verify():
        if completed[0] or not win.update_results.get("cyberpunk-2077"):
            return
        completed[0] = True
        win.sidebar.game_list.setCurrentRow(target)
        win.game_details_tabs.setCurrentIndex(2)
        app.processEvents()
        win.disable_mutations()
        summary = win.table.item(target, 4).text()
        components = win.rows[target]["components"]
        checks = {
            "opening_size_close_to_screen_aware_default":
                abs(win.width() - expected_open_size[0]) <= 2
                and abs(win.height() - expected_open_size[1]) <= 2,
            "overview_has_only_launch_and_preflight": (
                win.quick_actions.buttons ==
                    (win.game_play_btn, win.preflight_btn)
                and win.check_btn not in win.quick_actions.buttons
                and win.install_btn not in win.quick_actions.buttons),
            "only_one_refresh_update_control": (
                win.check_btn is win.mod_updates.refresh_button
                and len([btn for btn in win.findChildren(QPushButton)
                         if btn.text() == "Refresh update status"]) == 1),
            "installer_buttons_scoped_to_install_tab": (
                win.install_tools_panel.parent() is win.downloads
                and win.profile_btn.parent() is win.install_tools_panel
                and win.verify_btn.parent() is win.install_tools_panel),
            "update_tools_scoped_to_updates_tab": (
                win.update_tools_panel.parent() is win.mod_updates
                and win.key_btn.parent() is win.update_tools_panel),
            "compatibility_tools_scoped_to_compatibility": (
                win.more_tools_panel.parent() is win.compat_page
                and win.log_diagnostics_btn.parent() is win.more_tools_panel),
            "rollback_guards_and_dev_saves_relocated": (
                win.uninstall_btn.parent() is win.rollback_page
                and win.unprofile_btn.parent() is win.rollback_page
                and win.doom_saves_btn.parent() is win.rollback_page),
            "folder_menu_plus_scan_is_only_primary_folder_row": (
                win.downloads.action_toolbar.buttons ==
                    (win.downloads.folder_menu_button, win.downloads.scan)
                and len(win.downloads.folder_menu_actions) == 4),
            "full_folder_behavior_remains_available_in_menu": (
                [btn.text() for btn in win.downloads.folder_menu_actions] ==
                ["Choose game folder", "Choose default folder",
                 "Use default folder", "Auto-detect default"]),
            "seven_game_nav_tabs": (
                win.game_details_tabs.count() == 7
                and win.game_details_tabs.tabText(1).split(" (", 1)[0] == "Updates"
                and [win.game_details_tabs.tabText(i) for i in (0, 2, 3, 4, 5, 6)]
                    == ["Overview", "Install / Update", "Rollback",
                        "Compatibility", "Controller Bindings", "Setup Guide"]),
            "all_seven_icons_visible": all(
                not win.game_details_tabs.tabIcon(i).isNull()
                for i in range(win.game_details_tabs.count())),
            "selected_yellow_and_blue_hover": (
                "QTabWidget#gameDetailsTabs" in win.styleSheet()
                and "background: #FFD21A" in win.styleSheet()
                and "color: #23B7FF" in win.styleSheet()),
            "overflow_navigation_scrollable": (
                win.game_details_tabs.tabBar().usesScrollButtons()
                and not win.game_details_tabs.tabBar().expanding()),
            "overview_owns_original_dashboard": (
                win.game_dashboard.parent() is win.overview_page
                and win.quick_actions.parent() is win.overview_page),
            "rollback_owns_existing_guards": (
                win.uninstall_btn.parent() is win.rollback_page
                and win.unprofile_btn.parent() is win.rollback_page
                and not win.uninstall_btn.isEnabled()
                and not win.unprofile_btn.isEnabled()),
            "compatibility_same_original_report_page": (
                win.game_details_tabs.widget(4) is win.compat_page
                and win.compat_details.toPlainText()
                and "Gameplay evidence" in win.compat_details.toPlainText()),
            "controller_original_widget_retained": (
                win.game_details_tabs.widget(5) is win.controller_bindings),
            "setup_guide_original_widget_retained": (
                win.game_details_tabs.widget(6) is win.details),
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
                gui.dashboard_snapshot(
                    win.rows[target], win.update_results["cyberpunk-2077"])["updates"][1],
            "vr_not_assumed_ready": win.game_dashboard.cards["vr"].value.text() == "Not run",
            "actual_hero_is_tall": win.game_banner.height() >= 140,
            "no_gameplay_claim": "VR Ready" not in win.game_banner.status.text(),
            "fourth_tab_is_native_updates":
                win.game_details_tabs.widget(1) is win.mod_updates,
            "updates_tab_retained_at_original_index":
                win.game_details_tabs.widget(1) is win.mod_updates,
            "setup_guide_compact":
                "See the Updates tab" in win.details.toPlainText()
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
                win.game_details_tabs.widget(2) is win.downloads,
            "downloads_tab_selected": win.game_details_tabs.currentIndex() == 2,
            "verified_download_controls_present": (
                win.downloads.download_button.text() == "Download and verify"
                and win.downloads.download_cancel.text() == "Cancel download"),
            "guided_review_button_present": (
                win.downloads.install_review_button.text() == "Review installation"),
            "persistent_backup_notice_shows_record_safety":
                bool(win.downloads.backup_safety_status.text()),
            "legacy_cyberpunk_has_no_false_restore_claim": (
                ("LEGACY CYBERPUNK INSTALLATION" in
                 win.downloads.backup_safety_status.text())
                if hub.state().get("cyberpunk-2077", {}).get("installer") != "gameroot-2"
                and "cyberpunk-2077" in hub.state() else True),
            "no_cyberpunk_install_authorized_in_preview":
                not win.allow_guided_installs,
            "guided_review_safe_in_preview": (
                win.downloads.install_review_button.isEnabled()
                and not win.allow_guided_installs),
            "guided_review_tooltip_read_only": (
                "Nothing changes without confirmation"
                in win.downloads.install_review_button.toolTip()),
            "archive_first_column_order": (
                [win.downloads.table.horizontalHeader().logicalIndex(i)
                 for i in range(5)] == [2,0,3,1,4]),
            "archive_inspector_is_advanced": (
                win.downloads.inspect.parent() is win.install_tools_panel
                and not win.downloads.inspect.isVisible()),
            "legacy_install_button_now_says_review":
                win.install_btn.text() == "Review mod archives",
            "uevr_profile_install_has_safety_hold":
                win.profile_btn.text() == "Review UEVR profile…",
            "installed_profile_button_remains_disabled": (
                not win.profile_btn.isEnabled()),
            "preview_network_permissions_disabled": (
                not win.downloads.allow_transfers
                and not win.downloads.download_button.isEnabled()
                and not win.downloads.download_cancel.isEnabled()
                and win.downloads.download_worker is None),
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
            win.game_details_tabs.setCurrentIndex(0)
            app.processEvents()
            checks["compact_actual_window_size"] = (win.width(), win.height()) == (920, 600)
            checks["compact_cards_two_columns"] = win.game_dashboard._columns == 2
            checks["compact_actions_two_columns"] = win.quick_actions._columns == 2
            checks["compact_vertical_scroll"] = win.game_page_scroll.verticalScrollBar().maximum() > 0
            checks["compact_no_horizontal_scroll"] = win.game_page_scroll.horizontalScrollBar().maximum() == 0
            checks["tab_overflow_accessible_at_compact_width"] = (
                win.game_details_tabs.tabBar().usesScrollButtons()
                and win.game_details_tabs.tabBar().minimumSizeHint().width() <=
                    win.game_details_tabs.width()
                and win.game_details_tabs.count() == 7)
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
            win.game_details_tabs.setCurrentIndex(2)
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
            checks["cyberpunk_scan_writes_only_private_hub_snapshot"] = (
                "cyberpunk-2077" in archive_scans.load_saved()
                and str(archive_scans.snapshot_file()).startswith(
                    str(Path(os.environ["VRHUB_STATE"]).parent.resolve())))
            checks["scan_timestamp_is_visible"] = (
                "Saved scan:" in win.downloads.scan_age.text()
                and "Historical snapshot" in win.downloads.scan_age.text())

            # Check two distinct pinned-hash profiles, then return to
            # Cyberpunk. None of the results may be forgotten or overwritten.
            for game_id, expected_hashes in (("valheim", 2), ("subnautica", 2)):
                index = next(i for i, row in enumerate(win.rows)
                             if row["recipe"]["id"] == game_id)
                win.sidebar.game_list.setCurrentRow(index)
                win.downloads.start_scan()
                scan_thread = win.downloads.worker
                finished = bool(scan_thread and scan_thread.wait(25000))
                app.processEvents()
                checks[f"{game_id}_scan_completed"] = finished
                checks[f"{game_id}_pinned_hashes_saved"] = (
                    win.downloads._last_plan is not None
                    and win.downloads._last_plan["verified"] == expected_hashes
                    and "Saved scan:" in win.downloads.scan_age.text())

            win.sidebar.game_list.setCurrentRow(target)
            app.processEvents()
            from vrhub import verified_download
            checks["nexus_packages_manual_only"] = not any(
                verified_download.source_support(win.current(), c)[0]
                for c in gui.download_planner.plan_components(win.current()))
            checks["cyberpunk_15_rows_restored_without_rescan"] = (
                win.downloads._last_plan is not None
                and win.downloads._last_plan["possible"] >= 14
                and win.downloads.table.rowCount() == 15
                and "Saved scan:" in win.downloads.scan_age.text())
            win.sidebar.game_list.setCurrentRow(
                next(i for i, row in enumerate(win.rows)
                     if row["recipe"]["id"] == "valheim"))
            app.processEvents()
            checks["valheim_two_verified_restored_after_switch"] = (
                win.downloads._last_plan is not None
                and win.downloads._last_plan["verified"] == 2)
            valheim_recipe = win.current()
            valheim_parts = gui.download_planner.plan_components(valheim_recipe)
            checks["pinned_valheim_sources_supported"] = all(
                verified_download.source_support(valheim_recipe, c)[0]
                for c in valheim_parts)
            win.downloads.table.selectRow(1)
            app.processEvents()
            checks["even_pinned_transfer_disabled_in_preview"] = (
                not win.downloads.download_button.isEnabled()
                and not win.downloads.allow_transfers)
            win.sidebar.game_list.setCurrentRow(
                next(i for i, row in enumerate(win.rows)
                     if row["recipe"]["id"] == "subnautica"))
            app.processEvents()
            checks["subnautica_two_verified_restored_after_switch"] = (
                win.downloads._last_plan is not None
                and win.downloads._last_plan["verified"] == 2)
            checks["three_distinct_saved_profiles"] = (
                {"cyberpunk-2077", "valheim", "subnautica"}
                <= set(archive_scans.load_saved()))
            # A synthetic plan exercises the actual QDialog UI in the
            # isolated, network-disabled preview without inspecting or
            # modifying ANY user game. Its target path is a label, not a file.
            demo_target = install_review.Target(
                "BepInEx/plugins/VRSample.dll",
                "/sample/game/BepInEx/plugins/VRSample.dll",
                "Replace; back up original", 18_600_000,
                "d" * 64, 1, 1, 1)
            demo = install_review.InstallPlan(
                "demo", "Demo only — NO GAME FILES", "bepinex",
                "/sample/game", ("/sample/archives/demo.zip",),
                ("a" * 64,), ("Demo pinned archive",),
                (demo_target,), 0, 1, 18_600_000,
                "Persistent Hub-managed originals; checksum-protected restoration",
                (), ("The preview cannot install any mod.",), "f" * 64)
            dlg = InstallReviewDialog(demo, win, allow_install=False)
            dlg.show()
            app.processEvents()
            checks["preview_review_dialog_shows_exact_files"] = (
                dlg.targets.item(0, 0).text() == demo_target.relative
                and "Demo" in dlg.notes.toPlainText())
            checks["review_sizes_use_human_readable_mb"] = (
                dlg.targets.item(0, 2).text() == "18.6 MB"
                and "18.6 MB" in dlg.notes.toPlainText()
                and "18,600,000 bytes" in dlg.targets.item(0, 2).toolTip()
                and "18,600,000 bytes" in dlg.findChild(
                    QLabel, "installReviewOverview").toolTip())
            checks["review_archive_summary_visible"] = (
                dlg.archives.isVisible() and dlg.archives.rowCount() == 1
                and dlg.archives.item(0,0).text() == "demo.zip"
                and not dlg.targets.isVisible()
                and dlg.confirm_targets.isEnabled()
                and dlg.archives.item(0,1).text() == 'Demo pinned archive')
            dlg.grab().save(
                str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-archive-review.png"), "PNG")
            dlg.manifest_toggle.setChecked(True)
            app.processEvents()
            checks["review_exact_manifest_expandable"] = (
                dlg.targets.isVisible() and dlg.targets.rowCount() == len(demo.target_rows)
                and dlg.confirm_targets.isEnabled())
            for box in (dlg.confirm_targets, dlg.confirm_backup, dlg.confirm_closed):
                box.setChecked(True)
            checks["review_install_always_blocked_in_preview"] = (
                not dlg.apply_button.isEnabled()
                and not dlg.confirmed_by_user)
            dlg.grab().save(
                str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-review-dialog.png"),
                "PNG")
            dlg.close()
            dlg.deleteLater()
            # Profile-specific dialogs are synthetic; no user game is involved.
            sample = ProfilePlan(
                "fatekeeper", "Demo only — not a real game",
                "/sample/archive/profile.zip", "a" * 64,
                "/sample/ProtonPrefix/UnrealVRMod/Sample",
                ("config.txt", "plugins/sample.dll"),
                2, 3_750_000, 3, 54_483_692, 1, True, (), "b" * 64)
            profdlg = ProfileReviewDialog(sample, win, allow_install=False)
            profdlg.show()
            app.processEvents()
            checks["uevr_profile_read_only_handler_active"] = (
                LauncherPreview.install_profile is not gui.HubWindow.install_profile)
            checks["uevr_review_exact_destination_visible"] = (
                profdlg.table.item(0, 0).text() == "config.txt"
                and sample.destination in profdlg.findChildren(QLabel)[2].text())
            from PySide6.QtWidgets import QLabel as GuiLabel
            uevr_overview = profdlg.findChild(GuiLabel, "uevrProfileReviewOverview")
            checks["uevr_review_human_readable_size"] = bool(
                uevr_overview
                and "3.75 MB" in uevr_overview.text()
                and "54.48 MB" in uevr_overview.text()
                and "3,750,000 bytes" in uevr_overview.toolTip()
                and "54,483,692 bytes" in uevr_overview.toolTip())
            checks["uevr_review_full_directory_policy_visible"] = (
                "whole-directory" in profdlg.backup.text()
                and "SHA-256" in profdlg.backup.text())
            checks["uevr_review_starts_archive_first"] = (
                not profdlg.table.isVisible() and profdlg.ack.isEnabled()
                and profdlg.archives.item(0,1).text() == 'Matching game profile')
            profdlg.grab().save(
                str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-profile-archive-review.png"), "PNG")
            profdlg.manifest_toggle.setChecked(True)
            app.processEvents()
            checks["uevr_complete_inventory_expandable"] = (
                profdlg.table.isVisible() and profdlg.table.rowCount() == len(sample.file_names)
                and profdlg.ack.isEnabled())
            profdlg.ack.setChecked(True)
            checks["uevr_preview_never_allows_profile_install"] = (
                not profdlg.apply_btn.isEnabled() and not profdlg.confirmed_by_user)
            checks["uevr_review_renders"] = bool(profdlg.grab().save(
                str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-profile-review.png"), "PNG"))
            profdlg.close()
            blocked = ProfilePlan(
                sample.game_id, sample.game_name, sample.archive, sample.archive_sha256,
                sample.destination, sample.file_names, sample.profile_files, sample.profile_bytes,
                sample.existing_files, sample.existing_bytes, sample.existing_dirs,
                sample.previous_exists,
                ("Legacy Hub record requires manual recovery review.",), sample.fingerprint)
            blocked_dlg = ProfileReviewDialog(blocked, win, allow_install=False)
            blocked_dlg.ack.setChecked(True)
            checks["uevr_legacy_warning_blocked"] = (
                "BLOCKED" in blocked_dlg.status.text() and not blocked_dlg.apply_btn.isEnabled())
            blocked_dlg.close()
            checks["buttons_use_clear_labels_without_ellipses"] = (
                [x.text() for x in (
                    win.downloads.set_global, win.downloads.set_game,
                    win.downloads.clear_game, win.downloads.reset_global,
                    win.downloads.scan)] == [
                    "Choose default folder", "Choose game folder",
                    "Use default folder", "Auto-detect default",
                    "Scan local archives"])
            checks["hover_help_disambiguates_folder_reset_from_scan_reset"] = (
                "SHARED folder" in win.downloads.reset_global.toolTip()
                and "Other games" in win.downloads.set_game.toolTip()
                and "No archives" in win.downloads.scan.toolTip())
            checks["hover_descriptions_are_compact_multiline"] = all(
                2 <= len(btn.toolTip().splitlines()) <= 3 and
                max(len(line) for line in btn.toolTip().splitlines()) <= 58
                for btn in (win.downloads.set_global, win.downloads.set_game,
                            win.downloads.clear_game, win.downloads.reset_global,
                            win.downloads.scan, win.downloads.inspect))
            checks["default_and_override_are_visible_separately"] = (
                "Current game folder" in win.downloads.location.text()
                and "Shared default" in win.downloads.location.text())

            # New page simulates reopening the application. Its view comes
            # from the isolated on-disk scan snapshot, not the old QWidget.
            fresh_page = GuidedDownloadsPage()
            fresh_page.set_recipe(hub.load_recipes()["valheim"])
            checks["reopen_restores_valheim_from_disk"] = (
                fresh_page._last_plan is not None
                and fresh_page._last_plan["verified"] == 2
                and "Saved scan:" in fresh_page.scan_age.text())
            fresh_page.close()
            fresh_page.deleteLater()

            win.sidebar.game_list.setCurrentRow(art_game)
            app.processEvents()
            checks["heroic_art_auto_detected"] = (
                win.game_banner.artwork_choice.source == "Heroic local cover artwork"
                and not win.game_banner._local_art.isNull())
            checks["restore_disabled_without_custom"] = (
                not win.restore_banner_btn.isEnabled())
            win.resize(1630, 1060)
            win.sidebar.game_list.setCurrentRow(target)
            win.game_details_tabs.setCurrentIndex(2)
            win.game_details_tabs.setCurrentIndex(0)
            win.library_toggle.setChecked(True)
            win.game_page_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            checks["library_game_column_balanced"] = (
                150 <= win.table.columnWidth(0) <= 780
                and win.table.columnWidth(0) < win.table.viewport().width() * .65)
            capture = Path.home() / ".cache/nannersvrhub-055-dev5d2d-preview.png"
            table_capture = Path.home() / ".cache/nannersvrhub-055-dev5d2d-plan-tab.png"
            checks["render_snapshot"] = bool(win.grab().save(str(capture), "PNG"))
            win.game_details_tabs.setCurrentIndex(2)
            app.processEvents()
            checks["render_native_tab"] = bool(
                win.downloads.grab().save(str(table_capture), "PNG"))
            win.game_details_tabs.setCurrentIndex(0)
            win.library_toggle.setChecked(False)
            app.processEvents()
            nav_capture = Path.home() / ".cache/nannersvrhub-055-dev5d2d-navigation.png"
            checks["render_navigation_overview"] = bool(
                win.grab().save(str(nav_capture), "PNG"))
            print("NAV_SNAPSHOT", nav_capture, flush=True)
            for tab_id, tab_key, toggler in (
                (1, "updates", win.update_tools_toggle),
                (2, "installation", win.install_tools_toggle),
                (3, "rollback", None),
                (4, "compatibility", win.more_tools_toggle),
            ):
                win.game_details_tabs.setCurrentIndex(tab_id)
                if toggler is not None:
                    toggler.setChecked(True)
                app.processEvents()
                filename = Path.home() / (
                    f".cache/nannersvrhub-055-dev5d2d-{tab_key}.png")
                checks[f"render_consolidated_{tab_key}"] = bool(
                    win.grab().save(str(filename), "PNG"))
                if toggler is not None:
                    toggler.setChecked(False)
            win.game_details_tabs.setCurrentIndex(0)
            app.processEvents()
            print("NAV_SNAPSHOT", nav_capture, flush=True)
            print("SNAPSHOT", capture, flush=True)
            print("TAB_SNAPSHOT", table_capture, flush=True)
        # New read-only acceptance checks: the existing actions moved, but
        # none can launch an actual game or injector in the preview.
        checks["launch_tools_own_original_buttons"] = (
            win.launch_tools_panel.parent() is win.overview_page
            and win.copy_btn.parent() is win.launch_tools_panel
            and win.inject_btn.parent() is win.launch_tools_panel
            and win.game_launch_btn.parent() is win.launch_tools_panel
            and win.doom_probe_btn.parent() is win.launch_tools_panel
            and win.launch_tools_panel.maximumWidth() <= 760)
        checks["compatibility_keeps_diagnostics_not_launch_tools"] = (
            win.log_diagnostics_btn.parent() is win.more_tools_panel
            and win.support_report_btn.parent() is win.more_tools_panel
            and win.copy_btn not in win.more_tools_panel.findChildren(QPushButton)
            and win.inject_btn not in win.more_tools_panel.findChildren(QPushButton)
            and win.game_launch_btn not in win.more_tools_panel.findChildren(QPushButton)
            and win.doom_probe_btn not in win.more_tools_panel.findChildren(QPushButton)
            and win.bridge_log_btn.parent() is win.more_tools_panel
            and win.doom_logs_btn.parent() is win.more_tools_panel)
        def review_launch_actions(game_id, expected_copy, expected_inject,
                                  expected_launcher, expected_probe, suffix):
            row = next(i for i, item in enumerate(win.rows)
                       if item["recipe"]["id"] == game_id)
            win.sidebar.game_list.setCurrentRow(row)
            win.game_details_tabs.setCurrentIndex(0)
            win.library_toggle.setChecked(False)
            app.processEvents()
            win.disable_mutations()
            expected_any = any((expected_copy, expected_inject,
                                expected_launcher, expected_probe))
            checks[f"{suffix}_launch_actions_visibility"] = (
                win.copy_btn.isVisible() is expected_copy
                and win.inject_btn.isVisible() is expected_inject
                and win.game_launch_btn.isVisible() is expected_launcher
                and win.doom_probe_btn.isVisible() is expected_probe
                and win.launch_tools_panel.isVisible() is expected_any)
            checks[f"{suffix}_launch_safety_gate"] = all(
                not control.isEnabled() for control in (
                    win.copy_btn, win.inject_btn,
                    win.game_launch_btn, win.doom_probe_btn))
            shot = Path.home() / f".cache/nannersvrhub-055-dev5d2d-{suffix}.png"
            checks[f"{suffix}_screenshot"] = bool(win.grab().save(str(shot), "PNG"))
            print("GAME_ACTIONS_SNAPSHOT", suffix, shot, flush=True)
            return win.current()

        review_launch_actions("fatekeeper", True, True, False, False, "fatekeeper")
        review_launch_actions("hogwarts-legacy", False, True, False, False, "hogwarts")
        review_launch_actions("cyberpunk-2077", True, False, False, False, "cyberpunk")
        review_launch_actions("skyrim-vr-mgo", True, False, True, False, "skyrim")
        checks["skyrim_launch_labels"] = (
            win.game_play_btn.text() == "Launch Skyrim VR"
            and win.game_launch_btn.text() == "Launch MO2"
            and win.bridge_log_btn.text() == "Open MO2 bridge log")
        review_launch_actions("doom-2016-gog", False, False, True, True, "doom")
        checks["doom_launch_labels"] = (
            win.game_play_btn.text() == "Launch DOOM (flat)"
            and win.game_launch_btn.text() == "Launch DOOM VR"
            and win.doom_probe_btn.text() == "Test VR bridge"
            and win.bridge_log_btn.text() == "Open KHARVOX log")
        checks["doom_log_is_compatibility_tool"] = (
            win.bridge_log_btn.parent() is win.more_tools_panel
            and win.doom_logs_btn.parent() is win.more_tools_panel)
        # The desktop preview will open on DOOM because that was the missing
        # game-specific pair reported by the user.
        review_launch_actions("doom-2016-gog", False, False, True, True, "desktop")

        # Dev5D1-C exclusively tests visual presentation; no game mutations.
        from PySide6.QtCore import QSize as IconSize
        from PySide6.QtGui import QColor as IconColor
        from vrhub import theme as colors

        checks["visual_brand_palette_exact"] = (
            colors.YELLOW == "#FFD21A"
            and colors.BLUE == "#23B7FF"
            and colors.BG == "#0A0D10")
        css = win.styleSheet()
        checks["visual_disclosure_styles"] = (
            "QPushButton#launcherDisclosure:checked" in css
            and "QPushButton#launcherDisclosure:hover" in css
            and "font-size: 12px" in css)
        checks["visual_secondary_launch_presentation"] = (
            win.launch_tools_panel.objectName() == "overviewLaunchTools"
            and "QWidget#overviewLaunchTools" in css
            and "QPushButton#overviewSecondaryLaunch:hover" in css
            and all(button.objectName() == "overviewSecondaryLaunch"
                    for button in (win.copy_btn, win.inject_btn,
                                   win.doom_probe_btn)))
        checks["visual_compatibility_margins"] = (
            win.compat_page.layout().contentsMargins().left() == 12
            and win.compat_page.layout().contentsMargins().top() == 12)
        checks["visual_tab_icons_original_shapes"] = (
            len(win._game_tab_original_icons) == 7
            and all(not icon.isNull()
                    for icon in win._game_tab_original_icons))

        def tab_color_is(index, expected):
            pix = win.game_details_tabs.tabIcon(index).pixmap(
                IconSize(18, 18)).toImage()
            target = IconColor(expected)
            pixels = [pix.pixelColor(x, y) for x in range(pix.width())
                      for y in range(pix.height())
                      if pix.pixelColor(x, y).alpha() >= 200]
            return len(pixels) >= 7 and all(
                abs(actual - goal) <= 2 for c in pixels for actual, goal in zip(
                    (c.red(), c.green(), c.blue()),
                    (target.red(), target.green(), target.blue())))

        win.game_details_tabs.setCurrentIndex(0)
        app.processEvents()
        checks["visual_selected_icon_dark_on_yellow"] = (
            tab_color_is(0, colors.BG)
            and all(tab_color_is(i, colors.MUTED) for i in range(1,7)))
        win.game_details_tabs.setCurrentIndex(4)
        app.processEvents()
        checks["visual_switch_recolors_icons"] = (
            tab_color_is(4, colors.BG)
            and tab_color_is(0, colors.MUTED))
        win.game_details_tabs.setCurrentIndex(0)
        win.resize(920, 600)
        app.processEvents()
        checks["visual_narrow_no_horizontal_page_scroll"] = (
            win.game_page_scroll.horizontalScrollBar().maximum() == 0
            and win.game_details_tabs.tabBar().usesScrollButtons())
        win.resize(*expected_open_size)
        app.processEvents()
        for tab_index, name in enumerate(
            ("overview", "updates", "install", "rollback",
             "compatibility", "controllers", "guide")):
            win.game_details_tabs.setCurrentIndex(tab_index)
            app.processEvents()
            shot = Path.home() / (
                f".cache/nannersvrhub-055-dev5d2d-tab-{name}.png")
            checks[f"visual_screenshot_{name}"] = bool(
                win.grab().save(str(shot), "PNG"))
            print("POLISH_TAB_SNAPSHOT", name, shot, flush=True)
        win.game_details_tabs.setCurrentIndex(0)
        app.processEvents()
        win.resize(1630, 1060)
        app.processEvents()
        for rid in ("cyberpunk-2077", "subnautica", "fatekeeper"):
            row = next(i for i, item in enumerate(win.rows)
                       if item["recipe"]["id"] == rid)
            win.sidebar.game_list.setCurrentRow(row)
            win.game_details_tabs.setCurrentIndex(2)
            win.install_tools_toggle.setChecked(False)
            app.processEvents()
            cells = [win.downloads.table.item(i,3)
                     for i in range(win.downloads.table.rowCount())]
            checks[f"{rid}_status_icons_visible"] = bool(cells) and all(
                c is not None and not c.icon().isNull() for c in cells)
            checks[f"{rid}_archive_first_header_preserved"] = (
                win.downloads.table.horizontalHeader().logicalIndex(0) == 2)
            checks[f"{rid}_archive_checklist_screenshot"] = bool(win.grab().save(
                str(Path.home() / f".cache/nannersvrhub-055-dev5d2d-checklist-{rid}.png"), "PNG"))
            if rid == "subnautica" and win.downloads._last_plan and win.downloads._last_plan["verified"] == 2:
                checks["complete_pinned_set_review_label"] = (
                    win.downloads.install_review_button.text() == "Review 2 verified archives")
            if rid == "cyberpunk-2077":
                checks["unpinned_review_label_not_verified"] = (
                    win.downloads.install_review_button.text() == "Review installation")
        win.sidebar.game_list.setCurrentRow(next(
            i for i, row in enumerate(win.rows) if row["recipe"]["id"] == "fatekeeper"))
        win.game_details_tabs.setCurrentIndex(6)
        app.processEvents()
        guide = win.details.toHtml()
        source = "https://github.com/jbusfield/FK_UEVR/releases"
        mod = source + "/tag/1.0.0"
        profile = source + "/tag/v1.0.4"
        checks["fatekeeper_guide_separates_mod_profile_sources"] = all(
            part in guide for part in (mod, profile, "UEVR FK Mod", "Fatekeeper VR Profile"))
        checks["fatekeeper_guide_only_requested_sources"] = (
            "praydog/UEVR-nightly" not in guide and "joeyhodge/UEVR/releases" not in guide
            and "/releases/download/" not in guide and guide.count(source) == 2)
        win.grab().save(str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-fk-guide.png"), "PNG")
        win.game_details_tabs.setCurrentIndex(2)
        app.processEvents()
        checks["fatekeeper_archive_display_sources"] = (
            win.downloads.table.item(0,0).text() == "UEVR FK — Mod / injector"
            and win.downloads.table.item(1,0).text() == "Fatekeeper — VR profile"
            and mod in win.downloads.table.cellWidget(0,4).toolTip()
            and profile in win.downloads.table.cellWidget(1,4).toolTip()
            and win.downloads.upstream_link.isHidden())
        win.grab().save(str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-fk-install.png"), "PNG")
        win.game_details_tabs.setCurrentIndex(1)
        app.processEvents()
        rows = win.update_results.get("fatekeeper", [])
        checks["fatekeeper_two_independent_update_entries"] = (
            len(rows) == 2 and rows[0]["name"] == "UEVR_FK.zip"
            and rows[1]["name"] == "SLASHER-Win64-Shipping.zip"
            and rows[0]["page"] == mod and rows[0]["latest_version"] == "1.0.0"
            and source in rows[1]["page"])
        checks["fatekeeper_bundle_version_not_inferred"] = (
            len(rows) == 2 and rows[0]["status"] in ("unknown", "not_installed")
            and not rows[0].get("installed_version"))
        win.grab().save(str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-fk-updates.png"), "PNG")
        from vrhub import updates as update_logic
        checks["fatekeeper_update_badge_excludes_bundle_review"] = (
            update_logic.release_count(rows) == sum(r["status"] == "update" for r in rows)
            and len(rows) == 2
            and rows[0]["dependency_type"] == "Mod" and rows[1]["dependency_type"] == "Profile")
        win.sidebar.game_list.setCurrentRow(next(
            i for i, row in enumerate(win.rows) if row["recipe"]["id"] == "hogwarts-legacy"))
        win.game_details_tabs.setCurrentIndex(1)
        app.processEvents()
        hl_rows = win.update_results.get("hogwarts-legacy", [])
        checks["hogwarts_separate_archive_dependencies"] = (
            len(hl_rows) == 2 and
            {(r["name"], r.get("dependency_type")) for r in hl_rows}
            == {("UEVR.zip", "Mod"), ("HogwartsLegacy.zip", "Profile")})
        hl_count = update_logic.release_count(hl_rows)
        checks["hogwarts_badge_matches_release_notifications"] = (
            win.game_details_tabs.tabText(1) == (f"Updates ({hl_count})" if hl_count else "Updates"))
        checks["hogwarts_upstream_version_not_fabricated"] = (
            len(hl_rows) == 2 and hl_rows[1]["status"] in ("unknown", "error")
            and not hl_rows[1].get("installed_version"))
        checks["dependency_type_column_visible"] = (
            win.mod_updates.sections["update"].table.horizontalHeaderItem(0).text() == "Dependency"
            and win.mod_updates.sections["update"].table.horizontalHeader().logicalIndex(1) == 5)
        print("LIVE_RELEASE_COUNTS", "Fatekeeper", update_logic.release_count(rows),
              "Hogwarts Legacy", hl_count, flush=True)
        win.grab().save(str(Path.home() / ".cache/nannersvrhub-055-dev5d2d-hogwarts-updates.png"), "PNG")
        win.resize(*expected_open_size)
        app.processEvents()
        for name, ok in checks.items():
            print("DEV5D2D_CHECK", name, "PASS" if ok else "FAIL", flush=True)
        print("DEV5D2D_GUI_RESULT", "PASS" if all(checks.values()) else "FAIL", flush=True)
        if opts.verify:
            QTimer.singleShot(800, lambda: app.exit(0 if all(checks.values()) else 1))
        else:
            win.sidebar.game_list.setCurrentRow(
                next(i for i, row in enumerate(win.rows)
                     if row["recipe"]["id"] == "fatekeeper"))
            win.game_details_tabs.setCurrentIndex(6)
            win.install_tools_toggle.setChecked(False)
            win.library_toggle.setChecked(False)
            win.game_page_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            win.disable_mutations()
            print(f"KDE DEV5D2D ARCHIVE-FIRST PREVIEW READY at {win.width()}x{win.height()}. "
                  "Hogwarts Legacy Updates is selected. Archive verification "
                  "icons, complete pinned-set review, collapsed file inventory, "
                  "and original safety confirmations are preserved. "
                  "No live install, profile replacement, transfer, or launch is authorized.",
                  flush=True)


    polling = QTimer()
    polling.timeout.connect(verify)
    polling.start(300)
    if opts.verify:
        QTimer.singleShot(60000, lambda: app.exit(2) if not completed[0] else None)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
