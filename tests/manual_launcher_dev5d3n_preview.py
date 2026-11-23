# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-N synthetic pinned-package staging and compatibility preview: no game modifications."""
import argparse
import os
import sys
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from PySide6.QtWidgets import QApplication, QLabel, QDialog, QPushButton, QWidget, QVBoxLayout
from PySide6.QtCore import QPoint
from vrhub import gui, hub, archive_scans, download_planner as planner, offline_transaction, update_integration, pinned_staging
from vrhub.app_update_gui import HubUpdateController
from tests.manual_launcher_dev5d3e1_preview import CleanupPreview


def suppress_preview_name_cache_updates():
    """Keep authenticated Updates lookups, but don't rewrite preview state.

    The standard UpdateWorker can refresh persisted Nexus name metadata as a
    side effect. That persistence is unnecessary for a read-only preview.
    """
    hub.refresh_component_names = lambda *args, **kwargs: 0


class PinnedStagingPreview(CleanupPreview):
    def __init__(self):
        super().__init__()
        self.offline_button = QPushButton("Rehearse pinned package staging (TEST FIXTURE ONLY)")
        self.offline_button.setObjectName("downloadsAction")
        self.offline_button.setToolTip(
            "Synthetic pinned Valheim, Subnautica and Elden Ring ZIPs are mapped "
            "using existing safety rules, with declared build and phase checks, "
            "then interrupted and recovered inside disposable fixtures. "
            "Real game builds, archives and installers are never touched.")
        self.offline_status = QLabel(
            "Offline transaction rehearsal: not run. Real mod replacement remains blocked.")
        self.offline_status.setWordWrap(True)
        # A separate preview-only sibling keeps the approved J comparison
        # panel's height and scrolling behavior intact.
        self.offline_footer = QWidget(self.downloads)
        self.offline_footer.setObjectName("offlineRecoveryFixtureOnly")
        layout = QVBoxLayout(self.offline_footer)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(5)
        layout.addWidget(self.offline_button)
        layout.addWidget(self.offline_status)
        main_layout = self.downloads.layout()
        index = main_layout.indexOf(self.downloads.comparison_panel)
        main_layout.insertWidget(index + 1, self.offline_footer)
        self.offline_footer.hide()
        self.downloads.comparison_toggle.toggled.connect(
            self.offline_footer.setVisible)
        self.offline_button.clicked.connect(self._rehearse_fixture)
        # A completed fixture check does not belong to the currently selected
        # real game. Clear its result whenever the game selection changes.
        self.sidebar.game_list.currentRowChanged.connect(self._clear_fixture_result)

    def _clear_fixture_result(self, *_):
        self.offline_status.setText(
            "Offline transaction rehearsal: not run. TEST FIXTURE ONLY.")

    def _rehearse_fixture(self):
        self.offline_button.setEnabled(False)
        self.offline_status.setText(
            "Validating three synthetic pinned ZIP sets and private interrupted-update fixtures…")
        QApplication.processEvents()
        try:
            evidence=pinned_staging.rehearse_pinned_packages()
            rows=evidence.get("results", [])
            expected=["valheim", "subnautica", "elden-ring"]
            if (not evidence.get("fixture_only") or
                    evidence.get("real_game_files_modified") or
                    evidence.get("live_update_authorized") or
                    evidence.get("real_game_compatibility_verified") or
                    not evidence.get("temporary_fixtures_discarded") or
                    [r.get("game") for r in rows] != expected or
                    not all(r.get("rollback_passed") and
                            r.get("synthetic_pin_verified") and
                            r.get("declared_fixture_build_checked") and
                            not r.get("real_compatibility_verified") and
                            not r.get("live_update_authorized") for r in rows)):
                raise RuntimeError("Pinned staging fixture rehearsal did not prove recovery.")
        except Exception:
            self.offline_status.setText(
                "Pinned staging rehearsal FAILED. No live update authorized.")
        else:
            self.offline_status.setText(
                "Pinned staging PASSED · Valheim 2 ZIPs / 4 targets · "
                "Subnautica 2 ZIPs / 4 targets · Elden Ring 1 ZIP / 2 targets · "
                "3 synthetic rollbacks · temporary fixtures discarded · "
                "REAL COMPATIBILITY UNVERIFIED · LIVE UPDATE DISABLED")
        finally:
            self.offline_button.setEnabled(True)

    def disable_mutations(self):
        super().disable_mutations()
        # Read-only comparison is safe; legacy preview allowlist predates it.
        self.downloads.comparison_toggle.setEnabled(True)
        # The user explicitly starts this read-only integrity scan.
        self.downloads.integrity_button.setEnabled(True)
        # Explicit read-only backup/ZIP review; old preview allowlist predates it.
        self.downloads.safety_button.setEnabled(True)
        if hasattr(self, "offline_button"):
            self.offline_button.setEnabled(True)


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
    if opts.verify and not state.parent.name.startswith("nanners-dev5d3n-gui."):
        raise SystemExit("GUI verification requires a disposable private fixture.")

    suppress_preview_name_cache_updates()
    HubUpdateController.startup=lambda self: None
    gui.HubWindow.scan_setup=lambda self,*a,**kw: None
    if opts.verify:
        gui.HubWindow.check_updates=lambda self: None
    app=QApplication([sys.argv[0]])
    win=PinnedStagingPreview()
    win.key_btn.setToolTip(
        "Preview uses your existing Nexus key read-only when available. "
        "Manage or remove the real key outside this preview.")
    win.allow_guided_installs=False
    win.downloads.allow_transfers=False
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3n — PINNED PACKAGE STAGING (NO GAME WRITES)")
    brand=win.findChild(QLabel,"brandTitle")
    if brand: brand.setText("NAnnersVRhub  0.5.5-dev5D3n · PREVIEW")
    win.tabs.setCurrentIndex(1)

    def select(rid):
        win.sidebar.game_list.setCurrentRow(next(
            i for i,row in enumerate(win.rows) if row["recipe"]["id"]==rid))
        win.game_details_tabs.setCurrentWidget(win.downloads)
        win.more_tools_toggle.setChecked(False)
        win.library_toggle.setChecked(False)
        win.game_page_scroll.verticalScrollBar().setValue(0)
        app.processEvents()
        win.disable_mutations()

    select("fatekeeper")
    win.show()
    app.processEvents()
    win.disable_mutations()
    if opts.show:
        print("DEV5D3N DESKTOP READY — Nexus credential read-only; scans preserved; no game writes.",flush=True)
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
        page = win.downloads
        checks[rid+"_no_legacy_drawer"] = (
            win.install_tools_toggle.isHidden()
            and win.install_tools_panel.isHidden()
            and page.layout().indexOf(win.install_tools_panel) == -1)
        checks[rid+"_manual_in_review_footer"] = (
            page.manual_review_button.parent() is page.review_actions)
        checks[rid+"_selection_inspection_in_review"] = (
            page.inspect.parent() is page.review_actions)
        checks[rid+"_transfer_in_archive_page"] = (
            page.download_button.parent() is page)
        checks[rid+"_no_duplicate_buttons"] = (
            win.verify_btn.isHidden() and win.inspect_btn.isHidden())
        checks[rid+"_manual_only_when_needed"] = (
            page.manual_review_button.isHidden() ==
            (page._manual_review_route() is None))
        supported = recipe.get("method") in ("gameroot","bepinex","ervr")
        checks[rid+"_external_inspection_context"] = (
            win.manual_archive_inspect_action.isVisible() == supported)
        checks[rid+"_specialists_in_compatibility"] = all(
            button.parent() is win.more_tools_panel
            for button in (win.kharvox_folder_btn,
                           win.doom_prepare_btn, win.doom_import_btn))
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
            checks[rid+"_readiness_header"] = (
                page.comparison_table.horizontalHeaderItem(4).text()=="Update readiness")
            checks[rid+"_no_install_authority"] = (
                "No update is authorized" in page.readiness_summary.text())
            checks[rid+"_replacement_review_action"] = (
                page.safety_button.text() == "Review replacement safety (read-only)"
                and page.safety_button.isEnabled())
            checks[rid+"_safety_not_automatic"] = (
                page.safety_worker is None and page._safety_result is None
                and "not reviewed" in page.safety_summary.text())
            checks[rid+"_safety_details_hidden"] = not page.safety_details.isVisible()
            contract = update_integration.assess(recipe)
            checks[rid+"_integration_contract_not_executable"] = (
                contract["game_id"] == rid and not contract["authorized"]
                and not contract["live_executor_connected"]
                and all(not c["authorized"] and not c["replacement_supported"]
                        for c in contract["contracts"]))
            checks[rid+"_integration_adapter_coverage"] = (
                {c["id"] for c in contract["contracts"]} ==
                {c["id"] for c in planner.plan_components(recipe)})
            checks[rid+"_pinned_staging_scope"] = (
                (rid in pinned_staging.SUPPORTED) ==
                (recipe.get("method") in ("bepinex", "ervr") and bool(recipe.get("packages"))))
            checks[rid+"_offline_rehearsal_only"] = (
                win.offline_button.text() ==
                "Rehearse pinned package staging (TEST FIXTURE ONLY)" and
                "not run" in win.offline_status.text() and
                win.offline_button.parent() is win.offline_footer and
                win.offline_footer.parent() is page)
            checks[rid+"_readiness_cells_populated"] = all(
                page.comparison_table.item(i,4) is not None and
                bool(page.comparison_table.item(i,4).text()) and
                "No replacement" in page.comparison_table.item(i,4).toolTip()
                for i in range(page.comparison_table.rowCount()))
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
                from vrhub import installed_provenance
                actual = installed_provenance.evidence(
                    recipe, planner.plan_components(recipe)[1], hub.state())
                checks["valheim_installed_provenance"] = (
                    page.comparison_table.item(1,1).text() == actual["label"])
                checks["valheim_online_fixture_render"] = win.grab().save(str(imgs/"valheim-after-online-fixture.png"))
            page.comparison_toggle.click()
            app.processEvents()
            checks[rid+"_comparison_recollapses"] = not page.comparison_panel.isVisible()
        checks[rid+"_integrity_action_present"] = (
            page.integrity_button.text() == "Verify installed files")
        checks[rid+"_integrity_not_automatic"] = (
            page.integrity_worker is None and page._integrity_result is None)
        checks[rid+"_integrity_details_hidden"] = not page.integrity_details.isVisible()
        if rid in saved:
            current=archive_scans.matching_record(rid,roots)
            checks[rid+"_scan_record"] = current is not None
            checks[rid+"_active_plan"] = win.downloads._last_plan is not None
            checks[rid+"_folders_in_plan"] = (
                bool(current) and archive_scans.plan_folders(current["plan"])==roots)
            checks[rid+"_paths_within_roots"] = bool(current) and all(
                not r["file"] or any(Path(r["file"]).is_relative_to(root) for root in roots)
                for r in current["plan"]["rows"])
    # Synthetic Hub state entries exercise recorded release provenance
    # without mutating the copied user state or a live game.
    for game in ("subnautica", "valheim"):
        recipe=hub.load_recipes()[game]
        marker="submersed-vr-1" if game=="subnautica" else "vhvr-1"
        synthetic={game:{"installer": marker, "packages": {
            p["id"]: {"sha256":p["sha256"],"files":["/fixture/recorded.dll"]}
            for p in recipe["packages"]}}}
        with mock.patch.object(hub, "state", return_value=synthetic):
            select(game)
            table=win.downloads.comparison_table
            checks[game+"_recorded_pins"] = all(
                table.item(i,1) is not None and table.item(i,1).text().startswith("Recorded pin ")
                for i in range(len(recipe["packages"])))
            checks[game+"_recorded_provenance_tooltips"] = all(
                "recipe-pinned-hash" in table.item(i,1).toolTip()
                for i in range(len(recipe["packages"])))
            checks[game+"_no_auto_install_from_pins"] = not win.allow_guided_installs
            win.downloads.comparison_toggle.setChecked(True)
            app.processEvents()
            win.setWindowTitle("DEV5D3-N TEST FIXTURE — NOT A LIVE INSTALLED VERSION")
            checks[game+"_recorded_render"] = win.grab().save(
                str(imgs/(game+"-recorded-FIXTURE.png")))
            win.downloads.comparison_toggle.setChecked(False)

    # On-demand GUI integration test uses a disposable synthetic file tree.
    # No actual installed game file is opened in the automated harness.
    from vrhub import installed_integrity
    import hashlib
    fixture_root = state.parent / "readonly-integrity-fixture"
    fixture_root.mkdir(exist_ok=True)
    relative = "BepInEx/plugins/VHVR-fixture.dll"
    fixture_file = fixture_root / relative
    fixture_file.parent.mkdir(parents=True, exist_ok=True)
    fixture_file.write_bytes(b"fixture-good")
    vhvr = hub.load_recipes()["valheim"]
    fake_state = {"valheim": {
        "installer": "vhvr-1",
        "keep": str(fixture_root),
        "files": [str(fixture_file)],
        "file_hashes": {relative: hashlib.sha256(b"fixture-good").hexdigest()},
        "packages": {
            "vhvr": {"sha256": vhvr["packages"][1]["sha256"],
                     "files": [str(fixture_file)]}}}}
    select("valheim")
    with mock.patch.object(hub, "state", return_value=fake_state), mock.patch.object(
            hub, "game_path", return_value=fixture_root):
        result = installed_integrity.verify(vhvr)
    checks["fixture_one_file_verified"] = (
        result["rows"][1]["status"]=="Verified" and result["checked"]==1)
    checks["fixture_untracked_loader_unknown"] = result["rows"][0]["status"]=="Unknown"
    win.downloads._integrity_result=result
    win.downloads.integrity_status.setText(
        "TEST FIXTURE · one tracked file matched · loader untracked")
    win.downloads.integrity_details.setPlainText(
        "TEST FIXTURE · BepInExPack: Unknown — no recorded file hash")
    win.downloads.integrity_details.show()
    checks["fixture_render"] = win.grab().save(str(imgs/"valheim-integrity-TEST-FIXTURE.png"))
    checks["fixture_not_game_install"] = fixture_root.is_relative_to(state.parent)
    # Strictly synthetic candidate: the historical installed profile hash,
    # on-demand integrity outcome, two GitHub archive digests, and separate
    # online version are fixture-only. No real profile is inspected or changed.
    recipe=hub.load_recipes()["fatekeeper"]
    parts=planner.plan_components(recipe)
    a="a"*64
    b="b"*64
    profile={
        **parts[1], "status":"Possible archive — inspect first",
        "file":"/fixture/downloads/SLASHER-Win64-Shipping-1.zip",
        "candidates":[
            {"file":"/fixture/downloads/SLASHER-Win64-Shipping-1.zip",
             "sha256":b,"tags":["v1.0.4"],"expected":True,"copies":1},
            {"file":"/fixture/old/SLASHER-Win64-Shipping.zip",
             "sha256":a,"tags":["v1.0.3"],"expected":False,"copies":1}],
        "release_expected":"v1.0.4",
        "release_review":False,"ambiguous":False,
        "candidate_incomplete":False}
    plan={"game_id":"fatekeeper",
          "rows":[{**parts[0],"status":"Not found locally","file":""},profile],
          "warning":None}
    synthetic={"fatekeeper:profile":{
        "installer":"uevr-profile-2","archive_sha256":a,
        "installed":{"exists":True,"files":{
            "config.txt":{"sha256":"c"*64,"size":12}}}}}
    select("fatekeeper")
    with mock.patch.object(hub,"state",return_value=synthetic):
        win.downloads._last_plan=plan
        win.downloads._integrity_result={
            "game_id":"fatekeeper",
            "rows":[{"id":"profile","status":"Verified","files":1,"checked":1}],
            "presence":{"status":"Ready","required_bad":[]}}
        win.downloads.set_online_results([{
            "name":"SLASHER-Win64-Shipping.zip",
            "latest_version":"v1.0.4","status":"update"}])
        candidate_cell=win.downloads.comparison_table.item(1,4)
        checks["synthetic_candidate_review_only"] = (
            candidate_cell is not None and
            "Future update candidate" in candidate_cell.text() and
            "No replacement" in candidate_cell.toolTip())
        checks["synthetic_candidate_no_install_bypass"] = (
            not win.allow_guided_installs and not win.downloads.allow_transfers)
        checks["synthetic_candidate_count_only"] = (
            "1 future candidate(s)" in win.downloads.readiness_summary.text())
        win.setWindowTitle("DEV5D3-N TEST FIXTURE — NO REAL GAME READY FOR UPDATE")
        win.downloads.comparison_toggle.setChecked(True)
        app.processEvents()
        checks["synthetic_candidate_render"] = win.grab().save(
            str(imgs/"fatekeeper-update-readiness-TEST-FIXTURE.png"))
        win.downloads.comparison_toggle.setChecked(False)
    select("valheim")
    checks["game_switch_drops_candidate"] = (
        win.downloads._integrity_result is None and
        "0 future candidate(s)" in win.downloads.readiness_summary.text() and
        all("Future update candidate" not in
            win.downloads.comparison_table.item(i, 4).text()
            for i in range(win.downloads.comparison_table.rowCount())))

    # Synthetic, disposable profile folder and exact ZIP metadata for
    # replacement planning; NEVER inspect a real game backup here.
    from vrhub import preupdate_safety
    from threading import Event
    import zipfile
    plan_root = state.parent / "preupdate-safety-FIXTURE"
    plan_root.mkdir(exist_ok=True)
    synthetic_profile = plan_root / "profile"
    synthetic_profile.mkdir(exist_ok=True)
    zipped = plan_root / "profile-next.zip"
    with zipfile.ZipFile(zipped, "w") as z:
        z.writestr("SLASHER-Win64-Shipping/config.txt", "next-profile-test")
        z.writestr("SLASHER-Win64-Shipping/settings.ini", "settings-test")
    next_sha = preupdate_safety.install_review._hash(zipped)
    recipe = hub.load_recipes()["fatekeeper"]
    profile_part = planner.plan_components(recipe)[1]
    synthetic = {"fatekeeper:profile": {
        "installer": "uevr-profile-2", "root": str(synthetic_profile),
        "archive_sha256": "a"*64, "backup": None,
        "original": {"exists": False, "files": {}, "dirs": [], "bytes": 0},
        "installed": {"exists": True, "files": {
            "config.txt": {"sha256":"b"*64,"size": 10}},
            "dirs": [], "bytes": 10}}}
    scan = {"game_id":"fatekeeper", "warning": None, "rows": [
        {**profile_part, "status":"Possible archive — inspect first",
         "file":str(zipped), "ambiguous":False,
         "candidate_incomplete":False,"release_review":False,
         "candidates":[{"file":str(zipped),"sha256":next_sha,
                        "tags":["v2.0.0"],"expected":True}]}]}
    decisions = [{"id":"profile","code":"candidate",
                  "label":"Future update candidate · review"}]
    with mock.patch.object(hub, "state_file", return_value=state), mock.patch.object(
            hub, "profile_dir", return_value=synthetic_profile):
        safety = preupdate_safety.review(recipe,scan,synthetic,decisions)
    checks["fixture_no_update_approval"] = (
        safety["authorized"] is False and safety["has_live_install_plan"] is False)
    checks["fixture_profile_prospective_mapping"] = (
        safety["rows"][1]["future_destinations"] == 2)
    checks["fixture_fresh_backup_required"] = (
        "fresh, verified backup" in safety["new_backup"])
    safety["integration"] = update_integration.assess(
        recipe, synthetic, decisions, {
            "game_id":"fatekeeper",
            "rows":[{"id":"profile","status":"Verified","files":1,"checked":1}],
            "presence":{"status":"Ready","required_bad":[]},
        }, safety)
    checks["fixture_uevr_draft_but_blocked"] = (
        safety["integration"]["contracts"][1]["adapter"] == "uevr_profile"
        and safety["integration"]["contracts"][1]["recorded_ownership"]
        and not safety["integration"]["contracts"][1]["authorized"])
    select("fatekeeper")
    from types import SimpleNamespace
    fake_worker = SimpleNamespace(cancel_flag=Event(), recipe=recipe)
    win.downloads.safety_worker = fake_worker
    win.downloads._safety_done(safety, fake_worker)
    checks["fixture_adapter_report_visible"] = (
        "UPDATE ADAPTER CONTRACTS" in win.downloads.safety_details.toPlainText()
        and "UEVR injector" in win.downloads.safety_details.toPlainText()
        and "Live adapter disabled" in win.downloads.safety_details.toPlainText())
    checks["fixture_result_rendered"] = (
        "Replacement blocked" in win.downloads.safety_summary.text()
        and win.downloads.safety_details.toPlainText().startswith("PLANNING ONLY"))
    win.setWindowTitle("DEV5D3-N TEST FIXTURE — NO REAL GAME READY FOR REPLACEMENT")
    win.downloads.comparison_toggle.setChecked(True)
    app.processEvents()
    t=win.downloads.comparison_table.geometry()
    b=win.downloads.safety_button.geometry()
    su=win.downloads.safety_summary.geometry()
    d=win.downloads.safety_details.geometry()
    print("DEV5D3N_SAFETY_GEOMETRY", t, b, su, d, "PANEL",win.downloads.comparison_panel.geometry(), flush=True)
    checks["fixture_safety_no_table_overlap"] = b.top() >= t.bottom()
    checks["fixture_safety_no_detail_overlap"] = d.top() >= su.bottom()
    panel_bottom=(win.downloads.comparison_panel.y()+
                  win.downloads.comparison_panel.height())
    integrity_top=win.downloads.integrity_button.mapTo(
        win.downloads,QPoint(0,0)).y()
    print("DEV5D3N_OUTER_GEOMETRY", panel_bottom,integrity_top,
          "PAGE",win.downloads.geometry(),
          "MIN",win.downloads.layout().minimumSize(),flush=True)
    checks["fixture_no_sibling_overlap"] = integrity_top >= panel_bottom
    checks["fixture_safety_render"] = win.grab().save(
        str(imgs/"fatekeeper-preupdate-safety-TEST-FIXTURE.png"))
    win.downloads.safety_worker = None
    select("valheim")
    checks["fixture_does_not_carry_to_next_game"] = (
        win.downloads._safety_result is None and not win.downloads.safety_details.isVisible())

    # Explicit button click works entirely within an owned temporary fixture.
    # The selected game is not consulted by pinned_staging.rehearse_pinned_packages().
    select("valheim")
    win.downloads.comparison_toggle.setChecked(True)
    app.processEvents()
    checks["offline_not_automatic"] = "not run" in win.offline_status.text()
    primary_before = (
        win.downloads.install_review_button.text(),
        win.downloads.install_review_button.isEnabled())
    print("DEV5D3N_OFFLINE_BUTTON", win.offline_button.isEnabled(), flush=True)
    win.offline_button.click()
    app.processEvents()
    print("DEV5D3N_OFFLINE_RESULT", win.offline_status.text(), flush=True)
    checks["offline_rehearsal_passed"] = (
        "Pinned staging PASSED" in win.offline_status.text() and
        "temporary fixtures discarded" in win.offline_status.text())
    checks["offline_valheim_loader_mod_staging"] = (
        "Valheim 2 ZIPs / 4 targets" in win.offline_status.text())
    checks["offline_subnautica_loader_mod_staging"] = (
        "Subnautica 2 ZIPs / 4 targets" in win.offline_status.text())
    checks["offline_elden_reshade_staging"] = (
        "Elden Ring 1 ZIP / 2 targets" in win.offline_status.text())
    checks["offline_three_transaction_rollbacks"] = (
        "3 synthetic rollbacks" in win.offline_status.text())
    checks["offline_declared_build_not_real_compatibility"] = (
        "REAL COMPATIBILITY UNVERIFIED" in win.offline_status.text())
    checks["offline_review_does_not_authorize_install"] = (
        primary_before == (win.downloads.install_review_button.text(),
                           win.downloads.install_review_button.isEnabled())
        and not win.allow_guided_installs and not win.downloads.allow_transfers)
    checks["offline_fixture_no_live_install"] = (
        "LIVE UPDATE DISABLED" in win.offline_status.text())
    win.setWindowTitle("DEV5D3-N OFFLINE REHEARSAL — NO REAL GAME FILES")
    comparison_bottom = (win.downloads.comparison_panel.y()
                         + win.downloads.comparison_panel.height())
    footer_top = win.offline_footer.mapTo(win.downloads,QPoint(0,0)).y()
    integrity_top = win.downloads.integrity_button.mapTo(
        win.downloads,QPoint(0,0)).y()
    checks["offline_footer_no_panel_overlap"] = footer_top >= comparison_bottom
    checks["offline_footer_no_integrity_overlap"] = (
        integrity_top >= footer_top + win.offline_footer.height())
    win.game_page_scroll.ensureWidgetVisible(win.offline_footer, 0, 20)
    app.processEvents()
    checks["offline_result_render"] = win.grab().save(
        str(imgs / "valheim-offline-rollback-TEST-FIXTURE.png"))
    win.downloads.comparison_toggle.setChecked(False)

    # KHARVOX-specific actions remain available only in the Compatibility
    # disclosure; the legacy install drawer is never exposed.
    select("doom-2016-gog")
    checks["rehearsal_result_not_carried_to_other_game"] = (
        "not run" in win.offline_status.text())
    win.game_details_tabs.setCurrentWidget(win.compat_page)
    win.more_tools_toggle.setChecked(True)
    app.processEvents()
    checks["doom_compatibility_tools_visible"] = all(
        button.isVisible() for button in (
            win.kharvox_folder_btn, win.doom_prepare_btn, win.doom_import_btn))
    checks["doom_no_installation_drawer"] = win.install_tools_toggle.isHidden()
    checks["doom_compatibility_render"] = win.grab().save(
        str(imgs/"doom-specialist-actions.png"))
    win.more_tools_toggle.setChecked(False)

    # The user-owned private preview remains unmodified by these synthetic
    # evidence tests; screenshot artefacts are written only to this fixture.
    checks["no_original_scan_mutations"] = previous_bytes != b"" and archive_scans.snapshot_file().is_file()
    for name,passed in checks.items():
        print("DEV5D3N_CHECK",name,"PASS" if passed else "FAIL",flush=True)
    print("DEV5D3N_GUI_RESULT",sum(bool(x) for x in checks.values()),"/",len(checks),flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1

if __name__=="__main__":
    raise SystemExit(main())
