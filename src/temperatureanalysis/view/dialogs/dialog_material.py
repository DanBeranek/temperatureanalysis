"""
Modal Dialog for Material Properties Management
Using PyQtGraph for plots.
Refactored to separate editors for Generic and Concrete materials.
"""
import copy
import os
import csv
import logging
import pyqtgraph as pg
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QGroupBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QWidget,
    QLineEdit, QFileDialog, QMessageBox, QDoubleSpinBox,
    QComboBox, QStackedWidget, QSizePolicy, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer

from temperatureanalysis.model.materials import (
    Material, MaterialLibrary, MaterialType, ThermalConductivityBoundary,
    GenericMaterial, ConcreteMaterial, MaterialProperty,
    TemperatureDependentProperty, PROPERTY_METADATA, PropertyMetadata
)

logger = logging.getLogger(__name__)

# ==============================================================================
# EDITOR WIDGETS
# ==============================================================================

class GenericMaterialEditor(QWidget):
    """
    Editor for GenericMaterial.
    Contains tabs for Conductivity, Specific Heat, and Density.
    Each tab has a table to edit the curve points.
    """
    dataChanged = Signal()
    activePropertyChanged = Signal(TemperatureDependentProperty)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_material: Optional[GenericMaterial] = None

        # Timer for debouncing table changes (prevents C++ object access issues)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(0)
        self._save_timer.timeout.connect(self._on_timer_save)
        self._current_page = None  # Store current page reference for timer callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Create Tabs dynamically via Enum?
        # Manual creation allows us to order them specifically and keep references

        # 1. Conductivity
        meta_k = PROPERTY_METADATA[TemperatureDependentProperty.CONDUCTIVITY]
        self.tab_cond = self._create_property_tab(meta_k)
        self.tabs.addTab(self.tab_cond, meta_k.label)

        # 2. Specific Heat
        meta_c = PROPERTY_METADATA[TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY]
        self.tab_heat = self._create_property_tab(meta_c)
        self.tabs.addTab(self.tab_heat, meta_c.label)

        # 3. Density
        meta_d = PROPERTY_METADATA[TemperatureDependentProperty.DENSITY]
        self.tab_dens = self._create_property_tab(meta_d)
        self.tabs.addTab(self.tab_dens, meta_d.label)

        layout.addWidget(self.tabs)

    def _create_property_tab(self, prop_metadata: PropertyMetadata) -> QWidget:
        """Creates a tab page with a table and tool buttons."""
        page = QWidget()
        lay = QVBoxLayout(page)

        lay.addWidget(QLabel(f"Definice křivky:"))

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Teplota (°C)", f"{prop_metadata.label} ({prop_metadata.unit})"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(table)

        # Tools
        h_tools = QHBoxLayout()
        btn_add_row = QPushButton("+ Bod")
        btn_del_row = QPushButton("- Bod")
        btn_load_csv = QPushButton("Načíst křivku...")

        h_tools.addWidget(btn_add_row)
        h_tools.addWidget(btn_del_row)
        h_tools.addWidget(btn_load_csv)
        h_tools.addStretch()
        lay.addLayout(h_tools)

        # Store references on the widget for easy access later
        page.table = table

        # Internal Logic
        def add_row():
            """
            DATA-FIRST APPROACH:
            1. Read all points from UI.
            2. Calculate new point.
            3. Update Model directly (which sorts them).
            4. Reload UI from Model.
            """
            # Identify Property
            prop = None
            if page == self.tab_cond: prop = self.current_material.conductivity
            elif page == self.tab_heat: prop = self.current_material.specific_heat_capacity
            elif page == self.tab_dens: prop = self.current_material.density

            if not prop: return

            # Block table signals to prevent timer trigger during manual update
            table.blockSignals(True)
            try:
                # 1. Scrape current UI data
                points = []
                for r in range(table.rowCount()):
                    try:
                        t = float(table.item(r, 0).text())
                        v = float(table.item(r, 1).text())
                        points.append((t, v))
                    except (ValueError, AttributeError): pass

                points.sort(key=lambda x: x[0])

                # 2. Calculate insertion point
                if not points:
                    points = [(20.0, 0.0), (1200.0, 0.0)]
                elif len(points) == 1:
                    # Extend range
                    points.append((points[0][0] + 100.0, points[0][1]))
                else:
                    # Find max gap
                    max_gap = -1.0
                    best_idx = 0
                    for i in range(len(points) - 1):
                        gap = points[i+1][0] - points[i][0]
                        if gap > max_gap:
                            max_gap = gap
                            best_idx = i

                    # Split gap
                    t1, v1 = points[best_idx]
                    t2, v2 = points[best_idx+1]

                    new_t = t1 + max_gap / 2.0
                    ratio = (new_t - t1) / max_gap
                    new_v = v1 + ratio * (v2 - v1)

                    points.append((new_t, new_v))

                # 3. Update Model
                # sort points
                points.sort(key=lambda x: x[0])
                t_list = [p[0] for p in points]
                v_list = [p[1] for p in points]
                prop.set_curve(t_list, v_list)

                # 4. Refresh UI (signals still blocked)
                self._load_prop_to_tab(page, prop)
            finally:
                # Always unblock signals
                table.blockSignals(False)

            # 5. Emit change signal AFTER table is fully updated
            self.dataChanged.emit()

        def del_row():
            # ENFORCE MINIMUM 2 POINTS
            if table.rowCount() <= 2:
                QMessageBox.warning(self, "Varování", "Materiál musí být definován alespoň 2 body.")
                return

            table.blockSignals(True)
            try:
                r = table.currentRow()
                if r >= 0:
                    table.removeRow(r)
                    self._save_current_prop(page)
                else:
                    # Optional: Remove last row if nothing selected
                    table.removeRow(table.rowCount() - 1)
                    self._save_current_prop(page)
            finally:
                table.blockSignals(False)

        def load_csv():
            self._import_csv_curve(page)

        btn_add_row.clicked.connect(add_row)
        btn_del_row.clicked.connect(del_row)
        btn_load_csv.clicked.connect(load_csv)

        # FIX: Defer the save to allow item editor to close cleanly
        # Use instance timer to prevent C++ object access issues
        def on_item_changed(item):
            self._current_page = page
            self._save_timer.start()

        table.itemChanged.connect(on_item_changed)

        return page

    def set_material(self, material: GenericMaterial):
        self.current_material = material
        self.blockSignals(True) # Prevent signals during load

        self._load_prop_to_tab(self.tab_cond, material.conductivity)
        self._load_prop_to_tab(self.tab_heat, material.specific_heat_capacity)
        self._load_prop_to_tab(self.tab_dens, material.density)

        self.blockSignals(False)
        # Trigger initial plot update
        self._on_tab_changed(self.tabs.currentIndex())

    def _on_timer_save(self):
        """Timer callback to save current page data (prevents C++ object issues)."""
        if self._current_page:
            self._save_current_prop(self._current_page)

    def _get_prop_for_page(self, page):
        if page == self.tab_cond:
            return self.current_material.conductivity
        elif page == self.tab_heat:
            return self.current_material.specific_heat_capacity
        elif page == self.tab_dens:
            return self.current_material.density
        return None

    def _load_prop_to_tab(self, tab_page, prop: MaterialProperty):
        table = tab_page.table
        table.blockSignals(True)
        table.setRowCount(0)

        # Ensure we have data to display
        if not prop.temperatures or len(prop.temperatures) < 2:
            # Fallback: Create 20-1200 range based on existing value or 0
            base_val = prop.values[0] if prop.values else 0.0
            prop.temperatures = [20.0, 1200.0]
            prop.values = [base_val, base_val]

        table.setRowCount(len(prop.temperatures))
        for i, (t, v) in enumerate(zip(prop.temperatures, prop.values)):
            table.setItem(i, 0, QTableWidgetItem(f"{t:.1f}"))
            table.setItem(i, 1, QTableWidgetItem(f"{v:.3f}"))

        table.blockSignals(False)

    def _save_current_prop(self, tab_page):
        if not self.current_material: return
        prop = self._get_prop_for_page(tab_page)
        if not prop: return

        t_list, v_list = [], []
        table = tab_page.table
        for r in range(table.rowCount()):
            try:
                item_t = table.item(r, 0)
                item_v = table.item(r, 1)
                if item_t and item_v:
                    t = float(item_t.text())
                    v = float(item_v.text())
                    t_list.append(t)
                    v_list.append(v)
            except (ValueError, AttributeError):
                pass

        # This sorts the data internally
        prop.set_curve(t_list, v_list)

        # Reload the table from the sorted model to reflect the new order
        self._load_prop_to_tab(tab_page, prop)

        self.dataChanged.emit()

    def _import_csv_curve(self, tab_page):
        path, _ = QFileDialog.getOpenFileName(self, "Načíst křivku (CSV)", "", "CSV (*.csv);;Text (*.txt)")
        if not path: return

        try:
            data_points = []
            with open(path, 'r', encoding='utf-8-sig') as f:
                line = f.readline()
                delimiter = ';' if ';' in line else ','
                f.seek(0)
                reader = csv.reader(f, delimiter=delimiter)

                for row in reader:
                    if not row or len(row) < 2: continue
                    if not row[0][0].isdigit() and not row[0].lstrip('-')[0].isdigit(): continue
                    try:
                        t = float(row[0].replace(',', '.'))
                        v = float(row[1].replace(',', '.'))
                        data_points.append((t, v))
                    except ValueError: continue

            if data_points:
                if len(data_points) < 2:
                    QMessageBox.warning(self, "Chyba", "CSV musí obsahovat alespoň 2 body (teplotní rozsah).")
                    return

                data_points.sort(key=lambda x: x[0])
                table = tab_page.table
                table.blockSignals(True)
                table.setRowCount(len(data_points))
                for i, (t, v) in enumerate(data_points):
                    table.setItem(i, 0, QTableWidgetItem(str(t)))
                    table.setItem(i, 1, QTableWidgetItem(str(v)))
                table.blockSignals(False)

                self._save_current_prop(tab_page)
                QMessageBox.information(self, "Info", f"Načteno {len(data_points)} bodů.")
            else:
                QMessageBox.warning(self, "Varování", "Nenalezena žádná platná data.")

        except Exception as e:
            logger.error(f"Failed to load CSV property: {e}")
            QMessageBox.critical(self, "Chyba", str(e))

    def _on_tab_changed(self, index: int):
        if index == 0: self.activePropertyChanged.emit(TemperatureDependentProperty.CONDUCTIVITY)
        elif index == 1: self.activePropertyChanged.emit(TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY)
        elif index == 2: self.activePropertyChanged.emit(TemperatureDependentProperty.DENSITY)

    def select_tab(self, prop_type: TemperatureDependentProperty):
        if prop_type == TemperatureDependentProperty.CONDUCTIVITY:
            self.tabs.setCurrentIndex(0)
        elif prop_type == TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY:
            self.tabs.setCurrentIndex(1)
        elif prop_type == TemperatureDependentProperty.DENSITY:
            self.tabs.setCurrentIndex(2)


