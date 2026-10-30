"""
Kairo Control — LED Panel Tool Window

Manual control for the Kairo multispectral LED light panel, integrated as
a tool window in the main Kairo application (Window menu, or by clicking
the LED status chip in the top bar).

Built in the Kairo design language (skeleton/macos_style.py): dark neutral
palette, K mark, hairline top bar with device status chip, flat controls.

Two board revisions, matching the original MISHA LEDS tool:
  - Board V1: 18 bands (365-940 nm, incl. 490 / 520)
  - Board V2: 16 bands (365-940 nm)

The window borrows the LED controller from the main window (LEDController
when the CP210x panel is connected, LEDMock in test mode), so the serial
connection is shared with the capture workflow — closing this window never
disconnects the panel.

Based on the MISHA LEDS panel tool (RIT). Written for the Project Kairo
release, designed and built by Shrieve Industries.
"""

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from controllers.led_mock import LEDMock
from skeleton import macos_style

# Board revisions from the original MISHA LEDS tool (mainwindow.ui)
BOARD_V1 = ['365', '385', '395', '420',
            '450', '470', '490', '500', '520', '530',
            '560', '590', '615', '630',
            '660', '730', '850', '940']
BOARD_V2 = ['365', '385', '395', '420',
            '450', '470', '500', '530',
            '560', '590', '615', '630',
            '660', '730', '850', '940']
BOARDS = {'V1': BOARD_V1, 'V2': BOARD_V2}

# Spectral color per wavelength: UV/violet -> visible -> NIR (the NIR
# bands are dark red to suggest their invisible light). Same family as
# the 16-band strip on the K mark.
BAND_COLORS = {
    '365': '#8e7dff', '385': '#7a6bff', '395': '#6b5bff', '420': '#5a4bff',
    '450': '#2b6bff', '470': '#007aff', '490': '#00a2ff', '500': '#00c3ff',
    '520': '#00e0e0', '530': '#00e676', '560': '#76ff03', '590': '#ffd60a',
    '615': '#ff9f0a', '630': '#ff6b3b', '660': '#ff3b30',
    '730': '#c22a20', '850': '#8e1a13', '940': '#5a100c',
}

# Window-local stylesheet: board segment control, Turn Off.
# (The app-level stylesheet from macos_style applies underneath.)
_WINDOW_QSS = """
QFrame#segTrack {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QPushButton#segBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    color: {TEXT_2};
    font-size: 12px;
    font-weight: 500;
    padding: 5px 18px;
}}
QPushButton#segBtn:hover {{
    color: {TEXT};
}}
QPushButton#segBtn:checked {{
    background-color: {ELEMENT_HOVER};
    border: 1px solid {BORDER_2};
    color: {TEXT};
    font-weight: 600;
}}
QPushButton#turnOff {{
    color: {RED};
    font-weight: 600;
}}
QLabel#microLabel {{
    color: {TEXT_3};
    font-size: 10px;
    letter-spacing: 1px;
}}
QFrame#testBanner {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
""".format(PANEL=macos_style.PANEL, BORDER=macos_style.BORDER,
           TEXT=macos_style.TEXT, TEXT_2=macos_style.TEXT_2,
           TEXT_3=macos_style.TEXT_3, ELEMENT_HOVER=macos_style.ELEMENT_HOVER,
           BORDER_2=macos_style.BORDER_2, RED=macos_style.RED)


