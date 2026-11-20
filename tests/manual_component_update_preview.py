# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Run the REAL Hub GUI with update checks enabled and other actions disabled.

Caller MUST provide VRHUB_STATE pointing at a private copy of production state.
The original game tree remains read-only. CLI: --verify or --desktop.
"""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from vrhub import gui, hub
from vrhub.app_update_gui import HubUpdateController


class ReadOnlyUpdatePreview(gui.HubWindow):
    def show_details(self):
        super().show_details()
        self.block_other_actions()

    def block_other_actions(self):
        for button in self.findChildren(QPushButton):
            if button is not self.check_btn:
                button.setEnabled(False)
        self.development_tools_action.setEnabled(False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true",
                        help="Run actual Qt UpdateWorker and inspect GUI results, then exit")
    parser.add_argument("--desktop", action="store_true",
                        help="Open a read-only interactive GUI for manual inspection")
    args = parser.parse_args()
    if args.verify == args.desktop:
        parser.error("Choose exactly one of --verify or --desktop")

    state = Path(os.environ.get("VRHUB_STATE", "")).resolve()
    production = (Path.home() / ".local/share/vrhub/state.json").resolve()
    if not state.is_file() or state == production:
        parser.error("VRHUB_STATE must name an existing, isolated state copy")
    if not os.environ.get("VRHUB_NEXUS_KEY_FILE"):
        parser.error("VRHUB_NEXUS_KEY_FILE must explicitly point to the existing Nexus key")
    if os.environ.get("_NANNERSVRHUB_ROOT"):
        parser.error("Do not use the installed Hub launcher to run this test")
    app = QApplication([sys.argv[0]])
    # No Hub self-updater, even when the normal installed app has startup checks.
    HubUpdateController.startup = lambda self: None
    # Avoid the unrelated VR system scan during this focused GUI test.
    gui.HubWindow.scan_setup = lambda self, *a, **kw: None
    win = ReadOnlyUpdatePreview()
    win.setWindowTitle("NAnnersVRhub — Cyberpunk update TEST (READ-ONLY)")
    win.tabs.setCurrentIndex(1)
    win.game_details_tabs.setCurrentIndex(0)
    def select_cyberpunk():
        for i, row in enumerate(win.rows):
            if row["recipe"]["id"] == "cyberpunk-2077":
                win.table.selectRow(i)
                win.show_details()
                return i
        raise AssertionError("Cyberpunk recipe missing from real GUI")

    select_cyberpunk()
    win.block_other_actions()
    win.show()
    completed = [False]
    expected = {107, 4198, 4575, 7780, 21936}
    target_by_name = {x["name"]: x["nexus_mod"] for x in
                      __import__("vrhub.updates", fromlist=["_update_targets"])._update_targets(
                          hub.load_recipes()["cyberpunk-2077"], hub.state())}

    def read_results():
        if completed[0] or not win.update_results.get("cyberpunk-2077"):
            return
        completed[0] = True
        select_cyberpunk()
        items = win.update_results["cyberpunk-2077"]
        found = {target_by_name[x["name"]] for x in items if x["status"] == "update"}
        summary = win.table.item(next(i for i, row in enumerate(win.rows)
                                      if row["recipe"]["id"] == "cyberpunk-2077"), 4).text()
        body = win.details.toPlainText()
        print("GUI_UPDATE_TARGET_COUNT", len(items), flush=True)
        print("GUI_SUMMARY", summary, flush=True)
        print("GUI_UPDATE_MOD_IDS", ",".join(map(str, sorted(found))), flush=True)
        for mod in sorted(expected):
            item = next(x for x in items if target_by_name[x["name"]] == mod)
            print("GUI_MOD", mod, item["status"], item["detail"], flush=True)
        if args.verify:
            from vrhub import updates
            by_id = {target_by_name[x["name"]]: x for x in items}
            checks = {
                "all_15_components": len(items) == 15 and len(by_id) == 15,
                "five_known_mods_present": all(
                    mod in by_id and by_id[mod]["status"] in {"update", "current"}
                    for mod in expected),
                "table_summary_matches_logic": summary == updates.summarize(items),
                "details_include_updates": all(by_id[mod]["detail"] in body for mod in expected),
                "groups_visibly_separated": all(heading in body for heading in (
                    "Updates available (", "Up to date (", "Needs manual review (",
                    "Not installed (")),
                "read_only_description": "does not download, install, remove" in body,
                "refresh_button_label": win.check_btn.text() == "Refresh update status",
                "cyber_engine_tweaks_visible": "Cyber Engine Tweaks" in body,
                "no_api_errors": all(x["status"] != "error" for x in items),
                "install_disabled": not win.install_btn.isEnabled(),
                "uninstall_disabled": not win.uninstall_btn.isEnabled(),
                "self_update_disabled": not win.hub_update_btn.isEnabled(),
            }
            for name, passed in checks.items():
                print("GUI_CHECK", name, "PASS" if passed else "FAIL", flush=True)
            if all(checks.values()):
                print("GUI_VERIFICATION PASS", flush=True)
                QTimer.singleShot(900, app.quit)
            else:
                print("GUI_VERIFICATION FAIL", file=sys.stderr, flush=True)
                QTimer.singleShot(900, lambda: app.exit(1))
        else:
            print("READ_ONLY_TEST_WINDOW_READY; close the window when finished.", flush=True)

    def poll():
        if not completed[0]:
            read_results()
    ticker = QTimer()
    ticker.timeout.connect(poll)
    ticker.start(400)

    if args.verify:
        def timeout():
            if not completed[0]:
                print("GUI_VERIFICATION FAIL: update worker did not complete", file=sys.stderr)
                app.exit(2)
        QTimer.singleShot(90000, timeout)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
