"""
Fire Curve Configuration Dialog
Supports Standard, Tabulated, and Zonal definitions.
"""
import copy
import csv
import logging
import numpy as np
import pyqtgraph as pg
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QGroupBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QWidget,
    QLineEdit, QFileDialog, QMessageBox, QDoubleSpinBox,
    QComboBox, QStackedWidget, QDialogButtonBox, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer

from temperatureanalysis.model.bc import (
    FireCurveLibrary, FireCurveConfig, FireCurveType, StandardCurveType,
    StandardFireCurveConfig, TabulatedFireCurveConfig, ZonalFireCurveConfig, ZoneConfig
)
# Import FEA implementations only for preview data generation
from temperatureanalysis.controller.fea.pre.fire_curves import (
    ISO834FireCurve, HCFireCurve, HCMFireCurve, RABTZTVTrainFireCurve,
    RABTZTVCarFireCurve, RWSFireCurve, TabulatedFireCurve
)

logger = logging.getLogger(__name__)

# ==============================================================================
# HELPERS
# ==============================================================================

def get_preview_data(config: FireCurveConfig, duration=180*60) -> tuple[np.ndarray, np.ndarray]:
    """Generates (time_sec, temp_celsius) for plotting."""
    times = np.linspace(0, duration, 200)

    # Instantiate FEA object temporarily
    curve_obj = None
    if isinstance(config, StandardFireCurveConfig):
        t = config.curve_type
        if t == StandardCurveType.ISO834: curve_obj = ISO834FireCurve()
        elif t == StandardCurveType.HC: curve_obj = HCFireCurve()
        elif t == StandardCurveType.HCM: curve_obj = HCMFireCurve()
        elif t == StandardCurveType.RABT_TRAIN: curve_obj = RABTZTVTrainFireCurve()
        elif t == StandardCurveType.RABT_CAR: curve_obj = RABTZTVCarFireCurve()
        elif t == StandardCurveType.RWS: curve_obj = RWSFireCurve()

    elif isinstance(config, TabulatedFireCurveConfig):
        if len(config.times) > 1:
            # Config stores raw values (assumed s/C from UI).
            # TabulatedFireCurve expects K for values.
            t_k = np.array(config.temperatures) + 273.15
            curve_obj = TabulatedFireCurve(config.times, t_k)

    # Zonal curves are handled by plotting their components directly via the UI logic

    if curve_obj:
        try:
            temps_k = curve_obj.get_temperature(times)
            return times / 60.0, temps_k - 273.15 # Min, C
        except Exception:
            pass

    return times / 60.0, np.zeros_like(times)

# ==============================================================================
# SUB-EDITORS
# ==============================================================================

class StandardCurveEditor(QWidget):
    dataChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: Optional[StandardFireCurveConfig] = None

        layout = QFormLayout(self)
        self.combo = QComboBox()
        for t in StandardCurveType:
            self.combo.addItem(t.value, t)
        self.combo.currentIndexChanged.connect(self._on_change)
        layout.addRow("Typ křivky:", self.combo)

    def set_config(self, config: StandardFireCurveConfig):
        self.current_config = config
        self.combo.blockSignals(True)
        idx = self.combo.findData(config.curve_type)
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)

    def _on_change(self):
        if self.current_config:
            self.current_config.curve_type = self.combo.currentData()
            self.dataChanged.emit()

