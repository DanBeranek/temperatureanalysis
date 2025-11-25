from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QGridLayout,
    QSizePolicy, QDoubleSpinBox
)

from temperatureanalysis.app.ui.preview import PreviewDomain


class ParamEditorBase(QWidget):
    """Base class for shape-specific parameter editors."""
    KEY: str = "base"  # Override in subclass
    TITLE: str = "Parameters"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        box = QGroupBox(self.tr(self.TITLE), self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(box)
        self.grid = QGridLayout(box)
        self.grid.setVerticalSpacing(8)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._row = 0
        self._build_ui()  # subclass defines inputs

    # ---- utilities ----

    def _next_row(self) -> int:
        r = self._row
        self._row += 1
        return r

    def _add_spin(
        self,
        key: str,
        label: str,
        *,
        min_value: float = -1e9,
        max_value: float = 1e9,
        step: float = 0.1,
        default: float = 0.0,
        suffix: str = "",
        decimals: int = 3
    ) -> QDoubleSpinBox:
        row = self._next_row()
        lab = QLabel(self.tr(label), self)
        self.grid.addWidget(lab, row, 0)
        w = QDoubleSpinBox(self)
        w.setRange(min_value, max_value)
        w.setSingleStep(step)
        w.setDecimals(decimals)
        w.setValue(default)
        w.setKeyboardTracking(False)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if suffix:
            w.setSuffix(f" {suffix}")
        self.grid.addWidget(w, row, 1)
        self._spins[key] = w
        return w

    def params(self) -> dict[str, float]:
        return {k: w.value() for k, w in self._spins.items()}

    def retranslate(self) -> None:
        """Override to update labels/titles on language change."""
        box = self.findChild(QGroupBox)
        if box:
            box.setTitle(self.tr(self.TITLE))

    @Slot()
    def _relay_changed(self) -> None:
        self.parent().parent()._emit_domains()  # or emit a custom Qt signal from base

    # ---- abstract API for subclasses ----
    def _build_ui(self) -> None:
        """Create form widgets and connect signals (use `add_spin` helper)."""
        raise NotImplementedError("`_build_ui` must be implemented in subclass.")

    def build_domains(self) -> list[PreviewDomain]:
        """
        Return a list of MaterialLayer instance to render in the preview.
        """
        raise NotImplementedError("`_build_layers` must be implemented in subclass.")
