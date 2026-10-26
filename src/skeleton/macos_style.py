"""
macOS-Native Styling for Kairo (MISHA-based multispectral imaging GUI)

Applies a macOS "Big Sur / Sequoia" light aesthetic to the PyQt5 UI:
  - Apple system palette (systemBlue #007aff, systemGray #8e8e93,
    background #f5f5f7, cards on white, separators #d1d1d6)
  - San Francisco system font (with Helvetica Neue fallback)
  - Rounded cards (QGroupBox), rounded controls, macOS default buttons
    (blue fill) for the primary forward action of each step
  - Thin macOS-style scrollbars and dark system tooltips
  - A runtime-generated app icon (blue tile, spectral band strip) so the
    window / Dock shows a proper icon without shipping a binary asset

The stylesheet is applied once at the QApplication level, so all dialogs
(QMessageBox, QProgressDialog, QFileDialog) inherit it automatically.
Written for the Project Kairo port (see README, Credits).
"""
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap,
)

# ---------------------------------------------------------------------------
# Palette (Apple system colors, light appearance)
# ---------------------------------------------------------------------------
BLUE = "#007aff"          # systemBlue
BLUE_PRESSED = "#0062cc"
RED = "#ff3b30"           # systemRed (destructive actions)
GREEN = "#34c759"         # systemGreen
BG = "#f5f5f7"            # macOS window background
CARD = "#ffffff"          # card / control background
BORDER = "#d1d1d6"        # separator gray
BORDER_FOCUS = "#007aff"
TEXT = "#1d1d1f"          # label color
TEXT_SECONDARY = "#6e6e73"
TRACK = "#e9e9eb"         # slider groove / progress track
SCROLL = "#b0b0b5"
TOOLTIP_BG = "#2c2c2e"

# The blue "default" button for the primary forward action of each step
PRIMARY_BUTTONS = (
    "startButton", "metadataContinueButton", "noiseStartButton",
    "focusStartButton", "lightNext0Button", "objectNextButton",
    "objectStartCaptureButton", "flatsNextButton", "flatsStartCaptureButton",
    "editContinueButton", "performCalibration", "finishFinishButton",
)

# Red-text destructive actions (the "Start Over" family)
DESTRUCTIVE_BUTTONS = (
    "noiseStartOverButton", "focusStartOverButton", "lightStartOverButton",
    "objectStartOverButton", "objectStartOver2Button", "flatsStartOverButton",
    "flatsStartOver2Button", "editStartOverButton", "finishStartOverButton",
    "metadataStartOverButton", "cancelLEDsButton",
)


def _btn_list(names):
    return ",\n".join("QPushButton#{}".format(n) for n in names)


def _btn_list_states(names, *states):
    # Apply the pseudo-state to EVERY selector (a bare trailing ":hover"
    # in a comma list would only attach to the last selector).
    if not states:
        return _btn_list(names)
    suffix = ":" + ":".join(states)
    return ",\n".join("QPushButton#{}{}".format(n, suffix) for n in names)


