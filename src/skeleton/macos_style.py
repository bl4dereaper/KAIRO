"""
Kairo Application Styling — Dark Professional Theme

A Capture One / Pro Display-style dark neutral theme for the PyQt5 UI:
  - Dark neutral palette: window #1e1e1e, panels #262628, elements #323234,
    hairline separators #3a3a3c, text #f5f5f7 / #a1a1a6 / #6e6e73
  - System accent blue #0a84ff (macOS dark-mode systemBlue) used sparingly
    for the primary action, active states, and slider fill
  - San Francisco system font (with Helvetica Neue fallback)
  - Flat, precise controls: hairline borders, small radii, thin sliders,
    black image canvas (#000) with a 1px frame
  - Top bar treatment (wordmark, step indicator, device status chips)
  - Thin scrollbars, dark menus / dialogs / tooltips
  - A runtime-generated app icon (blue tile, "K", spectral strip) so the
    window / Dock shows a proper icon without shipping a binary asset

The stylesheet is applied once at the QApplication level, so all dialogs
(QMessageBox, QProgressDialog, QFileDialog) inherit it automatically.
Written for the Project Kairo redesign (see README, Credits).
"""
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QRectF, QTimer
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap,
)

# ---------------------------------------------------------------------------
# Palette (dark neutral, "pro display" appearance)
# ---------------------------------------------------------------------------
BLUE = "#0a84ff"          # dark-mode systemBlue (accent)
BLUE_HOVER = "#409cff"
BLUE_PRESSED = "#0060df"
RED = "#ff453a"           # destructive actions
GREEN = "#30d158"         # connected / on
AMBER = "#ff9f0a"         # degraded / test mode
BG = "#1e1e1e"            # window background
PANEL = "#262628"         # cards / group boxes
ELEMENT = "#323234"       # buttons, fields
ELEMENT_HOVER = "#3d3d3f"
ELEMENT_PRESSED = "#2a2a2c"
BORDER = "#3a3a3c"        # hairline separator
BORDER_2 = "#48484a"      # stronger border (controls)
TEXT = "#f5f5f7"          # primary text
TEXT_2 = "#a1a1a6"        # secondary text
TEXT_3 = "#6e6e73"        # tertiary / micro labels
TRACK = "#3a3a3c"         # slider groove / progress track
SCROLL = "#5a5a5e"        # scrollbar handle
CANVAS = "#000000"        # image view background
TOOLTIP_BG = "#3a3a3c"
TOPOBAR = "#191919"       # top bar (slightly darker than window)

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

QStatusBar {{
    background: {TOPOBAR};
    color: {TEXT_2};
    font-size: 11px;
}}
QStatusBar QLabel {{
    color: {TEXT_2};
    font-size: 11px;
}}

/* ============================ Top bar ============================ */
QFrame#topBar {{
    background-color: {TOPOBAR};
    border-bottom: 1px solid {BORDER};
}}
QLabel#topWordmark {{
    color: {TEXT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#topSublabel {{
    color: {TEXT_3};
    font-size: 10px;
}}
QWidget#stepBar, QWidget#statusArea {{
    background: transparent;
}}
/* Step indicator segments (state set at runtime: future / done / active) */
QLabel#stepSeg {{
    color: {TEXT_3};
    font-size: 12px;
    padding: 0 14px;
    background: transparent;
}}
QLabel#stepSeg[state="done"] {{
    color: {TEXT_2};
}}
QLabel#stepSeg[state="active"] {{
    color: {TEXT};
    font-weight: 600;
    border-bottom: 2px solid {BLUE};
}}
QLabel#stepSep {{
    color: {BORDER_2};
    font-size: 10px;
    padding: 0 2px;
}}
/* Device status chips */
QFrame#statusChip {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#statusChipText {{
    color: {TEXT_2};
    font-size: 11px;
}}
QLabel#statusDot {{
    font-size: 9px;
}}

