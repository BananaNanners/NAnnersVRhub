# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Spreadsheet-style Qt columns for the Hub's three game/mod tables.

Drag a header separator to resize; double-click to fit text; long labels wrap.
Only explicitly resized widths are saved, in the Hub's *own* state folder.
Never reads or writes any installed game, Steam or Heroic configuration.
"""
import fcntl
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, QTimer, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView

from . import hub, self_install

_SCHEMA = 1
_KEYS = frozenset({"game-library", "guided-downloads", "mod-updates"})
_MAX_SETTINGS_BYTES = 16 * 1024


def preferences_file() -> Path:
    return hub.state_file().parent / "table-column-layouts.json"


def _valid_widths(value, count):
    if (not isinstance(value, list) or len(value) != count or
            any(type(n) is not int or n < 76 or n > 2400 for n in value)):
        return None
    return list(value)


def _read_preferences() -> dict:
    path = preferences_file()
    if not path.exists() and not path.is_symlink():
        return {"schema": _SCHEMA, "tables": {}}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_SETTINGS_BYTES:
        raise ValueError("Existing column preferences are invalid; they were preserved.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("Existing column preferences cannot be read; they were preserved.") from exc
    if (not isinstance(data, dict) or set(data) != {"schema", "tables"} or
            data["schema"] != _SCHEMA or not isinstance(data["tables"], dict)):
        raise ValueError("Existing column preferences need review; they were preserved.")
    for key, value in data["tables"].items():
        if key not in _KEYS or _valid_widths(value, 5) is None:
            raise ValueError("Existing column preferences contain invalid widths; they were preserved.")
    return data


def load_widths(key, count):
    if key not in _KEYS:
        raise ValueError("Unknown table layout")
    try:
        return _valid_widths(_read_preferences()["tables"].get(key), count)
    except (ValueError, OSError):
        return None  # never crash a GUI because of bad display preferences


def save_widths(key, widths):
    if key not in _KEYS:
        raise ValueError("Unknown table layout")
    if _valid_widths(widths, 5) is None:
        raise ValueError("Invalid column widths")
    path = preferences_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _read_preferences()  # reject invalid file rather than silently replacing it
        data["tables"][key] = list(widths)
        self_install._atomic(path, (json.dumps(data, indent=2) + "\n").encode("utf-8"))


class SpreadsheetColumns(QObject):
    """Attaches familiar spreadsheet column controls to a QTableWidget."""

    def __init__(self, table, key, initial_widths, *, min_row_height=32,
                 expand_weights=None, fixed_table_height=False):
        super().__init__(table)
        if key not in _KEYS or len(initial_widths) != table.columnCount():
            raise ValueError("Unknown table or wrong number of columns")
        self.table = table
        self.key = key
        self.initial_widths = tuple(initial_widths)
        self.min_row_height = min_row_height
        self.fixed_table_height = fixed_table_height
        self.expand_weights = (tuple(expand_weights) if expand_weights
                               else tuple(1 for _ in initial_widths))
        self._applying = False
        self._needs_first_show = True
        self._stored = load_widths(key, table.columnCount())
        self._row_timer = QTimer(self)
        self._row_timer.setSingleShot(True)
        self._row_timer.timeout.connect(self.reflow_rows)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self._save_now)
        # Parent this deferred first-show callback to the table controller.
        # A bare singleShot bound-method can outlive its deleted QTableWidget.
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._first_visible)

        table.setWordWrap(True)
        table.setTextElideMode(Qt.ElideRight)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(76)
        header.setSectionsClickable(False)
        header.setSectionsMovable(False)
        header.setHighlightSections(False)
        for index in range(table.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.Interactive)
        self._apply(self._stored or self.initial_widths)
        header.sectionResized.connect(self._on_resize)
        header.sectionHandleDoubleClicked.connect(self._fit_column)
        table.installEventFilter(self)
        table.setToolTip("Drag a column separator to resize. Double-click to fit text.")
        if self._stored:
            self._needs_first_show = False

    def eventFilter(self, source, event):
        if source is self.table and event.type() == QEvent.Show:
            if self._needs_first_show:
                if not self._show_timer.isActive():
                    self._show_timer.start(0)
            self.schedule_rows()
        return super().eventFilter(source, event)

    def _first_visible(self):
        if not self._needs_first_show:
            return
        self._needs_first_show = False
        usable = self.table.viewport().width()
        minimum = sum(self.initial_widths)
        if usable > minimum:
            extra = usable - minimum
            weights = self.expand_weights
            total = max(1, sum(weights))
            sizes = list(self.initial_widths)
            distributed = 0
            for i, weight in enumerate(weights):
                gain = extra * weight // total
                sizes[i] += gain
                distributed += gain
            sizes[0] += extra - distributed
            self._apply(sizes)
        self.schedule_rows()

    def _apply(self, widths):
        self._applying = True
        try:
            for index, width in enumerate(widths):
                self.table.setColumnWidth(index, width)
        finally:
            self._applying = False

    def _on_resize(self, index, old, new):
        if self._applying or old == new:
            return
        if self._needs_first_show:
            # Qt may resize header sections while laying out a hidden tab.
            # Do not mistake that for a user's drag, save it, or cancel the
            # first-visible proportional fill.
            return
        self._save_timer.start()
        self.schedule_rows()

    def _fit_column(self, index):
        # Qt's built-in double-click fit can make a long archive filename
        # thousands of pixels wide. Keep autofit useful but bounded; users
        # can drag it wider if desired.
        self.table.resizeColumnToContents(index)
        size = self.table.columnWidth(index)
        size = max(88, min(720, size + 12))
        self.table.setColumnWidth(index, size)
        self.schedule_rows()

    def schedule_rows(self):
        if not self._row_timer.isActive():
            self._row_timer.start(0)

    def reflow_rows(self):
        table = self.table
        if table.rowCount() > 0:
            table.resizeRowsToContents()
            for index in range(table.rowCount()):
                height = max(self.min_row_height, min(140, table.rowHeight(index)))
                table.setRowHeight(index, height)
        if self.fixed_table_height:
            target = (table.horizontalHeader().height() +
                      sum(table.rowHeight(i) for i in range(table.rowCount())) + 4)
            table.setFixedHeight(max(table.horizontalHeader().height() + 4, target))

    def _save_now(self):
        widths = [self.table.columnWidth(i) for i in range(self.table.columnCount())]
        try:
            save_widths(self.key, widths)
        except (ValueError, OSError):
            # Display preferences must never interfere with an install check.
            self.table.setToolTip(
                "You can resize columns, but existing layout preferences could not be saved.")

    def flush(self):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_now()


def enable_spreadsheet_columns(table, key, widths, **kwargs):
    controller = SpreadsheetColumns(table, key, widths, **kwargs)
    table.spreadsheet_columns = controller
    return controller