class TabulatedCurveEditor(QWidget):
    dataChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: Optional[TabulatedFireCurveConfig] = None

        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Čas [s]", "Teplota [°C]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Tools
        h_tools = QHBoxLayout()
        btn_add = QPushButton("+ Bod")
        btn_del = QPushButton("- Bod")
        btn_imp = QPushButton("Import CSV...")
        h_tools.addWidget(btn_add)
        h_tools.addWidget(btn_del)
        h_tools.addWidget(btn_imp)
        h_tools.addStretch()
        layout.addLayout(h_tools)

        btn_add.clicked.connect(self._add_row)
        btn_del.clicked.connect(self._del_row)
        btn_imp.clicked.connect(self._import_csv)

        # Defer save to avoid committing partially edited data
        self.table.itemChanged.connect(lambda item: QTimer.singleShot(0, self._save_data))

    def set_config(self, config: TabulatedFireCurveConfig):
        self.current_config = config
        self._load_table()

    def _load_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self.current_config:
            times = self.current_config.times
            temps = self.current_config.temperatures
            self.table.setRowCount(len(times))
            for i, (t, T) in enumerate(zip(times, temps)):
                self.table.setItem(i, 0, QTableWidgetItem(str(t)))
                self.table.setItem(i, 1, QTableWidgetItem(str(T)))
        self.table.blockSignals(False)

    def _save_data(self):
        if not self.current_config: return

        times = []
        temps = []
        for r in range(self.table.rowCount()):
            try:
                t_item = self.table.item(r, 0)
                T_item = self.table.item(r, 1)
                if t_item and T_item:
                    t = float(t_item.text())
                    T = float(T_item.text())
                    times.append(t)
                    temps.append(T)
            except (ValueError, AttributeError): pass

        # Sort
        if times:
            combined = sorted(zip(times, temps), key=lambda x: x[0])
            self.current_config.times, self.current_config.temperatures = map(list, zip(*combined))
        else:
            self.current_config.times = []
            self.current_config.temperatures = []

        self.dataChanged.emit()

    def _add_row(self):
        self.table.blockSignals(True)
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem("0"))
        self.table.setItem(r, 1, QTableWidgetItem("20"))
        self.table.blockSignals(False)
        self._save_data()

    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._save_data()

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv);;Text (*.txt)")
        if not path: return
        try:
            ts, Ts = [], []
            with open(path, 'r') as f:
                reader = csv.reader(f, delimiter=',' if ',' in f.readline() else ';')
                f.seek(0)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            ts.append(float(row[0]))
                            Ts.append(float(row[1]))
                        except ValueError: pass

            if ts:
                self.current_config.times = ts
                self.current_config.temperatures = Ts
                self._save_data() # Sorts and emits
                self._load_table()
                QMessageBox.information(self, "Info", f"Načteno {len(ts)} bodů.")
        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))


