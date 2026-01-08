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
from typing import Optional, List, Dict

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

        self.setWindowTitle("Import okrajové podmínky z CSV")
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
# CSV PARSING HELPERS
# ==============================================================================

def is_numeric_value(value: str) -> bool:
    """Check if a string can be converted to float."""
    try:
        float(value.replace(',', '.'))
        return True
    except (ValueError, AttributeError):
        return False


def parse_csv_headers(filepath: str) -> tuple[list[str], str, int]:
    """
    Parse CSV file and detect headers, delimiter, and number of header rows.

    Handles FDS-style CSVs with:
    - Row 1: Units (s, C, C, ...)
    - Row 2: Names (Time, TEMP_01, TEMP_02, ...)
    - Row 3+: Data

    Args:
        filepath: Path to CSV file

    Returns:
        (headers, delimiter, num_header_rows) tuple
        headers will be formatted as "Name [Unit]" if both rows exist
    """
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            # Detect delimiter
            first_line = f.readline()
            delimiter = ';' if ';' in first_line else ','
            f.seek(0)

            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

            if not rows:
                raise ValueError("CSV soubor je prázdný")

            first_row = rows[0]
            num_cols = len(first_row)

            # Check if first row is non-numeric (likely header)
            first_row_is_header = not all(is_numeric_value(cell) for cell in first_row if cell.strip())

            if not first_row_is_header:
                # No headers at all - generate default
                headers = [f"Sloupec {i+1}" for i in range(num_cols)]
                return headers, delimiter, 0

            # Check if second row is also non-numeric (FDS format: units + names)
            if len(rows) > 1:
                second_row = rows[1]
                second_row_is_header = not all(is_numeric_value(cell) for cell in second_row if cell.strip())

                if second_row_is_header:
                    # FDS format: Row 1 = units, Row 2 = names
                    # Combine as "Name [Unit]"
                    units_row = [cell.strip() for cell in first_row]
                    names_row = [cell.strip() for cell in second_row]

                    headers = []
                    for i in range(num_cols):
                        unit = units_row[i] if i < len(units_row) else ""
                        name = names_row[i] if i < len(names_row) else ""

                        # Clean quotes from name
                        name = name.strip('"')

                        if name and unit:
                            headers.append(f"{name} [{unit}]")
                        elif name:
                            headers.append(name)
                        elif unit:
                            headers.append(f"Sloupec {i+1} [{unit}]")
                        else:
                            headers.append(f"Sloupec {i+1}")

                    return headers, delimiter, 2  # Two header rows

            # Single header row
            headers = [cell.strip().strip('"') for cell in first_row]
            return headers, delimiter, 1

    except Exception as e:
        logger.error(f"Failed to parse CSV headers: {e}")
        raise