class ConcreteMaterialEditor(QWidget):
    """
    Editor for ConcreteMaterial (Eurocode).
    """
    dataChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_material: Optional[ConcreteMaterial] = None
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.spin_dens = QDoubleSpinBox()
        self.spin_dens.setRange(500, 5000)
        self.spin_dens.setSuffix(" kg/m³")
        self.spin_dens.valueChanged.connect(self._on_value_changed)
        layout.addRow("Počáteční hustota:", self.spin_dens)

        self.spin_moist = QDoubleSpinBox()
        self.spin_moist.setRange(0, 100)
        self.spin_moist.setSuffix(" %")
        self.spin_moist.valueChanged.connect(self._on_value_changed)
        layout.addRow("Vlhkost:", self.spin_moist)

        self.combo_bound = QComboBox()
        self.combo_bound.addItem("Horní mez (Upper)", ThermalConductivityBoundary.UPPER)
        self.combo_bound.addItem("Dolní mez (Lower)", ThermalConductivityBoundary.LOWER)
        self.combo_bound.currentIndexChanged.connect(self._on_value_changed)
        layout.addRow("Mez vodivosti:", self.combo_bound)

        layout.addRow(QLabel("\nPoznámka: Teplotní závislosti jsou vypočteny automaticky\ndle norem Eurokód 2."))

        # Add stretch to push form to top
        v_spacer = QWidget()
        v_spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addRow(v_spacer)

    def set_material(self, material: ConcreteMaterial):
        self.current_material = material
        self.blockSignals(True)
        self.spin_dens.blockSignals(True)
        self.spin_moist.blockSignals(True)
        self.combo_bound.blockSignals(True)

        self.spin_dens.setValue(material.initial_density)
        self.spin_moist.setValue(material.initial_moisture_content)
        idx = self.combo_bound.findData(material.conductivity_boundary)
        self.combo_bound.setCurrentIndex(idx)

        self.combo_bound.blockSignals(False)
        self.spin_moist.blockSignals(False)
        self.spin_dens.blockSignals(False)
        self.blockSignals(False)

    def _on_value_changed(self):
        if not self.current_material: return
        self.current_material.initial_density = self.spin_dens.value()
        self.current_material.initial_moisture_content = self.spin_moist.value()
        self.current_material.conductivity_boundary = self.combo_bound.currentData()
        self.dataChanged.emit()


