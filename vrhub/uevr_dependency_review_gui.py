# SPDX-License-Identifier: GPL-3.0-only
"""Review pinned dependencies and invoke the gated installer."""
from collections import Counter

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

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            self.action()
        except (OSError, RuntimeError, ValueError):
            self.result.emit(False)
        else:
            self.result.emit(True)


class DependencyReviewDialog(QDialog):
    def __init__(self, plan, parent=None, *, disposable_rehearsal=False,
                 install_action=None, install_authorized=None):
        super().__init__(parent)
        self.plan = plan
        self.disposable_rehearsal = disposable_rehearsal
        self.verified_asset = None
        self.install_action = install_action
        self.install_authorized = install_authorized or (lambda: False)
        self.install_worker = None
        self.install_attempted = False
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
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        if plan.verification_failed:
            self.status.setText("INSTALLATION BLOCKED - DOWNLOAD COULD NOT BE VERIFIED")

        def archive_label(path, role):
            if path in plan.failed_archives:
                return role + " (checksum failed)"
            return role

        self.archives = archive_table([
            (plan.injector_archive, archive_label(plan.injector_archive, "Mod / injector"), plan.injector_sha256),
            (plan.profile.archive, archive_label(plan.profile.archive, "VR profile"), plan.profile.archive_sha256)], self)
        layout.addWidget(self.archives)
        def label(text):
            widget = QLabel(text)
            widget.setTextFormat(Qt.PlainText)
            widget.setWordWrap(True)
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(widget)
            return widget
        def archive_summary(files, archive_bytes):
            if plan.verification_failed:
                return "Archive contents pending checksum verification"
            return f"Archive: {files} files / {size(archive_bytes)}"

        self.injector = label(
            f"Injector destination: {plan.injector_destination}"+chr(10)+
            archive_summary(len(plan.injector_files), plan.injector_bytes) + "; existing: "
            f"{plan.existing_files} files, {plan.existing_dirs} directories / {size(plan.existing_bytes)}"+chr(10)+
            f"Release evidence: {', '.join(plan.release_tags[0]) or 'Not established'}")
        if plan.backend_status:
            self.backend = label(plan.backend_status)
        self.profile = label(
            f"Profile destination: {plan.profile.destination}"+chr(10)+
            archive_summary(plan.profile.profile_files, plan.profile.profile_bytes) + "; existing: "
            f"{plan.profile.existing_files} files, {plan.profile.existing_dirs} directories / {size(plan.profile.existing_bytes)}"+chr(10)+
            f"Release evidence: {', '.join(plan.release_tags[1]) or 'Not established'}")
        self.has_changes = True
        if plan.file_decisions:
            counts = Counter(action for action, _, _ in plan.file_decisions)
            summary = " / ".join(f"{action} {counts[action]}" for action in ("Install", "Replace", "Preserve"))
            self.has_changes = bool(counts["Install"] or counts["Replace"])
            self.backup = label(summary)
            status = ("Existing files selected for replacement and Hub records are backed up before writes."
                      if self.has_changes else
                      "No file or Hub record writes are needed.")
            from .fatekeeper_recognition import summarize_plan, summary_text
            status = summary_text(summarize_plan(plan)) + "\n" + status
            if plan.blockers:
                status += "\n" + "\n".join(plan.blockers)
            self.blockers = label(status)
        else:
            self.backup = label("Backup policy: existing profile requires verified backup and recovery.")
            self.blockers = label(chr(10).join(plan.blockers) if plan.blockers else
                                  "No additional recovery blocker detected.")
        self.blockers.setStyleSheet("color:#FFD21A;font-weight:700")
        label("Verified downloads do not guarantee that VR will work. Follow the Setup Guide for the remaining requirements.")
        details = "file decisions" if plan.file_decisions else "exact archive file inventories"
        self.inventory_toggle = QPushButton("Show " + details)
        self.inventory_toggle.setCheckable(True)
        layout.addWidget(self.inventory_toggle)
        self.inventory = QPlainTextEdit()
        self.inventory.setReadOnly(True)
        if plan.file_decisions:
            self.inventory.setPlainText(chr(10).join(
                f"{action}  |  {component}  |  {name}"
                for action, component, name in sorted(
                    plan.file_decisions, key=lambda row: (("Install", "Replace", "Preserve").index(row[0]), row[1], row[2]))
            ))
        else:
            self.inventory.setPlainText(chr(10).join(("INJECTOR", *plan.injector_files,
                                                       "", "PROFILE", *plan.profile.file_names)))
        if plan.verification_failed:
            self.inventory_toggle.hide()
            label("The file checks in the table identify the required versions. Download the approved release and scan again.")
        self.inventory.hide()
        layout.addWidget(self.inventory)
        self.inventory_toggle.toggled.connect(self.inventory.setVisible)
        self.inventory_toggle.toggled.connect(lambda active: self.inventory_toggle.setText(
            ("Hide " if active else "Show ") + details))
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

        if plan.verification_failed:
            return
        if install_action is not None and not disposable_rehearsal:
            self.apply_button.setToolTip("Live installation requires separate authorization.")
            self.apply_button.clicked.connect(self.run_rehearsal)
            self.apply_button.setEnabled(self.has_changes and self.install_authorized() and not plan.needs_backend_verification)
        if disposable_rehearsal:
            self.apply_button.setText("Test installation and rollback")
            self.apply_button.setToolTip("Runs only against a separate disposable prefix.")
            self.apply_button.clicked.connect(self.run_rehearsal)
        if plan.needs_backend_verification:
            self.backend.setText(plan.backend_status + " Checking the required UEVR file...")
            worker = BackendVerification(QApplication.instance())
            worker.result.connect(self.show_backend_result)
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def show_backend_result(self, asset):
        if asset is not None:
            self.verified_asset = asset
            self.apply_button.setEnabled(self.disposable_rehearsal or (self.has_changes and self.install_authorized()))
            self.backend.setText(self.plan.backend_status + " Required UEVR file verified.")
        else:
            self.backend.setText(
                "Backend verification failed. Check your connection and reopen Review installation. "
                "No installation files were changed.")


    def reject(self):
        if self.install_worker is None:
            super().reject()

    def closeEvent(self, event):
        if self.install_worker is not None:
            event.ignore()
        else:
            super().closeEvent(event)

    def run_rehearsal(self):
        if self.plan.verification_failed or self.install_worker is not None or (self.install_attempted and not self.disposable_rehearsal):
            return
        if not self.disposable_rehearsal and (not self.has_changes or not self.install_authorized()):
            return
        if self.plan.needs_backend_verification and self.verified_asset is None:
            return
        from pathlib import Path
        from .fatekeeper_rehearsal import rehearse_install

        self.apply_button.setEnabled(False)
        self.close_button.setEnabled(False)
        if self.disposable_rehearsal:
            archives = [Path(self.plan.injector_archive), Path(self.plan.profile.archive)]
            if self.install_action is not None:
                action = lambda: self.install_action(self.verified_asset)
            else:
                action = lambda: rehearse_install(archives, self.verified_asset)
            self.status.setText("Testing install and rollback in a disposable prefix...")
        else:
            action = lambda: self.install_action(self.verified_asset)
            self.install_attempted = True
            self.status.setText("Installing reviewed Fatekeeper dependencies...")
        worker = self.install_worker = InstallRehearsal(action, self)
        worker.result.connect(self.show_rehearsal_result)
        worker.finished.connect(self._finish_install)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _finish_install(self):
        self.install_worker = None
        self.close_button.setEnabled(True)
        self.apply_button.setEnabled(self.disposable_rehearsal)

    def show_rehearsal_result(self, passed):
        if self.disposable_rehearsal:
            self.status.setText(
                "Disposable installation and rollback passed. Live installation disabled." if passed else
                "Disposable installation check failed. Live installation remains disabled."
            )
        else:
            self.status.setText(
                "Reviewed Fatekeeper installation completed. Local checks will refresh when you close this review; gameplay is not verified." if passed else
                "Installation did not complete. Close this review and check recovery status before retrying."
            )
