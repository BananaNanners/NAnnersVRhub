"""NAnnersVRhub Qt window. Run with:  python -m vrhub.gui   (needs PySide6)"""
import sys
import subprocess
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QComboBox, QDialog, QDialogButtonBox, QFormLayout, QListWidget, QPlainTextEdit,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from . import __version__, app_updates, compatibility, heroic_epic, hub, live_tests, log_diagnostics, runtime, support_report, system_scan, updates
from .handlers import get_handler
from .cli import _roots
from .display_time import age_text, filename_stamp, local_time
from .theme import BLUE, GREEN, LOGO_PATH, MUTED, RED, STYLESHEET, TEXT, YELLOW
from .app_update_gui import HubUpdateController
from .controller_gui import ControllerBindingsPage


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
        self.scan_worker: ScanWorker | None = None
        self.scan_report: dict | None = None
        self._closing = False

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
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
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
        compat_layout = QVBoxLayout(compat_page)
        compat_layout.addLayout(_row(self.compat_refresh_btn, self.compat_copy_btn))
        compat_layout.addLayout(_row(self.record_test_btn, self.test_history_btn, self.log_diagnostics_btn))
        compat_layout.addWidget(self.support_report_btn)
        compat_layout.addWidget(self.compat_details)
        self.game_details_tabs = QTabWidget()
        self.game_details_tabs.addTab(self.details, "Setup guide")
        self.game_details_tabs.addTab(compat_page, "Compatibility profile")
        self.controller_bindings = ControllerBindingsPage()
        self.game_details_tabs.addTab(self.controller_bindings, "Controller bindings")
        self.game_details_tabs.currentChanged.connect(
            lambda index: self.refresh_compatibility() if index == 1 else None)
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
        self.kharvox_folder_btn = QPushButton("Choose KHARVOX folder…")
        self.doom_prepare_btn = QPushButton("Install VR runner")
        self.doom_probe_btn = QPushButton("Test VR bridge")
        self.doom_logs_btn = QPushButton("Open DOOM diagnostics")
        self.doom_import_btn = QPushButton("Import bridge package…")
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
        self.kharvox_folder_btn.clicked.connect(self.choose_kharvox_folder)
        self.doom_prepare_btn.clicked.connect(lambda: self.run_kharvox_bridge('prepare'))
        self.doom_probe_btn.clicked.connect(lambda: self.run_kharvox_bridge('probe'))
        self.doom_logs_btn.clicked.connect(self.open_doom_diagnostics)
        self.doom_import_btn.clicked.connect(self.import_kharvox_bridge)
        refresh_btn.clicked.connect(self.refresh)

        left = QVBoxLayout()
        left.addWidget(self.table)
        left.addLayout(_row(self.install_btn, self.uninstall_btn, self.profile_btn, self.unprofile_btn))
        left.addLayout(_row(self.copy_btn, self.inject_btn, self.game_launch_btn, self.game_play_btn, self.verify_btn, self.preflight_btn))
        left.addLayout(_row(self.inspect_btn, self.diag_btn, self.bridge_log_btn, self.check_btn, self.mark_btn))
        left.addLayout(_row(self.key_btn, self.kharvox_folder_btn, refresh_btn))
        left.addLayout(_row(self.doom_prepare_btn, self.doom_probe_btn, self.doom_logs_btn))
        left.addLayout(_row(self.doom_import_btn))
        main = QHBoxLayout()
        main.setSpacing(10)
        main.addLayout(left, 5)
        main.addWidget(self.game_details_tabs, 6)
        games_page = QWidget()
        games_page.setObjectName("gamesPage")
        games_page.setLayout(main)
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
        self.tabs.addTab(games_page, "Games")
        self.tabs.currentChanged.connect(lambda index: self.refresh_system_live() if index == 0 else None)
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
        root.addWidget(self.tabs, 1)
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
        if self._closing and not self.scan_worker and not (self.worker and self.worker.isRunning()) and not self.hub_updates.busy:
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
        # Polling threads must finish before the window can destroy them.
        self._closing = True
        self.scan_timer.stop()
        self.hub_updates.shutdown()
        if self.scan_worker or (self.worker and self.worker.isRunning()) or self.hub_updates.busy:
            event.ignore()
            return
        super().closeEvent(event)

    def current(self) -> dict | None:
        idx = self.table.currentRow()
        return self.rows[idx]["recipe"] if 0 <= idx < len(self.rows) else None

    def refresh(self):
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
                self.table.setItem(i, c, QTableWidgetItem(text))
        if self.rows:
            self.table.selectRow(keep if 0 <= keep < len(self.rows) else 0)
        self.show_details()

    def show_details(self):
        r = self.current()
        kharvox = bool(r and r.get('handler') == 'kharvox-gog')
        self.kharvox_folder_btn.setVisible(kharvox)
        for button in (self.doom_prepare_btn, self.doom_probe_btn, self.doom_logs_btn, self.doom_import_btn):
            button.setVisible(kharvox)
        for button in [self.install_btn,self.uninstall_btn,self.profile_btn,self.unprofile_btn,
                       self.copy_btn,self.inject_btn,self.verify_btn,self.inspect_btn,self.key_btn]:
            button.setVisible(not kharvox)
        self.controller_bindings.set_recipe(r)
        self.refresh_compatibility()
        self.details.setHtml(hub.details_html(r, self.update_results.get(r["id"]), hub.verify(r)) if r else "")
        can_install = bool(r and get_handler(r).install_supported(r))
        self.install_btn.setEnabled(can_install)
        self.uninstall_btn.setEnabled(bool(r and r.get("method") != "guide"))
        self.inject_btn.setEnabled(bool(r and r.get("method") == "uevr"))
        self.inject_btn.setText("Run UEVR injector")
        self.copy_btn.setEnabled(bool(r and r.get("store", "steam") == "steam"))
        label = hub.game_launcher_label(r) if r else None
        self.game_launch_btn.setText(label or "Launch game tool")
        self.game_launch_btn.setVisible(bool(label))
        self.game_launch_btn.setEnabled(bool(label))
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
        self.bridge_log_btn.setVisible(bool(r and hub.game_bridge_log(r)))
        if r:
            self.bridge_log_btn.setText(hub.game_bridge_log_label(r))
        self.update_live_status()

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

    # ---- update checking -------------------------------------------------
    def check_updates(self):
        if self.worker and self.worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking…")
        self.worker = UpdateWorker()
        self.worker.done.connect(self._updates_done)
        self.worker.finished.connect(self.close_when_idle)
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
        if not r:
            return
        message = (f"Remove the mod files for {r['name']} and restore backed-up originals?"
                   if r.get("method") in {"bepinex", "ervr"} else f"Remove the mod files for {r['name']}?")
        if QMessageBox.question(self, "Uninstall", message) == QMessageBox.Yes:
            self._run(lambda: hub.uninstall(r["id"]), "Removed",
                      lambda out: f"Removed or restored {len(out)} recorded files.")

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
