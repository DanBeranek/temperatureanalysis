"""
Fire Curve Configuration Dialog
Supports Standard, Tabulated, and Zonal definitions.

Business Rules:
- Standard curves are read-only (cannot delete, cannot change type)
- New curves default to Tabulated type
- Tabulated curves: UI shows time in Minutes, model stores in Seconds
- Zonal curves: Zones must use Tabulated curves only (no Standard curves)
- Zonal curves: No default curve - zones must cover entire geometry
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
# CSV IMPORT DIALOG
# ==============================================================================

class CsvImportDialog(QDialog):
    """Dialog for importing CSV data with unit selection for time and temperature."""

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.csv_data = []
        self.headers = []

        self.setWindowTitle("Importovat CSV - Nastavení")
        self.resize(800, 600)

        self._load_csv_preview()
        self._init_ui()

    def _load_csv_preview(self):
        """Load first few rows of CSV for preview."""
        try:
            with open(self.filepath, 'r', encoding='utf-8-sig') as f:
                # Detect delimiter
                first_line = f.readline()
                delimiter = ';' if ';' in first_line else ','
                f.seek(0)

                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)

                if not rows:
                    raise ValueError("CSV soubor je prázdný")

                # Detect headers (first row has non-numeric values)
                first_row = rows[0]
                has_header = not all(self._is_numeric(cell) for cell in first_row if cell.strip())

                if has_header:
                    self.headers = [cell.strip() for cell in first_row]
                    self.csv_data = rows[1:20]  # Preview up to 20 rows
                else:
                    # Generate default headers
                    num_cols = len(first_row)
                    self.headers = [f"Sloupec {i+1}" for i in range(num_cols)]
                    self.csv_data = rows[:20]  # Preview up to 20 rows

        except Exception as e:
            logger.error(f"Failed to load CSV preview: {e}")
            raise

    def _is_numeric(self, value: str) -> bool:
        """Check if a string can be converted to float."""
        try:
            float(value.replace(',', '.'))
            return True
        except (ValueError, AttributeError):
            return False

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        info = QLabel("Vyberte sloupce a jednotky:")
        layout.addWidget(info)

        # Column mapping
        map_group = QGroupBox("Mapování sloupců")
        map_layout = QFormLayout(map_group)

        self.combo_time = QComboBox()
        self.combo_time.addItem("-- Nevybráno --", None)
        for i, header in enumerate(self.headers):
            self.combo_time.addItem(f"{header}", i)
        map_layout.addRow("Čas:", self.combo_time)

        self.combo_temp = QComboBox()
        self.combo_temp.addItem("-- Nevybráno --", None)
        for i, header in enumerate(self.headers):
            self.combo_temp.addItem(f"{header}", i)
        map_layout.addRow("Teplota:", self.combo_temp)

        layout.addWidget(map_group)

        # Unit selection
        unit_group = QGroupBox("Jednotky")
        unit_layout = QFormLayout(unit_group)

        self.combo_time_unit = QComboBox()
        self.combo_time_unit.addItem("Sekundy (s)", "seconds")
        self.combo_time_unit.addItem("Minuty (min)", "minutes")
        unit_layout.addRow("Jednotka času:", self.combo_time_unit)

        self.combo_temp_unit = QComboBox()
        self.combo_temp_unit.addItem("°C (Celsius)", "celsius")
        self.combo_temp_unit.addItem("K (Kelvin)", "kelvin")
        unit_layout.addRow("Jednotka teploty:", self.combo_temp_unit)

        layout.addWidget(unit_group)

        # Preview table
        preview_label = QLabel("Náhled dat:")
        layout.addWidget(preview_label)

        self.table_preview = QTableWidget()
        self.table_preview.setColumnCount(len(self.headers))
        self.table_preview.setHorizontalHeaderLabels(self.headers)
        self.table_preview.setRowCount(min(10, len(self.csv_data)))

        for row_idx, row_data in enumerate(self.csv_data[:10]):
            for col_idx, cell_value in enumerate(row_data):
                self.table_preview.setItem(row_idx, col_idx, QTableWidgetItem(cell_value))

        self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table_preview)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self):
        """Validate before accepting the dialog."""
        try:
            # Validate column selections
            time_col = self.combo_time.currentData()
            temp_col = self.combo_temp.currentData()

            if time_col is None or temp_col is None:
                QMessageBox.warning(self, "Chyba", "Sloupce času a teploty musí být vybrány.")
                return

            # Try to load data to validate it
            try:
                data = self.get_mapped_data()
                if len(data['times']) < 2:
                    QMessageBox.warning(self, "Chyba", "CSV musí obsahovat alespoň 2 platné řádky dat.")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Chyba při načítání dat", str(e))
                return

            # All validation passed - accept dialog
            self.accept()

        except Exception as e:
            logger.exception("Validation error in CSV import dialog")
            QMessageBox.critical(self, "Chyba", f"Neočekávaná chyba: {str(e)}")

    def get_mapped_data(self) -> dict:
        """Extract mapped data based on user selection and convert to internal units."""
        time_col = self.combo_time.currentData()
        temp_col = self.combo_temp.currentData()
        time_unit = self.combo_time_unit.currentData()
        temp_unit = self.combo_temp_unit.currentData()

        if time_col is None or temp_col is None:
            raise ValueError("Sloupce času a teploty musí být vybrány")

        # Read all data from CSV
        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            delimiter = ';' if ';' in first_line else ','
            f.seek(0)
            reader = csv.reader(f, delimiter=delimiter)
            all_rows = list(reader)

            # Skip header if present
            has_header = not all(self._is_numeric(cell) for cell in all_rows[0] if cell.strip())
            data_rows = all_rows[1:] if has_header else all_rows

        times = []
        temps = []

        for row in data_rows:
            if len(row) <= max(time_col, temp_col):
                continue
            try:
                time_val = float(row[time_col].replace(',', '.'))
                temp_val = float(row[temp_col].replace(',', '.'))

                # Convert to internal units
                # Time: Convert to Seconds
                if time_unit == "minutes":
                    time_val = time_val * 60.0

                # Temperature: Convert to Celsius
                if temp_unit == "kelvin":
                    temp_val = temp_val - 273.15

                times.append(time_val)
                temps.append(temp_val)
            except (ValueError, IndexError):
                continue

        return {
            'times': times,
            'temperatures': temps,
            'time_unit_original': time_unit,
            'temp_unit_original': temp_unit
        }


# ==============================================================================
# HELPERS
# ==============================================================================

def get_preview_data(config: FireCurveConfig, duration=180*60) -> tuple[np.ndarray, np.ndarray]:
    """Generates (time_min, temp_celsius) for plotting."""
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
            # Config stores times in seconds, temps in Celsius
            # TabulatedFireCurve expects times in seconds, temps in Kelvin
            t_k = np.array(config.temperatures) + 273.15
            curve_obj = TabulatedFireCurve(config.times, t_k)

    if curve_obj:
        try:
            temps_k = curve_obj.get_temperature(times)
            return times / 60.0, temps_k - 273.15  # Return Minutes, Celsius
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

        # Add info label
        info_label = QLabel("<i>Standardní křivky jsou pouze pro čtení.</i>")
        info_label.setWordWrap(True)
        layout.addRow("", info_label)

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
    """
    Editor for Tabulated fire curves.
    UI shows time in MINUTES, but model stores in SECONDS.
    """
    dataChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: Optional[TabulatedFireCurveConfig] = None

        layout = QVBoxLayout(self)

        # Info label about units
        info = QLabel("<b>Jednotky:</b> Čas v Minutách, Teplota v °C")
        layout.addWidget(info)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Čas [min]", "Teplota [°C]"])
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
        """Load data from model (Seconds) and convert to UI units (Minutes)."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self.current_config:
            times_sec = self.current_config.times
            temps = self.current_config.temperatures
            self.table.setRowCount(len(times_sec))
            for i, (t_sec, T) in enumerate(zip(times_sec, temps)):
                t_min = t_sec / 60.0  # Convert Seconds to Minutes for UI
                self.table.setItem(i, 0, QTableWidgetItem(f"{t_min:.2f}"))
                self.table.setItem(i, 1, QTableWidgetItem(f"{T:.1f}"))
        self.table.blockSignals(False)

    def _save_data(self):
        """Save data from UI (Minutes) and convert to model units (Seconds)."""
        if not self.current_config:
            return

        times_min = []
        temps = []
        for r in range(self.table.rowCount()):
            try:
                t_item = self.table.item(r, 0)
                T_item = self.table.item(r, 1)
                if t_item and T_item:
                    t_min = float(t_item.text().replace(',', '.'))
                    T = float(T_item.text().replace(',', '.'))
                    times_min.append(t_min)
                    temps.append(T)
            except (ValueError, AttributeError):
                pass

        # Convert Minutes to Seconds for model
        times_sec = [t * 60.0 for t in times_min]

        # Sort by time
        if times_sec:
            combined = sorted(zip(times_sec, temps), key=lambda x: x[0])
            self.current_config.times, self.current_config.temperatures = map(list, zip(*combined))
        else:
            self.current_config.times = []
            self.current_config.temperatures = []

        # Enforce minimum 2 points
        if len(self.current_config.times) < 2:
            logger.warning("Tabulated curve must have at least 2 points")

        self.dataChanged.emit()

    def _add_row(self):
        """Add a new row to the table."""
        self.table.blockSignals(True)
        r = self.table.rowCount()
        self.table.insertRow(r)
        # Default values in UI units (Minutes)
        default_time_min = 0.0 if r == 0 else (r * 10.0)  # 0, 10, 20, ... minutes
        self.table.setItem(r, 0, QTableWidgetItem(f"{default_time_min:.2f}"))
        self.table.setItem(r, 1, QTableWidgetItem("20.0"))
        self.table.blockSignals(False)
        self._save_data()

    def _del_row(self):
        """Delete selected row from table."""
        # Enforce minimum 2 points
        if self.table.rowCount() <= 2:
            QMessageBox.warning(self, "Varování", "Křivka musí obsahovat alespoň 2 body.")
            return

        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._save_data()

    def _import_csv(self):
        """Import curve data from CSV with unit selection."""
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv);;Text (*.txt)")
        if not path:
            return

        try:
            # Show CSV import dialog with unit selection
            import_dialog = CsvImportDialog(path, parent=self)
            if import_dialog.exec() != QDialog.Accepted:
                return

            # Get mapped data (already converted to internal units: Seconds, Celsius)
            data = import_dialog.get_mapped_data()

            if len(data['times']) < 2:
                QMessageBox.warning(self, "Chyba", "CSV musí obsahovat alespoň 2 body.")
                return

            # Store in model (already in Seconds, Celsius)
            self.current_config.times = data['times']
            self.current_config.temperatures = data['temperatures']

            # Reload table (will convert Seconds to Minutes for display)
            self._load_table()
            self.dataChanged.emit()

            QMessageBox.information(self, "Info",
                                    f"Načteno {len(data['times'])} bodů.\n"
                                    f"Čas: {data['time_unit_original']}, "
                                    f"Teplota: {data['temp_unit_original']}")

        except Exception as e:
            logger.exception("Failed to load CSV")
            QMessageBox.critical(self, "Chyba", str(e))


