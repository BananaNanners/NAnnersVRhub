# SPDX-License-Identifier: GPL-3.0-only
"""Read-only archive identity review. No install/extract/runner mutation API."""
from dataclasses import dataclass
from pathlib import Path
import zipfile
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from . import kharvox, download_planner as planner, archive_releases, install_review


@dataclass(frozen=True)
class Review:
    archive: str
    tags: tuple
    latest: str
    digest: str
    size: int
    files: int
    tested_archive: bool


def build_review(path, evidence, latest=""):
    path = Path(path)
    identity = planner.archive_identity(path)
    if (not identity or not isinstance(evidence, dict) or
            evidence.get("identity") != identity or evidence.get("file") != str(path) or
            not evidence.get("tags") or not archive_releases.kharvox_asset_name(path.name, local=True)):
        raise RuntimeError("Missing or stale official release evidence. Scan local archives again.")
    sha = planner._pinned_hash(planner.InventoryFile(path, identity["size"]),
                              remaining=[planner.MAX_HASH_BYTES])
    if not sha or sha != evidence.get("sha256"):
        raise RuntimeError("Archive digest changed; rescan before review.")
    install_review._zip_preflight(path)
    with zipfile.ZipFile(path) as archive:
        names = [i.filename.replace(chr(92), "/").casefold() for i in archive.infolist()
                 if not i.is_dir()]
    if not any(n.rsplit("/", 1)[-1] == "kharvoxlauncher.exe" for n in names):
        raise RuntimeError("Expected KHARVOX launcher is missing from archive.")
    if planner.archive_identity(path) != identity:
        raise RuntimeError("Archive changed during review; rescan.")
    return Review(str(path), tuple(evidence["tags"]), latest, sha,
                  identity["size"], len(names), sha == kharvox.ARCHIVE_SHA256)


class ReviewDialog(QDialog):
    def __init__(self, plan, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("KHARVOX dependency review")
        self.resize(780, 440)
        self.setObjectName("kharvoxArchiveReview")
        self.setStyleSheet("""QDialog#kharvoxArchiveReview {background:#0A0D10;}
            QLabel {color:#E5E8ED;} QPushButton {background:#14212B;color:#E5E8ED;padding:9px;}
            QPushButton:disabled {background:#151D25;color:#69717C;}""")
        layout = QVBoxLayout(self)
        def line(text, highlight=False):
            widget = QLabel(text)
            widget.setTextFormat(Qt.PlainText)
            widget.setWordWrap(True)
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if highlight:
                widget.setStyleSheet("color:#FFD21A;font-weight:700")
            layout.addWidget(widget)
            return widget
        line("KHARVOX — INSTALLATION REVIEW", True)
        line("PREVIEW ONLY — LIVE INSTALLATION DISABLED", True)
        line(f"Archive: {plan.archive}")
        line(f"Official release identity from saved scan: {', '.join(plan.tags)}")
        line(f"SHA-256 rechecked: {plan.digest}")
        line(f"Archive size: {install_review.human_file_size(plan.size)} · {plan.files} files")
        line(f"Latest upstream at scan: {plan.latest or 'Unknown'} · Tested baseline: v1.4.0")
        self.compatibility = line(
            "Matches the existing tested archive pin. Existing package and bridge checks still apply."
            if plan.tested_archive else
            "COMPATIBILITY BLOCKED: this ZIP is not the existing tested v1.4.0 archive pin.", True)
        line("KHARVOX must reside in a separate folder outside DOOM. No destination is selected, no extraction or replacement occurs, and the existing runner, bridge and installed files are unchanged. Use Setup Guide for the tested setup.")
        layout.addStretch()
        buttons = QHBoxLayout()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        buttons.addStretch()
        self.apply_button = QPushButton("Install reviewed dependencies")
        self.apply_button.setEnabled(False)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)
