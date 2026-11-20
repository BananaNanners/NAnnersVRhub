# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""BananNanners visual theme for the Qt GUI."""
from pathlib import Path

ASSET_DIR = Path(__file__).with_name("assets")
LOGO_PATH = ASSET_DIR / "bananananners.png"

# Palette sampled from the channel art: black / charcoal, banana yellow,
# electric blue, Linux-terminal green, and warm off-white.
YELLOW = "#FFD21A"
YELLOW_HOVER = "#FFE15C"
BLUE = "#23B7FF"
GREEN = "#4FE39A"
RED = "#FF5B50"
TEXT = "#F5F2DE"
MUTED = "#A7ADB7"
BG = "#0A0D10"
PANEL = "#11161B"
PANEL_2 = "#171D23"
BORDER = "#2A3139"

STYLESHEET = f"""
QMenuBar, QMenu {{
    background: {PANEL};
    color: {TEXT};
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background: #3B3108;
    color: {YELLOW};
}}
QMenu::item {{
    padding: 7px 24px;
}}
QMainWindow {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-size: 10.5pt;
}}
QWidget#systemDashboard, QWidget#gamesPage, QDialog#liveTestDialog, QDialog#testHistoryDialog, QDialog#logDiagnosticsDialog, QDialog#supportReportDialog, QDialog#hubUpdateDialog, QDialog#heroicInjectorDialog, QDialog#controllerBindingsDialog, QDialog#doomSaveRecoveryDialog, QDialog#doomSaveConfirmation {{
    background: {BG};
}}
QTabWidget::pane {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: {PANEL_2};
    color: {MUTED};
    padding: 9px 18px;
    border: 1px solid {BORDER};
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}}
QTabBar::tab:selected {{
    color: {YELLOW};
    background: {PANEL};
    border-bottom-color: {PANEL};
}}
QFrame#brandHeader {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #090B0E, stop:0.55 #15130A, stop:1 #08131C);
    border: 1px solid #3B3414;
    border-radius: 12px;
}}
QLabel#brandTitle {{
    color: {YELLOW};
    font-size: 24px;
    font-weight: 800;
}}
QLabel#brandTagline {{
    color: {TEXT};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#brandSubline {{
    color: {MUTED};
    font-size: 10px;
}}
QLabel#runtimePill, QLabel#liveStatus {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 6px 10px;
    font-weight: 700;
}}
QLabel#snapshotStatus {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 8px;
    color: {TEXT};
}}
QTableWidget, QTextBrowser, QPlainTextEdit, QListWidget {{
    background: {PANEL};
    alternate-background-color: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    selection-background-color: #3B3108;
    selection-color: {TEXT};
    gridline-color: #252C33;
}}
QHeaderView::section {{
    background: #14212B;
    color: {TEXT};
    border: none;
    border-right: 1px solid #26343F;
    border-bottom: 1px solid #26343F;
    padding: 7px;
    font-weight: 700;
}}
QPushButton {{
    background: #171B20;
    border: 1px solid #39414A;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 20px;
    font-weight: 650;
}}
QPushButton:hover {{
    border-color: {YELLOW};
    color: {YELLOW};
    background: #201D10;
}}
QPushButton:pressed {{
    background: #332B0A;
}}
QPushButton:disabled {{
    color: #626872;
    background: #101317;
    border-color: #242A30;
}}
QPushButton#primaryAction {{
    background: #2A2408;
    border: 1px solid {YELLOW};
    color: {YELLOW};
}}
QPushButton#primaryAction:hover {{
    background: #3A3108;
    color: {YELLOW_HOVER};
}}
QPushButton#secondaryAction {{
    border-color: #1E7198;
    color: {BLUE};
}}
QComboBox {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL};
    color: {TEXT};
    selection-background-color: #3B3108;
    selection-color: {TEXT};
}}
QLineEdit {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px;
}}
QToolTip {{
    background: #171D23;
    color: {TEXT};
    border: 1px solid {YELLOW};
}}

/* Dev1 launcher chrome: strictly reuse the BananaNanners palette. */
QFrame#launcherSidebar {{
    background: #11161B;
    border: 1px solid #2A3139;
    border-radius: 11px;
}}
QLabel#launcherSideTitle {{
    color: #FFD21A;
    font-size: 16px;
    font-weight: 800;
}}
QLabel#launcherSideHint {{
    color: #A7ADB7;
    font-size: 11px;
}}
QPushButton#launcherNavButton {{
    text-align: left;
    font-size: 14px;
    min-height: 34px;
    padding: 7px 10px;
}}
QPushButton#launcherNavButton:checked {{
    background: #332B0A;
    color: #FFD21A;
    border: 1px solid #FFD21A;
}}
QPushButton#launcherFutureToggle {{
    text-align: left;
    color: #A7ADB7;
    font-size: 12px;
    min-height: 28px;
    padding: 5px 8px;
}}
QPushButton#launcherFutureToggle:checked {{
    color: #FFD21A;
    border-color: #FFD21A;
}}
QPushButton#launcherNavPlanned {{
    text-align: left;
    min-height: 30px;
    font-size: 12px;
}}
QListWidget#launcherGameList {{
    background: transparent;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    outline: none;
}}
QListWidget#launcherGameList::item {{
    padding: 7px 5px;
    border: 1px solid transparent;
    border-radius: 7px;
}}
QListWidget#launcherGameList::item:selected {{
    background: #342B0B;
    color: #FFD21A;
    border: 1px solid #FFD21A;
}}
QFrame#launcherGameBanner {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #28230A, stop:0.50 #14171B, stop:1 #10232E);
    border: 1px solid #4B4219;
    border-radius: 12px;
}}
QLabel#launcherBannerCaption {{
    color: #FFD21A;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#launcherGameTitle {{
    color: #F5F2DE;
    font-size: 23px;
    font-weight: 800;
}}
QLabel#launcherBannerStatus {{
    color: #A7ADB7;
    font-size: 10px;
}}
QPushButton#launcherDisclosure {{
    color: #23B7FF;
    text-align: left;
    font-size: 10px;
}}

/* Match scrollbars to the existing charcoal theme in the game library. */
QListWidget#launcherGameList QScrollBar:vertical {{
    background: #11161B;
    width: 9px;
    margin: 0px;
    border: none;
}}
QListWidget#launcherGameList QScrollBar::handle:vertical {{
    background: #39414A;
    min-height: 24px;
    border-radius: 4px;
}}
QListWidget#launcherGameList QScrollBar::add-line:vertical,
QListWidget#launcherGameList QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}
QListWidget#launcherGameList QScrollBar::add-page:vertical,
QListWidget#launcherGameList QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* Dev2 read-only game dashboard — existing BananaNanners palette. */
QWidget#gameDashboard {{
    background: transparent;
}}
QFrame#dashboardCard {{
    background: #171D23;
    border: 1px solid #2A3139;
    border-radius: 10px;
}}
QFrame#dashboardCard[tone="warning"] {{
    border: 1px solid #766115;
}}
QFrame#dashboardCard[tone="success"] {{
    border: 1px solid #246348;
}}
QLabel#dashboardCardHeading {{
    color: #A7ADB7;
    font-size: 11px;
    font-weight: 700;
    border: none;
}}
QLabel#dashboardCardValue {{
    color: #F5F2DE;
    font-size: 18px;
    font-weight: 800;
    border: none;
}}
QLabel#dashboardCardValue[tone="success"] {{
    color: #4FE39A;
}}
QLabel#dashboardCardValue[tone="warning"] {{
    color: #FFD21A;
}}
QLabel#dashboardCardDetail {{
    color: #A7ADB7;
    font-size: 11px;
    border: none;
}}

/* Dev3 Mod Updates: native table, familiar launcher layout, original brand. */
QWidget#modUpdatesPage, QWidget#modUpdatesContent {{
    background: #0A0D10;
}}
QLabel#modUpdatesHeading {{
    color: #FFD21A;
    font-size: 18px;
    font-weight: 800;
}}
QLabel#modUpdatesExplanation {{
    color: #A7ADB7;
    font-size: 11px;
}}
QLabel#modUpdatesSummary {{
    background: #171D23;
    color: #F5F2DE;
    border: 1px solid #2A3139;
    border-radius: 8px;
    padding: 12px;
    font-size: 12px;
    font-weight: 700;
}}
QLabel#modUpdatesEmpty {{
    color: #A7ADB7;
    padding: 14px;
    font-size: 12px;
}}
QToolButton#modUpdatesDisclosure {{
    background: #171D23;
    border: 1px solid #2A3139;
    border-radius: 7px;
    color: #FFD21A;
    padding: 8px 12px;
    font-weight: 700;
    font-size: 12px;
    text-align: left;
}}
QToolButton#modUpdatesDisclosure[group="current"] {{
    color: #4FE39A;
}}
QToolButton#modUpdatesDisclosure[group="later"],
QToolButton#modUpdatesDisclosure[group="not_installed"] {{
    color: #A7ADB7;
}}
QToolButton#modUpdatesDisclosure:hover {{
    background: #27250D;
    border: 1px solid #FFD21A;
}}
QPushButton#modSourceButton {{
    background: #14212B;
    border: 1px solid #244A61;
    color: #23B7FF;
    font-weight: 700;
    padding: 5px 8px;
}}
QPushButton#modSourceButton:hover {{
    background: #143246;
    border-color: #23B7FF;
}}
QPushButton#modUpdatesRefresh {{
    padding: 9px 14px;
}}
QTableWidget#modUpdatesTable {{
    background: #11161B;
    alternate-background-color: #171D23;
    border: 1px solid #2A3139;
    border-radius: 7px;
    font-size: 12px;
}}
QTableWidget#modUpdatesTable QHeaderView::section {{
    background: #14212B;
    color: #F5F2DE;
    padding: 6px;
    border-right: 1px solid #26343F;
    font-weight: 700;
}}
"""
