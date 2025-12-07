import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QSlider, QHBoxLayout, QGroupBox, QMessageBox, QProgressBar, QFormLayout,
    QDoubleSpinBox, QStyle, QSpinBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
import logging

from temperatureanalysis.model.io import IOManager
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.controller.workers import SolverWorker, prepare_simulation_model


logger = logging.getLogger(__name__)

class ResultsControlPanel(QWidget):
    # Signal: (mesh_path, temperature_array)
    update_view_requested = Signal(str, object, bool)
    results_generated = Signal()

    def __init__(self, project_state: ProjectState) -> None:
        super().__init__()
        self.project = project_state
        self.solver_worker = None

        # Animation Timer
        self.timer = QTimer()
        self.timer.setInterval(200)  # 200ms per frame (5 FPS)
        self.timer.timeout.connect(self.advance_frame)

        layout = QVBoxLayout(self)

        # --- Simulation Settings ---
        grp_settings = QGroupBox("Nastavení výpočtu")
        form_settings = QFormLayout(grp_settings)

        self.spin_total_time = QDoubleSpinBox()
        self.spin_total_time.setDecimals(0)
        self.spin_total_time.setRange(1.0, 180.0)  # Up to 3 hours
        self.spin_total_time.setValue(self.project.total_time_minutes)
        self.spin_total_time.setSuffix(" min")
        self.spin_total_time.valueChanged.connect(self.on_params_changed)
        form_settings.addRow("Celkový čas:", self.spin_total_time)

        self.spin_dt = QDoubleSpinBox()
        self.spin_dt.setDecimals(0)
        self.spin_dt.setRange(1.0, 60.0)  # Up to 1 min step
        self.spin_dt.setValue(self.project.time_step)
        self.spin_dt.setSuffix(" s")
        self.spin_dt.valueChanged.connect(self.on_params_changed)
        form_settings.addRow("Časový krok:", self.spin_dt)

        layout.addWidget(grp_settings)

        # --- Analysis ---
        grp_calc = QGroupBox("Výpočet")
        l_calc = QVBoxLayout(grp_calc)

        self.btn_run = QPushButton("Spustit výpočet")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.clicked.connect(self.on_run_clicked)
        l_calc.addWidget(self.btn_run)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        l_calc.addWidget(self.progress)

        # Export Results Button
        self.btn_export = QPushButton("Exportovat do ParaView...")
        self.btn_export.clicked.connect(self.on_export_clicked)
        self.btn_export.setEnabled(False)  # Disabled until results exist
        l_calc.addWidget(self.btn_export)

        layout.addWidget(grp_calc)

        # --- Viz ---
        grp_vis = QGroupBox("Prohlížeč")
        l_vis = QVBoxLayout(grp_vis)

        self.lbl_time = QLabel("Čas: -")
        self.lbl_time.setAlignment(Qt.AlignCenter)
        l_vis.addWidget(self.lbl_time)

        # Playback Controls Layout
        hbox_play = QHBoxLayout()

        self.btn_play = QPushButton()
        # Use built-in standard icon for Play
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setEnabled(False)
        hbox_play.addWidget(self.btn_play)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.on_slider_changed)
        hbox_play.addWidget(self.slider)

        l_vis.addLayout(hbox_play)

        # FPS Control
        hbox_fps = QHBoxLayout()
        hbox_fps.addWidget(QLabel("Rychlost animace:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 60)
        self.spin_fps.setValue(10)  # Default 10 FPS
        self.spin_fps.setSuffix(" FPS")
        self.spin_fps.valueChanged.connect(self.on_fps_changed)
        hbox_fps.addWidget(self.spin_fps)
        hbox_fps.addStretch()
        l_vis.addLayout(hbox_fps)

        # Apply initial FPS
        self.on_fps_changed(self.spin_fps.value())

        layout.addWidget(grp_vis)
        layout.addStretch()

    def on_fps_changed(self, value: int) -> None:
        """Update timer interval based on FPS."""
        if value > 0:
            interval = 1000 // value
            self.timer.setInterval(interval)

    def on_params_changed(self) -> None:
        self.project.total_time_minutes = self.spin_total_time.value()
        self.project.time_step = self.spin_dt.value()

    def load_from_state(self) -> None:
        """Syncs UI from loaded ProjectState."""
        self.spin_total_time.blockSignals(True)
        self.spin_dt.blockSignals(True)

        self.spin_total_time.setValue(self.project.total_time_minutes)
        self.spin_dt.setValue(self.project.time_step)

        self.spin_total_time.blockSignals(False)
        self.spin_dt.blockSignals(False)

        # Reset slider/status if results exist
        if self.project.results:
            self.on_finished()  # Re-enable controls
        else:
            self.slider.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.lbl_time.setText("Čas: -")

    def on_run_clicked(self) -> None:
        if not self.project.mesh_path:
            QMessageBox.warning(self, "Chyba", "Nejdříve musíte vygenerovat síť.")
            return

        self.btn_run.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate mode while loading
        self.lbl_time.setText("Načítání modelu...")
        self.repaint()  # Force redraw

        try:
            # 1. LOAD MODEL IN MAIN THREAD (Fixes signal error)
            # This might freeze UI for a second, but it's safe.
            model = prepare_simulation_model(self.project)

            # 2. START SOLVER IN WORKER THREAD
            self.progress.setRange(0, 100)  # Switch to percentage
            self.solver_worker = SolverWorker(model, self.project)
            self.solver_worker.progress_updated.connect(self.on_progress)
            self.solver_worker.finished.connect(self.on_finished)
            self.solver_worker.error_occurred.connect(self.on_error)
            self.solver_worker.start()

        except Exception as e:
            logger.exception("Model preparation failed")
            self.on_error(str(e))

    def on_progress(self, percent: int, msg: str) -> None:
        self.progress.setValue(percent)
        self.lbl_time.setText(msg)

    def on_finished(self) -> None:
        self.btn_run.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_time.setText("Výpočet dokončen.")

        count = len(self.project.results)
        if count > 0:
            self.slider.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_export.setEnabled(True)
            self.slider.blockSignals(True)
            self.slider.setRange(0, count - 1)
            self.slider.setValue(count - 1)
            self.slider.blockSignals(False)
            self.update_view_requested.emit(self.project.mesh_path, self.project.results[-1], False)

            # Notify that results are ready
            self.results_generated.emit()

    def on_error(self, msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Chyba Výpočtu", msg)

    def on_export_clicked(self) -> None:
        """Export result sequence."""
        if not self.project.results:
            return

        dir_path = QFileDialog.getExistingDirectory(self, "Vybrat složku pro export")
        if dir_path:
            try:
                self.lbl_time.setText("Exportuji data...")
                self.repaint()
                output_path = IOManager.export_results_to_vtu(self.project, dir_path)
                self.lbl_time.setText("Export dokončen.")
                QMessageBox.information(self, "Export",
                                        f"Data uložena do:\n{output_path}\n\nOtevřete soubor .pvd v ParaView.")
            except Exception as e:
                QMessageBox.critical(self, "Chyba Exportu", str(e))

    def on_slider_changed(self, index: int) -> None:
        if not self.project.results or not self.project.mesh_path: return

        temp_data = self.project.results[index]
        time_val = self.project.time_steps[index]

        self.lbl_time.setText(f"Čas: {str(datetime.timedelta(seconds=time_val))}")

        # Emit signal to MainWindow
        self.update_view_requested.emit(self.project.mesh_path, temp_data, False)

    # --- ANIMATION LOGIC ---

    def toggle_play(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        else:
            # If at the end, restart from 0
            if self.slider.value() >= self.slider.maximum():
                self.slider.setValue(0)
            self.timer.start()

        self.update_play_icon()

    def advance_frame(self) -> None:
        current = self.slider.value()
        if current < self.slider.maximum():
            self.slider.setValue(current + 1)
        else:
            self.timer.stop()
            self.update_play_icon()

    def update_play_icon(self) -> None:
        if self.timer.isActive():
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
