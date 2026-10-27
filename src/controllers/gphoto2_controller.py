"""
gphoto2 DSLR Camera Controller (Kairo)

Supports converted full-spectrum DSLR/mirrorless bodies (Canon, Nikon,
Fuji, and other PTP cameras) over USB using the libgphoto2 python
bindings (PyPI package: gphoto2). One library covers all vendors, which
is why Kairo chose it as the DSLR backend (see README).

Verified live with a Fujifilm GFX 100 (appears to gphoto2 as the
generic "USB PTP Class Camera" driver, which fully supports capture).

v1 behavior:
  - Auto-detects PTP cameras and connects to the first one found
    (reporting its model name for the UI), retrying transient
    USB-claim failures (macOS can be slow to release a claim after a
    crashed process).
  - Captures full-resolution stills in the camera's file format
    (JPEG or RAW), saves the transfer to a temp file at the C level
    (get_data_and_size() in this binding materializes the whole image
    as a Python int list — unusable for 100 MP files), decodes it in
    RAM — JPEG via OpenCV, RAW via rawpy (no camera white balance) —
    then deletes the file from the camera's memory card.
  - If a capture fails (PTP sessions go stale when the camera screen
    sleeps or the USB link hiccups), the controller reconnects once
    and retries.
  - Exposure is emulated in software (brightness scale). Mapping
    exposure floats to discrete camera shutter speeds via the gphoto2
    config tree is a Kairo roadmap item (config-tree caching, RAW
    linear Bayer extraction).

Optional install:
    macOS:  brew install gphoto2 && pip install gphoto2 rawpy
    Linux:  sudo apt install libgphoto2-dev && pip install gphoto2 rawpy

If the dependencies are missing, this module imports cleanly and the
controller raises ValueError, so the app falls back to other cameras.
Written by Tom Shrieve (Kairo); see README.md for full credits.
"""
import os
import tempfile
import time

import numpy as np
import cv2
from controllers.camera_interface import CameraInterface

try:
    import gphoto2
    GPHOTO2_AVAILABLE = True
except Exception:
    gphoto2 = None
    GPHOTO2_AVAILABLE = False

try:
    import rawpy
    RAWPY_AVAILABLE = True
except Exception:
    rawpy = None
    RAWPY_AVAILABLE = False


def _yield_ui():
    """
    Give the GUI event loop a turn if a QApplication exists.

    Called from inside blocking connect-retry sleeps so the launch splash
    (a wall-clock-animated Qt window) can keep repainting while libgphoto2
    is waiting for the USB camera to settle. No-op in headless contexts.
    """
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


