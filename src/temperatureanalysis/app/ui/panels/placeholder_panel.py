from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout

from temperatureanalysis.app.ui.panels.base import BasePanel

if TYPE_CHECKING:
    from temperatureanalysis.app.state import Store

class PlaceholderPanel(BasePanel):
    """A simple placeholder panel with a label."""
    def __init__(self, store: Store, parent=None) -> None:
        super().__init__(store, parent)
        widget = QLabel("This is a placeholder", self)
        layout = QVBoxLayout(self)
        layout.addWidget(widget)
        layout.addStretch(1)
