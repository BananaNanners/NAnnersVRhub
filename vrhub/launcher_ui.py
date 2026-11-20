# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Launcher-style presentation widgets. No installation or runtime side effects.

Dev1 keeps the existing game table as the authoritative GUI selection source;
the game list here is a synchronized navigation view, not a second model.
"""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (QFrame, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QHBoxLayout)

from .theme import BLUE, GREEN, MUTED, RED, TEXT, YELLOW


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


class LauncherSidebar(QFrame):
    page_selected = Signal(int)
    game_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("launcherSidebar")
        self.setMinimumWidth(205)
        self.setMaximumWidth(290)

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
        self.game_list.setSpacing(3)
        self.game_list.setSelectionMode(QListWidget.SingleSelection)
        self.game_list.currentRowChanged.connect(self._game_chosen)
        layout.addWidget(self.game_list, 1)

        self.system_button = QPushButton("  VR System")
        self.system_button.setObjectName("launcherNavButton")
        self.system_button.setCheckable(True)
        self.system_button.clicked.connect(lambda: self.page_selected.emit(0))
        layout.addWidget(self.system_button)

        upcoming = QLabel("COMING IN LATER MILESTONES")
        upcoming.setObjectName("launcherSideHint")
        upcoming.setWordWrap(True)
        layout.addWidget(upcoming)
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
            layout.addWidget(button)
            self.planned_buttons[name] = button

        footer = QLabel("🍌  NAnnersVRhub  •  Linux VR")
        footer.setObjectName("launcherSideHint")
        layout.addWidget(footer)
        self.set_page(1)

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
                item.setSizeHint(QSize(175, 49))
                if not row["game_found"]:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(MUTED))
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(5)
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
        layout.addWidget(self.status)

    def set_game(self, row, update_items=None):
        if row is None:
            self.heading.setText("Choose a game")
            self.status.setText("Select a profile from the game library.")
            return
        recipe = row["recipe"]
        self.heading.setText(display_game_name(recipe))
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