class Gphoto2Controller(CameraInterface):
    """Camera controller for PTP/DSLR bodies via libgphoto2."""

    def __init__(self):
        """
        Detect and connect to the first PTP camera found.
        :raises ValueError: if gphoto2 is not installed or no camera is found.
        """
        if not GPHOTO2_AVAILABLE:
            raise ValueError(
                "gphoto2 is not installed. Install with: brew install gphoto2 && "
                "pip install gphoto2")

        self.ORIGINAL_EXPOSURE = 1.0
        self.selected_exposure_array = [self.ORIGINAL_EXPOSURE] * 16
        self.acquisition_mode = "SingleFrame"
        self._band = 0
        self._exposure_scale = 1.0
        self.camera_model = ""
        self.camera = None
        self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self):
        """
        Scan for PTP cameras and connect to the first one found.
        Retries up to 3 times on transient USB-claim failures (macOS
        IOKit can lag in releasing a claim after a process dies).
        """
        try:
            detected = list(gphoto2.Camera.autodetect())
        except Exception as ex:
            raise ValueError("Camera scan failed: {}".format(ex))
        if not detected:
            raise ValueError(
                "No PTP camera found. Power on the camera, connect it via USB, "
                "and make sure it is in PC/remote mode.")

        name, addr = detected[0]
        self.camera_model = name

        last_err = None
        for attempt in range(3):
            cam = None
            try:
                port_info_list = gphoto2.PortInfoList()
                port_info_list.load()
                abilities_list = gphoto2.CameraAbilitiesList()
                abilities_list.load()

                cam = gphoto2.Camera()
                cam.set_port_info(
                    port_info_list[port_info_list.lookup_path(addr)])
                model_idx = abilities_list.lookup_model(name)
                if model_idx is not None and model_idx >= 0:
                    cam.set_abilities(abilities_list[model_idx])
                cam.init()
                self.camera = cam
                return
            except Exception as ex:
                last_err = ex
                if cam is not None:
                    try:
                        cam.exit()
                    except Exception:
                        pass
                if attempt < 2:
                    # Sleep in small slices, yielding to the GUI event loop
                    # each slice so the launch splash keeps animating while
                    # we wait for macOS to release the USB claim.
                    deadline = time.time() + 1.5 * (attempt + 1)
                    while time.time() < deadline:
                        _yield_ui()
                        time.sleep(0.1)
        raise ValueError("Failed to connect to {}: {}".format(name, last_err))

    def initialize_camera(self):
        """Re-open the camera if the connection was lost."""
        if self.camera is not None:
            return {"Success": True, "Error": None}
        try:
            self._connect()
        except ValueError as ex:
            return {"Success": False, "Error": ex}
        return {"Success": True, "Error": None}

    def check_camera_initialized(self) -> bool:
        """True if the gphoto2 camera object exists (connection checked on use)."""
        return self.camera is not None

    def uninitialize_camera(self):
        """Close the gphoto2 camera connection (best-effort; PTP teardown
        can itself fail with [-1] on a stale link, which is harmless)."""
        try:
            if self.camera is not None:
                self.camera.exit()
        except Exception:
            pass
        self.camera = None

    # ------------------------------------------------------------------
    # Acquisition (DSLR capture is single-shot; these are no-ops)
    # ------------------------------------------------------------------

    def change_acquisition_mode(self, mode: str) -> None:
        """Recorded only; DSLR capture is single-shot."""
        self.acquisition_mode = mode

    def Begin_Acquisition(self):
        """No-op for single-shot DSLR capture."""
        pass

    def End_Acquisition(self):
        """No-op for single-shot DSLR capture."""
        pass

    # ------------------------------------------------------------------
    # Exposure (software emulation; discrete shutter mapping is roadmap)
    # ------------------------------------------------------------------

    def change_exposure(self, change, waveIndex):
        """
        Emulate an exposure change with a brightness scale for the band.
        Returns the new exposure value (0 on failure).
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

    @staticmethod
    def _decode_image_file(path: str, mime: str) -> np.ndarray:
        """
        Decode a captured image file into a grayscale float32 array in
        [0, 1]. JPEG decodes via OpenCV; RAW (RAF/CR2/NEF/ARW/...)
        decodes via rawpy with no camera white balance.
        """
        mime = (mime or "").lower()

        # JPEG path
        if "jpeg" in mime or "jpg" in mime:
            bgr = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if bgr is not None:
                return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        # RAW path (also a fallback for odd mime types)
        if RAWPY_AVAILABLE:
            try:
                raw = rawpy.imread(path)
                # No camera white balance; keep the response as linear as possible
                bgr = raw.postprocess(use_camera_wb=False,
                                      output_color=rawpy.ColorSpace.sRGB)
                return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            except Exception:
                pass

        # Last resort: try JPEG decode even if the mime said otherwise
        bgr = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is not None:
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        raise ValueError(
            "Could not decode captured image (mime: {})."
            .format(mime or "unknown"))

    def _capture_once(self) -> dict:
        """
        One capture attempt: fire the shutter, transfer the file to a
        temp file (C-level write), decode it, and delete the file from
        the camera's memory card.
        :return: dict {"Success": bool, "Image": ndarray | None, "Error": str}
        """
        try:
            file_path = self.camera.capture(gphoto2.GP_CAPTURE_IMAGE)
            camera_file = self.camera.file_get(
                file_path.folder, file_path.name, gphoto2.GP_FILE_TYPE_NORMAL)
            mime = camera_file.get_mime_type()

            # Save the capture straight to disk from C: in this binding
            # get_data_and_size() materializes the whole image as a Python
            # list of ints, which explodes memory on 100 MP files.
            fd, tmp_path = tempfile.mkstemp(
                prefix="kairo_gphoto2_", suffix=".bin")
            os.close(fd)
            try:
                camera_file.save(tmp_path)
                img = self._decode_image_file(tmp_path, mime)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            # Free the SD card: remove the capture from camera memory.
            try:
                self.camera.file_delete(file_path.folder, file_path.name)
            except Exception:
                pass

            return {"Success": True, "Image": self._apply_exposure(img), "Error": None}
        except Exception as ex:
            return {"Success": False, "Image": None, "Error": str(ex)}

    def _preview_once(self) -> dict:
        """
        One live-view preview read: pulls the camera's live-view buffer
        (small JPEG on most bodies) without firing the shutter and
        without writing anything to the memory card. This is what the
        Focus step uses for its live view.
        :return: dict {"Success": bool, "Image": ndarray | None, "Error": str}
        """
        try:
            camera_file = self.camera.capture_preview()
            mime = camera_file.get_mime_type()

            fd, tmp_path = tempfile.mkstemp(
                prefix="kairo_gphoto2_prev_", suffix=".bin")
            os.close(fd)
            try:
                camera_file.save(tmp_path)
                img = self._decode_image_file(tmp_path, mime)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            return {"Success": True, "Image": self._apply_exposure(img), "Error": None}
        except Exception as ex:
            return {"Success": False, "Image": None, "Error": str(ex)}

    def _apply_exposure(self, img: np.ndarray) -> np.ndarray:
        """Apply the (software-emulated) exposure scale to a decoded frame."""
        if self._exposure_scale != 1.0 and img is not None:
            img = np.clip(img * self._exposure_scale, 0.0, 1.0).astype(np.float32)
        return img

    def capture(self):
        """
        Capture one full-resolution still and decode it to a float32
        grayscale frame in [0, 1]. On failure (stale PTP session),
        reconnects once and retries.
        :return: dict {"Success": bool, "Image": np.ndarray | None}
        """
        if not self.check_camera_initialized():
            return {"Success": False, "Image": None}

        result = self._capture_once()
        if not result["Success"]:
            # PTP sessions go stale (camera screen sleep, USB hiccup):
            # reconnect once and retry.
            print("gphoto2 capture failed ({}); reconnecting and "
                  "retrying once...".format(result.get("Error")))
            self.uninitialize_camera()
            init = self.initialize_camera()
            if init["Success"]:
                result = self._capture_once()

        if not result["Success"]:
            print("gphoto2 capture failed: {}".format(result.get("Error")))
            return {"Success": False, "Image": None}
        return {"Success": True, "Image": result["Image"]}

    def capture_preview(self):
        """
        Capture one fast live-view preview frame (no shutter fire,
        nothing written to the card) for the Focus step's live view.
        Reconnects once and retries on failure, like capture().
        :return: dict {"Success": bool, "Image": np.ndarray | None}
        """
        if not self.check_camera_initialized():
            return {"Success": False, "Image": None}

        result = self._preview_once()
        if not result["Success"]:
            print("gphoto2 preview failed ({}); reconnecting and "
                  "retrying once...".format(result.get("Error")))
            self.uninitialize_camera()
            if self.initialize_camera()["Success"]:
                result = self._preview_once()

        if not result["Success"]:
            print("gphoto2 preview failed: {}".format(result.get("Error")))
            return {"Success": False, "Image": None}
        return {"Success": True, "Image": result["Image"]}

    def capture_at_exposure(self, exposure, waveIndex):
        """Set the (emulated) exposure for the band, then capture."""
        if self.change_exposure(exposure, waveIndex) == 0:
            return {"Success": False, "Image": None}
        return self.capture()
