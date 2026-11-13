"""Hand a saved cube from Kairo over to the Prism analysis app.

Kairo's finish page has an "Open in Prism" button; it launches Prism
detached (so closing Kairo never kills it) with the freshly saved cube:

    python -m prism <name>.hdr

The Prism checkout location defaults to ``/Users/tom/prism`` and can be
overridden with the KAIRO_PRISM_DIR environment variable.
"""
import os
import subprocess

# Where the Prism app lives on this machine (env override wins).
PRISM_APP_DIR = os.environ.get("KAIRO_PRISM_DIR", "/Users/tom/prism")


def prism_available() -> bool:
    """True if the Prism app and its venv exist at the expected location."""
    return os.path.isfile(os.path.join(PRISM_APP_DIR, ".venv", "bin", "python"))


def open_cube_in_prism(cube_path: str):
    """Launch Prism showing ``cube_path`` (.hdr cube or band-TIFF folder).

    Returns (ok, message).  The process is detached (start_new_session)
    so it survives Kairo quitting.
    """
    python = os.path.join(PRISM_APP_DIR, ".venv", "bin", "python")
    if not os.path.isfile(python):
        return False, (f"Prism was not found at {PRISM_APP_DIR}.\n"
                       "Set KAIRO_PRISM_DIR to the Prism folder to fix this.")
    if cube_path and not os.path.exists(cube_path):
        return False, f"Cube not found:\n{cube_path}"
    try:
        subprocess.Popen([python, "-m", "prism", cube_path],
                         cwd=PRISM_APP_DIR, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as ex:
        return False, f"Could not launch Prism:\n{ex}"
    return True, ""