def read_csv_column(filepath: str, column_index: int, time_column_index: int,
                   time_unit: str, temp_unit: str, delimiter: str = ',',
                   num_header_rows: int = 1) -> dict:
    """
    Read a single temperature column with its corresponding time values.

    Args:
        filepath: Path to CSV file
        column_index: Index of temperature column to read
        time_column_index: Index of time column
        time_unit: 'seconds' or 'minutes'
        temp_unit: 'celsius' or 'kelvin'
        delimiter: CSV delimiter
        num_header_rows: Number of header rows to skip (0, 1, or 2)

    Returns:
        {'times': [...], 'temperatures': [...]} in internal units (seconds, Celsius)
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=delimiter)
        all_rows = list(reader)

        # Skip header rows
        data_rows = all_rows[num_header_rows:]

    times = []
    temps = []

    for row in data_rows:
        if len(row) <= max(time_column_index, column_index):
            continue
        try:
            time_val = float(row[time_column_index].replace(',', '.'))
            temp_val = float(row[column_index].replace(',', '.'))

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
        'temperatures': temps
    }


def extract_temp_columns(headers: list[str]) -> list[tuple[int, str]]:
    """
    Extract temperature column indices and names from CSV headers.
    Looks for columns matching pattern: TEMP_01, TEMP_02, etc. (with or without quotes)

    Args:
        headers: List of CSV column headers

    Returns:
        List of (column_index, column_name) tuples for TEMP_XX columns
    """
    import re
    temp_columns = []

    # Pattern matches: TEMP_01, "TEMP_01", TEMP_105, etc.
    pattern = re.compile(r'^"?TEMP_\d+"?$', re.IGNORECASE)

    for idx, header in enumerate(headers):
        if pattern.match(header.strip()):
            # Clean header (remove quotes)
            clean_name = header.strip().strip('"')
            temp_columns.append((idx, clean_name))

    return temp_columns


# ==============================================================================
# ZONAL CSV IMPORT DIALOG
# ==============================================================================

class ZonalCsvImportDialog(QDialog):
    """
    Dialog for importing CSV data into multiple zones simultaneously.
    Allows mapping temperature columns to predefined zones.
    """

    def __init__(self, zones: List[ZoneConfig], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.zones = zones  # Reference to existing zones
        self.csv_filepath: Optional[str] = None
        self.csv_headers: List[str] = []
        self.csv_delimiter: str = ','
        self.num_header_rows: int = 0  # Number of header rows to skip when reading data
        self.time_column_index: int = 0  # Index of time column (default: first column)
        self.column_mappings: Dict[int, Optional[int]] = {}  # zone_idx -> column_idx
        self.mapping_combos: List[QComboBox] = []  # Store combobox references

        self.setWindowTitle("Import všech zón z CSV")
        self.resize(900, 750)

        self._init_ui()

        # Open file dialog immediately (like material import)
        QTimer.singleShot(0, self._on_browse_file)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # === File Info Section ===
        file_group = QGroupBox("Informace o souboru")
        file_layout = QVBoxLayout(file_group)

        self.lbl_file_info = QLabel("Načítání...")
        self.lbl_file_info.setWordWrap(True)
        file_layout.addWidget(self.lbl_file_info)

        layout.addWidget(file_group)

        # === Time Column Selection ===
        time_group = QGroupBox("Sloupec s časem")
        time_layout = QFormLayout(time_group)

        self.combo_time_column = QComboBox()
        self.combo_time_column.currentIndexChanged.connect(self._on_time_column_changed)
        time_layout.addRow("Vyberte sloupec s časem:", self.combo_time_column)

        layout.addWidget(time_group)

        # === Zone Mapping Section ===
        mapping_group = QGroupBox("Mapování zón na sloupce CSV")
        mapping_layout = QVBoxLayout(mapping_group)

        self.table_mapping = QTableWidget()
        self.table_mapping.setColumnCount(3)
        self.table_mapping.setHorizontalHeaderLabels(["Zóna", "Rozsah Y [m]", "Sloupec CSV"])
        self.table_mapping.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_mapping.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_mapping.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_mapping.setSelectionMode(QTableWidget.NoSelection)
        self.table_mapping.setEditTriggers(QTableWidget.NoEditTriggers)
        mapping_layout.addWidget(self.table_mapping)

        layout.addWidget(mapping_group)

        # === Unit Selection Section ===
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

        # === Data Preview Section ===
        preview_group = QGroupBox("Náhled dat (prvních 10 řádků)")
        preview_layout = QVBoxLayout(preview_group)

        self.table_preview = QTableWidget()
        self.table_preview.setMaximumHeight(200)
        preview_layout.addWidget(self.table_preview)

        layout.addWidget(preview_group)

        # === Dialog Buttons ===
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Importovat")
        button_box.button(QDialogButtonBox.Cancel).setText("Zrušit")
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.button_box = button_box
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

        # Populate zone mapping table with existing zones
        self._populate_mapping_table()

    def _populate_mapping_table(self):
        """Populate the zone-to-column mapping table with existing zones."""
        self.table_mapping.setRowCount(len(self.zones))
        self.mapping_combos.clear()

        for i, zone in enumerate(self.zones):
            # Zone name
            zone_item = QTableWidgetItem(f"Zóna {i + 1}")
            zone_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_mapping.setItem(i, 0, zone_item)

            # Y range
            y_range_text = f"{zone.y_min:.2f} - {zone.y_max:.2f} m"
            y_range_item = QTableWidgetItem(y_range_text)
            y_range_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_mapping.setItem(i, 1, y_range_item)

            # Column selector combobox (initially empty)
            combo = QComboBox()
            combo.addItem("-- Přeskočit --", None)
            combo.currentIndexChanged.connect(lambda idx, zone_idx=i: self._on_mapping_changed(zone_idx))
            self.table_mapping.setCellWidget(i, 2, combo)
            self.mapping_combos.append(combo)

    def _on_browse_file(self):
        """Handle file browser button click."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte CSV soubor",
            "",
            "CSV (*.csv);;Text (*.txt);;Všechny soubory (*)"
        )
        if not path:
            # User cancelled - close the dialog
            self.reject()
            return

        try:
            self._on_file_selected(path)
        except Exception as e:
            logger.exception("Failed to load CSV file")
            QMessageBox.critical(self, "Chyba", f"Chyba při načítání souboru:\n{str(e)}")
            self.reject()

    def _on_file_selected(self, filepath: str):
        """Process selected CSV file."""
        # Parse CSV headers (now returns num_header_rows instead of has_header)
        headers, delimiter, num_header_rows = parse_csv_headers(filepath)

        self.csv_filepath = filepath
        self.csv_headers = headers
        self.csv_delimiter = delimiter
        self.num_header_rows = num_header_rows

        # Update file info label
        self.lbl_file_info.setText(
            f"<b>Načteno:</b> {len(headers)} sloupců"
        )

        # Populate time column selector (preselect first column)
        self.combo_time_column.blockSignals(True)
        self.combo_time_column.clear()
        for col_idx, header in enumerate(headers):
            display_name = header if header else f"Sloupec {col_idx + 1}"
            self.combo_time_column.addItem(display_name, col_idx)
        self.combo_time_column.setCurrentIndex(0)  # Default to first column
        self.time_column_index = 0
        self.combo_time_column.blockSignals(False)

        # Update mapping comboboxes with ALL columns (not just TEMP_XX)
        for combo in self.mapping_combos:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("-- Přeskočit --", None)
            # Add all columns with their headers or "Sloupec X" if no header
            for col_idx, header in enumerate(headers):
                # Use actual header or generate "Sloupec X" label
                display_name = header if header else f"Sloupec {col_idx + 1}"
                combo.addItem(display_name, col_idx)
            combo.blockSignals(False)

        # Enable OK button
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)

        # Clear previous mappings
        self.column_mappings.clear()

        # Update preview (empty initially)
        self._update_preview()

    def _on_time_column_changed(self):
        """Handle time column selection change."""
        self.time_column_index = self.combo_time_column.currentData()
        if self.time_column_index is None:
            self.time_column_index = 0
        # Update preview with new time column
        self._update_preview()

    def _on_mapping_changed(self, zone_idx: int):
        """Handle column mapping change for a zone."""
        if zone_idx >= len(self.mapping_combos):
            return

        combo = self.mapping_combos[zone_idx]
        col_idx = combo.currentData()

        if col_idx is None:
            # User selected "Skip"
            if zone_idx in self.column_mappings:
                del self.column_mappings[zone_idx]
        else:
            # User mapped this zone to a column
            self.column_mappings[zone_idx] = col_idx

        # Update preview
        self._update_preview()

    def _update_preview(self):
        """Update data preview table based on current mappings."""
        if not self.csv_filepath or not self.column_mappings:
            self.table_preview.clear()
            self.table_preview.setRowCount(0)
            self.table_preview.setColumnCount(0)
            return

        try:
            # Read first 10 rows of CSV
            with open(self.csv_filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=self.csv_delimiter)
                all_rows = list(reader)

            # Skip header rows and get first 10 data rows
            data_rows = all_rows[self.num_header_rows:self.num_header_rows + 10]

            # Setup preview table
            mapped_zones = sorted(self.column_mappings.keys())
            self.table_preview.setColumnCount(1 + len(mapped_zones))  # Time + mapped zones
            headers = ["Čas [s]"] + [f"Zóna {z + 1}" for z in mapped_zones]
            self.table_preview.setHorizontalHeaderLabels(headers)
            self.table_preview.setRowCount(len(data_rows))

            # Populate preview
            for row_idx, row in enumerate(data_rows):
                if len(row) <= self.time_column_index:
                    continue

                # Time column
                try:
                    time_val = row[self.time_column_index]
                    self.table_preview.setItem(row_idx, 0, QTableWidgetItem(time_val))
                except (ValueError, IndexError):
                    pass

                # Temperature columns
                for col_idx, zone_idx in enumerate(mapped_zones, start=1):
                    temp_col_idx = self.column_mappings[zone_idx]
                    if len(row) > temp_col_idx:
                        try:
                            temp_val = row[temp_col_idx]
                            self.table_preview.setItem(row_idx, col_idx, QTableWidgetItem(temp_val))
                        except (ValueError, IndexError):
                            pass

            self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        except Exception as e:
            logger.exception("Failed to update preview")

    def _validate_mappings(self) -> tuple[bool, str]:
        """
        Validate current mappings before accepting.

        Returns:
            (is_valid, error_message) tuple
        """
        if not self.csv_filepath:
            return False, "Nebyl vybrán žádný CSV soubor."

        if not self.column_mappings:
            return False, "Musíte namapovat alespoň jednu zónu."

        # Check that mapped columns have sufficient data
        time_unit = self.combo_time_unit.currentData()
        temp_unit = self.combo_temp_unit.currentData()

        try:
            for zone_idx, col_idx in self.column_mappings.items():
                data = read_csv_column(
                    self.csv_filepath,
                    col_idx,
                    self.time_column_index,
                    time_unit,
                    temp_unit,
                    self.csv_delimiter,
                    self.num_header_rows
                )

                if len(data['times']) < 2:
                    # Get column name from headers
                    col_name = self.csv_headers[col_idx] if col_idx < len(self.csv_headers) else f"Sloupec {col_idx + 1}"
                    if not col_name:
                        col_name = f"Sloupec {col_idx + 1}"
                    return False, f"Sloupec {col_name} obsahuje méně než 2 platné body."

        except Exception as e:
            return False, f"Chyba při validaci dat: {str(e)}"

        # Warn about unmapped zones (non-blocking)
        unmapped_zones = [i + 1 for i in range(len(self.zones)) if i not in self.column_mappings]
        if unmapped_zones:
            zone_list = ", ".join(map(str, unmapped_zones))
            QMessageBox.information(
                self,
                "Informace",
                f"Zóny {zone_list} nebyly namapovány.\nJejich data zůstanou nezměněna."
            )

        return True, ""

    def _on_accept(self):
        """Handle OK button click."""
        is_valid, error_msg = self._validate_mappings()

        if not is_valid:
            QMessageBox.warning(self, "Chyba", error_msg)
            return

        self.accept()

    def get_imported_data(self) -> Dict[int, dict]:
        """
        Extract imported data for all mapped zones.

        Returns:
            Dict mapping zone_idx to {'times': [...], 'temperatures': [...]}
        """
        if not self.csv_filepath or not self.column_mappings:
            return {}

        time_unit = self.combo_time_unit.currentData()
        temp_unit = self.combo_temp_unit.currentData()

        imported_data = {}

        for zone_idx, col_idx in self.column_mappings.items():
            try:
                data = read_csv_column(
                    self.csv_filepath,
                    col_idx,
                    self.time_column_index,
                    time_unit,
                    temp_unit,
                    self.csv_delimiter,
                    self.num_header_rows
                )
                imported_data[zone_idx] = data
            except Exception as e:
                logger.exception(f"Failed to read column {col_idx} for zone {zone_idx}")
                continue

        return imported_data


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
        btn_imp = QPushButton("Import z CSV...")
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
        table = self.table
        table.blockSignals(True)
        table.setRowCount(0)

        if not self.current_config or len(self.current_config.temperatures) < 2:
            # Fallback: Create 20-1200 range based on existing value or 0
            self.current_config.times = [0.0, 10_800.0]  # 20 min to 3 hours in seconds
            self.current_config.temperatures = [20.0, 1200.0]

        table.setRowCount(len(self.current_config.times))
        for i, (t_sec, T) in enumerate(zip(self.current_config.times, self.current_config.temperatures)):
            t_min = t_sec / 60.0  # Convert Seconds to Minutes for UI
            table.setItem(i, 0, QTableWidgetItem(f"{t_min:.2f}"))
            table.setItem(i, 1, QTableWidgetItem(f"{T:.1f}"))

        table.blockSignals(False)
        # self.table.blockSignals(True)
        # self.table.setRowCount(0)
        # if self.current_config:
        #     times_sec = self.current_config.times
        #     temps = self.current_config.temperatures
        #     self.table.setRowCount(len(times_sec))
        #     for i, (t_sec, T) in enumerate(zip(times_sec, temps)):
        #         t_min = t_sec / 60.0  # Convert Seconds to Minutes for UI
        #         self.table.setItem(i, 0, QTableWidgetItem(f"{t_min:.2f}"))
        #         self.table.setItem(i, 1, QTableWidgetItem(f"{T:.1f}"))
        # self.table.blockSignals(False)

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

        self._load_table()
        self.dataChanged.emit()

    def _add_row(self):
        """Add a new row to the table."""
        self.table.blockSignals(True)
        try:
            # Scrape current UI data
            points = []
            for r in range(self.table.rowCount()):
                try:
                    t = float(self.table.item(r, 0).text())
                    T = float(self.table.item(r, 1).text())
                    points.append((t, T))
                except (ValueError, AttributeError): pass

            # Calculate insertion point
            if not points:
                points = [(20.0, 293.15), (180.0, 800.0)]  # Default points if none exist
            elif len(points) == 1:
                points.append((points[0][0] + 10.0, points[0][1] + 100.0))
            else:
                # find max gap
                max_gap = -1.0
                best_idx = 0
                for i in range(len(points) - 1):
                    gap = points[i + 1][0] - points[i][0]
                    if gap > max_gap:
                        max_gap = gap
                        best_idx = i

                # split gap
                t1, T1 = points[best_idx]
                t2, T2 = points[best_idx + 1]

                new_t = t1 + max_gap / 2.0
                ratio = (new_t - t1) / max_gap
                new_T = T1 + ratio * (T2 - T1)

                points.append((new_t, new_T))

            # sort points
            points.sort(key=lambda x: x[0])
            t_list = [p[0] for p in points]
            T_list = [p[1] for p in points]
            self.current_config.times = [t * 60.0 for t in t_list]  # Minutes to Seconds
            self.current_config.temperatures = T_list
        finally:
            self.table.blockSignals(False)

        self._load_table()
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
    - Enforces geometric constraints based on tunnel geometry
    """
    dataChanged = Signal()
    selectionChanged = Signal()  # Emitted when zone selection changes to update plot preview

    def __init__(self, project_state, parent=None):
        super().__init__(parent)
        self.project_state = project_state
        self.current_config: Optional[ZonalFireCurveConfig] = None
        self._init_ui()

    def _get_tunnel_min_max_height(self) -> tuple[float, float]:
        """
        Extract the maximum height H of the tunnel from project geometry.
        Returns the ceiling height that zones must cover up to.
        """
        geometry = self.project_state.geometry

        # Try to get resolved profile
        profile = geometry.get_resolved_profile()

        if profile and profile.y_bounds:
            # Use the maximum y-bound from the profile
            return profile.y_bounds

        # Fallback: Default height if geometry not defined
        logger.warning("Could not determine tunnel height from geometry, using default 7.5m")
        return 0.0, 7.5  # Default height range

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Info about zonal curves
        info = QLabel("<b>Vícezónová okrajová podmínka:</b> Definujte průběh teploty "
                      "po výšce konstrukce. Zóny musí pokrývat celou výšku bez mezer.")
        info.setWordWrap(True)
        layout.addWidget(info)

        # --- Zones Section ---
        grp_zones = QGroupBox("Zóny (dle výšky Y)")
        l_zones = QVBoxLayout(grp_zones)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Y min [m]", "Y max [m]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_zone_selected)
        l_zones.addWidget(self.table)

        h_tools = QHBoxLayout()
        btn_add = QPushButton("Přidat zónu")
        btn_del = QPushButton("Smazat zónu")
        self.btn_import_csv = QPushButton("Import teplot z CSV...")
        btn_add.clicked.connect(self._add_zone)
        btn_del.clicked.connect(self._del_zone)
        self.btn_import_csv.clicked.connect(self._import_zones_from_csv)
        h_tools.addWidget(btn_add)
        h_tools.addWidget(btn_del)
        h_tools.addWidget(self.btn_import_csv)
        h_tools.addStretch()
        l_zones.addLayout(h_tools)

        # --- Zone Detail Editor ---
        self.grp_zone_detail = QGroupBox("Nastavení vybrané zóny")
        self.grp_zone_detail.setEnabled(False)
        l_detail = QVBoxLayout(self.grp_zone_detail)

        # Zone limits info label
        self.lbl_zone_limits = QLabel()
        self.lbl_zone_limits.setWordWrap(True)
        l_detail.addWidget(self.lbl_zone_limits)

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

        # Ensure at least one zone covering [0, H]
        if not self.current_config.zones:
            H_min, H_max = self._get_tunnel_min_max_height()
            default_curve = TabulatedFireCurveConfig(
                name="ZoneCurve",
                times=[0, 3600],  # 0 and 60 minutes in seconds
                temperatures=[20, 800]
            )
            self.current_config.zones = [ZoneConfig(y_min=H_min, y_max=H_max, curve=default_curve)]
            self.table.blockSignals(True)
            self.table.selectRow(0)
            self.table.blockSignals(False)

        self._load_zones_table()
        # Reset selection details
        self.grp_zone_detail.setEnabled(False)
        # Enable/disable import button based on whether zones exist
        self.btn_import_csv.setEnabled(len(self.current_config.zones) > 0)
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
            t_str = "Vlastní (jednozónová)"
            item = QTableWidgetItem(t_str)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # Read-only
            self.table.setItem(i, 2, item)

        self.table.blockSignals(False)

    def _save_zone_geometry(self):
        """
        Save zone geometry with validation, clamping, and continuity enforcement.
        - Clamps values to [0, H]
        - Ensures y_min < y_max
        - Enforces continuity between adjacent zones
        """
        if not self.current_config:
            return

        H_min, H_max = self._get_tunnel_min_max_height()

        # Block signals to prevent recursive updates
        self.table.blockSignals(True)

        try:
            # First pass: Read and validate all values
            new_zones = []
            for r in range(self.table.rowCount()):
                if r >= len(self.current_config.zones):
                    break

                try:
                    y1 = float(self.table.item(r, 0).text().replace(',', '.'))
                    y2 = float(self.table.item(r, 1).text().replace(',', '.'))

                    # Clamp to [H_min, H_max]
                    y1 = max(H_min, min(y1, H_max))
                    y2 = max(H_min, min(y2, H_max))

                    # Ensure y_min < y_max (minimum gap of 0.1m)
                    if y2 - y1 < 0.1:
                        y2 = min(y1 + 0.1, H_max)

                    new_zones.append((y1, y2))
                except (ValueError, AttributeError):
                    # Keep existing values on parse error
                    zone = self.current_config.zones[r]
                    new_zones.append((zone.y_min, zone.y_max))

            # Second pass: Enforce continuity between adjacent zones
            for r in range(len(new_zones)):
                y1, y2 = new_zones[r]

                # Enforce continuity with previous zone
                if r > 0:
                    prev_y2 = new_zones[r - 1][1]
                    # Current zone's y_min must match previous zone's y_max
                    y1 = prev_y2

                # Enforce continuity with next zone
                if r < len(new_zones) - 1:
                    next_y1, next_y2 = new_zones[r + 1]
                    # Next zone's y_min must match current zone's y_max
                    new_zones[r + 1] = (y2, next_y2)

                # Update the zone
                self.current_config.zones[r].y_min = y1
                self.current_config.zones[r].y_max = y2

            # Reload table to show corrected values
            self._load_zones_table()

            # Update the zone limits label if a zone is currently selected
            current_row = self.table.currentRow()
            if 0 <= current_row < len(self.current_config.zones):
                zone = self.current_config.zones[current_row]
                self.lbl_zone_limits.setText(
                    f"<b>Zóna {current_row + 1}:</b> Výška Y = {zone.y_min:.2f} m až {zone.y_max:.2f} m "
                    f"(rozsah: {zone.y_max - zone.y_min:.2f} m)"
                )

        finally:
            self.table.blockSignals(False)

        self.dataChanged.emit()

    def _on_zone_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_config.zones):
            self.grp_zone_detail.setEnabled(False)
            self.lbl_zone_limits.setText("")
            self.selectionChanged.emit()
            return

        self.grp_zone_detail.setEnabled(True)
        zone = self.current_config.zones[row]

        # Update zone limits label
        self.lbl_zone_limits.setText(
            f"<b>Zóna {row + 1}:</b> {zone.y_min:.2f} m až {zone.y_max:.2f} m "
            f"(rozsah: {zone.y_max - zone.y_min:.2f} m)"
        )

        # Zone curve is always Tabulated (enforced on creation)
        if isinstance(zone.curve, TabulatedFireCurveConfig):
            self.edit_zone_tab.set_config(zone.curve)
        else:
            logger.error(f"Zone {row} has invalid curve type: {zone.curve.type}")

        self.selectionChanged.emit()

    def _add_zone(self):
        """
        Add a new zone by splitting the currently selected zone in half.
        If no zone is selected, split the first zone.
        The new zone inherits the curve type from the parent zone.
        """
        if not self.current_config.zones:
            # Should not happen due to set_config enforcement, but handle gracefully
            H_min, H_max = self._get_tunnel_min_max_height()
            new_curve = TabulatedFireCurveConfig(
                name="ZoneCurve",
                times=[0, 3600],
                temperatures=[20, 800]
            )
            self.current_config.zones = [ZoneConfig(y_min=H_min, y_max=H_max, curve=new_curve)]
            self._load_zones_table()
            self.dataChanged.emit()
            return

        # Get selected zone index, default to first zone if none selected
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_config.zones):
            row = 0

        # Split the selected zone
        zone_to_split = self.current_config.zones[row]
        y_min = zone_to_split.y_min
        y_max = zone_to_split.y_max
        y_mid = (y_min + y_max) / 2.0

        # Update the original zone to cover first half
        zone_to_split.y_max = y_mid

        # Create new zone for second half, inheriting the curve type
        new_curve = copy.deepcopy(zone_to_split.curve)
        new_zone = ZoneConfig(y_min=y_mid, y_max=y_max, curve=new_curve)

        # Insert the new zone right after the split zone
        self.current_config.zones.insert(row + 1, new_zone)

        self._load_zones_table()
        self.dataChanged.emit()

    def _del_zone(self):
        """
        Delete the selected zone and merge its space into an adjacent zone.
        Enforces minimum one zone constraint.
        """
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_config.zones):
            return

        # Enforce minimum one zone
        if len(self.current_config.zones) <= 1:
            QMessageBox.warning(
                self,
                "Nelze smazat",
                "Musí existovat alespoň jedna zóna pokrývající celou výšku tunelu."
            )
            return

        # Get the zone to delete
        zone_to_delete = self.current_config.zones[row]

        # Merge space into adjacent zone
        if row > 0:
            # Merge into previous zone (extend its y_max)
            self.current_config.zones[row - 1].y_max = zone_to_delete.y_max
        elif row < len(self.current_config.zones) - 1:
            # This is the first zone, merge into next zone (extend its y_min)
            self.current_config.zones[row + 1].y_min = zone_to_delete.y_min

        # Delete the zone
        del self.current_config.zones[row]

        self._load_zones_table()
        self.dataChanged.emit()
        self.selectionChanged.emit()

    def _import_zones_from_csv(self):
        """
        Import time-temperature data for all zones from a multi-column CSV file.
        User selects which TEMP_XX column maps to which zone.
        """
        if not self.current_config or not self.current_config.zones:
            QMessageBox.warning(
                self,
                "Chyba",
                "Před importem dat musíte nejprve vytvořit zóny."
            )
            return

        # Show import dialog
        dialog = ZonalCsvImportDialog(self.current_config.zones, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return

        # Get imported data
        imported_data = dialog.get_imported_data()

        if not imported_data:
            QMessageBox.warning(self, "Chyba", "Nebyly importována žádná data.")
            return

        # Apply data to zones
        zones_updated = 0
        for zone_idx, data in imported_data.items():
            if zone_idx < len(self.current_config.zones):
                zone = self.current_config.zones[zone_idx]
                # Update zone's curve (already in correct units from dialog)
                zone.curve.times = data['times']
                zone.curve.temperatures = data['temperatures']
                zones_updated += 1

        # Refresh UI
        if self.table.currentRow() >= 0:
            # Reload currently selected zone's curve editor
            self._on_zone_selected()

        # Emit change signals
        self.dataChanged.emit()
        self.selectionChanged.emit()

        # Show success message
        total_points = len(imported_data[list(imported_data.keys())[0]]['times']) if imported_data else 0
        QMessageBox.information(
            self,
            "Import úspěšný",
            f"Data úspěšně importována pro {zones_updated} {'zónu' if zones_updated == 1 else 'zóny' if zones_updated < 5 else 'zón'}.\n"
            f"Celkový počet bodů: {total_points}"
        )


# ==============================================================================
# MAIN DIALOG
# ==============================================================================

class FireCurveDialog(QDialog):
    def __init__(self, project_state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Knihovna okrajových podmínek")
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
        left.addWidget(QLabel("Dostupné okrajové podmínky:"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection)
        left.addWidget(self.list_widget)

        # Action buttons
        btn_add = QPushButton("Nová")
        btn_add.clicked.connect(self.on_add)
        left.addWidget(btn_add)

        self.btn_copy = QPushButton("Kopírovat")
        self.btn_copy.clicked.connect(self.on_copy)
        self.btn_copy.setEnabled(False)
        left.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("Smazat")
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
        self.form = QFormLayout()
        self.edit_name = QLineEdit()
        self.edit_name.editingFinished.connect(self.on_name_change)
        self.form.addRow("Název:", self.edit_name)

        self.edit_desc = QLineEdit()
        self.edit_desc.editingFinished.connect(self.on_desc_change)
        self.form.addRow("Popis:", self.edit_desc)

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

        self.form.addRow("Typ:", self.type_row_widget)
        l_center.addLayout(self.form)

        # Stack
        self.stack = QStackedWidget()
        self.editor_std = StandardCurveEditor()
        self.editor_tab = TabulatedCurveEditor()
        self.editor_zone = ZonalCurveEditor(project_state=self.project_ref)

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
        self.form.setRowVisible(self.type_row_widget, False)

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
            self.form.setRowVisible(self.type_row_widget, True)

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
        base = "Nová okrajová podmínka"
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

    def _update_plot(self):
        """Updates the plot preview based on the selected fire curve."""
        curve = self.current_curve
        if not curve:
            self.plot_widget.clear()
            return

        times, temps = get_preview_data(curve)

        self.plot_widget.clear()
        pen = pg.mkPen(color='r', width=2)
        self.plot_widget.plot(times, temps, pen=pen)
