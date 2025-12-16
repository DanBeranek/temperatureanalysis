import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QSlider, QHBoxLayout, QGroupBox, QMessageBox, QProgressBar, QFormLayout,
    QDoubleSpinBox, QStyle, QSpinBox, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
import logging

from temperatureanalysis.model.io import IOManager
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.controller.solver import SolverWorker, prepare_simulation_model
from temperatureanalysis.view.dialogs.thermocouple_plot_dialog import ThermocouplePlotDialog


logger = logging.getLogger(__name__)

class ResultsControlPanel(QWidget):
    # Signal: (mesh_path, temperature_array, v_min_override, reset_camera)
    update_view_requested = Signal(str, object, object, bool)
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

        self.spin_critical_temp = QDoubleSpinBox()
        self.spin_critical_temp.setDecimals(0)
        self.spin_critical_temp.setRange(100.0, 1000.0)
        self.spin_critical_temp.setValue(500.0)
        self.spin_critical_temp.setSuffix(" °C")
        self.spin_critical_temp.setToolTip("Kritická teplota výztuže pro analýzu")
        form_settings.addRow("Kritická teplota výztuže:", self.spin_critical_temp)

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

        # Colorbar Min Value Control
        hbox_min = QHBoxLayout()
        hbox_min.addWidget(QLabel("Min. Teplota:"))

        self.chk_auto_min = QCheckBox("Auto")
        self.chk_auto_min.setChecked(True)
        self.chk_auto_min.toggled.connect(self.on_vis_settings_changed)
        hbox_min.addWidget(self.chk_auto_min)

        self.spin_vmin = QDoubleSpinBox()
        self.spin_vmin.setRange(20, 2000)
        self.spin_vmin.setValue(20)
        self.spin_vmin.setSuffix(" °C")
        self.spin_vmin.setEnabled(False)
        self.spin_vmin.valueChanged.connect(self.on_vis_settings_changed)
        hbox_min.addWidget(self.spin_vmin)

        l_vis.addLayout(hbox_min)

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

        # --- Rebar Analysis ---
        grp_rebar = QGroupBox("Analýza Výztuže")
        l_rebar = QVBoxLayout(grp_rebar)

        self.lbl_stats = QLabel("Statistiky budou dostupné po dokončení výpočtu.")
        self.lbl_stats.setWordWrap(True)
        self.lbl_stats.setTextFormat(Qt.RichText)
        self.lbl_stats.setStyleSheet("QLabel { padding: 5px; background-color: rgba(0,0,0,10); border-radius: 3px; }")
        l_rebar.addWidget(self.lbl_stats)

        self.btn_plot_rebar = QPushButton("Vykreslit Teploty Výztuže")
        self.btn_plot_rebar.clicked.connect(self.on_plot_rebar_clicked)
        self.btn_plot_rebar.setEnabled(False)
        l_rebar.addWidget(self.btn_plot_rebar)

        layout.addWidget(grp_rebar)

        layout.addStretch()

    def on_fps_changed(self, value: int) -> None:
        """Update timer interval based on FPS."""
        if value > 0:
            interval = 1000 // value
            self.timer.setInterval(interval)

    def on_params_changed(self) -> None:
        self.project.total_time_minutes = self.spin_total_time.value()
        self.project.time_step = self.spin_dt.value()

    def on_vis_settings_changed(self) -> None:
        """Called when auto-min checkbox or spinbox changes."""
        self.spin_vmin.setEnabled(not self.chk_auto_min.isChecked())

        # Trigger update of the view
        if self.project.results:
            self.on_slider_changed(self.slider.value())

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
            self.solver_worker.results_ready.connect(self.on_results_ready)  # THREAD SAFE
            self.solver_worker.finished.connect(self.on_finished)
            self.solver_worker.error_occurred.connect(self.on_error)
            self.solver_worker.start()

        except Exception as e:
            logger.exception("Model preparation failed")
            self.on_error(str(e))

    def on_progress(self, percent: int, msg: str) -> None:
        self.progress.setValue(percent)
        self.lbl_time.setText(msg)

    def on_results_ready(self, temperatures: list, time_steps: list) -> None:
        """
        THREAD SAFE: Handle results from worker thread.
        This runs in the main thread via Qt's signal/slot mechanism.
        """
        self.project.results = temperatures
        self.project.time_steps = time_steps
        logger.info(f"Results received: {len(temperatures)} frames")

    def on_finished(self) -> None:
        self.btn_run.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_time.setText("Výpočet dokončen.")

        count = len(self.project.results)
        if count > 0:
            self.slider.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_export.setEnabled(True)
            self.slider.setRange(0, count - 1)
            # Setting slider value will emit slider change and update view
            self.slider.setValue(count - 1)

            # Calculate and display statistics
            self._update_rebar_statistics()

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

        # Determine v_min override
        v_min_override = None
        if not self.chk_auto_min.isChecked():
            v_min_override = self.spin_vmin.value()

        # Emit signal to MainWindow
        self.update_view_requested.emit(self.project.mesh_path, temp_data, v_min_override, False)

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

    def reset_status(self) -> None:
        """Reset all status indicators."""
        self.lbl_time.setText("Čas: -")
        self.slider.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_plot_rebar.setEnabled(False)
        self.slider.setValue(0)
        self.update_play_icon()
        self.lbl_stats.setText("Statistiky budou dostupné po dokončení výpočtu.")

    def _update_rebar_statistics(self) -> None:
        """Calculate and display rebar temperature statistics."""
        if not self.project.results or not self.project.time_steps:
            return

        try:
            # Load model to access thermocouple data
            model = prepare_simulation_model(self.project)

            if not model.mesh.thermocouples:
                self.lbl_stats.setText("<b>Informace:</b> V síti nebyly nalezeny žádné termočlánky (výztuž).")
                self.btn_plot_rebar.setEnabled(False)
                return

            # Extract thermocouple node indices
            tc_indices = [node.uid for node in model.mesh.thermocouples.values()]

            # Get critical temperature
            T_crit = self.spin_critical_temp.value()  # Celsius

            # Convert results to Celsius for analysis
            import numpy as np
            results_celsius = [np.asarray(temp_K) - 273.15 for temp_K in self.project.results]
            time_steps_min = [t / 60.0 for t in self.project.time_steps]  # Convert to minutes

            # Calculate max concrete temp across all nodes
            max_concrete_temps = [np.max(temp) for temp in results_celsius]
            idx_max_concrete = int(np.argmax(max_concrete_temps))
            max_concrete_temp = max_concrete_temps[idx_max_concrete]
            time_max_concrete = time_steps_min[idx_max_concrete]

            # Calculate max rebar temp across thermocouple nodes
            max_rebar_temps = [np.max(temp[tc_indices]) for temp in results_celsius]
            idx_max_rebar = int(np.argmax(max_rebar_temps))
            max_rebar_temp = max_rebar_temps[idx_max_rebar]
            time_max_rebar = time_steps_min[idx_max_rebar]

            # Find critical failure time (first time any thermocouple exceeds T_crit)
            critical_time = None
            for i, temp in enumerate(results_celsius):
                if np.max(temp[tc_indices]) > T_crit:
                    critical_time = time_steps_min[i]
                    break

            # Format statistics display
            stats_text = "<b>Statistiky Teplotní Analýzy:</b><br><br>"

            stats_text += f"<b>Maximální Teplota Betonu:</b><br>"
            stats_text += f"&nbsp;&nbsp;• Teplota: {max_concrete_temp:.1f} °C<br>"
            stats_text += f"&nbsp;&nbsp;• Čas: {time_max_concrete:.1f} min<br><br>"

            stats_text += f"<b>Maximální Teplota Výztuže:</b><br>"
            stats_text += f"&nbsp;&nbsp;• Teplota: {max_rebar_temp:.1f} °C<br>"
            stats_text += f"&nbsp;&nbsp;• Čas: {time_max_rebar:.1f} min<br><br>"

            stats_text += f"<b>Kritická Teplota: {T_crit:.0f} °C</b><br>"
            if critical_time is not None:
                stats_text += f"&nbsp;&nbsp;• ⚠ Překročeno v čase: {critical_time:.1f} min<br>"
            else:
                stats_text += f"&nbsp;&nbsp;• ✓ Nepřekročeno během analýzy<br>"

            self.lbl_stats.setText(stats_text)
            self.btn_plot_rebar.setEnabled(True)

        except Exception as e:
            logger.exception("Failed to calculate rebar statistics")
            self.lbl_stats.setText(f"<b>Chyba při výpočtu statistik:</b><br>{str(e)}")
            self.btn_plot_rebar.setEnabled(False)

    def on_plot_rebar_clicked(self) -> None:
        """Plot rebar temperature history using the thermocouple plot dialog."""
        if not self.project.results or not self.project.time_steps:
            return

        try:
            # Load model to access thermocouple data
            model = prepare_simulation_model(self.project)

            if not model.mesh.thermocouples:
                QMessageBox.warning(self, "Chyba", "V síti nebyly nalezeny termočlánky.")
                return

            # Get critical temperature
            T_crit = self.spin_critical_temp.value()

            # Open the dialog
            dialog = ThermocouplePlotDialog(
                thermocouples=model.mesh.thermocouples,
                results=self.project.results,
                time_steps=self.project.time_steps,
                critical_temp=T_crit,
                parent=self
            )
            dialog.exec()

        except Exception as e:
            logger.exception("Failed to open thermocouple plot dialog")
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se otevřít dialog s grafem:\n{str(e)}")
