"""
Mock Camera Controller (hardware-free demo mode)

Provides a drop-in CameraInterface implementation that generates synthetic
grayscale test frames so the full MISHA GUI workflow can be exercised on a
machine without a Pixelink/Blackfly camera (e.g. a development laptop).

Frames are deterministic, vary per wavelength band, and scale with the
requested exposure so the exposure-adjustment UI shows visible differences.

Based on MISHA (Multispectral Imaging System for Historical Artifacts),
RIT. Original mock written by Cecelia Ahrens; completed for cross-platform
use in Project Kairo.
"""
import numpy as np
from controllers.camera_interface import CameraInterface

# Synthetic frame size (portrait, similar to a typical flatbed capture)
MOCK_FRAME_HEIGHT = 1024
MOCK_FRAME_WIDTH = 768


class CameraMock(CameraInterface):
    """Mock camera that returns synthetic frames instead of real captures."""

    def __init__(self):
        self.ORIGINAL_EXPOSURE = 1.0
        # Per-band exposure table, mirroring the real controllers
        self.selected_exposure_array = [self.ORIGINAL_EXPOSURE] * 16
        self.acquisition_mode = "SingleFrame"
        self._last_exposure = self.ORIGINAL_EXPOSURE
        self._band = 8  # default to the "visible" band (560 nm region)

    def initialize_camera(self):
        """Mock cameras need no initialization; report success."""
        return {"Success": True, "Error": None}

    def check_camera_initialized(self) -> bool:
        """A mock camera is always 'connected'."""
        return True

    def uninitialize_camera(self):
        """No hardware to release."""
        pass

    def change_acquisition_mode(self, mode: str) -> None:
        """Record the requested acquisition mode."""
        self.acquisition_mode = mode

    def Begin_Acquisition(self):
        """No-op for the mock camera."""
        pass

    def End_Acquisition(self):
        """No-op for the mock camera."""
        pass

    # ------------------------------------------------------------------
    # Exposure control (same interface as the real controllers)
    # ------------------------------------------------------------------

    def change_exposure(self, change, waveIndex):
        """
        Set exposure for a band as a factor over the saved per-band value.
        Returns the resulting exposure value (0 on failure, like real cameras).
        """
        if waveIndex is None or waveIndex >= len(self.selected_exposure_array):
            return 0
        self._last_exposure = self.selected_exposure_array[waveIndex] * change
        self._band = waveIndex
        return self._last_exposure

    def reset_exposure(self):
        """Reset all per-band exposures to the original value."""
        self.selected_exposure_array = [self.ORIGINAL_EXPOSURE] * 16
        self._last_exposure = self.ORIGINAL_EXPOSURE

    def save_exposure(self, change, waveIndex):
        """Save the exposure for a single band (factor applied to current)."""
        self.selected_exposure_array[waveIndex] = (
            change * self.selected_exposure_array[waveIndex])

    def save_all_exposures(self, change):
        """Apply an exposure factor to all bands at once."""
        for i in range(len(self.selected_exposure_array)):
            self.selected_exposure_array[i] *= change

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def _synthetic_frame(self, band: int, exposure_factor: float) -> np.ndarray:
        """
        Build a deterministic test pattern:
          - a smooth diagonal brightness gradient (simulates uneven lighting)
          - a band-dependent sinusoidal texture (each wavelength 'sees' differently)
          - a bright square in the upper center (stand-in for a Spectralon white patch)
        """
        h, w = MOCK_FRAME_HEIGHT, MOCK_FRAME_WIDTH
        y = np.linspace(0.0, 1.0, h)[:, None]
        x = np.linspace(0.0, 1.0, w)[None, :]

        # Base lighting gradient
        base = 0.20 + 0.45 * (0.5 * (x + y))

        # Band-dependent texture: phase shifts with wavelength index
        phase = (band / 16.0) * np.pi
        texture = 0.5 + 0.5 * np.sin(24.0 * x + phase) * np.cos(24.0 * y + phase)

        img = base * (0.45 + 0.55 * texture)

        # Bright reference patch (simulated Spectralon standard)
        cy, cx = h // 4, w // 2
        img[cy - 64:cy + 64, cx - 96:cx + 96] = 0.9

        # Scale by exposure so different exposure levels are visibly different
        img = img * exposure_factor
        return np.clip(img, 0.0, 1.0).astype(np.float32)

    def capture(self):
        """
        Return a synthetic frame, matching the real controller return format.
        :return: dict {"Success": bool, "Image": np.ndarray float32 in [0, 1]}
        """
        factor = self._last_exposure / self.ORIGINAL_EXPOSURE
        return {"Success": True, "Image": self._synthetic_frame(self._band, factor)}

    def capture_at_exposure(self, exposure, waveIndex):
        """Capture a frame after setting the given exposure for the band."""
        if self.change_exposure(exposure, waveIndex) == 0:
            return {"Success": False, "Image": None}
        return self.capture()
