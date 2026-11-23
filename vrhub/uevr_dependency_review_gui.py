# SPDX-License-Identifier: GPL-3.0-only
"""Read-only dialog; deliberately no mutation or confirmation callback."""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout
from .archive_checklist_ui import archive_table
from .install_review import human_file_size as size


class BackendVerification(QThread):
    result = Signal(object)

    def run(self):
        from .fatekeeper_rehearsal import fetch_verified_backend
        try:
            asset = fetch_verified_backend()
        except (OSError, ValueError, RuntimeError):
            self.result.emit(None)
        else:
            self.result.emit(asset)


class InstallRehearsal(QThread):
    result = Signal(bool)

    def __init__(self, archives, asset, parent):
        super().__init__(parent)
        self.archives, self.asset = archives, asset

    def run(self):
        from .fatekeeper_rehearsal import rehearse_install
        try:
            rehearse_install(self.archives, self.asset)
        except (OSError, RuntimeError, ValueError):
            self.result.emit(False)
        else:
            self.result.emit(True)


class DependencyReviewDialog(QDialog):
    def __init__(self, plan, parent=None, *, disposable_rehearsal=False):
        super().__init__(parent)
        self.plan = plan
        self.disposable_rehearsal = disposable_rehearsal
        self.verified_asset = None
        self.setObjectName("uevrDependencyReviewDialog")
        self.setStyleSheet("""
            QDialog#uevrDependencyReviewDialog {background:#0A0D10; color:#E5E8ED;}
            QLabel {color:#E5E8ED;}
            QTableWidget, QPlainTextEdit {background:#11161B;color:#E5E8ED;alternate-background-color:#171D23;}
            QHeaderView::section {background:#14212B;color:#E5E8ED;}
            QPushButton {background:#14212B;color:#E5E8ED;padding:9px;}
            QPushButton:disabled {background:#151D25;color:#69717C;}
        """)
        self.setWindowTitle("Review UEVR installation — preview only")
        self.resize(990, 660)
        layout = QVBoxLayout(self)
        title = QLabel("UEVR INSTALLATION REVIEW — " + plan.game_name)
        title.setWordWrap(True)
        title.setStyleSheet("color:#FFD21A;font-weight:800;font-size:16px")
        layout.addWidget(title)
        self.status = QLabel("PREVIEW ONLY — LIVE INSTALLATION DISABLED")
        self.status.setStyleSheet("color:#FFD21A;font-weight:800")
        layout.addWidget(self.status)
        self.archives = archive_table([
            (plan.injector_archive, "Mod / injector", plan.injector_sha256),
            (plan.profile.archive, "VR profile", plan.profile.archive_sha256)], self)
        layout.addWidget(self.archives)
        def label(text):
            widget = QLabel(text)
            widget.setTextFormat(Qt.PlainText)
            widget.setWordWrap(True)
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(widget)
            return widget
        self.injector = label(
            f"Injector destination: {plan.injector_destination}"+chr(10)+
            f"Archive: {len(plan.injector_files)} files / {size(plan.injector_bytes)}; existing: "
            f"{plan.existing_files} files, {plan.existing_dirs} directories / {size(plan.existing_bytes)}"+chr(10)+
            f"Release evidence: {', '.join(plan.release_tags[0]) or 'Not established'}")
        if plan.backend_status:
            self.backend = label(plan.backend_status)
        self.profile = label(
            f"Profile destination: {plan.profile.destination}"+chr(10)+
            f"Archive: {plan.profile.profile_files} files / {size(plan.profile.profile_bytes)}; existing: "
            f"{plan.profile.existing_files} files, {plan.profile.existing_dirs} directories / {size(plan.profile.existing_bytes)}"+chr(10)+
            f"Release evidence: {', '.join(plan.release_tags[1]) or 'Not established'}")
        self.backup = label("Backup policy: existing profile requires the established verified whole-directory backup and recovery process. "
                            "Injector recovery protection must be validated separately before any live installation.")
        self.blockers = label(chr(10).join(plan.blockers) if plan.blockers else
                              "No additional recovery blocker detected; this is not installation authorization.")
        self.blockers.setStyleSheet("color:#FFD21A;font-weight:700")
        label("Archive identity and layout do not establish VR compatibility. Follow the Setup Guide for runtime prerequisites.")
        self.inventory_toggle = QPushButton("Show exact archive file inventories")
        self.inventory_toggle.setCheckable(True)
        layout.addWidget(self.inventory_toggle)
        self.inventory = QPlainTextEdit()
        self.inventory.setReadOnly(True)
        self.inventory.setPlainText(chr(10).join(("INJECTOR", *plan.injector_files,
                                                   "", "PROFILE", *plan.profile.file_names)))
        self.inventory.hide()
        layout.addWidget(self.inventory)
        self.inventory_toggle.toggled.connect(self.inventory.setVisible)
        self.inventory_toggle.toggled.connect(lambda active: self.inventory_toggle.setText(
            "Hide exact archive file inventories" if active else "Show exact archive file inventories"))
        layout.addStretch(1)
        buttons = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        buttons.addStretch()
        self.apply_button = QPushButton("Install reviewed dependencies")
        self.apply_button.setEnabled(False)
        self.apply_button.setToolTip("Live UEVR dependency installation is not implemented or authorized.")
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)

        if disposable_rehearsal:
            self.apply_button.setText("Test installation and rollback")
            self.apply_button.setToolTip("Runs only against a separate disposable prefix.")
            self.apply_button.clicked.connect(self.run_rehearsal)
        if plan.needs_backend_verification:
            self.backend.setText(plan.backend_status + " Verifying the pinned backend release...")
            worker = BackendVerification(QApplication.instance())
            worker.result.connect(self.show_backend_result)
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def show_backend_result(self, asset):
        if asset is not None:
            self.verified_asset = asset
            self.apply_button.setEnabled(self.disposable_rehearsal)
            self.backend.setText(self.plan.backend_status + " Backend SHA-256 verified.")
        else:
            self.backend.setText(
                "Backend verification failed. Check your connection and reopen Review installation. "
                "No installation files were changed.")


    def run_rehearsal(self):
        if not self.disposable_rehearsal or self.verified_asset is None:
            return
        from pathlib import Path

        self.apply_button.setEnabled(False)
        self.status.setText("Testing install and rollback in a disposable prefix...")
        archives = [Path(self.plan.injector_archive), Path(self.plan.profile.archive)]
        worker = InstallRehearsal(archives, self.verified_asset, QApplication.instance())
        worker.result.connect(self.show_rehearsal_result)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def show_rehearsal_result(self, passed):
        self.status.setText(
            "Disposable installation and rollback passed. Live installation disabled." if passed else
            "Disposable installation check failed. Live installation remains disabled."
        )
        self.apply_button.setEnabled(True)
