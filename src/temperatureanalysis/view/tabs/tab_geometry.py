from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QDoubleSpinBox, QComboBox, QStackedWidget, QLabel
)
from PySide6.QtCore import Signal

from temperatureanalysis.model.state import ProjectState, PredefinedParams, CircleParams, BoxParams
from temperatureanalysis.model.profiles import (
    PROFILE_GROUPS, ALL_PROFILES, OutlineShape, ProfileGroupKey, CustomTunnelShape
)


# ==========================================
# 1. CUSTOM DEFINITION WIDGETS
# ==========================================

class CustomShapeWidget(QWidget):
    # Signal to notify parent
    param_changed = Signal()

    def __init__(self, project_state: ProjectState) -> None:
        super().__init__()
        self.project = project_state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.type_combo = QComboBox()
        # Add Custom Types based on Enum values
        self.type_combo.addItem(CustomTunnelShape.CIRCLE)
        self.type_combo.addItem(CustomTunnelShape.BOX)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)

        form = QFormLayout()
        form.addRow("Tvar:", self.type_combo)
        layout.addLayout(form)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Initialize pages and store references to spinboxes
        self.page_circle = QWidget()
        self._setup_circle_page(self.page_circle)

        self.page_box = QWidget()
        self._setup_box_page(self.page_box)

        self.stack.addWidget(self.page_circle)
        self.stack.addWidget(self.page_box)

        # Initial sync
        self.load_from_state()

    def on_type_changed(self, text: str) -> None:
        if text == CustomTunnelShape.BOX.value:
            self.project.geometry.set_custom_box()
            self.stack.setCurrentWidget(self.page_box)
        else:
            self.project.geometry.set_custom_circle()
            self.stack.setCurrentWidget(self.page_circle)
        self.param_changed.emit()

    def _setup_circle_page(self, parent: QWidget) -> None:
        layout = QFormLayout(parent)

        self.circle_radius_spin = QDoubleSpinBox()
        self.circle_radius_spin.setRange(0.1, 50.0)
        self.circle_radius_spin.setValue(6.0)
        self.circle_radius_spin.valueChanged.connect(lambda v: self._update_param("radius", v))
        layout.addRow("Poloměr [m]:", self.circle_radius_spin)

        self.circle_center_spin = QDoubleSpinBox()
        self.circle_center_spin.setRange(0., 5.0)
        self.circle_center_spin.setValue(4.0)
        self.circle_center_spin.valueChanged.connect(lambda v: self._update_param("center_y", v))
        layout.addRow("Y-Střed [m]:", self.circle_center_spin)

        self.circle_thick_spin = QDoubleSpinBox()
        self.circle_thick_spin.setRange(0.05, 5.0)
        self.circle_thick_spin.setSingleStep(0.05)
        self.circle_thick_spin.setValue(0.5)
        self.circle_thick_spin.valueChanged.connect(lambda v: self._update_param("thickness", v))
        layout.addRow("Tloušťka [m]:", self.circle_thick_spin)

    def _setup_box_page(self, parent: QWidget) -> None:
        layout = QFormLayout(parent)

        self.box_width_spin = QDoubleSpinBox()
        self.box_width_spin.setRange(0.1, 100.0)
        self.box_width_spin.setValue(6)
        self.box_width_spin.valueChanged.connect(lambda v: self._update_param("width", v))
        layout.addRow("Šířka [m]:", self.box_width_spin)

        self.box_height_spin = QDoubleSpinBox()
        self.box_height_spin.setRange(0.1, 100.0)
        self.box_height_spin.setValue(4)
        self.box_height_spin.valueChanged.connect(lambda v: self._update_param("height", v))
        layout.addRow("Výška [m]:", self.box_height_spin)

        self.box_thick_spin = QDoubleSpinBox()
        self.box_thick_spin.setRange(0.05, 5.0)
        self.box_thick_spin.setSingleStep(0.05)
        self.box_thick_spin.setValue(0.5)
        self.box_thick_spin.valueChanged.connect(lambda v: self._update_param("thickness", v))
        layout.addRow("Tloušťka [m]:", self.box_thick_spin)

    def _update_param(self, key: str, value: float) -> None:
        # Check if attribute exists on current params object to avoid errors during transitions
        if hasattr(self.project.geometry.parameters, key):
            setattr(self.project.geometry.parameters, key, value)
            self.param_changed.emit()

    def load_from_state(self):
        """
        Updates UI widgets to match ProjectState.
        """
        self.blockSignals(True)
        self.type_combo.blockSignals(True)

        # 1. Update Shape Selector
        shape = self.project.geometry.custom_shape
        if shape == CustomTunnelShape.BOX:
            print("Updated box!")
            self.type_combo.setCurrentText(CustomTunnelShape.BOX)
            self.stack.setCurrentWidget(self.page_box)

            # 2. Update Box Spinboxes
            params = self.project.geometry.parameters
            if isinstance(params, BoxParams):
                self.box_width_spin.setValue(params.width)
                self.box_height_spin.setValue(params.height)
                self.box_thick_spin.setValue(params.thickness)

        if shape == CustomTunnelShape.CIRCLE:  # Circle
            print("Updated circle!")
            self.type_combo.setCurrentText(CustomTunnelShape.CIRCLE)
            self.stack.setCurrentWidget(self.page_circle)

            # 2. Update Circle Spinboxes
            params = self.project.geometry.parameters
            if isinstance(params, CircleParams):
                self.circle_radius_spin.setValue(params.radius)
                self.circle_center_spin.setValue(params.center_y)
                self.circle_thick_spin.setValue(params.thickness)

        self.type_combo.blockSignals(False)
        self.blockSignals(False)


