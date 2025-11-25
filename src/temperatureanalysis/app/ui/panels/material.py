from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QDialog)

from temperatureanalysis.app.state import Store
from temperatureanalysis.app.ui.panels.base import BasePanel
from temperatureanalysis.app.ui.panels.material_dialog.material_editor import MaterialEditorDialog
from temperatureanalysis.app.ui.panels.material_dialog.properties import TemperatureDependentMaterial


class MaterialPanel(BasePanel):
    """
    Panel for adding materials, preview material properties and assigning them to domains.
    """
    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(store, parent)

        root = QVBoxLayout(self)

        add_button = QPushButton(self.tr("Add Material"), self)
        add_button.clicked.connect(self._add_material)

        root.addWidget(add_button)

    def _add_material(self) -> TemperatureDependentMaterial:
        pass
        # mat = new_material()
        dialog = MaterialEditorDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            print("Super!")
        #     self.store.add_material(dialog.result_material())
        #     self.materials_changed.emit(self.store.materials_store)




