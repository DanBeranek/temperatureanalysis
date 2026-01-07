"""
Mesh Generation Control Panel
"""
import os
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QDoubleSpinBox, QGroupBox, QFormLayout, QMessageBox, QCheckBox,
    QFileDialog, QSpinBox
)
from PySide6.QtCore import Signal, Qt

from temperatureanalysis.model.io import IOManager
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.controller.mesher import GmshMesher

class MeshControlPanel(QWidget):
    # Signal emitted when mesh is ready, passing the file path
    mesh_generated = Signal(str)

    def __init__(self, project_state: ProjectState) -> None:
        super().__init__()
        self.project = project_state
        self.mesher = GmshMesher()

        layout = QVBoxLayout(self)

        # --- Settings Group ---
        grp = QGroupBox("Nastavení sítě")
        form = QFormLayout(grp)

        # 1. Gradient Toggle
        self.chk_gradient = QCheckBox("")
        self.chk_gradient.toggled.connect(self.on_gradient_toggled)
        form.addRow("Použít proměnnou hustotu sítě", self.chk_gradient)

        # 2. Inner Size (Always active)
        self.lc_inner_spin = QDoubleSpinBox()
        self.lc_inner_spin.setRange(0.01, 2.0)
        self.lc_inner_spin.setSingleStep(0.01)
        self.lc_inner_spin.setValue(0.03)  # Default fine
        self.lc_inner_spin.setSuffix(" m")
        self.lc_inner_spin.valueChanged.connect(self.on_inner_spin_changed)
        form.addRow("Velikost elementu (líc):", self.lc_inner_spin)

        # 3. Outer Size (Optional)
        self.lc_outer_spin = QDoubleSpinBox()
        self.lc_outer_spin.setRange(0.01, 2.0)
        self.lc_outer_spin.setSingleStep(0.05)
        self.lc_outer_spin.setValue(0.1)  # Default coarse
        self.lc_outer_spin.setSuffix(" m")
        self.lc_outer_spin.setEnabled(False)  # Disabled by default
        form.addRow("Velikost elementu (rub):", self.lc_outer_spin)

        # 4. Thermocouple Count
        self.thermocouple_count_spin = QSpinBox()
        self.thermocouple_count_spin.setRange(5, 100)
        self.thermocouple_count_spin.setSingleStep(1)
        self.thermocouple_count_spin.setValue(self.project.thermocouple_count)
        self.thermocouple_count_spin.valueChanged.connect(self.on_thermocouple_count_changed)
        form.addRow("Počet termočlánků:", self.thermocouple_count_spin)

        layout.addWidget(grp)

        # --- Actions ---
        self.btn_generate = QPushButton("Generovat síť")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.btn_generate)

        self.btn_export = QPushButton("Exportovat síť")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.clicked.connect(self.on_export_clicked)
        self.btn_export.setEnabled(False)  # Disabled until mesh exists
        layout.addWidget(self.btn_export)

        # --- Status Info ---
        self.lbl_status = QLabel("Stav: Síť nebyla generována.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_status)

        self.lbl_stats = QLabel("")
        self.lbl_stats.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_stats)

        layout.addStretch()

    # --- PROPERTIES ---

    @property
    def status_message(self) -> str:
        return self.lbl_status.text()

    @status_message.setter
    def status_message(self, text: str) -> None:
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet("color: gray;")

    def _set_status_styled(self, text: str, color: str, bold: bool = False) -> None:
        self.lbl_status.setText(text)
        weight = "bold" if bold else "normal"
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: {weight};")

    # --- SLOTS ---

    def on_inner_spin_changed(self) -> None:
        if not self.chk_gradient.isChecked():
            # Sync outer with inner when gradient is off
            self.lc_outer_spin.setValue(self.lc_inner_spin.value())

    def on_gradient_toggled(self, checked: bool) -> None:
        self.lc_outer_spin.setEnabled(checked)
        if not self.chk_gradient.isChecked():
            # Sync outer with inner when gradient is off
            self.lc_outer_spin.setValue(self.lc_inner_spin.value())

    def on_thermocouple_count_changed(self, value: int) -> None:
        """Update project state when thermocouple count changes."""
        self.project.thermocouple_count = value

    def on_generate_clicked(self) -> None:
        lc_min = self.lc_inner_spin.value()
        lc_max = self.lc_outer_spin.value()
        use_gradient = self.chk_gradient.isChecked()

        # If gradient is off, use inner size everywhere
        if not use_gradient:
            lc_max = lc_min

        self.status_message = "Generuji síť..."
        self.lbl_stats.setText("")
        self.btn_generate.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.repaint()

        try:
            # Run generation with new params
            result = self.mesher.generate_mesh(
                self.project,
                lc_min=lc_min,
                lc_max=lc_max,
                use_gradient=use_gradient
            )

            self.project.mesh_path = result.filepath

            self._set_status_styled("Stav: Hotovo ✓", "green", bold=True)
            self.lbl_stats.setText(
                f"Počet uzlů: {result.num_nodes}\n"
                f"Počet elementů: {result.num_elements}"
            )

            self.btn_export.setEnabled(True)

            self.mesh_generated.emit(result.filepath)

        except Exception as e:
            self._set_status_styled("Chyba při generování", "red")
            QMessageBox.critical(self, "Chyba sítě", str(e))

        finally:
            self.btn_generate.setEnabled(True)

    def on_export_clicked(self) -> None:
        """Export the current temporary mesh file to a user-selected location."""
        if not self.project.mesh_path or not os.path.exists(self.project.mesh_path):
            QMessageBox.warning(self, "Chyba", "Neexistuje žádný soubor sítě k exportu.")
            return

        # Suggest a filename
        default_name = "tunnel_mesh.msh"
        if self.project.filepath:
            # Use project name if available
            base = os.path.splitext(os.path.basename(self.project.filepath))[0]
            default_name = f"{base}_mesh.msh"

        dest_path, _ = QFileDialog.getSaveFileName(
            self, "Exportovat síť", default_name, "Gmsh Files (*.msh);;All Files (*)"
        )

        if dest_path:
            try:
                # Ensure extension
                if not dest_path.endswith('.msh'):
                    dest_path += '.msh'

                IOManager.export_mesh_file(self.project.mesh_path, dest_path)
                QMessageBox.information(self, "Export", f"Síť byla úspěšně uložena do:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Chyba Exportu", f"Nepodařilo se uložit soubor:\n{str(e)}")

    def reset_status(self) -> None:
        self._set_status_styled("Stav: Síť nebyla generována.", "gray", bold=True)
        self.lbl_stats.setText("")
        self.btn_export.setEnabled(False)

    def update_status_from_state(self) -> None:
        if self.project.mesh_path:
            self._set_status_styled("Stav: Načteno ze souboru ✓", "green", bold=True)

            # Try to read mesh statistics from the loaded file
            stats = self.mesher.read_mesh_stats(self.project.mesh_path)
            if stats:
                self.lbl_stats.setText(
                    f"Počet uzlů: {stats.num_nodes}\n"
                    f"Počet elementů: {stats.num_elements}"
                )
            else:
                self.lbl_stats.setText("")

            self.btn_export.setEnabled(True)
        else:
            self.status_message = "Stav: Síť nebyla generována."
            self.lbl_stats.setText("")
            self.btn_export.setEnabled(False)
