"""
Run with: python -m temperatureanalysis.app
"""
from __future__ import annotations

import sys

from temperatureanalysis.app.application import create_app
from temperatureanalysis.app.ui.main_window import MainWindow

import pyqtgraph as pg

pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")

def main() -> int:
    """Main entry point for the application."""
    app = create_app()
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
