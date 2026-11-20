# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Launcher-style presentation widgets. No installation or runtime side effects.

Dev1 keeps the existing game table as the authoritative GUI selection source;
the game list here is a synchronized navigation view, not a second model.
"""
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QColor, QFont, QPen, QPainter, QPixmap, QLinearGradient, QBrush
from PySide6.QtWidgets import (QFrame, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QStyledItemDelegate, QStyle)

from .theme import GREEN, MUTED, TEXT, YELLOW


SHORT_GAME_NAMES = {
    "cyberpunk-2077": "Cyberpunk 2077",
    "doom-2016-gog": "DOOM (2016)",
    "elden-ring": "Elden Ring",
    "fatekeeper": "Fatekeeper",
    "hogwarts-legacy": "Hogwarts Legacy",
    "ready-or-not": "Ready or Not",
    "skyrim-vr-mgo": "Skyrim VR",
    "subnautica": "Subnautica",
    "valheim": "Valheim",
}


def display_game_name(recipe):
    """Present known game names compactly without altering recipe identity."""
    return SHORT_GAME_NAMES.get(recipe["id"], recipe["name"])


class GameLibraryItemDelegate(QStyledItemDelegate):
    """Readable two-line game rows with a visible selection and neutral status.

    The second line is deliberately "Game detected", not "VR ready":
    detecting an installed game never certifies its headset behavior.
    """

    def sizeHint(self, option, index):
        return QSize(185, 65)

    def paint(self, painter, option, index):
        painter.save()
        try:
            rect = option.rect.adjusted(3, 1, -4, -1)
            selected = bool(option.state & QStyle.State_Selected)
            hovered = bool(option.state & QStyle.State_MouseOver)
            if selected:
                painter.setPen(QPen(QColor(YELLOW), 1))
                painter.setBrush(QColor("#342B0B"))
                painter.drawRoundedRect(rect, 7, 7)
            elif hovered:
                painter.setPen(QPen(QColor("#39414A"), 1))
                painter.setBrush(QColor("#1B2026"))
                painter.drawRoundedRect(rect, 7, 7)

            title = index.data(Qt.UserRole) or index.data(Qt.DisplayRole) or ""
            detected = bool(index.data(Qt.UserRole + 1))
            base = option.font
            heading = QFont(base)
            heading.setPixelSize(15)
            heading.setWeight(QFont.DemiBold)
            subtitle = QFont(base)
            subtitle.setPixelSize(12)
            subtitle.setWeight(QFont.Normal)

            x = rect.x() + 13
            width = max(0, rect.width() - 22)
            painter.setFont(heading)
            painter.setPen(QColor(YELLOW if selected else TEXT if detected else MUTED))
            painter.drawText(QRect(x, rect.y() + 8, width, 26),
                             Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, str(title))
            painter.setFont(subtitle)
            painter.setPen(QColor(GREEN if detected else MUTED))
            painter.drawText(QRect(x, rect.y() + 36, width, 20),
                             Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
                             "Game detected" if detected else "Not detected")
        finally:
            painter.restore()


class LauncherSidebar(QFrame):
    page_selected = Signal(int)
    game_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("launcherSidebar")
        self.setMinimumWidth(235)
        self.setMaximumWidth(315)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(9)

        title = QLabel("GAME LIBRARY")
        title.setObjectName("launcherSideTitle")
        layout.addWidget(title)
        subtitle = QLabel("Select a game or check your VR setup.")
        subtitle.setObjectName("launcherSideHint")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.games_button = QPushButton("  Games")
        self.games_button.setObjectName("launcherNavButton")
        self.games_button.setCheckable(True)
        self.games_button.clicked.connect(lambda: self.page_selected.emit(1))
        layout.addWidget(self.games_button)

        self.game_list = QListWidget()
        self.game_list.setObjectName("launcherGameList")
        self.game_list.setSpacing(4)
        self.game_list.setItemDelegate(GameLibraryItemDelegate(self.game_list))
        self.game_list.setSelectionMode(QListWidget.SingleSelection)
        self.game_list.currentRowChanged.connect(self._game_chosen)
        layout.addWidget(self.game_list, 1)

        self.system_button = QPushButton("  VR System")
        self.system_button.setObjectName("launcherNavButton")
        self.system_button.setCheckable(True)
        self.system_button.clicked.connect(lambda: self.page_selected.emit(0))
        layout.addWidget(self.system_button)

        # Keep most of the sidebar available for the nine real game profiles.
        # Planned pages remain discoverable without consuming navigation space.
        self.future_toggle = QPushButton("  Future sections  ▸")
        self.future_toggle.setObjectName("launcherFutureToggle")
        self.future_toggle.setCheckable(True)
        layout.addWidget(self.future_toggle)
        self.future_panel = QFrame()
        future_layout = QVBoxLayout(self.future_panel)
        future_layout.setContentsMargins(0, 0, 0, 0)
        future_layout.setSpacing(4)
        self.planned_buttons = {}
        for name, phase in (
            ("Downloads", "Dev4"),
            ("Backups", "Dev5"),
            ("Settings", "later milestone"),
            ("Logs", "later milestone"),
        ):
            button = QPushButton("  " + name)
            button.setObjectName("launcherNavPlanned")
            button.setEnabled(False)
            button.setToolTip(name + " navigation is planned for " + phase +
                              "; existing tools remain accessible under each game.")
            future_layout.addWidget(button)
            self.planned_buttons[name] = button
        self.future_panel.hide()
        layout.addWidget(self.future_panel)
        self.future_toggle.toggled.connect(self._set_future_visible)

        footer = QLabel("🍌  NAnnersVRhub  •  Linux VR")
        footer.setObjectName("launcherSideHint")
        layout.addWidget(footer)
        self.set_page(1)

    def _set_future_visible(self, expanded):
        self.future_panel.setVisible(bool(expanded))
        self.future_toggle.setText(
            "  Hide future sections  ▾" if expanded else "  Future sections  ▸")

    def _game_chosen(self, index):
        if index >= 0:
            self.game_selected.emit(index)

    def set_page(self, index):
        self.games_button.setChecked(index == 1)
        self.system_button.setChecked(index == 0)

    def set_games(self, rows, selected):
        self.game_list.blockSignals(True)
        try:
            self.game_list.clear()
            for row in rows:
                name = display_game_name(row["recipe"])
                status = "Game detected" if row["game_found"] else "Not detected"
                item = QListWidgetItem(f"{name}\n{status}")
                item.setToolTip(row["recipe"]["name"])
                item.setSizeHint(QSize(185, 65))
                item.setData(Qt.UserRole, name)
                item.setData(Qt.UserRole + 1, bool(row["game_found"]))
                self.game_list.addItem(item)
            if rows:
                self.game_list.setCurrentRow(min(max(0, selected), len(rows) - 1))
        finally:
            self.game_list.blockSignals(False)

    def select_game(self, index):
        if 0 <= index < self.game_list.count() and self.game_list.currentRow() != index:
            self.game_list.blockSignals(True)
            try:
                self.game_list.setCurrentRow(index)
            finally:
                self.game_list.blockSignals(False)


class GameBanner(QFrame):
    """Accurate, deliberately non-gameplay-verifying game header for Dev1."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("launcherGameBanner")
        self._local_art = QPixmap()
        self.setMinimumHeight(148)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 14)
        layout.setSpacing(6)
        self.caption = QLabel("NANNERSVRHUB  /  GAME PROFILE")
        self.caption.setObjectName("launcherBannerCaption")
        layout.addWidget(self.caption)
        self.heading = QLabel("Choose a game")
        self.heading.setObjectName("launcherGameTitle")
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.status = QLabel("Only verified installation and runtime facts are shown.")
        self.status.setObjectName("launcherBannerStatus")
        self.status.setWordWrap(True)
        self.status.setMaximumWidth(630)
        layout.addWidget(self.status)
        layout.addStretch(1)

    def paintEvent(self, event):
        super().paintEvent(event)
        # Local Steam art is optional, never downloaded or redistributed.
        # Without it, paint an original neutral sci-fi texture using brand hues.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        right = int(self.width() * 0.58)
        area = QRect(right, 1, self.width() - right - 1, self.height() - 2)
        painter.setClipRect(area)
        if not self._local_art.isNull():
            art = self._local_art.scaled(
                area.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            crop = QRect(max(0, (art.width() - area.width()) // 2),
                         max(0, (art.height() - area.height()) // 2),
                         area.width(), area.height())
            painter.drawPixmap(area, art, crop)
        else:
            painter.fillRect(area, QColor("#10232E"))
            for pos in range(-60, area.width() + 120, 57):
                x = area.x() + pos
                painter.setPen(QPen(QColor(35, 183, 255, 65), 1))
                painter.drawLine(x, 0, x + 120, area.height())
            painter.setPen(QPen(QColor(255, 210, 26, 140), 3))
            painter.drawLine(area.x() + area.width() * 2 // 3, 10,
                             area.x() + area.width() // 3, area.height() - 8)
        fade = QLinearGradient(area.x(), 0, self.width(), 0)
        fade.setColorAt(0, QColor(16, 20, 23, 255))
        fade.setColorAt(0.43, QColor(12, 18, 22, 92))
        fade.setColorAt(1, QColor(10, 13, 16, 25))
        painter.fillRect(area, QBrush(fade))
        painter.end()

    def _find_local_art(self, recipe):
        """Use only user-cached Steam library hero images, with a safe fallback."""
        appid = recipe.get("steam_appid")
        if not isinstance(appid, int):
            return QPixmap()
        cache = Path.home() / ".local/share/Steam/appcache/librarycache" / str(appid)
        for name in ("library_hero.jpg", "library_hero.png"):
            path = cache / name
            if path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return pixmap
        return QPixmap()

    def set_game(self, row, update_items=None):
        if row is None:
            self._local_art = QPixmap()
            self.heading.setText("Choose a game")
            self.status.setText("Select a profile from the game library.")
            self.update()
            return
        recipe = row["recipe"]
        self._local_art = self._find_local_art(recipe)
        self.heading.setText(display_game_name(recipe))
        self.update()
        store = {
            "steam": "Steam",
            "heroic-epic": "Heroic / Epic",
            "heroic-gog": "Heroic / GOG",
        }.get(recipe.get("store", "steam"), "Game")
        found = "Game detected" if row["game_found"] else "Game not detected"
        details = [f"{found} ({store})"]
        mods = row.get("components")
        if mods:
            details.append(f"{mods[0]} / {mods[1]} tracked mods installed")
        else:
            details.append("Guided VR setup")
        if update_items:
            pending = sum(item.get("status") == "update" for item in update_items)
            details.append(f"{pending} mod update(s) reported")
        self.status.setText("   •   ".join(details))
