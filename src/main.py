"""
Kairo — Main Entry Point

Cross-platform (macOS/Linux/Windows) launcher for Kairo, a multispectral
imaging system designed and built by Tom Shrieve. Initializes the UI
(loaded from skeleton/capture.ui), the camera controller, and the LED
controller, then wires all buttons to their operations.

Camera fallback order: Pixelink -> FLIR Blackfly -> gphoto2 (DSLR) ->
OpenCV (any USB camera) -> CameraMock (hardware-free demo mode), with
automatic selection of the first backend that connects.

Based on MISHA (Multispectral Imaging System for Historical Artifacts),
developed at RIT's Imaging Science and Museum Studies Programs.
Original authors: Sai Keshav Sasanapuri, Cecelia Ahrens, Mallory Bridge,
Eric Gao, Robert Maron. See README.md for full credits.
"""
from datetime import date
import sys, os, subprocess
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from controllers.led_mock import LEDMock
from controllers.pixilink_controller import PixilinkController
from controllers.blackfly_controller import BlackflyController
from controllers.opencv_controller import OpenCVController
from controllers.gphoto2_controller import Gphoto2Controller
from controllers.camera_mock import CameraMock
from controllers.led_controller import LEDController
from operations.operation import Operation
from cube_creation.build_cube import CubeBuilder
from skeleton import macos_style
import time

# import qdarktheme
import numpy as np
import tifffile


# Camera backends in auto-selection priority order: dedicated rig cameras
# first, then PTP DSLR bodies (highest fidelity for Kairo's converted
# cameras), then generic UVC cameras, with the mock demo mode as the
# last resort.
CAMERA_BACKENDS = [
    ("Pixelink", PixilinkController),
    ("FLIR Blackfly", BlackflyController),
    ("DSLR (gphoto2)", Gphoto2Controller),
    ("Generic camera (OpenCV)", OpenCVController),
]


