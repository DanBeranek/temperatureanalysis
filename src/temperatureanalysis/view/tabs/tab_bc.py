"""
Boundary Conditions Control Panel
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QGroupBox,
    QHBoxLayout, QComboBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt

from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.model.bc import FireCurveType
from temperatureanalysis.view.dialogs.dialog_bc import FireCurveDialog

class BCControlPanel(QWidget):
    def __init__(self, project_state: ProjectState, parent_window=None) -> None:
        super().__init__()
        self.project = project_state
        self.parent_window = parent_window

        layout = QVBoxLayout(self)

        # 1. Management
        manage_group = QGroupBox("Definice Požárních Křivek")
        manage_layout = QVBoxLayout(manage_group)

        btn_manage = QPushButton("Spravovat Knihovnu Křivek...")
        btn_manage.setFixedHeight(40)
        btn_manage.clicked.connect(self.open_manager_modal)
        manage_layout.addWidget(btn_manage)

        layout.addWidget(manage_group)

        # 2. Assignment
        assign_group = QGroupBox("Přiřazení Okrajových Podmínek")
        assign_layout = QVBoxLayout(assign_group)

        # Curve Selection (Simplified: Only one curve for the construction)
        assign_layout.addWidget(QLabel("Vyberte požární křivku pro konstrukci:"))

        self.curve_combo = QComboBox()
        self.curve_combo.currentIndexChanged.connect(self.on_assignment_changed)
        assign_layout.addWidget(self.curve_combo)

        layout.addWidget(assign_group)

        # 3. Info Box
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_layout = QVBoxLayout(info_frame)
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        info_layout.addWidget(self.lbl_info)
        layout.addWidget(info_frame)

        layout.addStretch()

        # Initial Load
        self.refresh_combo()

    def open_manager_modal(self) -> None:
        dlg = FireCurveDialog(self.project, self.parent_window)
        dlg.exec()
        self.refresh_combo()

    def refresh_combo(self):
        self.curve_combo.blockSignals(True)

        current_name = self.project.selected_fire_curve.name if self.project.selected_fire_curve else None

        self.curve_combo.clear()
        names = self.project.fire_library.get_names()
        self.curve_combo.addItems(names)

        if current_name:
            idx = self.curve_combo.findText(current_name)
            if idx >= 0:
                self.curve_combo.setCurrentIndex(idx)
        elif self.curve_combo.count() > 0:
            self.curve_combo.setCurrentIndex(0)
            self.on_assignment_changed()

        self.curve_combo.blockSignals(False)
        self._update_info()

    def on_assignment_changed(self):
        curve_name = self.curve_combo.currentText()
        if not curve_name: return

        config = self.project.fire_library.get_fire_curve(curve_name)
        if config:
            self.project.selected_fire_curve = config
            self._update_info()

    def _update_info(self):
        c = self.project.selected_fire_curve
        if c:
            txt = f"<b>Aktivní křivka:</b> {c.name}<br>"
            txt += f"<b>Typ:</b> {c.type.value}<br>"
            if c.description:
                txt += f"<i>{c.description}</i>"
            self.lbl_info.setText(txt)
        else:
            self.lbl_info.setText("Žádná křivka není vybrána.")
