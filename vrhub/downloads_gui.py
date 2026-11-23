# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A: native read-only guided downloads and archive inspection page.

Changing a folder only updates Hub-specific preferences. Archive scans hash
local files and validate pinned checksums, but never download or install.
"""
from pathlib import Path
import copy
from html import escape
from datetime import datetime
from threading import Event

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView,
    QApplication, QLabel, QInputDialog, QMessageBox, QLayout, QMenu, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from . import download_planner as planner, archive_scans, archive_releases, verified_download, hub, archive_update_comparison, installed_integrity, update_readiness, preupdate_safety, update_integration, unified_update_plan, real_readiness_audit, ownership_triage, preservation_decisions, update_manifest_preview, destination_coverage
from .table_columns import enable_spreadsheet_columns
from .archive_checklist_ui import status_icon
from .install_review import human_file_size

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

    def __init__(self, recipe, folders, parent=None):
        super().__init__(parent)
        self.recipe = recipe
        self.folders = tuple(folders)

    def run(self):
        try:
            catalogs, errors = archive_releases.catalogs_for(self.recipe)
            result = planner.build_plan(self.recipe, self.folders,
                                        release_catalogs=catalogs, release_errors=errors)
        except (OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)


class InstalledIntegrityWorker(QThread):
    """Explicit one-game, read-only file hash job; never installs."""
    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, recipe, parent=None):
        super().__init__(parent)
        self.recipe = dict(recipe)
        self.cancel_flag = Event()

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        try:
            result = installed_integrity.verify(self.recipe, cancel=self.cancel_flag)
        except installed_integrity.Cancelled:
            self.cancelled.emit()
        except Exception as exc:
            # Untrusted historical manifests must never crash the QThread.
            self.failed.emit(str(exc))
        else:
            # The former "Verify mods" checks required component presence,
            # not bytes. Keep that distinct from current SHA-256 integrity.
            if self.cancel_flag.is_set():
                self.cancelled.emit()
                return
            try:
                presence = hub.verify(self.recipe)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
                result["presence"] = {"status": "Unknown",
                                      "detail": "Required-mod presence check unavailable."}
            else:
                if isinstance(presence, dict):
                    rows = presence.get("rows", [])
                    result["presence"] = {
                        "status": "Ready" if presence.get("ready") else "Needs review",
                        "ok": presence.get("ok", 0),
                        "total": presence.get("total", len(rows)),
                        "required_bad": [
                            {"name": str(row.get("name", "Dependency")),
                             "status": str(row.get("status", "unknown"))}
                            for row in presence.get("required_bad", [])[:24]
                            if isinstance(row, dict)],
                        "later_bad": [
                            {"name": str(row.get("name", "Dependency")),
                             "status": str(row.get("status", "unknown"))}
                            for row in presence.get("later_bad", [])[:24]
                            if isinstance(row, dict)],
                    }
                else:
                    result["presence"] = None
            if self.cancel_flag.is_set():
                self.cancelled.emit()
                return
            self.done.emit(result)


class PreUpdateSafetyWorker(QThread):
    """User-requested, read-only snapshot/ZIP/backup review; never installs."""
    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, recipe, scan, state, decisions, integrity, parent=None):
        super().__init__(parent)
        self.recipe = copy.deepcopy(recipe)
        self.scan = copy.deepcopy(scan)
        self.state = copy.deepcopy(state)
        self.decisions = copy.deepcopy(decisions)
        self.integrity = copy.deepcopy(integrity)
        self.cancel_flag = Event()

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        try:
            result = preupdate_safety.review(
                self.recipe, self.scan, self.state, self.decisions,
                self.integrity, cancel=self.cancel_flag)
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # Pure, read-only adapter analysis, no executable handoff.
            result["integration"] = update_integration.assess(
                self.recipe, self.state, self.decisions, self.integrity, result)
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # Consolidate review-only gates; never build an executable plan.
            result["unified"] = unified_update_plan.assess(
                self.recipe, result, result["integration"])
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # Explicitly requested REAL directory metadata audit. Observe
            # only recipe-discovered directories; do not hash current files,
            # adopt legacy mods or create a live installation capability.
            result["real_audit"] = real_readiness_audit.audit_game(
                self.recipe, self.state, integrity=self.integrity,
                safety=result, integration=result["integration"])
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # Triage consumes only the prior on-demand SHA result and validated
            # read-only ownership audit. No file reads, adoption or writes.
            result["triage"] = ownership_triage.assess(
                self.recipe, self.state, result["real_audit"],
                integrity=self.integrity)
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # This never saves file decisions or authorizes an update: the
            # existing review displays recommendations only. No auto-adoption.
            result["preservation"] = preservation_decisions.assess(
                self.recipe, result["triage"])
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # Only sampled read-only real mappings: NEVER an executable
            # before/after plan. A complete manifest exists for fake fixtures.
            result["manifest_preview"] = update_manifest_preview.preview_from_review(
                self.recipe, result, result["preservation"])
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
            # Audit the bounded FULL recipe install-target lists in this
            # on-demand result. No live game compatibility or update authority.
            result["coverage"] = destination_coverage.assess(
                self.recipe, result, result["preservation"],
                validated_manifest=result["manifest_preview"])
            if self.cancel_flag.is_set():
                raise installed_integrity.Cancelled()
        except installed_integrity.Cancelled:
            self.cancelled.emit()
        except Exception:
            # Untrusted saved manifests must fail closed, without leaking paths.
            self.failed.emit("Backup or archive evidence could not be inspected safely.")
        else:
            self.done.emit(result)


class VerifiedArchiveDownloadWorker(QThread):
    """One explicitly authorized, digest-pinned download; never installs."""
    progress_changed = Signal(object, object)
    succeeded = Signal(object)
    rejected = Signal(str)
    cancelled = Signal(str)

    def __init__(self, authority, parent=None):
        super().__init__(parent)
        self.authority = authority
        self.cancel_flag = Event()

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        try:
            result = verified_download.download(
                self.authority, cancel_event=self.cancel_flag,
                progress=lambda done, total:
                    self.progress_changed.emit(done, total))
        except verified_download.DownloadCancelled as exc:
            self.cancelled.emit(str(exc))
        except (verified_download.DownloadRejected, OSError, ValueError) as exc:
            self.rejected.emit(str(exc))
        else:
            self.succeeded.emit(result)


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
        self._set_columns(min(len(self.buttons),
                              5 if self.width() >= 930 else 2))


class GuidedDownloadsPage(QWidget):
    """One plan per selected game; no hidden installer actions."""
    inspect_requested = Signal(str)
    install_review_requested = Signal(object)
    scan_idle = Signal()
    download_idle = Signal()
    advanced_availability_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("guidedDownloadsPage")
        self.recipe = None
        self._last_id = None
        self._last_folder = None
        self._last_roots = ()
        self._last_plan = None
        self.worker = None
        self.download_worker = None
        self.integrity_worker = None
        self._integrity_result = None
        self.allow_transfers = True
        self._download_notice = None  # (game_id, result message, color)
        self._rescan_after_download = False
        self._saved_error = None
        self._download_cancelling = False
        self._comparison_online = None
        try:
            self._saved = archive_scans.load_saved()
        except (ValueError, OSError) as exc:
            # A damaged snapshot file must be preserved, never overwritten.
            self._saved, self._saved_error = {}, str(exc)

        outer = QVBoxLayout(self)
        # Prevent expanding read-only review widgets from overlapping later
        # actions inside the containing QTabWidget/QScrollArea.
        outer.setSizeConstraint(QLayout.SetMinimumSize)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(9)

        title = QLabel("ARCHIVE DEPENDENCIES")
        title.setObjectName("downloadsHeading")
        outer.addWidget(title)

        explanation = QLabel(
            "Find downloaded VR dependencies, then review what needs installing. "
            "Scanning never changes game files.")
        explanation.setObjectName("downloadsExplanation")
        explanation.setWordWrap(True)
        outer.addWidget(explanation)
        self.upstream_link = QLabel()
        self.upstream_link.setObjectName("downloadsExplanation")
        self.upstream_link.setWordWrap(True)
        self.upstream_link.setTextFormat(Qt.RichText)
        self.upstream_link.setOpenExternalLinks(False)
        self.upstream_link.linkActivated.connect(
            lambda url: QDesktopServices.openUrl(QUrl(url)) if planner.source_url(url) else None)
        self.upstream_link.hide()
        outer.addWidget(self.upstream_link)

        self.location = QLabel("Select a game to review its archive library.")
        self.location.setObjectName("downloadsLocation")
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.location)

        self.set_global = QPushButton("Choose shared extra folder")
        self.set_global.setObjectName("downloadsAction")
        self.set_game = QPushButton("Add game archive folder")
        self.set_game.setObjectName("downloadsAction")
        self.clear_game = QPushButton("Use shared extra for this game")
        self.clear_game.setObjectName("downloadsAction")
        self.reset_global = QPushButton("Remove shared extra folder")
        self.reset_global.setObjectName("downloadsAction")
        self.scan = QPushButton("Scan local archives")
        self.scan.setObjectName("downloadsScan")
        # Brief, deliberately line-broken native tooltips. One action per
        # button; no multi-paragraph mouse hover covering other controls.
        self.set_global.setToolTip(
            "Choose an extra shared scan folder.\n"
            "Games without custom folders use it.\n"
            "Archives are not moved or downloaded.")
        self.set_game.setToolTip(
            "Add a folder for this game only.\n"
            "Prior scan sets remain in history.\n"
            "Other games keep their saved scans.")
        self.clear_game.setToolTip(
            "Remove this game's additional archive folder.\n"
            "Downloads and shared folder remain active.\n"
            "Unchanged-folder scans stay saved.")
        self.reset_global.setToolTip(
            "Remove the optional shared archive folder.\n"
            "Custom game folders stay selected.\n"
            "Unchanged-folder scans stay saved.")
        self.scan.setToolTip(
            "Scan Downloads and this game's optional extra folder.\n"
            "Preserve previous scans by folder combination.\n"
            "No archives are installed or changed.")
        # Dev5D1-B: one folder menu replaces four persistent buttons.
        # Keep each original action object and its signal handler so folder
        # selection, default clearing, and saved scans behave exactly as before.
        self.folder_menu_button = QPushButton("Archive folder")
        self.folder_menu_button.setObjectName("downloadsAction")
        self.folder_menu_button.setToolTip(
            "Add or change the game's extra archive scan folder.\n"
            "No archives are moved or installed.")
        self.folder_menu = QMenu(self.folder_menu_button)
        self.folder_menu_actions = {}
        for btn in (self.set_game, self.set_global,
                    self.clear_game, self.reset_global):
            btn.setParent(self)
            btn.hide()
            action = self.folder_menu.addAction(btn.text())
            action.triggered.connect(
                lambda _checked=False, original=btn:
                    original.click() if original.isEnabled() else None)
            self.folder_menu_actions[btn] = action
        self.saved_folder_action = self.folder_menu.addAction("Use previous archive folder (rescan if needed)")
        self.saved_folder_action.triggered.connect(self._use_saved_folder)
        self.saved_folder_action.setVisible(False)
        self.folder_menu.aboutToShow.connect(self._sync_folder_actions)
        self.folder_menu_button.setMenu(self.folder_menu)
        self.action_toolbar = ResponsiveDownloadActions((
            self.folder_menu_button, self.scan,
        ))
        outer.addWidget(self.action_toolbar)
        self.folder_action_feedback = QLabel("")
        self.folder_action_feedback.setObjectName("downloadsFolderFeedback")
        self.folder_action_feedback.setWordWrap(True)
        self.folder_action_feedback.hide()
        outer.addWidget(self.folder_action_feedback)
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
        self.saved_scan_count = QLabel("")
        self.saved_scan_count.setObjectName("downloadsSavedScanCount")
        self.saved_scan_count.setWordWrap(True)
        outer.addWidget(self.saved_scan_count)
        self.backup_safety_status = QLabel("")
        self.backup_safety_status.setObjectName("downloadsBackupSafety")
        self.backup_safety_status.setWordWrap(True)
        self.backup_safety_status.hide()
        outer.addWidget(self.backup_safety_status)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("downloadsTable")
        self.table.setHorizontalHeaderLabels(
            ("Dependency", "Install stage", "Downloaded archive", "Verification", "Source"))
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
        # Visual archive-first ordering keeps logical columns unchanged, so
        # remembered widths, existing row selections and backend IDs survive.
        header = self.table.horizontalHeader()
        for visual, logical in enumerate((2, 0, 3, 1, 4)):
            header.moveSection(header.visualIndex(logical), visual)
        outer.addWidget(self.table, 1)

        # Deep diagnostics, not a second player-facing Updates workflow.
        # Preserve the historical read-only provenance/safety widgets and
        # their test hooks, but keep them in a collapsed technical disclosure.
        self.comparison_toggle = QPushButton("Advanced diagnostics ▸")
        self.comparison_toggle.setObjectName("downloadsAction")
        self.comparison_toggle.setCheckable(True)
        self.comparison_toggle.setToolTip(
            "Optional technical details about downloaded ZIPs, installed-file "
            "evidence and preservation risks. For versions use the Updates tab. "
            "Nothing is installed or changed here.")
        self.comparison_panel = QWidget(self)
        comparison_layout = QVBoxLayout(self.comparison_panel)
        comparison_layout.setContentsMargins(0, 0, 0, 0)
        comparison_layout.setSpacing(5)
        self.comparison_note = QLabel(
            "Technical archive evidence only. See Updates for installed and latest "
            "versions. These records help diagnose unclear ZIPs, ownership and "
            "preservation risks; they never authorize replacement.")
        self.comparison_note.setWordWrap(True)
        comparison_layout.addWidget(self.comparison_note)
        self.comparison_summary = QLabel()
        self.comparison_summary.setWordWrap(True)
        comparison_layout.addWidget(self.comparison_summary)
        # Updates alone owns the visible installed/latest version comparison.
        self.comparison_summary.hide()
        self.readiness_summary = QLabel(
            "Technical readiness evidence: no installation or update authorized.")
        self.readiness_summary.setObjectName("archiveReadinessSummary")
        self.readiness_summary.setWordWrap(True)
        comparison_layout.addWidget(self.readiness_summary)
        self.readiness_summary.hide()
        self.comparison_table = QTableWidget(0, 5)
        self.comparison_table.setObjectName("archiveVersionComparisonTable")
        self.comparison_table.setHorizontalHeaderLabels(
            ("Dependency", "Installed (Hub)", "Downloaded (scan)", "Latest online", "Update readiness"))
        self.comparison_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.comparison_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.comparison_table.setWordWrap(True)
        self.comparison_table.setAlternatingRowColors(True)
        self.comparison_table.setShowGrid(False)
        self.comparison_table.verticalHeader().hide()
        self.comparison_table.setMinimumHeight(150)
        self.comparison_table.setMaximumHeight(280)
        self.comparison_columns = enable_spreadsheet_columns(
            self.comparison_table, "archive-version-comparison",
            (200, 170, 225, 140, 275),
            expand_weights=(2, 1, 2, 1, 3), min_row_height=55)
        comparison_layout.addWidget(self.comparison_table)
        self.comparison_table.hide()
        self.safety_button = QPushButton("Review replacement safety (read-only)")
        self.safety_button.setObjectName("downloadsAction")
        self.safety_button.setToolTip(
            "On demand, inspect known managed file impact, retained-original backup "
            "SHA-256 evidence, candidate ZIP mapping and possible conflicts. "
            "This does NOT approve replacement or simulate rollback.")
        self.safety_button.clicked.connect(self._start_safety_review)
        comparison_layout.addWidget(self.safety_button)
        self.safety_summary = QLabel("Replacement safety: not reviewed.")
        self.safety_summary.setObjectName("preUpdateSafetySummary")
        self.safety_summary.setWordWrap(True)
        comparison_layout.addWidget(self.safety_summary)
        self.safety_details = QPlainTextEdit()
        self.safety_details.setObjectName("preUpdateSafetyDetails")
        self.safety_details.setReadOnly(True)
        self.safety_details.setMinimumHeight(140)
        self.safety_details.setMaximumHeight(230)
        self.safety_details.hide()
        comparison_layout.addWidget(self.safety_details)
        self.safety_worker = None
        self._safety_result = None
        # This page sits inside a scroll area. Explicitly reserve enough
        # vertical space when disclosure children appear; otherwise Qt may
        # compress the panel and overlap the evidence table and safety review.
        self.comparison_panel.setMinimumHeight(0)
        self.comparison_panel.hide()
        self._comparison_scroll_timer = QTimer(self)
        self._comparison_scroll_timer.setSingleShot(True)
        self._comparison_scroll_timer.timeout.connect(self._scroll_to_comparison)
        self.comparison_toggle.toggled.connect(self._toggle_comparison)
        outer.addWidget(self.comparison_toggle)
        outer.addWidget(self.comparison_panel)

        integrity_line = QHBoxLayout()
        integrity_line.setSpacing(8)
        self.integrity_button = QPushButton("Verify installed files")
        self.integrity_button.setObjectName("downloadsAction")
        self.integrity_button.setToolTip(
            "Read-only SHA-256 check of Hub-tracked installed files and a separate "
            "required-mod presence check where supported. "
            "Missing, manual, and untracked mods are never automatically adopted. "
            "Nothing is installed, repaired, or replaced.")
        self.integrity_button.clicked.connect(self._start_integrity_check)
        integrity_line.addWidget(self.integrity_button)
        integrity_line.addStretch()
        outer.addLayout(integrity_line)
        self.integrity_status = QLabel("Installed file integrity: not checked.")
        self.integrity_status.setWordWrap(True)
        self.integrity_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.integrity_status)
        self.integrity_details = QPlainTextEdit()
        self.integrity_details.setObjectName("integrityReviewDetails")
        self.integrity_details.setReadOnly(True)
        self.integrity_details.setMinimumHeight(80)
        self.integrity_details.setMaximumHeight(150)
        self.integrity_details.hide()
        outer.addWidget(self.integrity_details)

        self.review_actions = QWidget(self)
        self.review_footer = QHBoxLayout(self.review_actions)
        self.review_footer.setContentsMargins(0, 0, 0, 0)
        footer = self.review_footer
        self.inspect = QPushButton("Inspect selected archive")
        self.inspect.setObjectName("downloadsAction")
        self.inspect.setToolTip(
            "Inspect a supported local archive.\n"
            "Read-only check; nothing is installed.")
        self.inspect.setEnabled(False)
        self.inspect.clicked.connect(self._inspect)
        footer.addWidget(self.inspect)
        self.install_review_button = QPushButton("Review installation")
        self.install_review_button.setObjectName("primaryAction")
        self.install_review_button.setToolTip(
            "Review selected archives and backup policy.\n"
            "The Hub checks every destination internally.\n"
            "Nothing changes without confirmation.")
        self.install_review_button.clicked.connect(self._request_install_review)
        self.manual_review_button = QPushButton("Choose archives manually…")
        self.manual_review_button.setObjectName("downloadsAction")
        self.manual_review_button.setToolTip(
            "Explicit fallback when archives need manual selection. "
            "Opens the existing safety review; never installs directly.")
        self.manual_review_button.clicked.connect(self._request_manual_review)
        self.manual_review_button.hide()
        footer.addWidget(self.manual_review_button)
        footer.addStretch()
        footer.addWidget(self.install_review_button)
        outer.addWidget(self.review_actions)

        transfer_actions = QHBoxLayout()
        transfer_actions.setSpacing(8)
        self.download_button = QPushButton("Download and verify")
        self.download_button.setObjectName("downloadsScan")
        self.download_button.setEnabled(False)
        self.download_button.setToolTip(
            "Requires a recipe-pinned SHA-256 hash.\n"
            "Paste an official direct release-asset URL.\n"
            "Always asks for confirmation first.")
        transfer_actions.addWidget(self.download_button)
        self.download_cancel = QPushButton("Cancel download")
        self.download_cancel.setObjectName("downloadsAction")
        self.download_cancel.setEnabled(False)
        self.download_cancel.hide()
        self.download_cancel.setToolTip(
            "Cancel the active transfer.\n"
            "Any unfinished temporary file is removed.")
        transfer_actions.addWidget(self.download_cancel)
        transfer_actions.addStretch()
        outer.addLayout(transfer_actions)

        self.download_progress = QProgressBar()
        self.download_progress.setObjectName("verifiedDownloadsProgress")
        self.download_progress.setRange(0, 100)
        self.download_progress.hide()
        outer.addWidget(self.download_progress)
        self.download_status = QLabel(
            "Select a component to see whether verified direct download is available.")
        self.download_status.setObjectName("verifiedDownloadsStatus")
        self.download_status.setWordWrap(True)
        self.download_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.download_status)
        self.download_status.hide()

        self.download_button.clicked.connect(self._request_download)
        self.download_cancel.clicked.connect(self.cancel_download)
        self.table.itemSelectionChanged.connect(self._update_download_button)

        self.guidance = QLabel(
            "Only approved installer workflows should modify game files. "
            "The existing Setup guide remains the source for installation order.")
        self.guidance.setObjectName("downloadsExplanation")
        self.guidance.setWordWrap(True)
        outer.insertWidget(outer.indexOf(self.review_actions), self.guidance)
        # Dev5D3-Y: move the ORIGINAL guarded primary action above the long
        # dependency table. Do not add a duplicate button or a second route.
        # The scan controls, backup warnings and next-step guidance now sit
        # together before the scrollable technical checklist.
        outer.removeWidget(self.review_actions)
        outer.insertWidget(outer.indexOf(self.table), self.review_actions)
        outer.removeWidget(self.guidance)
        outer.insertWidget(outer.indexOf(self.table), self.guidance)
        # Historical scan metadata is still visible, but should never push
        # the action off a small screen before the archive checklist.
        for scan_note in (self.scan_age, self.saved_scan_count):
            outer.removeWidget(scan_note)
            outer.insertWidget(outer.indexOf(self.table), scan_note)
        # Deep diagnostics follow installed-file troubleshooting rather than
        # splitting the scan -> review task with a second version table.
        outer.removeWidget(self.comparison_toggle)
        outer.removeWidget(self.comparison_panel)
        anchor = outer.indexOf(self.integrity_details) + 1
        outer.insertWidget(anchor, self.comparison_toggle)
        outer.insertWidget(anchor + 1, self.comparison_panel)
        self.table.itemSelectionChanged.connect(self._update_inspect_button)
        self.table.itemSelectionChanged.connect(self._update_review_action)
        self.set_recipe(None)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_integrity_worker)

    def _sync_folder_actions(self):
        """Reflect current scan/download safety state in the folder menu."""
        for button, action in self.folder_menu_actions.items():
            action.setEnabled(button.isEnabled())
            action.setText(button.text())
            action.setToolTip(button.toolTip())
        rid = (self.recipe or {}).get("id")
        record = self._saved.get(rid)
        prior = archive_scans.plan_folders(record["plan"]) if record else ()
        previous = prior[-1] if prior else None
        different = bool(record and tuple(prior) != self._last_roots and
                         archive_scans.matching_record(rid, self._last_roots) is None)
        self.saved_folder_action.setVisible(different)
        self.saved_folder_action.setEnabled(bool(
            different and previous and previous.is_dir() and self.set_game.isEnabled()))
        self.folder_menu_button.setEnabled(
            any(button.isEnabled() for button in self.folder_menu_actions))

    def _stop_integrity_worker(self):
        if self.integrity_worker and self.integrity_worker.isRunning():
            self.integrity_worker.cancel()
            self.integrity_worker.wait()
        if self.safety_worker and self.safety_worker.isRunning():
            self.safety_worker.cancel()
            self.safety_worker.wait()

    def closeEvent(self, event):
        self._stop_integrity_worker()
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            event.ignore()
            return
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        super().closeEvent(event)

    def _folder(self):
        return planner.folder_for(self.recipe) if self.recipe else (None, "")

    def _folders(self):
        return planner.scan_folders(self.recipe) if self.recipe else ()

    def set_recipe(self, recipe):
        if (recipe or {}).get("id") != (self.recipe or {}).get("id"):
            self._comparison_online = None
            if self.integrity_worker is not None:
                self.integrity_worker.cancel()
            if self.safety_worker is not None:
                self.safety_worker.cancel()
        self.recipe = recipe
        self._invalidate_safety_review()
        self.safety_button.setEnabled(bool(recipe))
        # A verification result is never reused across game switches,
        # saved-scan refreshes, or later update checks.
        self._integrity_result = None
        self.integrity_status.setText("Installed file integrity: not checked.")
        self.integrity_details.clear()
        self.integrity_details.hide()
        active_integrity = bool(self.integrity_worker and self.integrity_worker.isRunning())
        self.integrity_button.setText(
            "Cancel verification" if active_integrity else "Verify installed files")
        self.integrity_button.setEnabled(bool(recipe))
        # Read the stable shared store again on game switch/refresh. A second
        # preview may have saved a newer scan since this window was opened.
        try:
            self._saved = archive_scans.load_saved()
            self._saved_error = None
        except (ValueError, OSError) as exc:
            self._saved = {}
            self._saved_error = str(exc)
        upstream = next((planner.source_url(item.get("reference_page"))
                         for item in (recipe or {}).get("updates", [])
                         if item.get("upstream_reference") is True
                         and planner.source_url(item.get("reference_page"))), "")
        if upstream:
            self.upstream_link.setText(
                f'<a style="color:#23B7FF" href="{escape(upstream, quote=True)}">'
                'UEVR downloads (JoeyHodge)</a> — upstream reference; '
                'the matched Hogwarts bundle remains the recommended archive source.')
        else:
            release = (recipe or {}).get("archive_release_link", {})
            source = planner.source_url(release.get("url", ""))
            if source:
                self.upstream_link.setText(
                    f'<a style="color:#23B7FF" href="{escape(source, quote=True)}">'
                    f'{escape(release["label"])}</a>')
            else:
                self.upstream_link.clear()
        self.upstream_link.setVisible(bool(self.upstream_link.text()))
        if self._saved_error:
            self.saved_scan_count.setText(
                "Saved scan history needs review; original data was preserved.")
        else:
            self.saved_scan_count.setText(
                f"Saved archive scans: {len(self._saved)} game profiles")
        self.saved_scan_count.setToolTip(
            "Historical results retained across Hub updates. A saved scan is not fresh verification.")
        rid = recipe.get("id") if recipe else None
        self._show_backup_safety(recipe)
        error = None
        try:
            folder, source = self._folder()
        except (ValueError, RuntimeError, OSError) as exc:
            folder, source, error = None, "", str(exc)
        if rid != self._last_id:
            # Never carry an action result from another game into this one.
            self.folder_action_feedback.clear()
            self.folder_action_feedback.hide()
        roots = ()
        if rid and folder and not error:
            try:
                roots = self._folders()
            except (ValueError, RuntimeError, OSError) as exc:
                error = str(exc)
        if rid != self._last_id or folder != self._last_folder or roots != self._last_roots:
            self._last_id = rid
            self._last_folder = folder
            self._last_roots = roots
        saved = self._saved.get(rid) if rid and folder else None
        selected = archive_scans.matching_record(rid, roots) if rid and roots and not self._saved_error else None
        # A historical snapshot from a previous recipe version must never
        # display a green check for a changed pin or dependency assignment.
        # Leave the persisted record untouched; only suppress its display.
        outdated_recipe = False
        if selected:
            keys = ("id", "sha256", "phase", "hint", "name", "url")
            expected = [tuple(c.get(k) for k in keys)
                        for c in planner.plan_components(recipe)]
            recorded = [tuple(c.get(k) for k in keys)
                        for c in selected["plan"]["rows"]]
            outdated_recipe = expected != recorded
        if selected and not outdated_recipe:
            # Re-evaluate identities; a different root combination needs its
            # own scan before it can be used in any installation review.
            self._last_plan = archive_scans.displayed_record(selected)["plan"]
            self._set_scan_age(selected)
        else:
            self._last_plan = None
            self.scan_age.setText(
                self._saved_error or (
                    "Saved scan uses older dependency requirements. "
                    "Rescan required; historical record retained."
                    if outdated_recipe else
                    "Previous scan retained for a different folder combination. "
                    "Scan the active locations, or choose the previous folder from the menu."
                    if saved else "No scan saved for this game yet. "
                    "Scan local archives to create a per-game snapshot."))
        active_download = bool(self.download_worker and
                               self.download_worker.isRunning())
        active_scan = bool(self.worker and self.worker.isRunning())
        for btn in (self.set_global, self.set_game, self.clear_game,
                    self.reset_global, self.scan):
            btn.setEnabled(bool(recipe) and not (active_scan or active_download))
        self.folder_menu_button.setEnabled(
            bool(recipe) and not (active_scan or active_download))
        self.install_review_button.setEnabled(bool(recipe) and not (active_scan or active_download))
        self._update_download_button()
        if recipe and folder:
            try:
                planner.load_preferences()  # Keep preference errors visible.
                additional = (f"Additional folder ({source}): {folder}"
                              if len(roots) == 2 else "Additional folder: None")
                self.location.setText(
                    f"Always scanned: {planner.default_library()}\n"
                    f"{additional}")
            except (ValueError, RuntimeError, OSError) as exc:
                self.location.setText(f"{source}: {folder}\n"
                                      f"Shared folder preference error: {exc}")
        elif recipe:
            self.location.setText(f"Download preferences unavailable: {error}")
        else:
            self.location.setText("Select a game to review its archive library.")
        self.location.setToolTip(str(folder or error or ""))
        if self._last_plan is None:
            self._display_unsanned(recipe, error)
        else:
            self._show_plan(self._last_plan)

    def _show_backup_safety(self, recipe):
        if not recipe or recipe.get("method") != "gameroot":
            self.backup_safety_status.hide()
            return
        try:
            state = hub.state().get(recipe["id"])
        except (ValueError, OSError) as exc:
            self.backup_safety_status.setText(
                f"Cannot read game-root backup status: {exc}. "
                "Guided installation must be reviewed manually.")
        else:
            if not state:
                self.backup_safety_status.setText(
                    "New game-root installs retain original files for checksum-"
                    "protected restoration. Review installation before applying.")
            elif state.get("installer") == "gameroot-2":
                originals = state.get("originals", {})
                count = sum(v is not None for v in originals.values())
                self.backup_safety_status.setText(
                    f"Persistent Cyberpunk backups recorded for {count} original "
                    "file(s). Restore requires all original and installed "
                    "hashes to match. No automatic updates are performed.")
            else:
                self.backup_safety_status.setText(
                    "LEGACY CYBERPUNK INSTALLATION: No verified retained "
                    "original-file backups. Replacement and automatic "
                    "uninstall remain BLOCKED. Preserve the working setup.")
        self.backup_safety_status.show()

    def _folder_feedback(self, message):
        self.folder_action_feedback.setText(message)
        self.folder_action_feedback.setVisible(bool(message))

    def _set_scan_age(self, record):
        scanned = datetime.fromisoformat(record["scanned_at"]).astimezone()
        self.scan_age.setText(
            f"Saved scan: {scanned:%Y-%m-%d %H:%M} (local time) · "
            "Historical snapshot; rescan after archive changes.")

    def _invalidate_changed_locations(self):
        # Folder changes are not deletion requests. Keep the last scan for
        # each game; set_recipe refuses to use it for a different folder.
        try:
            self._saved = archive_scans.load_saved()
            self._saved_error = None
        except (ValueError, OSError) as exc:
            self._saved_error = str(exc)

    def _use_saved_folder(self):
        if not self.recipe or not self.set_game.isEnabled():
            return
        try:
            record = archive_scans.load_saved().get(self.recipe["id"])
            if not record:
                raise ValueError("No saved scan for this game.")
            previous = archive_scans.plan_folders(record["plan"])[-1]
            planner.set_location("game", str(previous), self.recipe["id"])
            self.set_recipe(self.recipe)
            self._folder_feedback(
                "Previous archive folder selected for this game. Downloads is always included. "
                "Rescan if the original scan roots differ.")
        except (RuntimeError, ValueError, OSError) as exc:
            self._folder_feedback(f"Folder was NOT saved: {exc}")

    def _display_unsanned(self, recipe, error):
        self.summary.setToolTip("")
        self._set_rows([
            {**c, "phase_label": ("Later: install after first flat launch"
                                   if c["phase"] > 1 else "Stage 1: prerequisites"),
             "status": "Not checked", "file": ""}
            for c in planner.plan_components(recipe)] if recipe else [])
        self.summary.setText(
            f"Cannot read preferences: {error}" if error else
            "Scan local archives to find candidate packages. Nothing is installed."
            if recipe else "Select a game to review its archive library.")
        self._refresh_comparison()

    def _choose_folder(self, scope):
        if not self.recipe:
            return
        try:
            existing, _ = self._folder()
        except (RuntimeError, ValueError, OSError) as exc:
            self._folder_feedback(f"Folder preference needs review: {exc}")
            return
        rid = self.recipe["id"]
        selected = QFileDialog.getExistingDirectory(
            self, "Choose existing mod archive folder",
            str(existing if existing and existing.is_dir() else Path.home() / "Downloads"))
        if not selected or not self.recipe or self.recipe["id"] != rid:
            return
        try:
            planner.set_location(scope, selected, rid if scope == "game" else None)
            self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
            if scope == "global" and planner.load_preferences()["games"].get(
                    self.recipe["id"]):
                self._folder_feedback(
                    "Shared extra folder changed; this game still has its own "
                    "additional folder alongside Downloads.")
            else:
                self._folder_feedback(
                    ("Folder saved for this game only. " if scope == "game" else
                     "Shared extra folder saved. ") +
                    "Older folder combinations remain saved; rescan both current folders when needed.")
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Folder was NOT saved: {exc}")

    def _clear_game(self):
        if not self.recipe:
            return
        try:
            planner.set_location("game", None, self.recipe["id"])
            self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
            self._folder_feedback(
                "This game now uses Downloads plus the optional shared extra folder. Saved results are "
                "kept when its effective folder is unchanged.")
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Folder preference was NOT changed: {exc}")

    def _reset_global(self):
        if not self.recipe:
            return
        try:
            prefs = planner.load_preferences()
            had_shared_override = bool(prefs["global"])
            has_game_override = bool(prefs["games"].get(self.recipe["id"]))
            # Avoid a needless preference-file write when the shared default
            # is already Downloads.
            if had_shared_override:
                planner.set_location("global", None)
                self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
            if has_game_override:
                self._folder_feedback(
                    "Shared extra folder removed. This game still uses "
                    "its custom folder. Select 'Use shared extra for this game' to switch.")
            elif had_shared_override:
                self._folder_feedback(
                    "Shared extra folder removed. "
                    "Rescan if the scan locations changed.")
            else:
                self._folder_feedback(
                    "No shared extra folder configured. No setting "
                    "or saved scan was changed.")
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Default folder preference was NOT changed: {exc}")

    def start_scan(self):
        if (not self.recipe or (self.worker and self.worker.isRunning())
                or (self.download_worker and self.download_worker.isRunning())):
            return
        try:
            folders = self._folders()
        except (ValueError, RuntimeError, OSError) as exc:
            self.summary.setText(f"Cannot scan folders: {exc}")
            return
        self._folder_feedback("")
        self.summary.setToolTip("")
        self.progress.show()
        self.summary.setText("Scanning local archives and checking any pinned release hashes…")
        for btn in (self.set_global, self.set_game, self.clear_game,
                    self.reset_global, self.scan, self.install_review_button):
            btn.setEnabled(False)
        self.folder_menu_button.setEnabled(False)
        worker = LocalInventoryWorker(dict(self.recipe), folders, self)
        self.worker = worker
        worker.done.connect(lambda result, token=worker: self._completed(result, token))
        worker.failed.connect(lambda message, token=worker: self._failed(message, token))
        worker.finished.connect(lambda token=worker: self._finished(token))
        worker.start()
        self._update_review_action()
        self._update_download_button()

    def _completed(self, result, worker):
        if self.worker is not worker:
            return
        # Worker results belong to the game that launched the scan, not
        # whatever game happens to be selected when it finishes.
        if (result.get("game_id") != worker.recipe.get("id") or
                tuple(result.get("folders", [result["folder"]])) !=
                tuple(str(p) for p in worker.folders)):
            return
        try:
            if planner.scan_folders(worker.recipe) != worker.folders:
                return  # selected folders changed since scan started
            rec = archive_scans.persist(result)
        except (OSError, ValueError, RuntimeError) as exc:
            if self.recipe and self.recipe["id"] == result["game_id"]:
                self._last_plan = result
                self._show_plan(result)
                self.scan_age.setText(
                    f"Scan completed but could not be saved: {exc}")
                self._folder_feedback(f"Scan completed but could not be saved: {exc}")
            return
        self._saved[worker.recipe["id"]] = rec
        self._saved_error = None
        if (self.recipe and self.recipe["id"] == result["game_id"] and
                self._last_roots == worker.folders):
            self._last_plan = archive_scans.displayed_record(rec)["plan"]
            self._set_scan_age(rec)
            self._show_plan(self._last_plan)

    def _failed(self, message, worker):
        if self.worker is worker:
            self.summary.setText(f"Could not scan archive folder: {message}")
            self._folder_feedback(f"Could not scan archive folder: {message}")

    def _finished(self, worker):
        if self.worker is not worker:
            return
        self.progress.hide()
        self.worker = None
        self.set_recipe(self.recipe)
        worker.deleteLater()
        self.scan_idle.emit()

    def _show_plan(self, plan):
        self._invalidate_safety_review()
        self._set_rows(plan["rows"])
        changed = plan.get("changed", 0)
        official = sum(
            row.get("status") == "Possible archive — inspect first"
            and not row.get("candidate_incomplete")
            and bool((row.get("candidates") or [{}])[0].get("tags"))
            for row in plan["rows"])
        counts = (
            (plan["verified"], "pinned hashes verified"),
            (official, "official release matches — review required"),
            (plan["possible"] - official, "possible matches needing review"),
            (plan["mismatch"], "mismatched (BLOCKED)"),
            (plan["unverified"], "unchecked (BLOCKED)"),
            (plan["missing"], "missing"),
            (changed, "changed — rescan required"),
        )
        heading = (f'{len(plan["rows"])} dependencies · {plan["scanned"]} archives · '
                   f'{len(plan.get("folders", [plan["folder"]]))} scanned location(s)')
        details = [f"{count} {label}" for count, label in counts]
        current = [f"{count} {label}" for count, label in counts if count]
        if plan.get("warning"):
            current.append(str(plan["warning"]))
            details.append(str(plan["warning"]))
        self.summary.setText(" · ".join([heading, *current]))
        self.summary.setToolTip(" · ".join([heading, *details]))
        self._update_workflow_guidance()
        self._refresh_comparison()

    def _toggle_comparison(self, open_):
        self.comparison_panel.setVisible(bool(open_))
        self.comparison_toggle.setText(
            "Hide advanced diagnostics ▴" if open_ else "Advanced diagnostics ▸")
        if open_:
            self._comparison_scroll_timer.start(0)
        else:
            self._comparison_scroll_timer.stop()

    def _scroll_to_comparison(self):
        """Bring expanded evidence into view without touching its content."""
        widget = self.parentWidget()
        while widget is not None and not isinstance(widget, QScrollArea):
            widget = widget.parentWidget()
        if widget is not None and self.comparison_panel.isVisible():
            widget.ensureWidgetVisible(self.safety_button, 0, 24)

    def set_online_results(self, results):
        """Update from the separate Updates tab refresh; never fetch here."""
        self._invalidate_safety_review()
        self._comparison_online = results if isinstance(results, list) else None
        self._refresh_comparison()

    def _refresh_comparison(self):
        recipe = self.recipe
        if not recipe or (planner.plan_components(recipe) == [] or
                          all(c["id"] == "guide" for c in planner.plan_components(recipe))):
            self.comparison_toggle.hide()
            self.comparison_toggle.setChecked(False)
            self.comparison_table.setRowCount(0)
            self.readiness_summary.setText("Update readiness: select a supported dependency.")
            return
        self.comparison_toggle.show()
        try:
            state = hub.state()
            if not isinstance(state, dict):
                raise ValueError("Hub installation state is not a mapping.")
        except (OSError, ValueError, TypeError) as exc:
            self.comparison_summary.setText(f"Cannot compare installed records: {exc}")
            self.comparison_table.setRowCount(0)
            self.readiness_summary.setText("Update readiness unavailable: installed records need review.")
            return
        records = archive_update_comparison.compare(
            recipe, self._last_plan, state, self._comparison_online)
        decisions = update_readiness.assess(
            recipe, self._last_plan, state, self._comparison_online,
            self._integrity_result, records)
        by_decision = {entry["id"]: entry for entry in decisions}
        self.comparison_table.setRowCount(0)
        self.comparison_table.setRowCount(len(records))
        for i, record in enumerate(records):
            self.comparison_table.setRowHeight(i, 58)
            decision = by_decision.get(record["id"], {})
            for j, key in enumerate(("name", "installed", "downloaded", "latest", "assessment")):
                value = decision.get("label", "Manual evidence review") if j == 4 else record[key]
                cell = QTableWidgetItem(value)
                cell.setFlags(Qt.ItemIsEnabled)
                if j == 4:
                    cell.setToolTip(
                        record["detail"] + chr(10) +
                        "Previous comparison: " + record["assessment"] + chr(10) +
                        "Update readiness: " + decision.get("detail", "Not established.") + chr(10) +
                        "Next safe step: " + decision.get("next", "Manual review.") + chr(10) +
                        "No replacement, download, or installation is authorized.")
                else:
                    cell.setToolTip(record["detail"])
                tone = decision.get("tone", "unknown") if j == 4 else record["tone"]
                if j == 4 or (j == 2 and record["tone"] != "success"):
                    cell.setForeground(QColor({
                        "danger": "#FF5B50", "warning": "#FFD21A",
                        "success": "#4FE39A", "unknown": "#A7ADB7",
                    }.get(tone, "#A7ADB7")))
                self.comparison_table.setItem(i, j, cell)
        candidates = sum(x["code"] == "candidate" for x in decisions)
        blocked = sum(x["code"] in ("blocked", "pin", "integrity-review") for x in decisions)
        further = len(decisions) - candidates - blocked
        self.readiness_summary.setText(
            f"Update readiness (planning only): {candidates} future candidate(s) · "
            f"{blocked} blocked / integrity review · {further} need more evidence. "
            "No update is authorized.")
        self.readiness_summary.setToolTip(
            "Uses your last on-demand installed-file check, selected-folder scan and "
            "separately refreshed online metadata. Hover the readiness cell for the next safe step. "
            "Backup, dependency compatibility and recovery preflight are NOT performed here.")
        identified = sum(row["matched_release"] for row in records)
        checked = sum(row["latest"] not in ("Not checked", "Unavailable") for row in records)
        self.comparison_summary.setText(
            f"{identified} identified archive(s) · "
            f"{sum(row['installed_attributed'] for row in records)} Hub-recorded release identity(ies) · "
            f"{checked} online version(s) from last refresh")
        self.comparison_summary.setToolTip(
            "Comparison uses saved or newly scanned archive metadata and in-memory "
            "online results only. Refresh online results separately in Updates.")

    def _invalidate_safety_review(self):
        if self.safety_worker is not None and self.safety_worker.isRunning():
            self.safety_worker.cancel()
        self._safety_result = None
        self.safety_summary.setText("Replacement safety: not reviewed.")
        self.safety_details.clear()
        self.safety_details.hide()
        self.comparison_panel.setMinimumHeight(0)

    def _scroll_to_safety(self):
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if parent is not None and self.safety_details.isVisible():
            parent.ensureWidgetVisible(self.safety_details, 0, 20)

    def _start_safety_review(self):
        worker = self.safety_worker
        if worker is not None:
            if worker.isRunning():
                worker.cancel()
                self.safety_summary.setText("Canceling read-only replacement review…")
            return
        recipe = self.recipe
        if not recipe:
            return
        self._invalidate_safety_review()
        try:
            state = hub.state()
            if not isinstance(state, dict):
                raise ValueError("Invalid state snapshot.")
            records = archive_update_comparison.compare(
                recipe, self._last_plan, state, self._comparison_online)
            decisions = update_readiness.assess(
                recipe, self._last_plan, state, self._comparison_online,
                self._integrity_result, records)
        except (OSError, ValueError, RuntimeError, TypeError):
            self.safety_summary.setText("Replacement safety unavailable: saved evidence needs review.")
            return
        self.safety_summary.setText(
            "Checking retained backup hashes and candidate ZIP metadata (read-only)…")
        worker = PreUpdateSafetyWorker(
            recipe, self._last_plan, state, decisions, self._integrity_result, self)
        self.safety_worker = worker
        self.safety_button.setText("Cancel replacement review")
        worker.done.connect(lambda result, token=worker:
                            self._safety_done(result, token))
        worker.failed.connect(lambda error, token=worker:
                              self._safety_failed(error, token))
        worker.cancelled.connect(lambda token=worker:
                                 self._safety_cancelled(token))
        worker.finished.connect(lambda token=worker:
                                self._safety_finished(token))
        worker.start()

    def _safety_done(self, result, worker):
        if (worker is not self.safety_worker or worker.cancel_flag.is_set()
                or not self.recipe or result.get("game_id") != self.recipe.get("id")):
            return
        self._safety_result = result
        backup = result["existing_backup"]
        known = sum(row["current_managed"] for row in result["rows"])
        mapped = sum(row["future_destinations"] is not None for row in result["rows"])
        self.safety_summary.setText(
            f"Replacement blocked · {known} currently tracked file(s) · "
            f"{mapped}/{len(result['rows'])} future target map(s) identified · "
            f"retained-original backup: {backup['status']}. No changes made.")
        lines = [
            "PLANNING ONLY — NO UPDATE OR REPLACEMENT AUTHORIZED",
            "Retained originals: " + backup["reason"],
            "New backup needed: " + result["new_backup"],
            "Compatibility: " + result["compatibility"],
            "Recovery: " + result["recovery"],
        ]
        audit = result.get("real_audit")
        if (isinstance(audit, dict) and audit.get("game_id") == result["game_id"]
                and audit.get("authorized") is False
                and audit.get("real_installer_connected") is False):
            location_names = {
                "directory": "Located directory (identity not a file check)",
                "missing": "Missing", "symlink": "Symlink — not trusted",
                "not_directory": "Not a directory", "unresolved": "Not located",
                "unavailable": "Cannot safely inspect",
                "not_applicable": "Not applicable",
            }
            integrity_names = {
                "verified_at_prior_check": "SHA matched at PRIOR on-demand check",
                "needs_review_at_prior_check": "PRIOR SHA check needs review",
                "unknown_at_prior_check": "PRIOR SHA check unknown",
                "not_checked": "SHA not checked in this review",
            }
            lines.extend((
                "",
                "REAL INSTALLATION READINESS AUDIT — READ ONLY / LIVE UPDATE DISABLED",
                audit["summary"],
                "Game location: " + location_names.get(audit["game_location"], "Unknown"),
                "Profile location: " + location_names.get(audit["profile_location"], "Unknown"),
                "Retained originals: " + audit["retained_originals"].replace("_", " "),
                "File hashes are NOT recalculated by this audit. Previous checks may be stale.",
            ))
            for item in audit["rows"]:
                lines.append(
                    f"  {item['name']}: {item['verdict'].replace('_', ' ')} · "
                    f"Hub ownership: {'recorded' if item['root_bound_ownership'] else 'unverified'} · "
                    f"{integrity_names.get(item['integrity'], 'Unknown')}")
                lines.append("    Next: " + item["next_step"])
            lines.append(
                "  All live gates unresolved: fresh verified backup · game lock · "
                "real compatibility · tested real recovery · separate approval · executor disabled")
        triage = result.get("triage")
        if (isinstance(triage, dict) and triage.get("game_id") == result["game_id"]
                and triage.get("live_update_authorized") is False
                and triage.get("legacy_state_migrated") is False
                and triage.get("manual_files_adopted") is False):
            lines.extend((
                "",
                "OWNERSHIP RECONCILIATION & MODIFIED-FILE TRIAGE — READ ONLY",
                triage["summary"],
                "Differences are NOT proof of damage or of a newer mod version.",
                "No installed files read again, ownership adopted, SHA records rewritten or repair performed.",
            ))
            labels = {
                "possible_customization": "Possible configuration customization (cause unverified)",
                "binary_drift": "Binary difference (cause unknown)",
                "other_modified": "Recorded file changed (cause unknown)",
                "missing": "Missing recorded file",
                "unsafe": "Unsafe path or file type",
                "unknown": "Unable to verify safely",
            }
            for item in triage["rows"]:
                lines.append(
                    f"  {item['name']}: {item['classification'].replace('_', ' ')} · "
                    f"prior SHA: {item['status']} · "
                    f"Hub ownership: {'recorded' if item['owned_by_hub'] else 'unverified'}")
                for issue in item["reported_issues"]:
                    lines.append(
                        f"    {labels.get(issue['category'], 'Unresolved issue')}: "
                        + issue["relative_file"])
                    lines.append("      Next: " + issue["next_step"])
                if item["unreported_issues"]:
                    lines.append(
                        f"    {item['unreported_issues']} additional unmatched file(s) "
                        "not listed; bounded verifier output is NOT a full inventory.")
                lines.append("    Next: " + item["next_step"])
        preservation = result.get("preservation")
        if (isinstance(preservation, dict) and
                preservation.get("game_id") == result["game_id"] and
                preservation.get("session_only") is True and
                preservation.get("live_update_authorized") is False and
                preservation.get("choices_saved") is False and
                preservation.get("recorded_file_hashes_rewritten") is False):
            lines.extend((
                "",
                "MODIFIED-FILE PRESERVATION DECISION WORKSHEET — READ ONLY",
                preservation["summary"],
                "Recommendations are NOT user decisions and do NOT enforce file preservation.",
                "Review paths: preserve existing · investigate unknown · consider future replacement.",
                "No choice saved. No backup created, owner adopted, hash updated, repair or update authorized.",
            ))
            if not preservation["rows"]:
                lines.append(
                    "  No listed differences to plan. This is NOT proof of valid "
                    "ownership or a clean installation.")
            for item in preservation["rows"]:
                labels = {
                    "preserve_existing": "Recommend preserving current file pending review",
                    "investigate_unknown": "Investigate difference before deciding",
                    "consider_future_replacement": "Potential future replacement review ONLY",
                }
                lines.append(
                    f"  {item['component_name']}: {item['relative_file']} · "
                    f"{labels[item['draft_decision']]}")
                lines.append("    Next: " + item["next_step"])
            if preservation["unreported_differences"]:
                lines.append(
                    f"  {preservation['unreported_differences']} unlisted difference(s) "
                    "must be independently reviewed before any plan.")
            lines.append(
                "  LIVE UPDATE DISABLED: fresh complete backup · game lock · "
                "real compatibility · recovery · separate approval · no executor.")
        manifest = result.get("manifest_preview")
        if (isinstance(manifest, dict) and manifest.get("game_id") == result["game_id"]
                and manifest.get("evidence_level") == "real_readonly_samples"
                and manifest.get("candidate_mapping_complete") is False
                and manifest.get("live_update_authorized") is False
                and manifest.get("executable_plan") is None):
            lines.extend((
                "",
                "PRESERVATION-AWARE UPDATE MANIFEST PREVIEW — READ ONLY",
                "BEFORE: recorded ownership counts only, NOT a verified current whole-tree snapshot.",
                "AFTER: prospective destination SAMPLES only, NOT a complete target manifest.",
                "A sample match is NOT proof of no overlap; real compatibility and live updating remain blocked.",
            ))
            kinds = {
                "known_conflict": "Known ownership/destination conflict",
                "preservation_review": "Modified-file preservation review required",
                "mapping_incomplete": "Full future target mapping unavailable",
                "sample_only": "Mapped destination sample only — NOT a safe-to-update result",
                "manual_or_guide": "Manual setup; no automated manifest",
            }
            for item in manifest["rows"]:
                old = item["current_managed_count"]
                new = item["candidate_count"]
                lines.append(
                    f"  {item['name']}: {kinds.get(item['status'], 'Unverified')} · "
                    f"before recorded: {old if old is not None else 'unknown'} · "
                    f"candidate targets: {new if new is not None else 'unknown'}")
                if item["preservation_review_count"]:
                    lines.append(
                        f"    {item['preservation_review_count']} changed-file "
                        "preservation decision(s) need overlap review.")
                if item["known_conflicts"]:
                    lines.append(
                        f"    {len(item['known_conflicts'])} conflict hint(s); "
                        "manual inspection required.")
                if item["sample_paths"]:
                    lines.append(
                        "    Sampled future paths (partial): " +
                        ", ".join(item["sample_paths"][:3]))
                lines.append("    Next: " + item["next_step"])
            lines.append(
                "  LIVE UPDATE DISABLED: no full real before/after data, "
                "no fresh backup, no real recovery approval, no executor.")
        coverage = result.get("coverage")
        if (isinstance(coverage, dict)
                and coverage.get("game_id") == result["game_id"]
                and coverage.get("live_update_authorized") is False
                and coverage.get("executable_plan") is None):
            lines.extend((
                "",
                "COMPLETE DESTINATION MAPPING & PRESERVATION COVERAGE — READ ONLY",
                f"{coverage['complete_recipe_target_lists']} of "
                f"{coverage['total_dependencies']} recipe target lists mapped at review.",
                "FULL list means mapped INSTALL TARGETS; strict Cyberpunk ZIP maps "
                "also account for every regular member. Neither verifies release "
                "authenticity, current ownership, compatibility, or safe updating.",
                "No complete real before/after, automatic preservation, backup or "
                "release compatibility certification exists.",
            ))
            names = {
                "target_list_mapped": "Install-target map captured; update still blocked",
                "mapping_missing": "No supported complete target map yet",
                "preservation_review": "Modified-file preservation review required",
                "conflict_review": "Ownership or destination conflicts require review",
                "manual": "Manual workflow only",
            }
            for entry in coverage["rows"]:
                count = entry["full_target_count"]
                lines.append(
                    f"  {entry['name']}: {names.get(entry['status'], 'Review')} · "
                    f"mapped: {count if count is not None else 'unknown'} · "
                    f"source: {entry['mapped_by'] or 'not established'}")
                if entry.get("mapped_by") == "cyberpunk_gameroot":
                    lines.append(
                        "    Strict ZIP member accounting at review only; "
                        "Nexus release authenticity and game-build compatibility UNVERIFIED.")
                if entry.get("preservation_overlaps") or entry.get("unmapped_preservation_issues"):
                    lines.append(
                        f"    Modified-file review: {entry['preservation_overlaps']} "
                        f"candidate overlaps; {entry['unmapped_preservation_issues']} "
                        "changed file(s) outside listed targets.")
                conflicts = (entry.get("cross_component_overlaps", 0) +
                             entry.get("untracked_hints", 0) +
                             entry.get("ownership_hints", 0))
                if conflicts:
                    lines.append(
                        f"    At least {conflicts} overlap/conflict hint(s); "
                        "lack of other hints is NOT clearance.")
                lines.append("    Next: " + entry["next_step"])
            lines.append(
                "  LIVE UPDATE DISABLED: installation and deletion require "
                "fresh backups, current integrity, compatibility, recovery and consent.")
        if result["game_id"] == "cyberpunk-2077":
            payloads = [
                row for row in result["rows"]
                if isinstance(row.get("payload_evidence"), dict)
                and row["payload_evidence"].get("game_id") == result["game_id"]
                and row["payload_evidence"].get("live_update_authorized") is False
            ]
            lines.extend((
                "",
                "ARCHIVE PAYLOAD CLASSIFICATION & COMPATIBILITY EVIDENCE — READ ONLY",
                f"{len(payloads)} local Cyberpunk ZIP payload review(s) classified.",
                "Filename/ZIP-metadata labels only: documentation-looking entries "
                "are NOT approved exclusions, and optional entries are NOT selected.",
                "Nexus release authenticity, newest version, actual game build, "
                "runtime compatibility, payload CRC, and current ownership remain UNVERIFIED.",
            ))
            for entry in payloads:
                evidence = entry["payload_evidence"]
                categories = evidence["counts"]
                lines.append(
                    f"  {entry['name']}: {categories['installable']} installable · "
                    f"{categories['documentation']} documentation · "
                    f"{categories['optional']} optional · "
                    f"{categories['unknown']} unknown · "
                    f"{categories['unsafe']} unsafe signal(s)")
                if evidence["regular_members"] is None:
                    lines.append(
                        "    Unsafe/invalid ZIP metadata: the member inventory "
                        "and exact unsafe count could not be trusted.")
                for category in ("documentation", "optional", "unknown"):
                    if evidence["samples"][category]:
                        lines.append(
                            f"    {category.title()} example(s): "
                            + ", ".join(evidence["samples"][category][:3]))
                lines.append("    Next: " + evidence["reason"])
                lines.append(
                    "    Component required-file rule: " +
                    ("present (not compatibility proof)" if
                     evidence["required_payload_contract_exists"] and
                     evidence["required_payload_contract_satisfied"] else
                     "required payload missing or not established" if
                     evidence["required_payload_contract_exists"] else
                     "no recipe-specific required-file contract"))
            lines.append(
                "  STRICT MAPPING STILL REQUIRED · LIVE UPDATE DISABLED · "
                "NO FILES INSTALLED, EXCLUDED, OR MODIFIED")
        unified = result.get("unified")
        if (isinstance(unified, dict) and unified.get("game_id") == result["game_id"]
                and unified.get("authorized") is False
                and unified.get("live_executor_connected") is False):
            lines.extend((
                "",
                "UNIFIED UPDATE PLAN — REVIEW ONLY / LIVE UPDATE DISABLED",
                unified["summary"],
                "Evidence reported below is not compatibility approval or update permission.",
            ))
            for item in unified["rows"]:
                lines.append(
                    f"  {item['name']}: {item['label']} · "
                    f"{item['observed_count']}/{item['observed_total']} review signals observed")
                lines.append("    Next: " + item["next_step"])
            lines.append(
                "  Hard live gates: fresh backup · runtime lock · real compatibility · "
                "rollback validation · explicit approval · no live executor")
        for row in result["rows"]:
            lines.extend((
                "",
                f"{row['name']}: {row['readiness']}",
                f"  Currently tracked: {row['current_managed']} file(s). "
                f"Integrity: {row['integrity']}.",
                f"  Proposed targets: "
                f"{row['future_destinations'] if row['future_destinations'] is not None else 'Unknown'}. "
                + row["mapping"],
                "  " + row["file_issue"],
            ))
            if row["current_sample"]:
                lines.append("  Existing examples: " + ", ".join(row["current_sample"]))
            if row["future_sample"]:
                lines.append("  Proposed examples: " + ", ".join(row["future_sample"]))
            if row["ownership_conflicts"]:
                lines.append("  Overlapping ownership: " + ", ".join(row["ownership_conflicts"]))
            if row["untracked_collisions"]:
                lines.append("  Untracked/unsafe targets: " + ", ".join(row["untracked_collisions"]))
            lines.extend("  " + text for text in row["order"])
        integration = result.get("integration")
        if isinstance(integration, dict) and integration.get("game_id") == result["game_id"]:
            lines.extend((
                "",
                "UPDATE ADAPTER CONTRACTS — PLANNING ONLY / NO LIVE EXECUTION",
                f"{integration['drafts']} draft adapter(s); "
                f"{integration['manual']} manual workflow(s). "
                "Every live update remains blocked.",
            ))
            for contract in integration["contracts"]:
                lines.append(
                    f"  {contract['name']}: {contract['adapter_label']} · "
                    f"{contract['contract_stage']}")
                lines.append(
                    f"    Existing ownership: "
                    f"{'recorded' if contract['recorded_ownership'] else 'not verified'} · "
                    f"installed integrity: "
                    f"{'observed' if contract['integrity_observed'] else 'not verified'} · "
                    f"future target map: "
                    f"{contract['mapped_destinations'] if contract['mapped_destinations'] is not None else 'Unknown'}")
                lines.append("    Next integration gaps: " + " | ".join(
                    contract["blockers"][:2]))
                lines.append("    Live adapter disabled; fresh backup, compatibility, "
                             "runtime lock and rollback validation required.")
        self.safety_details.setPlainText(chr(10).join(lines))
        self.safety_details.show()
        self.comparison_panel.setMinimumHeight(345)
        self.comparison_panel.updateGeometry()
        QTimer.singleShot(0, self._scroll_to_safety)

    def _safety_failed(self, error, worker):
        if worker is self.safety_worker and self.recipe and (
                self.recipe.get("id") == worker.recipe.get("id")):
            self._safety_result = None
            self.safety_summary.setText(
                "Replacement safety could not be checked. No installation authorized.")
            self.safety_details.setPlainText(error)
            self.safety_details.show()
            self.comparison_panel.setMinimumHeight(345)
            self.comparison_panel.updateGeometry()
            QTimer.singleShot(0, self._scroll_to_safety)

    def _safety_cancelled(self, worker):
        if worker is self.safety_worker and self.recipe and (
                self.recipe.get("id") == worker.recipe.get("id")):
            self._safety_result = None
            self.safety_summary.setText("Replacement safety review canceled; no changes made.")
            self.safety_details.hide()
            self.comparison_panel.setMinimumHeight(0)

    def _safety_finished(self, worker):
        if worker is not self.safety_worker:
            return
        self.safety_worker = None
        self.safety_button.setText("Review replacement safety (read-only)")
        self.safety_button.setEnabled(bool(self.recipe))
        worker.deleteLater()

    def _start_integrity_check(self):
        worker = self.integrity_worker
        if worker is not None:
            if worker.isRunning():
                worker.cancel()
                self.integrity_status.setText("Canceling read-only verification…")
            return
        if not self.recipe:
            return
        self.integrity_status.setText(
            "Reading recorded installation hashes (read-only). No game-file writes will occur…")
        # Any prior verification is now superseded by this in-progress job.
        self._integrity_result = None
        self._invalidate_safety_review()
        self._refresh_comparison()
        self.integrity_details.clear()
        self.integrity_details.hide()
        worker = InstalledIntegrityWorker(self.recipe, self)
        self.integrity_worker = worker
        self.integrity_button.setText("Cancel verification")
        worker.done.connect(lambda result, token=worker:
                            self._integrity_done(result, token))
        worker.failed.connect(lambda error, token=worker:
                              self._integrity_failed(error, token))
        worker.cancelled.connect(lambda token=worker:
                                 self._integrity_cancelled(token))
        worker.finished.connect(lambda token=worker:
                                self._integrity_finished(token))
        worker.start()

    def _integrity_done(self, result, worker):
        if (worker is not self.integrity_worker or
                not self.recipe or result.get("game_id") != self.recipe.get("id")
                or worker.cancel_flag.is_set()):
            return
        self._integrity_result = result
        verified = sum(row["status"] == "Verified" for row in result["rows"])
        review = sum(row["status"] == "Review" for row in result["rows"])
        unknown = sum(row["status"] == "Unknown" for row in result["rows"])
        message = (
            f"Installed integrity: {result['checked']} tracked file(s) matched · "
            f"{verified} verified dependency(ies) · {review} need review · "
            f"{unknown} unknown.")
        presence = result.get("presence")
        if isinstance(presence, dict):
            if presence.get("status") == "Unknown":
                message += " Required mod presence: unknown."
            else:
                message += (
                    f" Required mod presence: {presence.get('ok', 0)}/"
                    f"{presence.get('total', 0)} recorded present "
                    "(presence only; not hash verification).")
        self.integrity_status.setText(message + " No game-file writes performed.")
        lines = []
        for row in result["rows"]:
            if row["status"] == "Verified":
                continue
            lines.append(f"{row['name']}: {row['status']} — {row['reason']}")
            for item in row["issues"]:
                lines.append(f"  {item['status']}: {item['file']} — {item['detail']}")
                if (item.get("status") in ("Modified", "Missing", "Unsafe", "Unknown")
                        and installed_integrity._relative(item.get("file"))):
                    category = ownership_triage._category(
                        item["status"], item["file"])
                    lines.append("    Triage (not a diagnosis): " +
                                 ownership_triage._next_for(category))
            if len(row["issues"]) >= installed_integrity.MAX_ISSUES_PER_COMPONENT:
                lines.append("  Additional differences may exist; output is bounded.")
        if isinstance(presence, dict):
            for key in ("required_bad", "later_bad"):
                for row in presence.get(key, []):
                    lines.append(
                        f"Required mod presence ({'required' if key == 'required_bad' else 'optional'}): "
                        f"{row['name']} — {row['status']} (presence check, not SHA-256).")
            if presence.get("status") == "Unknown":
                lines.append("Required mod presence: unknown — no readiness evidence.")
        self.integrity_details.setPlainText(chr(10).join(lines))
        self.integrity_details.setVisible(bool(lines))
        self._invalidate_safety_review()
        self._refresh_comparison()

    def _integrity_failed(self, error, worker):
        if worker is self.integrity_worker and self.recipe and (
                self.recipe.get("id") == worker.recipe.get("id")):
            self.integrity_status.setText(
                "Verification could not finish safely. No game-file writes performed.")
            self.integrity_details.setPlainText("Read-only verification failed: " + error)
            self.integrity_details.show()
            self._integrity_result = None
            self._invalidate_safety_review()
            self._refresh_comparison()

    def _integrity_cancelled(self, worker):
        if worker is self.integrity_worker and self.recipe and (
                self.recipe.get("id") == worker.recipe.get("id")):
            self.integrity_status.setText("Verification cancelled. No game-file writes performed.")
            self.integrity_details.hide()
            self._integrity_result = None
            self._invalidate_safety_review()
            self._refresh_comparison()

    def _integrity_finished(self, worker):
        if worker is not self.integrity_worker:
            return
        self.integrity_worker = None
        self.integrity_button.setText("Verify installed files")
        self.integrity_button.setEnabled(bool(self.recipe))
        worker.deleteLater()

    def _set_rows(self, records):
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.setRowCount(0)  # prevent stale QTableWidget link widgets
        self.table.setRowCount(len(records))
        for i, record in enumerate(records):
            self.table.setRowHeight(i, 52)
            # These explicit download links/labels are presentation only.
            # Keep the saved scan's dependency identity, status and evidence.
            display = (self.recipe or {}).get("archive_display", {}).get(record.get("id"), {})
            status = record["status"]
            selected = (record.get("candidates") or [{}])[0]
            label = status
            if self._official_pin_review(record):
                label = f"{record['release_expected']} — Release matched; pin not approved"
            elif status == "Possible archive — inspect first":
                if record.get("candidate_incomplete"):
                    label = "Rescan required — incomplete candidates"
                elif self._needs_rescan(record):
                    label = "Rescan required — older candidate evidence"
                elif record.get("ambiguous") and (record.get("id") != "kharvox" or
                        sum(bool(c.get("tags")) for c in record.get("candidates", [])) > 1):
                    label = "Choose archive"
                elif record.get("id") == "kharvox" and not selected.get("tags"):
                    label = "Official SHA-256 not matched"
                elif selected.get("tags"):
                    version = record.get("release_expected") if selected.get("expected") else selected["tags"][0]
                    label = f"{version} — " + ("Bundle matched" if selected.get("expected") and record.get("release_fixed")
                        else "Latest release matched" if selected.get("expected") else
                        "Older release matched" if record.get("id") == "kharvox" and record.get("release_expected")
                        else "Release matched")
                elif selected.get("copies", 0) > 1:
                    label = "Identical copies — review"
            values = (
                str(display.get("name", record["name"])),
                str(record["phase_label"]),
                Path(record["file"]).name if record.get("file") else "—",
                label,
            )
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(
                    str(record["file"]) if col == 2 and record.get("file") else value)
                if col == 2 and record.get("file"):
                    size = record.get("size", 0)
                    count = record.get("matches", 1)
                    cell.setToolTip(
                        str(record["file"]) +
                        (f"\nSize: {human_file_size(size)}" if size else "") +
                        (f"\n{count} matching files; shown archive is the suggested candidate."
                         if count > 1 else ""))
                if col == 3:
                    cell.setForeground(QColor(COLOR.get(status, "#A7ADB7")))
                    cell.setIcon(status_icon(status))
                    evidence = (
                        "\nA scan is not permission to install."
                        if status == "Pinned SHA-256 verified" else
                        "\nOfficial SHA-256 match: " + ", ".join(selected["tags"]) +
                        "\nRelease identity only; compatibility and installation still require review."
                        if selected.get("tags") else
                        "\nA filename match does not establish archive authenticity."
                        if status == "Possible archive — inspect first" else "")
                    if selected.get("copies", 0) > 1:
                        evidence += f"\n{selected['copies']} byte-identical copies; newest modified representative shown."
                    if record.get("release_notice"):
                        evidence += "\n" + record["release_notice"]
                    cell.setToolTip(label + evidence)
                cell.setData(Qt.UserRole, record.get("file", ""))
                self.table.setItem(i, col, cell)
            url = planner.source_url(display.get("url", record.get("url")))
            if url:
                btn = QPushButton("Open source")
                btn.setObjectName("downloadsSourceButton")
                btn.setToolTip(f"Open external link in browser: {url}")
                btn.clicked.connect(lambda checked=False, uri=url:
                                    QDesktopServices.openUrl(QUrl(uri)))
                self.table.setCellWidget(i, 4, btn)
            else:
                self.table.setItem(i, 4, QTableWidgetItem("—"))
        self.columns.schedule_rows()
        self._update_review_action()
        self._update_inspect_button()
        self._update_download_button()

    def _review_action(self):
        """Resolve UI intent only; never grant install authority."""
        recipe = self.recipe or {}
        method = recipe.get("method", "file")
        component, _ = self._selected_component()
        if method == "uevr":
            if self._has_uevr_pair():
                return "uevr-pair", "Review installation"
            if recipe.get("profile") and component and component["id"] == "profile":
                return "profile", "Review profile"
            return "guide", "Open Setup Guide"
        if method not in {"bepinex", "ervr", "gameroot"} and not (
                recipe.get("files") and recipe["files"][0].get("kind") == "pak"):
            return "guide", "Open Setup Guide"
        rows = (self._last_plan or {}).get("rows", [])
        components = planner.plan_components(recipe) if recipe else []
        if (method in ("bepinex", "ervr") and components
                and len(rows) == len(components)
                and all(c.get("sha256") for c in components)
                and all(r.get("file") and r.get("status") == "Pinned SHA-256 verified"
                        for r in rows)
                and len({r["file"] for r in rows}) == len(rows)
                and {r["id"] for r in rows} == {c["id"] for c in components}):
            return "mod", "Install verified dependencies"
        return "mod", "Review installation"

    def _has_uevr_pair(self):
        from .uevr_dependency_review import SUPPORTED
        rows = (self._last_plan or {}).get("rows", [])
        return ((self.recipe or {}).get("id") in SUPPORTED
                and len(rows) == 2 and [r.get("id") for r in rows] == ["uevr", "profile"]
                and all(r.get("file") for r in rows))

    @staticmethod
    def _needs_rescan(row):
        return (row.get("status") == "Archive changed — rescan required"
                or row.get("candidate_incomplete")
                or (row.get("matches", 0) > 1 and not row.get("sha256")
                    and "candidates" not in row))

    @staticmethod
    def _verification_blocked(row):
        return row.get("status") in (
            "Hash mismatch — do not install", "Hash not verified — do not install")

    @staticmethod
    def _official_pin_review(row):
        candidates = row.get("candidates") or []
        return (row.get("release_review") is True and row.get("sha256")
                and row.get("status") == "Hash mismatch — do not install"
                and not row.get("candidate_incomplete") and len(candidates) == 1
                and candidates[0].get("expected") and candidates[0].get("sha256")
                and candidates[0]["sha256"] != row["sha256"]
                and row.get("release_expected") in candidates[0].get("tags", [])
                and row.get("file") == candidates[0].get("file"))

    @staticmethod
    def _pin_review_set(rows):
        return (bool(rows) and any(GuidedDownloadsPage._official_pin_review(r) for r in rows)
                and all(r.get("file") and not GuidedDownloadsPage._needs_rescan(r) and
                        (GuidedDownloadsPage._official_pin_review(r) or r.get("status") == "Pinned SHA-256 verified")
                        for r in rows)
                and len({r["file"] for r in rows}) == len(rows))

    def _primary_action(self):
        """Presentation only. The existing review dispatcher still revalidates."""
        recipe = self.recipe or {}
        method = recipe.get("method", "file")
        rows = (self._last_plan or {}).get("rows", [])
        row = self._selected_row_record()
        route, label = self._review_action()
        if not recipe:
            return "idle", "Review installation"
        if recipe.get("handler") == "kharvox-gog":
            label = "Review installation"
            if len(rows) != 1 or self._needs_rescan(rows[0]):
                return "kharvox-wait", label
            record = rows[0]
            if record.get("status") != "Possible archive — inspect first":
                return "kharvox-wait", label
            official = [c for c in record.get("candidates", []) if c.get("tags") and c.get("sha256")]
            if not official:
                return "kharvox-wait", label
            return "kharvox-review", label
        if method == "guide":
            return route, label
        if not rows:
            return "scan", "Scan local archives"
        if (self._last_plan or {}).get("warning"):
            return "scan", "Scan local archives"
        # A complete pinned set and the UEVR pair are batch workflows;
        # an invalid dependency must not be bypassed with a different selection.
        batch = method in ("bepinex", "ervr", "uevr")
        relevant = rows if batch or not row else [row]
        if method in ("bepinex", "ervr") and self._pin_review_set(rows):
            return "pinned-release-review", "Review installation"
        if any(self._verification_blocked(r) for r in relevant):
            return "blocked", "Installation blocked"
        if any(self._needs_rescan(r) for r in relevant):
            return "scan", "Scan local archives"
        if method in ("bepinex", "ervr"):
            if label != "Install verified dependencies":
                return "scan", "Scan local archives"
            return route, label
        if method == "uevr":
            if route == "uevr-pair":
                return route, "Choose archive" if any(r.get("ambiguous") for r in rows) else label
            if route == "profile":
                if not row.get("file"):
                    return "scan", "Scan local archives"
                return route, "Choose archive" if row.get("ambiguous") else label
            if not row:
                profile = next((r for r in rows if r.get("id") == "profile" and r.get("file")), None)
                if profile:
                    return "profile", "Choose archive" if profile.get("ambiguous") else "Review profile"
            if not any(r.get("file") for r in rows):
                return "scan", "Scan local archives"
            return route, label
        if route == "mod":
            if row:
                if not row.get("file"):
                    return "scan", "Scan local archives"
                return route, "Choose archive" if row.get("ambiguous") else label
            available = [r for r in rows if r.get("file")]
            if not available:
                return "scan", "Scan local archives"
            if len(available) == 1:
                return route, "Choose archive" if available[0].get("ambiguous") else label
            return "select", "Select dependency"
        return route, label

    def _manual_review_route(self):
        """One deliberate fallback; never offered for stale/blocked evidence."""
        recipe = self.recipe or {}
        method = recipe.get("method", "file")
        rows = (self._last_plan or {}).get("rows", [])
        if (not recipe or self._saved_error or (self._last_plan or {}).get("warning")
                or not self._last_folder
                or (recipe.get("id") in self._saved and not rows)
                or any(self._needs_rescan(r) or self._verification_blocked(r)
                       for r in rows)):
            return None
        if method == "uevr":
            if recipe.get("profile") and not any(r.get("id") == "profile" and r.get("file") for r in rows):
                return "profile"
            return None
        if self._review_action()[0] != "mod":
            return None
        if not rows:
            return "mod"
        # Unpinned multi-package workflows retain deliberate manual batch
        # selection, without making users pick a single detected archive twice.
        if method == "gameroot" and sum(bool(r.get("file")) for r in rows) > 1:
            return "mod"
        if method not in ("bepinex", "ervr") and not any(r.get("file") for r in rows):
            return "mod"
        return None

    def _request_manual_review(self):
        if (not self.manual_review_button.isEnabled()
                or self.manual_review_button.isHidden()
                or self.worker is not None or self.download_worker is not None):
            return
        route = self._manual_review_route()
        if route and self.recipe:
            if self._last_plan:
                try:
                    fresh = self._fresh_review_rows()
                    if fresh != self._last_plan.get("rows") or any(
                            self._needs_rescan(row) or self._verification_blocked(row)
                            for row in fresh):
                        raise ValueError("Archive evidence changed or is blocked. Rescan before manual review.")
                except (ValueError, RuntimeError, OSError) as exc:
                    self._folder_feedback(str(exc))
                    return
            request = {"game_id": self.recipe["id"], "archives": [], "origin": "downloads-page"}
            if route == "profile":
                request["route"] = route
            self.install_review_requested.emit(request)

    def _selected_row_record(self):
        rows = (self._last_plan or {}).get("rows", [])
        i = self.table.currentRow()
        return rows[i] if 0 <= i < len(rows) else {}

    def _update_workflow_guidance(self):
        if not self.recipe:
            return
        row = self._selected_row_record()
        route, label = self._primary_action()
        plan = self._last_plan or {}
        if (self._last_plan or {}).get("warning"):
            message = "Scan incomplete: " + str(self._last_plan["warning"])
        elif route == "pinned-release-review":
            message = "Newer official release matched, but the recipe pin is not approved. Review only; installation remains blocked."
        elif route in ("kharvox-review", "kharvox-wait"):
            record = (plan.get("rows") or [{}])[0]
            latest = record.get("release_expected")
            message = ("Official release SHA-256 matched. Review compatibility with the tested 1.4 runner; no installation is authorized."
                       if route == "kharvox-review" else
                       "Scan or obtain an official KHARVOX ZIP with matching SHA-256 before review.")
            if latest:
                message += f" Latest upstream archive: {latest}."
            if record.get("release_notice"):
                message += " " + record["release_notice"]
        elif route == "blocked":
            message = "Archive verification blocked. Obtain the correct package from its source and rescan."
        elif route == "scan":
            message = "Scan the archive folder. Missing or stale dependencies must be checked before review."
        elif route == "select":
            message = "Select a dependency below, or choose multiple archives manually."
        elif label == "Choose archive":
            message = "Different archive candidates need your selection before review."
        elif route == "uevr-pair":
            message = "Review both downloaded dependencies together. Existing injector/profile files and recovery needs are evaluated separately. No installation is authorized."
        elif route == "guide":
            message = "Follow this game's existing Setup Guide. Archive detection alone is not installation readiness."
        elif row.get("status") == "Archive changed — rescan required" or row.get("candidate_incomplete"):
            message = "Archive selection is stale or incomplete. Scan local archives again before review."
        elif row.get("phase", 1) > 1:
            message = "Stage 2: complete the required flat-game first launch using Setup Guide. The existing installation gate remains in place."
        elif row.get("status") in ("Hash mismatch — do not install", "Hash not verified — do not install") or (
                self.recipe.get("method") in ("bepinex", "ervr") and
                (plan.get("mismatch") or plan.get("unverified"))):
            message = "Archive verification blocked. Obtain the correct package from its source and rescan."
        elif row.get("matches", 0) > 1 and not row.get("sha256") and "candidates" not in row:
            message = "Saved scan predates candidate detection. Scan local archives to choose the intended version."
        elif row.get("ambiguous"):
            message = "Multiple different or unidentified archives match this dependency. Choose the intended archive before review."
        elif row.get("release_expected") and not any(c.get("expected") for c in row.get("candidates", [])):
            message = f"Could not identify expected release {row['release_expected']} by SHA-256. Check the source before selecting an archive."
        elif row.get("status") == "Not found locally" or plan.get("missing", 0) and self.recipe.get("method") in ("bepinex", "ervr"):
            message = "Required archive missing. Open source, download the dependency and rescan."
        elif plan.get("rows") and plan.get("verified") == len(plan["rows"]):
            message = "All required archives are pinned-hash verified. Continue to installation review."
        else:
            message = "Review archives as packages; the Hub checks internal files, destinations and backups. A release match does not establish compatibility."
        if row.get("phase", 1) > 1 and "Stage 2" not in message:
            message += " Stage 2 requires the game's first flat launch; the installation gate remains in place."
        if row.get("release_notice"):
            message += " " + row["release_notice"]
        self.guidance.setText(message)

    def _update_review_action(self):
        route, label = self._primary_action()
        busy = self.worker is not None or self.download_worker is not None
        # The existing top scan control is the primary action for scan states.
        # Do not display a second identical button.
        self.install_review_button.setVisible(route not in ("scan", "idle"))
        self.install_review_button.setEnabled(not busy and route not in ("blocked", "select", "scan", "idle", "kharvox-wait"))
        self.install_review_button.setText(label)
        manual = self._manual_review_route()
        self.manual_review_button.setVisible(bool(manual))
        self.manual_review_button.setEnabled(bool(manual) and not busy)
        self.manual_review_button.setText("Choose profile manually…" if manual == "profile"
                                          else "Choose archives manually…")
        self.install_review_button.setToolTip(
            "Open this game's existing manual setup instructions."
            if route == "guide" and self.recipe else
            "Open read-only KHARVOX release and compatibility review. No extraction or installation."
            if route in ("kharvox-review", "kharvox-wait") else
            "Review the selected profile ZIP, exact destination and full-directory backup. Nothing changes without confirmation."
            if route == "profile" else
            "Review selected archives and backup policy. Nothing changes without confirmation."
            if route != "blocked" else "Verification blocked. Obtain the correct archive and rescan.")
        self._update_workflow_guidance()
        self.advanced_availability_changed.emit()

    def _fresh_review_rows(self):
        """Recheck the persisted scan identity before reusing a selection."""
        if not self._last_plan:
            return None
        saved = archive_scans.matching_record(self.recipe["id"], self._folders())
        if not saved:
            raise ValueError("Scan both active archive folders before reusing this selection.")
        if saved["plan"].get("warning"):
            raise ValueError("Incomplete scan cannot authorize review; rescan both folders.")
        keys = ("id", "sha256", "phase", "hint", "name", "url")
        expected = [tuple(c.get(k) for k in keys)
                    for c in planner.plan_components(self.recipe)]
        if expected != [tuple(c.get(k) for k in keys) for c in saved["plan"]["rows"]]:
            raise ValueError("Dependency requirements changed. Rescan local archives.")
        return archive_scans.displayed_record(saved)["plan"]["rows"]

    def _update_inspect_button(self):
        row = self.table.currentRow()
        entry = self.table.item(row, 0) if row >= 0 else None
        path = entry.data(Qt.UserRole) if entry else None
        supported = (self.recipe or {}).get("method") in {"gameroot", "bepinex", "ervr"}
        self.inspect.setVisible(bool(supported and path))
        self.inspect.setEnabled(bool(supported and path and Path(path).is_file()))
        self.advanced_availability_changed.emit()

    def _inspect(self):
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        if cell:
            path = cell.data(Qt.UserRole)
            if path and Path(path).is_file():
                self.inspect_requested.emit(str(path))

    def _choose_archive_candidate(self, row):
        options = row.get("candidates", [])
        if not options or row.get("candidate_incomplete"):
            self._folder_feedback("Multiple archive matches need a fresh scan before review.")
            return None
        labels = ["Select an archive"]
        for c in options:
            ident = c["identity"]
            date = datetime.fromtimestamp(ident["mtime_ns"] / 1e9).strftime("%Y-%m-%d %H:%M")
            tags = ", ".join(c["tags"]) or "Release unknown"
            labels.append(f"{Path(c['file']).name}  |  {tags}  |  "
                          f"{human_file_size(ident['size'])}  |  {date}  |  {c['file']}")
        chosen, ok = QInputDialog.getItem(
            self, "Choose dependency archive", "Choose the archive you intend to review (no installation):",
            labels, 0, False)
        if not ok or chosen not in labels[1:]:
            return None
        return options[labels.index(chosen) - 1]

    def _request_install_review(self):
        """Route only current recipe selections to existing review handlers."""
        if not self.recipe or not self.install_review_button.isEnabled():
            return
        rid = self.recipe["id"]
        route, _ = self._primary_action()
        if route in ("blocked", "scan", "idle", "select", "kharvox-wait"):
            return
        if route == "kharvox-review":
            self._request_kharvox_review(rid)
            return
        if route == "pinned-release-review":
            try:
                rows = self._fresh_review_rows()
                if not self._pin_review_set(rows) or rows != self._last_plan["rows"]:
                    raise ValueError("Archive evidence changed. Rescan before review.")
            except (ValueError, RuntimeError, OSError) as exc:
                self._folder_feedback(str(exc))
                return
            self.install_review_requested.emit({"game_id": rid, "route": route,
                "archives": [r["file"] for r in rows], "rows": rows, "origin": "downloads-page"})
            return
        if route in ("profile", "mod") and self.table.currentRow() < 0:
            rows = (self._last_plan or {}).get("rows", [])
            if (self.recipe or {}).get("method") not in ("bepinex", "ervr"):
                available = [i for i, row in enumerate(rows)
                             if row.get("file") and (route != "profile" or row.get("id") == "profile")]
                if len(available) != 1:
                    return
                self.table.selectRow(available[0])
        request = {"game_id": rid, "archives": [], "origin": "downloads-page"}
        if route == "guide":
            self.install_review_requested.emit(dict(request, route="guide"))
            return
        if route == "uevr-pair":
            self._request_uevr_pair(rid, request)
            return
        try:
            rows = self._fresh_review_rows()
        except (ValueError, RuntimeError, OSError) as exc:
            self._folder_feedback(str(exc))
            return
        if rows is not None:
            if self.recipe.get("method") in ("bepinex", "ervr"):
                if (not rows or any(r.get("status") != "Pinned SHA-256 verified"
                                    or not r.get("file") for r in rows)
                        or len({r["file"] for r in rows}) != len(rows)):
                    self._folder_feedback("Complete the verified archive set and rescan before review.")
                    return
                request["archives"] = [r["file"] for r in rows]
            else:
                i = self.table.currentRow()
                if 0 <= i < len(rows):
                    row = rows[i]
                    if row.get("status") in (
                            "Archive changed — rescan required",
                            "Hash mismatch — do not install",
                            "Hash not verified — do not install"):
                        self._folder_feedback("Selected archive is blocked. Rescan or choose another archive.")
                        return
                    if row.get("status") == "Not found locally":
                        self._folder_feedback("Required archive missing. Open source, download it and rescan, or use the manual review tool.")
                        return
                    if row.get("candidate_incomplete"):
                        self._folder_feedback("Incomplete candidate scan. Choose a more specific archive folder and rescan.")
                        return
                    if row.get("ambiguous") or (row.get("matches", 0) > 1 and "candidates" not in row):
                        selected = self._choose_archive_candidate(row)
                        if selected is None:
                            return
                        # A nested dialog can outlive the original selection or
                        # encounter a replaced file. Recheck exact evidence.
                        if not self.recipe or self.recipe["id"] != rid or self.table.currentRow() != i:
                            return
                        try:
                            refreshed = self._fresh_review_rows()
                        except (ValueError, RuntimeError, OSError) as exc:
                            self._folder_feedback(str(exc))
                            return
                        if (not refreshed or i >= len(refreshed)
                                or selected not in refreshed[i].get("candidates", [])
                                or planner.archive_identity(Path(selected["file"])) != selected["identity"]):
                            self._folder_feedback("Selected archive changed. Rescan before review.")
                            return
                        request["archives"] = [selected["file"]]
                    elif row.get("file"):
                        request["archives"] = [row["file"]]
        if route == "profile":
            request["route"] = "profile"
        self.install_review_requested.emit(request)

    def _request_kharvox_review(self, rid):
        try:
            rows = self._fresh_review_rows()
            if (not rows or len(rows) != 1 or rows[0].get("id") != "kharvox"
                    or self._needs_rescan(rows[0])):
                raise ValueError("Archive evidence changed. Rescan before review.")
            row = rows[0]
            candidates = [c for c in row.get("candidates", [])
                          if c.get("tags") and c.get("sha256")]
            expected = [c for c in candidates if c.get("expected")]
            if len(expected) == 1:
                chosen = expected[0]
            elif len(candidates) == 1:
                chosen = candidates[0]
            elif candidates:
                chosen = self._choose_archive_candidate(dict(row, candidates=candidates))
                if chosen is None:
                    return
            else:
                raise ValueError("No official SHA-256 match. Rescan before review.")
            if not self.recipe or self.recipe["id"] != rid:
                return
            if (chosen not in candidates or self._fresh_review_rows() != rows
                    or planner.archive_identity(Path(chosen["file"])) != chosen["identity"]):
                raise ValueError("Selected archive changed. Rescan before review.")
        except (ValueError, RuntimeError, OSError) as exc:
            self._folder_feedback(str(exc))
            return
        self.install_review_requested.emit({
            "game_id": rid, "route": "kharvox-review", "archives": [chosen["file"]],
            "evidence": chosen, "latest": row.get("release_expected", ""),
            "origin": "downloads-page"})

    def _request_uevr_pair(self, rid, request):
        try:
            rows = self._fresh_review_rows()
            if not rows or [r.get("id") for r in rows] != ["uevr", "profile"]:
                raise ValueError("Scan both dependencies before review.")
            files, evidence = [], []
            for row in rows:
                if (not row.get("file") or row.get("candidate_incomplete")
                        or row.get("status") not in ("Possible archive — inspect first", "Pinned SHA-256 verified")):
                    raise ValueError("A required archive is missing, stale or blocked. Rescan before review.")
                if row.get("matches", 0) > 1 and "candidates" not in row:
                    raise ValueError("Saved scan predates candidate detection. Rescan first.")
                if row.get("ambiguous"):
                    chosen = self._choose_archive_candidate(row)
                    if chosen is None:
                        return
                else:
                    chosen = next((c for c in row.get("candidates", []) if c["file"] == row["file"]), None)
                if not self.recipe or self.recipe["id"] != rid:
                    return
                if chosen is not None and (chosen not in row.get("candidates", []) or
                        planner.archive_identity(Path(chosen["file"])) != chosen["identity"]):
                    raise ValueError("Selected archive changed. Rescan before review.")
                files.append(chosen["file"] if chosen else row["file"])
                evidence.append(chosen)
            if len(set(files)) != 2 or self._fresh_review_rows() != rows:
                raise ValueError("Dependencies changed or overlap. Rescan before review.")
        except (ValueError, RuntimeError, OSError) as exc:
            self._folder_feedback(str(exc))
            return
        self.install_review_requested.emit(dict(request, route="uevr-pair", archives=files, evidence=evidence))

    def _selected_component(self):
        """Resolve selection against the CURRENT recipe, not snapshot data."""
        if not self.recipe:
            return None, None
        index = self.table.currentRow()
        components = planner.plan_components(self.recipe)
        if index < 0 or index >= len(components):
            return None, None
        component = components[index]
        status = (self._last_plan["rows"][index]["status"]
                  if self._last_plan and index < len(self._last_plan["rows"])
                  else "Not checked")
        return component, status

    def _update_download_button(self):
        if not hasattr(self, "download_button"):
            return
        transferring = self.download_worker is not None
        active = transferring or self.worker is not None
        component, status = self._selected_component()
        eligible, reason = (
            verified_download.source_support(self.recipe, component)
            if component and self.recipe else (False, "Select a component first."))
        can_download = bool(
            self.allow_transfers and eligible and not active
            and status != "Pinned SHA-256 verified")
        self.download_button.setEnabled(can_download)
        self.download_button.setVisible(bool(eligible and not active
                                             and status != "Pinned SHA-256 verified"))
        self.download_cancel.setVisible(transferring)
        self.download_cancel.setEnabled(transferring and not self._download_cancelling)
        self.advanced_availability_changed.emit()
        if transferring:
            self.download_status.show()
            return  # never replace transfer progress with row-selection hints
        if (self._download_notice and self.recipe
                and self._download_notice[0] == self.recipe["id"]):
            _, message, color = self._download_notice
            self.download_status.setText(message)
            self.download_status.setStyleSheet(f"color: {color};")
            self.download_status.show()
            return
        self.download_status.hide()
        self.download_status.setStyleSheet("")
        if component and status == "Pinned SHA-256 verified":
            self.download_status.setText(
                "Already verified in the archive library. No duplicate download needed.")
        else:
            self.download_status.setText(reason)

    def _request_download(self):
        """No transfer until the user provides a direct URL AND confirms."""
        if not self.allow_transfers or not self.download_button.isEnabled():
            return
        component, status = self._selected_component()
        if not component or not self.recipe:
            return
        allowed, explanation = verified_download.source_support(
            self.recipe, component)
        if not allowed or status == "Pinned SHA-256 verified":
            return
        source = component.get("url", "")
        direct_url, ok = QInputDialog.getText(
            self, "Direct archive URL",
            "Copy a DIRECT archive download link from the official release page.\n"
            "Nexus login/manual downloads are not supported here.\n"
            f"Release page: {source}\n"
            "Paste the exact HTTPS archive URL:")
        if not ok or not direct_url.strip():
            return
        try:
            folder, _ = self._folder()
            authority = verified_download.create_authorization(
                self.recipe, component, direct_url.strip(), folder)
        except (verified_download.DownloadRejected,
                OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Archive URL refused (nothing downloaded)", str(exc))
            return
        approval = QMessageBox.question(
            self, "Confirm verified archive download",
            f"Game: {self.recipe['name']}\n"
            f"Package: {authority.label}\n"
            f"Source: {authority.direct_url}\n"
            f"Destination: {authority.destination_folder / authority.destination_name}\n"
            f"Expected SHA-256:\n{authority.expected_sha256}\n\n"
            "Only the exact SHA-256 match will be retained.\n"
            "Existing archives will never be overwritten.\n"
            "THIS WILL NOT INSTALL ANY MOD.\n\n"
            "Authorize this one download?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if approval != QMessageBox.Yes:
            return
        self._start_verified_download(authority)

    def _start_verified_download(self, authority):
        if not self.allow_transfers:
            return  # isolated acceptance previews have no network permission
        if ((self.download_worker and self.download_worker.isRunning())
                or (self.worker and self.worker.isRunning())):
            return
        self._rescan_after_download = False
        self._download_notice = None
        self._download_cancelling = False
        self.download_status.setStyleSheet("")
        self.download_status.show()
        self.download_progress.setRange(0, 0)
        self.download_progress.show()
        self.download_status.setText(
            f"Downloading and SHA-256 verifying {authority.label}. "
            "No mod files will be installed.")
        self.download_button.setEnabled(False)
        self.download_button.hide()
        self.download_cancel.show()
        self.download_cancel.setEnabled(True)
        for btn in (self.set_global, self.set_game, self.clear_game,
                    self.reset_global, self.scan, self.install_review_button):
            btn.setEnabled(False)
        self.folder_menu_button.setEnabled(False)
        worker = VerifiedArchiveDownloadWorker(authority, self)
        self.download_worker = worker
        worker.progress_changed.connect(
            lambda current, total, token=worker:
                self._download_progress(current, total, token))
        worker.succeeded.connect(
            lambda result, token=worker:
                self._download_succeeded(result, token))
        worker.rejected.connect(
            lambda message, token=worker:
                self._download_failed(message, token))
        worker.cancelled.connect(
            lambda message, token=worker:
                self._download_cancelled(message, token))
        worker.finished.connect(
            lambda token=worker: self._download_finished(token))
        worker.start()
        self._update_review_action()
        self._update_download_button()

    def _download_progress(self, current, total, worker):
        if worker is not self.download_worker:
            return
        if total > 0:
            self.download_progress.setRange(0, 100)
            self.download_progress.setValue(
                max(0, min(100, int(current * 100 / total))))
        else:
            self.download_progress.setRange(0, 0)
        self.download_status.setText(
            f"Downloading {worker.authority.label}: "
            f"{current / 1048576:.1f} MiB"
            + (f" / {total / 1048576:.1f} MiB" if total else "")
            + " — no files installed.")

    def _download_succeeded(self, result, worker):
        if worker is not self.download_worker:
            return
        self._rescan_after_download = (
            self.recipe is not None
            and self.recipe["id"] == worker.authority.game_id
            and self._last_folder == worker.authority.destination_folder)
        message = (
            ("Reused existing verified archive: " if result.reused_existing else
             "Downloaded and SHA-256 verified: ") + str(result.file) +
            "\nNo mods installed.")
        if self._rescan_after_download:
            message += " Refreshing this game's local archive plan."
        else:
            message += " Return to that game and rescan its library."
        self._download_notice = (worker.authority.game_id, message, "#4FE39A")
        self.download_status.setText(message)
        self.download_status.setStyleSheet("color: #4FE39A;")

    def _download_failed(self, message, worker):
        if worker is not self.download_worker:
            return
        msg = f"Download rejected: {message} Existing archives are untouched."
        self._download_notice = (worker.authority.game_id, msg, "#FF5B50")
        self.download_status.setText(msg)
        self.download_status.setStyleSheet("color: #FF5B50;")

    def _download_cancelled(self, message, worker):
        if worker is not self.download_worker:
            return
        self._download_notice = (worker.authority.game_id, message, "#FFD21A")
        self.download_status.setText(message)
        self.download_status.setStyleSheet("color: #FFD21A;")

    def _download_finished(self, worker):
        if worker is not self.download_worker:
            return
        should_scan = self._rescan_after_download
        self._rescan_after_download = False
        self.download_progress.hide()
        self.download_cancel.setEnabled(False)
        self.download_cancel.hide()
        self._download_cancelling = False
        self.download_worker = None
        worker.deleteLater()
        self.set_recipe(self.recipe)
        if should_scan and not getattr(self.window(), "_closing", False):
            # Start the read-only rescan BEFORE announcing idle. Otherwise
            # a pending Hub close could destroy the page in this callback.
            self.start_scan()
        self.download_idle.emit()

    def cancel_download(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self._download_cancelling = True
            self.download_cancel.setEnabled(False)
            self.download_status.setText(
                "Cancelling the transfer. Unfinished data will be discarded.")
