# SPDX-License-Identifier: GPL-3.0-only
"""Archive-first presentation helpers. No verification or install authority."""
from pathlib import Path

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


def status_icon(status):
    """Only an exact pinned-hash result earns a green checkmark."""
    verified = status == "Pinned SHA-256 verified"
    review = status == "Possible archive — inspect first"
    blocked = status in {
        "Hash mismatch — do not install", "Hash not verified — do not install",
        "Archive changed — rescan required",
    }
    color = "#4FE39A" if verified else "#FFD21A" if review else "#FF5B50" if blocked else "#A7ADB7"
    pix = QPixmap(20, 20)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(10, 10), 8, 8)
        if verified:
            painter.drawLine(QPointF(6, 10), QPointF(9, 13))
            painter.drawLine(QPointF(9, 13), QPointF(14, 7))
        elif review or blocked:
            painter.drawLine(QPointF(10, 5), QPointF(10, 10))
            painter.drawPoint(QPointF(10, 14))
        else:
            painter.drawLine(QPointF(6, 10), QPointF(14, 10))
    finally:
        painter.end()
    return QIcon(pix)


def review_archive_table(plan, parent=None):
    """Show exact archive names and recorded digests, never infer pinned trust.

    Package labels may be sorted by recipe order while paths retain selection
    order. Do not pair them by index; the original summary lists packages.
    """
    table = QTableWidget(len(plan.archives), 2, parent)
    table.setObjectName("installReviewArchives")
    table.setHorizontalHeaderLabels(("Selected archive", "Review evidence"))
    table.verticalHeader().hide()
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    for i, path in enumerate(plan.archives):
        archive = QTableWidgetItem(Path(path).name)
        archive.setToolTip(path)
        table.setItem(i, 0, archive)
        evidence = QTableWidgetItem("Review SHA-256 recorded")
        if i < len(plan.archive_sha256):
            evidence.setToolTip("Exact archive SHA-256: " + plan.archive_sha256[i]
                                + "\nA review digest alone is not pinned verification.")
        table.setItem(i, 1, evidence)
    table.setMinimumHeight(95)
    table.setMaximumHeight(min(180, 42 + 34 * max(1, len(plan.archives))))
    return table