# ==========================================
# 2. STANDARD PROFILE WIDGET
# ==========================================

class StandardProfileWidget(QWidget):
    param_changed = Signal()

    def __init__(self, project_state: ProjectState) -> None:
        super().__init__()
        self.project = project_state

        layout = QFormLayout(self)

        self.sub_combo = QComboBox()
        self.sub_combo.currentTextChanged.connect(self.on_profile_changed)
        layout.addRow("Varianta:", self.sub_combo)

        p = self.project.geometry.parameters
        val_t = p.thickness if isinstance(p, PredefinedParams) else 0.4

        self.thick_spin = QDoubleSpinBox()
        self.thick_spin.setRange(0.05, 2.0)
        self.thick_spin.setSingleStep(0.05)
        self.thick_spin.setValue(val_t)
        self.thick_spin.valueChanged.connect(self.on_thickness_changed)
        layout.addRow("Tloušťka [m]:", self.thick_spin)

    def populate_profiles(self, profile_list: List[str]) -> None:
        self.sub_combo.blockSignals(True)
        self.sub_combo.clear()
        self.sub_combo.addItems(profile_list)

        # If current state matches a profile in this list, select it
        current = ""
        if isinstance(self.project.geometry.parameters, PredefinedParams):
            current = self.project.geometry.parameters.profile_name

        if current in profile_list:
            self.sub_combo.setCurrentText(current)
        elif self.sub_combo.count() > 0:
            self.sub_combo.setCurrentIndex(0)
            self.on_profile_changed(self.sub_combo.currentText())

        self.sub_combo.blockSignals(False)

    def on_profile_changed(self, text: str) -> None:
        if not text: return

        # Ensure we are in predefined mode data-wise
        self.project.geometry.set_predefined(self.project.geometry.group_key)

        # Update name
        if isinstance(self.project.geometry.parameters, PredefinedParams):
            self.project.geometry.parameters.profile_name = text

        self.param_changed.emit()

    def on_thickness_changed(self, val: float) -> None:
        if isinstance(self.project.geometry.parameters, PredefinedParams):
            self.project.geometry.parameters.thickness = val
            self.param_changed.emit()

    def load_from_state(self):
        # Refresh logic
        if isinstance(self.project.geometry.parameters, PredefinedParams):
            self.thick_spin.setValue(self.project.geometry.parameters.thickness)
            # Combo population handles the name setting


# ==========================================
# 3. MAIN GEOMETRY CONTROL PANEL
# ==========================================

class GeometryControlPanel(QWidget):
    data_changed = Signal()

    def __init__(self, project_state: ProjectState) -> None:
        super().__init__()
        self.project = project_state

        self.layout_main = QVBoxLayout(self)

        # 1. Main Category Selector
        self.category_combo = QComboBox()
        # Add items from Enum
        self.category_items = [
            ProfileGroupKey.VL5_ROAD.value,
            ProfileGroupKey.RAIL_SINGLE.value,
            ProfileGroupKey.RAIL_DOUBLE.value,
            ProfileGroupKey.CUSTOM.value
        ]
        self.category_combo.addItems(self.category_items)
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)

        cat_group = QGroupBox("Kategorie Profilu")
        cat_layout = QVBoxLayout(cat_group)
        cat_layout.addWidget(self.category_combo)
        self.layout_main.addWidget(cat_group)

        # 2. Stacked Content
        self.stack = QStackedWidget()
        self.layout_main.addWidget(self.stack)

        self.page_standard = StandardProfileWidget(self.project)
        self.page_standard.param_changed.connect(self.data_changed)

        self.page_custom = CustomShapeWidget(self.project)
        self.page_custom.param_changed.connect(self.data_changed)

        self.stack.addWidget(self.page_standard)  # Index 0
        self.stack.addWidget(self.page_custom)  # Index 1

        self.layout_main.addStretch()

        # Initial State Sync
        self.load_from_state()

    def on_category_changed(self, index: int) -> None:
        category_text = self.category_items[index]

        if category_text == ProfileGroupKey.CUSTOM.value:
            # Switch Data Model to Custom
            # Default to box if not set
            if not self.project.geometry.custom_shape:
                self.project.geometry.set_custom_box()
            else:
                # Re-apply existing custom shape to ensure params match
                if self.project.geometry.custom_shape == CustomTunnelShape.BOX:
                    self.project.geometry.set_custom_box()
                else:
                    self.project.geometry.set_custom_circle()

            self.stack.setCurrentIndex(1)
            # Trigger update in custom widget to match state
            self.page_custom.load_from_state()

        else:
            # Switch Data Model to Predefined Group
            # Map text back to Enum member
            group_enum = ProfileGroupKey(category_text)
            self.project.geometry.set_predefined(group_enum)

            self.stack.setCurrentIndex(0)
            if category_text in PROFILE_GROUPS:
                self.page_standard.populate_profiles(PROFILE_GROUPS[category_text])

        self.data_changed.emit()

    def load_from_state(self) -> None:
        """Sync UI with current ProjectState."""
        self.category_combo.blockSignals(True)

        current_key = self.project.geometry.group_key

        # Find index in combo
        idx = self.category_combo.findText(current_key.value)
        if idx != -1:
            self.category_combo.setCurrentIndex(idx)

            if current_key == ProfileGroupKey.CUSTOM:
                self.stack.setCurrentIndex(1)
                self.page_custom.load_from_state()
            else:
                self.stack.setCurrentIndex(0)
                if current_key.value in PROFILE_GROUPS:
                    self.page_standard.populate_profiles(PROFILE_GROUPS[current_key.value])
                    self.page_standard.load_from_state()

        self.category_combo.blockSignals(False)
