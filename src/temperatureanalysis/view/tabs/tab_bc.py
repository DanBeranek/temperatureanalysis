"""
Boundary Conditions Control Panel
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QGroupBox,
    QHBoxLayout, QComboBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt

from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.model.bc import FireCurveLibrary, FireCurveType
from temperatureanalysis.view.dialogs.dialog_bc import FireCurveDialog

class BCControlPanel(QWidget):
    def __init__(self, project_state: ProjectState, parent_window=None) -> None:
        super().__init__()
        self.project = project_state
        self.parent_window = parent_window

        # Ensure fire library is initialized (safety check)
        if not hasattr(self.project, "fire_library") or self.project.fire_library is None:
            self.project.fire_library = FireCurveLibrary()

        layout = QVBoxLayout(self)

        # 1. Management
        manage_group = QGroupBox("Definice Požárních Křivek")
        manage_layout = QVBoxLayout(manage_group)

        btn_manage = QPushButton("Spravovat Knihovnu Křivek...")
        btn_manage.setFixedHeight(40)
        btn_manage.clicked.connect(self.open_manager_modal)
        manage_layout.addWidget(btn_manage)

        layout.addWidget(manage_group)

        # 2. Assignment Section
        assign_group = QGroupBox("Požární Křivka Konstrukce")
        assign_layout = QVBoxLayout(assign_group)

        # Curve Selection (Single curve for the entire domain)
        assign_layout.addWidget(QLabel("Vyberte požární křivku:"))

        self.curve_combo = QComboBox()
        self.curve_combo.currentIndexChanged.connect(self.on_assignment_changed)
        assign_layout.addWidget(self.curve_combo)

        layout.addWidget(assign_group)

        # 3. Info Section
        info_group = QGroupBox("Informace o Vybrané Křivce")
        info_layout = QVBoxLayout(info_group)

        self.lbl_info = QLabel("Žádná křivka není vybrána.")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setTextFormat(Qt.RichText)
        info_layout.addWidget(self.lbl_info)

        layout.addWidget(info_group)

        layout.addStretch()

        # Initial Load
        self.refresh_combo()
        self.load_from_state()

    def open_manager_modal(self) -> None:
        dlg = FireCurveDialog(self.project, self.parent_window)
        dlg.exec()
        self.refresh_combo()

    def refresh_combo(self):
        """Reloads fire curves from library and restores previous selection if possible."""
        # Block signals to prevent triggering selection change during reload
        self.curve_combo.blockSignals(True)

        current_selection_name = self.project.selected_fire_curve.name if self.project.selected_fire_curve else None

        self.curve_combo.clear()

        names = self.project.fire_library.get_names()
        self.curve_combo.addItems(names)

        # Restore previous selection
        if current_selection_name:
            idx = self.curve_combo.findText(current_selection_name)
            if idx >= 0:
                self.curve_combo.setCurrentIndex(idx)
        elif self.curve_combo.count() > 0:
            # Default to first curve if nothing selected
            self.curve_combo.setCurrentIndex(0)
            self.on_assignment_changed()  # Trigger save of default

        self.curve_combo.blockSignals(False)
        self._update_info()

    def on_assignment_changed(self):
        """Called when combobox selection changes."""
        curve_name = self.curve_combo.currentText()
        if not curve_name:
            return

        config = self.project.fire_library.get_fire_curve(curve_name)
        if config:
            self.project.selected_fire_curve = config
            self._update_info()

    def load_from_state(self):
        """Loads the current selection from the project state."""
        self.refresh_combo()
        curve = self.project.selected_fire_curve
        if curve:
            idx = self.curve_combo.findText(curve.name)
            if idx >= 0:
                self.curve_combo.setCurrentIndex(idx)
        self._update_info()

    def _update_info(self):
        """Updates the info label with details about the selected fire curve."""
        curve = self.project.selected_fire_curve
        if curve:
            txt = f"<b>Název:</b> {curve.name}<br>"
            txt += f"<b>Typ:</b> {curve.type.value}<br>"

            # Add type-specific info
            if curve.type == FireCurveType.STANDARD:
                from temperatureanalysis.model.bc import StandardFireCurveConfig
                if isinstance(curve, StandardFireCurveConfig):
                    txt += f"<b>Křivka:</b> {curve.curve_type.value}<br>"

            elif curve.type == FireCurveType.TABULATED:
                from temperatureanalysis.model.bc import TabulatedFireCurveConfig
                if isinstance(curve, TabulatedFireCurveConfig):
                    num_points = len(curve.times)
                    txt += f"<b>Počet bodů:</b> {num_points}<br>"
                    if num_points > 0:
                        max_time = max(curve.times) if curve.times else 0
                        txt += f"<b>Maximální čas:</b> {max_time:.0f} s<br>"

            elif curve.type == FireCurveType.ZONAL:
                from temperatureanalysis.model.bc import ZonalFireCurveConfig
                if isinstance(curve, ZonalFireCurveConfig):
                    num_zones = len(curve.zones)
                    txt += f"<b>Počet zón:</b> {num_zones}<br>"

            # Add description if available
            if curve.description:
                txt += f"<br><i>{curve.description}</i>"

            self.lbl_info.setText(txt)
        else:
            self.lbl_info.setText("Žádná křivka není vybrána.")
