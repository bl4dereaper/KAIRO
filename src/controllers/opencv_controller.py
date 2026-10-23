"""
Generic OpenCV Camera Controller ("most cameras" support)

Captures from any camera OpenCV can open -- USB/webcam-style cameras on
macOS (AVFoundation) or Linux (V4L2), including converted full-spectrum
bodies when they are connected in UVC mode. No vendor SDK required.

Note: exposure is emulated in software (a brightness scale applied to each
frame). Real hardware exposure control through OpenCV is backend-dependent
and not reliable across cameras; discrete per-band exposure mapping is a
Project Kairo roadmap item (see README).

Part of Project Kairo (MISHA-based multispectral imaging).
"""
import cv2
import numpy as np
from controllers.camera_interface import CameraInterface


class OpenCVController(CameraInterface):
    """Camera controller backed by cv2.VideoCapture (generic cameras)."""

    def __init__(self, camera_index: int = 0):
        """
        Open the camera at the given device index.
        :param camera_index: OpenCV device index (0 = default camera).
        :raises ValueError: if the camera cannot be opened.
        """
        self.ORIGINAL_EXPOSURE = 1.0
        self.selected_exposure_array = [self.ORIGINAL_EXPOSURE] * 16
        self.acquisition_mode = "Continuous"
        self._band = 0
        self._exposure_scale = 1.0

        self.capture_device = cv2.VideoCapture(camera_index)
        if not self.capture_device.isOpened():
            self.capture_device.release()
            raise ValueError("OpenCV could not open camera index {}".format(camera_index))

        # Frame dimensions (used for frame bookkeeping / debugging)
        self.frame_width = int(self.capture_device.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.capture_device.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def initialize_camera(self):
        """Re-open the camera if it was released."""
        if self.capture_device is not None and self.capture_device.isOpened():
            return {"Success": True, "Error": None}
        self.capture_device = cv2.VideoCapture(0)
        if not self.capture_device.isOpened():
            return {"Success": False, "Error": "camera could not be opened"}
        return {"Success": True, "Error": None}

    def check_camera_initialized(self) -> bool:
        """True if the underlying device is still open."""
        return bool(self.capture_device is not None and self.capture_device.isOpened())

    def change_acquisition_mode(self, mode: str) -> None:
        """OpenCV streams continuously; mode is recorded only."""
        self.acquisition_mode = mode

    def Begin_Acquisition(self):
        """No-op: the OpenCV stream is continuous."""
        pass

    def End_Acquisition(self):
        """No-op: the OpenCV stream is continuous."""
        pass

    # ------------------------------------------------------------------
    # Exposure (software emulation for generic cameras)
    # ------------------------------------------------------------------

    def change_exposure(self, change, waveIndex):
        """
        Emulate an exposure change by recording a brightness scale for the
        band. Returns the new exposure value (0 on failure).
        """
        if waveIndex is None or waveIndex >= len(self.selected_exposure_array):
            return 0
        new_exposure = self.selected_exposure_array[waveIndex] * change
        self._exposure_scale = new_exposure / self.ORIGINAL_EXPOSURE
        self._band = waveIndex
        return new_exposure

    def reset_exposure(self):
        """Reset the per-band exposure table and the software scale."""
        self.selected_exposure_array = [self.ORIGINAL_EXPOSURE] * 16
        self._exposure_scale = 1.0

    def save_exposure(self, change, waveIndex):
        """Save the per-band exposure after applying a factor."""
        self.selected_exposure_array[waveIndex] = (
            change * self.selected_exposure_array[waveIndex])

    def save_all_exposures(self, change):
        """Apply an exposure factor to all bands."""
        for i in range(len(self.selected_exposure_array)):
            self.selected_exposure_array[i] *= change

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture(self):
        """
        Grab the latest frame and convert it to a float32 grayscale image
        in [0, 1], with the current software exposure scale applied.
        :return: dict {"Success": bool, "Image": np.ndarray | None}
        """
        if not self.check_camera_initialized():
            return {"Success": False, "Image": None}

        # Webcams often return the first frame(s) black; retry a few times
        frame = None
        for _ in range(3):
            ok, bgr = self.capture_device.read()
            if ok and bgr is not None:
                frame = bgr
                break
        if frame is None:
            return {"Success": False, "Image": None}

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        img = gray.astype(np.float32) / 255.0
        if self._exposure_scale != 1.0:
            img = np.clip(img * self._exposure_scale, 0.0, 1.0)
        return {"Success": True, "Image": img}

    def capture_at_exposure(self, exposure, waveIndex):
        """Set the (emulated) exposure for the band, then capture."""
        if self.change_exposure(exposure, waveIndex) == 0:
            return {"Success": False, "Image": None}
        return self.capture()

    def uninitialize_camera(self):
        """Release the camera device."""
        try:
            if self.capture_device is not None:
                self.capture_device.release()
        except Exception:
            pass
        self.capture_device = None
