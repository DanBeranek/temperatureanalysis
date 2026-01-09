"""
Entry Point Script (Bootstrap)
==============================
This script is the absolute starting point of the application for development.

Why is this file needed?
------------------------
1. It is located outside the 'src' package to act as a convenient runner.
2. It modifies 'sys.path' to ensure Python can resolve imports like
   'from temperatureanalysis.model...' without errors.

Usage:
    $ python run.py
"""
import sys
import os
from typing import NoReturn

# Add the 'src' directory to the Python path
# We cast __file__ to str because in some rare frozen environments it might be None
current_dir: str = os.path.dirname(os.path.abspath(__file__))
src_path: str = os.path.join(current_dir, 'src')
sys.path.insert(0, src_path)

appid = 'CK04000274-V2.PozarTunel'  # Arbitrary string
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
except (AttributeError, ImportError):
    # Not on Windows or ctypes not available
    pass

from temperatureanalysis.main import main

if __name__ == "__main__":
    main()
