# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-Y3: runtime-aware VR System and read-only player-first preview."""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel
from vrhub import gui, hub, archive_scans, download_planner as planner
from vrhub.app_update_gui import HubUpdateController
from tests.manual_launcher_dev5d3x_preview import (
    PayloadEvidencePreview, suppress_preview_name_cache_updates,
)


def _bind_host_openxr_runtime_for_preview(host_config=None):
    """Expose the user's SELECTED OpenXR manifest read-only in isolated UI.

    The preview intentionally uses a private XDG_CONFIG_HOME to protect state
    and desktop settings. That isolation also hides the host's real OpenXR
    loader selection. Only point XR_RUNTIME_JSON at the existing manifest
    file; never copy, rewrite or switch the user's configured runtime.
    Honor an explicit XR_RUNTIME_JSON override already set by the user.
    """
    if os.environ.get("XR_RUNTIME_JSON"):
        return False
    source = (Path(host_config) if host_config is not None
              else Path.home() / ".config") / "openxr/1"
    from platform import machine
    arch = {"AMD64": "x86_64", "arm64": "aarch64"}.get(machine(), machine())
    for name in (f"active_runtime.{arch}.json", "active_runtime.json"):
        candidate = source / name
        if candidate.is_file():
            os.environ["XR_RUNTIME_JSON"] = str(candidate)
            return True
    return False