# ==============================================================================
# MAIN DIALOG
# ==============================================================================

class MaterialsDialog(QDialog):
    def __init__(self, project_state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Knihovna Materiálů")
        self.resize(1200, 750)

        self.project = project_state
        # DEEP COPY for Safe Editing

        if not hasattr(self.project, "material_library"):
            self.project.material_library = MaterialLibrary()

        self.working_library = copy.deepcopy(self.project.material_library)

        self.current_material = None
        self.active_prop_key = TemperatureDependentProperty.CONDUCTIVITY

        # Store plotting widgets for tabs
        self.plot_widgets: dict[TemperatureDependentProperty, pg.PlotWidget] = {}

        self._init_ui()
        self._refresh_list()

        if self.project.selected_material:
            items = self.list_widget.findItems(self.project.selected_material.name, Qt.MatchExactly)
            if items:
                self.list_widget.setCurrentItem(items[0])

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # --- TOP CONTENT AREA (Horizontal) ---
        h_content = QHBoxLayout()
        layout.addLayout(h_content)

        # --- LEFT: Material List ---
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Dostupné materiály:"))

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.list_widget)

        btn_add = QPushButton("Nový Materiál")
        btn_add.clicked.connect(self.on_add_clicked)
        left_layout.addWidget(btn_add)

        btn_import = QPushButton("Importovat nový z CSV...")
        btn_import.clicked.connect(self.on_import_clicked)
        left_layout.addWidget(btn_import)

        h_content.addLayout(left_layout, stretch=1)

        # --- CENTER: Editors (Swappable) ---
        self.center_group = QGroupBox("Vlastnosti Materiálu")
        self.center_group.setEnabled(False)
        center_layout = QVBoxLayout(self.center_group)

        # Common Header (Name, Desc, Type)
        form = QFormLayout()
        self.edit_name = QLineEdit()
        self.edit_name.editingFinished.connect(self.on_name_changed)
        form.addRow("Název:", self.edit_name)

        self.edit_desc = QLineEdit()
        self.edit_desc.editingFinished.connect(self.on_desc_changed)
        form.addRow("Popis:", self.edit_desc)

        self.combo_type = QComboBox()
        self.combo_type.addItem("Vlastní", MaterialType.GENERIC)
        self.combo_type.addItem("Beton (Eurokód 2)", MaterialType.CONCRETE)
        self.combo_type.currentIndexChanged.connect(self.on_type_changed)
        form.addRow("Typ modelu:", self.combo_type)
        center_layout.addLayout(form)

        # Editor Stack
        self.stack = QStackedWidget()

        # Editor 1: Generic
        self.editor_generic = GenericMaterialEditor()
        self.editor_generic.dataChanged.connect(self._update_plot)
        self.editor_generic.activePropertyChanged.connect(self._on_generic_tab_changed)
        self.stack.addWidget(self.editor_generic)

        # Editor 2: Concrete
        self.editor_concrete = ConcreteMaterialEditor()
        self.editor_concrete.dataChanged.connect(self._update_plot)
        self.stack.addWidget(self.editor_concrete)

        center_layout.addWidget(self.stack)
        h_content.addWidget(self.center_group, stretch=2)

        # --- RIGHT: Plot ---
        self.plot_tabs = QTabWidget()
        # Add Tabs for each property type
        for prop in TemperatureDependentProperty:
            meta = PROPERTY_METADATA[prop]

            # Create Plot Widget
            plot = pg.PlotWidget()
            plot.setBackground('w')
            plot.showGrid(x=True, y=True)
            plot.setLabel('bottom', 'Teplota (°C)', color='black')
            plot.getAxis('bottom').setPen('k')
            plot.getAxis('left').setPen('k')
            plot.setTitle(meta.label, color='k')

            self.plot_widgets[prop] = plot
            self.plot_tabs.addTab(plot, meta.label)  # Use label for Tab Title

        self.plot_tabs.currentChanged.connect(self._on_plot_tab_changed)
        h_content.addWidget(self.plot_tabs, stretch=2)

        # --- BOTTOM: Standard Buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        self.button_box.button(QDialogButtonBox.Ok)
        self.button_box.button(QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Apply)

        self.button_box.clicked.connect(self.on_button_box_clicked)
        layout.addWidget(self.button_box)

    def on_button_box_clicked(self, button):
        role = self.button_box.buttonRole(button)

        if role == QDialogButtonBox.ApplyRole: # Apply
            self.save_changes()
            QMessageBox.information(self, "Uloženo", "Změny byly uloženy.")

        elif role == QDialogButtonBox.AcceptRole: # OK
            self.save_changes()
            self.accept()

        elif role == QDialogButtonBox.RejectRole: # Cancel
            self.reject()

    def save_changes(self):
        # Save Working Copy -> Project
        self.project.material_library = copy.deepcopy(self.working_library)

    def _refresh_list(self):
        curr = self.list_widget.currentRow()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for name in self.working_library.get_names():
            self.list_widget.addItem(name)
        self.list_widget.blockSignals(False)
        if self.list_widget.count() > 0:
            row = curr if curr >= 0 else 0
            self.list_widget.setCurrentRow(row)
        else:
            self.center_group.setEnabled(False)

    def on_selection_changed(self, current, previous):
        if not current: return
        name = current.text()
        mat = self.working_library.get_material(name)
        if not mat: return

        self.current_material = mat
        self.center_group.setEnabled(True)

        self.edit_name.setText(mat.name)
        self.edit_desc.setText(mat.description)

        is_concrete = (mat.type == MaterialType.CONCRETE)
        self.edit_name.setReadOnly(is_concrete)
        self.edit_desc.setReadOnly(is_concrete)
        self.combo_type.setVisible(not is_concrete)

        idx = self.combo_type.findData(mat.type)
        self.combo_type.blockSignals(True)
        self.combo_type.setCurrentIndex(idx)
        self.combo_type.blockSignals(False)

        if is_concrete:
            self.stack.setCurrentWidget(self.editor_concrete)
            self.editor_concrete.set_material(mat)
        else:
            self.stack.setCurrentWidget(self.editor_generic)
            self.editor_generic.set_material(mat)

        self._update_plot()

    def on_type_changed(self):
        if not self.current_material: return
        new_type = self.combo_type.currentData()
        if self.current_material.type == new_type: return

        new_mat = None
        if new_type == MaterialType.CONCRETE:
            new_mat = ConcreteMaterial(
                name=self.current_material.name,
                description=self.current_material.description
            )
        else:
            new_mat = GenericMaterial(
                name=self.current_material.name,
                description=self.current_material.description
            )

        self.working_library.materials[new_mat.name] = new_mat
        self.current_material = new_mat

        self.on_selection_changed(self.list_widget.currentItem(), None)

    def on_name_changed(self):
        if not self.current_material: return
        if self.edit_name.isReadOnly(): return

        new_name = self.edit_name.text().strip()

        # Validation: Check for empty name
        if not new_name:
            QMessageBox.warning(self, "Chyba", "Název nemůže být prázdný.")
            self.edit_name.setText(self.current_material.name)  # Revert
            return

        # No change needed
        if new_name == self.current_material.name:
            return

        # Validation: Check for name collision
        if new_name in self.working_library.materials:
            QMessageBox.warning(self, "Chyba", f"Materiál '{new_name}' již existuje.")
            self.edit_name.setText(self.current_material.name)  # Revert
            return

        # Safe to rename
        old_name = self.current_material.name
        del self.working_library.materials[old_name]
        self.current_material.name = new_name
        self.working_library.materials[new_name] = self.current_material
        self._refresh_list()

    def on_desc_changed(self):
        if not self.current_material: return
        if self.edit_desc.isReadOnly(): return
        self.current_material.description = self.edit_desc.text()

    def on_add_clicked(self):
        base_name = "Nový Materiál"
        name = base_name
        cnt = 1
        while self.working_library.get_material(name):
            name = f"{base_name} ({cnt})"
            cnt += 1

        new_mat = GenericMaterial(name=name)
        self.working_library.add_material(new_mat)
        self._refresh_list()

        items = self.list_widget.findItems(name, Qt.MatchExactly)
        if items: self.list_widget.setCurrentItem(items[0])

    def on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importovat CSV", "", "CSV (*.csv)")
        if path:
            try:
                name = os.path.splitext(os.path.basename(path))[0]
                mat = GenericMaterial.from_csv(name, path)
                if self.working_library.get_material(name):
                    name += "_imported"
                mat.name = name
                self.working_library.add_material(mat)
                self._refresh_list()
                items = self.list_widget.findItems(mat.name, Qt.MatchExactly)
                if items: self.list_widget.setCurrentItem(items[0])
                QMessageBox.information(self, "Úspěch", f"Materiál '{name}' byl importován.")
            except Exception as e:
                QMessageBox.critical(self, "Chyba", str(e))

    # --- PLOTTING SYNC ---

    def _on_generic_tab_changed(self, prop_key: TemperatureDependentProperty):
        # Sync Right Tab to match Editor Tab
        self.active_prop_key = prop_key
        # Find index for this property
        idx = list(PROPERTY_METADATA.keys()).index(prop_key)
        self.plot_tabs.blockSignals(True)
        self.plot_tabs.setCurrentIndex(idx)
        self.plot_tabs.blockSignals(False)
        self._update_plot()

    def _on_plot_tab_changed(self, index: int):
        # Sync Editor Tab to match Right Tab
        props = list(PROPERTY_METADATA.keys())
        if index < len(props):
            self.active_prop_key = props[index]

            # If Generic Editor is active, switch its tab too
            if isinstance(self.current_material, GenericMaterial):
                self.editor_generic.tabs.blockSignals(True)
                self.editor_generic.select_tab(self.active_prop_key)
                self.editor_generic.tabs.blockSignals(False)

            self._update_plot()

    def _update_plot(self):
        if not self.current_material: return

        prop_key = self.active_prop_key
        plot = self.plot_widgets[prop_key]

        meta = PROPERTY_METADATA[prop_key]
        plot.setLabel('left', meta.unit)

        # Fetch Data
        temps, values = self.current_material.get_preview_curve(prop_key)

        logger.info(f"Updating plot for {self.current_material.name} - {prop_key.name}: {len(temps)} points, "
                    f"temps={temps}, "
                    f"values={values}.")

        plot.clear()

        pen = pg.mkPen(color=(0, 120, 215), width=2)
        plot.plot(temps, values, pen=pen)

        max_val = max(values)

        plot.setYRange(0, max_val)
