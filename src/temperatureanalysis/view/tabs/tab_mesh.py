"""
Mesh Generation Control Panel
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QDoubleSpinBox, QGroupBox, QFormLayout, QMessageBox
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

        self.lc_spin = QDoubleSpinBox()
        self.lc_spin.setRange(0.01, 2.0)
        self.lc_spin.setSingleStep(0.05)
        self.lc_spin.setValue(0.2)
        self.lc_spin.setSuffix(" m")
        form.addRow("Velikost elementu:", self.lc_spin)

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

        # Detailed stats label
        self.lbl_stats = QLabel("")
        self.lbl_stats.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_stats)

        layout.addStretch()

    def on_generate_clicked(self) -> None:
        mesh_size = self.lc_spin.value()

        self.lbl_status.setText("Generuji síť...")
        self.lbl_stats.setText("")
        self.btn_generate.setEnabled(False)
        self.repaint()

        try:
            # Run generation
            result = self.mesher.generate_mesh(self.project, mesh_size)

            # Update State
            self.project.mesh_path = result.filepath

            # Update UI
            self.lbl_status.setText("Stav: Hotovo ✓")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")

            self.lbl_stats.setText(
                f"Počet uzlů: {result.num_nodes}\n"
                f"Počet elementů: {result.num_elements}"
            )

            # Notify Main Window (pass path for visualization)
            self.mesh_generated.emit(result.filepath)

        except Exception as e:
            self.lbl_status.setText("Chyba při generování")
            self.lbl_status.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Chyba Sítě", str(e))

        finally:
            self.btn_generate.setEnabled(True)

    def reset_status(self) -> None:
        """Called when geometry changes to indicate mesh is invalid."""
        self.lbl_status.setText("Stav: Neaktuální (Geometrie změněna)")
        self.lbl_status.setStyleSheet("color: orange; font-weight: bold;")
        self.lbl_stats.setText("")
