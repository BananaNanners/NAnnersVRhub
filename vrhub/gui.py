"""NAnnersVRhub Qt window. Run with:  python -m vrhub.gui   (needs PySide6)"""
import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from . import hub, runtime, updates
from .cli import _roots


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
        self.setWindowTitle("NAnnersVRhub")
        self.resize(1150, 640)
        self.rows: list[dict] = []
        self.update_results: dict = {}
        self.worker: UpdateWorker | None = None

        title = QLabel("NAnnersVRhub")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.runtime_label = QLabel()
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
        self.check_btn = QPushButton("Check for updates")
        self.mark_btn = QPushButton("Mark as up to date")
        self.key_btn = QPushButton("Nexus API key…")
        self.verify_btn = QPushButton("Verify mods")
        refresh_btn = QPushButton("Refresh")
        self.install_btn.clicked.connect(self.install)
        self.uninstall_btn.clicked.connect(self.uninstall)
        self.profile_btn.clicked.connect(self.install_profile)
        self.unprofile_btn.clicked.connect(self.uninstall_profile)
        self.copy_btn.clicked.connect(self.copy_options)
        self.inject_btn.clicked.connect(self.run_injector)
        self.check_btn.clicked.connect(self.check_updates)
        self.mark_btn.clicked.connect(self.mark_current)
        self.key_btn.clicked.connect(self.set_nexus_key)
        self.verify_btn.clicked.connect(self.verify_mods)
        refresh_btn.clicked.connect(self.refresh)

        left = QVBoxLayout()
        left.addWidget(self.table)
        left.addLayout(_row(self.install_btn, self.uninstall_btn, self.profile_btn, self.unprofile_btn))
        left.addLayout(_row(self.copy_btn, self.inject_btn, self.verify_btn))
        left.addLayout(_row(self.check_btn, self.mark_btn, self.key_btn, refresh_btn))
        main = QHBoxLayout()
        main.addLayout(left, 5)
        main.addWidget(self.details, 6)
        root = QVBoxLayout()
        root.addWidget(title)
        root.addWidget(self.runtime_label)
        root.addLayout(main)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.refresh()
        self.check_updates()  # quietly, in the background

    def current(self) -> dict | None:
        idx = self.table.currentRow()
        return self.rows[idx]["recipe"] if 0 <= idx < len(self.rows) else None

    def refresh(self):
        keep = self.table.currentRow()
        ok = runtime.is_wivrn()
        self.runtime_label.setText("OpenXR runtime: WiVRn is active" if ok else
                                   "OpenXR runtime: WiVRn is NOT the active runtime (start/set up WiVRn)")
        self.runtime_label.setStyleSheet("color: %s; font-weight: bold;" % ("#2e9e4f" if ok else "#c0392b"))
        self.rows = hub.game_rows(_roots())
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            rid = row["recipe"]["id"]
            profile = ("Installed" if row["profile_installed"] else "Not installed") if row["has_profile"] else "—"
            cells = [row["recipe"]["name"],
                     "Found" if row["game_found"] else "Not found",
                     (f"{row['components'][0]}/{row['components'][1]} mods"
                      + ("" if row["components"][2] else " (NOT READY)")) if row["components"] else
                     ("Installed" if row["mod_installed"] else "Not installed"),
                     profile,
                     updates.summarize(self.update_results.get(rid))]
            for c, text in enumerate(cells):
                self.table.setItem(i, c, QTableWidgetItem(text))
        if self.rows:
            self.table.selectRow(keep if 0 <= keep < len(self.rows) else 0)
        self.show_details()

    def show_details(self):
        r = self.current()
        self.details.setHtml(hub.details_html(r, self.update_results.get(r["id"]), hub.verify(r)) if r else "")
        self.inject_btn.setEnabled(bool(r and r.get("method") == "uevr"))
        self.verify_btn.setEnabled(bool(r and r.get("components")))
        has_profile = bool(r and "profile" in r)
        self.profile_btn.setEnabled(has_profile)
        self.unprofile_btn.setEnabled(has_profile)

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

    def verify_mods(self):
        r = self.current()
        rep = r and hub.verify(r)
        if rep:
            QMessageBox.information(self, "Mod check", hub.verify_text(rep))

    def copy_options(self):
        r = self.current()
        if r:
            QApplication.clipboard().setText(hub.launch_options(r))


def main() -> int:
    app = QApplication(sys.argv)
    win = HubWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
