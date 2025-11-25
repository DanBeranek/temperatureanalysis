from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QComboBox, QLabel, QGridLayout, QStackedWidget,
)

from temperatureanalysis.app.state import Store, Stage
from temperatureanalysis.app.ui.panels.base import BasePanel
from temperatureanalysis.app.ui.panels.geometry_editors.base import ParamEditorBase
from temperatureanalysis.app.ui.panels.geometry_editors.registry import list_keys, create_editor

LABELS = {
    "circle": "Circular",
    "rectangle": "Rectangular",
    "ellipse": "Elliptical",
    "d_section": "D-Section"
}

class GeometryPanel(BasePanel):
    """
    Panel for selecting and configuring tunnel geometry.

    Top: tunnel shape selector (circular, rectangular, etc.)
    Below: parameter editor from the registry. Emits layers to Store on change.
    """
    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(store, parent)

        root = QVBoxLayout(self)

        # selection row
        # self.group_select = QGroupBox(self.tr("Tunnel Type:"), self)
        self.group_select = QGroupBox("", self)
        root.addWidget(self.group_select, 0)
        sel = QGridLayout(self.group_select)
        self.label_type = QLabel(self.tr("Tunnel Type:"), self.group_select)
        sel.addWidget(self.label_type, 0, 0)
        self.combo_box = QComboBox(self.group_select)
        sel.addWidget(self.combo_box, 0, 1)

        # parameter editor stack
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 0)

        # Fill combo box and stack with registered editors
        self._keys = list_keys()
        self._editors: dict[str, ParamEditorBase] = {}
        for key in self._keys:
            self.combo_box.addItem(self.tr(LABELS.get(key, key)), userData=key)
            editor = create_editor(key, parent=self.stack)
            self._editors[key] = editor
            self.stack.addWidget(editor)

        # wiring
        self.combo_box.currentIndexChanged.connect(self._on_changed)

        root.addStretch()

        self._adjust_stacked_widget_height()

        # default selection
        self._select_key("circle")
        self._emit_domains()

    def retranslate(self) -> None:
        raise NotImplementedError

    def _select_key(self, key: str) -> None:
        index = self._keys.index(key)
        self.combo_box.setCurrentIndex(index)
        self.stack.setCurrentIndex(index)

    def _current_editor(self) -> ParamEditorBase:
        return self._editors[self.combo_box.currentData()]

    @Slot()
    def _on_changed(self) -> None:
        self.stack.setCurrentIndex(self.combo_box.currentIndex())
        self._adjust_stacked_widget_height()
        self._emit_domains()

    def _emit_domains(self) -> None:
        # Geometry change => invalidate downstream
        self.store.invalidate_from(Stage.MATERIALS)
        layers = self._current_editor().build_domains()
        self.store.set_domains(layers)

    def _adjust_stacked_widget_height(self) -> None:
        """
        This method is necessary for the stacked widget to resize.

        Without it, the stacked widget will always have the height of the tallest
        editor, which looks bad when switching to a smaller one.
        """
        h = self._current_editor().sizeHint().height()
        self.stack.setFixedHeight(h)
