# Kairo

**Repository:** https://github.com/bl4dereaper/Kairo

**Kairo** — a low-cost, end-to-end multispectral imaging system for
historical artifacts, by **Shrieve Industries**.

Kairo is a cross-platform (macOS / Linux / Windows) application based on RIT's
[MISHA](https://github.com/palimpsest-pursuers/capturing) (*Multispectral Imaging
System for Historical Artifacts*).



Kairo adds support for general-purpose cameras
(any USB camera via OpenCV) and converted full-spectrum DSLR/mirrorless
bodies (Canon, Nikon, Fuji over libgphoto2), a hardware-free demo mode,
**automatic camera selection** (the app probes every backend, picks the
best connected one, and reports the decision on the start page), a
**macOS-native application look** (Apple system palette, San Francisco
font, rounded cards, native menu bar with About/Quit), and a
float32/uint16 imaging pipeline for improved dynamic range.

**Purpose:** enable scholars, curators, and researchers with non-scientific
backgrounds to analyze cultural heritage items (manuscripts, historical
documents, etc.).

**Output:** ENVI spectral image cubes (`*.hdr` + band TIFFs), plus raw
images, noise image, optional flats, true-color image, metadata XML, and
exposure profile.

---

## Quick Start (macOS)

```bash
# 1. Use Python 3.12 (the app is tested on 3.12; 3.11 should also work)
brew install python@3.12

# 2. Create and activate a virtual environment
cd Kairo
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python src/main.py
```

Linux:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

On first launch on macOS, the system may ask for **Camera** permissions
(for the generic camera) — allow them.

> **No hardware? No problem.** If no camera is detected the app starts in
> **MOCK camera mode**: synthetic frames are generated so the entire GUI
> workflow (metadata → noise → focus → exposure → object → flats →
> edit/calibrate → save cube) can be exercised without the rig.

## Camera Support

| Camera | Controller | How it connects | Availability |
|---|---|---|---|
| Pixelink | `controllers/pixilink_controller.py` | Pixelink API 4.0 (SDK required) | Windows / Linux |
| FLIR Blackfly | `controllers/blackfly_controller.py` | Spinnaker / PySpin (SDK required) | Windows |
| Any USB camera / webcam | `controllers/opencv_controller.py` | OpenCV (`avfoundation` on macOS, `v4l2` on Linux) | **All platforms** |
| Converted DSLR bodies (Canon, Nikon, Fuji, …) | `controllers/gphoto2_controller.py` | libgphoto2 over USB/PTP | **All platforms** (optional install) |
| None (demo mode) | `controllers/camera_mock.py` | Synthetic frames | All platforms |

The app auto-detects in the order above and reports which camera is active
on the start page; you can also select one explicitly with the
**Camera Options** radio buttons. (`baumer_controller.py` is kept as a
commented-out reference from the original MISHA tree.)