class Ui(QtWidgets.QMainWindow):
    led_control = LEDMock()
    camera_control = None
    intro_text = ('Welcome to Kairo\n\n'
                 'Kairo is a low-cost, end-to-end multispectral imaging '
                 'system designed and built by Tom Shrieve, based on '
                 'MISHA (the "Multispectral Imaging System for Historical '
                 'Artifacts"), developed by RIT\'s Imaging Science and '
                 'Museum Studies Programs for small format historical '
                 'documents, sheet, and leaf collections that have '
                 'overwritten text, faded ink, or other un-readable or '
                 'unknown content.\n'
                 'For more information about MISHA, contact David Messinger '
                 'and Juilee Decker at RIT: https://chipr2022.wordpress.com/\n')
    metadata = {}
    noiseImg = None
    led_op = None
    noise_op = None
    focus_op = None
    light_op = None
    object_op = None
    flats_op = None
    edit_op = None
    finish_op = None
    waveIndex = None
    progress_box = None
    message_box = None
    cube_builder = CubeBuilder()

    '''Initializes the UI, Camera controller and LED controller and starts connecting buttons and operations'''

    def __init__(self, parent=None):
        """Initializes the application"""
        super(Ui, self).__init__(parent)
        basedir = os.path.dirname(__file__)
        uic.loadUi(os.path.join(basedir, "skeleton", "capture.ui"), self)

        self._build_top_bar()
        self._install_focus_assist_switch()
        # Kairo mark on the start page (replaces the old RIT credit logo)
        self.KLogo.setPixmap(macos_style.build_app_pixmap(128))
        # Display-only text boxes (step instructions / info): read-only so
        # they render as plain text on the panel instead of input fields
        for _info in ("noiseInfo", "focasInfo", "lightInfo", "objectInfo",
                      "objectStep2Text", "flatsInfo", "flatsStep2Text",
                      "rotateInfo", "calibrationInfo", "cropInfo",
                      "finishInfoText"):
            getattr(self, _info).setReadOnly(True)
        self._set_starting_info(self.intro_text)
        self.startingInfo.setReadOnly(True)
        self.pages.setCurrentWidget(self.startingPage)
        self.connectButtons()
        self.setOperations()
        self.buildMenuBar()
        self.waveIndex = 0

        init_text = self.initialize_cameras()["Init text"]

        try:
            self.led_control = LEDController()
            self._set_led_status("Panel connected", "on")
        except ValueError as e:
            self._set_led_status("Test mode", "warn")
            init_text += ('LED panel not detected — CAMERA TEST MODE: capture can '
                          'run without the LEDs (no per-band LED switching; frames '
                          'are taken under continuous/ambient light).\n')

        self._set_starting_info(init_text)

        # dev mode
        # self.titleInput.setText("dev mode")  # del
        # self.institutionOrOwnerInput.setText("dev mode")  # del

    '''Initialize cameras'''

    # ------------------------------------------------------------------
    # Top bar: step indicator + device status chips
    # ------------------------------------------------------------------

    def _build_top_bar(self):
        """Populate the top bar with the workflow step indicator and
        the Camera / LED status chips."""
        self.step_defs = [
            ("Setup", self.metadataOp),
            ("Noise", self.noiseOp),
            ("Focus", self.focusOp),
            ("Light", self.lightOp),
            ("Object", self.objectOp),
            ("Flats", self.flatsOp),
            ("Edit", self.editOp),
            ("Finish", self.finishOp),
        ]
        self._page_index = {}
        self.step_segments = []
        for i, (name, page) in enumerate(self.step_defs):
            self._page_index[page] = i
            lab = QtWidgets.QLabel(name)
            lab.setObjectName("stepSeg")
            lab.setProperty("state", "future")
            self.stepBarLayout.addWidget(lab)
            self.step_segments.append((name, lab))
            if i < len(self.step_defs) - 1:
                sep = QtWidgets.QLabel("·")
                sep.setObjectName("stepSep")
                self.stepBarLayout.addWidget(sep)
        self._update_step_indicator(-1)

        self.status_chips = {
            "camera": self._add_status_chip("Camera"),
            "led": self._add_status_chip("LED"),
        }

    def _add_status_chip(self, title):
        """Create a (dot, text) status chip in the top bar."""
        chip = QtWidgets.QFrame()
        chip.setObjectName("statusChip")
        lay = QtWidgets.QHBoxLayout(chip)
        lay.setContentsMargins(10, 3, 12, 3)
        lay.setSpacing(6)
        dot = QtWidgets.QLabel("●")
        dot.setObjectName("statusDot")
        dot.setStyleSheet("color: #5a5a5e;")
        txt = QtWidgets.QLabel(title)
        txt.setObjectName("statusChipText")
        lay.addWidget(dot)
        lay.addWidget(txt)
        self.statusBarLayout.addWidget(chip)
        return (dot, txt)

    _CHIP_COLORS = {"on": "#30d158", "warn": "#ff9f0a", "off": "#5a5a5e"}

    def _set_chip(self, key, text, state):
        dot, txt = self.status_chips[key]
        dot.setStyleSheet("color: {};".format(self._CHIP_COLORS.get(state, "off")))
        txt.setText(text)

    def _set_camera_status(self, text, state="on"):
        self._set_chip("camera", "Camera · " + text, state)

    def _set_led_status(self, text, state="on"):
        self._set_chip("led", "LED · " + text, state)

    def _set_seg_state(self, lab, state):
        lab.setProperty("state", state)
        s = lab.style()
        s.unpolish(lab)
        s.polish(lab)

    def _update_step_indicator(self, idx):
        """idx: -1 = before the workflow (start page), else step index."""
        for i, (_name, lab) in enumerate(self.step_segments):
            if idx >= 0 and i < idx:
                state = "done"
            elif i == idx:
                state = "active"
            else:
                state = "future"
            self._set_seg_state(lab, state)

    def _install_focus_assist_switch(self):
        """Replace the placeholder Focus Assist button (from the .ui)
        with a real macOS-style Switch widget in the same layout slot."""
        from skeleton.switch_widget import Switch
        btn = self.focusAssistToggle
        parent_lay = btn.parent().layout()
        idx = parent_lay.indexOf(btn)
        sw = Switch("Focus Assist")
        sw.setChecked(True)
        parent_lay.insertWidget(idx, sw)
        btn.deleteLater()
        self.focusAssist = sw

    def _set_starting_info(self, text):
        """Render the start-page intro as styled HTML: KAIRO hero title,
        a micro-label, and the body text (first 'Welcome' line dropped)."""
        import html as _html
        lines = [l for l in (text or "").strip().split("\n")
                 if l.strip() and not l.strip().lower().startswith("welcome to")]
        body = "<br>".join(_html.escape(l).replace("  ", "&nbsp;&nbsp;")
                           for l in lines)
        self.startingInfo.setHtml(
            '<div style="font-size:26px; font-weight:700; color:#f5f5f7;'
            ' letter-spacing:3px;">KAIRO</div>'
            '<div style="font-size:10px; color:#6e6e73; letter-spacing:2px;'
            ' margin:6px 0 22px 0;">MULTISPECTRAL CAPTURE &nbsp;&middot;&nbsp; '
            'BY TOM SHRIEVE</div>'
            '<div style="font-size:13px; line-height:1.65; color:#c7c7cc;">'
            + body + "</div>"
        )

    def initialize_cameras(self):
        """
        Automatically selects a camera: probes each backend in priority
        order and uses the first one that connects. Every detection result
        is reported in the start-page text so the user can see what the
        app found and why this camera was chosen. Falls back to the mock
        camera (hardware-free demo mode) when nothing is available.
        """
        skipped = []
        for label, factory in CAMERA_BACKENDS:
            try:
                self.camera_control = factory()
            except ValueError as e:
                skipped.append("{}: {}".format(label, e))
                continue
            except Exception as e:
                skipped.append("{}: unexpected error ({})".format(label, e))
                continue

            model = getattr(self.camera_control, "camera_model", "") or ""
            selected = label + ((" — " + model) if model else "")
            self._set_camera_status(selected, "on")
            init_text = self.intro_text + "\nCamera auto-selected: " + selected + "\n"
            for s in skipped:
                init_text += "  · " + s + "\n"
            self._setCameraRadio(label)
            return {"Success": True, "Init text": init_text}

        # No hardware camera found: fall back to mock camera (demo mode)
        self.camera_control = CameraMock()
        self._set_camera_status("Mock (demo)", "warn")
        init_text = (self.intro_text +
                     '\nNo cameras found. Running in MOCK camera mode (demo only).\n')
        for s in skipped:
            init_text += "  · " + s + "\n"
        init_text += ('Connect a Pixelink/Blackfly camera, a PTP DSLR body, or any '
                      'USB camera, then restart the app or select a camera to '
                      'try again.\n')
        return {"Success": True, "Init text": init_text, "Mock": True}

    def _setCameraRadio(self, label):
        """Check the Camera Options radio button matching the selected backend."""
        radios = {
            "Pixelink": self.pixilinkSelect,
            "FLIR Blackfly": self.blackflySelect,
            "DSLR (gphoto2)": self.gphotoSelect,
            "Generic camera (OpenCV)": self.opencvSelect,
        }
        radio = radios.get(label)
        if radio is not None:
            radio.setChecked(True)

    '''Builds the macOS-style menu bar (app menu, standard Edit, Help)'''

    def buildMenuBar(self):
        """
        Adds the macOS menu bar: the first menu merges into the system
        app menu on macOS (About + Quit); the Edit menu gets the standard
        editing actions; Help links to the MISHA project page.
        """
        from PyQt5.QtWidgets import QAction
        from PyQt5.QtGui import QDesktopServices, QKeySequence
        from PyQt5.QtCore import QUrl

        menubar = self.menuBar()

        # App menu (merged into the macOS application menu)
        app_menu = menubar.addMenu("Kairo")
        app_menu.addAction("About Kairo").triggered.connect(
            self.showAbout)
        quit_action = app_menu.addAction("Quit")
        quit_action.setMenuRole(QAction.QuitRole)  # native ⌘Q on macOS

        # Standard Edit menu (native shortcuts via QKeySequence standard keys)
        edit_menu = menubar.addMenu("Edit")
        for label, key, command in (
                ("Cut", QKeySequence.Cut, "cut"),
                ("Copy", QKeySequence.Copy, "copy"),
                ("Paste", QKeySequence.Paste, "paste"),
                ("Select All", QKeySequence.SelectAll, "selectAll")):
            action = edit_menu.addAction(label)
            action.setShortcut(key)
            action.triggered.connect(
                lambda _checked=False, c=command: self._sendEditCommand(c))

        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("MISHA Project Website").triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://chipr2022.wordpress.com")))
        help_menu.addAction("About Kairo").triggered.connect(
            self.showAboutKairo)

    '''Sends a cut/copy/paste/selectAll command to the focused widget'''

    def _sendEditCommand(self, command):
        focused = QtWidgets.QApplication.focusWidget()
        if focused is not None and hasattr(focused, command):
            getattr(focused, command)()

    '''Shows the About dialog with full credits'''

    def showAbout(self):
        QtWidgets.QMessageBox.about(
            self, "About Kairo",
            '<h3>Kairo</h3>'
            '<p>A low-cost, end-to-end multispectral imaging system '
            'designed and built by <b>Tom Shrieve</b>.</p>'
            '<p>Kairo is based on <b>MISHA</b> — the <i>Multispectral '
            'Imaging System for Historical Artifacts</i>, developed by '
            'RIT\'s Imaging Science and Museum Studies Programs to image '
            'small-format historical documents, sheets, and leaf '
            'collections with overwritten, faded, or unreadable text.</p>'
            '<p>Original MISHA authors: Sai Keshav Sasanapuri, Cecelia '
            'Ahrens, Mallory Bridge, Eric Gao, Robert Maron.</p>'
            '<p>RIT contacts: David Messinger and Juilee Decker. '
            'MISHA website: <a href="https://chipr2022.wordpress.com">'
            'chipr2022.wordpress.com</a></p>')

    '''Shows the About dialog for the Kairo release'''

    def showAboutKairo(self):
        QtWidgets.QMessageBox.about(
            self, "About Kairo",
            '<h3>Kairo</h3>'
            '<p>Designed and built by <b>Tom Shrieve</b> — a '
            'cross-platform (macOS / Linux / Windows) release of MISHA '
            'Image Capture.</p>'
            '<ul>'
            '<li>Automatic camera selection: Pixelink, FLIR Blackfly, '
            'PTP DSLR bodies (gphoto2), any USB camera (OpenCV), and a '
            'hardware-free mock demo mode</li>'
            '<li>macOS-native application styling</li>'
            '<li>float32/uint16 imaging pipeline</li>'
            '</ul>')

    '''Checks if camera is initialized'''

    def check_if_camera_is_initialized(self):
        if self.camera_control is None:
            return {"Success": False, "Reason": "Camera control is None"}
        elif not self.camera_control.check_camera_initialized():
            return {"Success": False, "Reason": "Camera not initialized"}
        else:
            return {"Success": True, "Reason": "This code is literally awesome!"}

    '''Initializes all the individual operations.'''

    def setOperations(self):
        from operations.led_test_mode import TestLEDMode
        self.led_op = TestLEDMode()
        self.led_op.set_main(self)

        from operations.noise_operation import NoiseOp
        self.noise_op = NoiseOp()
        self.noise_op.set_main(self)

        from operations.focus_operation import FocusOp
        self.focus_op = FocusOp()
        self.focus_op.set_main(self)

        from operations.light_operation import LightOp
        self.light_op = LightOp()
        self.light_op.set_main(self)

        from operations.object_operation import ObjectOp
        self.object_op = ObjectOp()
        self.object_op.set_main(self)

        from operations.flats_operation import FlatsOp
        self.flats_op = FlatsOp()
        self.flats_op.set_main(self)

        from operations.edit_operation import EditOp
        self.edit_op = EditOp()
        self.edit_op.set_main(self)

        from operations.finish_operation import FinishOp
        self.finish_op = FinishOp()
        self.finish_op.set_main(self)

        from skeleton.progress_dialog import ProgressDialog
        self.progress_box = ProgressDialog(self, 'Running Operation')

        from skeleton.message_box import MessageBox
        self.message_box = MessageBox(self)

    '''Calls all the button connection/initializaton funcutions divided by what page they appear on'''

    def connectButtons(self):
        self.connectStartingButtons()
        self.connectMetadataButtons()
        self.connectNoiseButtons()
        self.connectFocusButtons()
        self.connectLightButtons()
        self.connectObjectButtons()
        self.connectFlatsButtons()
        self.connectEditButtons()
        self.connectFinishButtons()

    '''Connects all the buttons for the starting page to their respective function'''

    def connectStartingButtons(self):
        self.testLEDsButton.clicked.connect(lambda: self.testLEDsClicked())
        self.cancelLEDsButton.clicked.connect(lambda: self.testCanceled())
        self.startButton.clicked.connect(lambda: self.startButtonClicked())
        self.LEDversion1.clicked.connect(lambda: self.LEDvSelected('Version 1'))
        self.LEDversion2.clicked.connect(lambda: self.LEDvSelected('Version 2'))
        self.blackflySelect.clicked.connect(lambda: self.cameraSelected("Flir"))
        self.pixilinkSelect.clicked.connect(lambda: self.cameraSelected("Pixelink"))
        self.opencvSelect.clicked.connect(lambda: self.cameraSelected("OpenCV"))
        self.gphotoSelect.clicked.connect(lambda: self.cameraSelected("Gphoto2"))

    '''function connects start button to it's functionality'''

    def startButtonClicked(self):
        starting_info_plain_text = self.startingInfo.toPlainText().strip().lower()
        if starting_info_plain_text == "misha party mode":
            basedir = os.path.dirname(__file__)
            video_path = os.path.join(basedir, "skeleton", "MISHA Party mode.mp4")
            if os.path.exists(video_path):
                # Cross-platform: 'open' on macOS, 'xdg-open' on Linux, os.startfile on Windows
                if sys.platform == "darwin":
                    subprocess.Popen(["open", video_path])
                elif sys.platform.startswith("linux"):
                    subprocess.Popen(["xdg-open", video_path])
                elif sys.platform == "win32":
                    os.startfile(video_path)
            self._set_starting_info(self.intro_text)
        elif starting_info_plain_text == "bella mode":
            self.pages.setStyleSheet("background-color: rgb(255, 170, 255);")
            self._set_starting_info(self.intro_text)
        elif not self.check_if_camera_is_initialized()["Success"]:
            self.message_box.show_error(message="Camera not connected. "
                                                "Ensure wired connection and select camera to try again.")
        elif isinstance(self.led_control, LEDMock) and not isinstance(self.camera_control, CameraMock):
            # Real camera but no LED panel: CAMERA TEST MODE. The LED
            # controller is a no-op mock, so per-band LED switching is
            # skipped and all bands are captured under continuous/ambient
            # light — enough to exercise the full camera pipeline.
            self.message_box.show_warning(
                title="Camera Test Mode",
                message="No LED panel detected.\n\nContinuing in CAMERA TEST "
                        "MODE: per-band LED switching is disabled and all "
                        "bands will be captured under continuous/ambient "
                        "light.\n\nConnect the LED panel later and select its "
                        "version for full multispectral capture.")
            self.setPageWithinPage(self.pages, self.capturingPage,
                                   self.capturingOps, self.metadataOp)
        else:
            # Either a real LED panel, or full demo mode (mock camera + mock LEDs)
            self.setPageWithinPage(self.pages, self.capturingPage, self.capturingOps, self.metadataOp)
    '''Sets the LED panel version to version 1'''

    def LEDvSelected(self, version='Version 2'):
        try:
            if isinstance(self.led_control, LEDMock):  # If it had previously failed to connect to the LEDs
                self.led_control = LEDController()

            if version == 'Version 1':
                # Different versions have different LED wavelengths
                self.led_control.wavelength_list = ['365', '385', '395', '420',
                                                    '450', '470', '490', '520',
                                                    '560', '590', '615', '630',
                                                    '660', '730', '850', '940']
            elif version == 'Version 2':
                # Different versions have different LED wavelengths
                self.led_control.wavelength_list = ['365', '385', '395', '420',
                                                    '450', '470', '500', '530',
                                                    '560', '590', '615', '630',
                                                    '660', '730', '850', '940']

            self.message_box.show_info(message="LEDs connected successfully")
            self._set_starting_info(self.intro_text + '\n{} LED panel initialization successful\n'.format(version))
        except ValueError as e:
            if isinstance(self.camera_control, CameraMock):
                # Demo mode: keep the mock LEDs so the full flow stays usable
                self._set_starting_info(self.intro_text +
                                          '\nRunning in MOCK LED mode (demo only). '
                                          'No LED panel detected.\n')
                return
            self._set_starting_info(self.intro_text + '\nLED panel initialization failed, ensure wired '
                                                        'connection to computer and select LED version to try '
                                                        'again.\n')
            self.message_box.show_error(message="LED panel initialization failed")

    def cameraSelected(self, camera='Flir'):
        """(Re)initialize the selected camera type and update the status text."""
        try:
            if camera == 'Flir':
                self.camera_control = BlackflyController()
            elif camera == 'Pixelink':
                self.camera_control = PixilinkController()
            elif camera == 'OpenCV':
                self.camera_control = OpenCVController()
            elif camera == 'Gphoto2':
                self.camera_control = Gphoto2Controller()
            self._set_starting_info(self.intro_text +
                                      '\n{} camera initialization successful\n'.format(camera))
            self.message_box.show_info(message="Camera connected successfully")
        except ValueError:
            self._set_starting_info(self.intro_text + '\n{} camera initialization failed, ensure wired '
                                                        'connection to computer and try again.\n'.format(camera))
            self.message_box.show_error(message="Camera initialization failed")

    '''Connects all the buttons for the metadata page to their respective function and fills in the date'''

    def connectMetadataButtons(self):
        self.metadataStartOverButton.clicked.connect(lambda: self.startOverClicked())
        self.metadataClearButton.clicked.connect(lambda: self.metadataClear())
        self.metadataContinueButton.clicked.connect(lambda: self.metadataContinue())
        today = str(date.today())
        self.dateInput.setText(today)
        self.metadata["date"] = today

    '''Clears all previously entered metadata information and refills in the date'''

    def metadataClear(self):
        today = str(date.today())
        self.dateInput.setText(today)
        self.metadata["date"] = today
        self.titleInput.setText("")  # del
        self.institutionOrOwnerInput.setText("")  # del
        self.identifyingNumberInput.setText("")
        self.catalogNumberInput.setText("")
        self.artistInput.setText("")
        self.creationDateInput.setText("")
        self.creditLineInput.setText("")
        self.materialInput.setText("")
        self.measurementLInput.setText("")
        self.measurementWInput.setText("")
        self.operatorInput.setText("")
        self.notesInput.setText("")
        self.metadata = {}

    '''
    Saves all entered metadata information and moves to the next page
    UNLESS required information has been left out
        THEN changes label for left out info to red text color
    '''

    def metadataContinue(self):
        self.metadata = {
            "title": self.titleInput.text(),
            "institutionOrOwner": self.institutionOrOwnerInput.text(),
            "date": self.dateInput.text(),
            "identifyingNumber": self.identifyingNumberInput.text(),
            "catalogNumber": self.catalogNumberInput.text(),
            "artist": self.artistInput.text(),
            "creationDate": self.creationDateInput.text(),
            "creditLine": self.creditLineInput.text(),
            "material": self.materialInput.text(),
            "measurementLengthCM": self.measurementLInput.text(),
            "measurementWidthCM": self.measurementWInput.text(),
            "operator": self.operatorInput.text(),
            "notes": self.notesInput.text(),
        }
        # Checks required info has been filled out
        if (self.metadata["title"] == '' or
                self.metadata["institutionOrOwner"] == '' or
                self.metadata["date"] == ''):

            if self.metadata["title"] == '':
                self.titleLabel.setStyleSheet('color:rgb(255, 0, 0);')
            else:
                self.titleLabel.setStyleSheet('color:rgb(0, 0, 0);')

            if self.metadata["institutionOrOwner"] == '':
                self.institutionOrOwnerLabel.setStyleSheet('color:rgb(255, 0, 0);')
            else:
                self.institutionOrOwnerLabel.setStyleSheet('color:rgb(0, 0, 0);')

            if self.metadata["date"] == '':
                self.dateLabel.setStyleSheet('color:rgb(255, 0, 0);')
            else:
                self.dateLabel.setStyleSheet('color:rgb(0, 0, 0);')
        else:
            # resets color
            self.titleLabel.setStyleSheet('color:rgb(0, 0, 0);')
            self.institutionOrOwnerLabel.setStyleSheet('color:rgb(0, 0, 0);')
            self.dateLabel.setStyleSheet('color:rgb(0, 0, 0);')
            # moves to initial info step within next page
            if len(self.cube_builder.noise) == 0:
                self.useExistingNoiseButton.setEnabled(False)
            self.setPageWithinPage(self.capturingOps, self.noiseOp, self.noiseSteps, self.noiseStep0)

    '''Connects all the buttons for the noise page to their respective function'''

    def connectNoiseButtons(self):
        self.noiseStartOverButton.clicked.connect(lambda: self.startOverClicked())
        self.noiseSkipButton.clicked.connect(lambda: self.skipNoiseClicked())
        self.useExistingNoiseButton.clicked.connect(lambda: self.useExistingNoiseClicked())
        self.noiseBackButton.clicked.connect(lambda: self.noiseBackButtonClicked())
        self.noiseStartButton.clicked.connect(lambda: self.noiseStart())
        self.noiseCancelButton.clicked.connect(lambda: self.cancelOp(self.noiseSteps, self.noiseStep0, self.noise_op))
        self.noiseContinueButton.clicked.connect(lambda: self.noiseContinue())
        self.noiseRetakeButton.clicked.connect(lambda: self.noiseStart())

    '''Skip noise selected. Remove existing noise'''

    def skipNoiseClicked(self):
        self.cube_builder.noise = []
        self.useExistingNoiseButton.setEnabled(False)
        self.setPageWithinPage(self.capturingOps, self.focusOp, self.focusSteps, self.focusStep0)

    '''uses existing noise and goes to next step'''

    def useExistingNoiseClicked(self):
        self.setPageWithinPage(self.capturingOps, self.focusOp, self.focusSteps, self.focusStep0)

    '''Goes back to previous step before noise'''

    def noiseBackButtonClicked(self):
        self.setPageWithinPage(self.pages, self.capturingPage, self.capturingOps, self.metadataOp)

    '''Starts noise operation and moves to the noise display step within noise page'''

    def noiseStart(self):
        self.noise_op.on_start()
        self.setPage(self.noiseSteps, self.noiseStep1)

    '''Finishes noise operation and moves to focus operation page, initial infomation step'''

    def noiseContinue(self):
        self.noise_op.finished()
        if len(self.cube_builder.noise) != 0:
            self.useExistingNoiseButton.setEnabled(True)
        self.setPageWithinPage(self.capturingOps, self.focusOp, self.focusSteps, self.focusStep0)

    '''Connects all the buttons for the focus page to their respective function'''

    def connectFocusButtons(self):
        self.focusStartOverButton.clicked.connect(lambda: self.startOverClicked())
        self.focusBackButton.clicked.connect(lambda: self.focusBackButtonClicked())
        self.focusSkipButton.clicked.connect(lambda: self.focusContinue())
        self.focusStartButton.clicked.connect(lambda: self.focusStart())
        self.focusCancelButton.clicked.connect(lambda: self.cancelOp(self.focusSteps, self.focusStep0, self.focus_op))
        self.focusContinueButton.clicked.connect(
            lambda: (
                self.focus_op.cancel(),
                self.focusContinue()
            )
        )
        self.focusZoomFactor.valueChanged.connect(self.updateFocusZoomFactor)
        self.focusAssist.toggled.connect(self.updateFocusAssist)

    '''Starts focus operation and moves to the focus display step within focus page'''

    def focusStart(self):
        self.focus_op.on_start()
        self.setPage(self.focusSteps, self.focusStep1)

    '''goes back to noise step'''

    def focusBackButtonClicked(self):
        if len(self.cube_builder.noise) != 0:
            self.useExistingNoiseButton.setEnabled(True)
        self.setPageWithinPage(self.capturingOps, self.noiseOp, self.noiseSteps, self.noiseStep0)

    '''Update zoom factor in focus operation triggered by slider change'''

    def updateFocusZoomFactor(self, value):
        self.focus_op.updateZoomFactor(value)

    '''Forward the Focus Assist (peaking) toggle to the running focus worker'''

    def updateFocusAssist(self, enabled):
        if self.focus_op is not None and getattr(self.focus_op, "worker", None) is not None:
            self.focus_op.worker.focus_assist = enabled

    '''Finishes focus operation and moves to light operation page, initial infomation step'''

    def focusContinue(self):
        self.lightPageTitle.setText("Adjust Camera Exposure")
        self.saveProfileButton.setEnabled(False)
        self.lightNext1Button.setEnabled(False)
        self.skipBands.setChecked(True)
        self.resetLightsDisplay()
        self.resetWaveIndex()
        self.setPageWithinPage(self.capturingOps, self.lightOp, self.lightSteps, self.lightStep0)

    '''Starts light operation and moves to the light display step within light page'''

    def connectLightButtons(self):
        self.singleBand.clicked.connect(lambda: self.singleBand.setChecked(True))
        self.lightsBackButton.clicked.connect(lambda: self.lightsBackButtonClicked())
        self.allBands.clicked.connect(lambda: self.allBands.setChecked(True))
        self.skipBands.clicked.connect(lambda: self.skipBands.setChecked(True))
        self.lightStartOverButton.clicked.connect(lambda: self.startOverClicked())
        self.lightNext0Button.clicked.connect(
            lambda: (
                self.useExistingExposuresButton.setEnabled(True),
                self.lightStart()
            )
        )
        self.useExistingExposuresButton.clicked.connect(
            lambda: (
                self.object_op.updateExposureDisplay(),
                self.setPageWithinPage(self.capturingOps, self.objectOp, self.objectSteps, self.objectStep0)
            )
        )
        self.lightCancelButton.clicked.connect(lambda: self.lightCancelButtonClicked())
        self.lightSkip1Button.clicked.connect(
            lambda: (
                self.light_op.cancel(),
                self.object_op.updateExposureDisplay(),
                self.setPageWithinPage(self.capturingOps, self.objectOp, self.objectSteps, self.objectStep0)
            )
        )
        self.lightNext1Button.clicked.connect(
            lambda: (
                self.light_op.finished(),
                self.lightsFinished()
            )
        )
        self.saveProfileButton.clicked.connect(lambda: self.saveProfileSelected())
        self.loadProfileButton.clicked.connect(lambda: self.loadProfileSelected())
        self.lightLevel0.clicked.connect(lambda: self.lightLevelSelected1(1.0))
        self.lightLevel1.clicked.connect(lambda: self.lightLevelSelected1(0.6))
        self.lightLevel2.clicked.connect(lambda: self.lightLevelSelected1(1.5))
        self.lightLevel3.clicked.connect(lambda: self.lightLevelSelected1(2.0))

    '''moves back to beginning of set exposures step'''

    def lightCancelButtonClicked(self):
        self.lightPageTitle.setText("Adjust Camera Exposure"),
        self.lightNext1Button.setEnabled(False),
        self.resetWaveIndex(),
        self.resetLightsDisplay(),
        self.cancelOp(self.lightSteps, self.lightStep0, self.light_op)

    '''light operation start helper function to decide process of capture'''

    def lightStart(self):
        self.camera_control.reset_exposure()
        if self.singleBand.isChecked():
            self.waveIndex = 8
            self.disconnectLightLevels()
            self.lightLevel0.clicked.connect(lambda: self.lightLevelSelected1(1.0))
            self.lightLevel1.clicked.connect(lambda: self.lightLevelSelected1(0.6))
            self.lightLevel2.clicked.connect(lambda: self.lightLevelSelected1(1.5))
            self.lightLevel3.clicked.connect(lambda: self.lightLevelSelected1(2.0))
            self.__lightStart()
        elif self.allBands.isChecked():
            self.disconnectLightLevels()
            self.lightLevel0.clicked.connect(lambda: self.lightLevelSelected2(1.0))
            self.lightLevel1.clicked.connect(lambda: self.lightLevelSelected2(0.6))
            self.lightLevel2.clicked.connect(lambda: self.lightLevelSelected2(1.5))
            self.lightLevel3.clicked.connect(lambda: self.lightLevelSelected2(2.0))
            self.__lightStart()
        else:
            self.object_op.updateExposureDisplay()
            self.setPageWithinPage(self.capturingOps, self.objectOp, self.objectSteps, self.objectStep0)

    '''Starts light operation and moves to the light display step within light page'''

    def __lightStart(self):
        # Initialize the camera
        self.camera_control.initialize_camera()
        self.light_op.on_start(self.waveIndex)
        self.setPage(self.lightSteps, self.lightStep1)

    '''goes back to focus step'''

    def lightsBackButtonClicked(self):
        self.setPageWithinPage(self.capturingOps, self.focusOp, self.focusSteps, self.focusStep0)

    '''disable light levels'''

    def disableLightLevels(self):
        self.lightLevel0.setEnabled(False)
        self.lightLevel1.setEnabled(False)
        self.lightLevel2.setEnabled(False)
        self.lightLevel3.setEnabled(False)

    '''Saves the selected light level'''

    def lightLevelSelected1(self, num):
        self.light_op.save_all_levels(num)
        self.disableLightLevels()
        self.lightNext1Button.setEnabled(True)
        self.lightPageTitle.setText("Capturing Done. Click next to continue")

    '''Saves the selected light level when "allBands" option was selected'''

    def lightLevelSelected2(self, num):
        self.light_op.save_level(num, self.waveIndex)
        self.disableLightLevels()
        if self.updateWaveIndex():
            self.resetLightsDisplay()
            self.light_op.on_start(self.waveIndex)
            self.setPage(self.lightSteps, self.lightStep1)
        else:
            self.lightNext1Button.setEnabled(True)
            self.saveProfileButton.setEnabled(True)
            self.lightPageTitle.setText("Capturing Done. Click next to continue")

    '''Disconnect lightLevel push buttons'''

    def disconnectLightLevels(self):
        self.lightLevel0.clicked.disconnect()
        self.lightLevel1.clicked.disconnect()
        self.lightLevel2.clicked.disconnect()
        self.lightLevel3.clicked.disconnect()

    '''Update wavelength Index'''

    def updateWaveIndex(self):
        if self.waveIndex < 15:
            self.waveIndex += 1
            return True
        else:
            return False

    '''Resets the waveIndex to 0'''

    def resetWaveIndex(self):
        self.waveIndex = 0

    '''Resets all the 4 displays and removes images from them'''

    def resetLightsDisplay(self):
        icon = QIcon()
        size = QSize()
        self.lightLevel0.setIcon(icon)
        self.lightLevel0.setIconSize(size)
        self.lightLevel1.setIcon(icon)
        self.lightLevel1.setIconSize(size)
        self.lightLevel2.setIcon(icon)
        self.lightLevel2.setIconSize(size)
        self.lightLevel3.setIcon(icon)
        self.lightLevel3.setIconSize(size)

    '''Ends lights step and prepares page for object capture'''

    def lightsFinished(self):
        self.object_op.updateExposureDisplay()
        self.setPageWithinPage(self.capturingOps, self.objectOp, self.objectSteps, self.objectStep0)

    ''' saves the exposure profile'''

    def saveProfileSelected(self):
        self.light_op.saveProfile(self.fileName.text())
        self.light_op.finished()
        self.lightsFinished()

    '''loads a exposure profile from the system'''

    def loadProfileSelected(self):
        if self.light_op.loadProfile():
            self.lightPageTitle.setText("Adjust Camera Exposure")
            self.object_op.updateExposureDisplay()
            self.setPageWithinPage(self.capturingOps, self.objectOp, self.objectSteps, self.objectStep0)

    '''Connects all the buttons for the object page to their respective function'''

    def connectObjectButtons(self):
        self.objectStartOverButton.clicked.connect(lambda: self.startOverClicked())
        self.objectBackButton.clicked.connect(lambda: self.objectBackButtonClicked())
        self.objectNextButton.clicked.connect(lambda: self.objectStart())
        self.objectCancelButton.clicked.connect(
            lambda: self.cancelOp(self.objectSteps, self.objectStep0, self.object_op))
        self.objectStartOver2Button.clicked.connect(
            lambda: (
                self.object_op.cancel(),
                self.startOverClicked()
            )
        )
        self.objectContinueButton.clicked.connect(lambda: self.objectContinue())
        self.objectRedoButton.clicked.connect(lambda: self.objectStart())
        self.objectStartCaptureButton.clicked.connect(lambda: self.startObjectCapture())
        self.objectComboBox.addItems(self.led_control.wavelength_list)
        self.objectComboBox.currentIndexChanged.connect(lambda: self.objectDisplay(self.objectComboBox.currentIndex()))
        self.reselectExposures.clicked.connect(lambda: self.reselectExposuresClicked())

    '''Starts object operation and moves to the object display step within object page'''

    def objectStart(self):
        self.objectStartCaptureButton.setEnabled(True)
        self.object_op.on_start()
        self.setPage(self.objectSteps, self.objectStep1)

    '''goes back to exposures step'''

    def objectBackButtonClicked(self):
        self.focusContinue()

    '''Start Capturing images in object capture step'''

    def startObjectCapture(self):
        self.object_op.startObjectCapture()

    '''Changes the wavelength image to display in object display'''

    def objectDisplay(self, i):
        self.objectComboBox.setCurrentIndex(i)
        frame = self.cube_builder.final_array[:, :, i]
        img = self.camera_control.convert_nparray_to_QPixmap(frame)
        scene = QtWidgets.QGraphicsScene()
        self.objectStep2View.setScene(scene)
        self.objectStep2View.setHidden(False)
        scene.addPixmap(
            img.scaled(self.objectStep2View.width(), self.objectStep2View.height(), QtCore.Qt.KeepAspectRatio))

    '''Finishes object operation and moves to flats operation page, initial infomation step'''

    def objectContinue(self):
        if len(self.cube_builder.flats_array) == 0:
            self.useExistingFlatsButton.setEnabled(False)
        else:
            self.useExistingFlatsButton.setEnabled(True)
        self.setPageWithinPage(self.capturingOps, self.flatsOp, self.flatsSteps, self.flatsStep0)

    '''Sends back to exposure setting page to change exposures'''

    def reselectExposuresClicked(self):
        self.camera_control.reset_exposure()
        self.cube_builder.re_capture()
        self.focusContinue()

    '''Connects all the buttons for the flats page to their respective function'''

    def connectFlatsButtons(self):
        self.flatsStartOverButton.clicked.connect(lambda: self.startOverClicked())
        self.useExistingFlatsButton.clicked.connect(lambda: self.useExistingFlatsClicked())
        self.flatsSkip0Button.clicked.connect(
            lambda: (
                self.flatsSkip()
            )
        )
        self.flatsNextButton.clicked.connect(lambda: self.flatsStart())
        self.flatsBackButton.clicked.connect(lambda: self.flatsBackButtonClicked())
        self.flatsCancelButton.clicked.connect(lambda: self.cancelOp(self.flatsSteps, self.flatsStep0, self.flats_op))
        self.flatsStartOver2Button.clicked.connect(
            lambda: (
                self.flats_op.cancel(),
                self.startOverClicked()
            )
        )
        self.flatsContinueButton.clicked.connect(lambda: self.flatsContinue())
        self.flatsRedoButton.clicked.connect(lambda: self.flatsStart())
        self.flatsStartCaptureButton.clicked.connect(lambda: self.startFlatsCapture())
        self.flatsComboBox.addItems(self.led_control.wavelength_list)
        self.flatsComboBox.currentIndexChanged.connect(lambda: self.flatsDisplay(self.flatsComboBox.currentIndex()))

    '''Skips the flats operation and sets the edit display'''

    def flatsSkip(self):
        self.cube_builder.flats_array = []
        self.cube_builder.apply_flats(self)
        self.edit_op.on_start()
        self.setPage(self.capturingOps, self.editOp)
        self.editDisplay(0)

    '''uses existing flats and goes to next step'''

    def useExistingFlatsClicked(self):
        self.cube_builder.apply_flats(self)
        self.edit_op.on_start()
        self.setPage(self.capturingOps, self.editOp)
        self.editDisplay(0)

    '''goes back to object step'''

    def flatsBackButtonClicked(self):
        self.setPageWithinPage(self.capturingOps, self.objectOp, self.objectSteps, self.objectStep0)

    '''Starts flats operation and moves to the flats display step within flats page'''

    def flatsStart(self):
        self.flatsStartCaptureButton.setEnabled(True)
        self.cube_builder.revert_final(self)
        self.flats_op.on_start()
        self.setPage(self.flatsSteps, self.flatsStep1)

    '''Start capturing flats images'''

    def startFlatsCapture(self):
        self.flats_op.startFlatsCapture()

    '''Changes the wavelength image to display in flats display'''

    def flatsDisplay(self, i):
        try:
            self.flatsComboBox.setCurrentIndex(i)
            frame = self.cube_builder.final_array[:, :, i]
            img = self.camera_control.convert_nparray_to_QPixmap(frame)
            scene = QtWidgets.QGraphicsScene()
            self.flatsStep2View.setScene(scene)
            self.flatsStep2View.setHidden(False)
            scene.addPixmap(
                img.scaled(self.flatsStep2View.width(), self.flatsStep2View.height(), QtCore.Qt.KeepAspectRatio))
        except:
            pass

    '''Finishes flats operation and moves to edit operation page and sets the inital display for that page'''

    def flatsContinue(self):
        self.flats_op.finished()
        self.edit_op.on_start()
        self.setPage(self.capturingOps, self.editOp)
        self.editDisplay(0)

    '''Connects all the buttons for the edit page to their respective function'''

    def connectEditButtons(self):
        self.editStartOverButton.clicked.connect(
            lambda: (
                self.edit_op.cancel(),
                self.startOverClicked()
            )
        )
        self.editBackButton.clicked.connect(lambda: self.editBackButtonClicked())
        self.editContinueButton.clicked.connect(lambda: self.editContinue())
        self.rotateButton.clicked.connect(lambda: self.rotate())
        self.cropButton.clicked.connect(lambda: self.crop())
        self.autoButton.clicked.connect(lambda: self.autoCalibrate())
        self.calibrationButton.clicked.connect(lambda: self.calibrate())
        self.editComboBox.addItems(self.led_control.wavelength_list)
        self.editComboBox.currentIndexChanged.connect(lambda: self.editDisplay(self.editComboBox.currentIndex()))
        self.calibrationCancel.clicked.connect(lambda: self.calibrateCancel())

    '''Changes the wavelength image to display in edit display'''

    def editDisplay(self, i):
        self.editComboBox.setCurrentIndex(i)
        frame = self.cube_builder.final_array[:, :, i]
        img = self.camera_control.convert_nparray_to_QPixmap(frame)
        self.edit_op.updateEditView(img)

    '''goes back to flats step'''

    def editBackButtonClicked(self):
        self.cube_builder.revert_final(self)
        self.objectContinue()

    '''Calls the edit rotate function'''

    def rotate(self):
        self.edit_op.rotate()

    '''Calls the edit crop function'''

    def crop(self):
        self.edit_op.crop()

    def cropCancel(self):
        pass

    '''Calls the edit auto calibration function and disables the calibration buttons'''

    def autoCalibrate(self):
        self.autoButton.setEnabled(False)
        self.calibrationButton.setEnabled(False)
        self.edit_op.auto_calibrate()

    '''Calls the edit calibration functon and disables the auto calibration button'''

    def calibrate(self):
        self.autoButton.setEnabled(False)
        self.calibrationButton.setEnabled(False)
        self.performCalibration.setEnabled(True)
        self.calibrationCancel.setEnabled(True)
        self.edit_op.calibrate()

    '''cancels calibration'''

    def calibrateCancel(self):
        self.editDisplay(8)
        self.performCalibration.setEnabled(False)
        self.calibrationCancel.setEnabled(False)
        self.autoButton.setEnabled(True)
        self.calibrationButton.setEnabled(True)

    '''Finishes edit operation and moves to final operation page and sets the inital display for that page'''

    def editContinue(self):
        self.edit_op.finished()
        self.setPage(self.capturingOps, self.finishOp)
        self.finishDisplay(0)

    '''Connects all the buttons for the finish page to their respective function'''

    def connectFinishButtons(self):
        self.finishStartOverButton.clicked.connect(
            lambda: (
                self.finish_op.cancel(),
                self.startOverClicked()
            )
        )
        self.finishFinishButton.clicked.connect(lambda: self.finishFinish())
        self.finishRedoButton.clicked.connect(lambda: self.finishRedo())
        self.finishComboBox.addItems(self.led_control.wavelength_list)
        self.finishComboBox.currentIndexChanged.connect(lambda: self.finishDisplay(self.finishComboBox.currentIndex()))

    '''Changes the wavelength image to display in finish display'''

    def finishDisplay(self, i):
        self.finishComboBox.setCurrentIndex(i)
        frame = self.cube_builder.final_array[:, :, i]
        img = self.camera_control.convert_nparray_to_QPixmap(frame)
        scene = QtWidgets.QGraphicsScene()
        self.finishView.setScene(scene)
        self.finishView.setHidden(False)
        scene.addPixmap(img.scaled(self.finishView.width(), self.finishView.height(), QtCore.Qt.KeepAspectRatio))

    '''Finishes and saves everything'''

    def finishFinish(self):
        self.finishFinishButton.setEnabled(False)
        self.finishStartOverButton.setEnabled(False)
        self.finishRedoButton.setEnabled(False)
        self.finishComboBox.setEnabled(False)
        self.finishInfoText.setEnabled(False)
        self.finish_op.on_start()

    '''Redo imaging session without changing the metadata'''

    def finishRedo(self):
        self.finish_op.cancel()
        self.setPageWithinPage(self.pages, self.capturingPage, self.capturingOps, self.metadataOp)

    '''Sends the UI back to the start'''

    def finishDone(self):
        self.setPage(self.pages, self.startingPage)

    '''Sets the UI to the given page within the given widget'''

    def setPage(self, widget, page):
        widget.setCurrentWidget(page)
        self._update_step_indicator(self._page_index.get(page, -1))

    '''Sets the UI to the given nested pages and widgets'''

    def setPageWithinPage(self, widget1, page1, widget2, page2):
        widget2.setCurrentWidget(page2)
        widget1.setCurrentWidget(page1)

    '''Cancels the entire imaging session and sends the user back to the starting page'''

    def startOverClicked(self):
        self.cube_builder.re_capture()
        self.camera_control.reset_exposure()
        self.useExistingExposuresButton.setEnabled(False)
        self.setPage(self.pages, self.startingPage)

    '''Cancels a operation and sends the user back to the inital info step for that operation'''

    def cancelOp(self, currentOpSteps, goToStep, currentOp=Operation):
        currentOp.cancel()
        self.setPage(currentOpSteps, goToStep)

    '''Starts the test LED process'''

    def testLEDsClicked(self):
        try:
            if isinstance(self.led_control, LEDMock):
                self.message_box.show_error(message="LEDs not connected. "
                                                    "Ensure wired connection and select version to try again.")
            else:
                self.testLEDsButton.setEnabled(False)
                self.cancelLEDsButton.setEnabled(True)
                self.led_op.on_start(self)
        except:
            self._set_starting_info("Error in test LEDs clicked")

    '''Cancels the test LED process'''

    def testCanceled(self):
        try:
            self.cancelLEDsButton.setEnabled(False)
            self.testLEDsButton.setEnabled(True)
            self.led_op.cancel()
            self._set_starting_info(self.intro_text)
        except:
            self._set_starting_info("Error in test LEDs cancel")

    '''Directly begin at any step by giving path to load images'''
    def load_images(self):
        # Dev helper: load a stack of .tif bands from a local directory.
        # Set the path below to your own raw image folder.
        path_to_image_directory = os.path.join(os.path.expanduser("~"), "MISHA data",
                                               "color checker mis images",
                                               "Color_checker_images_DataCube Raw Images")
        extension = ".tif"

        # Get all matching image files sorted by name
        image_files = sorted(
            f for f in os.listdir(path_to_image_directory)
            if f.lower().endswith(extension)
        )

        # Load images and stack along the last axis
        image_stack = []
        for filename in image_files:
            image_path = os.path.join(path_to_image_directory, filename)
            img = tifffile.imread(image_path)

            if img.ndim != 2:
                raise ValueError(f"Image '{filename}' is not grayscale (2D). Got shape {img.shape}")

            image_stack.append(img)

        self.cube_builder.final_array = np.stack(image_stack, axis=-1)  # Shape: (H, W, 16)
        self.cube_builder.img_array = np.stack(image_stack, axis=-1)  # Shape: (H, W, 16)

    '''Destructor of the class. Un-Initialize camera and led '''

    def __del__(self):
        if type(self.led_control) != type(LEDMock()):
            self.led_control.turn_off()
        if self.camera_control is not None:
            self.camera_control.uninitialize_camera()


'''Starts up the Application'''
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # macOS-native look & feel (system font, Apple palette, window icon)
    macos_style.apply(app)

    # Splash screen — Kairo launch card (K mark, wordmark, progress line,
    # copyright). Held for 5 s of real time; the progress line fills over
    # the first 4.5 s so it visibly completes, then rests at 100%.
    # Progress is driven from this loop's wall clock (the same clock that
    # decides when the card closes), so the bar is guaranteed to finish.
    splash = macos_style.KairoSplash(duration_ms=5000, fill_ms=4500)
    t0 = time.time()
    splash.start()
    app.processEvents()

    window = Ui()
    macos_style.apply(app, window)
    remaining = 5.0 - (time.time() - t0)
    while remaining > 0:
        splash.set_progress(min(1.0, (time.time() - t0) / 4.5))
        app.processEvents()
        time.sleep(min(0.05, remaining))
        remaining = 5.0 - (time.time() - t0)
    splash.set_progress(1.0)
    # Guarantee the finished frame is actually painted before the card
    # closes — if camera init consumed the whole hold, the loop above never
    # ran and this is the only repaint that will show the bar at 100%.
    app.processEvents()
    splash.close()
    window.show()
    sys.exit(app.exec_())