class PlayerFirstPreview(PayloadEvidencePreview):
    """Normal view has no rehearsals; the old evidence worker stays intact."""

    def __init__(self):
        super().__init__()
        # The inherited synthetic rehearsal is NOT a player workflow. It is
        # only available after an explicit Tools > Enable development tools,
        # and only while inspecting advanced diagnostics. No backend changes.
        self.downloads.comparison_toggle.toggled.disconnect(
            self.offline_footer.setVisible)
        # The inherited X preview appended the rehearsal as an OUTER sibling.
        # Y moved the diagnostics panel, leaving that sibling elsewhere in
        # the scroll area. Parent it INSIDE the actual Advanced diagnostics
        # disclosure so the visible menu action is directly discoverable.
        self.downloads.layout().removeWidget(self.offline_footer)
        self.downloads.comparison_panel.layout().insertWidget(
            1, self.offline_footer)
        self.downloads.comparison_toggle.toggled.connect(
            self._sync_developer_only_rehearsal)
        self.development_tools_action.toggled.connect(
            self._sync_developer_only_rehearsal)
        self.development_tools_action.toggled.connect(
            self._announce_development_tools)
        self.game_details_tabs.currentChanged.connect(
            self._sync_developer_only_rehearsal)
        self.development_tools_action.setToolTip(
            "Optional preview-only diagnostic rehearsals appear under "
            "Install / Update → Advanced diagnostics. No game files changed.")
        self.offline_footer.hide()

    def disable_mutations(self):
        # The inherited preview safety allowlist intentionally disabled this
        # QAction in older milestones. That also made Tools > Enable
        # development tools inert for humans, while direct setChecked() in
        # tests misleadingly worked. Permit ONLY the reversible UI toggle:
        # the inherited implementation still disables every real installer,
        # downloader, save editor and live update action.
        super().disable_mutations()
        self.development_tools_action.setEnabled(True)
        # The actual VR System scan is read-only. Permit it and clipboard
        # copy, but continue to block Save report (writes an arbitrary file)
        # and every live game-related mutation in this preview.
        self.scan_btn.setEnabled(self.scan_worker is None)
        self.copy_scan_btn.setEnabled(self.scan_report is not None)
        self.save_scan_btn.setEnabled(False)

    def show_system_report(self, report):
        # Make the export distinguish this development preview from the stable
        # 0.5.4 app. Never rewrite or mutate the scanner's underlying report.
        report = dict(report)
        report["hub_version"] = "0.5.5-dev5D3y3"
        super().show_system_report(report)
        self.save_scan_btn.setEnabled(False)

    def _announce_development_tools(self, enabled):
        self.statusBar().showMessage(
            "Development tools ON — open Install / Update → "
            "Advanced diagnostics for TEST FIXTURE ONLY."
            if enabled else
            "Development tools OFF — fixture rehearsals hidden.",
            12000)

    def _sync_developer_only_rehearsal(self, *_):
        allowed = (self.development_tools_action.isChecked()
                   and self.game_details_tabs.currentWidget() is self.downloads
                   and self.downloads.comparison_toggle.isChecked())
        self.offline_footer.setVisible(allowed)
        if allowed:
            # Opening the disclosure from Tools must bring the actual fixture
            # control into view rather than leaving it above/below the scroll.
            from PySide6.QtCore import QTimer
            # show_details() rebuilds the game panel on QAction toggling.
            # Scroll AFTER Qt finishes that layout, not during the toggle.
            QTimer.singleShot(
                80, lambda: self.game_page_scroll.ensureWidgetVisible(
                    self.offline_button, 0, 24)
                if self.offline_footer.isVisible() else None)


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = p.parse_args()

    if args.show:
        os.environ["VRHUB_NEXUS_READONLY_KEY_FILE"] = str(
            Path.home() / ".config/vrhub/nexus_key")
        from vrhub.dev_preview_storage import shared_directory
        shared = shared_directory()
        state = (shared / "state.json").resolve()
        if (Path(os.environ.get("VRHUB_STATE", "")).resolve() != state
                or not state.is_file() or state.is_symlink()):
            raise SystemExit("Shared existing non-symlinked preview state required.")
    else:
        state = Path(os.environ.get("VRHUB_STATE", "")).resolve()
        if not state.parent.name.startswith("nanners-dev5d3y3-gui."):
            raise SystemExit("Disposable Dev5D3-Y3 fixture state required.")

    if (not state.is_file()
            or state == (Path.home() / ".local/share/vrhub/state.json").resolve()
            or not os.environ.get("VRHUB_NEXUS_KEY_FILE")):
        raise SystemExit("Private preview state + key path required.")

    if args.show:
        _bind_host_openxr_runtime_for_preview()
    suppress_preview_name_cache_updates()
    HubUpdateController.startup = lambda self: None
    # Early previews suppressed VR scans to focus on installer rehearsals.
    # Dev5D3-Y2 restores the original ScanWorker in the desktop preview.
    # Only the disposable offline GUI harness may stub it for deterministic
    # layout checks; a separate test validates the real worker path.
    if args.verify:
        gui.HubWindow.scan_setup = lambda self, *a, **kw: None
        gui.HubWindow.check_updates = lambda self: None

    app = QApplication([sys.argv[0]])
    win = PlayerFirstPreview()
    win.key_btn.setToolTip(
        "Read-only Nexus key lookup, when available. No key is copied.")
    win.allow_guided_installs = False
    win.downloads.allow_transfers = False
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3y3 — PLAYER-FIRST ACCEPTANCE FIX (NO GAME WRITES)")
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev5D3y3 · PREVIEW")
    win.tabs.setCurrentIndex(1)

    def select(rid):
        win.sidebar.game_list.setCurrentRow(next(
            i for i, row in enumerate(win.rows) if row["recipe"]["id"] == rid))
        win.game_details_tabs.setCurrentWidget(win.downloads)
        win.more_tools_toggle.setChecked(False)
        win.library_toggle.setChecked(False)
        win.downloads.comparison_toggle.setChecked(False)
        win.game_page_scroll.verticalScrollBar().setValue(0)
        app.processEvents()
        win.disable_mutations()

    select("fatekeeper")
    win.show()
    app.processEvents()
    win.disable_mutations()
    if args.show:
        print("DEV5D3Y3 DESKTOP READY — Player-first workflow; "
              "technical rehearsal under Tools > Enable development tools; "
              "no game writes.", flush=True)
        return app.exec()

    win.resize(1630, 1060)
    app.processEvents()
    checks = {}
    imgs = state.parent / "renders"
    imgs.mkdir(exist_ok=True)
    previous_scans = archive_scans.snapshot_file().read_bytes()
    saved = archive_scans.load_saved()
    checks["prior_saved_scan_history_available"] = bool(saved)
    checks["scan_downloads_default"] = planner.default_library() == Path.home() / "Downloads"

    # Reproduce saved matches in copied test state only. No real folders,
    # persisted user prefs, source ZIPs, or game files are edited.
    for rid, rec in saved.items():
        if rid not in hub.load_recipes():
            continue
        prior = archive_scans.plan_folders(rec["plan"])
        if prior and prior[-1] != Path.home() / "Downloads" and prior[-1].is_dir():
            planner.set_location("game", str(prior[-1]), rid)
        recipe = hub.load_recipes()[rid]
        roots = planner.scan_folders(recipe)
        if all(root.is_dir() and not root.is_symlink() for root in roots):
            try:
                archive_scans.persist(planner.build_plan(recipe, roots))
            except (OSError, ValueError) as exc:
                print("Y_FIXTURE_SCAN_UNAVAILABLE", rid, type(exc).__name__, flush=True)

    checks["nine_games"] = len(win.rows) == 9
    checks["sidebar_preserved"] = win.sidebar.isVisible()
    checks["no_unfinished_sidebar_navigation"] = (
        not win.sidebar.future_toggle.isVisible()
        and not win.sidebar.future_toggle.isEnabled()
        and not win.sidebar.future_panel.isVisible()
        and all(not b.isVisible()
                for b in win.sidebar.planned_buttons.values()))
    checks["updates_separate_tab"] = (
        win.game_details_tabs.indexOf(win.mod_updates) >= 0
        and "Installed" in str(win.mod_updates.sections["current"].table.horizontalHeaderItem(1).text()))
    checks["original_saved_history_preserved"] = all(
        rid in archive_scans.load_histories() for rid in saved
        if rid in hub.load_recipes())

    for row in win.rows:
        rid = row["recipe"]["id"]
        select(rid)
        page = win.downloads
        label = page.comparison_toggle.text()
        checks[rid+"_advanced_not_versions"] = (
            "Advanced diagnostics" in label and "Compare versions" not in label)
        checks[rid+"_advanced_collapsed"] = (
            not page.comparison_panel.isVisible() and
            not win.offline_footer.isVisible())
        checks[rid+"_review_before_table"] = (
            page.layout().indexOf(page.review_actions) <
            page.layout().indexOf(page.table))
        checks[rid+"_archive_scan_visible"] = page.scan.isVisible()
        checks[rid+"_no_duplicate_primary"] = (
            len([x for x in page.findChildren(type(page.install_review_button))
                 if x.objectName()=="primaryAction"
                 and x.text() in ("Review installation","Choose archive",
                                 "Review profile","Install verified dependencies")]) <= 1)
        checks[rid+"_existing_route_unchanged"] = (
            page.install_review_button.text() == page._primary_action()[1])
        checks[rid+"_safety_never_automatically_runs"] = (
            page._safety_result is None and page.safety_worker is None)
        checks[rid+"_normal_mode_no_rehearsal"] = (
            not win.offline_footer.isVisible()
            and not win.development_tools_action.isChecked())
        checks[rid+"_original_installer_gate"] = (
            not win.allow_guided_installs and
            not page.allow_transfers and
            win.install_btn.isHidden())
        checks[rid+"_saved_scan_available"] = (
            rid not in saved or page._last_plan is not None
            or bool(page.scan_age.text()))
        checks[rid+"_render"] = win.grab().save(str(imgs/(rid+"-player-default.png")))
        if rid in ("fatekeeper","cyberpunk-2077","valheim"):
            checks[rid+"_action_above_first_table_row"] = (
                page.review_actions.mapTo(page,QPoint(0,0)).y() <
                page.table.mapTo(page,QPoint(0,0)).y())
        if page.comparison_toggle.isVisible():
            page.comparison_toggle.click()
            app.processEvents()
            checks[rid+"_advanced_manual_open"] = (
                page.comparison_panel.isVisible()
                and not win.offline_footer.isVisible()
                and page.safety_button.isVisible()
                and not page.comparison_table.isVisible()
                and not page.comparison_summary.isVisible()
                and not page.readiness_summary.isVisible())
            page.comparison_toggle.click()
            app.processEvents()

    # Actual action visibility is checked in a compact 1280x720 window,
    # not merely by checking QWidget.isVisible while scrolled off-screen.
    select("fatekeeper")
    win.resize(1280,720)
    app.processEvents()
    win.game_page_scroll.verticalScrollBar().setValue(0)
    app.processEvents()
    page = win.downloads
    action = page.install_review_button if page.install_review_button.isVisible() else page.scan
    top = action.mapTo(win.game_page_scroll.viewport(),QPoint(0,0)).y()
    bottom = top+action.height()
    checks["fatekeeper_player_action_within_first_viewport"] = (
        top >= 0 and bottom <= win.game_page_scroll.viewport().height())
    checks["fatekeeper_720p_screen_render"] = win.grab().save(
        str(imgs/"fatekeeper-1280x720-player.png"))
    print("DEV5D3Y3_FATEKEEPER_VIEWPORT",
          "button_top",top,"button_bottom",bottom,
          "viewport_height",win.game_page_scroll.viewport().height(),
          flush=True)
    win.resize(1630,1060)
    select("fatekeeper")
    checks["developer_rehearsal_not_shown_on_advanced_open"] = (
        not win.offline_footer.isVisible())
    win.downloads.comparison_toggle.setChecked(True)
    app.processEvents()
    checks["advanced_still_no_rehearsal"] = not win.offline_footer.isVisible()
    # Use the actual Tools menu QAction trigger, not setChecked(): the
    # original desktop acceptance failure was in the menu-to-layout path.
    tools = next((entry.menu() for entry in win.menuBar().actions()
                  if entry.menu() and entry.menu().title()=="Tools"), None)
    action = next((item for item in tools.actions()
                   if item is win.development_tools_action), None) if tools else None
    checks["development_tools_menu_action_accessible"] = (
        action is win.development_tools_action
        and action.isEnabled() and action.isCheckable())
    if action:
        action.trigger()
    app.processEvents()
    from PySide6.QtTest import QTest
    QTest.qWait(130)
    app.processEvents()
    print("DEV5D3Y3_MENU_TRACE", {
        "checked":win.development_tools_action.isChecked(),
        "action_enabled":win.development_tools_action.isEnabled(),
        "enabled":win.development_tools_enabled,
        "footer_visible":win.offline_footer.isVisible(),
        "button_visible":win.offline_button.isVisible(),
        "footer_parent_is_panel":win.offline_footer.parent() is win.downloads.comparison_panel,
        "footer_in_panel_index":win.downloads.comparison_panel.layout().indexOf(win.offline_footer),
        "panel_visible":win.downloads.comparison_panel.isVisible(),
        "status_message":win.statusBar().currentMessage(),
        "menu_action_text":win.development_tools_action.text(),
    },flush=True)
    checks["dev_tools_explicitly_enable_rehearsal"] = (
        win.development_tools_action.isChecked()
        and win.offline_footer.isVisible()
        and win.offline_button.isVisible()
        and win.offline_footer.parent() is win.downloads.comparison_panel
        and win.downloads.comparison_panel.layout().indexOf(
            win.offline_footer)==1)
    checks["developer_tools_menu_feedback"] = (
        "Development tools ON" in win.statusBar().currentMessage())
    top = win.offline_button.mapTo(
        win.game_page_scroll.viewport(), QPoint(0,0)).y()
    bottom = top+win.offline_button.height()
    checks["developer_fixture_visible_in_viewport"] = (
        top >= 0 and bottom <= win.game_page_scroll.viewport().height())
    print("DEV5D3Y3_DEVELOPER_BUTTON_VIEWPORT",
          "top",top,"bottom",bottom,
          "viewport_height",win.game_page_scroll.viewport().height(),
          flush=True)
    checks["dev_tools_no_mutation_permissions"] = (
        not win.allow_guided_installs
        and not win.downloads.allow_transfers
        and not win.install_btn.isEnabled()
        and not win.downloads.download_button.isEnabled()
        and not win.downloads.download_cancel.isEnabled()
        and not win.doom_saves_btn.isEnabled()
        and not win.hub_update_btn.isEnabled())
    checks["dev_tools_fixture_not_run_automatically"] = (
        "not run" in win.offline_status.text())
    win.offline_button.click()
    app.processEvents()
    checks["dev_tools_six_rehearsals_pass"] = (
        "Unified fixture staging PASSED" in win.offline_status.text()
        and "6 synthetic rollbacks" in win.offline_status.text()
        and "5 synthetic payload classifications" in win.offline_status.text())
    checks["dev_tools_rehearsal_stays_readonly"] = (
        "LIVE UPDATE DISABLED" in win.offline_status.text()
        and not win.allow_guided_installs
        and not page.allow_transfers)
    checks["dev_only_render"] = win.grab().save(
        str(imgs/"developer-only-rehearsal.png"))
    if action:
        action.trigger()
    app.processEvents()
    checks["dev_tools_off_hides_rehearsal"] = (
        not win.development_tools_action.isChecked()
        and not win.offline_footer.isVisible()
        and "Development tools OFF" in win.statusBar().currentMessage())
    select("cyberpunk-2077")
    checks["game_switch_discards_fixture_result"] = (
        "not run" in win.offline_status.text()
        and not win.offline_details.isVisible()
        and not win.offline_footer.isVisible())
    checks["read_only_report_still_reachable"] = (
        win.downloads.safety_button.text()=="Review replacement safety (read-only)")
    checks["sidebar_only_real_navigation"] = (
        win.sidebar.games_button.isVisible()
        and win.sidebar.system_button.isVisible()
        and not win.sidebar.future_toggle.isVisible())

    # Y3: two synthetic reports, no actual OpenXR runtime manipulation.
    # Explicitly verify the dashboard does not confuse selection, process
    # observation, or WiVRn-only headset telemetry.
    from vrhub import system_scan
    from copy import deepcopy
    simulated=system_scan.scan()
    simulated["status"]="HOST CHECKS PASSED"
    simulated["runtime"]="SteamVR"
    simulated["scope"]=system_scan._scope_for_runtime("SteamVR")
    simulated["live"].update(
        runtime_selected=True, server_running=False, headset_connected=None,
        headset_connection_verified=False, controllers_verified=False)
    win.show_system_report(simulated)
    checks["runtime_steamvr_selected_label"] = (
        win.runtime_state.text()=="Runtime: SteamVR SELECTED"
        and win.server_state.text()=="Server: NOT OBSERVED"
        and win.headset_state.text()=="Headset: UNKNOWN")
    checks["runtime_steamvr_report_scope"] = (
        "SteamVR server-process observation" in
            win.system_details.toPlainText()
        and "SteamVR" in win.scan_summary.text())
    win.show_system_report(deepcopy(dict(
        simulated, runtime="WiVRn",scope=system_scan._scope_for_runtime("WiVRn"),
        live=dict(simulated["live"], server_running=True,
                  headset_connected=True, headset_connection_verified=True))))
    checks["runtime_wivrn_selected_label"] = (
        win.runtime_state.text()=="Runtime: WiVRn SELECTED"
        and win.server_state.text()=="Server: RUNNING"
        and win.headset_state.text()=="Headset: CONNECTED")
    checks["runtime_preview_report_version"] = (
        "NAnnersVRhub 0.5.5-dev5D3y3" in
            system_scan.report_text(win.scan_report))
    checks["runtime_still_no_live_changes"] = (
        not win.save_scan_btn.isEnabled()
        and not win.allow_guided_installs
        and not win.downloads.allow_transfers)
    win.tabs.setCurrentIndex(1)
    app.processEvents()

    checks["saved_scan_fixture_unchanged_on_render"] = (
        archive_scans.snapshot_file().is_file()
        and previous_scans != b"")

    for name, passed in checks.items():
        print("DEV5D3Y3_CHECK", name, "PASS" if passed else "FAIL", flush=True)
    print("DEV5D3Y3_GUI_RESULT",
          sum(bool(v) for v in checks.values()), "/", len(checks), flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
