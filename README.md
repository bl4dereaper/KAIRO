## MISHA Capture Upgrade — Working Notes
Repo: github.com/bl4dereaper/MISHA · Focus: DSLR/mirrorless camera support + streamlining

## 1. Project Context
MISHA: low-cost multispectral imaging system, RIT, NEH-funded (PR-268783-20), co-directed by Dr. David Messinger & Dr. Juilee Decker
Produces ENVI spectral image cubes for cultural heritage/document analysis
Stack: Python + PyQt5; modular layout: controllers/, cube_creation/, operations/, skeleton/
Existing cameras: Pixelink, FLIR Blackfly (PySpin/Spinnaker), Baumer + mock for testing
CameraInterface ABC contract: initialize_camera(), capture(), capture_at_exposure(), uninitialize_camera(), reset_exposure(), save_exposure()
## 2. New Feature: Converted Camera Support
Goal: full-spectrum converted bodies (Kolari-style) — Canon, Nikon, Fuji first
Platform: Linux/macOS confirmed (Windows deferred)
Backend decision: libgphoto2 via python-gphoto2 — one library covers all three vendors over PTP; avoids three separate SDK integrations
Key design points:
Capture-to-RAM (skips SD card write + download handshake)
Config-tree caching (avoid expensive PTP traversals per shot)
RAW capture, linear Bayer extraction via rawpy/LibRaw (no demosaic, no WB, no gamma — preserves linear reflectance signal)
Exposure floats mapped to nearest discrete camera shutter speed
## 3. Output Shape Decision — RESOLVED
Chosen: Three-plane Bayer (Option B) — per band, return (H, W, 3):

Plane 0 = Red Bayer sites, Plane 1 = Green (both diagonal greens averaged, ~2× SNR), Plane 2 = Blue
Rejected: mono-only (loses channel-specific pigment signatures), demosaiced RGB (destroys linearity), bracketing (slower, only if glare issues demand it later)
Rationale: preserves maximum information for future scholarship; channel ratios are diagnostically useful
## 4. Calibration Context
Spectralon = PTFE diffuse reflectance standard, the "ruler for brightness"
Normalize per band: Reflectance_doc = (DN_doc / DN_Spectralon) × R_Spectralon
Needed item: calibrated Labsphere SRS-series standard (99% white, ~$400–700; optionally grayscale set 99/50/20/2% for sensor linearity) — not a Newport port plug like 819M-PP-SL-1.5
## 5. Streamlining Roadmap (agreed order)
Externalized rig config — exposureArray → YAML RigConfig/BandSpec dataclasses; validation at load; retune_band_exposure() + save() for UI retuning; legacy shim for old controllers. rig_config.py drafted ✓
Exposure state pattern — ExposureMode enum (FIXED / TABLE / AUTO) unifying reset_exposure/save_exposure (next up)
Frame-buffer refactor — factor _grab_raw_frame() / _frame_to_ndarray() pattern into base class; SDK differences localized to subclasses
## 6. Open Questions
LED channel mapping (led_id) co-located in rig config? — leaning yes (single source of truth)
RigConfig authoring: real per-rig YAML files to be written for each system

### 
# MISHA Image Capturing Software
MISHA Image Capturing Software is funded by the National Endowment for the Humanities, PR-268783-20, Preservation and Access: Research and Development, RIT, Low-Cost End-to-End Spectral Imaging System for Historical Document Discovery co-directed by Dr. David Messinger and Dr. Juilee Decker at Rochester Institute of Technology This software works together with the MISHA hardware to create multispectral image ENVI cubes. 
### 
## License
[MIT](https://choosealicense.com/licenses/mit/)
### 
