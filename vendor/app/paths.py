"""Separate read-only bundled resources from persistent application data."""
import hashlib
import os
from pathlib import Path
import sys

FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
INSTALL_ROOT = Path(sys.executable).resolve().parent if FROZEN else RESOURCE_ROOT


def default_data_dir():
    override = os.getenv("CLASH_STUDIO_DATA")
    if override:
        return Path(override).expanduser().resolve()
    if not FROZEN:
        return INSTALL_ROOT / "data"
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "ClashStudio"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ClashStudio"
    return Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "clash-studio"


def instance_id():
    identity = "clash-studio:" + str(default_data_dir()) if FROZEN else str(INSTALL_ROOT)
    return hashlib.sha256(identity.casefold().encode()).hexdigest()[:16]
