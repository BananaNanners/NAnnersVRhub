# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""UEVR profile read-only review with explicit guarded confirmation."""
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QAbstractItemView, QHeaderView
)
from PySide6.QtCore import Qt

from .profile_safety import ProfilePlan
from .install_review import human_file_size


class ProfileReviewDialog(QDialog):
    def __init__(self, plan: ProfilePlan, parent=None, *, allow_install=True):
        super().__init__(parent)
        self.plan = plan
        self.confirmed_by_user = False
        self.allow_install = bool(allow_install)
        self.setObjectName("uevrProfileReviewDialog")
        self.setWindowTitle("Review UEVR profile replacement — no changes yet")
        self.resize(990, 455)
        self.setStyleSheet("""
        QDialog#uevrProfileReviewDialog {background: #0A0D10; color: #E5E8ED;}
        QLabel {color: #E5E8ED;}
        QLabel#uevrProfileReviewTitle {color: #FFD21A; font-weight: 800; font-size: 18px;}
        QLabel#uevrProfileReviewBackup {color: #23B7FF; font-weight: 700;}
        QTableWidget {background:#11161B; color:#E5E8ED; alternate-background-color:#171D23;}
        QHeaderView::section {background:#14212B; color:#E5E8ED;}
        QCheckBox {color:#E5E8ED;}
        QPushButton {background:#14212B; color:#E5E8ED; padding:9px;}
        QPushButton:disabled {background:#151D25; color:#69717C;}
        QPushButton#profileManifestDisclosure {
            background:#14212B; color:#23B7FF; border:1px solid #244A61;
            border-radius:6px; text-align:left; font-weight:700;
        }
        QPushButton#profileManifestDisclosure:checked {
            color:#FFD21A; border-color:#66591A;
        }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title = QLabel("UEVR PROFILE — BACKUP AND REPLACEMENT REVIEW")
        title.setObjectName("uevrProfileReviewTitle")
        layout.addWidget(title)
        self.status = QLabel(
            "BLOCKED — MANUAL RECOVERY REVIEW REQUIRED" if plan.blocked else
            ("READ-ONLY PREVIEW — INSTALLATION IS DISABLED"
             if not self.allow_install else
             "READY FOR CONFIRMATION — NO GAME FILES CHANGED"))
        self.status.setStyleSheet(
            "color:#FF5B50; font-weight:800" if plan.blocked else
            ("color:#FFD21A; font-weight:800" if not self.allow_install else
             "color:#4FE39A; font-weight:800"))
        layout.addWidget(self.status)
        overview = QLabel(
            f"Game: {plan.game_name}\n"
            f"Exact destination: {plan.destination}\n"
            f"Archive: {plan.archive}\n"
            f"New profile: {plan.profile_files} files / {human_file_size(plan.profile_bytes)}\n"
            f"Current profile: {plan.existing_files} files, {plan.existing_dirs} directories / "
            f"{human_file_size(plan.existing_bytes)}"
        )
        overview.setObjectName("uevrProfileReviewOverview")
        overview.setToolTip(
            f"Exact selected archive contents: {plan.profile_bytes:,} bytes\n"
            f"Exact existing profile size / backup estimate: {plan.existing_bytes:,} bytes")
        overview.setWordWrap(True)
        overview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(overview)
        self.backup = QLabel(
            "BACKUP POLICY: Make and verify a persistent SHA-256 whole-directory "
            "backup before replacement. Retain originals after restoration. "
            "Restore stops if the installed profile changes.")
        self.backup.setObjectName("uevrProfileReviewBackup")
        self.backup.setWordWrap(True)
        layout.addWidget(self.backup)
        if plan.blocked:
            warning = QLabel("\n".join(plan.blocked))
            warning.setObjectName("uevrProfileReviewBlocker")
            warning.setWordWrap(True)
            warning.setStyleSheet("color:#FFD21A; font-weight:700")
            layout.addWidget(warning)
        self.table = QTableWidget(len(plan.file_names), 1)
        self.table.setObjectName("uevrProfileArchiveFiles")
        self.table.setHorizontalHeaderLabels(["Archive file to place inside the reviewed profile directory"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for index, name in enumerate(plan.file_names):
            self.table.setItem(index, 0, QTableWidgetItem(name))
        self.manifest_seen = False
        self.manifest_toggle = QPushButton(
            f"Show profile file inventory ({len(plan.file_names)})")
        self.manifest_toggle.setObjectName("profileManifestDisclosure")
        self.manifest_toggle.setCheckable(True)
        layout.addWidget(self.manifest_toggle)
        layout.addWidget(self.table)
        self.table.setMinimumHeight(150)
        self.table.hide()
        layout.addStretch(1)
        self.manifest_toggle.toggled.connect(self._toggle_manifest)
        self.ack = QCheckBox("I reviewed the exact destination, full-backup policy and file inventory.")
        self.ack.setEnabled(False)
        self.ack.setToolTip("Open the complete file inventory once before acknowledging.")
        self.ack.setObjectName("uevrProfileAck")
        layout.addWidget(self.ack)
        self.apply_btn = QPushButton("Confirm safe profile replacement")
        self.apply_btn.setObjectName("uevrProfileApply")
        self.cancel_btn = QPushButton("Cancel")
        self.apply_btn.clicked.connect(self._confirmed)
        self.cancel_btn.clicked.connect(self.reject)
        self.ack.toggled.connect(self._update)
        buttons = QHBoxLayout()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.apply_btn)
        layout.addLayout(buttons)
        self.allow_install = bool(allow_install)
        self._update()

    def _toggle_manifest(self, expanded):
        self.table.setVisible(expanded)
        self.manifest_toggle.setText(
            f"{'Hide' if expanded else 'Show'} profile file inventory ({len(self.plan.file_names)})")
        if expanded and not self.manifest_seen:
            self.manifest_seen = True
            self.ack.setChecked(False)
            self.ack.setEnabled(True)
        self._update()

    def _update(self):
        self.apply_btn.setEnabled(self.allow_install and self.manifest_seen
                                  and self.plan.ready and self.ack.isChecked())

    def _confirmed(self):
        if not (self.allow_install and self.manifest_seen
                and self.plan.ready and self.ack.isChecked()):
            return
        self.confirmed_by_user = True
        self.accept()
