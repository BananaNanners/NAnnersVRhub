# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""DOOM-only, explicit save comparison and recovery window."""
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog,
                               QHeaderView, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from . import doom_saves
from .display_time import local_time


class SaveWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.done.emit(self.function())
        except Exception as exc:
            self.failed.emit(str(exc))


def summary(row):
    return (f"Mission: {row.get('mission', 'Unknown')}\n"
            f"Saved: {local_time(row.get('saved_at'))}\n"
            f"Recorded time value: {row.get('time_value', 'Unknown')}\n"
            f"Game version: {row.get('game_version') or 'Unknown'}\n"
            f"Files: {row.get('file_count', 0)}; bytes: {row.get('total_bytes', 0)}\n"
            f"Location: {row['root']}")


def save_state(row):
    if row["usable"]:
        return "Current target" if row["current"] else "Available"
    state = "Restore blocked — backup verification needed" if row.get("backup_verification_needed") else "Restore blocked"
    return "Current target — " + state.lower() if row["current"] else state


class DoomSavesDialog(QDialog):
    def __init__(self, recipe, parent=None, *, auto_scan=True, backend=None):
        super().__init__(parent)
        self.backend = backend or doom_saves
        self.recipe = recipe
        self.extra_roots = []
        self.report = None
        self.plan = None
        self.worker = None
        self.action = None
        self.last_backup = None
        self.setObjectName("doomSaveRecoveryDialog")
        self.setWindowTitle("DOOM (2016) — Find and restore saves")
        self.resize(1050, 650)
        layout = QVBoxLayout(self)
        self.note = note = QLabel("Scan Heroic, known KHARVOX experiment prefixes and recovery backups. Select a source to compare with the active save target. Dates alone do not prove progress. Nothing is synchronized automatically.")
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        self.scan_button = QPushButton("Scan save locations")
        self.choose_button = QPushButton("Choose save folder…")
        self.backup_button = QPushButton("Open recovery backup")
        self.backup_button.setEnabled(False)
        self.scan_button.clicked.connect(self.scan)
        self.choose_button.clicked.connect(self.choose)
        self.backup_button.clicked.connect(self.open_backup)
        for button in (self.scan_button, self.choose_button, self.backup_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel("Scan to locate saves. No source is selected automatically.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Location", "Mission", "Save date", "Time value", "Files", "State"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.table)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        self.result = QLabel("")
        self.result.setTextFormat(Qt.PlainText)
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.restore_button = QPushButton("Back up both sets and restore selected source…")
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self.request_restore)
        layout.addWidget(self.restore_button)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if auto_scan:
            self.scan()

    def _start(self, action, function, callback):
        if self.worker is not None:
            return
        self.action = action
        self.worker = SaveWorker(function, self)
        self.worker.done.connect(callback)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished_work)
        self._controls()
        self.worker.start()

    def _controls(self):
        idle = self.worker is None
        self.scan_button.setEnabled(idle)
        self.choose_button.setEnabled(idle)
        self.table.setEnabled(idle)
        self.restore_button.setEnabled(idle and self.plan is not None)

    def scan(self):
        if self.worker is not None:
            return
        self.plan = None
        self.report = None
        self.status.setText("Scanning save locations (read-only)…")
        extras = list(self.extra_roots)
        self._start("scan", lambda: self.backend.discover(self.recipe, extras), self.scanned)

    def scanned(self, report):
        self.report = report
        self.table.setRowCount(0)
        for index, row in enumerate(report["rows"]):
            self.table.insertRow(index)
            date = row.get("saved_at") or row.get("file_modified_at")
            date_text = local_time(date) if date else "Date unavailable"
            if row.get("file_modified_at"):
                date_text += " (folder files" + (", partial" if row.get("observation_partial") else "") + ")"
            count = str(row.get("file_count", "—"))
            if "observed_file_count" in row:
                count = str(row["observed_file_count"]) + ("+ (partial)" if row.get("observation_partial") else " (observed)")
            state = save_state(row)
            values = [row["label"] + (" — " + row["location_role"] if row.get("location_role") else ""), row.get("mission", "Not read"), date_text,
                      row.get("time_value", "—"), count, state]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(row["root"] + ("\n" + row["error"] if row.get("error") else "")
                                + ("\nDate source: " + row["date_source"] if row.get("date_source") else "")
                                + ("\n" + row["date_reason"] if row.get("date_reason") else ""))
                self.table.setItem(index, column, item)
        self.table.clearSelection()
        self.plan = None
        errors = [row["label"] + " — " + row["root"] + "\n" + row.get("error", "Restore blocked")
                  + (("\nDate unavailable: " if not row.get("file_modified_at") else "\nFile-date scan: ") + row["date_reason"]
                     if row.get("date_reason") else "") for row in report["rows"] if not row["usable"]]
        self.details.setPlainText("Choose a source row to compare complete save sets. The active target row cannot restore itself."
                                 + ("\n\nSCAN ISSUES (restore blocked)\n" + "\n\n".join(errors) if errors else ""))
        self.status.setText(f"Found {len(report['rows'])} save locations. No source selected."
                            + ("\nRestore blocked: " + " | ".join(dict.fromkeys(row.get("error", "Unknown scan error") for row in report["rows"] if not row["usable"])) if errors else "")
                            + ("\n" + "\n".join(report["notes"]) if report["notes"] else ""))

    def selection_changed(self):
        self.plan = None
        if not self.report:
            self._controls()
            return
        index = self.table.currentRow()
        if index < 0 or index >= len(self.report["rows"]) or not self.table.selectedItems():
            self._controls()
            return
        row = self.report["rows"][index]
        target = next((r for r in self.report["rows"] if r["current"] and r["usable"]), None)
        if not row["usable"]:
            self.details.setPlainText("Restore blocked: " + row.get("error", "Save set needs review.")
                                     + "\nLocation: " + row["root"]
                                     + ("\nObserved folder file date: " + local_time(row["file_modified_at"]) + " (not validated save data)"
                                        if row.get("file_modified_at") else "\nDate unavailable")
                                     + ("\n" + row["date_reason"] if row.get("date_reason") else ""))
        elif row["current"]:
            self.details.setPlainText("ACTIVE SAVE TARGET\n" + summary(row))
        elif target is None:
            self.details.setPlainText("A unique, complete active save target is required before restoring.\n\n" + summary(row))
        elif row["fingerprint"] == target["fingerprint"]:
            self.details.setPlainText("This complete save set already matches the active save targets. No restore is needed.\n\n" + summary(row))
        elif row["game_version"] and target["game_version"] and row["game_version"] != target["game_version"]:
            self.details.setPlainText("Different game versions; restore blocked pending compatibility review.\n\nSOURCE\n"
                                     + summary(row) + "\n\nACTIVE SAVE TARGET\n" + summary(target))
        else:
            self.plan = {"source": deepcopy(row), "target": deepcopy(target)}
            self.details.setPlainText("SELECTED SOURCE\n" + summary(row) + "\n\nACTIVE SAVE TARGET TO REPLACE\n"
                                     + summary(target) + "\n\nBoth complete sets will be backed up and verified. Only the selected save folder is copied; review its contents first. Source files are preserved.")
        self._controls()

    def choose(self):
        path = QFileDialog.getExistingDirectory(self, "Choose the complete DOOM savegame folder", str(Path.home()))
        if path:
            self.extra_roots.append(path)
            self.scan()

    def confirm_restore(self, plan):
        question = QMessageBox(self)
        question.setObjectName("doomSaveConfirmation")
        question.setWindowTitle("Restore selected DOOM saves?")
        question.setIcon(QMessageBox.Question)
        question.setTextFormat(Qt.PlainText)
        question.setText("Close DOOM, KHARVOX and Heroic first.\n\nSOURCE\n" + summary(plan["source"])
                         + "\n\nREPLACE ACTIVE SAVE TARGET\n" + summary(plan["target"])
                         + "\n\nBack up both sets and restore the complete selected source? Recovery backups are retained.")
        question.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        question.setDefaultButton(QMessageBox.No)
        return question.exec() == QMessageBox.Yes

    def request_restore(self):
        if self.worker is not None or self.plan is None:
            return
        plan = deepcopy(self.plan)
        if not self.confirm_restore(plan):
            return
        self.status.setText("Backing up, verifying and restoring the selected complete save set…")
        self._start("restore", lambda: self.backend.restore(plan, self.recipe), self.restored)

    def restored(self, result):
        self.last_backup = result["backup"]
        self.backup_button.setEnabled(True)
        self.result.setText(f"Restored {result['file_count']} files; SHA-256 verification passed.\nBackup: {result['backup']}\n"
                            "Launch DOOM normally and check Continue. Keep the backup until you confirm your progress."
                            + ("\n" + result["warning"] if result.get("warning") else ""))

    def failed(self, message):
        self.status.setText(message)
        if self.action == "restore":
            self.result.setText("Restore stopped.\n" + message)

    def finished_work(self):
        action = self.action
        self.worker.deleteLater()
        self.worker = None
        self.action = None
        self._controls()
        if action == "restore":
            self.scan()

    def open_backup(self):
        if self.last_backup:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_backup))

    def reject(self):
        if self.worker is None:
            super().reject()
        else:
            self.status.setText("Wait for the current save operation to finish before closing.")

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
            self.status.setText("Wait for the current save operation to finish before closing.")
        else:
            super().closeEvent(event)