/* ============================ Cards ============================ */
QGroupBox {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 4px;
    color: {TEXT_2};
    font-weight: 500;
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
    background-color: {ELEMENT};
    border: 1px solid {BORDER_2};
    border-radius: 7px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 20px;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: {ELEMENT_HOVER};
}}
QPushButton:pressed {{
    background-color: {ELEMENT_PRESSED};
}}
QPushButton:disabled {{
    color: {TEXT_3};
    border-color: {BORDER};
    background-color: {PANEL};
}}

/* Checkable toggle buttons: blue fill while ON */
QPushButton:checked {{
    background-color: {BLUE};
    border-color: {BLUE};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton:checked:hover {{
    background-color: {BLUE_HOVER};
    border-color: {BLUE_HOVER};
}}

/* Primary "default" buttons: blue fill, white text */
{primary} {{
    background-color: {BLUE};
    border: 1px solid {BLUE};
    color: #ffffff;
    font-weight: 600;
}}
{primary_hover} {{
    background-color: {BLUE_HOVER};
    border-color: {BLUE_HOVER};
}}
{primary_pressed} {{
    background-color: {BLUE_PRESSED};
    border-color: {BLUE_PRESSED};
}}
{primary_disabled} {{
    background-color: #274a6d;
    border-color: #274a6d;
    color: #7d9cc0;
}}

/* Destructive "Start Over" actions: red text */
{destructive} {{
    color: {RED};
}}

/* The big thumbnail buttons on the light-level step */
QPushButton#lightLevel0, QPushButton#lightLevel1,
QPushButton#lightLevel2, QPushButton#lightLevel3 {{
    border-radius: 10px;
    padding: 4px;
}}

/* ============================ Text fields ============================ */
QLineEdit, QTextEdit, QTextBrowser, QComboBox {{
    background-color: {PANEL};
    border: 1px solid {BORDER_2};
    border-radius: 7px;
    padding: 5px 8px;
    font-size: 13px;
    min-height: 20px;
    color: {TEXT};
}}
QLineEdit:focus, QTextEdit:focus, QTextBrowser:focus {{
    border: 1px solid {BLUE};
}}
QLineEdit:read-only {{
    border-color: {BORDER};
    background-color: {PANEL};
}}
/* Display-only info text boxes: explicit dark viewport (transparent would
   let the scrollarea viewport's light Base palette show through), no frame */
QTextEdit:read-only, QTextBrowser:read-only {{
    border: none;
    background-color: {BG};
    padding: 0;
}}
/* The start-page hero text: floats on the window background */
QTextEdit#startingInfo {{
    background: transparent;
    border: none;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL};
    border: 1px solid {BORDER_2};
    border-radius: 7px;
    selection-background-color: {BLUE};
    selection-color: #ffffff;
    outline: none;
}}

