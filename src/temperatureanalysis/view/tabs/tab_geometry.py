import os
import re
import unicodedata
from typing import Optional, List, Dict

from PySide6 import QtCore
from PySide6.QtGui import QPixmap, QPalette, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QDoubleSpinBox, QComboBox, QStackedWidget, QLabel, QDialog, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QEvent

from temperatureanalysis.model.state import ProjectState, PredefinedParams, CircleParams, BoxParams
from temperatureanalysis.model.profiles import (
    PROFILE_GROUPS, ALL_PROFILES, OutlineShape, ProfileGroupKey, CustomTunnelShape
)

from temperatureanalysis.config import ASSETS_PATH


PROFILE_IMAGE_MAP = {
    "Jednokolejný tunel - Konvenční ražba (do 160 km/h)": "jednokolejny_000_160_konvencni_razba",
    "Jednokolejný tunel - Konvenční ražba (od 161 km/h do 230 km/h)": "jednokolejny_161_230_konvencni_razba",
    "Jednokolejný tunel - Konvenční ražba (od 231 km/h do 300 km/h)": "jednokolejny_231_300_konvencni_razba",
    "Jednokolejný tunel - Mechanizovaná ražba (do 160 km/h)": "jednokolejny_000_160_mechanizovana_razba",
    "Jednokolejný tunel - Mechanizovaná ražba (od 161 km/h do 230 km/h)": "jednokolejny_161_230_mechanizovana_razba",
    "Jednokolejný tunel - Mechanizovaná ražba (od 231 km/h do 300 km/h)": "jednokolejny_231_300_mechanizovana_razba",
    "Dvoukolejný tunel - Konvenční ražba (do 160 km/h)": "dvoukolejny_000_160_konvencni_razba",
    "Dvoukolejný tunel - Konvenční ražba (od 161 km/h do 230 km/h)": "dvoukolejny_161_230_konvencni_razba",
    "Dvoukolejný tunel - Konvenční ražba (od 231 km/h do 300 km/h)": "dvoukolejny_231_300_konvencni_razba",
    "Tunel T-7,5, ražený": "silnicni_t7_5_razeny",
    "Tunel T-8,0, ražený": "silnicni_t8_0_razeny",
    "Tunel T-9,0, ražený": "silnicni_t9_0_razeny",
    "Tunel T-9,5, ražený": "silnicni_t9_5_razeny",
    "Tunel T-8,0, hloubený": "silnicni_t8_0_hloubeny",
}


# ==========================================
# HELPER WIDGETS
# ==========================================

class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed = False
        self._original_pixmap: Optional[QPixmap] = None

        # Enable responsive resizing:
        # 1. Minimum width 1 allows the label to shrink below image size
        self.setMinimumWidth(1)
        # 2. Ignored size policy tells layout "I don't care about my content's size, just give me space"
        #    Preferred height allows it to grow vertically to fit aspect ratio
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setAlignment(Qt.AlignCenter)

    def set_source_pixmap(self, pixmap: Optional[QPixmap]):
        self._original_pixmap = pixmap
        if pixmap is None:
            self.clear()
        else:
            self._update_display()

    def resizeEvent(self, event):
        if self._original_pixmap:
            self._update_display()
        super().resizeEvent(event)

    def _update_display(self):
        if self._original_pixmap and not self._original_pixmap.isNull():
            w = self.width()
            if w > 0:
                # Scale to current width, keeping aspect ratio
                scaled = self._original_pixmap.scaledToWidth(w, Qt.SmoothTransformation)
                super().setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed and event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        self._pressed = False
        super().mouseReleaseEvent(event)