class ZonalCurveEditor(QWidget):
    """
    Complex editor:
    - Top: Default Curve (Standard/Tabulated selector + Editor)
    - Middle: Zone Table (Y-Min, Y-Max, Type)
    - Bottom: Selected Zone Editor (Standard/Tabulated)
    """
    dataChanged = Signal()
    selectionChanged = Signal() # Emitted when zone selection changes to update plot preview

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: Optional[ZonalFireCurveConfig] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # --- Default Curve Section ---
        grp_def = QGroupBox("Výchozí Křivka (mimo zóny)")
        l_def = QVBoxLayout(grp_def)

        h_def_type = QHBoxLayout()
        self.combo_def_type = QComboBox()
        self.combo_def_type.addItem("Standardní", FireCurveType.STANDARD)
        self.combo_def_type.addItem("Vlastní", FireCurveType.TABULATED)
        self.combo_def_type.currentIndexChanged.connect(self._on_def_type_changed)
        h_def_type.addWidget(QLabel("Typ:"))
        h_def_type.addWidget(self.combo_def_type)
        l_def.addLayout(h_def_type)

        self.stack_def = QStackedWidget()
        self.edit_def_std = StandardCurveEditor()
        self.edit_def_tab = TabulatedCurveEditor()
        self.edit_def_std.dataChanged.connect(self.dataChanged)
        self.edit_def_tab.dataChanged.connect(self.dataChanged)
        # When default data changes, we want to update plot if default is active
        self.edit_def_std.dataChanged.connect(self.selectionChanged)
        self.edit_def_tab.dataChanged.connect(self.selectionChanged)

        self.stack_def.addWidget(self.edit_def_std)
        self.stack_def.addWidget(self.edit_def_tab)
        l_def.addWidget(self.stack_def)

        layout.addWidget(grp_def)

        # --- Zones Section ---
        grp_zones = QGroupBox("Zóny (dle výšky Y)")
        l_zones = QVBoxLayout(grp_zones)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Y Min [m]", "Y Max [m]", "Typ Křivky"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_zone_selected)
        l_zones.addWidget(self.table)

        h_tools = QHBoxLayout()
        btn_add = QPushButton("Přidat Zónu")
        btn_del = QPushButton("Smazat Zónu")
        btn_add.clicked.connect(self._add_zone)
        btn_del.clicked.connect(self._del_zone)
        h_tools.addWidget(btn_add)
        h_tools.addWidget(btn_del)
        h_tools.addStretch()
        l_zones.addLayout(h_tools)

        # --- Zone Detail Editor ---
        self.grp_zone_detail = QGroupBox("Nastavení vybrané zóny")
        self.grp_zone_detail.setEnabled(False)
        l_detail = QVBoxLayout(self.grp_zone_detail)

        self._init_ui_extras(l_detail) # Add combo to detail group

        self.stack_zone = QStackedWidget()
        self.edit_zone_std = StandardCurveEditor()
        self.edit_zone_tab = TabulatedCurveEditor()
        # Connect sub-editors signals
        self.edit_zone_std.dataChanged.connect(self.dataChanged)
        self.edit_zone_tab.dataChanged.connect(self.dataChanged)
        # Trigger plot update on zone data change
        self.edit_zone_std.dataChanged.connect(self.selectionChanged)
        self.edit_zone_tab.dataChanged.connect(self.selectionChanged)

        self.stack_zone.addWidget(self.edit_zone_std)
        self.stack_zone.addWidget(self.edit_zone_tab)
        l_detail.addWidget(self.stack_zone)

        l_zones.addWidget(self.grp_zone_detail)
        layout.addWidget(grp_zones)

        # Connect table changes (geometry)
        self.table.itemChanged.connect(lambda i: QTimer.singleShot(0, self._save_zone_geometry))

    def _init_ui_extras(self, layout):
        h = QHBoxLayout()
        h.addWidget(QLabel("Typ křivky pro zónu:"))
        self.combo_zone_type = QComboBox()
        self.combo_zone_type.addItem("Standardní", FireCurveType.STANDARD)
        self.combo_zone_type.addItem("Vlastní", FireCurveType.TABULATED)
        self.combo_zone_type.currentIndexChanged.connect(self._on_zone_type_changed)
        h.addWidget(self.combo_zone_type)
        layout.addLayout(h)

    def set_config(self, config: ZonalFireCurveConfig):
        self.current_config = config
        self._load_default_curve()
        self._load_zones_table()
        # Reset selection details
        self.grp_zone_detail.setEnabled(False)
        # Notify initial view
        self.selectionChanged.emit()

    def get_active_preview_config(self) -> FireCurveConfig:
        """Returns the curve config that should be currently previewed."""
        if not self.current_config: return None

        # If a zone row is selected, return that zone's curve
        row = self.table.currentRow()
        if row >= 0 and row < len(self.current_config.zones):
            return self.current_config.zones[row].curve

        # Otherwise return the default curve
        return self.current_config.default_curve

    def _load_default_curve(self):
        c = self.current_config.default_curve
        self.combo_def_type.blockSignals(True)
        if c.type == FireCurveType.STANDARD:
            self.combo_def_type.setCurrentIndex(0)
            self.stack_def.setCurrentWidget(self.edit_def_std)
            self.edit_def_std.set_config(c)
        else:
            self.combo_def_type.setCurrentIndex(1)
            self.stack_def.setCurrentWidget(self.edit_def_tab)
            self.edit_def_tab.set_config(c)
        self.combo_def_type.blockSignals(False)

    def _on_def_type_changed(self):
        if not self.current_config: return
        t = self.combo_def_type.currentData()

        # Switch config object type in place
        old_c = self.current_config.default_curve
        new_c = None
        if t == FireCurveType.STANDARD:
            new_c = StandardFireCurveConfig(name=old_c.name)
        else:
            new_c = TabulatedFireCurveConfig(name=old_c.name)

        self.current_config.default_curve = new_c
        self._load_default_curve()
        self.dataChanged.emit()
        self.selectionChanged.emit() # Force preview update

    def _load_zones_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, z in enumerate(self.current_config.zones):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(z.y_min)))
            self.table.setItem(i, 1, QTableWidgetItem(str(z.y_max)))

            t_str = "Standardní" if z.curve.type == FireCurveType.STANDARD else "Vlastní"
            self.table.setItem(i, 2, QTableWidgetItem(t_str))
            # Make type read-only in table, force change via detail
            self.table.item(i, 2).setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        self.table.blockSignals(False)

    def _save_zone_geometry(self):
        if not self.current_config: return
        # Only update y_min/y_max, curve data is handled by sub-editors
        for r in range(self.table.rowCount()):
            try:
                y1 = float(self.table.item(r, 0).text())
                y2 = float(self.table.item(r, 1).text())
                if r < len(self.current_config.zones):
                    self.current_config.zones[r].y_min = y1
                    self.current_config.zones[r].y_max = y2
            except ValueError: pass
        self.dataChanged.emit()

    def _on_zone_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_config.zones):
            self.grp_zone_detail.setEnabled(False)
            # Notify that selection changed (likely back to default)
            self.selectionChanged.emit()
            return

        self.grp_zone_detail.setEnabled(True)
        zone = self.current_config.zones[row]

        is_std = (zone.curve.type == FireCurveType.STANDARD)
        self.combo_zone_type.blockSignals(True)
        self.combo_zone_type.setCurrentIndex(0 if is_std else 1)
        self.combo_zone_type.blockSignals(False)

        if is_std:
            self.stack_zone.setCurrentWidget(self.edit_zone_std)
            self.edit_zone_std.set_config(zone.curve)
        else:
            self.stack_zone.setCurrentWidget(self.edit_zone_tab)
            self.edit_zone_tab.set_config(zone.curve)

        self.selectionChanged.emit()

    def _on_zone_type_changed(self):
        row = self.table.currentRow()
        if row < 0: return
        t = self.combo_zone_type.currentData()
        zone = self.current_config.zones[row]

        if zone.curve.type == t: return # No change

        # Replace curve
        if t == FireCurveType.STANDARD:
            zone.curve = StandardFireCurveConfig(name="ZoneCurve")
        else:
            zone.curve = TabulatedFireCurveConfig(name="ZoneCurve")

        self._load_zones_table() # Update type column text
        self.table.blockSignals(True)
        self.table.selectRow(row) # Restore selection
        self.table.blockSignals(False)

        self._on_zone_selected() # Refresh editors
        self.dataChanged.emit()
        self.selectionChanged.emit()

    def _add_zone(self):
        # Default new zone
        z = ZoneConfig(y_min=0.0, y_max=2.0, curve=StandardFireCurveConfig(name="NewZone"))
        self.current_config.zones.append(z)
        self._load_zones_table()
        self.dataChanged.emit()

    def _del_zone(self):
        row = self.table.currentRow()
        if row >= 0:
            del self.current_config.zones[row]
            self._load_zones_table()
            self.dataChanged.emit()
            self.selectionChanged.emit()


