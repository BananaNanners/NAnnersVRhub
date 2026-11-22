# SPDX-License-Identifier: GPL-3.0-only
"""Isolated Dev5D3-C preview and rendered combined-review checks.

Uses caller-provided private state and saved scans. Never restores prior scans,
runs transfers or permits game writes.
"""
import argparse
import os
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox
from vrhub import gui, hub
from vrhub.app_update_gui import HubUpdateController
from vrhub.uevr_dependency_review_gui import DependencyReviewDialog
from tests.manual_launcher_dev5d3b_preview import LauncherPreview


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--show", action="store_true")
    mode.add_argument("--verify", action="store_true")
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
    win = LauncherPreview()
    win.allow_guided_installs = False
    win.downloads.allow_transfers = False
    win.setWindowTitle("NAnnersVRhub 0.5.5-dev5D3c — UEVR REVIEW (NO GAME WRITES)")
    brand = win.findChild(QLabel, "brandTitle")
    if brand:
        brand.setText("NAnnersVRhub  0.5.5-dev5D3c · PREVIEW")
    win.tabs.setCurrentIndex(1)

    def select(rid):
        win.sidebar.game_list.setCurrentRow(next(
            i for i, row in enumerate(win.rows) if row["recipe"]["id"] == rid))
        win.game_details_tabs.setCurrentWidget(win.downloads)
        win.install_tools_toggle.setChecked(False)
        win.library_toggle.setChecked(False)
        app.processEvents()
        win.disable_mutations()

    select("fatekeeper")
    win.show()
    app.processEvents()
    win.disable_mutations()
    if opts.show:
        print("DEV5D3C DESKTOP READY — Fatekeeper selected; no game writes or transfers.", flush=True)
        return app.exec()

    checks = {}
    screenshots = state.parent / "renders"
    screenshots.mkdir(exist_ok=True)
    for rid in ("fatekeeper", "hogwarts-legacy"):
        select(rid)
        checks[rid + "_pair_action"] = win.downloads.install_review_button.text() == "Review installation"
        checks[rid + "_pair_enabled"] = win.downloads.install_review_button.isEnabled()
        checks[rid + "_preview_gates"] = not win.allow_guided_installs and not win.downloads.allow_transfers
        checks[rid + "_tab_render"] = win.grab().save(str(screenshots / (rid + "-tab.png")))
        received = []
        def inspect(dialog):
            received.append(dialog.plan)
            dialog.show()
            app.processEvents()
            checks[rid + "_two_archives"] = dialog.archives.rowCount() == 2
            checks[rid + "_apply_disabled"] = not dialog.apply_button.isEnabled()
            checks[rid + "_inventory_collapsed"] = not dialog.inventory.isVisible()
            checks[rid + "_blockers_visible"] = bool(dialog.plan.blockers) and all(
                message in dialog.blockers.text() for message in dialog.plan.blockers)
            checks[rid + "_review_render"] = dialog.grab().save(str(screenshots / (rid + "-review.png")))
            dialog.inventory_toggle.click()
            app.processEvents()
            checks[rid + "_inventory_expands"] = dialog.inventory.isVisible()
            dialog.close()
            return QDialog.Rejected
        with mock.patch.object(DependencyReviewDialog, "exec", inspect), mock.patch.object(
                win.downloads, "_choose_archive_candidate", return_value=None) as chooser, mock.patch.object(
                win, "_pick") as picker, mock.patch.object(win, "_pick_many") as many, mock.patch.object(
                QMessageBox, "warning") as warning, mock.patch.object(hub, "install_many") as install, mock.patch.object(
                hub, "install_profile") as profile, mock.patch.object(hub, "install") as legacy:
            win.downloads.install_review_button.click()
            checks[rid + "_no_picker"] = not chooser.called and not picker.called and not many.called
            checks[rid + "_no_writes"] = not install.called and not profile.called and not legacy.called
            checks[rid + "_review_opened"] = len(received) == 1 and not warning.called
            if warning.called:
                print("REVIEW REFUSED", rid, warning.call_args, flush=True)
    for name, ok in checks.items():
        print("DEV5D3C_CHECK", name, "PASS" if ok else "FAIL", flush=True)
    print("DEV5D3C_GUI_RESULT", sum(bool(ok) for ok in checks.values()), "/", len(checks), flush=True)
    win.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