class ZonalCurveEditor(QWidget):
    """
    Editor for Zonal fire curves.
    - No default curve (removed per requirements)
    - Zones can only use Tabulated curves (not Standard)
    - Validates zone coverage
    """
    dataChanged = Signal()
    selectionChanged = Signal()  # Emitted when zone selection changes to update plot preview

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: Optional[ZonalFireCurveConfig] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Info about zonal curves
        info = QLabel("<b>Zónová křivka:</b> Definujte požární křivky pro různé výšky konstrukce. "
                      "Zóny musí pokrývat celou výšku bez mezer.")
        info.setWordWrap(True)
        layout.addWidget(info)

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

        # Note: Zones can only use Tabulated curves
        info_zone = QLabel("<i>Zóny mohou používat pouze vlastní (tabulkové) křivky.</i>")
        l_detail.addWidget(info_zone)

        # Tabulated editor for zone
        self.edit_zone_tab = TabulatedCurveEditor()
        self.edit_zone_tab.dataChanged.connect(self.dataChanged)
        self.edit_zone_tab.dataChanged.connect(self.selectionChanged)
        l_detail.addWidget(self.edit_zone_tab)

        l_zones.addWidget(self.grp_zone_detail)
        layout.addWidget(grp_zones)

        # Connect table changes (geometry)
        self.table.itemChanged.connect(lambda i: QTimer.singleShot(0, self._save_zone_geometry))

    def set_config(self, config: ZonalFireCurveConfig):
        self.current_config = config
        self._load_zones_table()
        # Reset selection details
        self.grp_zone_detail.setEnabled(False)
        # Notify initial view
        self.selectionChanged.emit()

    def get_active_preview_config(self) -> FireCurveConfig:
        """Returns the curve config that should be currently previewed."""
        if not self.current_config:
            return None

        # If a zone row is selected, return that zone's curve
        row = self.table.currentRow()
        if row >= 0 and row < len(self.current_config.zones):
            return self.current_config.zones[row].curve

        # No zone selected - return None (no preview available)
        return None

    def _load_zones_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, z in enumerate(self.current_config.zones):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(f"{z.y_min:.2f}"))
            self.table.setItem(i, 1, QTableWidgetItem(f"{z.y_max:.2f}"))

            # Zone can only be Tabulated
            t_str = "Vlastní (Tabulka)"
            item = QTableWidgetItem(t_str)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # Read-only
            self.table.setItem(i, 2, item)

        self.table.blockSignals(False)

    def _save_zone_geometry(self):
        if not self.current_config:
            return
        # Only update y_min/y_max, curve data is handled by sub-editor
        for r in range(self.table.rowCount()):
            try:
                y1 = float(self.table.item(r, 0).text().replace(',', '.'))
                y2 = float(self.table.item(r, 1).text().replace(',', '.'))
                if r < len(self.current_config.zones):
                    self.current_config.zones[r].y_min = y1
                    self.current_config.zones[r].y_max = y2
            except (ValueError, AttributeError):
                pass
        self.dataChanged.emit()

    def _on_zone_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_config.zones):
            self.grp_zone_detail.setEnabled(False)
            self.selectionChanged.emit()
            return

        self.grp_zone_detail.setEnabled(True)
        zone = self.current_config.zones[row]

        # Zone curve is always Tabulated (enforced on creation)
        if isinstance(zone.curve, TabulatedFireCurveConfig):
            self.edit_zone_tab.set_config(zone.curve)
        else:
            logger.error(f"Zone {row} has invalid curve type: {zone.curve.type}")

        self.selectionChanged.emit()

    def _add_zone(self):
        """Add a new zone with a default Tabulated curve."""
        # Create new zone with Tabulated curve (NOT Standard)
        new_curve = TabulatedFireCurveConfig(
            name="ZoneCurve",
            times=[0, 3600],  # 0 and 60 minutes in seconds
            temperatures=[20, 800]
        )
        z = ZoneConfig(y_min=0.0, y_max=2.0, curve=new_curve)
        self.current_config.zones.append(z)
        self._load_zones_table()
        self.dataChanged.emit()

    def _del_zone(self):
        """Delete the selected zone."""
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
            if items:
                self.list_widget.setCurrentItem(items[0])

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # LEFT: List and Action Buttons
        left = QVBoxLayout()
        left.addWidget(QLabel("Dostupné křivky:"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection)
        left.addWidget(self.list_widget)

        # Action buttons
        btn_add = QPushButton("Nová Křivka")
        btn_add.clicked.connect(self.on_add)
        left.addWidget(btn_add)

        self.btn_copy = QPushButton("Kopírovat Křivku")
        self.btn_copy.clicked.connect(self.on_copy)
        self.btn_copy.setEnabled(False)
        left.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("Smazat Křivku")
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_delete.setEnabled(False)
        left.addWidget(self.btn_delete)

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

        self.edit_desc = QLineEdit()
        self.edit_desc.editingFinished.connect(self.on_desc_change)
        form.addRow("Popis:", self.edit_desc)

        # Type combobox (will be hidden for Standard curves)
        self.type_row_widget = QWidget()
        type_row_layout = QHBoxLayout(self.type_row_widget)
        type_row_layout.setContentsMargins(0, 0, 0, 0)
        self.combo_type = QComboBox()
        # NOTE: Standard is NOT included for user-created curves
        self.combo_type.addItem(FireCurveType.TABULATED.value, FireCurveType.TABULATED)
        self.combo_type.addItem(FireCurveType.ZONAL.value, FireCurveType.ZONAL)
        self.combo_type.currentIndexChanged.connect(self.on_type_change)
        type_row_layout.addWidget(self.combo_type)
        self.type_row_widget.setLayout(type_row_layout)

        form.addRow("Typ:", self.type_row_widget)
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
        right.addWidget(QLabel("Náhled křivky:"))
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('bottom', 'Čas [min]', color='black')
        self.plot_widget.setLabel('left', 'Teplota [°C]', color='black')
        self.plot_widget.getAxis('bottom').setPen('k')
        self.plot_widget.getAxis('left').setPen('k')
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
            self.btn_copy.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return

        name = current.text()
        config = self.working_library.get_fire_curve(name)
        if not config:
            self.btn_copy.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return

        self.current_curve = config
        self.center_group.setEnabled(True)
        self.btn_copy.setEnabled(True)

        # Enable/disable delete based on whether curve is standard
        is_standard = config.is_standard_curve()
        self.btn_delete.setEnabled(not is_standard)

        # Set name and description
        self.edit_name.setText(config.name)
        self.edit_name.setReadOnly(is_standard)  # Can't rename standard curves

        self.edit_desc.setText(config.description)
        self.edit_desc.setReadOnly(is_standard)  # Can't edit description of standard curves

        # Hide Type combobox for Standard curves (they can't be changed)
        self.type_row_widget.setVisible(not is_standard)

        if not is_standard:
            # Set type combobox for non-standard curves
            idx = self.combo_type.findData(config.type)
            self.combo_type.blockSignals(True)
            self.combo_type.setCurrentIndex(idx)
            self.combo_type.blockSignals(False)

        # Load appropriate editor
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
        """Add a new curve (defaults to Tabulated type)."""
        base = "Nova krivka"
        name = base
        i = 1
        while self.working_library.get_fire_curve(name):
            name = f"{base} ({i})"
            i += 1

        # New curves default to Tabulated (NOT Standard)
        c = TabulatedFireCurveConfig(
            name=name,
            times=[0, 3600],  # 0 and 60 minutes in seconds
            temperatures=[20, 800]
        )
        self.working_library.add(c)
        self._refresh_list()
        items = self.list_widget.findItems(name, Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])

    def on_copy(self):
        """Copy the currently selected curve."""
        if not self.current_curve:
            QMessageBox.warning(self, "Chyba", "Vyberte křivku ke kopírování.")
            return

        # Create base name
        base_name = f"{self.current_curve.name} - kopie"
        name = base_name
        cnt = 1
        while self.working_library.get_fire_curve(name):
            name = f"{self.current_curve.name} - kopie ({cnt})"
            cnt += 1

        # Deep copy the curve
        new_curve = copy.deepcopy(self.current_curve)
        new_curve.name = name

        # If copying a Standard curve, convert it to Tabulated
        # (Standard curves can only be the built-in presets)
        if new_curve.is_standard_curve():
            # Generate preview data and create Tabulated curve from it
            times_min, temps_c = get_preview_data(new_curve, duration=180*60)
            times_sec = times_min * 60.0  # Convert back to seconds for storage

            new_curve = TabulatedFireCurveConfig(
                name=name,
                description=f"Kopie z {self.current_curve.name}",
                times=times_sec.tolist(),
                temperatures=temps_c.tolist()
            )

        self.working_library.add(new_curve)
        self._refresh_list()

        items = self.list_widget.findItems(name, Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])

    def on_delete(self):
        """Delete the currently selected curve."""
        if not self.current_curve:
            QMessageBox.warning(self, "Chyba", "Vyberte křivku ke smazání.")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Potvrdit smazání",
            f"Opravdu chcete smazat křivku '{self.current_curve.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Try to delete (library will check if it's a standard curve)
        success = self.working_library.delete(self.current_curve.name)
        if not success:
            QMessageBox.warning(self, "Chyba", "Nelze smazat standardní křivku.")
            return

        self.current_curve = None
        self._refresh_list()

    def on_name_change(self):
        if not self.current_curve:
            return
        if self.edit_name.isReadOnly():
            return

        new_name = self.edit_name.text().strip()

        # Validation: Check for empty name
        if not new_name:
            QMessageBox.warning(self, "Chyba", "Název nemůže být prázdný.")
            self.edit_name.setText(self.current_curve.name)  # Revert
            return

        # No change needed
        if new_name == self.current_curve.name:
            return

        # Validation: Check for name collision
        if new_name in self.working_library.curves:
            QMessageBox.warning(self, "Chyba", f"Křivka '{new_name}' již existuje.")
            self.edit_name.setText(self.current_curve.name)  # Revert
            return

        # Safe to rename
        old_name = self.current_curve.name
        del self.working_library.curves[old_name]
        self.current_curve.name = new_name
        self.working_library.add(self.current_curve)
        self._refresh_list()

    def on_desc_change(self):
        if not self.current_curve:
            return
        if self.edit_desc.isReadOnly():
            return
        self.current_curve.description = self.edit_desc.text()

    def on_type_change(self):
        if not self.current_curve:
            return

        # Standard curves cannot change type (combo is hidden for them)
        if self.current_curve.is_standard_curve():
            return

        t = self.combo_type.currentData()
        if t == self.current_curve.type:
            return

        # Convert logic
        new_c = None
        name = self.current_curve.name
        desc = self.current_curve.description

        if t == FireCurveType.TABULATED:
            new_c = TabulatedFireCurveConfig(
                name=name,
                description=desc,
                times=[0, 3600],
                temperatures=[20, 800]
            )
        elif t == FireCurveType.ZONAL:
            new_c = ZonalFireCurveConfig(name=name, description=desc)

        if new_c:
            self.working_library.curves[name] = new_c
            self.current_curve = new_c

            # Reload
            self.on_selection(self.list_widget.currentItem(), None)

    def update_plot(self):
        if not self.current_curve:
            self.plot_widget.clear()
            return

        config_to_plot = self.current_curve

        # If Zonal, ask editor for active component
        if self.current_curve.type == FireCurveType.ZONAL:
            config_to_plot = self.editor_zone.get_active_preview_config()

        if not config_to_plot:
            self.plot_widget.clear()
            return

        # Get data from helper using FEA objects
        t, T = get_preview_data(config_to_plot)

        self.plot_widget.clear()
        pen = pg.mkPen(color='r', width=2)
        self.plot_widget.plot(t, T, pen=pen)

    def on_btns(self, btn):
        role = self.sender().buttonRole(btn)
        if role == QDialogButtonBox.ApplyRole:
            self.project_ref.fire_library = copy.deepcopy(self.working_library)
            QMessageBox.information(self, "Uloženo", "Knihovna uložena.")
        elif role == QDialogButtonBox.AcceptRole:
            self.project_ref.fire_library = copy.deepcopy(self.working_library)
            self.accept()
        elif role == QDialogButtonBox.RejectRole:
            self.reject()