def build_stylesheet() -> str:
    """Assemble the application-wide QSS stylesheet."""
    primary = _btn_list(PRIMARY_BUTTONS)
    primary_hover = _btn_list_states(PRIMARY_BUTTONS, "hover")
    primary_pressed = _btn_list_states(PRIMARY_BUTTONS, "pressed")
    primary_disabled = _btn_list_states(PRIMARY_BUTTONS, "disabled")
    destructive = _btn_list(DESTRUCTIVE_BUTTONS)

    return f"""
/* ============================ Base ============================ */
* {{
    color: {TEXT};
    selection-background-color: {BLUE};
    selection-color: #ffffff;
    outline: none;
}}

QMainWindow, QStackedWidget, QWidget#pages > QWidget, QDialog {{
    background-color: {BG};
}}

QLabel {{
    background: transparent;
    font-size: 13px;
}}

/* ============================ Cards ============================ */
QGroupBox {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    font-size: 13px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 4px;
    color: {TEXT};
}}

QFrame {{
    background: transparent;
}}
Line {{
    color: {BORDER};
    background-color: {BORDER};
    max-height: 1px;
    border: none;
}}

/* ============================ Buttons ============================ */
QPushButton {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #f0f0f5;
    border-color: #b8b8bd;
}}
QPushButton:pressed {{
    background-color: #e4e4ea;
}}
QPushButton:disabled {{
    color: #c7c7cc;
    border-color: #e3e3e8;
    background-color: #fafafa;
}}

/* macOS default buttons: blue fill, white text */
{primary} {{
    background-color: {BLUE};
    border: 1px solid {BLUE};
    color: #ffffff;
    font-weight: 600;
}}
{primary_hover} {{
    background-color: #0a7cff;
    border-color: #0a7cff;
}}
{primary_pressed} {{
    background-color: {BLUE_PRESSED};
    border-color: {BLUE_PRESSED};
}}
{primary_disabled} {{
    background-color: #a8d2ff;
    border-color: #a8d2ff;
    color: #ffffff;
}}

/* Destructive "Start Over" actions: red text */
{destructive} {{
    color: {RED};
}}

/* The big thumbnail buttons on the light-level step */
QPushButton#lightLevel0, QPushButton#lightLevel1,
QPushButton#lightLevel2, QPushButton#lightLevel3 {{
    border-radius: 12px;
    padding: 4px;
}}

/* ============================ Text fields ============================ */
QLineEdit, QTextEdit, QTextBrowser, QComboBox {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 13px;
    min-height: 20px;
}}
QLineEdit:focus, QTextEdit:focus, QTextBrowser:focus {{
    border: 2px solid {BORDER_FOCUS};
}}
QLineEdit:read-only, QTextEdit:read-only, QTextBrowser:read-only {{
    background-color: #fbfbfd;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {BLUE};
    selection-color: #ffffff;
    outline: none;
}}

/* ============================ Check / radio ============================ */
QRadioButton, QCheckBox {{
    background: transparent;
    spacing: 6px;
    font-size: 13px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}
QRadioButton::indicator {{
    border: 2px solid #b0b0b5;
    border-radius: 9px;
    background: {CARD};
}}
QRadioButton::indicator:checked {{
    border: 5px solid {BLUE};
    background: {CARD};
}}
QCheckBox::indicator {{
    border: 1px solid #b0b0b5;
    border-radius: 4px;
    background: {CARD};
}}
QCheckBox::indicator:checked {{
    background: {BLUE};
    border: 1px solid {BLUE};
    image: none;
}}

/* ============================ Sliders ============================ */
QSlider::groove:horizontal {{
    height: 4px;
    background: {TRACK};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {BLUE};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
    background: #ffffff;
    border: 1px solid #c7c7cc;
}}

/* ============================ Progress ============================ */
QProgressBar {{
    background-color: {TRACK};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: {TEXT_SECONDARY};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background-color: {BLUE};
    border-radius: 5px;
}}

/* ============================ Image views ============================ */
QGraphicsView {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* ============================ ToolBox (edit page) ============================ */
QToolBox::tab-button {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    margin: 2px 0;
}}
QToolBox::tab-button:hover {{
    background: #f0f0f5;
}}
QToolBox::tab {{
    background: transparent;
}}

/* ============================ Menus (macOS menu bar) ============ */
QMenuBar {{
    background: transparent;
}}
QMenuBar::item {{
    background: transparent;
    padding: 2px 8px;
}}
QMenuBar::item:selected {{
    background: {BLUE};
    color: #ffffff;
    border-radius: 4px;
}}
QMenu {{
    background-color: #f2f2f7;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 5px 22px 5px 20px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {BLUE};
    color: #ffffff;
}}

/* ============================ Tooltips ============================ */
QToolTip {{
    background-color: {TOOLTIP_BG};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 8px;
}}

/* ============================ Scrollbars =========================== */
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {SCROLL};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #8e8e93;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {SCROLL};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
"""


def build_app_icon() -> QIcon:
    """
    Generate the app icon at runtime: a rounded blue tile with a white "K"
    and a 16-color spectral strip across the bottom (a nod to the 16-band
    multispectral capture workflow).
    """
    size = 256
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # Tile
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QColor("#3ba4ff"))
    grad.setColorAt(1.0, QColor("#0055d4"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(8, 8, size - 16, size - 16), 56, 56)

    # 16-band spectral strip (matches the LED wavelength list, UV -> NIR)
    band_colors = [
        "#8e7dff", "#7a6bff", "#6b5bff", "#5a4bff",  # UV / violet
        "#3f37ff", "#2b2bff", "#007aff", "#00a2ff",  # blue
        "#00c3ff", "#00e0e0", "#00e676", "#76ff03",  # cyan / green
        "#ffd60a", "#ff9f0a", "#ff6b3b", "#ff3b30",  # yellow / orange / red
    ]
    strip_h = 22
    strip_y = size - 40
    seg_w = (size - 48) / len(band_colors)
    for i, c in enumerate(band_colors):
        p.setBrush(QColor(c))
        x = 24 + i * seg_w
        p.drawRect(QRectF(x, strip_y, seg_w + 0.6, strip_h))

    # "K"
    p.setPen(QColor("#ffffff"))
    font = QFont(".AppleSystemUIFont")
    font.setPixelSize(150)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(8, 18, size - 16, size - 90), Qt.AlignCenter, "K")
    p.end()
    return QIcon(pix)


def apply(app, window=None):
    """
    Apply the macOS-native look to a QApplication (and optionally a main
    window): app identity, system font, stylesheet, and window icon.
    """
    app.setApplicationName("Kairo")
    app.setApplicationDisplayName("Kairo")
    app.setOrganizationName("Tom Shrieve")

    # San Francisco (macOS system font) with graceful fallbacks: pick the
    # first family actually present on the system.
    from PyQt5.QtGui import QFontDatabase
    db = QFontDatabase()
    font = QFont()
    for family in (".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue",
                   "DejaVu Sans"):
        if family in db.families():
            font = QFont(family)
            break
    app.setFont(font)

    app.setStyleSheet(build_stylesheet())

    if window is not None:
        window.setWindowIcon(build_app_icon())
        window.setWindowTitle("Kairo")
