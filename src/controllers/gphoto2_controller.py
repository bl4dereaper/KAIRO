"""
gphoto2 DSLR Camera Controller (Project Kairo)

Supports converted full-spectrum DSLR/mirrorless bodies (Canon, Nikon,
Fuji, and other PTP cameras) over USB using the official libgphoto2
python bindings (PyPI package: gphoto2). One library covers all three
vendors, which is why Project Kairo chose it as the DSLR backend
(see README).

Verified in the camlib database (libgphoto2 >= 2.5.18) e.g.:
    Fuji Fujifilm GFX100 / GFX100 II / GFX 100S, X-series,
    Canon EOS R / 5D, Nikon Z / D series, ...

v1 behavior:
  - Auto-detects PTP cameras and connects to the first one found
    (reporting its model name for the UI).
  - Captures full-resolution stills (camera's file format: JPEG or RAW)
    and decodes them in RAM -- JPEG via OpenCV, RAW via rawpy (no
    camera white balance).
  - Exposure is emulated in software (brightness scale). Mapping
    exposure floats to discrete camera shutter speeds via the gphoto2
    config tree is a Kairo roadmap item (config-tree caching, RAW
    linear Bayer extraction).

Optional install:
    macOS:  brew install gphoto2 && pip install gphoto2 rawpy
    Linux:  sudo apt install libgphoto2-dev && pip install gphoto2 rawpy

If the dependencies are missing, this module imports cleanly and the
controller raises ValueError, so the app falls back to other cameras.
"""
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
        """Scan for PTP cameras and connect to the first one found."""
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

        try:
            port_info_list = gphoto2.PortInfoList()
            port_info_list.load()
            abilities_list = gphoto2.CameraAbilitiesList()
            abilities_list.load()

            self.camera = gphoto2.Camera()
            port_idx = port_info_list.lookup_path(addr)
            self.camera.set_port_info(port_info_list[port_idx])
            model_idx = abilities_list.lookup_model(name)
            self.camera.set_abilities(abilities_list[model_idx])
            self.camera.init()
        except Exception as ex:
            raise ValueError("Failed to connect to {}: {}".format(name, ex))

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
        """Close the gphoto2 camera connection."""
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
    def _decode_image_bytes(data: bytes, mime: str) -> np.ndarray:
        """
        Decode captured image bytes into a grayscale float32 array in [0, 1].
        JPEG decodes directly; RAW (RAF/CR2/NEF/ARW/...) decodes via rawpy
        when installed.
        """
        mime = (mime or "").lower()

        # JPEG path
        if "jpeg" in mime or "jpg" in mime:
            bgr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if bgr is not None:
                return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        # RAW path (RAF/CR2/NEF/ARW/...), also a fallback for odd mime types
        if RAWPY_AVAILABLE:
            try:
                raw = rawpy.imread(np.frombuffer(data, dtype=np.uint8))
                # No camera white balance; keep the response as linear as possible
                bgr = raw.postprocess(use_camera_wb=False,
                                      output_color=rawpy.ColorSpace.sRGB)
                return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            except Exception:
                pass

        raise ValueError(
            "Could not decode captured image (mime: {})."
            .format(mime or "unknown"))

    def capture(self):
        """
        Capture one full-resolution still and decode it to a float32
        grayscale frame in [0, 1].
        :return: dict {"Success": bool, "Image": np.ndarray | None}
        """
        if not self.check_camera_initialized():
            return {"Success": False, "Image": None}
        try:
            file_path = self.camera.capture(gphoto2.GP_CAPTURE_IMAGE)
            camera_file = self.camera.file_get(
                file_path.folder, file_path.name, gphoto2.GP_FILE_TYPE_NORMAL)
            data, _size = camera_file.get_data_and_size()
            mime = camera_file.get_mime_type()
            img = self._decode_image_bytes(bytes(data), mime)
            if self._exposure_scale != 1.0:
                img = np.clip(img * self._exposure_scale, 0.0, 1.0)
            return {"Success": True, "Image": img}
        except Exception as ex:
            print("gphoto2 capture failed: {}".format(ex))
            return {"Success": False, "Image": None}

    def capture_at_exposure(self, exposure, waveIndex):
        """Set the (emulated) exposure for the band, then capture."""
        if self.change_exposure(exposure, waveIndex) == 0:
            return {"Success": False, "Image": None}
        return self.capture()
