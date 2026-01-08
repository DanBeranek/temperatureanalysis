"""
Materials Control Panel
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QGroupBox,
    QComboBox, QMessageBox
)
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.model.materials import MaterialLibrary
from temperatureanalysis.view.dialogs.dialog_material import MaterialsDialog

class MaterialsControlPanel(QWidget):
    data_changed = Signal()
    material_changed = Signal()

    def __init__(self, project_state: ProjectState, parent_window=None) -> None:
        super().__init__()
        self.project = project_state
        self.parent_window = parent_window

        if not hasattr(self.project, "material_library"):
            self.project.material_library = MaterialLibrary()

        layout = QVBoxLayout(self)

        # 1. Management
        manage_group = QGroupBox("Definice materiálů")
        manage_layout = QVBoxLayout(manage_group)

        btn_manage = QPushButton("Spravovat knihovnu materiálů...")
        btn_manage.setFixedHeight(40)
        btn_manage.clicked.connect(self.open_manager_modal)
        manage_layout.addWidget(btn_manage)

        layout.addWidget(manage_group)

        # 2. Assignment Section
        assign_group = QGroupBox("Materiál ostění")
        assign_layout = QVBoxLayout(assign_group)

        assign_layout.addWidget(QLabel("Vyberte materiál:"))
        self.mat_combo = QComboBox()
        self.mat_combo.currentIndexChanged.connect(self.on_assignment_changed)
        assign_layout.addWidget(self.mat_combo)

        layout.addWidget(assign_group)

        layout.addStretch()

        # Initial Load
        self.refresh_combo()
        self.load_from_state()

    def load_from_state(self):
        """Load selected material from project state into the combo box."""
        self.refresh_combo()
        if self.project.selected_material:
            mat_name = self.project.selected_material.name
            idx = self.mat_combo.findText(mat_name)
            if idx >= 0:
                self.mat_combo.setCurrentIndex(idx)

    def open_manager_modal(self) -> None:
        dlg = MaterialsDialog(self.project, self.parent_window)
        if dlg.exec():
            # Dialog accepted - materials may have changed
            self.data_changed.emit()
        self.refresh_combo()

    def refresh_combo(self):
        """Reloads material names into the combobox."""
        # Block signals to prevent triggering selection change during reload
        self.mat_combo.blockSignals(True)

        current_selection_name = self.project.selected_material.name if self.project.selected_material else None

        self.mat_combo.clear()

        names = self.project.material_library.get_names()
        self.mat_combo.addItems(names)

        # Restore selection
        if current_selection_name:
            idx = self.mat_combo.findText(current_selection_name)
            if idx >= 0:
                self.mat_combo.setCurrentIndex(idx)
        elif self.mat_combo.count() > 0:
            # Default to first if nothing selected
            self.mat_combo.setCurrentIndex(0)
            self.on_assignment_changed() # Trigger save of default

        self.mat_combo.blockSignals(False)

    def on_assignment_changed(self):
        """Called when combo box selection changes."""
        material_name = self.mat_combo.currentText()
        if not material_name:
            return

        mat = self.project.material_library.get_material(material_name)
        if mat:
            self.project.selected_material = mat
            self.material_changed.emit()
            self.data_changed.emit()
