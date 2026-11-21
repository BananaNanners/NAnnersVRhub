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


def archive_table(rows, parent=None):
    """Display archive, dependency and evidence without granting authority."""
    table = QTableWidget(len(rows), 3, parent)
    table.setObjectName("installReviewArchives")
    table.setHorizontalHeaderLabels(("Selected archive", "Dependency", "Review evidence"))
    table.verticalHeader().hide()
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
    for i, (path, name, digest) in enumerate(rows):
        archive = QTableWidgetItem(Path(path).name)
        archive.setToolTip(path)
        table.setItem(i, 0, archive)
        dependency = QTableWidgetItem(name)
        dependency.setToolTip(name)
        table.setItem(i, 1, dependency)
        evidence = QTableWidgetItem("Review SHA-256 recorded" if digest else "Not recorded")
        if digest:
            evidence.setToolTip("Exact archive SHA-256: " + digest
                                + "\nA review digest alone is not pinned verification.")
        table.setItem(i, 2, evidence)
    table.setMinimumHeight(95)
    table.setMaximumHeight(min(180, 42 + 34 * max(1, len(rows))))
    return table


def review_archive_table(plan, parent=None, *, recipe=None):
    """Map archive to dependency using the same recipe identifiers as the planner.

    Package labels may be in recipe order while archives are in selection order.
    Never guess a mapping from index or from a mere filename for pinned packages.
    """
    from . import hub
    rows = []
    for i, path in enumerate(plan.archives):
        digest = plan.archive_sha256[i] if i < len(plan.archive_sha256) else ""
        name = None
        if recipe and recipe.get("id") == plan.game_id:
            if plan.method in ("bepinex", "ervr"):
                matches = [p["name"] for p in recipe.get("packages", [])
                           if digest and p.get("sha256", "").lower() == digest.lower()]
                if len(matches) == 1:
                    name = matches[0]
            elif plan.method == "gameroot":
                comp = hub._component_for(recipe, Path(path).name)
                if comp:
                    name = comp["name"]
        if name not in plan.package_labels:
            name = (plan.package_labels[0] if len(plan.archives) == len(plan.package_labels) == 1
                    else "See package summary")
        rows.append((path, name, digest))
    return archive_table(rows, parent)
