"""
Mesh Generation Control Panel
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QDoubleSpinBox, QGroupBox, QFormLayout, QMessageBox, QCheckBox
)
from PySide6.QtCore import Signal, Qt

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
        grp = QGroupBox("Nastavení Sítě")
        form = QFormLayout(grp)

        # 1. Gradient Toggle
        self.chk_gradient = QCheckBox("")
        self.chk_gradient.toggled.connect(self.on_gradient_toggled)
        form.addRow("Použít proměnnou hustotu sítě", self.chk_gradient)

        # 2. Inner Size (Always active)
        self.lc_inner_spin = QDoubleSpinBox()
        self.lc_inner_spin.setRange(0.01, 2.0)
        self.lc_inner_spin.setSingleStep(0.01)
        self.lc_inner_spin.setValue(0.1)  # Default fine
        self.lc_inner_spin.setSuffix(" m")
        self.lc_inner_spin.valueChanged.connect(self.on_inner_spin_changed)
        form.addRow("Velikost elementu (Vnitřní):", self.lc_inner_spin)

        # 3. Outer Size (Optional)
        self.lc_outer_spin = QDoubleSpinBox()
        self.lc_outer_spin.setRange(0.01, 2.0)
        self.lc_outer_spin.setSingleStep(0.05)
        self.lc_outer_spin.setValue(0.1)  # Default coarse
        self.lc_outer_spin.setSuffix(" m")
        self.lc_outer_spin.setEnabled(False)  # Disabled by default
        form.addRow("Velikost elementu (Vnější):", self.lc_outer_spin)

        layout.addWidget(grp)

        # --- Actions ---
        self.btn_generate = QPushButton("Generovat Síť")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.btn_generate)

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

            self.mesh_generated.emit(result.filepath)

        except Exception as e:
            self._set_status_styled("Chyba při generování", "red")
            QMessageBox.critical(self, "Chyba Sítě", str(e))

        finally:
            self.btn_generate.setEnabled(True)

    def reset_status(self) -> None:
        self._set_status_styled("Stav: Neaktuální (Geometrie změněna)", "orange", bold=True)
        self.lbl_stats.setText("")

    def update_status_from_state(self) -> None:
        if self.project.mesh_path:
            self._set_status_styled("Stav: Načteno ze souboru ✓", "blue", bold=True)
            self.lbl_stats.setText("")
        else:
            self.status_message = "Stav: Síť nebyla generována."
            self.lbl_stats.setText("")