class KairoControlWindow(QtWidgets.QMainWindow):
    """LED panel control tool window (a child of the main Kairo window)."""

    def __init__(self, main):
        """
        :param main: the main Kairo Ui instance. Its led_control
            (LEDController or LEDMock) is shared — this window never
            opens its own serial connection.
        """
        super(KairoControlWindow, self).__init__(parent=main)
        self.main = main
        self.led = main.led_control
        self._board = 'V1'
        self._active = None  # wavelength string currently ON, or None
        self._buttons = {}   # wavelength -> button for the current page

        self.setObjectName("kairoControlWindow")
        self.setWindowTitle("Kairo Control")
        self.setWindowIcon(macos_style.build_app_icon())
        self.setStyleSheet(_WINDOW_QSS)
        self._build()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar (48 px): K mark + wordmark, status chip on the right
        root.addWidget(self._build_top_bar())

        body = QtWidgets.QWidget()
        body_lay = QtWidgets.QVBoxLayout(body)
        body_lay.setContentsMargins(24, 18, 24, 20)
        body_lay.setSpacing(14)

        # Test-mode banner (only visible when no real panel is connected)
        self.test_banner = self._build_test_banner()
        body_lay.addWidget(self.test_banner)

        # Board revision segment control
        body_lay.addWidget(self._build_board_segment())

        # Micro label row
        row = QtWidgets.QHBoxLayout()
        self._micro_left = QtWidgets.QLabel("SELECT WAVELENGTH (nm)")
        self._micro_left.setObjectName("microLabel")
        self._micro_right = QtWidgets.QLabel("")
        self._micro_right.setObjectName("microLabel")
        row.addWidget(self._micro_left)
        row.addStretch(1)
        row.addWidget(self._micro_right)
        body_lay.addLayout(row)

        # Board pages (stacked), then Turn Off
        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self._build_board_page('V1'))
        self.pages.addWidget(self._build_board_page('V2'))
        body_lay.addWidget(self.pages, 1)

        off = QtWidgets.QPushButton("Turn Off")
        off.setObjectName("turnOff")
        off.setMinimumHeight(38)
        off.clicked.connect(self._turn_off)
        body_lay.addWidget(off)

        root.addWidget(body, 1)
        # Establish the initial board state (segment check, micro label,
        # button sync)
        self._set_board(self._board)
        self.resize(560, 720)

    def _build_top_bar(self):
        bar = QtWidgets.QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(48)
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(10)

        mark = QtWidgets.QLabel()
        mark.setPixmap(macos_style.build_app_pixmap(128)
                       .scaled(28, 28, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation))
        lay.addWidget(mark)

        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(0)
        word = QtWidgets.QLabel("K A I R O")
        word.setObjectName("topWordmark")
        sub = QtWidgets.QLabel("LED PANEL CONTROL")
        sub.setObjectName("topSublabel")
        texts.addWidget(word)
        texts.addWidget(sub)
        lay.addLayout(texts)

        lay.addStretch(1)

        # LED status chip (same treatment as the main window's chips)
        chip = QtWidgets.QFrame()
        chip.setObjectName("statusChip")
        chip_lay = QtWidgets.QHBoxLayout(chip)
        chip_lay.setContentsMargins(10, 3, 12, 3)
        chip_lay.setSpacing(6)
        connected = not isinstance(self.led, LEDMock)
        dot = QtWidgets.QLabel("\u25cf")
        dot.setObjectName("statusDot")
        dot.setStyleSheet("color: {};".format(
            "#30d158" if connected else "#ff9f0a"))
        txt = QtWidgets.QLabel("LED \u00b7 " +
                               ("Panel connected" if connected
                                else "Test mode"))
        txt.setObjectName("statusChipText")
        chip_lay.addWidget(dot)
        chip_lay.addWidget(txt)
        lay.addWidget(chip)
        return bar

    def _build_test_banner(self):
        ban = QtWidgets.QFrame()
        ban.setObjectName("testBanner")
        ban_lay = QtWidgets.QHBoxLayout(ban)
        ban_lay.setContentsMargins(12, 8, 12, 8)
        ban_lay.setSpacing(8)
        dot = QtWidgets.QLabel("\u25cf")
        dot.setStyleSheet("color: #ff9f0a; font-size: 9px;")
        dot.setAlignment(Qt.AlignTop)
        txt = QtWidgets.QLabel(
            "Test mode \u2014 no LED panel detected; selections are "
            "simulated. Connect the panel and restart Kairo to control "
            "hardware.")
        txt.setStyleSheet("color: #a1a1a6; font-size: 11px;")
        txt.setWordWrap(True)
        txt.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        ban_lay.addWidget(dot)
        ban_lay.addWidget(txt)
        ban_lay.addStretch(1)
        ban.setVisible(isinstance(self.led, LEDMock))
        return ban

    def _build_board_segment(self):
        track = QtWidgets.QFrame()
        track.setObjectName("segTrack")
        lay = QtWidgets.QHBoxLayout(track)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(4)
        self._seg_buttons = {}
        for name in ('V1', 'V2'):
            b = QtWidgets.QPushButton("Board " + name)
            b.setObjectName("segBtn")
            b.setCheckable(True)
            b.setChecked(name == self._board)
            b.clicked.connect(
                lambda _checked=False, n=name: self._set_board(n))
            lay.addWidget(b)
            self._seg_buttons[name] = b
        return track

    def _build_board_page(self, name):
        wls = BOARDS[name]
        page = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        ncols = 2
        for i, wl in enumerate(wls):
            btn = QtWidgets.QPushButton(wl)
            btn.setObjectName("bandBtn")
            btn.setCheckable(True)
            btn.setMinimumHeight(42)
            # Spectral color key on the left edge of the button
            btn.setStyleSheet(
                "border-left: 4px solid {};".format(BAND_COLORS[wl]))
            btn.clicked.connect(
                lambda _checked=False, w=wl: self._band_clicked(w))
            grid.addWidget(btn, i // ncols, i % ncols)
            self._buttons.setdefault(name, {})[wl] = btn
        return page

    # ------------------------------------------------------------------
    # Behavior
    # ------------------------------------------------------------------

    def _set_board(self, name):
        """Switch the displayed board revision (app's own navigation
        method — offscreen renders must go through here)."""
        self._board = name
        self._seg_buttons['V1'].setChecked(name == 'V1')
        self._seg_buttons['V2'].setChecked(name == 'V2')
        self.pages.setCurrentIndex(0 if name == 'V1' else 1)
        self._micro_right.setText(
            "{} BANDS".format(len(BOARDS[name])))
        self._refresh_buttons()

    def _refresh_buttons(self):
        """Sync check state on BOTH board pages with the wavelength
        currently ON (the hidden page must not keep stale state)."""
        for name in BOARDS:
            for wl, btn in self._buttons[name].items():
                btn.setChecked(wl == self._active)

    def _band_clicked(self, wl):
        if self._active == wl:
            self._turn_off()
            return
        self._active = wl
        if not isinstance(self.led, LEDMock):
            try:
                self.led.turn_on(wl)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "LED Panel",
                    "Failed to switch the LED panel:\n{}".format(e))
                self._active = None
                self._refresh_buttons()
                return
        self._refresh_buttons()

    def _turn_off(self):
        self._active = None
        if not isinstance(self.led, LEDMock):
            try:
                self.led.turn_off()
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "LED Panel",
                    "Failed to turn off the LED panel:\n{}".format(e))
        self._refresh_buttons()

    def closeEvent(self, event):
        # The main window owns the serial connection; closing this tool
        # window just hides it so it can be reopened from the menu.
        self.hide()
        event.accept()
