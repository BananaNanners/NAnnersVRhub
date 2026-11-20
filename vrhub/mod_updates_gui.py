# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev3: read-only native mod-update page for every game profile.

It displays the existing update worker's results. No mod installation,
download, deletion, archive movement or background network work occurs here.
"""
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QUrl

from .table_columns import enable_spreadsheet_columns


GROUPS = ("update", "review", "later", "not_installed", "current")
GROUP_TITLES = {
    "update": "Updates available",
    "review": "Needs review",
    "later": "Install later",
    "not_installed": "Not installed",
    "current": "Up to date",
}
STATUS_LABELS = {
    "update": "Update available",
    "current": "Current",
    "unknown": "Review version",
    "error": "Check failed",
    "manual": "Check manually",
    "no_key": "Nexus key needed",
    "not_installed": "Not installed",
}
COLUMN_TITLES = ("Mod", "Installed", "Latest", "Status", "Source")


def grouped_updates(recipe, items):
    """Categorize update results without assuming an unknown version is safe."""
    groups = {key: [] for key in GROUPS}
    phase2 = {int(c["nexus_mod"]) for c in (recipe or {}).get("components", [])
              if c.get("phase", 1) != 1}
    for raw in items or []:
        status = raw.get("status", "unknown")
        if status == "update":
            group = "update"
        elif status == "current":
            group = "current"
        elif status == "not_installed":
            group = "later" if raw.get("mod_id") in phase2 else "not_installed"
        else:
            group = "review"
        record = {
            "name": str(raw.get("name") or "Unnamed mod"),
            "installed": str(raw.get("installed_version") or "—"),
            "latest": str(raw.get("latest_version") or "—"),
            "status": ("Install later" if group == "later" else
                       "Rate limited" if status == "error" and "rate limit" in
                       str(raw.get("detail", "")).lower() else
                       STATUS_LABELS.get(status, "Review")),
            "tone": group,
            "detail": str(raw.get("detail") or "No version details provided."),
            "page": str(raw.get("page") or ""),
            "mod_id": raw.get("mod_id"),
        }
        groups[group].append(record)
    return groups


def safe_source_url(value):
    """Only explicitly opened HTTPS source pages, never shell commands."""
    if not isinstance(value, str):
        return ""
    url = urlparse(value)
    if url.scheme.lower() != "https" or not url.hostname or url.username or url.password:
        return ""
    return value


class UpdateTable(QTableWidget):
    """Compact table with versions, status details and one source button per row."""
    def __init__(self, parent=None):
        super().__init__(0, len(COLUMN_TITLES), parent)
        self.setObjectName("modUpdatesTable")
        self.setHorizontalHeaderLabels(COLUMN_TITLES)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setWordWrap(True)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.columns = enable_spreadsheet_columns(
            self, "mod-updates", (295, 120, 120, 185, 137),
            expand_weights=(3, 1, 1, 2, 0), min_row_height=44,
            fixed_table_height=True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setMinimumWidth(0)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(self.horizontalHeader().height() + 4)

    def set_records(self, rows):
        # A previous game's external-link widgets can otherwise survive in
        # QTableWidget's viewport at their old coordinates during a reflow.
        # Clear previous cell widgets *before* reusing rows for another game.
        self.setRowCount(0)
        self.setRowCount(len(rows))
        for idx, record in enumerate(rows):
            self.setRowHeight(idx, 52 if len(record["name"]) > 31 else 44)
            for col, field in enumerate(("name", "installed", "latest", "status")):
                value = record[field]
                if col == 3:
                    symbol = {"update": "↑", "current": "✓", "review": "!",
                              "later": "◷", "not_installed": "–"}.get(
                                  record.get("tone"), "!")
                    value = f"{symbol}  {value}"
                cell = QTableWidgetItem(value)
                cell.setToolTip(record['name'] + chr(10) + record['detail'])
                if col in (1, 2, 3):
                    cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if col == 3:
                    tone = record.get("tone")
                    cell.setForeground(QColor({
                        "update": "#FFD21A", "current": "#4FE39A",
                        "review": "#FFD21A", "later": "#A7ADB7",
                        "not_installed": "#A7ADB7",
                    }.get(tone, "#F5F2DE")))
                    face = QFont(cell.font())
                    face.setWeight(QFont.DemiBold)
                    cell.setFont(face)
                self.setItem(idx, col, cell)
            link = safe_source_url(record["page"])
            if link:
                button = QPushButton("Open source")
                button.setObjectName("modSourceButton")
                button.setToolTip(f"Open external source page: {link}")
                button.clicked.connect(lambda _checked=False, uri=link:
                                       QDesktopServices.openUrl(QUrl(uri)))
                self.setCellWidget(idx, 4, button)
            else:
                self.setItem(idx, 4, QTableWidgetItem("—"))
        height = (self.horizontalHeader().height()
                  + sum(self.rowHeight(i) for i in range(self.rowCount())) + 4)
        self.setFixedHeight(max(self.horizontalHeader().height() + 4, height))
        self.columns.schedule_rows()


class UpdateSection(QWidget):
    """One table with a heading; Current is collapsed by default."""
    def __init__(self, group_key, *, collapsed=False, parent=None):
        super().__init__(parent)
        self.setObjectName("modUpdatesSection")
        self.group_key = group_key
        self.collapsed = bool(collapsed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.disclosure = QToolButton()
        self.disclosure.setObjectName("modUpdatesDisclosure")
        self.disclosure.setProperty("group", group_key)
        self.disclosure.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.disclosure.setCheckable(True)
        self.disclosure.setChecked(not self.collapsed)
        self.disclosure.clicked.connect(self._toggle)
        layout.addWidget(self.disclosure, 0, Qt.AlignLeft)
        self.table = UpdateTable()
        layout.addWidget(self.table)
        if collapsed:
            self.table.hide()
        self.set_records([])

    def _toggle(self, enabled):
        self.table.setVisible(bool(enabled))
        self._update_heading()

    def _update_heading(self):
        arrow = "▾" if self.disclosure.isChecked() else "▸"
        self.disclosure.setText(
            f"{arrow}  {GROUP_TITLES[self.group_key]} ({self.table.rowCount()})")

    def set_records(self, rows):
        self.table.set_records(rows)
        self.setVisible(bool(rows))
        self._update_heading()


class ModUpdatesPage(QWidget):
    """One native updates page, refreshed on game selection or check completion."""
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("modUpdatesPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 9, 9, 9)
        root.setSpacing(8)

        self.heading = QLabel("MOD UPDATES")
        self.heading.setObjectName("modUpdatesHeading")
        root.addWidget(self.heading)

        top = QHBoxLayout()
        self.explanation = QLabel(
            "Read-only version check. Refreshing does not download, install, "
            "remove or automatically mark mods as updated. Recent GitHub "
            "results may be reused for 15 minutes to avoid rate limits.")
        self.explanation.setObjectName("modUpdatesExplanation")
        self.explanation.setWordWrap(True)
        top.addWidget(self.explanation, 1)
        self.refresh_button = QPushButton("Refresh update status")
        self.refresh_button.setObjectName("modUpdatesRefresh")
        self.refresh_button.clicked.connect(lambda _checked=False:
                                            self.refresh_requested.emit())
        top.addWidget(self.refresh_button)
        root.addLayout(top)

        self.summary = QLabel("Select a game to see tracked mod updates.")
        self.summary.setObjectName("modUpdatesSummary")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.github_notice = QLabel()
        self.github_notice.setObjectName("modUpdatesRateLimitNotice")
        self.github_notice.setWordWrap(True)
        self.github_notice.hide()
        root.addWidget(self.github_notice)

        self.area = QScrollArea()
        self.area.setObjectName("modUpdatesScroll")
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root.addWidget(self.area, 1)
        content = QWidget()
        content.setObjectName("modUpdatesContent")
        self.area.setWidget(content)
        inner = QVBoxLayout(content)
        inner.setContentsMargins(0, 0, 3, 0)
        inner.setSpacing(12)

        self.sections = {}
        for name in GROUPS:
            section = UpdateSection(name, collapsed=(name == "current"))
            self.sections[name] = section
            inner.addWidget(section)
        self.empty = QLabel("No results yet. Refresh update status to check.")
        self.empty.setObjectName("modUpdatesEmpty")
        self.empty.setWordWrap(True)
        inner.addWidget(self.empty)
        inner.addStretch(1)
        self._last_id = None
        self.set_recipe(None, None)

    def set_checking(self, checking):
        self.refresh_button.setEnabled(not checking)
        self.refresh_button.setText("Checking…" if checking else "Refresh update status")

    def set_recipe(self, recipe, items):
        recipe_id = recipe.get("id") if recipe else None
        if recipe_id != self._last_id:
            self._last_id = recipe_id
            # Preserve a user's expansion within one game, but start each
            # newly selected game's current-mod section collapsed.
            current = self.sections["current"]
            current.disclosure.setChecked(False)
            current.table.hide()
        grouping = grouped_updates(recipe, items)
        total = sum(len(rows) for rows in grouping.values())
        self.empty.setVisible(not total)
        if not recipe:
            self.summary.setText("Select a game to see tracked mod updates.")
        elif not items:
            self.summary.setText(
                f"{recipe['name']}: no update results yet. Use Refresh update status.")
        else:
            review = len(grouping["review"])
            pending = len(grouping["update"])
            current = len(grouping["current"])
            later = len(grouping["later"])
            missing = len(grouping["not_installed"])
            self.summary.setText(
                f"{pending} updates available  •  {current} up to date  •  "
                f"{review} need review  •  {later} install later  •  "
                f"{missing} not installed")
        github_limited = sum(
            raw.get("status") == "error" and
            "GitHub" in str(raw.get("detail", "")) and
            "rate limit" in str(raw.get("detail", "")).lower()
            for raw in items or [])
        self.github_notice.setVisible(github_limited > 0)
        if github_limited:
            self.github_notice.setText(
                f"GitHub API rate limit reached: {github_limited} release "
                "check(s) couldn't finish. This is a temporary online lookup "
                "limit, not a failed mod installation. Try again after the "
                "quota resets; no mod files were changed.")
        else:
            self.github_notice.clear()
        for name, section in self.sections.items():
            section.set_records(grouping[name])
        return grouping
