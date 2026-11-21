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
/* Dev5D1-A: a compact icon-and-text launcher navigation strip.
   Uses the original yellow selection and blue hover accents. */
/* Dev5D1-C: clear selected-tab contrast and consistent launcher spacing.
   Icons are recolored at presentation time, never replaced with new artwork. */
QTabWidget#gameDetailsTabs QTabBar::tab {{
    color: {TEXT};
    background: #171D23;
    padding: 10px 13px;
    margin-right: 4px;
    border: 1px solid #34404B;
    border-radius: 8px;
    min-height: 24px;
    font-weight: 650;
}}
QTabWidget#gameDetailsTabs QTabBar::tab:selected {{
    background: {YELLOW};
    color: {BG};
    border: 1px solid {YELLOW};
    font-weight: 800;
}}
QTabWidget#gameDetailsTabs QTabBar::tab:hover:!selected {{
    color: {BLUE};
    background: #182734;
    border-color: {BLUE};
}}
QTabWidget#gameDetailsTabs QTabBar::tab:focus {{
    border-color: {BLUE};
}}
QWidget#overviewLaunchTools {{
    background: #101820;
    border: 1px solid #253748;
    border-radius: 9px;
    padding: 7px 10px;
}}
QLabel#launchToolsLabel {{
    color: {BLUE};
    font-size: 12px;
    font-weight: 800;
    padding: 1px 3px;
    border: none;
}}
QPushButton#overviewSecondaryLaunch {{
    background: #17212A;
    color: {TEXT};
    border: 1px solid #3A4A57;
    min-height: 26px;
}}
QPushButton#overviewSecondaryLaunch:hover {{
    border-color: {BLUE};
    color: {BLUE};
}}
QPushButton#overviewSecondaryLaunch:disabled {{
    color: #76828E;
    background: #121820;
    border-color: #2B343E;
}}
QLabel#rollbackHeading {{
    color: {YELLOW};
    font-size: 16px;
    font-weight: 800;
}}
QLabel#rollbackSummary, QLabel#rollbackNotice {{
    color: {TEXT};
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 12px;
}}
QLabel#rollbackNotice {{ color: {MUTED}; }}
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
QLabel#launcherArtworkSource {{
    color: #A7ADB7;
    font-size: 11px;
    padding: 3px 5px;
}}
QPushButton#launcherArtworkAction {{
    background: #151D25;
    border: 1px solid #39414A;
    color: #23B7FF;
    font-size: 11px;
    padding: 6px 11px;
}}
QPushButton#launcherArtworkAction:hover {{
    border-color: #23B7FF;
}}
QPushButton#launcherArtworkAction:disabled {{
    color: #69717C;
    border-color: #252C33;
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
    color: {BLUE};
    text-align: left;
    font-size: 12px;
    font-weight: 700;
    min-height: 28px;
    padding: 7px 12px;
    background: #101B25;
    border: 1px solid #284658;
    border-radius: 8px;
}}
QPushButton#launcherDisclosure:hover {{
    color: {BLUE};
    background: #142636;
    border-color: {BLUE};
}}
QPushButton#launcherDisclosure:checked {{
    color: {YELLOW};
    background: #24210F;
    border-color: #66591A;
}}
QPushButton:focus {{
    border-color: {BLUE};
}}
QPushButton#primaryAction:focus, QPushButton#downloadsScan:focus {{
    border-color: {YELLOW_HOVER};
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
QLabel#tableColumnHint {{
    color: #A7ADB7;
    font-size: 10px;
    padding: 5px 3px 3px 3px;
}}
QTableWidget QHeaderView {{
    background: #14212B;
}}
/* Dev5A: guided downloads, pinned-hash archive inventory, read-only plan. */
QWidget#guidedDownloadsPage {{
    background: #0A0D10;
}}
/* Dev5C: read-only target review and explicit install consent. */
QLabel#installReviewTitle {{
    color: #FFD21A;
    font-size: 18px;
    font-weight: 800;
}}
QLabel#installReviewOverview {{
    background: #151D25;
    border: 1px solid #2A3139;
    border-radius: 7px;
    padding: 9px;
    color: #E5E8ED;
    font-size: 12px;
}}
QLabel#installReviewBackup {{
    color: #23B7FF;
    font-size: 12px;
    font-weight: 700;
    padding: 3px 5px;
}}
QTableWidget#installReviewTargets {{
    background: #11161B;
    alternate-background-color: #171D23;
    border: 1px solid #2A3139;
    border-radius: 8px;
    selection-background-color: #3B3108;
}}
QPushButton#installReviewApply {{
    color: #FFD21A;
    border: 1px solid #FFD21A;
    background: #342B0B;
    padding: 9px 16px;
    font-weight: 700;
}}
QPushButton#installReviewApply:disabled {{
    color: #69717C;
    border: 1px solid #2A3139;
    background: #151D25;
}}
QPushButton#installReviewCancel {{
    color: #23B7FF;
    border: 1px solid #244A61;
    background: #14212B;
    padding: 9px 16px;
}}
QLabel#downloadsHeading {{
    color: #FFD21A;
    font-size: 17px;
    font-weight: 800;
}}
QLabel#downloadsExplanation {{
    color: #A7ADB7;
    font-size: 11px;
}}
QLabel#downloadsFolderFeedback {{
    background: #14212B;
    color: #23B7FF;
    border: 1px solid #244A61;
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 11px;
}}
QLabel#verifiedDownloadsStatus {{
    color: #23B7FF;
    font-size: 11px;
    padding: 5px 8px;
    background: #111A21;
    border: 1px solid #244A61;
    border-radius: 6px;
}}
QProgressBar#verifiedDownloadsProgress {{
    background: #151D25;
    border: 1px solid #244A61;
    border-radius: 5px;
    text-align: center;
    min-height: 14px;
}}
QProgressBar#verifiedDownloadsProgress::chunk {{
    background: #23B7FF;
    border-radius: 4px;
}}
QLabel#downloadsBackupSafety {{
    color: #FFCA71;
    background: #231D10;
    border: 1px solid #675319;
    border-radius: 6px;
    padding: 7px 9px;
    font-size: 11px;
}}
QLabel#downloadsSavedScanCount {{
    color: #A7ADB7;
    font-size: 10px;
    padding: 1px 5px;
}}
QLabel#downloadsScanAge {{
    color: #23B7FF;
    font-size: 11px;
    padding: 2px 5px;
}}
QLabel#downloadsLocation, QLabel#downloadsSummary {{
    background: #171D23;
    color: #F5F2DE;
    border: 1px solid #2A3139;
    border-radius: 8px;
    padding: 9px;
    font-size: 11px;
}}
QLabel#downloadsSummary {{
    font-weight: 700;
}}
QTableWidget#downloadsTable {{
    background: #11161B;
    alternate-background-color: #171D23;
    border: 1px solid #2A3139;
    border-radius: 8px;
    selection-background-color: #3B3108;
    gridline-color: #252C33;
}}
QTableWidget#downloadsTable QHeaderView::section {{
    background: #14212B;
    color: #F5F2DE;
    padding: 7px;
    font-weight: 700;
}}
QPushButton#downloadsScan {{
    color: #FFD21A;
    background: #342B0B;
    border: 1px solid #FFD21A;
    padding: 7px 12px;
    font-weight: 700;
}}
QPushButton#downloadsScan:disabled,
QPushButton#downloadsAction:disabled {{
    background: #151D25;
    color: #6D7882;
    border: 1px solid #2A3139;
}}
QPushButton#downloadsAction, QPushButton#downloadsSourceButton {{
    color: #23B7FF;
    background: #14212B;
    border: 1px solid #244A61;
    padding: 7px 10px;
}}
QPushButton#downloadsAction:hover, QPushButton#downloadsSourceButton:hover {{
    border-color: #23B7FF;
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
QLabel#modUpdatesRateLimitNotice {{
    background: #26220F;
    color: #FFD21A;
    border: 1px solid #655315;
    border-radius: 8px;
    padding: 10px;
    font-size: 12px;
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
