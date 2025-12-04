"""
Configuration & Path Management
===============================
This module serves as the central registry for file paths and global constants.

Why is this file needed?
------------------------
1. Abstraction: It prevents hardcoded paths (e.g., "C:/Users/...") scattered
   throughout the code.
2. Deployment: It handles the logic required by PyInstaller (sys._MEIPASS) to
   find assets (icons, JSONs) when the app is frozen into an .exe.

Exports:
    ASSETS_PATH (str): Absolute path to the assets directory.
    DEFAULT_MATS_PATH (str): Absolute path to the system materials file.
"""
import sys
import os
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller temp folder
        base_path: str = getattr(sys, '_MEIPASS')
        return os.path.join(base_path, relative_path)

    # Development mode: resolve relative to this file
    # config.py is in src/temperatureanalysis/
    current_file_path: Path = Path(__file__)
    project_root: Path = current_file_path.parent.parent.parent
    return os.path.join(str(project_root), relative_path)


# Global Constants
ASSETS_PATH: str = get_resource_path("assets")
DEFAULT_MATS_PATH: str = os.path.join(ASSETS_PATH, "materials_default.json")

if not os.path.exists(ASSETS_PATH):
    print(f"WARNING: Assets path not found at {ASSETS_PATH}")
