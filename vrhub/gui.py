# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NAnnersVRhub Qt window. Run with:  python -m vrhub.gui   (needs PySide6)"""
import sys
import subprocess
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QSize
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QComboBox, QDialog, QDialogButtonBox, QFormLayout, QListWidget, QPlainTextEdit,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
                               QScrollArea, QSizePolicy, QStyle)

from . import __version__, app_updates, compatibility, heroic_epic, hub, live_tests, log_diagnostics, runtime, support_report, system_scan, updates, game_saves
from .handlers import get_handler
from .cli import _roots
from .display_time import age_text, filename_stamp, local_time
from .theme import BG, BLUE, GREEN, LOGO_PATH, MUTED, RED, STYLESHEET, TEXT, YELLOW
from .app_update_gui import HubUpdateController
from .controller_gui import ControllerBindingsPage
from .launcher_ui import LauncherSidebar, GameBanner
from .dashboard_ui import GameDashboard, ResponsiveQuickActions, snapshot as dashboard_snapshot
from .mod_updates_gui import ModUpdatesPage
from .downloads_gui import GuidedDownloadsPage
from .install_review_gui import InstallReviewDialog
from .profile_review_gui import ProfileReviewDialog
from . import profile_safety
from . import artwork, download_planner, install_review
from .table_columns import enable_spreadsheet_columns


def _tab_icon_with_color(original: QIcon, color: str, edge: int = 18) -> QIcon:
    """Retain the theme/fallback pictogram while matching its tab contrast."""
    pixmap = original.pixmap(QSize(edge, edge))
    if pixmap.isNull():
        return original
    painter = QPainter(pixmap)
    try:
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
    finally:
        painter.end()
    return QIcon(pixmap)



class HeroicInjectorDialog(QDialog):
    def __init__(self, recipe, parent=None, *, launch=None, error=None):
        super().__init__(parent)
        self.info = heroic_epic.context(recipe)
        exe = hub.injector_path(recipe)
        self.setObjectName("heroicInjectorDialog")
        self.setWindowTitle("UEVR injector — Hogwarts Legacy")
        self.resize(690, 360)
        layout = QVBoxLayout(self)
        self.launch = launch
        self.status = QLabel(error or ("Injector launch requested using Heroic's selected runner and prefix." if launch else "Use the manual Heroic route below."))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        text = QLabel("Keep Hogwarts Legacy running after shader loading. In the injector, choose the HogwartsLegacy process and OpenXR, then Inject. Close the in-game overlay with Insert before checking immersion. Closing this Hub dialog leaves the injector and game running.")
        text.setWordWrap(True)
        layout.addWidget(text)
        manual = QLabel("Manual fallback: in this game's Heroic Settings → Wine → Run EXE on prefix, select UEVRInjector.exe below. Use this route for Flatpak Heroic or if the one-click launch fails.")
        manual.setWordWrap(True)
        layout.addWidget(manual)
        self.path = QLineEdit(str(exe))
        self.path.setReadOnly(True)
        layout.addWidget(self.path)
        selected = QLabel(f"Epic app: {self.info['appid']}\nConfigured runner: {self.info['wine'].get('name', 'review in Heroic')}")
        selected.setWordWrap(True)
        layout.addWidget(selected)
        self.copy = QPushButton("Copy injector path")
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.path.text()))
        self.folder = QPushButton("Open injector folder")
        self.folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(exe.parent))))
        self.open = QPushButton("Open Heroic")
        self.open.clicked.connect(self.open_heroic)
        row = QHBoxLayout()
        for button in (self.copy, self.folder, self.open):
            row.addWidget(button)
        layout.addLayout(row)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(140)
        self.output.hide()
        layout.addWidget(self.output)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_launch)
        self.finished.connect(self.timer.stop)
        if launch is not None:
            self.timer.start(500)
            self.check_launch()

    def check_launch(self):
        code = self.launch.poll()
        if code is None:
            return
        self.timer.stop()
        if code:
            self.status.setText(f"Injector launcher exited with code {code}. Use the manual Heroic route below if no injector appeared.")
            self.output.setPlainText(self.launch.output_tail()[-6000:])
            self.output.show()
        else:
            self.status.setText("Launcher exited without an error. Check the UEVR window; this does not confirm injection or VR rendering.")

    def open_heroic(self):
        try:
            subprocess.Popen(heroic_epic.command(self.info, play=False), start_new_session=True)
        except (RuntimeError, OSError) as exc:
            QMessageBox.warning(self, "Open Heroic manually", str(exc))


class ScanWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, previous=None, parent=None):
        super().__init__(parent)
        self.previous = previous

    def run(self):
        try:
            self.done.emit(system_scan.refresh_live(self.previous) if self.previous else system_scan.scan())
        except Exception as exc:
            self.failed.emit(str(exc))


class LogWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, recipe, roots, files, parent=None):
        super().__init__(parent)
        self.recipe, self.roots, self.files = recipe, roots, files

    def run(self):
        try:
            self.done.emit(log_diagnostics.report(self.recipe, self.roots, self.files))
        except Exception as exc:
            self.failed.emit(str(exc))


