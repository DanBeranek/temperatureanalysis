from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QSplitter, QStackedWidget, QVBoxLayout

from temperatureanalysis.app.ui.preview import Preview2D


class WorkArea(QWidget):
    """The main work area with a splitter between the side panels stack and the 2D preview."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        v = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.setChildrenCollapsible(False)
        v.addWidget(split, 1)

        self.panel_stack = QStackedWidget(split)
        self.preview = Preview2D(split)
        self.preview.set_grid_spacing(major=1.0, minor=0.2)
        self.preview.set_label_formatter(lambda lbl: f"{lbl:.1f}")

        split.addWidget(self.panel_stack)
        split.addWidget(self.preview)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

    def set_panel_index(self, index: int) -> None:
        """Set the currently visible panel by index."""
        self.panel_stack.setCurrentIndex(index)
