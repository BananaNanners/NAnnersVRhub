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
QMainWindow {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-size: 10.5pt;
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
QTableWidget, QTextBrowser {{
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
"""
