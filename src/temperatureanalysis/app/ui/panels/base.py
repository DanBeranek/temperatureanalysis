from __future__ import annotations

from PySide6.QtWidgets import QWidget

from temperatureanalysis.app.state import Store


class BasePanel(QWidget):
    """Base class for left-side panels. Holds a reference to the global store."""
    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store

