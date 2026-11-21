# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5C guided installation review and explicit, gated user confirmation."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout
)

from . import install_review
from .archive_checklist_ui import review_archive_table


class InstallReviewDialog(QDialog):
    """The caller may apply only if confirmed_by_user and a fresh plan matches."""

    def __init__(self, plan: install_review.InstallPlan, parent=None, *,
                 allow_install=True, recipe=None):
        super().__init__(parent)
        self.plan = plan
        self.confirmed_by_user = False
        self.setObjectName("installReviewDialog")
        # A QDialog does not reliably inherit the parent QMainWindow's dark
        # stylesheet on every KDE/Qt platform. Style this dialog explicitly
        # so safety confirmations remain visible on either desktop theme.
        self.setStyleSheet("""
        QDialog#installReviewDialog {
            background: #0A0D10;
            color: #E5E8ED;
        }
        QLabel {
            color: #E5E8ED;
            background: transparent;
        }
        QLabel#installReviewTitle {
            color: #FFD21A;
            font-size: 18px;
            font-weight: 800;
        }
        QLabel#installReviewOverview {
            color: #E5E8ED;
            background: #151D25;
            border: 1px solid #2A3139;
            border-radius: 7px;
            padding: 9px;
        }
        QLabel#installReviewBackup {
            color: #23B7FF;
            font-weight: 700;
            padding: 5px;
        }
        QCheckBox {
            color: #E5E8ED;
            padding: 4px 3px;
            font-size: 12px;
            background: transparent;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            background: #11161B;
            border: 1px solid #72808C;
            border-radius: 3px;
        }
        QCheckBox::indicator:checked {
            background: #FFD21A;
            border-color: #FFD21A;
        }
        QCheckBox::indicator:disabled {
            background: #151D25;
            border-color: #39414A;
        }
        QCheckBox::indicator:checked:disabled {
            background: #7C6B25;
        }
        QTextBrowser#installReviewNotes {
            background: #11161B;
            color: #E5E8ED;
            border: 1px solid #2A3139;
            padding: 6px;
        }
        QTableWidget#installReviewTargets, QTableWidget#installReviewArchives {
            background: #11161B;
            alternate-background-color: #171D23;
            color: #E5E8ED;
            selection-background-color: #3B3108;
            border: 1px solid #2A3139;
        }
        QHeaderView::section {
            background: #14212B;
            color: #E5E8ED;
            padding: 7px;
        }
        QPushButton#installManifestDisclosure {
            background: #14212B;
            color: #23B7FF;
            border: 1px solid #244A61;
            border-radius: 6px;
            padding: 8px 12px;
            text-align: left;
            font-weight: 700;
        }
        QPushButton#installManifestDisclosure:checked {
            color: #FFD21A;
            border-color: #66591A;
        }
        QPushButton#installReviewApply {
            background: #342B0B;
            border: 1px solid #FFD21A;
            color: #FFD21A;
            padding: 9px 16px;
            font-weight: 700;
        }
        QPushButton#installReviewApply:disabled {
            background: #151D25;
            border: 1px solid #2A3139;
            color: #69717C;
        }
        QPushButton#installReviewCancel {
            color: #23B7FF;
            background: #14212B;
            border: 1px solid #244A61;
            padding: 9px 16px;
        }
        """)
        self.setWindowTitle("Review installation — no files changed yet")
        self.resize(1050, 690)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        title = QLabel("REVIEW SELECTED ARCHIVES")
        title.setObjectName("installReviewTitle")
        outer.addWidget(title)

        badge = "BLOCKED — DO NOT INSTALL" if plan.blocked else (
            "REVIEW READY — INSTALLATION REQUIRES CONFIRMATION")
        self.status = QLabel(badge)
        self.status.setObjectName("installReviewStatus")
        self.status.setProperty("blocked", bool(plan.blocked))
        self.status.setStyleSheet(
            "color: #FF5B50; font-weight: 800; font-size: 13px;"
            if plan.blocked else
            "color: #4FE39A; font-weight: 800; font-size: 13px;")
        outer.addWidget(self.status)

        overview = QLabel(
            f"Game: {plan.game_name}\n"
            f"Destination: {plan.game_root}\n"
            f"Packages: {', '.join(plan.package_labels)}\n"
            f"{plan.new_files} new files · {plan.overwrites} replacements · "
            f"{install_review.human_file_size(plan.backup_bytes)} of originals to back up")
        overview.setObjectName("installReviewOverview")
        overview.setToolTip(
            f"Exact original-file backup estimate: {plan.backup_bytes:,} bytes")
        overview.setWordWrap(True)
        overview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(overview)

        backup = QLabel("BACKUP POLICY: " + plan.backup_policy)
        backup.setObjectName("installReviewBackup")
        backup.setWordWrap(True)
        outer.addWidget(backup)

        # Archive-level presentation is the default. The original exact
        # target manifest stays complete, accessible, and part of consent.
        self.archives = review_archive_table(plan, self, recipe=recipe)
        outer.addWidget(self.archives)
        self.manifest_toggle = QPushButton(
            f"Show exact file changes ({len(plan.target_rows)})")
        self.manifest_toggle.setObjectName("installManifestDisclosure")
        self.manifest_toggle.setCheckable(True)
        self.manifest_toggle.setToolTip(
            "Expand the full destination manifest. No individual file selections are needed.")
        outer.addWidget(self.manifest_toggle)

        self.targets = QTableWidget(len(plan.target_rows), 3)
        self.targets.setObjectName("installReviewTargets")
        self.targets.setHorizontalHeaderLabels(
            ("Exact relative destination", "Planned action", "Existing size"))
        self.targets.setAlternatingRowColors(True)
        self.targets.verticalHeader().hide()
        self.targets.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.targets.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.targets.setWordWrap(False)
        h = self.targets.horizontalHeader()
        h.setStretchLastSection(False)
        for column in range(3):
            h.setSectionResizeMode(column, QHeaderView.Interactive)
        self.targets.setColumnWidth(0, 520)
        self.targets.setColumnWidth(1, 315)
        self.targets.setColumnWidth(2, 125)
        for i, item in enumerate(plan.target_rows):
            values = (
                item.relative, item.action,
                install_review.human_file_size(item.current_bytes)
                if item.current_sha256 else "Not present")
            for j, val in enumerate(values):
                cell = QTableWidgetItem(val)
                if j == 2 and item.current_sha256:
                    cell.setToolTip(
                        f"Exact existing size: {item.current_bytes:,} bytes")
                else:
                    cell.setToolTip(item.path if j == 0 else val)
                if j == 1:
                    cell.setForeground(QColor(
                        "#FFD21A" if item.current_sha256 else "#4FE39A"))
                self.targets.setItem(i, j, cell)
        outer.addWidget(self.targets, 1)
        self.targets.hide()
        self.manifest_toggle.toggled.connect(self._toggle_manifest)

        self.notes = QTextBrowser()
        self.notes.setObjectName("installReviewNotes")
        self.notes.setOpenExternalLinks(False)
        self.notes.setPlainText(install_review.summary(plan))
        self.notes.setMinimumHeight(125)
        self.notes.setMaximumHeight(195)
        outer.addWidget(self.notes)

        self.confirm_targets = QCheckBox(
            "I reviewed the archive summary and understand the planned file additions or replacements.")
        self.confirm_targets.setObjectName("installConfirmTargets")
        self.confirm_targets.setChecked(False)
        self.confirm_targets.setToolTip(
            "Exact file changes are available for optional detailed review.")
        self.confirm_backup = QCheckBox(
            "I understand the backup policy and will preserve any personal mod changes.")
        self.confirm_backup.setObjectName("installConfirmBackup")
        self.confirm_backup.setChecked(False)
        self.confirm_closed = QCheckBox(
            "I confirm the game is closed and authorize this specific installation.")
        self.confirm_closed.setObjectName("installConfirmGameClosed")
        self.confirm_closed.setChecked(False)
        for box in (self.confirm_targets, self.confirm_backup, self.confirm_closed):
            outer.addWidget(box)
            box.toggled.connect(self._refresh_apply_button)

        row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("installReviewCancel")
        self.cancel_button.clicked.connect(self.reject)
        row.addWidget(self.cancel_button)
        row.addStretch(1)
        self.apply_button = QPushButton("Install reviewed archives")
        self.apply_button.setObjectName("installReviewApply")
        self.apply_button.clicked.connect(self._accept_confirmed)
        self.apply_button.setToolTip(
            "Installs only after all confirmations.\n"
            "A fresh manifest check runs first.")
        row.addWidget(self.apply_button)
        outer.addLayout(row)

        self.allow_install = bool(allow_install)
        if not allow_install:
            self.status.setText(
                ("PREVIEW ONLY — BLOCKED — live installation disabled"
                 if plan.blocked else
                 "PREVIEW ONLY — live installation disabled in this test window"))
            self.status.setStyleSheet(
                "color: #FFD21A; font-weight: 800; font-size: 13px;")
        self._refresh_apply_button()

    def _toggle_manifest(self, expanded):
        self.targets.setVisible(expanded)
        self.manifest_toggle.setText(
            f"{'Hide' if expanded else 'Show'} exact file changes ({len(self.plan.target_rows)})")
        self._refresh_apply_button()

    def _refresh_apply_button(self):
        enabled = (self.allow_install and self.plan.approved_for_review
                   and all(box.isChecked() for box in (
                       self.confirm_targets, self.confirm_backup,
                       self.confirm_closed)))
        self.apply_button.setEnabled(enabled)

    def _accept_confirmed(self):
        if not self.apply_button.isEnabled():
            return
        self.confirmed_by_user = True
        self.accept()
