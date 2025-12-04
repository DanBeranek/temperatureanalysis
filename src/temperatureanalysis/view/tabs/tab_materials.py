"""
Materials Control Panel
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QGroupBox, QHBoxLayout
)
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.view.dialogs.materials_dialog import MaterialsDialog


class MaterialsControlPanel(QWidget):
    def __init__(self, project_state: ProjectState, parent_window=None) -> None:
        super().__init__()
        self.project = project_state
        self.parent_window = parent_window

        layout = QVBoxLayout(self)

        # 1. Management Section
        manage_group = QGroupBox("Definice Materiálů")
        manage_layout = QVBoxLayout(manage_group)

        btn_manage = QPushButton("Spravovat Knihovnu Materiálů...")
        btn_manage.setFixedHeight(40)
        btn_manage.clicked.connect(self.open_manager_modal)
        manage_layout.addWidget(btn_manage)

        layout.addWidget(manage_group)

        # 2. Assignment Section
        assign_group = QGroupBox("Přiřazení ke Konstrukci")
        assign_layout = QVBoxLayout(assign_group)

        assign_layout.addWidget(QLabel("Vyberte komponentu (Ostění/Vzduch):"))
        self.comp_list = QListWidget()
        self.comp_list.addItems(["Vnitřní Ostění (Inner)", "Vnější Ostění (Outer)", "Vzduch (Air)"])
        assign_layout.addWidget(self.comp_list)

        assign_layout.addWidget(QLabel("Vyberte materiál:"))
        self.mat_list = QListWidget()  # This would be populated from ProjectState
        self.mat_list.addItems(["Beton C30/37", "Vzduch (Standard)", "Zemina"])
        assign_layout.addWidget(self.mat_list)

        btn_assign = QPushButton("Přiřadit")
        assign_layout.addWidget(btn_assign)

        layout.addWidget(assign_group)
        layout.addStretch()

    def open_manager_modal(self) -> None:
        # Open the modal dialog defined previously
        dlg = MaterialsDialog(self.project, self.parent_window)
        dlg.exec()
        # After dialog closes, refresh self.mat_list here...
