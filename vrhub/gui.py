"""NAnnersVRhub Qt window. Run with:  python -m vrhub.gui   (needs PySide6)"""
import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from . import __version__, hub, runtime, updates
from .handlers import get_handler
from .cli import _roots
from .theme import BLUE, GREEN, LOGO_PATH, MUTED, RED, STYLESHEET, TEXT, YELLOW


class UpdateWorker(QThread):
    """Checks GitHub in the background so the window never freezes."""
    done = Signal(object)

    def run(self):
        try:
            recipes = hub.load_recipes()
            for r in recipes.values():  # fill in real mod names (only if a Nexus key is set)
                hub.refresh_component_names(r)
            res = updates.check_all(recipes, hub.state())
        except Exception:  # never let a network hiccup crash the app
            res = {}
        self.done.emit(res)


def _row(*buttons):
    lay = QHBoxLayout()
    for b in buttons:
        lay.addWidget(b)
    return lay


class HubWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"NAnnersVRhub {__version__}")
        self.resize(1220, 720)
        self.setStyleSheet(STYLESHEET)
        if LOGO_PATH.is_file():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.rows: list[dict] = []
        self.update_results: dict = {}
        self.worker: UpdateWorker | None = None

        header = QFrame()
        header.setObjectName("brandHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(14, 10, 16, 10)
        logo = QLabel()
        if LOGO_PATH.is_file():
            pix = QPixmap(str(LOGO_PATH)).scaled(70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        logo.setFixedSize(74, 74)
        header_row.addWidget(logo)
        brand = QVBoxLayout()
        brand_title = QLabel(f"NAnnersVRhub  {__version__}")
        brand_title.setObjectName("brandTitle")
        brand_tagline = QLabel("PLAY  •  TWEAK  •  EXPLORE  •  REPEAT")
        brand_tagline.setObjectName("brandTagline")
        brand_subline = QLabel("LINUX GAMING  •  PCVR  •  MODS  •  MORE FREEDOM")
        brand_subline.setObjectName("brandSubline")
        brand.addWidget(brand_title)
        brand.addWidget(brand_tagline)
        brand.addWidget(brand_subline)
        header_row.addLayout(brand)
        header_row.addStretch(1)
        channel_mark = QLabel("🍌  BANANANNERS")
        channel_mark.setStyleSheet(f"color: {YELLOW}; font-weight: 800; font-size: 13px;")
        header_row.addWidget(channel_mark, 0, Qt.AlignVCenter)

        self.runtime_label = QLabel()
        self.runtime_label.setObjectName("runtimePill")
        self.live_status_label = QLabel()
        self.live_status_label.setObjectName("liveStatus")
        self.live_status_label.hide()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Game", "Steam install", "Mod", "Profile", "Updates"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.show_details)

        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.install_btn = QPushButton("Install mod file…")
        self.uninstall_btn = QPushButton("Uninstall mod")
        self.profile_btn = QPushButton("Install profile…")
        self.unprofile_btn = QPushButton("Remove profile")
        self.copy_btn = QPushButton("Copy launch options")
        self.inject_btn = QPushButton("Run UEVR injector")
        self.game_launch_btn = QPushButton("Launch game tool")
        self.game_play_btn = QPushButton("Launch game")
        self.check_btn = QPushButton("Check for updates")
        self.mark_btn = QPushButton("Mark as up to date")
        self.key_btn = QPushButton("Nexus API key…")
        self.verify_btn = QPushButton("Verify mods")
        self.preflight_btn = QPushButton("Preflight")
        self.inspect_btn = QPushButton("Inspect archive…")
        self.diag_btn = QPushButton("Copy diagnostics")
        self.bridge_log_btn = QPushButton("Open bridge log")
        self.bridge_log_btn.setObjectName("secondaryAction")
        refresh_btn = QPushButton("Refresh")
        self.install_btn.clicked.connect(self.install)
        self.uninstall_btn.clicked.connect(self.uninstall)
        self.profile_btn.clicked.connect(self.install_profile)
        self.unprofile_btn.clicked.connect(self.uninstall_profile)
        self.copy_btn.clicked.connect(self.copy_options)
        self.inject_btn.clicked.connect(self.run_injector)
        self.game_launch_btn.clicked.connect(self.launch_game_tool)
        self.game_play_btn.clicked.connect(self.launch_game_play)
        self.check_btn.clicked.connect(self.check_updates)
        self.mark_btn.clicked.connect(self.mark_current)
        self.key_btn.clicked.connect(self.set_nexus_key)
        self.verify_btn.clicked.connect(self.verify_mods)
        self.preflight_btn.clicked.connect(self.preflight)
        self.preflight_btn.setObjectName("primaryAction")
        self.game_launch_btn.setObjectName("primaryAction")
        self.game_play_btn.setObjectName("primaryAction")
        self.inspect_btn.clicked.connect(self.inspect_archive)
        self.diag_btn.clicked.connect(self.copy_diagnostics)
        self.bridge_log_btn.clicked.connect(self.open_bridge_log)
        refresh_btn.clicked.connect(self.refresh)

        left = QVBoxLayout()
        left.addWidget(self.table)
        left.addLayout(_row(self.install_btn, self.uninstall_btn, self.profile_btn, self.unprofile_btn))
        left.addLayout(_row(self.copy_btn, self.inject_btn, self.game_launch_btn, self.game_play_btn, self.verify_btn, self.preflight_btn))
        left.addLayout(_row(self.inspect_btn, self.diag_btn, self.bridge_log_btn, self.check_btn, self.mark_btn))
        left.addLayout(_row(self.key_btn, refresh_btn))
        main = QHBoxLayout()
        main.setSpacing(10)
        main.addLayout(left, 5)
        main.addWidget(self.details, 6)
        status_row = QHBoxLayout()
        status_row.addWidget(self.runtime_label)
        status_row.addWidget(self.live_status_label)
        status_row.addStretch(1)
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(9)
        root.addWidget(header)
        root.addLayout(status_row)
        root.addLayout(main)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(2000)
        self.status_timer.timeout.connect(self.update_live_status)
        self.status_timer.start()
        self.refresh()
        self.check_updates()  # quietly, in the background

    def current(self) -> dict | None:
        idx = self.table.currentRow()
        return self.rows[idx]["recipe"] if 0 <= idx < len(self.rows) else None

    def refresh(self):
        keep = self.table.currentRow()
        ok = runtime.is_wivrn()
        self.runtime_label.setText("●  WiVRn ACTIVE" if ok else "●  WiVRn NOT ACTIVE")
        self.runtime_label.setStyleSheet(f"color: {GREEN if ok else RED};")
        self.rows = hub.game_rows(_roots())
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            rid = row["recipe"]["id"]
            profile = ("Installed" if row["profile_installed"] else "Not installed") if row["has_profile"] else "—"
            method = row["recipe"].get("method", "file")
            mod_text = (f"{row['components'][0]}/{row['components'][1]} mods"
                        + ("" if row["components"][2] else " (NOT READY)")) if row["components"] else \
                       ("Guided setup" if method == "guide" else
                        ("Installed" if row["mod_installed"] else "Not installed"))
            cells = [row["recipe"]["name"],
                     "Found" if row["game_found"] else "Not found",
                     mod_text, profile,
                     updates.summarize(self.update_results.get(rid))]
            for c, text in enumerate(cells):
                self.table.setItem(i, c, QTableWidgetItem(text))
        if self.rows:
            self.table.selectRow(keep if 0 <= keep < len(self.rows) else 0)
        self.show_details()

    def show_details(self):
        r = self.current()
        self.details.setHtml(hub.details_html(r, self.update_results.get(r["id"]), hub.verify(r)) if r else "")
        can_install = bool(r and get_handler(r).install_supported(r))
        self.install_btn.setEnabled(can_install)
        self.uninstall_btn.setEnabled(bool(r and r.get("method") != "guide"))
        self.inject_btn.setEnabled(bool(r and r.get("method") == "uevr"))
        label = hub.game_launcher_label(r) if r else None
        self.game_launch_btn.setText(label or "Launch game tool")
        self.game_launch_btn.setVisible(bool(label))
        self.game_launch_btn.setEnabled(bool(label))
        play_label = hub.game_play_label(r) if r else None
        self.game_play_btn.setText(play_label or "Launch game")
        self.game_play_btn.setVisible(bool(play_label))
        self.game_play_btn.setEnabled(bool(play_label))
        self.verify_btn.setEnabled(bool(r and r.get("components")))
        self.preflight_btn.setEnabled(bool(r))
        self.inspect_btn.setEnabled(bool(r and r.get("method") == "gameroot"))
        has_profile = bool(r and "profile" in r)
        self.profile_btn.setEnabled(has_profile)
        self.unprofile_btn.setEnabled(has_profile)
        self.bridge_log_btn.setVisible(bool(r and hub.game_bridge_log(r)))
        if r:
            self.bridge_log_btn.setText(hub.game_bridge_log_label(r))
        self.update_live_status()

    def update_live_status(self):
        r = self.current()
        if not r:
            self.live_status_label.hide()
            return
        try:
            status = hub.game_live_status(r, _roots())
        except (RuntimeError, OSError):
            status = {}
        if not status:
            self.live_status_label.hide()
            return
        game = bool(status.get("game"))
        if "mo2" in status:
            mo2 = bool(status.get("mo2"))
            self.live_status_label.setText(
                f"MO2: {'RUNNING' if mo2 else 'IDLE'}   •   SKYRIM VR: {'RUNNING' if game else 'IDLE'}")
            colour = GREEN if game else (YELLOW if mo2 else MUTED)
        else:
            label = status.get("label", r.get("name", "GAME")).upper()
            self.live_status_label.setText(f"{label}: {'RUNNING' if game else 'IDLE'}")
            colour = GREEN if game else MUTED
        self.live_status_label.setStyleSheet(f"color: {colour};")
        self.live_status_label.show()

    def open_bridge_log(self):
        r = self.current()
        path = r and hub.game_bridge_log(r)
        if not path:
            return
        if not path.exists():
            QMessageBox.information(self, "Debug log", f"No debug log exists yet.\n\nExpected path:\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ---- update checking -------------------------------------------------
    def check_updates(self):
        if self.worker and self.worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking…")
        self.worker = UpdateWorker()
        self.worker.done.connect(self._updates_done)
        self.worker.start()

    def _updates_done(self, results):
        self.update_results = results or {}
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for updates")
        self.refresh()

    def mark_current(self):
        r = self.current()
        if not r:
            return
        done = hub.mark_current(r)
        QMessageBox.information(self, "Marked", "Marked as up to date." if done else
                                "Nothing installed through the hub to mark.")
        self.check_updates()
        self.refresh()

    def set_nexus_key(self):
        text, ok = QInputDialog.getText(
            self, "Nexus API key",
            "Paste your personal Nexus API key. It is stored only on this computer.\n"
            "(Leave empty to remove a saved key.)", QLineEdit.Password)
        if not ok:
            return
        text = text.strip()
        if not text:
            if updates.get_key() and QMessageBox.question(self, "Remove key", "Remove the saved Nexus API key?") \
                    == QMessageBox.Yes:
                updates.clear_key()
                self.check_updates()
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            name = updates.validate_key(text)
        except (OSError, ValueError, KeyError) as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Key not saved", f"Couldn't validate that key: {e}")
            return
        QApplication.restoreOverrideCursor()
        updates.set_key(text)
        QMessageBox.information(self, "Key saved", f"Accepted for Nexus account '{name}'.")
        self.check_updates()

    # ---- actions ---------------------------------------------------------
    def _pick(self, title: str) -> Path | None:
        f, _ = QFileDialog.getOpenFileName(self, title, str(Path.home() / "Downloads"), "Mod files (*.zip *.pak)")
        return Path(f) if f else None

    def _run(self, fn, ok_title: str, ok_text) -> None:
        try:
            result = fn()
        except (RuntimeError, OSError, zipfile.BadZipFile) as e:
            QMessageBox.warning(self, "Something went wrong", str(e))
            return
        QMessageBox.information(self, ok_title, ok_text(result))
        self.refresh()

    def _pick_many(self, title: str) -> list[Path]:
        files, _ = QFileDialog.getOpenFileNames(self, title, str(Path.home() / "Downloads"),
                                                "Mod files (*.zip *.7z *.rar *.pak)")
        return [Path(f) for f in files]

    def install(self):
        r = self.current()
        files = r and self._pick_many(f"Choose the {r['name']} file(s) you downloaded")
        if files:
            self._run(lambda: hub.install_many(r, files, _roots()), "Installed",
                      lambda out: (f"Installed {len(out)} files." if len(out) > 8 else
                                   "Installed:\n" + "\n".join(map(str, out))) +
                      "\n\nNow set the Steam launch options shown on the right.")

    def install_profile(self):
        r = self.current()
        f = r and self._pick("Choose the profile .zip you downloaded")
        if f:
            self._run(lambda: hub.install_profile(r, f, _roots()), "Profile installed",
                      lambda files: f"Installed {len(files)} profile files.\n"
                      "Anything that was there before is backed up.")

    def uninstall(self):
        r = self.current()
        if r and QMessageBox.question(self, "Uninstall", f"Remove the mod files for {r['name']}?") == QMessageBox.Yes:
            hub.uninstall(r["id"])
            self.refresh()

    def uninstall_profile(self):
        r = self.current()
        if r and QMessageBox.question(self, "Remove profile",
                                      f"Remove the profile for {r['name']} and restore the backup?") == QMessageBox.Yes:
            hub.uninstall(f"{r['id']}:profile")
            self.refresh()

    def run_injector(self):
        r = self.current()
        if not r:
            return
        try:
            hub.launch_injector(r, _roots())
        except (RuntimeError, OSError) as e:
            QMessageBox.warning(self, "Could not start injector", str(e))

    def launch_game_tool(self):
        r = self.current()
        if not r:
            return
        try:
            proc = hub.launch_game_tool(r, _roots())
        except (RuntimeError, OSError) as e:
            QMessageBox.warning(self, "Could not launch", str(e))
            return
        store = r.get("store", "steam")
        if store == "heroic-gog":
            via = "Heroic's configured prefix through umu-run"
        elif r.get("handler") == "skyrim-vr":
            via = "Steam"
        else:
            via = "the configured launcher"
        QMessageBox.information(self, "Launch request sent",
                                f"{hub.game_launcher_label(r) or 'Game launcher'} started through {via}.")

    def launch_game_play(self):
        r = self.current()
        if not r:
            return
        try:
            hub.launch_game_play(r, _roots())
        except (RuntimeError, OSError) as e:
            QMessageBox.warning(self, "Could not launch game", str(e))
            return
        store = r.get("store", "steam")
        via = "Heroic" if store == "heroic-gog" else ("Steam/MO2" if r.get("handler") == "skyrim-vr" else "Steam")
        QMessageBox.information(self, "Launch request sent",
                                f"{hub.game_play_label(r) or 'Game'} request sent through {via}.")

    def verify_mods(self):
        r = self.current()
        rep = r and hub.verify(r)
        if rep:
            QMessageBox.information(self, "Mod check", hub.verify_text(rep))

    def preflight(self):
        r = self.current()
        if r:
            rep = hub.preflight(r, _roots())
            QMessageBox.information(self, "Preflight", hub.preflight_text(rep))

    def inspect_archive(self):
        r = self.current()
        f = None
        if r:
            name, _ = QFileDialog.getOpenFileName(
                self, "Choose a mod archive to inspect (nothing will be installed)",
                str(Path.home() / "Downloads"), "Mod archives (*.zip *.7z *.rar)")
            f = Path(name) if name else None
        if not f:
            return
        try:
            rep = hub.inspect_archive(r, f)
        except (RuntimeError, OSError, zipfile.BadZipFile) as e:
            QMessageBox.warning(self, "Archive rejected", str(e))
            return
        QMessageBox.information(self, "Archive inspection", hub.inspect_text(rep))

    def copy_options(self):
        r = self.current()
        if r:
            QApplication.clipboard().setText(hub.launch_options(r))

    def copy_diagnostics(self):
        r = self.current()
        if r:
            QApplication.clipboard().setText(hub.diagnostics(r, _roots()))
            QMessageBox.information(self, "Diagnostics copied",
                                    "A paste-friendly diagnostic summary is now on the clipboard.")


def main() -> int:
    app = QApplication(sys.argv)
    win = HubWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
