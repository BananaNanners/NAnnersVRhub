"""Hub application updates, separate from game-mod update checks."""
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout)

from . import __version__, app_updates
from .display_time import local_time


class HubUpdateWorker(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, action, value=None, parent=None):
        super().__init__(parent)
        self.action, self.value = action, value
        self.cancel = threading.Event()

    def run(self):
        try:
            if self.action in ("check", "restore"):
                if self.action == "check":
                    result = app_updates.check(force=bool(self.value), cancel=self.cancel)
                else:
                    settings = app_updates.read_settings()
                    result = {"release": app_updates.parse_release(settings["release"]) if settings.get("release") else None,
                              "checked_at": settings.get("checked_at"), "cached": True}
                try:
                    result["bundle"] = app_updates.saved_download()
                except Exception as exc:
                    result["download_warning"] = str(exc)
                self.result.emit(result)
            elif self.action == "download":
                self.result.emit(app_updates.download(self.value, cancel=self.cancel, progress=self.progress.emit))
            else:
                self.result.emit(app_updates.install_bundle(Path(self.value)))
        except Exception as exc:
            self.failed.emit(str(exc))


class HubUpdateController(QObject):
    changed = Signal()
    idle = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worker = None
        self.dialog = None
        self.release = None
        self.bundle = None
        self.checked_at = None
        self.installed = False
        self.closing = False
        self.message = "Check for stable NAnnersVRhub releases on GitHub."
        self.progress_value = 0
        self._auto_pending = False
        self._check_pending = False
        self.preferences_error = None
        try:
            self.preferences = app_updates.read_settings()
        except Exception as exc:
            self.preferences = {"check_on_startup": False, "auto_download": False}
            self.preferences_error = self.message = str(exc)

    @property
    def busy(self):
        return self.worker is not None

    def startup(self):
        if not self.closing and not self.busy:
            self._check_pending = self.preferences["check_on_startup"]
            self.start("restore")

    def show(self):
        if self.dialog is None:
            self.dialog = HubUpdateDialog(self, self.window)
        self.dialog.refresh()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def preference(self, key, value):
        try:
            self.preferences = app_updates.save_settings(**{key: value})
        except Exception as exc:
            self.message = str(exc)
            self.changed.emit()

    def start(self, action, value=None):
        if self.busy or self.closing:
            return
        self._auto_pending = False
        self.progress_value = 0
        self.message = {"restore": "Checking the saved download…", "check": "Checking GitHub…", "download": "Downloading and verifying the source ZIP…",
                        "install": "Installing the verified update…"}[action]
        worker = self.worker = HubUpdateWorker(action, value, self)
        worker.result.connect(self.receive_result)
        worker.failed.connect(self.failed)
        worker.progress.connect(self.progress)
        worker.finished.connect(self.finished)
        self.changed.emit()
        worker.start()

    def receive_result(self, result):
        self.completed(self.worker.action, result)

    def completed(self, action, result):
        if action in ("check", "restore"):
            self.release = result["release"]
            self.checked_at = result["checked_at"]
            self.bundle = result.get("bundle")
            if not self.release:
                self.message = "Choose Check now to look for stable Hub releases."
                self.changed.emit()
                return
            if app_updates.newer(self.release):
                self.message = f"NAnnersVRhub {self.release['version']} is available."
            elif self.release["version"] == __version__:
                self.message = "You have the latest stable Hub."
            else:
                self.message = f"Latest stable: {self.release['version']}. This development build is newer."
            if result.get("download_warning"):
                self.message += "\n" + result["download_warning"]
            if result["cached"]:
                self.message += "\nUsing the last successful check; Check now refreshes GitHub."
            self._auto_pending = (action == "check" and app_updates.newer(self.release) and self.preferences["auto_download"]
                                  and not self.ready_for_release())
        elif action == "download":
            self.bundle = result
            self.message = f"Verified download ready: {result['release']['version']}."
        else:
            self.installed = True
            self.message = f"Installed {result['version']}. Restart the Hub to use it. Rollback is available through nannersvrhub-manage."
        self.changed.emit()

    def ready_for_release(self):
        return bool(self.bundle and self.release and self.bundle["release"] == self.release)

    def failed(self, message):
        self.message = message
        self._auto_pending = False
        self.changed.emit()

    def progress(self, done, total):
        self.progress_value = int(done * 100 / total) if total else 0
        self.changed.emit()

    def finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        pending, self._auto_pending = self._auto_pending, False
        check_pending, self._check_pending = self._check_pending, False
        self.changed.emit()
        self.idle.emit()
        if check_pending and not self.closing:
            self.start("check", False)
        elif pending and not self.closing:
            self.start("download", self.release)

    def shutdown(self):
        self.closing = True
        if self.worker and self.worker.action != "install":
            self.worker.cancel.set()

    def restart(self):
        try:
            subprocess.Popen(app_updates.restart_command(), cwd=Path.home(), start_new_session=True)
        except Exception as exc:
            self.message = f"Could not restart the Hub: {exc}. Open its application-menu entry."
            self.changed.emit()
            return
        self.window.close()


class HubUpdateDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("hubUpdateDialog")
        self.setWindowTitle("NAnnersVRhub updates")
        self.resize(700, 590)
        layout = QVBoxLayout(self)
        self.versions = QLabel()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.checked = QLabel()
        self.startup = QCheckBox("Check for Hub updates when opening the Hub (at most once a day)")
        self.automatic = QCheckBox("Automatically download newer stable releases after a check")
        self.startup.setChecked(controller.preferences["check_on_startup"])
        self.automatic.setChecked(controller.preferences["auto_download"])
        self.startup.toggled.connect(lambda value: controller.preference("check_on_startup", value))
        self.automatic.toggled.connect(lambda value: controller.preference("auto_download", value))
        self.startup.setEnabled(not controller.preferences_error)
        self.automatic.setEnabled(not controller.preferences_error)
        policy = QLabel("Installation and restart are always your choice. Downloads contain the Hub application; game installs and saved tests stay in place.")
        policy.setWordWrap(True)
        self.managed = QLabel()
        self.managed.setWordWrap(True)
        self.can_install = False
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText("Release notes appear after checking GitHub.")
        self.bar = QProgressBar()
        self.check = QPushButton("Check now")
        self.download = QPushButton("Download source ZIP")
        self.install = QPushButton("Install update…")
        self.restart = QPushButton("Restart Hub")
        self.cancel = QPushButton("Cancel download/check")
        self.release = QPushButton("View GitHub releases")
        self.folder = QPushButton("Open verified download")
        self.check.clicked.connect(lambda: controller.start("check", True))
        self.download.clicked.connect(lambda: controller.start("download", controller.release))
        self.install.clicked.connect(self.install_update)
        self.restart.clicked.connect(controller.restart)
        self.cancel.clicked.connect(lambda: controller.worker.cancel.set() if controller.worker else None)
        self.release.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(controller.release["html_url"] if controller.release else app_updates.RELEASES)))
        self.folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(controller.bundle["directory"])) if controller.bundle else None)
        for widget in (self.versions, self.status, self.checked, self.startup, self.automatic, policy, self.managed, self.notes, self.bar):
            layout.addWidget(widget)
        for widgets in ((self.check, self.download, self.install, self.restart), (self.cancel, self.release, self.folder)):
            row = QHBoxLayout()
            for widget in widgets:
                row.addWidget(widget)
            layout.addLayout(row)
        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        layout.addWidget(close)
        controller.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        c = self.controller
        latest = c.release["version"] if c.release else "not checked"
        self.versions.setText(f"Running Hub: {__version__}    •    Latest stable: {latest}")
        self.status.setText(c.message)
        self.checked.setText("Last successful check: " + (local_time(c.checked_at) if c.checked_at else "never"))
        notes = c.release["body"] if c.release else ""
        if self.notes.toPlainText() != notes:
            self.notes.setPlainText(notes)
        self.bar.setVisible(c.busy)
        self.bar.setRange(0, 100 if c.worker and c.worker.action == "download" else 0)
        self.bar.setValue(c.progress_value)
        self.check.setEnabled(not c.busy and not c.installed)
        self.download.setEnabled(bool(c.release) and not c.busy and not c.installed)
        self.cancel.setEnabled(c.busy and c.worker.action != "install")
        self.restart.setVisible(c.installed)
        self.restart.setEnabled(not c.busy)
        self.folder.setEnabled(bool(c.bundle) and not c.busy)
        if c.installed:
            self.managed.setText("Restart uses the installed application's stable launcher.")
        elif not c.busy:
            try:
                app_updates.managed_context()
                self.can_install = True
                self.managed.setText("Managed installation: in-app upgrades and rollback are available.")
            except Exception as exc:
                self.can_install = False
                self.managed.setText(str(exc))
        self.install.setEnabled(bool(self.can_install and c.ready_for_release() and app_updates.newer(c.release) and not c.busy and not c.installed))

    def install_update(self):
        c = self.controller
        if not c.bundle or c.busy:
            return
        answer = QMessageBox.question(self, "Install Hub update?",
                                      f"Install NAnnersVRhub {c.bundle['release']['version']}?\n\n"
                                      "Your current Hub stays open until you restart it. The previous installed version remains available for rollback.",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            c.start("install", c.bundle["directory"])