# ==============================================================================
# MAIN DIALOG
# ==============================================================================

class FireCurveDialog(QDialog):
    def __init__(self, project_state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Knihovna Požárních Křivek")
        self.resize(1200, 800)

        self.project_ref = project_state
        self.working_library = copy.deepcopy(self.project_ref.fire_library)
        self.current_curve = None

        self._init_ui()
        self._refresh_list()

        # Select active
        if self.project_ref.selected_fire_curve:
            items = self.list_widget.findItems(self.project_ref.selected_fire_curve.name, Qt.MatchExactly)
            if items: self.list_widget.setCurrentItem(items[0])

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # LEFT: List
        left = QVBoxLayout()
        left.addWidget(QLabel("Dostupné křivky:"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection)
        left.addWidget(self.list_widget)

        btn_add = QPushButton("Nová křivka")
        btn_add.clicked.connect(self.on_add)
        left.addWidget(btn_add)

        layout.addLayout(left, 1)

        # CENTER: Editors
        center = QGroupBox("Nastavení")
        self.center_group = center
        center.setEnabled(False)
        l_center = QVBoxLayout(center)

        # Header
        form = QFormLayout()
        self.edit_name = QLineEdit()
        self.edit_name.editingFinished.connect(self.on_name_change)
        form.addRow("Název:", self.edit_name)

        self.combo_type = QComboBox()
        self.combo_type.addItem(FireCurveType.STANDARD.value, FireCurveType.STANDARD)
        self.combo_type.addItem(FireCurveType.TABULATED.value, FireCurveType.TABULATED)
        self.combo_type.addItem(FireCurveType.ZONAL.value, FireCurveType.ZONAL)
        self.combo_type.currentIndexChanged.connect(self.on_type_change)
        form.addRow("Typ:", self.combo_type)
        l_center.addLayout(form)

        # Stack
        self.stack = QStackedWidget()
        self.editor_std = StandardCurveEditor()
        self.editor_tab = TabulatedCurveEditor()
        self.editor_zone = ZonalCurveEditor()

        # Connections for Plot Updates
        self.editor_std.dataChanged.connect(self.update_plot)
        self.editor_tab.dataChanged.connect(self.update_plot)
        self.editor_zone.dataChanged.connect(self.update_plot)
        # Zonal editor changes selection? Update plot.
        self.editor_zone.selectionChanged.connect(self.update_plot)

        self.stack.addWidget(self.editor_std)
        self.stack.addWidget(self.editor_tab)
        self.stack.addWidget(self.editor_zone)
        l_center.addWidget(self.stack)

        layout.addWidget(center, 2)

        # RIGHT: Plot
        right = QVBoxLayout()
        right.addWidget(QLabel("Náhled (Time/Temp):"))
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('bottom', 'Čas [min]', color='black')
        self.plot_widget.setLabel('left', 'Teplota [°C]', color='black')
        right.addWidget(self.plot_widget)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        btns.button(QDialogButtonBox.Ok).setText("Uložit a Zavřít")
        btns.button(QDialogButtonBox.Cancel).setText("Zavřít")
        btns.button(QDialogButtonBox.Apply).setText("Uložit")
        btns.clicked.connect(self.on_btns)
        right.addWidget(btns)

        layout.addLayout(right, 2)

    # --- ACTIONS ---
    def _refresh_list(self):
        curr = self.list_widget.currentRow()
        self.list_widget.clear()
        for name in self.working_library.get_names():
            self.list_widget.addItem(name)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(curr if curr >= 0 else 0)

    def on_selection(self, current, prev):
        if not current:
            self.center_group.setEnabled(False)
            return

        name = current.text()
        config = self.working_library.get_fire_curve(name)
        if not config: return

        self.current_curve = config
        self.center_group.setEnabled(True)

        self.edit_name.setText(config.name)

        idx = self.combo_type.findData(config.type)
        self.combo_type.blockSignals(True)
        self.combo_type.setCurrentIndex(idx)
        self.combo_type.blockSignals(False)

        if config.type == FireCurveType.STANDARD:
            self.stack.setCurrentWidget(self.editor_std)
            self.editor_std.set_config(config)
        elif config.type == FireCurveType.TABULATED:
            self.stack.setCurrentWidget(self.editor_tab)
            self.editor_tab.set_config(config)
        elif config.type == FireCurveType.ZONAL:
            self.stack.setCurrentWidget(self.editor_zone)
            self.editor_zone.set_config(config)

        self.update_plot()

    def on_add(self):
        base = "Nova krivka"
        name = base
        i = 1
        while self.working_library.get_fire_curve(name):
            name = f"{base} ({i})"
            i += 1

        c = StandardFireCurveConfig(name=name)
        self.working_library.add(c)
        self._refresh_list()
        items = self.list_widget.findItems(name, Qt.MatchExactly)
        if items: self.list_widget.setCurrentItem(items[0])

    def on_name_change(self):
        if not self.current_curve: return
        new_name = self.edit_name.text()
        if new_name and new_name != self.current_curve.name:
            del self.working_library.curves[self.current_curve.name]
            self.current_curve.name = new_name
            self.working_library.add(self.current_curve)
            self._refresh_list()

    def on_type_change(self):
        if not self.current_curve: return
        t = self.combo_type.currentData()
        if t == self.current_curve.type: return

        # Convert logic
        new_c = None
        name = self.current_curve.name
        if t == FireCurveType.STANDARD:
            new_c = StandardFireCurveConfig(name=name)
        elif t == FireCurveType.TABULATED:
            new_c = TabulatedFireCurveConfig(name=name)
        elif t == FireCurveType.ZONAL:
            new_c = ZonalFireCurveConfig(name=name)

        self.working_library.curves[name] = new_c
        self.current_curve = new_c

        # Reload
        self.on_selection(self.list_widget.currentItem(), None)

    def update_plot(self):
        if not self.current_curve: return

        config_to_plot = self.current_curve

        # If Zonal, ask editor for active component
        if self.current_curve.type == FireCurveType.ZONAL:
            config_to_plot = self.editor_zone.get_active_preview_config()

        if not config_to_plot: return

        # Get data from helper using FEA objects
        t, T = get_preview_data(config_to_plot)

        self.plot_widget.clear()
        pen = pg.mkPen(color='r', width=2)
        self.plot_widget.plot(t, T, pen=pen)

    def on_btns(self, btn):
        role = self.sender().buttonRole(btn)
        if role == QDialogButtonBox.ApplyRole:
            self.project_ref.fire_library = copy.deepcopy(self.working_library)
            QMessageBox.information(self, "Saved", "Library saved.")
        elif role == QDialogButtonBox.AcceptRole:
            self.project_ref.fire_library = copy.deepcopy(self.working_library)
            self.accept()
        elif role == QDialogButtonBox.RejectRole:
            self.reject()