/* ============================ Check / radio ============================ */
QRadioButton, QCheckBox {{
    background: transparent;
    spacing: 6px;
    font-size: 13px;
    color: {TEXT_2};
}}
QRadioButton:checked, QCheckBox:checked {{
    color: {TEXT};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}
QRadioButton::indicator {{
    border: 2px solid {BORDER_2};
    border-radius: 9px;
    background: {PANEL};
}}
QRadioButton::indicator:checked {{
    border: 5px solid {BLUE};
    background: {PANEL};
}}
QCheckBox::indicator {{
    border: 1px solid {BORDER_2};
    border-radius: 4px;
    background: {PANEL};
}}
QCheckBox::indicator:checked {{
    background: {BLUE};
    border: 1px solid {BLUE};
    image: none;
}}

/* ============================ Sliders ============================ */
QSlider::groove:horizontal {{
    height: 3px;
    background: {TRACK};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {BLUE};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    background: {TEXT};
    border: 1px solid {BORDER_2};
}}

/* ============================ Progress ============================ */
QProgressBar {{
    background-color: {TRACK};
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
    color: {TEXT_2};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background-color: {BLUE};
    border-radius: 2px;
}}

/* ============================ Image views ============================ */
QGraphicsView {{
    background-color: {CANVAS};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

/* ============================ ToolBox (edit page) ============================ */
QToolBox::tab-button {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 8px 14px;
    margin: 2px 0;
    color: {TEXT_2};
}}
QToolBox::tab-button:hover {{
    background: {ELEMENT};
    color: {TEXT};
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
    background-color: {PANEL};
    border: 1px solid {BORDER_2};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 5px 24px 5px 20px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {BLUE};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
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
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {SCROLL};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #7a7a80;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
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

/* ============================ Misc ============================ */
QSplitter::handle {{
    background: {BORDER};
}}
"""


def build_app_pixmap(size: int = 256) -> QPixmap:
    """
    Render the Kairo mark: a rounded blue tile with a white "K" and a
    16-color spectral strip across the bottom (a nod to the 16-band
    multispectral capture workflow). Returns a square QPixmap.
    """
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
    return pix


def build_app_icon() -> QIcon:
    return QIcon(build_app_pixmap())


class KairoSplash(QtWidgets.QWidget):
    """
    Launch splash in the Kairo design language — a Photoshop-style launch
    card: dark rounded panel, K mark, letterspaced KAIRO wordmark, an
    animated progress line that fills exactly over `duration_ms`, and
    copyright at the bottom. Frameless, centered, stays on top.
    """

    def __init__(self, duration_ms: int = 3000, parent=None):
        super().__init__(parent)
        self._duration = duration_ms
        self._elapsed = 0
        self._tile = build_app_pixmap(256)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(520, 560)
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2,
                  screen.center().y() - self.height() // 2)
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._tick)

    def start(self):
        """Show the splash and start the progress animation."""
        self._timer.start()
        self.show()

    def _tick(self):
        self._elapsed += self._timer.interval()
        self.update()

    @property
    def progress(self) -> float:
        return min(1.0, self._elapsed / self._duration)

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Panel
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 24, 24)
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 24, 24)

        # K mark
        p.drawPixmap((w - 120) // 2, 88,
                     self._tile.scaled(120, 120, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation))

        # Wordmark
        f = QFont()
        f.setPixelSize(34)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 10)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(0, 244, w, 50), Qt.AlignHCenter | Qt.AlignVCenter,
                   "KAIRO")

        # Micro label
        f2 = QFont()
        f2.setPixelSize(11)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        p.setFont(f2)
        p.setPen(QColor(TEXT_3))
        p.drawText(QRectF(0, 296, w, 18), Qt.AlignHCenter | Qt.AlignVCenter,
                   "MULTISPECTRAL IMAGING")

        # Progress line (fills 0 -> 100% over the hold time)
        bar_w = 320
        x0 = (w - bar_w) / 2
        y = 384
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(QRectF(x0, y, bar_w, 4), 2, 2)
        if self.progress > 0.01:
            grad = QLinearGradient(x0, 0, x0 + bar_w, 0)
            grad.setColorAt(0.0, QColor("#3ba4ff"))
            grad.setColorAt(1.0, QColor("#0055d4"))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(x0, y, bar_w * self.progress, 4), 2, 2)

        # Copyright
        fc = QFont()
        fc.setPixelSize(11)
        p.setFont(fc)
        p.setPen(QColor(TEXT_3))
        p.drawText(QRectF(0, h - 88, w, 16), Qt.AlignHCenter,
                   "\u00a9 2026 Tom Shrieve. All rights reserved.")
        p.setPen(QColor("#55555a"))
        p.drawText(QRectF(0, h - 66, w, 30), Qt.AlignHCenter | Qt.AlignTop,
                   "Based on MISHA (RIT) \u00b7 GPL v3")
        p.end()


def apply(app, window=None):
    """
    Apply the Kairo professional dark theme to a QApplication (and
    optionally a main window): app identity, system font, stylesheet,
    and window icon.
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
