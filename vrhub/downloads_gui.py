# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A: native read-only guided downloads and archive inspection page.

Changing a folder only updates Hub-specific preferences. Archive scans hash
local files and validate pinned checksums, but never download or install.
"""
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QPlainTextEdit, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from . import download_planner as planner, archive_scans
from .table_columns import enable_spreadsheet_columns

COLOR = {
    "Pinned SHA-256 verified": "#4FE39A",
    "Possible archive — inspect first": "#FFD21A",
    "Hash mismatch — do not install": "#FF5B50",
    "Hash not verified — do not install": "#FF5B50",
    "Not found locally": "#A7ADB7",
    "Archive changed — rescan required": "#FF5B50",
}


class LocalInventoryWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, recipe, folder, parent=None):
        super().__init__(parent)
        self.recipe = recipe
        self.folder = folder

    def run(self):
        try:
            result = planner.build_plan(self.recipe, self.folder)
        except (OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)


class ResponsiveDownloadActions(QWidget):
    """One row for broad desktops; two columns for compact KDE windows."""

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.buttons = tuple(buttons)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(7)
        self.columns = 0
        self._set_columns(2)

    def _set_columns(self, count):
        if count == self.columns:
            return
        for button in self.buttons:
            self.grid.removeWidget(button)
        for index, button in enumerate(self.buttons):
            row, col = divmod(index, count)
            self.grid.addWidget(button, row, col)
        self.columns = count
        self.grid.invalidate()
        self.setMinimumHeight(self.grid.minimumSize().height())
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._set_columns(5 if self.width() >= 930 else 2)


class GuidedDownloadsPage(QWidget):
    """One plan per selected game; no hidden installer actions."""
    inspect_requested = Signal(str)
    scan_idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("guidedDownloadsPage")
        self.recipe = None
        self._last_id = None
        self._last_folder = None
        self._last_plan = None
        self.worker = None
        self._saved_error = None
        try:
            self._saved = archive_scans.load_saved()
        except (ValueError, OSError) as exc:
            # A damaged snapshot file must be preserved, never overwritten.
            self._saved, self._saved_error = {}, str(exc)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(9)

        title = QLabel("GUIDED DOWNLOADS & INSTALL PLAN")
        title.setObjectName("downloadsHeading")
        outer.addWidget(title)

        explanation = QLabel(
            "Use downloaded archives you already own. Pinned hashes can be "
            "verified automatically; filename-only matches still require review. "
            "Scanning does NOT download, install, move or delete anything. "
            "Drag table column borders to resize, or double-click to fit text.")
        explanation.setObjectName("downloadsExplanation")
        explanation.setWordWrap(True)
        outer.addWidget(explanation)

        self.location = QLabel("Select a game to review its archive library.")
        self.location.setObjectName("downloadsLocation")
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.location)

        self.set_global = QPushButton("Set default folder…")
        self.set_global.setObjectName("downloadsAction")
        self.set_game = QPushButton("Set this game's folder…")
        self.set_game.setObjectName("downloadsAction")
        self.clear_game = QPushButton("Use default folder")
        self.clear_game.setObjectName("downloadsAction")
        self.reset_global = QPushButton("Reset default")
        self.reset_global.setObjectName("downloadsAction")
        self.scan = QPushButton("Scan local archives")
        self.scan.setObjectName("downloadsScan")
        self.action_toolbar = ResponsiveDownloadActions((
            self.set_global, self.set_game, self.clear_game,
            self.reset_global, self.scan,
        ))
        outer.addWidget(self.action_toolbar)
        self.set_global.clicked.connect(lambda: self._choose_folder("global"))
        self.set_game.clicked.connect(lambda: self._choose_folder("game"))
        self.clear_game.clicked.connect(self._clear_game)
        self.reset_global.clicked.connect(self._reset_global)
        self.scan.clicked.connect(self.start_scan)

        self.progress = QProgressBar()
        self.progress.setObjectName("downloadsProgress")
        self.progress.setRange(0, 0)
        self.progress.hide()
        outer.addWidget(self.progress)

        self.summary = QLabel("Choose a game, then scan for local archives.")
        self.summary.setObjectName("downloadsSummary")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        self.scan_age = QLabel("No scan saved for this game yet.")
        self.scan_age.setObjectName("downloadsScanAge")
        self.scan_age.setWordWrap(True)
        outer.addWidget(self.scan_age)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("downloadsTable")
        self.table.setHorizontalHeaderLabels(
            ("Component / package", "Install stage", "Local archive", "Verification", "Download page"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.columns = enable_spreadsheet_columns(
            self.table, "guided-downloads", (225, 160, 345, 230, 142),
            expand_weights=(2, 1, 3, 2, 0), min_row_height=48)
        outer.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.inspect = QPushButton("Inspect selected archive (read-only)")
        self.inspect.setObjectName("downloadsAction")
        self.inspect.setEnabled(False)
        self.inspect.clicked.connect(self._inspect)
        footer.addWidget(self.inspect)
        footer.addStretch()
        outer.addLayout(footer)

        self.guidance = QLabel(
            "Only approved installer workflows should modify game files. "
            "The existing Setup guide remains the source for installation order.")
        self.guidance.setObjectName("downloadsExplanation")
        self.guidance.setWordWrap(True)
        outer.addWidget(self.guidance)
        self.table.itemSelectionChanged.connect(self._update_inspect_button)
        self.set_recipe(None)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        super().closeEvent(event)

    def _folder(self):
        return planner.folder_for(self.recipe) if self.recipe else (None, "")

    def set_recipe(self, recipe):
        self.recipe = recipe
        rid = recipe.get("id") if recipe else None
        error = None
        try:
            folder, source = self._folder()
        except (ValueError, RuntimeError, OSError) as exc:
            folder, source, error = None, "", str(exc)
        if rid != self._last_id or folder != self._last_folder:
            self._last_id = rid
            self._last_folder = folder
        saved = self._saved.get(rid) if rid and folder else None
        if saved and saved["folder"] == str(folder):
            # Resolve again on game switch: changing or removing an archive
            # must invalidate previously verified status.
            self._last_plan = archive_scans.displayed_record(saved)["plan"]
            self._set_scan_age(saved)
        else:
            self._last_plan = None
            self.scan_age.setText(
                self._saved_error or "No scan saved for this game yet. "
                "Scan local archives to create a per-game snapshot.")
        for btn in (self.set_global, self.set_game, self.clear_game,
                    self.reset_global, self.scan):
            btn.setEnabled(bool(recipe) and (not self.worker or not self.worker.isRunning()))
        if recipe:
            self.location.setText(
                f"{source}: {folder}" if folder else
                f"Download preferences unavailable: {error}")
        else:
            self.location.setText("Select a game to review its archive library.")
        self.location.setToolTip(str(folder or error or ""))
        if self._last_plan is None:
            self._display_unsanned(recipe, error)
        else:
            self._show_plan(self._last_plan)

    def _set_scan_age(self, record):
        scanned = datetime.fromisoformat(record["scanned_at"]).astimezone()
        self.scan_age.setText(
            f"Saved scan: {scanned:%Y-%m-%d %H:%M} (local time) · "
            "Historical snapshot, not a fresh verification. "
            "Rescan when archives are added, removed or updated.")

    def _invalidate_changed_locations(self):
        try:
            invalid = archive_scans.remove_changed_folders()
        except (ValueError, OSError) as exc:
            self._saved_error = str(exc)
            self.scan_age.setText(
                f"Folder selection saved. Existing scan snapshots need review: {exc}")
            return
        for rid in invalid:
            self._saved.pop(rid, None)

    def _display_unsanned(self, recipe, error):
        self._set_rows([
            {**c, "phase_label": ("Later: install after first flat launch"
                                   if c["phase"] > 1 else "Stage 1: prerequisites"),
             "status": "Not checked", "file": ""}
            for c in planner.plan_components(recipe)] if recipe else [])
        self.summary.setText(
            f"Cannot read preferences: {error}" if error else
            "Scan local archives to find candidate packages. Nothing is installed."
            if recipe else "Select a game to review its archive library.")

    def _choose_folder(self, scope):
        if not self.recipe:
            return
        existing, _ = self._folder()
        selected = QFileDialog.getExistingDirectory(
            self, "Choose existing mod archive folder",
            str(existing if existing and existing.is_dir() else Path.home() / "Downloads"))
        if not selected:
            return
        try:
            planner.set_location(scope, selected,
                                 self.recipe["id"] if scope == "game" else None)
            self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Folder was NOT saved: {exc}")

    def _clear_game(self):
        if not self.recipe:
            return
        try:
            planner.set_location("game", None, self.recipe["id"])
            self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Folder preference was NOT changed: {exc}")

    def _reset_global(self):
        if not self.recipe:
            return
        try:
            planner.set_location("global", None)
            self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Default folder preference was NOT changed: {exc}")

    def start_scan(self):
        if not self.recipe or (self.worker and self.worker.isRunning()):
            return
        try:
            folder, _ = self._folder()
        except (ValueError, RuntimeError, OSError) as exc:
            self.summary.setText(f"Cannot scan folder: {exc}")
            return
        self.progress.show()
        self.summary.setText("Scanning local archives and checking any pinned release hashes…")
        for btn in (self.set_global, self.set_game, self.clear_game,
                    self.reset_global, self.scan):
            btn.setEnabled(False)
        worker = LocalInventoryWorker(dict(self.recipe), folder, self)
        self.worker = worker
        worker.done.connect(lambda result, token=worker: self._completed(result, token))
        worker.failed.connect(lambda message, token=worker: self._failed(message, token))
        worker.finished.connect(lambda token=worker: self._finished(token))
        worker.start()

    def _completed(self, result, worker):
        if self.worker is not worker:
            return
        # Worker results belong to the game that launched the scan, not
        # whatever game happens to be selected when it finishes.
        if (result.get("game_id") != worker.recipe.get("id") or
                result.get("folder") != str(worker.folder)):
            return
        try:
            active, _ = planner.folder_for(worker.recipe)
            if str(active) != result["folder"]:
                return  # its folder changed since scan started
            rec = archive_scans.persist(result)
        except (OSError, ValueError, RuntimeError) as exc:
            if self.recipe and self.recipe["id"] == result["game_id"]:
                self._last_plan = result
                self._show_plan(result)
                self.scan_age.setText(
                    f"Scan completed but could not be saved: {exc}")
            return
        self._saved[worker.recipe["id"]] = rec
        self._saved_error = None
        if (self.recipe and self.recipe["id"] == result["game_id"] and
                self._last_folder and str(self._last_folder) == result["folder"]):
            self._last_plan = archive_scans.displayed_record(rec)["plan"]
            self._set_scan_age(rec)
            self._show_plan(self._last_plan)

    def _failed(self, message, worker):
        if self.worker is worker:
            self.summary.setText(f"Could not scan archive folder: {message}")

    def _finished(self, worker):
        if self.worker is not worker:
            return
        self.progress.hide()
        self.worker = None
        self.set_recipe(self.recipe)
        worker.deleteLater()
        self.scan_idle.emit()

    def _show_plan(self, plan):
        self._set_rows(plan["rows"])
        changed = plan.get("changed", 0)
        self.summary.setText(
            f'{plan["scanned"]} archives found · {plan["verified"]} pinned hashes verified '
            f'· {plan["possible"]} possible matches needing inspection '
            f'· {plan["mismatch"]} mismatched (BLOCKED) '
            f'· {plan["unverified"]} unchecked (BLOCKED) · {plan["missing"]} missing'
            + (f' · {changed} changed — rescan required' if changed else "")
            + (f' — {plan["warning"]}' if plan.get("warning") else ""))
        self.guidance.setText(
            "Stage 1: inspect and install prerequisites using the existing installer. "
            "Stage 2 components must wait for the recipe's flat-game first-run step. "
            "Finding an archive does not establish game compatibility or VR readiness.")

    def _set_rows(self, records):
        self.table.setRowCount(0)  # prevent stale QTableWidget link widgets
        self.table.setRowCount(len(records))
        for i, record in enumerate(records):
            self.table.setRowHeight(i, 52)
            values = (
                str(record["name"]),
                str(record["phase_label"]),
                Path(record["file"]).name if record.get("file") else "—",
                record["status"],
            )
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(
                    str(record["file"]) if col == 2 and record.get("file") else value)
                if col == 3:
                    cell.setForeground(QColor(COLOR.get(value, "#A7ADB7")))
                cell.setData(Qt.UserRole, record.get("file", ""))
                self.table.setItem(i, col, cell)
            url = planner.source_url(record.get("url"))
            if url:
                btn = QPushButton("Open source")
                btn.setObjectName("downloadsSourceButton")
                btn.setToolTip(f"Open external source page (no download): {url}")
                btn.clicked.connect(lambda checked=False, uri=url:
                                    QDesktopServices.openUrl(QUrl(uri)))
                self.table.setCellWidget(i, 4, btn)
            else:
                self.table.setItem(i, 4, QTableWidgetItem("—"))
        self.columns.schedule_rows()
        self._update_inspect_button()

    def _update_inspect_button(self):
        row = self.table.currentRow()
        entry = self.table.item(row, 0) if row >= 0 else None
        path = entry.data(Qt.UserRole) if entry else None
        self.inspect.setEnabled(bool(path and Path(path).is_file()))

    def _inspect(self):
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        if cell:
            path = cell.data(Qt.UserRole)
            if path and Path(path).is_file():
                self.inspect_requested.emit(str(path))
