"""
Camera Interface (abstract base class)

Defines the common contract implemented by every camera controller
(Pixelink, FLIR Blackfly, generic OpenCV, gphoto2 DSLR, and the mock
camera). All capture methods return frames as float32 grayscale arrays
with values normalized to [0, 1] (no demosaic / WB / gamma), so the rest
of the pipeline works identically regardless of hardware.

Based on MISHA (RIT). Written by Sai Keshav Sasanapuri and Cecelia Ahrens;
interface updated in Project Kairo to match the real controller contract.
"""
from abc import ABC, abstractmethod
import cv2
from PyQt5.QtGui import QPixmap, QImage
from scipy import ndimage
import numpy as np


class CameraInterface(ABC):
    """Common interface for MISHA/Kairo camera controllers."""

    ORIGINAL_EXPOSURE = None
    exposure = None
    sharpness = None
    acquisition_mode = None
    # Human-readable model name, set by controllers that can identify it
    # (used for the auto-selection report on the start page)
    camera_model = ""

    # Default per-band exposure table (seconds) used when no profile is loaded.
    # 16 bands, matching the 16 LED wavelengths.
    exposureArray = [0.1, 0.1, 0.1, 0.09,
                     0.05, 0.045, 0.06, 0.072,
                     0.05, 0.18, 0.075, 0.08,
                     0.08, 0.1, 0.06, 0.15]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def initialize_camera(self) -> dict:
        """Initialize/attach the camera. Returns {"Success": bool, "Error": ...}."""
        pass

    @abstractmethod
    def check_camera_initialized(self) -> bool:
        """Return True if the camera is attached and usable."""
        pass

    @abstractmethod
    def uninitialize_camera(self) -> None:
        """Release the camera and any associated resources."""
        pass

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    @abstractmethod
    def change_acquisition_mode(self, mode: str) -> None:
        """Switch between 'SingleFrame' and 'Continuous' acquisition."""
        pass

    @abstractmethod
    def Begin_Acquisition(self) -> None:
        """Start the stream / arm a capture."""
        pass

    @abstractmethod
    def End_Acquisition(self) -> None:
        """Stop the stream."""
        pass

    @abstractmethod
    def capture(self) -> dict:
        """
        Capture one frame.
        :return: {"Success": bool, "Image": np.ndarray float32 [0,1] | None}
        """
        pass

    def capture_preview(self) -> dict:
        """
        Capture one fast live-view / preview frame for display (the
        Focus step). Default: a regular full capture. Controllers with
        a dedicated live-view path (PTP live view, UVC cameras)
        override this for a much higher frame rate.
        :return: same shape as capture()
        """
        return self.capture()

    @abstractmethod
    def capture_at_exposure(self, exposure, waveIndex) -> dict:
        """
        Set the exposure for a band, then capture one frame.
        :return: same shape as capture()
        """
        pass

    # ------------------------------------------------------------------
    # Exposure
    # ------------------------------------------------------------------

    @abstractmethod
    def change_exposure(self, change, waveIndex):
        """
        Apply an exposure factor to a band.
        :return: the new exposure value, or 0 on failure.
        """
        pass

    @abstractmethod
    def reset_exposure(self) -> None:
        """Reset all per-band exposures to their original values."""
        pass

    @abstractmethod
    def save_exposure(self, change, waveIndex) -> None:
        """Persist an exposure factor for a single band."""
        pass

    @abstractmethod
    def save_all_exposures(self, change) -> None:
        """Persist an exposure factor for all bands at once."""
        pass

    def get_exposure(self):
        return self.exposure

    def get_sharpness(self):
        if self.sharpness is None:
            return 0
        return round(self.sharpness)

    # ------------------------------------------------------------------
    # UI display helpers
    # ------------------------------------------------------------------

    def zoom(self, img, zoom):
        """
        Center-crop and zoom an image for the live-view zoom pane.
        :param img: 2D (grayscale) or 3D (RGB) ndarray
        :param zoom: zoom factor (2 = 2x zoom)
        :return: ndarray of the same size as the input
        """
        h, w = img.shape[:2]

        zoom_tuple = (zoom,) * 2 + (1,) * (img.ndim - 2)

        zh = int(np.round(h / zoom))
        zw = int(np.round(w / zoom))
        top = (h - zh) // 2
        left = (w - zw) // 2

        out = ndimage.zoom(img[top:top+zh, left:left+zw], zoom_tuple)

        trim_top = ((out.shape[0] - h) // 2)
        trim_left = ((out.shape[1] - w) // 2)
        out = out[trim_top:trim_top+h, trim_left:trim_left+w]

        return out

    def convert_nparray_to_QPixmap(self, raw_img):
        """
        Convert a captured frame to a QPixmap for display.
        Accepts float32 [0,1] or uint8 grayscale/RGB arrays.
        """
        image = np.copy(raw_img)

        # Normalize 0-1 floats to 0-255 for display
        if image.dtype == np.float32:
            image = (image * 255).astype(np.uint8)

        h, w = image.shape[:2]

        if len(image.shape) == 2:
            frame = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else:
            frame = image
            if len(image.shape) == 3 and h > w:
                frame = np.transpose(frame, (1, 0, 2))
                h, w = w, h

        # QImage requires the buffer to be C-contiguous (the transpose above
        # produces a non-contiguous view)
        frame = np.ascontiguousarray(frame)
        bytesPerLine = 3 * w
        qimage = QImage(frame.data, w, h, bytesPerLine, QImage.Format.Format_RGB888)
        # Keep a reference so the underlying buffer isn't garbage collected
        # before the QPixmap is rendered
        qimage._misha_data = frame  # noqa: SLF001
        return QPixmap(qimage)