class LogDiagnosticsDialog(QDialog):
    def __init__(self, recipe, roots=None, parent=None):
        super().__init__(parent)
        self.recipe, self.roots, self.files = recipe, roots, None
        self.worker = None
        self.log_report = None
        self._closing = False

        self.setObjectName("logDiagnosticsDialog")
        self.setWindowTitle("Game log diagnostics — " + recipe["name"])
        self.resize(900, 700)
        layout = QVBoxLayout(self)
        title = QLabel(recipe["name"])
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {YELLOW}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        intro = QLabel("Inspect recent log tails for known errors. Findings are historical evidence; they do not change compatibility checks or gameplay test history.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.auto_btn = QPushButton("Scan expected log")
        self.choose_btn = QPushButton("Choose log files…")
        self.refresh_btn = QPushButton("Refresh")
        self.copy_btn = QPushButton("Copy log report")
        self.copy_btn.setEnabled(False)
        self.auto_btn.clicked.connect(self.scan_expected)
        self.choose_btn.clicked.connect(self.choose_files)
        self.refresh_btn.clicked.connect(self.refresh)
        self.copy_btn.clicked.connect(self.copy_report)
        layout.addLayout(_row(self.auto_btn, self.choose_btn, self.refresh_btn, self.copy_btn))
        self.summary = QLabel("Ready to inspect the expected log path.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        QTimer.singleShot(0, self.refresh)

    def scan_expected(self):
        self.files = None
        self.refresh()

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose logs for " + self.recipe["name"], "", "Log/text files (*.log *.txt);;All files (*)")
        if not files:
            return
        if len(files) > log_diagnostics.MAX_FILES:
            self.summary.setText("Choose at most four log files.")
            return
        self.files = files
        self.refresh()

    def refresh(self):
        if self.worker or self._closing:
            return
        self.log_report = None
        self.copy_btn.setEnabled(False)
        for button in (self.auto_btn, self.choose_btn, self.refresh_btn):
            button.setEnabled(False)
        self.summary.setText("Reading bounded log tails…")
        self.details.clear()
        self.worker = LogWorker(self.recipe, self.roots, self.files, self)
        self.worker.done.connect(self.show_report)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(self.scan_finished)
        self.worker.start()

    def show_report(self, report):
        self.log_report = report
        self.summary.setText(report["status"] + " — modification times do not identify a session.")
        self.details.setPlainText(log_diagnostics.report_text(report))
        self.copy_btn.setEnabled(True)

    def show_error(self, message):
        self.summary.setText("Log diagnostics unavailable")
        self.details.setPlainText(message)

    def scan_finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        for button in (self.auto_btn, self.choose_btn, self.refresh_btn):
            button.setEnabled(True)
        if self._closing:
            super().reject()

    def copy_report(self):
        if self.log_report is not None:
            QApplication.clipboard().setText(log_diagnostics.report_text(self.log_report))
            self.summary.setText("Log report copied. Review paths and excerpts before sharing.")

    def reject(self):
        self._closing = True
        if not self.worker:
            super().reject()

    def closeEvent(self, event):
        self._closing = True
        if self.worker:
            event.ignore()
            return
        super().closeEvent(event)


class SupportReportWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, recipe, roots, files, parent=None):
        super().__init__(parent)
        self.recipe, self.roots, self.files = recipe, roots, files

    def run(self):
        try:
            self.done.emit(support_report.collect(self.recipe, self.roots, self.files))
        except Exception as exc:
            self.failed.emit(str(exc))


class SupportReportDialog(QDialog):
    def __init__(self, recipe, roots=None, parent=None):
        super().__init__(parent)
        self.recipe, self.roots = recipe, roots
        self.files = None
        self.worker = None
        self.snapshot = None
        self.view = None
        self._closing = False
        self.setObjectName("supportReportDialog")
        self.setWindowTitle("Combined support report — " + recipe["name"])
        self.resize(980, 800)
        layout = QVBoxLayout(self)
        title = QLabel(recipe["name"])
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {YELLOW}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        intro = QLabel("Preview a fresh system scan, compatibility checks, log findings and the latest local gameplay test. Review paths, notes and excerpts before sharing. Nothing is uploaded automatically.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.refresh_btn = QPushButton("Collect new snapshot")
        self.refresh_btn.setToolTip("Read the current sources again. Copy and Save keep the already captured snapshot.")
        self.choose_btn = QPushButton("Choose log files…")
        self.auto_btn = QPushButton("Use expected log")
        self.refresh_btn.clicked.connect(self.refresh)
        self.choose_btn.clicked.connect(self.choose_files)
        self.auto_btn.clicked.connect(self.use_expected)
        layout.addLayout(_row(self.refresh_btn, self.choose_btn, self.auto_btn))
        options = QHBoxLayout()
        self.home_check = QCheckBox("Replace this Linux home path with ~")
        self.home_check.setChecked(True)
        self.excerpts_check = QCheckBox("Include log excerpts")
        self.excerpts_check.setChecked(True)
        self.format_combo = QComboBox()
        self.format_combo.addItem("Text report", False)
        self.format_combo.addItem("JSON report", True)
        for checkbox in (self.home_check, self.excerpts_check):
            checkbox.toggled.connect(self.update_preview)
            options.addWidget(checkbox)
        options.addWidget(self.format_combo)
        self.format_combo.currentIndexChanged.connect(self.update_preview)
        layout.addLayout(options)
        self.snapshot_label = QLabel("No snapshot collected yet.")
        self.snapshot_label.setObjectName("snapshotStatus")
        self.snapshot_label.setWordWrap(True)
        layout.addWidget(self.snapshot_label)
        self.export_label = QLabel("Export options will appear after collection.")
        self.export_label.setWordWrap(True)
        self.export_label.setStyleSheet(f"color: {YELLOW}; font-weight: 700;")
        layout.addWidget(self.export_label)
        self.summary = QLabel("Ready to collect a fresh report.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)
        self.copy_btn = QPushButton("Copy report")
        self.save_btn = QPushButton("Save report…")
        close_btn = QPushButton("Close")
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_report)
        self.save_btn.clicked.connect(self.save_report)
        close_btn.clicked.connect(self.reject)
        layout.addLayout(_row(self.copy_btn, self.save_btn, close_btn))
        self.age_timer = QTimer(self)
        self.age_timer.setInterval(1000)
        self.age_timer.timeout.connect(self.update_snapshot_label)
        self.age_timer.start()
        QTimer.singleShot(0, self.refresh)

    def refresh(self):
        if self.worker or self._closing:
            return
        self.snapshot = self.view = None
        self.snapshot_label.setText("Collecting a new snapshot…")
        self.export_label.setText("Waiting for the new snapshot.")
        self.preview.clear()
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        for button in (self.refresh_btn, self.choose_btn, self.auto_btn):
            button.setEnabled(False)
        self.summary.setText("Collecting fresh sections…")
        self.worker = SupportReportWorker(self.recipe, self.roots, self.files, self)
        self.worker.done.connect(self.show_report)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(self.collection_finished)
        self.worker.start()

    def show_report(self, snapshot):
        self.snapshot = snapshot
        self.update_preview()

    def show_error(self, message):
        self.summary.setText("Support report unavailable")
        self.snapshot_label.setText("No snapshot available; collection failed.")
        self.export_label.setText("Copy/Save unavailable until a snapshot is collected.")
        self.preview.setPlainText(message)

    def collection_finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        for button in (self.refresh_btn, self.choose_btn, self.auto_btn):
            button.setEnabled(True)
        if self._closing:
            super().reject()

    def update_preview(self):
        if self.snapshot is None:
            return
        self.view = support_report.export_view(self.snapshot, self.excerpts_check.isChecked(), self.home_check.isChecked())
        self.preview.setPlainText(support_report.serialize(self.view, self.format_combo.currentData()))
        self.update_snapshot_label()
        options = self.view["export_options"]
        self.export_label.setText(("JSON" if self.format_combo.currentData() else "TEXT") + " export · Log excerpts: " +
                                  ("INCLUDED" if options["include_log_excerpts"] else "OMITTED") + " · Linux home path: " +
                                  ("REPLACED WITH ~" if options["replace_linux_home_path"] else "INCLUDED"))
        self.summary.setText("Section collection: " + self.snapshot["collection_status"] + " — availability only; each section retains its own evidence and dates.")
        self.copy_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def update_snapshot_label(self):
        if self.snapshot is None:
            return
        stamp = self.snapshot["collection_finished_at"]
        self.snapshot_label.setText("Snapshot collected: " + local_time(stamp) + " · " + age_text(stamp) +
                                    "\nCopy/Save export this snapshot. Collect new snapshot reads again; closing a game does not refresh it.")

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose logs for " + self.recipe["name"], "", "Log/text files (*.log *.txt);;All files (*)")
        if not files:
            return
        if len(files) > log_diagnostics.MAX_FILES:
            self.summary.setText("Choose at most four log files.")
            return
        self.files = files
        self.refresh()

    def use_expected(self):
        self.files = None
        self.refresh()

    def copy_report(self):
        if self.view is not None:
            QApplication.clipboard().setText(support_report.serialize(self.view, self.format_combo.currentData()))
            self.summary.setText("The previewed report was copied. Review it before sharing.")

    def save_report(self):
        if self.view is None:
            return
        json_format = self.format_combo.currentData()
        extension = ".json" if json_format else ".txt"
        stamp = filename_stamp(self.snapshot["collection_finished_at"])
        excerpt_suffix = "" if self.view["export_options"]["include_log_excerpts"] else "-no-excerpts"
        default = f"NAnnersVRhub-{self.recipe['id']}-support-{stamp}{excerpt_suffix}{extension}"
        name, _ = QFileDialog.getSaveFileName(self, "Save a new support report", default,
                                             "JSON reports (*.json)" if json_format else "Text reports (*.txt)")
        if not name:
            return
        if not name.lower().endswith(extension):
            name += extension
        try:
            support_report.save(Path(name), self.view, json_format)
        except FileExistsError:
            QMessageBox.warning(self, "Report already exists", "Choose a new filename. Existing files are preserved.")
        except OSError as exc:
            QMessageBox.warning(self, "Could not save report", str(exc))
        else:
            self.summary.setText("The previewed report was saved to " + name)

    def reject(self):
        self._closing = True
        if not self.worker:
            super().reject()

    def closeEvent(self, event):
        self._closing = True
        if self.worker:
            event.ignore()
            return
        super().closeEvent(event)


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


class RecordTestDialog(QDialog):
    def __init__(self, recipe, roots=None, parent=None):
        super().__init__(parent)
        self.recipe, self.roots = recipe, roots
        self.setObjectName("liveTestDialog")
        self.setWindowTitle("Record live test — " + recipe["name"])
        self.resize(640, 560)
        layout = QVBoxLayout(self)
        title = QLabel(recipe["name"])
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {YELLOW}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        intro = QLabel("Record what you tested. Areas marked Not tested remain unverified. The Hub does not detect gameplay success automatically.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.result_combo = QComboBox()
        self.result_combo.addItem("Choose a result…", None)
        for key, label in live_tests.OUTCOMES.items():
            self.result_combo.addItem(label.title(), key)
        form.addRow("Overall result", self.result_combo)
        self.checks = {}
        for key, label in live_tests.CHECKS.items():
            combo = QComboBox()
            for status in ("not-tested", "passed", "failed"):
                combo.addItem(live_tests.STATES[status].title(), status)
            self.checks[key] = combo
            form.addRow(label, combo)
        layout.addLayout(form)
        layout.addWidget(QLabel("Notes — what worked, failed, or needed a workaround"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Required for partial success or failure. Include limitations and any settings you changed.")
        layout.addWidget(self.notes, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {RED};")
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setObjectName("primaryAction")
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def save(self):
        checks = {key: combo.currentData() for key, combo in self.checks.items()}
        try:
            live_tests.validate_result(self.result_combo.currentData(), self.notes.toPlainText(), checks)
            report = compatibility.report(self.recipe, self.roots)
            self.saved_record = live_tests.record(self.recipe, self.result_combo.currentData(), self.notes.toPlainText(), checks, report)
        except (RuntimeError, OSError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class TestHistoryDialog(QDialog):
    def __init__(self, recipe, entries, parent=None):
        super().__init__(parent)
        self.entries = entries
        self.setObjectName("testHistoryDialog")
        self.setWindowTitle("Test history — " + recipe["name"])
        self.resize(850, 680)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        for entry in entries:
            self.list.addItem(f"{local_time(entry['recorded_at'])} — {live_tests.OUTCOMES[entry['outcome']]}")
        self.list.setMaximumHeight(170)
        layout.addWidget(self.list)
        self.details = QTextBrowser()
        layout.addWidget(self.details, 1)
        self.copy_btn = QPushButton("Copy selected test")
        self.copy_btn.clicked.connect(self.copy_selected)
        self.copy_btn.setEnabled(bool(entries))
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addLayout(_row(self.copy_btn, close))
        self.list.currentRowChanged.connect(self.show_record)
        if entries:
            self.list.setCurrentRow(0)
        else:
            self.details.setPlainText("No local tests recorded. Bundled references are separate from your local history.")

    def show_record(self, index):
        self.details.setPlainText(live_tests.record_text(self.entries[index], include_setup=True)
                                  if 0 <= index < len(self.entries) else "")

    def copy_selected(self):
        if 0 <= self.list.currentRow() < len(self.entries):
            QApplication.clipboard().setText(live_tests.record_text(self.entries[self.list.currentRow()], include_setup=True))


def preferred_launcher_size(available_width: int, available_height: int) -> tuple[int, int]:
    """Natural desktop opening size, bounded by the available screen.

    Use Qt logical pixels: on a smaller display the launcher opens restored
    within the workspace. Resizing/maximizing remain fully user-controlled.
    """
    return (
        min(1630, max(772, available_width - 64)),
        min(1060, max(530, available_height - 96)),
    )


class HubWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"NAnnersVRhub {__version__}")
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.resize(*preferred_launcher_size(area.width(), area.height()))
        else:
            self.resize(1630, 1060)
        self.setStyleSheet(STYLESHEET)
        if LOGO_PATH.is_file():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.rows: list[dict] = []
        self.update_results: dict = {}
        self.preflight_results: dict = {}  # Only explicit checks from this UI session.
        self.worker: UpdateWorker | None = None
        self.scan_worker: ScanWorker | None = None
        self.scan_report: dict | None = None
        self._closing = False
        self.allow_guided_installs = True
        self.development_tools_enabled = False
        tools_menu = self.menuBar().addMenu("Tools")
        self.development_tools_action = QAction("Enable development tools", self)
        self.development_tools_action.setCheckable(True)
        self.development_tools_action.setToolTip("Show development save recovery for this session only.")
        tools_menu.addAction(self.development_tools_action)
        self.development_tools_action.toggled.connect(self.set_development_tools_enabled)

        self.hub_updates = HubUpdateController(self)
        self.hub_updates.idle.connect(self.close_when_idle)
        self.hub_update_btn = QPushButton("Hub updates…")
        self.hub_update_btn.clicked.connect(self.hub_updates.show)
        self.hub_updates.changed.connect(self.update_hub_button)

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
        self.table.setHorizontalHeaderLabels(["Game", "Game install", "Mod", "Profile", "Updates"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.library_columns = enable_spreadsheet_columns(
            self.table, "game-library", (405, 160, 160, 160, 205),
            expand_weights=(2, 1, 1, 1, 2), min_row_height=28)
        self.table.itemSelectionChanged.connect(self.show_details)

        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.compat_report = None
        self.compat_details = QTextBrowser()
        self.compat_refresh_btn = QPushButton("Refresh compatibility")
        self.compat_copy_btn = QPushButton("Copy compatibility report")
        self.record_test_btn = QPushButton("Record live test…")
        self.test_history_btn = QPushButton("Test history…")
        self.log_diagnostics_btn = QPushButton("Log diagnostics…")
        self.support_report_btn = QPushButton("Create support report…")
        self.support_report_btn.clicked.connect(self.show_support_report)
        self.log_diagnostics_btn.clicked.connect(self.show_log_diagnostics)
        self.record_test_btn.clicked.connect(self.record_live_test)
        self.test_history_btn.clicked.connect(self.show_test_history)
        self.compat_refresh_btn.clicked.connect(self.refresh_compatibility)
        self.compat_copy_btn.clicked.connect(self.copy_compatibility)
        compat_page = QWidget()
        compat_page.setObjectName("compatibilityGamePage")
        compat_layout = QVBoxLayout(compat_page)
        compat_layout.setContentsMargins(12, 12, 12, 12)
        compat_layout.setSpacing(9)
        compat_layout.addLayout(_row(self.compat_refresh_btn, self.compat_copy_btn))
        compat_layout.addLayout(_row(self.record_test_btn, self.test_history_btn))
        compat_layout.addWidget(self.compat_details)
        # Dev5D1-A: keep existing content widgets and signal paths. Only the
        # navigation ownership changes; none of the installer logic changes.
        self.compat_page = compat_page
        self.controller_bindings = ControllerBindingsPage()
        self.mod_updates = ModUpdatesPage()
        self.mod_updates.refresh_requested.connect(self.check_updates)
        self.downloads = GuidedDownloadsPage()
        self.downloads.inspect_requested.connect(self.inspect_planned_archive)
        self.downloads.install_review_requested.connect(self.review_requested_install)
        self.downloads.scan_idle.connect(self.close_when_idle)
        self.downloads.download_idle.connect(self.close_when_idle)
        self.install_btn = QPushButton("Review mod archives")
        self.install_btn.setToolTip(
            "Choose archive files for review.\n"
            "The Hub checks exact destinations and backups.\n"
            "Installation requires a separate confirmation.")
        self.uninstall_btn = QPushButton("Uninstall mod")
        self.profile_btn = QPushButton("Review UEVR profile…")
        self.profile_btn.setToolTip(
            "Review selected ZIP, exact profile destination, persistent backup policy, "
            "and any legacy/manual-recovery blockers before installation.")
        self.unprofile_btn = QPushButton("Remove profile")
        self.copy_btn = QPushButton("Copy launch options")
        self.inject_btn = QPushButton("Run UEVR injector")
        self.copy_btn.setObjectName("overviewSecondaryLaunch")
        self.inject_btn.setObjectName("overviewSecondaryLaunch")
        self.game_launch_btn = QPushButton("Launch game tool")
        self.game_play_btn = QPushButton("Launch game")
        # Use the Mod Updates page's own refresh button: one visible action,
        # one backend, one in-progress status, and no duplicated signal.
        self.check_btn = self.mod_updates.refresh_button
        self.check_btn.setToolTip(
            "Read-only version lookup. Does not download, install or remove mods.")
        self.mark_btn = QPushButton("Mark as up to date")
        self.key_btn = QPushButton("Nexus API key…")
        self.verify_btn = QPushButton("Verify mods")
        self.preflight_btn = QPushButton("Preflight")
        self.inspect_btn = QPushButton("Inspect archive…")
        self.diag_btn = QPushButton("Copy diagnostics")
        self.bridge_log_btn = QPushButton("Open bridge log")
        self.kharvox_folder_btn = QPushButton("Choose KHARVOX folder…")
        self.doom_prepare_btn = QPushButton("Install VR runner")
        self.doom_probe_btn = QPushButton("Test VR bridge")
        self.doom_probe_btn.setObjectName("overviewSecondaryLaunch")
        self.doom_logs_btn = QPushButton("Open DOOM diagnostics")
        self.doom_import_btn = QPushButton("Import bridge package…")
        self.doom_saves_btn = QPushButton("Development: restore game saves…")
        self.bridge_log_btn.setObjectName("secondaryAction")
        refresh_btn = QPushButton("Refresh library")
        self.refresh_library_btn = refresh_btn
        self.install_btn.clicked.connect(self.install)
        self.uninstall_btn.clicked.connect(self.uninstall)
        self.profile_btn.clicked.connect(self.install_profile)
        self.unprofile_btn.clicked.connect(self.uninstall_profile)
        self.copy_btn.clicked.connect(self.copy_options)
        self.inject_btn.clicked.connect(self.run_injector)
        self.game_launch_btn.clicked.connect(self.launch_game_tool)
        self.game_play_btn.clicked.connect(self.launch_game_play)
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
        self.kharvox_folder_btn.clicked.connect(self.choose_kharvox_folder)
        self.doom_prepare_btn.clicked.connect(lambda: self.run_kharvox_bridge('prepare'))
        self.doom_probe_btn.clicked.connect(lambda: self.run_kharvox_bridge('probe'))
        self.doom_logs_btn.clicked.connect(self.open_doom_diagnostics)
        self.doom_import_btn.clicked.connect(self.import_kharvox_bridge)
        self.doom_saves_btn.clicked.connect(self.show_doom_saves)
        refresh_btn.clicked.connect(self.refresh)

        # Dev1 launcher shell: game selection stays backed by the existing
        # QTableWidget so legacy install/compatibility/save workflows retain
        # their original recipe IDs, signals and data.
        self.game_banner = GameBanner()
        self.artwork_label = QLabel("Artwork: NAnnersVRhub original banner")
        self.artwork_label.setObjectName("launcherArtworkSource")
        self.artwork_label.setWordWrap(True)
        self.artwork_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.change_banner_btn = QPushButton("Change banner…")
        self.change_banner_btn.setObjectName("launcherArtworkAction")
        self.restore_banner_btn = QPushButton("Restore default")
        self.restore_banner_btn.setObjectName("launcherArtworkAction")
        self.change_banner_btn.clicked.connect(self.choose_banner)
        self.restore_banner_btn.clicked.connect(self.restore_banner)
        self.game_dashboard = GameDashboard()
        self.library_toggle = QPushButton("Show detailed library table")
        self.library_toggle.setObjectName("launcherDisclosure")
        self.library_toggle.setCheckable(True)
        self.library_panel = QWidget()
        library_layout = QVBoxLayout(self.library_panel)
        library_layout.setContentsMargins(0, 0, 0, 0)
        self.library_column_hint = QLabel(
            "Drag column dividers to resize · Double-click a divider to fit text · Widths are remembered")
        self.library_column_hint.setObjectName("tableColumnHint")
        library_layout.addWidget(self.library_column_hint)
        library_layout.addLayout(_row(refresh_btn))
        self.table.setMaximumHeight(205)
        library_layout.addWidget(self.table)
        self.library_panel.hide()
        self.library_toggle.toggled.connect(self.library_panel.setVisible)
        self.library_toggle.toggled.connect(
            lambda enabled: self.library_toggle.setText(
                "Hide detailed library table" if enabled else "Show detailed library table"))

        # Dev5D1-B: keep original QPushButtons and their handlers, but
        # relocate them into task-specific disclosures, collapsed by default.
        # No "buttons for buttons' sake" on the Overview dashboard.
        self.more_tools_toggle = QPushButton("More compatibility tools")
        self.more_tools_toggle.setObjectName("launcherDisclosure")
        self.more_tools_toggle.setCheckable(True)
        self.more_tools_panel = QWidget()
        self.more_tools_panel.setObjectName("compatibilityAdvancedTools")
        advanced_layout = QVBoxLayout(self.more_tools_panel)
        advanced_layout.setContentsMargins(4, 5, 4, 5)
        advanced_layout.setSpacing(7)
        # Per-game launchers and the DOOM bridge pre-launch test live on
        # Overview. Compatibility retains bridge logs and other diagnostics.
        advanced_layout.addLayout(_row(self.diag_btn, self.bridge_log_btn,
                                       self.log_diagnostics_btn, self.support_report_btn))
        advanced_layout.addLayout(_row(self.doom_logs_btn))
        self.more_tools_panel.hide()
        self.more_tools_toggle.toggled.connect(self.more_tools_panel.setVisible)
        self.more_tools_toggle.toggled.connect(
            lambda active: self.more_tools_toggle.setText(
                "Hide compatibility tools" if active else "More compatibility tools"))
        compat_layout.insertWidget(2, self.more_tools_toggle)
        compat_layout.insertWidget(3, self.more_tools_panel)

        self.install_tools_toggle = QPushButton("More installation tools")
        self.install_tools_toggle.setObjectName("launcherDisclosure")
        self.install_tools_toggle.setCheckable(True)
        self.install_tools_panel = QWidget()
        self.install_tools_panel.setObjectName("installationAdvancedTools")
        install_tools_layout = QVBoxLayout(self.install_tools_panel)
        install_tools_layout.setContentsMargins(4, 5, 4, 5)
        install_tools_layout.setSpacing(7)
        install_tools_layout.addLayout(_row(self.install_btn, self.profile_btn,
                                            self.verify_btn, self.inspect_btn))
        install_tools_layout.addLayout(_row(self.kharvox_folder_btn,
                                            self.doom_prepare_btn, self.doom_import_btn))
        self.install_tools_panel.hide()
        self.install_tools_toggle.toggled.connect(self.install_tools_panel.setVisible)
        self.install_tools_toggle.toggled.connect(
            lambda active: self.install_tools_toggle.setText(
                "Hide installation tools" if active else "More installation tools"))
        self.downloads.layout().insertWidget(5, self.install_tools_toggle)
        self.downloads.layout().insertWidget(6, self.install_tools_panel)

        self.update_tools_toggle = QPushButton("More update tools")
        self.update_tools_toggle.setObjectName("launcherDisclosure")
        self.update_tools_toggle.setCheckable(True)
        self.update_tools_panel = QWidget()
        self.update_tools_panel.setObjectName("updatesAdvancedTools")
        update_tools_layout = QHBoxLayout(self.update_tools_panel)
        update_tools_layout.setContentsMargins(4, 5, 4, 5)
        update_tools_layout.addWidget(self.mark_btn)
        update_tools_layout.addWidget(self.key_btn)
        self.update_tools_panel.hide()
        self.update_tools_toggle.toggled.connect(self.update_tools_panel.setVisible)
        self.update_tools_toggle.toggled.connect(
            lambda active: self.update_tools_toggle.setText(
                "Hide update tools" if active else "More update tools"))
        self.mod_updates.layout().insertWidget(1, self.update_tools_toggle)
        self.mod_updates.layout().insertWidget(2, self.update_tools_panel)

        # The game banner and artwork controls remain visible on every tab.
        # Everything else belongs to the chosen game-page context.
        self.overview_page = QWidget()
        self.overview_page.setObjectName("gameOverviewPage")
        overview_layout = QVBoxLayout(self.overview_page)
        overview_layout.setContentsMargins(8, 12, 8, 12)
        overview_layout.setSpacing(8)
        overview_layout.addWidget(self.game_dashboard)
        self.quick_actions = ResponsiveQuickActions((
            self.game_play_btn, self.preflight_btn,
        ))
        self.quick_actions.setMaximumWidth(760)
        overview_layout.addWidget(self.quick_actions)

        # Secondary launch/pre-launch actions live alongside Launch Game and
        # Preflight. Reuse each original button and its existing click handler:
        # Steam options, UEVR injector, handler-owned MO2/KHARVOX launcher,
        # and the DOOM-specific synthetic VR bridge pre-launch probe.
        self.launch_tools_panel = QWidget()
        self.launch_tools_panel.setObjectName("overviewLaunchTools")
        self.launch_tools_panel.setMaximumWidth(760)
        launch_tools_layout = QVBoxLayout(self.launch_tools_panel)
        launch_tools_layout.setContentsMargins(0, 5, 0, 0)
        launch_tools_layout.setSpacing(6)
        self.launch_tools_label = QLabel("LAUNCH TOOLS")
        self.launch_tools_label.setObjectName("launchToolsLabel")
        launch_tools_layout.addWidget(self.launch_tools_label)
        launch_tools_layout.addLayout(_row(
            self.copy_btn, self.inject_btn,
            self.game_launch_btn, self.doom_probe_btn))
        overview_layout.addWidget(self.launch_tools_panel)

        overview_layout.addWidget(self.library_toggle)
        overview_layout.addWidget(self.library_panel)
        overview_layout.addStretch(1)

        self.rollback_page = QWidget()
        self.rollback_page.setObjectName("gameRollbackPage")
        rollback_layout = QVBoxLayout(self.rollback_page)
        rollback_layout.setContentsMargins(14, 15, 14, 15)
        rollback_layout.setSpacing(12)
        rollback_title = QLabel("BACKUPS & ROLLBACK")
        rollback_title.setObjectName("rollbackHeading")
        rollback_layout.addWidget(rollback_title)
        self.rollback_summary = QLabel(
            "Choose a game to view its Hub-managed recovery records.")
        self.rollback_summary.setObjectName("rollbackSummary")
        self.rollback_summary.setWordWrap(True)
        rollback_layout.addWidget(self.rollback_summary)
        rollback_notice = QLabel(
            "Recorded does not mean verified or recoverable. The Hub checks "
            "current files and retained originals when an operation is requested. "
            "Legacy and modified UEVR profile installations remain protected; "
            "Dev5C3 live-profile execution is disabled.")
        rollback_notice.setObjectName("rollbackNotice")
        rollback_notice.setWordWrap(True)
        rollback_layout.addWidget(rollback_notice)
        rollback_layout.addLayout(_row(self.uninstall_btn, self.unprofile_btn,
                                       self.doom_saves_btn))
        rollback_layout.addStretch(1)

        self.game_details_tabs = QTabWidget()
        self.game_details_tabs.setObjectName("gameDetailsTabs")
        self.game_details_tabs.setDocumentMode(True)
        # Ignore the combined seven-tab size hint: the tab bar has its own
        # arrows, and must not force the entire game page to scroll sideways.
        self.game_details_tabs.setMinimumWidth(0)
        self.game_details_tabs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.game_details_tabs.setIconSize(QSize(18, 18))
        bar = self.game_details_tabs.tabBar()
        bar.setExpanding(False)
        bar.setUsesScrollButtons(True)
        bar.setElideMode(Qt.ElideNone)
        # KDE icon themes are preferred. Qt-native icons are a safe fallback.
        icon_data = (
            (self.overview_page, "Overview", "go-home-symbolic", QStyle.SP_DirHomeIcon),
            (self.mod_updates, "Mod Updates", "download-symbolic", QStyle.SP_ArrowDown),
            (self.downloads, "Install / Update", "package-x-generic", QStyle.SP_DriveHDIcon),
            (self.rollback_page, "Rollback", "view-history", QStyle.SP_BrowserReload),
            (self.compat_page, "Compatibility", "video-display", QStyle.SP_ComputerIcon),
            (self.controller_bindings, "Controller Bindings", "applications-games", QStyle.SP_MediaPlay),
            (self.details, "Setup Guide", "documentation", QStyle.SP_DialogHelpButton),
        )
        self._game_tab_original_icons = []
        for page, label, themed_icon, fallback_icon in icon_data:
            icon = QIcon.fromTheme(themed_icon)
            if icon.isNull():
                icon = self.style().standardIcon(fallback_icon)
            self._game_tab_original_icons.append(icon)
            self.game_details_tabs.addTab(page, icon, label)
        self.game_details_tabs.currentChanged.connect(self._update_game_tab_icon_colors)
        self._update_game_tab_icon_colors(self.game_details_tabs.currentIndex())
        self.game_details_tabs.currentChanged.connect(
            lambda index: self.refresh_compatibility()
            if self.game_details_tabs.widget(index) is self.compat_page else None)

        game_layout = QVBoxLayout()
        game_layout.setContentsMargins(10, 10, 10, 10)
        game_layout.setSpacing(7)
        game_layout.addWidget(self.game_banner)
        artwork_toolbar = QHBoxLayout()
        artwork_toolbar.setSpacing(7)
        artwork_toolbar.addWidget(self.artwork_label, 1)
        artwork_toolbar.addWidget(self.change_banner_btn, 0)
        artwork_toolbar.addWidget(self.restore_banner_btn, 0)
        game_layout.addLayout(artwork_toolbar)
        game_layout.addWidget(self.game_details_tabs, 1)
        games_page = QWidget()
        games_page.setObjectName("gamesPage")
        games_page.setLayout(game_layout)
        # A long setup guide must never force the entire launcher beyond the
        # available KDE screen. The game content scrolls independently while
        # navigation and runtime indicators remain accessible at any height.
        # Cap the content width to avoid giant status cards when maximized.
        games_page.setMaximumWidth(1420)
        self.game_page_scroll = QScrollArea()
        self.game_page_scroll.setObjectName("gamePageScroll")
        self.game_page_scroll.setWidgetResizable(True)
        self.game_page_scroll.setFrameShape(QFrame.NoFrame)
        self.game_page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.game_page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.game_page_scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.game_page_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.game_page_scroll.setMinimumSize(0, 0)
        self.game_page_scroll.setWidget(games_page)
        dashboard = QWidget()
        dashboard.setObjectName("systemDashboard")
        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_title = QLabel("VR SYSTEM DASHBOARD")
        dashboard_title.setStyleSheet(f"color: {YELLOW}; font-size: 20px; font-weight: 800;")
        self.scan_summary = QLabel("Scan your host VR setup, then use game Preflight for the selected game.")
        self.scan_summary.setWordWrap(True)
        self.runtime_state = QLabel("Runtime: checking…")
        self.server_state = QLabel("Server: checking…")
        self.headset_state = QLabel("Headset: checking…")
        self.controllers_state = QLabel("Controllers: UNVERIFIED")
        for label in (self.runtime_state, self.server_state, self.headset_state, self.controllers_state):
            label.setObjectName("runtimePill")
        self.auto_live = QCheckBox("Auto-refresh live status every 5 seconds")
        self.auto_live.setChecked(True)
        self.auto_live.toggled.connect(lambda checked: self.refresh_system_live() if checked else None)
        self.scan_btn = QPushButton("SCAN MY VR SETUP")
        self.scan_btn.setObjectName("primaryAction")
        self.scan_btn.clicked.connect(self.scan_setup)
        self.copy_scan_btn = QPushButton("Copy system report")
        self.copy_scan_btn.clicked.connect(self.copy_system_report)
        self.copy_scan_btn.setEnabled(False)
        self.save_scan_btn = QPushButton("Save system report…")
        self.save_scan_btn.clicked.connect(self.save_system_report)
        self.save_scan_btn.setEnabled(False)
        self.system_details = QTextBrowser()
        self.system_details.setPlainText("Connect the headset in your runtime manager, then scan. The scan does not start a runtime or change your setup.")
        dashboard_layout.addWidget(dashboard_title)
        dashboard_layout.addLayout(_row(self.runtime_state, self.server_state, self.headset_state, self.controllers_state))
        dashboard_layout.addWidget(self.scan_summary)
        dashboard_layout.addWidget(self.auto_live)
        dashboard_layout.addLayout(_row(self.scan_btn, self.copy_scan_btn, self.save_scan_btn))
        dashboard_layout.addWidget(self.system_details, 1)
        self.tabs = QTabWidget()
        self.tabs.addTab(dashboard, "VR System")
        self.tabs.addTab(self.game_page_scroll, "Games")
        # Keep the same page indexes for older tests and existing callers;
        # sidebar navigation replaces only the visible page tabs.
        self.tabs.tabBar().hide()
        self.sidebar = LauncherSidebar()
        self.sidebar.page_selected.connect(self.tabs.setCurrentIndex)
        self.sidebar.game_selected.connect(self.select_launcher_game)
        self.tabs.currentChanged.connect(self.sidebar.set_page)
        self.tabs.currentChanged.connect(lambda index: self.refresh_system_live() if index == 0 else None)
        self.tabs.setCurrentIndex(1)
        shell = QHBoxLayout()
        shell.setSpacing(10)
        shell.addWidget(self.sidebar)
        shell.addWidget(self.tabs, 1)
        status_row = QHBoxLayout()
        status_row.addWidget(self.runtime_label)
        status_row.addWidget(self.live_status_label)
        status_row.addStretch(1)
        status_row.addWidget(self.hub_update_btn)
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(9)
        root.addWidget(header)
        root.addLayout(status_row)
        root.addLayout(shell, 1)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(2000)
        self.status_timer.timeout.connect(self.update_live_status)
        self.status_timer.start()
        self.scan_timer = QTimer(self)
        self.scan_timer.setInterval(5000)
        self.scan_timer.timeout.connect(self.refresh_system_live)
        self.scan_timer.start()
        self.refresh()
        self.check_updates()  # quietly, in the background
        QTimer.singleShot(0, self.scan_setup)
        QTimer.singleShot(0, self.hub_updates.startup)

    def update_hub_button(self):
        controller = self.hub_updates
        if controller.installed:
            text = "Hub update: restart ready"
        elif controller.release and app_updates.newer(controller.release):
            text = "Hub update ready…" if controller.ready_for_release() else "Hub update available…"
        else:
            text = "Hub updates…"
        self.hub_update_btn.setText(text)

    def refresh_system_live(self):
        if self.auto_live.isChecked() and self.tabs.currentIndex() == 0 and self.scan_report:
            self.scan_setup(live_only=True)

    def scan_setup(self, _checked=False, *, live_only=False):
        if self._closing or self.scan_worker:
            return
        self.scan_btn.setEnabled(False)
        self.copy_scan_btn.setEnabled(False)
        self.save_scan_btn.setEnabled(False)
        if not live_only:
            self.scan_summary.setText("Scanning host VR setup…")
        self.scan_worker = ScanWorker(self.scan_report if live_only else None, self)
        self.scan_worker.done.connect(self.show_system_report)
        self.scan_worker.failed.connect(self.scan_failed)
        self.scan_worker.finished.connect(self.scan_finished)
        self.scan_worker.start()

    def show_system_report(self, report):
        self.scan_report = report
        live = report["live"]
        selection = f"{report['runtime']} SELECTED" if live["runtime_selected"] else "NOT CONFIGURED"
        self.runtime_state.setText(f"Runtime: {selection}")
        self.runtime_state.setStyleSheet(f"color: {GREEN if live['runtime_selected'] else RED};")
        server = live["server_running"]
        self.server_state.setText("Server: " + ("RUNNING" if server else "NOT OBSERVED" if server is False else "UNKNOWN"))
        self.server_state.setStyleSheet(f"color: {GREEN if server else MUTED};")
        headset = live["headset_connected"]
        self.headset_state.setText("Headset: " + ("CONNECTED" if headset else "DISCONNECTED" if headset is False else "UNKNOWN"))
        self.headset_state.setStyleSheet(f"color: {GREEN if headset else YELLOW if headset is False else MUTED};")
        self.controllers_state.setStyleSheet(f"color: {MUTED};")
        self.scan_summary.setText(f"{report['status']}  •  Live status checked: {local_time(live['sampled_at'])}")
        self.runtime_label.setText(f"●  {selection}")
        self.runtime_label.setStyleSheet(f"color: {GREEN if live['runtime_selected'] else RED};")
        scrollbar = self.system_details.verticalScrollBar()
        position = scrollbar.value()
        self.system_details.setHtml(system_scan.report_html(report))
        scrollbar.setValue(position)
        self.copy_scan_btn.setEnabled(True)
        self.save_scan_btn.setEnabled(True)

    def scan_failed(self, message):
        self.scan_report = None
        self.runtime_state.setText("Runtime: UNKNOWN")
        self.server_state.setText("Server: UNKNOWN")
        self.headset_state.setText("Headset: UNKNOWN")
        for label in (self.runtime_state, self.server_state, self.headset_state):
            label.setStyleSheet(f"color: {MUTED};")
        self.scan_summary.setText("Scan could not complete. Rescan to try again.")
        self.system_details.setPlainText(message)

    def scan_finished(self):
        worker = self.scan_worker
        self.scan_worker = None
        if worker:
            worker.deleteLater()
        self.scan_btn.setEnabled(True)
        self.close_when_idle()

    def close_when_idle(self):
        downloads_busy = bool(
            (self.downloads.worker and self.downloads.worker.isRunning()) or
            (self.downloads.download_worker and self.downloads.download_worker.isRunning()))
        if (self._closing and not self.scan_worker
                and not (self.worker and self.worker.isRunning())
                and not self.hub_updates.busy and not downloads_busy):
            self.close()

    def copy_system_report(self):
        if self.scan_report:
            QApplication.clipboard().setText(system_scan.report_text(self.scan_report))
            self.statusBar().showMessage("System report copied.", 4000)

    def save_system_report(self):
        if not self.scan_report:
            return
        name, _ = QFileDialog.getSaveFileName(self, "Save VR system report", "NAnnersVRhub-system-report.txt", "Text reports (*.txt)")
        if name:
            try:
                Path(name).write_text(system_scan.report_text(self.scan_report) + "\n", encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self, "Could not save report", str(exc))
            else:
                self.statusBar().showMessage("System report saved.", 4000)

    def closeEvent(self, event):
        # Polling and transfer threads must finish before window teardown.
        self._closing = True
        if self.downloads.download_worker and self.downloads.download_worker.isRunning():
            self.downloads.cancel_download()
        self.scan_timer.stop()
        self.hub_updates.shutdown()
        if (self.scan_worker or (self.worker and self.worker.isRunning())
                or self.hub_updates.busy
                or (self.downloads.worker and self.downloads.worker.isRunning())
                or (self.downloads.download_worker
                    and self.downloads.download_worker.isRunning())):
            event.ignore()
            return
        # Save only user-initiated header width edits, never game data.
        self.library_columns.flush()
        self.downloads.table.spreadsheet_columns.flush()
        for section in self.mod_updates.sections.values():
            section.table.spreadsheet_columns.flush()
        super().closeEvent(event)

    def current(self) -> dict | None:
        idx = self.table.currentRow()
        return self.rows[idx]["recipe"] if 0 <= idx < len(self.rows) else None

    def select_launcher_game(self, index):
        """Use the original game-table selection as the single authority."""
        if 0 <= index < len(self.rows):
            if self.table.currentRow() != index:
                self.table.selectRow(index)
            else:
                self.show_details()
            self.tabs.setCurrentIndex(1)

    def refresh(self):
        # Game files and runtime conditions may have changed. Never retain a
        # previous local preflight success across a new state refresh.
        self.preflight_results.clear()
        keep = self.table.currentRow()
        path, lib = runtime.active_runtime()
        ok = bool(path and lib)
        self.runtime_label.setText(f"●  {runtime.runtime_name(path, lib)} SELECTED" if ok else "●  OpenXR NOT CONFIGURED")
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
                item = QTableWidgetItem(text)
                item.setToolTip(text)  # full value remains readable while narrow
                self.table.setItem(i, c, item)
        self.library_columns.schedule_rows()
        self.sidebar.set_games(self.rows, keep if 0 <= keep < len(self.rows) else 0)
        if self.rows:
            self.table.selectRow(keep if 0 <= keep < len(self.rows) else 0)
        self.show_details()

    def show_details(self):
        r = self.current()
        idx = self.table.currentRow()
        self.sidebar.select_game(idx)
        row = self.rows[idx] if 0 <= idx < len(self.rows) else None
        self.game_banner.set_game(row, self.update_results.get(r["id"]) if r else None)
        self.artwork_label.setText("Artwork: " + self.game_banner.artwork_choice.source)
        self.artwork_label.setToolTip(
            str(self.game_banner.artwork_choice.path or "Original NAnnersVRhub artwork"))
        self.change_banner_btn.setEnabled(bool(r))
        self.restore_banner_btn.setEnabled(bool(
            r and artwork.custom_artwork_path(r).exists()))
        kharvox = bool(r and r.get('handler') == 'kharvox-gog')
        self.doom_saves_btn.setVisible(bool(r and self.development_tools_enabled and r["id"] in game_saves.LAYOUTS))
        self.kharvox_folder_btn.setVisible(kharvox)
        for button in (self.doom_prepare_btn, self.doom_probe_btn, self.doom_logs_btn, self.doom_import_btn):
            button.setVisible(kharvox)
        for button in [self.install_btn,self.uninstall_btn,self.profile_btn,self.unprofile_btn,
                       self.verify_btn,self.inspect_btn,self.key_btn]:
            button.setVisible(not kharvox)
        self.controller_bindings.set_recipe(r)
        self.refresh_compatibility()
        verification = hub.verify(r) if r else None
        available = self.update_results.get(r["id"]) if r else None
        checked = self.preflight_results.get(r["id"]) if r else None
        self.game_dashboard.set_snapshot(
            dashboard_snapshot(row, available, verification, checked))
        self.mod_updates.set_recipe(r, available)
        self.downloads.set_recipe(r)
        self.refresh_rollback_summary(r)
        update_count = sum(item.get("status") == "update" for item in available or [])
        idx = self.game_details_tabs.indexOf(self.mod_updates)
        self.game_details_tabs.setTabText(
            idx, f"Mod Updates ({update_count})" if update_count else "Mod Updates")
        self.details.setHtml(hub.details_html(
            r, available, verification, compact_updates=True) if r else "")
        can_install = bool(r and get_handler(r).install_supported(r))
        self.install_btn.setEnabled(can_install)
        self.uninstall_btn.setEnabled(bool(r and r.get("method") != "guide"))
        # Context-sensitive visibility is based on existing recipe support,
        # never on game detection or a guessed "ready" status. A supported
        # action stays available even when the game is not installed yet;
        # its original handler still reports missing prerequisites.
        supports_injector = bool(r and r.get("method") == "uevr")
        supports_steam_options = bool(
            r and r.get("store", "steam") == "steam"
            and r.get("steam_appid") is not None)
        self.inject_btn.setText("Run UEVR injector")
        self.inject_btn.setEnabled(supports_injector)
        self.inject_btn.setVisible(supports_injector)
        self.copy_btn.setEnabled(supports_steam_options)
        self.copy_btn.setVisible(supports_steam_options)
        label = hub.game_launcher_label(r) if r else None
        self.game_launch_btn.setText(label or "Launch game tool")
        self.game_launch_btn.setVisible(bool(label))
        self.game_launch_btn.setEnabled(bool(label))
        # Some launchers are MO2/KHARVOX rather than generic Steam/UEVR
        # launchers. DOOM's bridge probe is a prerequisite check, not a
        # gameplay validation; it remains the existing guarded operation.
        self.launch_tools_panel.setVisible(
            supports_injector or supports_steam_options or bool(label) or kharvox)
        play_label = hub.game_play_label(r) if r else None
        self.game_play_btn.setText(play_label or "Launch game")
        self.game_play_btn.setVisible(bool(play_label))
        self.game_play_btn.setEnabled(bool(play_label))
        self.verify_btn.setEnabled(bool(r and (r.get("components") or r.get("packages"))))
        self.preflight_btn.setEnabled(bool(r))
        self.inspect_btn.setEnabled(bool(r and r.get("method") in {"gameroot", "bepinex", "ervr"}))
        has_profile = bool(r and "profile" in r)
        self.profile_btn.setEnabled(has_profile)
        self.unprofile_btn.setEnabled(has_profile)
        # Do not show a nonsensical "Remove profile" control for games
        # with no UEVR profile workflow. Existing guarded behavior is intact.
        self.unprofile_btn.setVisible(has_profile and not kharvox)
        self.bridge_log_btn.setVisible(bool(r and hub.game_bridge_log(r)))
        if r:
            self.bridge_log_btn.setText(
                "Open MO2 bridge log" if r.get("handler") == "skyrim-vr"
                else hub.game_bridge_log_label(r))
        self.update_live_status()

    def _update_game_tab_icon_colors(self, selected: int) -> None:
        """Selected navigation icon is dark on banana-yellow; others stay muted."""
        for index, original in enumerate(self._game_tab_original_icons):
            color = BG if index == selected else MUTED
            self.game_details_tabs.setTabIcon(
                index, _tab_icon_with_color(original, color))

    def refresh_rollback_summary(self, recipe):
        """Describe records without implying that a backup is validated."""
        if not recipe:
            self.rollback_summary.setText("Select a game to inspect recovery records.")
            return
        try:
            records = hub.state()
        except (OSError, ValueError, RuntimeError) as exc:
            self.rollback_summary.setText(
                "Recovery records could not be inspected. No restoration is authorized. "
                f"Reason: {exc}")
            return
        installed = records.get(recipe["id"])
        profile = records.get(recipe["id"] + ":profile")
        if installed is None:
            mod_status = "No Hub-managed mod installation record."
        elif installed.get("installer") == "gameroot-2":
            mod_status = "Recorded game-root install with retained originals; revalidation required."
        else:
            mod_status = "Existing mod installation record; recovery policy depends on installer."
        if "profile" not in recipe:
            profile_status = "No UEVR profile step for this game."
        elif profile is None:
            profile_status = "No Hub-managed UEVR profile record."
        elif profile.get("installer") == "uevr-profile-2":
            profile_status = "Recorded profile backup; full SHA-256 recheck required before restore."
        else:
            profile_status = "Legacy UEVR profile record: automatic restoration blocked."
        self.rollback_summary.setText(
            f"{recipe['name']}\nMods: {mod_status}\nProfile: {profile_status}")

    def refresh_compatibility(self):
        self.compat_report = None
        self.compat_copy_btn.setEnabled(False)
        self.compat_refresh_btn.setEnabled(bool(self.current()))
        self.record_test_btn.setEnabled(bool(self.current()))
        self.test_history_btn.setEnabled(bool(self.current()))
        self.log_diagnostics_btn.setEnabled(bool(self.current()))
        self.support_report_btn.setEnabled(bool(self.current()))
        r = self.current()
        if not r:
            self.compat_details.clear()
            return
        try:
            self.compat_report = compatibility.report(r, _roots())
            self.compat_details.setHtml(compatibility.report_html(self.compat_report))
            self.compat_copy_btn.setEnabled(True)
        except (RuntimeError, OSError) as exc:
            self.compat_details.setPlainText(f"Compatibility report unavailable: {exc}")

    def record_live_test(self):
        recipe = self.current()
        if recipe and RecordTestDialog(recipe, _roots(), self).exec() == QDialog.Accepted:
            self.refresh_compatibility()
            self.statusBar().showMessage("Local gameplay test saved.", 4000)

    def show_test_history(self):
        recipe = self.current()
        if not recipe:
            return
        try:
            entries = live_tests.history(recipe["id"])
        except (RuntimeError, OSError) as exc:
            QMessageBox.warning(self, "Test history unavailable", str(exc))
            return
        TestHistoryDialog(recipe, entries, self).exec()

    def show_log_diagnostics(self):
        recipe = self.current()
        if recipe:
            LogDiagnosticsDialog(recipe, _roots(), self).exec()

    def show_support_report(self):
        recipe = self.current()
        if recipe:
            SupportReportDialog(recipe, _roots(), self).exec()

    def copy_compatibility(self):
        if self.compat_report is not None:
            QApplication.clipboard().setText(compatibility.report_text(self.compat_report))
            self.statusBar().showMessage("Compatibility report copied.", 4000)

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

    def set_development_tools_enabled(self, checked):
        self.development_tools_enabled = bool(checked)
        self.show_details()

    # ---- game artwork, isolated from all Steam/Heroic files ---------------
    def choose_banner(self):
        recipe = self.current()
        if not recipe:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choose a custom game banner", str(Path.home()),
            "Image files (*.jpg *.jpeg *.png *.webp)")
        if not filename:
            return
        try:
            artwork.import_banner(recipe, filename)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Cannot use artwork", str(exc))
            return
        self.show_details()
        self.statusBar().showMessage(
            "Custom artwork saved in NAnnersVRhub's own data folder.", 4500)

    def restore_banner(self):
        recipe = self.current()
        if not recipe:
            return
        try:
            removed = artwork.restore_default(recipe)
        except OSError as exc:
            QMessageBox.warning(self, "Cannot restore banner", str(exc))
            return
        self.show_details()
        if removed:
            self.statusBar().showMessage(
                "Custom artwork removed. Restored available Steam/Heroic artwork or original banner.",
                5000)

    def show_doom_saves(self):
        recipe = self.current()
        if recipe and self.development_tools_enabled and recipe.get("id") in game_saves.LAYOUTS:
            from .game_save_gui import GameSavesDialog
            GameSavesDialog(recipe, self, development_enabled=True).exec()

    # ---- update checking -------------------------------------------------
    def check_updates(self):
        if self.worker and self.worker.isRunning():
            return
        self.mod_updates.set_checking(True)
        self.worker = UpdateWorker()
        self.worker.done.connect(self._updates_done)
        self.worker.finished.connect(self.close_when_idle)
        self.worker.start()

    def _updates_done(self, results):
        self.update_results = results or {}
        self.mod_updates.set_checking(False)
        self.refresh()

    def mark_current(self):
        r = self.current()
        if not r:
            return
        if r.get("track_component_updates"):
            QMessageBox.information(
                self, "Per-mod update tracking",
                "Cyberpunk dependencies use the installed archive version for each mod. "
                "To clear an update, install the newer archive through the hub. "
                "Mark as up to date cannot override a different recorded version.")
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
        f, _ = QFileDialog.getOpenFileName(self, title, self.download_picker_folder(), "Mod files (*.zip *.pak)")
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
        files, _ = QFileDialog.getOpenFileNames(self, title, self.download_picker_folder(),
                                                "Mod files (*.zip *.7z *.rar *.pak)")
        return [Path(f) for f in files]

    def install(self):
        """Both legacy and new install buttons use the same explicit preview."""
        r = self.current()
        if not r:
            return
        files = self._pick_many(f"Choose {r['name']} archive(s) to review")
        if files:
            self.review_installation(r, files)

    def review_requested_install(self, request):
        r = self.current()
        if not r or request.get("game_id") != r["id"]:
            return
        files = [Path(f) for f in request.get("archives", [])]
        if not files:
            files = self._pick_many(f"Choose {r['name']} archive(s) to review")
        if files:
            self.review_installation(r, files)

    def review_installation(self, recipe, files):
        """Read-only manifest -> three explicit consents -> fresh recheck."""
        if not recipe or self.current() is None or recipe["id"] != self.current()["id"]:
            return
        try:
            plan = install_review.build_install_plan(recipe, files, _roots())
        except (install_review.PlanRejected, RuntimeError, OSError,
                zipfile.BadZipFile) as exc:
            QMessageBox.warning(
                self, "Installation review refused (nothing changed)", str(exc))
            return
        dialog = InstallReviewDialog(
            plan, self, allow_install=self.allow_guided_installs)
        if dialog.exec() != QDialog.Accepted or not dialog.confirmed_by_user:
            return
        # This remains a hard safety gate even if a future preview accidentally
        # enables an install button or a test invokes a dialog directly.
        if not self.allow_guided_installs or not plan.approved_for_review:
            return
        try:
            install_review.revalidate(plan, recipe, _roots())
        except (install_review.PlanRejected, OSError, RuntimeError,
                zipfile.BadZipFile) as exc:
            QMessageBox.warning(
                self, "Game or archives changed — install cancelled", str(exc))
            return
        self._run(lambda: hub.install_many(recipe,
                                           [Path(f) for f in plan.archives], _roots()),
                  "Guided installation completed",
                  lambda out: f"Installed {len(out)} reviewed game files.\n"
                  "Original-file backups follow the reviewed installer policy.\n"
                  "No save files were intentionally changed.")

    def install_profile(self):
        """UEVR ZIP plan, explicit confirmation, then stale-plan revalidation."""
        recipe = self.current()
        if not recipe or not recipe.get("profile"):
            return
        zip_file = self._pick("Review UEVR profile ZIP before replacing anything")
        if zip_file is None:
            return
        try:
            plan = hub.review_profile_install(recipe, zip_file, _roots())
        except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, "UEVR profile review blocked", str(exc))
            return
        # Dev5C3 is a read-only milestone: live activation needs separate approval.
        dialog = ProfileReviewDialog(plan, self, allow_install=False)
        if dialog.exec() != QDialog.Accepted or not dialog.confirmed_by_user:
            return
        self._run(
            lambda: hub.install_profile(
                recipe, zip_file, _roots(),
                approved_fingerprint=plan.fingerprint, confirmed=True),
            "Verified UEVR profile installed",
            lambda out: f"Installed {len(out)} reviewed files.\n"
                        "Persistent original directory backup is retained.\n"
                        "Restoring later requires full checksum validation.")

    def uninstall(self):
        r = self.current()
        if not r:
            return
        if r.get("method") == "gameroot":
            try:
                entry = hub.state().get(r["id"])
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Cannot review original-file backup", str(exc))
                return
            if not entry:
                QMessageBox.information(
                    self, "No recorded game-root installation",
                    "No Hub-managed Cyberpunk installation is recorded. "
                    "Nothing will be removed.")
                return
            if entry.get("installer") != "gameroot-2":
                QMessageBox.warning(
                    self, "Legacy Cyberpunk install — automatic removal blocked",
                    "This installation record predates persistent originals. "
                    "The Hub cannot guarantee restoration of the working mod files. "
                    "Nothing has been removed. Preserve your game and review "
                    "the existing files manually before attempting migration.")
                return
            originals = entry.get("originals", {})
            restored = sum(v is not None for v in originals.values())
            removed = sum(v is None for v in originals.values())
            message = (
                f"Restore {restored} original Cyberpunk file(s) from verified "
                f"persistent backups, and remove {removed} files added by "
                "this recorded install?\n\n"
                "Every current file and original backup will be rehashed. "
                "Changes, missing backups and symlinks block all restoration. "
                "The retained originals remain in Hub storage afterward.\n\n"
                "Confirm the game is closed before proceeding.")
        else:
            message = (
                f"Remove the mod files for {r['name']} and restore backed-up originals?"
                if r.get("method") in {"bepinex", "ervr"}
                else f"Remove the mod files for {r['name']}?")
        if QMessageBox.question(
                self, "Review removal and restoration", message,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self._run(lambda: hub.uninstall(r["id"]), "Removed",
                      lambda out: f"Removed or restored {len(out)} recorded files.")

    def uninstall_profile(self):
        recipe = self.current()
        if not recipe or not recipe.get("profile"):
            return
        key = recipe["id"] + ":profile"
        review = profile_safety.review_restore(key)
        if not review["ready"]:
            QMessageBox.warning(
                self, "UEVR profile — recovery review required",
                review["reason"] + "\n\nAutomatic removal and restoration are blocked. "
                "Nothing has been changed.")
            return
        message = (
            f"Restore the previous {recipe['name']} UEVR profile?\n\n"
            f"Exact destination: {review['destination']}\n"
            f"Managed files verified: {review['installed_files']}\n"
            f"Original files retained: {review['original_files']} "
            f"({review['original_bytes']:,} bytes)\n\n"
            "The Hub will validate the entire installed directory again and "
            "check the retained original backup. Any additions, removals or "
            "changes block restoration. The backup remains retained afterward.")
        choice = QMessageBox.question(
            self, "Review verified UEVR profile restoration", message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if choice != QMessageBox.Yes:
            return
        self._run(lambda: hub.uninstall(key, profile_confirm=True),
                  "Verified UEVR profile restored",
                  lambda out: f"Safely restored the previous profile after "
                              f"checking {len(out)} installed files.")

    def run_injector(self):
        r = self.current()
        if not r:
            return
        try:
            if r.get("store") == "heroic-epic":
                try:
                    launch = hub.launch_injector(r, _roots())
                    dialog = HeroicInjectorDialog(r, self, launch=launch)
                except (RuntimeError, OSError) as exc:
                    dialog = HeroicInjectorDialog(r, self, error=str(exc))
                dialog.exec()
                return
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
        if r.get('handler') == 'kharvox-gog':
            self.show_kharvox_launch(proc)
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

    def choose_kharvox_folder(self):
        from . import kharvox
        path = QFileDialog.getExistingDirectory(self,'Choose the extracted KHARVOX 1.4 folder',str(Path.home()/'Games'))
        if not path:
            return
        try:
            kharvox.choose_directory(path,hub.game_path(self.current(),_roots()))
        except (RuntimeError,OSError) as exc:
            QMessageBox.warning(self,'KHARVOX folder not saved',str(exc))
            return
        self.refresh()

    def import_kharvox_bridge(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import the matching NAnners KHARVOX Bridge source package', str(Path.home()/'Downloads'), 'Bridge source archive (*.tar.gz)')
        if path:
            self.run_kharvox_bridge('prepare', bridge_archive=path)

    def run_kharvox_bridge(self, action, bridge_archive=None):
        from . import kharvox_bridge
        recipe = self.current()
        if not recipe or recipe.get('handler') != 'kharvox-gog':
            return
        try:
            launch = (kharvox_bridge.start(recipe, hub.game_path(recipe, _roots()), action, bridge_archive=bridge_archive)
                      if bridge_archive is not None else kharvox_bridge.start(recipe, hub.game_path(recipe, _roots()), action))
        except (RuntimeError, OSError) as exc:
            QMessageBox.warning(self, 'DOOM VR bridge', str(exc))
            return
        self.show_kharvox_launch(launch, action)

    def open_doom_diagnostics(self):
        from . import kharvox_bridge
        path = kharvox_bridge.state_dir() / 'logs'
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(self, 'DOOM diagnostics', 'Install or test the DOOM VR runner to create its diagnostics folder.')

    def show_kharvox_launch(self, launch, action='doom'):
        previous = getattr(self,'kharvox_dialog',None)
        if previous and previous.isVisible():
            if getattr(previous, 'bridge_launch', None) is launch:
                previous.raise_()
                return
            previous.close()
        dialog = QDialog(self)
        dialog.bridge_launch = launch
        names = {'prepare':'Install VR runner', 'probe':'Test VR bridge', 'doom':'Launch KHARVOX'}
        dialog.setWindowTitle('DOOM — ' + names[action])
        dialog.resize(800,480)
        layout = QVBoxLayout(dialog)
        messages = {'prepare':'Installing or verifying the isolated DOOM runner. The pinned base is downloaded if needed. Keep DOOM and KHARVOX closed.',
                    'probe':'Testing the DOOM VR bridge. Keep WiVRn connected; the JSON destination appears below.',
                    'doom':'KHARVOX is running through the tested isolated runner. Select DOOM and SFS in its window.'}
        status = QLabel(messages[action])
        status.setWordWrap(True)
        layout.addWidget(status)
        output = QPlainTextEdit()
        output.setReadOnly(True)
        layout.addWidget(output)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        timer = QTimer(dialog)
        def refresh():
            code = launch.poll()
            tail = launch.output_tail()[-12000:]
            output.setPlainText(tail or 'No console output yet. Game log diagnostics reads the prefix logs separately.')
            if code is not None:
                if code == 0 and action == 'prepare':
                    status.setText('Runner installation completed. Connect WiVRn, then use Test VR bridge.')
                elif code == 0 and action == 'probe':
                    status.setText('Bridge test passed. You can now Launch DOOM VR. This synthetic test does not verify gameplay.')
                else:
                    status.setText(f'{names[action]} exited with code {code}. Review the output and game logs; an exit code does not verify VR gameplay.')
                timer.stop()
                self.refresh()
        timer.timeout.connect(refresh)
        dialog.finished.connect(timer.stop)
        timer.start(1000)
        refresh()
        self.kharvox_dialog = dialog
        dialog.show()

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
        via = "Heroic" if store.startswith("heroic-") else ("Steam/MO2" if r.get("handler") == "skyrim-vr" else "Steam")
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
            self.preflight_results[r["id"]] = rep
            self.show_details()
            QMessageBox.information(self, "Preflight", hub.preflight_text(rep))

    def inspect_planned_archive(self, archive_path):
        """Use the existing validated read-only staging inspector only."""
        recipe = self.current()
        if not recipe:
            return
        if recipe.get("method") not in {"gameroot", "bepinex", "ervr"}:
            QMessageBox.information(
                self, "Manual package review required",
                "This profile has no supported generic archive inspector. "
                "Use the Setup guide for the correct package order. "
                "Nothing has been installed or changed.")
            return
        try:
            report = hub.inspect_archive(recipe, Path(archive_path))
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, "Archive rejected (nothing installed)", str(exc))
            return
        QMessageBox.information(self, "Read-only archive inspection", hub.inspect_text(report))

    def download_picker_folder(self):
        recipe = self.current()
        try:
            directory, _source = download_planner.folder_for(recipe) if recipe else (None, "")
        except (ValueError, RuntimeError, OSError):
            directory = None
        return str(directory if directory and directory.is_dir()
                   else Path.home() / "Downloads")

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
