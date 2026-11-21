# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A: native read-only guided downloads and archive inspection page.

Changing a folder only updates Hub-specific preferences. Archive scans hash
local files and validate pinned checksums, but never download or install.
"""
from pathlib import Path
from html import escape
from datetime import datetime
from threading import Event

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QInputDialog, QMessageBox, QMenu, QPlainTextEdit, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from . import download_planner as planner, archive_scans, verified_download, hub
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("guidedDownloadsPage")
        self.recipe = None
        self._last_id = None
        self._last_folder = None
        self._last_plan = None
        self.worker = None
        self.download_worker = None
        self.allow_transfers = True
        self._download_notice = None  # (game_id, result message, color)
        self._rescan_after_download = False
        self._saved_error = None
        try:
            self._saved = archive_scans.load_saved()
        except (ValueError, OSError) as exc:
            # A damaged snapshot file must be preserved, never overwritten.
            self._saved, self._saved_error = {}, str(exc)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(9)

        title = QLabel("ARCHIVE DEPENDENCIES")
        title.setObjectName("downloadsHeading")
        outer.addWidget(title)

        explanation = QLabel(
            "Scan downloaded archives for this game. A green check means a "
            "recipe-pinned SHA-256 matched; yellow means a filename match still "
            "needs review. Red means blocked. Scanning is read-only. "
            "Drag column dividers to resize or double-click to fit text.")
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

        self.set_global = QPushButton("Choose default folder")
        self.set_global.setObjectName("downloadsAction")
        self.set_game = QPushButton("Choose game folder")
        self.set_game.setObjectName("downloadsAction")
        self.clear_game = QPushButton("Use default folder")
        self.clear_game.setObjectName("downloadsAction")
        self.reset_global = QPushButton("Auto-detect default")
        self.reset_global.setObjectName("downloadsAction")
        self.scan = QPushButton("Scan local archives")
        self.scan.setObjectName("downloadsScan")
        # Brief, deliberately line-broken native tooltips. One action per
        # button; no multi-paragraph mouse hover covering other controls.
        self.set_global.setToolTip(
            "Choose the shared archive folder.\n"
            "Used by games without their own folder.\n"
            "Archives are not moved or downloaded.")
        self.set_game.setToolTip(
            "Choose a folder for this game only.\n"
            "Changing it clears this game's old scan.\n"
            "Other games keep their saved scans.")
        self.clear_game.setToolTip(
            "Remove this game's folder override.\n"
            "Use the shared default folder instead.\n"
            "Unchanged-folder scans stay saved.")
        self.reset_global.setToolTip(
            "Restore automatic SHARED folder discovery.\n"
            "A game-specific folder stays selected.\n"
            "Unchanged-folder scans stay saved.")
        self.scan.setToolTip(
            "Scan this game's selected archive folder.\n"
            "Update its saved verification results.\n"
            "No archives are installed or changed.")
        # Dev5D1-B: one folder menu replaces four persistent buttons.
        # Keep each original action object and its signal handler so folder
        # selection, default clearing, and saved scans behave exactly as before.
        self.folder_menu_button = QPushButton("Archive folder")
        self.folder_menu_button.setObjectName("downloadsAction")
        self.folder_menu_button.setToolTip(
            "Choose or change a shared/game-specific archive folder.\n"
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

        footer = QHBoxLayout()
        self.inspect = QPushButton("Inspect selected archive")
        self.inspect.setObjectName("downloadsAction")
        self.inspect.setToolTip(
            "Inspect a supported local archive.\n"
            "Read-only check; nothing is installed.")
        self.inspect.setEnabled(False)
        self.inspect.clicked.connect(self._inspect)
        footer.addWidget(self.inspect)
        self.install_review_button = QPushButton("Review installation")
        self.install_review_button.setObjectName("downloadsAction")
        self.install_review_button.setToolTip(
            "Review selected archives and backup policy.\n"
            "The Hub checks every destination internally.\n"
            "Nothing changes without confirmation.")
        self.install_review_button.clicked.connect(self._request_install_review)
        footer.addWidget(self.install_review_button)
        footer.addStretch()
        outer.addLayout(footer)

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

        self.download_button.clicked.connect(self._request_download)
        self.download_cancel.clicked.connect(self.cancel_download)
        self.table.itemSelectionChanged.connect(self._update_download_button)

        self.guidance = QLabel(
            "Only approved installer workflows should modify game files. "
            "The existing Setup guide remains the source for installation order.")
        self.guidance.setObjectName("downloadsExplanation")
        self.guidance.setWordWrap(True)
        outer.addWidget(self.guidance)
        self.table.itemSelectionChanged.connect(self._update_inspect_button)
        self.set_recipe(None)

    def _sync_folder_actions(self):
        """Reflect current scan/download safety state in the folder menu."""
        for button, action in self.folder_menu_actions.items():
            action.setEnabled(button.isEnabled())
            action.setText(button.text())
            action.setToolTip(button.toolTip())
        self.folder_menu_button.setEnabled(
            any(button.isEnabled() for button in self.folder_menu_actions))

    def closeEvent(self, event):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            event.ignore()
            return
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        super().closeEvent(event)

    def _folder(self):
        return planner.folder_for(self.recipe) if self.recipe else (None, "")

    def set_recipe(self, recipe):
        self.recipe = recipe
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
            self.upstream_link.clear()
        self.upstream_link.setVisible(bool(upstream))
        if self._saved_error:
            self.saved_scan_count.setText(
                "Saved scan history needs review; original data was preserved.")
        else:
            self.saved_scan_count.setText(
                f"Saved archive scans: {len(self._saved)} game profiles · "
                "Historical results retained across Hub updates.")
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
        if rid != self._last_id or folder != self._last_folder:
            self._last_id = rid
            self._last_folder = folder
        saved = self._saved.get(rid) if rid and folder else None
        # A historical snapshot from a previous recipe version must never
        # display a green check for a changed pin or dependency assignment.
        # Leave the persisted record untouched; only suppress its display.
        outdated_recipe = False
        if saved and saved["folder"] == str(folder):
            keys = ("id", "sha256", "phase", "hint", "name", "url")
            expected = [tuple(c.get(k) for k in keys)
                        for c in planner.plan_components(recipe)]
            recorded = [tuple(c.get(k) for k in keys)
                        for c in saved["plan"]["rows"]]
            outdated_recipe = expected != recorded
        if saved and saved["folder"] == str(folder) and not outdated_recipe:
            # Resolve again on game switch: changing or removing an archive
            # must invalidate previously verified status.
            self._last_plan = archive_scans.displayed_record(saved)["plan"]
            self._set_scan_age(saved)
        else:
            self._last_plan = None
            self.scan_age.setText(
                self._saved_error or (
                    "Saved scan uses older dependency requirements. "
                    "Rescan required; historical record retained."
                    if outdated_recipe else "No scan saved for this game yet. "
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
                prefs = planner.load_preferences()
                shared = (Path(prefs["global"]) if prefs["global"]
                          else planner.default_library())
                shared_source = ("manually selected" if prefs["global"]
                                 else "auto-detected")
                self.location.setText(
                    f"Current game folder ({source}): {folder}\n"
                    f"Shared default ({shared_source}): {shared}")
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
            if scope == "global" and planner.load_preferences()["games"].get(
                    self.recipe["id"]):
                self._folder_feedback(
                    "Shared default changed. This game still uses its custom "
                    "folder. Select 'Use default folder' to switch it.")
            else:
                self._folder_feedback(
                    "Folder choice updated. Archives were not moved. "
                    "Rescan if the selected folder changed.")
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
                "This game now uses the shared default. Saved results are "
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
            # is already auto-detected.
            if had_shared_override:
                planner.set_location("global", None)
                self._invalidate_changed_locations()
            self.set_recipe(self.recipe)
            if has_game_override:
                self._folder_feedback(
                    "Shared default now auto-detected. This game still uses "
                    "its custom folder. Select 'Use default folder' to switch.")
            elif had_shared_override:
                self._folder_feedback(
                    "Shared default restored to automatic discovery. "
                    "Rescan if the selected folder changed.")
            else:
                self._folder_feedback(
                    "Shared default is already auto-detected. No setting "
                    "or saved scan was changed.")
        except (RuntimeError, ValueError, OSError) as exc:
            self.summary.setText(f"Default folder preference was NOT changed: {exc}")

    def start_scan(self):
        if (not self.recipe or (self.worker and self.worker.isRunning())
                or (self.download_worker and self.download_worker.isRunning())):
            return
        try:
            folder, _ = self._folder()
        except (ValueError, RuntimeError, OSError) as exc:
            self.summary.setText(f"Cannot scan folder: {exc}")
            return
        self.progress.show()
        self.summary.setText("Scanning local archives and checking any pinned release hashes…")
        for btn in (self.set_global, self.set_game, self.clear_game,
                    self.reset_global, self.scan, self.install_review_button):
            btn.setEnabled(False)
        self.folder_menu_button.setEnabled(False)
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
            f'{len(plan["rows"])} dependencies · {plan["scanned"]} archives found in folder · {plan["verified"]} pinned hashes verified '
            f'· {plan["possible"]} possible matches needing inspection '
            f'· {plan["mismatch"]} mismatched (BLOCKED) '
            f'· {plan["unverified"]} unchecked (BLOCKED) · {plan["missing"]} missing'
            + (f' · {changed} changed — rescan required' if changed else "")
            + (f' — {plan["warning"]}' if plan.get("warning") else ""))
        self.guidance.setText(
            "Review archives as packages; the Hub checks internal files and backups "
            "when preparing installation. Stage 2 must wait for the required flat-game "
            "first run. A found or verified archive is not a VR readiness result.")

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
                if col == 2 and record.get("file"):
                    size = record.get("size", 0)
                    count = record.get("matches", 1)
                    cell.setToolTip(
                        str(record["file"]) +
                        (f"\nSize: {human_file_size(size)}" if size else "") +
                        (f"\n{count} matching candidates; shown archive is the planner's selection."
                         if count > 1 else ""))
                if col == 3:
                    cell.setForeground(QColor(COLOR.get(value, "#A7ADB7")))
                    cell.setIcon(status_icon(value))
                    cell.setToolTip(value + (
                        "\nA scan is not permission to install."
                        if value == "Pinned SHA-256 verified" else
                        "\nA filename match does not establish archive authenticity."
                        if value == "Possible archive — inspect first" else ""))
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
        # Make the existing all-pinned-package route discoverable. This is
        # display only: _request_install_review still passes paths to the
        # original full manifest builder and revalidation gate.
        components = planner.plan_components(self.recipe) if self.recipe else []
        complete_pinned = (
            bool(self.recipe and self.recipe.get("method") in ("bepinex", "ervr"))
            and bool(components) and len(records) == len(components)
            and all(c.get("sha256") for c in components)
            and all(r.get("file") and r.get("status") == "Pinned SHA-256 verified"
                    for r in records)
            and len({r["file"] for r in records}) == len(records)
            and {r.get("id") for r in records} == {c["id"] for c in components})
        self.install_review_button.setText(
            f"Review {len(records)} verified archives" if complete_pinned
            else "Review installation")
        self._update_inspect_button()
        self._update_download_button()

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

    def _request_install_review(self):
        """Emit only file selections. Parent must rebuild the exact manifest."""
        if not self.recipe or not self.install_review_button.isEnabled():
            return
        rid = self.recipe["id"]
        paths = []
        method = self.recipe.get("method")
        if self._last_plan and self._last_plan.get("game_id") == rid:
            records = self._last_plan["rows"]
            if method in ("bepinex", "ervr"):
                # An ordered set is required for pinned multi-package installs.
                paths = [row["file"] for row in records
                         if row.get("status") == "Pinned SHA-256 verified"
                         and row.get("file") and Path(row["file"]).is_file()]
            else:
                i = self.table.currentRow()
                if 0 <= i < len(records):
                    row = records[i]
                    if (row.get("file") and Path(row["file"]).is_file()
                            and row.get("status") != "Archive changed — rescan required"):
                        paths = [row["file"]]
        self.install_review_requested.emit({
            "game_id": rid, "archives": paths, "origin": "downloads-page"})

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
        active = bool(
            (self.download_worker and self.download_worker.isRunning()) or
            (self.worker and self.worker.isRunning()))
        component, status = self._selected_component()
        eligible, reason = (
            verified_download.source_support(self.recipe, component)
            if component and self.recipe else (False, "Select a component first."))
        can_download = bool(
            self.allow_transfers and eligible and not active
            and status != "Pinned SHA-256 verified")
        self.download_button.setEnabled(can_download)
        self.download_cancel.setEnabled(
            bool(self.download_worker and self.download_worker.isRunning()))
        if active:
            return  # never replace transfer progress with row-selection hints
        if (self._download_notice and self.recipe
                and self._download_notice[0] == self.recipe["id"]):
            _, message, color = self._download_notice
            self.download_status.setText(message)
            self.download_status.setStyleSheet(f"color: {color};")
            return
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
        self.download_status.setStyleSheet("")
        self.download_progress.setRange(0, 0)
        self.download_progress.show()
        self.download_status.setText(
            f"Downloading and SHA-256 verifying {authority.label}. "
            "No mod files will be installed.")
        self.download_button.setEnabled(False)
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
            self.download_cancel.setEnabled(False)
            self.download_status.setText(
                "Cancelling the transfer. Unfinished data will be discarded.")