Optional DSLR support (Project Kairo's converted-camera goal):

```bash
# macOS
brew install gphoto2
pip install gphoto2 rawpy

# Linux
sudo apt install libgphoto2-dev
pip install gphoto2 rawpy
```

## Project Layout

```
Kairo/
├── requirements.txt          # Core + optional hardware dependencies
├── src/
│   ├── main.py               # Entry point: UI + camera/LED init + button wiring
│   ├── controllers/          # Camera & LED abstractions
│   │   ├── camera_interface.py   # ABC: common contract for all cameras
│   │   ├── led_interface.py      # ABC: common contract for LED panels
│   │   ├── pixilink_controller.py
│   │   ├── blackfly_controller.py
│   │   ├── opencv_controller.py  # generic "most cameras" support
│   │   ├── gphoto2_controller.py # DSLR support (Kairo)
│   │   ├── camera_mock.py        # hardware-free demo mode
│   │   └── led_controller.py / led_mock.py
│   ├── operations/           # UI workflow steps (QThread workers)
│   │   ├── operation.py          # ABC for operations
│   │   ├── led_test_mode.py      # LED test flashing
│   │   ├── noise_operation.py    # dark/noise frame capture
│   │   ├── focus_operation.py    # live focus view, sharpness + peaking
│   │   ├── light_operation.py    # per-band exposure adjustment
│   │   ├── object_operation.py   # 16-band object capture
│   │   ├── flats_operation.py    # flat-field capture
│   │   ├── edit_operation.py     # rotate/crop/calibrate/true-color
│   │   └── finish_operation.py   # cube build + save
│   ├── cube_creation/
│   │   └── build_cube.py     # ENVI cube assembly, image math, saving
│   └── skeleton/             # UI assets
│       ├── capture.ui        # main window layout (Qt Designer)
│       ├── macos_style.py    # macOS-native styling (palette, font, icon,
│       │                     #   launch card)
│       ├── switch_widget.py  # macOS-style toggle switch (focus assist)
│       ├── progress_dialog.py / message_box.py
│       ├── rectangle_selection.py  # crop/calibration region picker
│       ├── Accessories.py    # illuminant/CMF helpers for true color
│       └── imgs/             # icons and image assets
```

### Imaging pipeline

Frames are processed as **float32 in [0, 1]** end-to-end (no demosaic, no
white balance, no gamma — preserves the linear reflectance signal) and are
written to disk as **uint16** (×65535) ENVI cubes.

1. **Noise** (optional): dark frame, subtracted from every band
2. **Focus**: live view with sharpness metric
3. **Exposure**: per-band exposure levels captured as four test frames;
   profiles can be saved/loaded as `.txt`
4. **Object**: one frame per LED wavelength (16 bands)
5. **Flats** (optional): flat-field frames, gaussian-filtered and divided out
6. **Edit**: rotate, crop, manual/auto Spectralon calibration, true-color
   image (D65 + CIE 1931 CMFs, white-balanced)
7. **Finish**: ENVI `.hdr` + per-band TIFFs + metadata XML + exposure profile

### Calibration context

- Spectralon (PTFE) is the diffuse reflectance standard — the "ruler for
  brightness". Per-band normalization:
  `Reflectance_doc = (DN_doc / DN_Spectralon) × R_Spectralon`
- Recommended standard: calibrated Labsphere SRS-series (99% white),
  optionally a grayscale set (99/50/20/2%) for sensor linearity.

---

## Project Kairo Roadmap (working notes)

### New Feature: Converted Camera Support
- **Goal:** full-spectrum converted bodies (Kolari-style) — Canon, Nikon,
  Fuji first.
- **Platform:** Linux/macOS confirmed (Windows deferred).
- **Backend decision:** libgphoto2 via python-gphoto2 — one library covers
  all three vendors over PTP; avoids three separate SDK integrations.
- **Key design points:**
  - Capture-to-RAM (skips SD card write + download handshake)
  - Config-tree caching (avoid expensive PTP traversals per shot)
  - RAW capture, linear Bayer extraction via rawpy/LibRaw (no demosaic, no
    WB, no gamma — preserves linear reflectance signal)
  - Exposure floats mapped to nearest discrete camera shutter speed

### Output Shape Decision — RESOLVED
Chosen: **Three-plane Bayer (Option B)** — per band, return (H, W, 3):
Plane 0 = Red Bayer sites, Plane 1 = Green (both diagonal greens averaged,
~2× SNR), Plane 2 = Blue.

Rejected: mono-only (loses channel-specific pigment signatures), demosaiced
RGB (destroys linearity), bracketing (slower, only if glare issues demand
it later).

Rationale: preserves maximum information for future scholarship; channel
ratios are diagnostically useful.

### Streamlining Roadmap (agreed order)
1. Externalized rig config — `exposureArray` → YAML RigConfig/BandSpec
   dataclasses; validation at load; `retune_band_exposure()` + `save()` for
   UI retuning; legacy shim for old controllers. (Not yet in the tree.)
2. Exposure state pattern — `ExposureMode` enum (FIXED / TABLE / AUTO)
   unifying `reset_exposure`/`save_exposure`
3. Frame-buffer refactor — factor `_grab_raw_frame()` /
   `_frame_to_ndarray()` pattern into base class; SDK differences localized
   to subclasses

### Open Questions
- LED channel mapping (`led_id`) co-located in rig config? — leaning yes
  (single source of truth)
- RigConfig authoring: real per-rig YAML files to be written for each system

---

## Acknowledgements & Credits

**Kairo** was designed and built by **Shrieve Industries**.

**MISHA** — the project Kairo is based on, developed at the Rochester
Institute of Technology (RIT) by the Imaging Science and Museum Studies
Programs for small-format historical documents, sheet, and leaf
collections with overwritten text, faded ink, or other unreadable/unknown
content.

- **Original MISHA Image Capture (Python) authors:** Sai Keshav Sasanapuri,
  Cecelia Ahrens, Mallory Bridge, Eric Gao, Robert Maron
- **RIT contacts:** David Messinger and Juilee Decker (RIT)
- **Project website:** https://chipr2022.wordpress.com/
- **Upstream repository:** https://github.com/palimpsest-pursuers/capturing

Additional contributions:

- **Baumer camera controller (reference):** Julia Schenatto (IFUSP)
- **Rectangle selection / MISHA Processing Software:** Eric Gao

## License

Kairo is released under the GNU General Public License v3 (GPL-3.0) — see
the `LICENSE` file. The upstream MISHA project it is based on is credited
above.
