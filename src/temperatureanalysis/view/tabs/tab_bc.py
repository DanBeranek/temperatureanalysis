"""
Boundary Conditions Control Panel
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QGroupBox
)
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.view.dialogs.bc_dialog import BCDialog


class BCControlPanel(QWidget):
    def __init__(self, project_state: ProjectState, parent_window=None) -> None:
        super().__init__()
        self.project = project_state
        self.parent_window = parent_window

        layout = QVBoxLayout(self)

        # 1. Management Section
        manage_group = QGroupBox("Definice Požárních Křivek")
        manage_layout = QVBoxLayout(manage_group)

        btn_manage = QPushButton("Definovat Okrajové Podmínky...")
        btn_manage.setFixedHeight(40)
        btn_manage.clicked.connect(self.open_manager_modal)
        manage_layout.addWidget(btn_manage)

        layout.addWidget(manage_group)

        # 2. Assignment Section
        assign_group = QGroupBox("Aplikace na Hranice")
        assign_layout = QVBoxLayout(assign_group)

        assign_layout.addWidget(QLabel("Dostupné Podmínky:"))
        self.bc_list = QListWidget()
        self.bc_list.addItems(["ISO 834 (Standard)", "RWS Curve", "Konstantní Teplota 20°C"])
        assign_layout.addWidget(self.bc_list)

        assign_layout.addWidget(QLabel("Návod: Vyberte hranu v 3D okně a klikněte na Aplikovat."))

        btn_apply = QPushButton("Aplikovat na Vybrané")
        assign_layout.addWidget(btn_apply)

        layout.addWidget(assign_group)
        layout.addStretch()

    def open_manager_modal(self) -> None:
        dlg = BCDialog(self.project, self.parent_window)
        dlg.exec()