class ScalableLabel(QLabel):
    """A label that scales its pixmap content to fill available space, maintaining aspect ratio."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._original_pixmap = pixmap
        self.setAlignment(Qt.AlignCenter)
        # Ignored size policy allows the label to shrink/grow freely based on layout
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(1, 1)

    def resizeEvent(self, event):
        if not self._original_pixmap.isNull():
            # Scale pixmap to the current size of the widget
            scaled = self._original_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
        super().resizeEvent(event)


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path: str, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 800)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pix = QPixmap(image_path)
        # Use custom ScalableLabel instead of QScrollArea
        self.image_label = ScalableLabel(pix, self)

        layout.addWidget(self.image_label, 1)  # Expand to fill space

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
            self.type_combo.setCurrentText(CustomTunnelShape.BOX)
            self.stack.setCurrentWidget(self.page_box)

            # 2. Update Box Spinboxes
            params = self.project.geometry.parameters
            if isinstance(params, BoxParams):
                self.box_width_spin.setValue(params.width)
                self.box_height_spin.setValue(params.height)
                self.box_thick_spin.setValue(params.thickness)

        if shape == CustomTunnelShape.CIRCLE:  # Circle
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
        self.current_image_path: Optional[str] = None

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)

        # --- Form Container ---
        self.form_widget = QWidget()
        self.layout_form = QFormLayout(self.form_widget)
        self.layout_form.setContentsMargins(0, 0, 0, 0)

        self.sub_combo = QComboBox()
        self.sub_combo.currentTextChanged.connect(self.on_profile_changed)
        self.layout_form.addRow("Varianta:", self.sub_combo)

        p = self.project.geometry.parameters
        val_t = p.thickness if isinstance(p, PredefinedParams) else 0.4

        self.thick_spin = QDoubleSpinBox()
        self.thick_spin.setRange(0.05, 2.0)
        self.thick_spin.setSingleStep(0.05)
        self.thick_spin.setValue(val_t)
        self.thick_spin.valueChanged.connect(self.on_thickness_changed)
        self.layout_form.addRow("Tloušťka [m]:", self.thick_spin)

        self.layout_main.addWidget(self.form_widget)

        # --- Image Preview (Clickable) ---
        self.lbl_image = ClickableLabel()
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setMinimumHeight(150)
        self.lbl_image.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                    }
                    QLabel:hover {
                        border: 1px solid #aaa;
                        background-color: rgba(0,0,0,5);
                    }
                """)
        self.lbl_image.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        self.lbl_image.setText("Náhled nedostupný")
        self.lbl_image.clicked.connect(self.on_image_clicked)
        self.layout_main.addWidget(self.lbl_image)

        # --- Source Label ---
        self.lbl_source = QLabel()
        self.lbl_source.setAlignment(Qt.AlignCenter)
        self.lbl_source.setWordWrap(True)
        self.layout_main.addWidget(self.lbl_source)

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
        self.update_image_preview()

    def on_thickness_changed(self, val: float) -> None:
        if isinstance(self.project.geometry.parameters, PredefinedParams):
            self.project.geometry.parameters.thickness = val
            self.param_changed.emit()

    def load_from_state(self):
        # Refresh logic
        if isinstance(self.project.geometry.parameters, PredefinedParams):
            self.thick_spin.setValue(self.project.geometry.parameters.thickness)
            # Combo population handles the name setting
            self.update_image_preview()

    # --- IMAGE & SOURCE LOGIC ---

    def update_image_preview(self):
        """Updates the image label based on selection and current theme."""
        # 1. Update Source Text
        group_key = self.project.geometry.group_key
        source_text = ""
        if group_key == ProfileGroupKey.VL5_ROAD:
            source_text = (
                "MINISTERSTVO DOPRAVY. "
                "<i>Vzorové listy staveb pozemních komunikací: VL 5 – Tunely.</i> "
                "Praha: Ministerstvo dopravy, 2024.<br>"
                # "<span style='color: gray; font-size: small;'>"
                # "Schváleno pod č.j. MD-42962/2023-930/2.</span>"
            )
        elif group_key == ProfileGroupKey.RAIL_SINGLE:
            source_text = (
                "SŽDC. "
                "<i>Vzorový list: Světlý tunelový průřez jednokolejného tunelu.</i> "
                "Praha: SŽDC, s.o., 2010.<br>"
                # "<span style='color: gray; font-size: small;'>"
                # "Schváleno pod č.j. S 65027/09 - OTH.</span>"
            )
        elif group_key == ProfileGroupKey.RAIL_DOUBLE:
            source_text = (
                "SŽDC. "
                "<i>Vzorový list: Světlý tunelový průřez dvoukolejného tunelu (konvenční ražba).</i> "
                "Praha: SŽDC, s.o., 2011.<br>"
                # "<span style='color: gray; font-size: small;'>"
                # "Schváleno pod č.j. S60135/2011-OTH.</span>"
            )

        self.lbl_source.setText(source_text)

        # 2. Update Image
        profile_name = self.sub_combo.currentText()
        if not profile_name:
            self.lbl_image.clear()
            self.current_image_path = None
            return

        # Determine Theme (Dark/Light)
        text_color = self.palette().color(QPalette.WindowText)
        is_dark = text_color.lightness() > 128
        mode_suffix = "dark" if is_dark else "light"

        # Determine Filename
        filename = self._resolve_filename(profile_name)

        # Construct Path: assets/profiles/{filename}_{mode}.png
        image_path = os.path.join(ASSETS_PATH, "profiles", f"{filename}_{mode_suffix}.png")
        self.current_image_path = image_path

        # Load
        if os.path.exists(image_path):
            pix = QPixmap(image_path)
            self.lbl_image.set_source_pixmap(pix)
            self.lbl_image.setText("")  # Clear text
            self.lbl_image.setToolTip("Klikněte pro zvětšení")
        else:
            self.lbl_image.set_source_pixmap(
                None)  # Clears and shows text in ClickableLabel logic if implemented, but here we set text manually
            self.lbl_image.clear()
            self.lbl_image.setText(f"Obrázek nenalezen:\n{filename}_{mode_suffix}.png")
            self.lbl_image.setToolTip("")
            self.current_image_path = None

    def on_image_clicked(self):
        if self.current_image_path and os.path.exists(self.current_image_path):
            title = self.sub_combo.currentText()
            dlg = ImagePreviewDialog(self.current_image_path, title, self)
            dlg.exec()

    def _resolve_filename(self, profile_name: str) -> str:
        """
        Maps profile display name to a base filename.
        """
        if profile_name in PROFILE_IMAGE_MAP:
            return PROFILE_IMAGE_MAP[profile_name]

        # Auto-Slugify (Fallback)
        norm = unicodedata.normalize('NFKD', profile_name).encode('ASCII', 'ignore').decode('utf-8')
        slug = norm.lower()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        return slug

    def changeEvent(self, event: QEvent) -> None:
        """Detect system theme changes and update image."""
        if event.type() == QEvent.PaletteChange:
            self.update_image_preview()
        super().changeEvent(event)

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
        idx = self.category_combo.findText(current_key)
        if idx != -1:
            self.category_combo.setCurrentIndex(idx)

            if current_key == ProfileGroupKey.CUSTOM:
                self.stack.setCurrentIndex(1)
                self.page_custom.load_from_state()
            else:
                self.stack.setCurrentIndex(0)
                if current_key in PROFILE_GROUPS:
                    self.page_standard.populate_profiles(PROFILE_GROUPS[current_key])
                    self.page_standard.load_from_state()

        self.category_combo.blockSignals(False)
