# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only factual game overview cards for the 0.5.5 Dev2 launcher."""
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget
from .updates import release_count

STORE_NAMES = {"steam": "Steam", "heroic-epic": "Heroic / Epic", "heroic-gog": "Heroic / GOG"}
UPDATES = ("update", "current", "unknown", "error", "no_key", "manual", "not_installed")


def snapshot(row, update_items=None, verification=None, preflight=None):
    """Form a four-card presentation from verified Hub data only.

    Game detection, installed files, preflight, and VR gameplay have distinct
    meanings. A card is not proof of headset or controller operation.
    """
    if row is None:
        return {
            "game": ("Game install", "Choose a game", "Select a game from the library.", "neutral"),
            "mods": ("Mod setup", "Not checked", "Select a game for installed component status.", "neutral"),
            "updates": ("Updates", "Not checked", "Refresh available dependency versions.", "neutral"),
            "vr": ("VR preflight", "Not run", "Use Preflight to test local prerequisites.", "neutral"),
        }
    recipe = row["recipe"]
    store = STORE_NAMES.get(recipe.get("store", "steam"), "Configured store")
    game = (("Game install", "Game detected", f"Found through {store}. Not a gameplay test.", "success")
            if row["game_found"] else
            ("Game install", "Not detected", f"No installation found through {store}.", "warning"))

    if verification is not None and "rows" in verification:
        total = verification.get("total", 0)
        installed = verification.get("ok", 0)
        required = verification.get("required_bad", [])
        later = verification.get("later_bad", [])
        if required:
            note, state = f"{len(required)} required component(s) need attention.", "warning"
        elif later:
            note, state = f"Required mods verified; {len(later)} later-stage item(s) pending.", "neutral"
        else:
            note, state = "Tracked files verified on disk; VR gameplay not tested.", "success"
        mods = ("Mod setup", f"{installed} / {total} installed", note, state)
    elif row.get("components"):
        installed, total, ready = row["components"]
        mods = ("Mod setup", f"{installed} / {total} installed",
                "Required mods verified." if ready else "Required components need attention.",
                "success" if ready else "warning")
    elif row.get("has_profile"):
        installed = bool(row.get("profile_installed"))
        mods = ("Mod profile", "Installed" if installed else "Not installed",
                "Profile recorded, not a live VR test." if installed else "Consult the setup guide.",
                "success" if installed else "neutral")
    else:
        mods = ("Mod setup", "Installed" if row.get("mod_installed") else "Guided setup",
                "Use the setup guide to verify the required files.", "neutral")

    if update_items is None or not update_items:
        updates = ("Updates", "Not checked",
                   "Refresh update status to query available versions.", "neutral")
    else:
        counts = {name: sum(i.get("status") == name for i in update_items) for name in UPDATES}
        uncertain = sum(counts[s] for s in ("unknown", "error", "no_key", "manual"))
        pending = release_count(update_items)
        if pending:
            label = "new release" if pending > counts["update"] else "update"
            title, tone = f"{pending} {label}" + ("" if pending == 1 else "s"), "warning"
        elif uncertain:
            title, tone = "Needs review", "warning"
        elif counts["not_installed"]:
            title, tone = "Install pending", "neutral"
        else:
            title, tone = "No newer versions reported", "success"
        detail = (f"{counts['current']} current  •  {uncertain} need review"
                  f"  •  {counts['not_installed']} not installed")
        updates = ("Updates", title, detail, tone)

    if preflight is None:
        vr = ("VR preflight", "Not run",
              "Run Preflight to check local requirements.", "neutral")
    else:
        bad = [i for i in preflight.get("rows", [])
               if i.get("required", True) and not i.get("ok", False)]
        if bad:
            vr = ("VR preflight", "Needs attention",
                  f"{len(bad)} local check(s) failed; gameplay unverified.", "warning")
        elif preflight.get("ready"):
            vr = ("VR preflight", "Local checks passed",
                  "Current session only. Headset rendering not verified.", "success")
        else:
            vr = ("VR preflight", "Needs review",
                  "See the preflight report. Gameplay unverified.", "warning")
    return {"game": game, "mods": mods, "updates": updates, "vr": vr}


class StatusCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 11, 15, 10)
        layout.setSpacing(4)
        self.heading = QLabel()
        self.heading.setObjectName("dashboardCardHeading")
        self.value = QLabel()
        self.value.setObjectName("dashboardCardValue")
        self.value.setWordWrap(True)
        self.detail = QLabel()
        self.detail.setObjectName("dashboardCardDetail")
        self.detail.setWordWrap(True)
        layout.addWidget(self.heading)
        layout.addWidget(self.value)
        layout.addWidget(self.detail, 1)
        self.setMinimumHeight(125)

    def set_card(self, data):
        title, value, detail, tone = data
        self.heading.setText(title)
        self.value.setText(value)
        self.detail.setText(detail)
        self.setProperty("tone", tone)
        self.value.setProperty("tone", tone)
        for widget in (self, self.value):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class GameDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameDashboard")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(9)
        layout.setVerticalSpacing(8)
        self.cards = {}
        self._columns = 4
        for i, key in enumerate(("game", "mods", "updates", "vr")):
            card = StatusCard()
            self.cards[key] = card
            layout.addWidget(card, 0, i)
            layout.setColumnStretch(i, 1)
        self.set_snapshot(snapshot(None))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # At narrower window sizes, show two readable cards per row instead
        # of squeezing four long status strings side-by-side. The parent
        # QScrollArea handles the additional vertical height.
        columns = 2 if self.width() < 980 else 4
        if columns != self._columns:
            self._columns = columns
            grid = self.layout()
            for i, key in enumerate(("game", "mods", "updates", "vr")):
                grid.addWidget(self.cards[key], i // columns, i % columns)
            for i in range(4):
                grid.setColumnStretch(i, 1 if i < columns else 0)
            grid.invalidate()
            # Changing a grid from one row to two changes its height hint.
            # Qt may otherwise keep the old one-row viewport until a SECOND
            # resize, clipping the lower cards on the first drag.
            self.setMinimumHeight(grid.minimumSize().height())
            self.updateGeometry()

    def set_snapshot(self, values):
        for key, card in self.cards.items():
            card.set_card(values[key])


class ResponsiveQuickActions(QWidget):
    """Keep existing real action buttons usable in compact window sizes.

    Buttons are reparented, not recreated: original signal connections and
    visibility/enabled state remain owned by HubWindow.
    """
    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.setObjectName("responsiveQuickActions")
        self.buttons = tuple(buttons)
        self._columns = max(1, len(self.buttons))
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(6)
        for i, button in enumerate(self.buttons):
            grid.addWidget(button, 0, i)
        for i in range(len(self.buttons)):
            grid.setColumnStretch(i, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = min(len(self.buttons), 1 if self.width() < 520 else
                      (2 if self.width() < 840 else len(self.buttons)))
        if columns != self._columns:
            self._columns = columns
            grid = self.layout()
            for i, button in enumerate(self.buttons):
                grid.addWidget(button, i // columns, i % columns)
            for i in range(len(self.buttons)):
                grid.setColumnStretch(i, 1 if i < columns else 0)
            grid.invalidate()
            self.setMinimumHeight(grid.minimumSize().height())
            self.updateGeometry()
