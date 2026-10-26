from operations.operation import Operation
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import time
import numpy as np
import cv2

'''
Focus Operation for Displaying "Live" Images for Camera Focus Adjustment
Written by Sai Keshav Sasanapuri and Cecelia Ahrens;
live view + focus-assist (peaking) extended in Project Kairo.

The worker loops the camera's FAST preview path (capture_preview):
  - DSLRs (gphoto2): the camera's live-view buffer, no shutter fire,
    nothing written to the card.
  - UVC cameras (OpenCV): a normal frame read, already real-time.
Per frame it shows the live view, a zoomed pane, a sharpness score
(Laplacian variance), and — when "Focus Assist" is on — a focus-peaking
overlay that highlights the highest-contrast edges in red, the same
aid mirrorless bodies show on their viewfinder.
'''


class FocusOp(Operation):
    main = None

    def on_start(self):
        # start thread, move worker to thread
        self.main.thread = QThread()
        self.main.worker = FocusWorker()
        self.main.worker.moveToThread(self.main.thread)
        self.main.worker.main = self.main
        # Pick up the current state of the Focus Assist switch
        self.main.worker.focus_assist = self.main.focusAssist.isChecked()

        # connect slots
        self.main.thread.started.connect(self.main.worker.run)
        self.main.worker.mainFrame.connect(self.updateFrame)
        self.main.worker.x2Frame.connect(self.update2XZoomed)
        self.main.worker.sharpness.connect(self.updateSharpness)
        self.main.worker.finished.connect(self.finished)
        self.main.worker.progress_signal.connect(self.updateProgressDialog)
        self.main.worker.message_signal.connect(self.showMessageBox)
        self.main.worker.end_operation.connect(self.end_operation_midway)

        self.main.thread.start()

    '''Cancel Operation'''

    def cancel(self):
        self.main.worker.notCancelled = False
        self.main.led_control.turn_off()
        self.main.thread.quit()

    '''Finish Operation'''

    def finished(self):
        self.main.thread.quit()

    '''end process due to error encountered'''

    def end_operation_midway(self, err_msg):
        self.main.progress_box.start("Cancelling Operation")
        self.main.camera_control.uninitialize_camera()
        self.main.progress_box.stop()
        self.main.message_box.show_error(message=err_msg)
        self.main.cancelOp(self.main.focusSteps, self.main.focusStep0, self.main.focus_op)

    '''Create and show message box'''

    def showMessageBox(self, msg_type, message):
        if msg_type == 'info':
            self.main.message_box.show_info(message=message)
        elif msg_type == 'warning':
            self.main.message_box.show_warning(message=message)
        elif msg_type == 'error':
            self.main.message_box.show_error(message=message)
        elif msg_type == 'question':
            return self.main.message_box.show_question(message=message)

    '''Start or Stop Progress dialog box'''

    def updateProgressDialog(self, message):
        if message == "close":
            self.main.progress_box.stop()
        else:
            self.main.progress_box.start(message)

    '''Update zoom factor in focus page of zoom window'''

    def updateZoomFactor(self, value):
        self.main.worker.zoom_factor = value

    '''Update Main Display'''

    def updateFrame(self, img):
        scene = QtWidgets.QGraphicsScene()
        scene.addPixmap(
            img.scaled(self.main.focusView.width(), self.main.focusView.height(), QtCore.Qt.KeepAspectRatio))
        self.main.focusView.setScene(scene)

    '''Update smaller display for X2 zoomed image'''

    def update2XZoomed(self, img, zoom_factor):
        scene = QtWidgets.QGraphicsScene()
        scene.addPixmap(img.scaled(self.main.focusStep1Zoom1View.width() * zoom_factor,
                                   self.main.focusStep1Zoom1View.height() * zoom_factor,
                                   QtCore.Qt.KeepAspectRatio))
        self.main.focusStep1Zoom1View.setScene(scene)

    '''Update sharpness label'''

    def updateSharpness(self, n):
        self.main.focusStep1Sharpness.setText(f"Sharpness: {n}")


class FocusWorker(QObject):
    mainFrame = pyqtSignal(QPixmap)
    x2Frame = pyqtSignal(QPixmap, int)
    sharpness = pyqtSignal(int)
    notCancelled = True
    main = None
    zoom_factor = 1
    # Focus Assist: red peaking overlay on the highest-contrast edges
    focus_assist = True
    finished = pyqtSignal()
    progress_signal = pyqtSignal(str)
    message_signal = pyqtSignal(str, str)
    end_operation = pyqtSignal(str)

    PEAK_WIDTH = 1280   # working width for peaking / sharpness (fast)

    def _downsample(self, frame, width):
        """Downsample a float32 grayscale frame to the given width."""
        h, w = frame.shape[:2]
        if w > width:
            return cv2.resize(frame, (width, int(h * width / w)),
                              interpolation=cv2.INTER_AREA)
        return frame

    @staticmethod
    def _to_uint8_gray(frame):
        return (frame * 255).clip(0, 255).astype(np.uint8)

    def _peaking_frame(self, frame):
        """
        Focus-assist peaking: return an RGB uint8 frame with the
        highest-contrast edges (top ~2% of the Sobel magnitude, above a
        noise floor) tinted red, so in-focus areas 'pop' on the live
        view — the same aid viewfinders use.
        """
        small = self._downsample(frame, self.PEAK_WIDTH)
        gray = self._to_uint8_gray(small)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.hypot(gx, gy)
        # Top ~2% of edge energy, with a noise floor for flat scenes
        threshold = max(float(np.percentile(mag, 98)), 18.0)
        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        rgb[mag >= threshold] = (0, 0, 255)
        return rgb

    def _sharpness(self, frame):
        """
        Sharpness score: variance of the Laplacian on a downsampled
        frame. Higher = sharper. Cheap enough to run every frame.
        """
        small = self._downsample(frame, 1024)
        gray = self._to_uint8_gray(small)
        return int(round(cv2.Laplacian(gray, cv2.CV_64F).var()))

    def run(self):
        self.progress_signal.emit("Starting Camera")

        # check if camera is initialized
        if not self.main.check_if_camera_is_initialized()["Success"]:
            ret = self.main.initialize_cameras()
            if not ret["Success"]:
                self.progress_signal.emit("close")
                self.end_operation.emit("Failed to connect to camera. Ensure wired connection and try again.")
                return

        # change acquisition mode to continuous
        if self.main.camera_control.acquisition_mode != 'Continuous':
            self.main.camera_control.change_acquisition_mode(mode='Continuous')
        self.main.led_control.turn_on(self.main.led_control.wavelength_list[8])
        self.main.camera_control.change_exposure(self.main.camera_control.exposureArray[8], 8)
        frame_no = -1
        self.main.camera_control.Begin_Acquisition()
        self.progress_signal.emit("close")

        while self.notCancelled:
            # Live view: use the fast preview path (DSLR live-view buffer,
            # or a real-time UVC read). No shutter fire, no card writes.
            ret = self.main.camera_control.capture_preview()
            if not ret["Success"]:
                self.end_operation.emit("Image acquisition failed")
                return

            frame = ret["Image"]
            frame_no += 1

            if self.focus_assist:
                img = self.main.camera_control.convert_nparray_to_QPixmap(
                    self._peaking_frame(frame))
            else:
                img = self.main.camera_control.convert_nparray_to_QPixmap(frame)

            self.mainFrame.emit(img)
            if self.zoom_factor > 1:
                self.x2Frame.emit(img, self.zoom_factor)
            self.sharpness.emit(self._sharpness(frame))

        self.main.camera_control.End_Acquisition()
        self.finished.emit()
