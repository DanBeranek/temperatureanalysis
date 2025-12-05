"""
Background Workers (Threading)
==============================
This module contains QThread subclasses for handling long-running tasks.

Why is this file needed?
------------------------
1. Responsiveness: If we run the FEM solver on the main thread, the GUI freezes.
   These classes push calculations to a background thread.
2. Signals: They provide a safe way to update the GUI (Progress Bars, Logs)
   from the background process using Qt Signals.

Classes:
    SolverWorker: Runs the FEM analysis loop.
"""
import numpy as np
import time
import logging
from PySide6.QtCore import QThread, Signal

from temperatureanalysis.controller.fea.pre.material import Concrete, Steel, ThermalConductivityBoundary
from temperatureanalysis.controller.fea.pre.mesh import Mesh
from temperatureanalysis.controller.fea.pre.fire_curves import ISO834FireCurve
from temperatureanalysis.controller.fea.analysis.model import Model
from temperatureanalysis.controller.fea.solvers.solver import Solver
from temperatureanalysis.model.state import ProjectState

logger = logging.getLogger(__name__)


def prepare_simulation_model(project: ProjectState) -> Model:
    """
    Loads the mesh and prepares the FEA model.

    CRITICAL: This MUST be called in the MAIN THREAD because Mesh.from_file
    calls gmsh.initialize(), which registers signal handlers (not allowed in threads).
    """
    logger.info("Initializing FEA Model...")

    # 1. Define BCs & Materials # TODO: Hardcoded for now
    fire_curve = ISO834FireCurve()
    concrete = Concrete()

    # 2. Load mesh
    logger.info(f"Loading mesh from: {project.mesh_path}")
    mesh = Mesh.from_file(
        filename=project.mesh_path,
        physical_surface_to_material_mapping={
            "Beton": concrete,
        },
        physical_line_to_fire_curve_mapping={
            "FIRE EXPOSED SIDE": fire_curve
        }
    )

    # 3. Create Analysis Model
    return Model(mesh=mesh)


class SolverWorker(QThread):
    # Signals to update the UI from the background
    progress_updated = Signal(int, str)  # e.g., (10, "Solving step 5/50...")
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, model: Model, project_state: ProjectState):
        super().__init__()
        self.model = model
        self.project = project_state
        self.is_running = True

    def run(self):
        try:
            logger.info("Starting Solver in Background Thread...")

            if not self.project.mesh_path:
                raise ValueError("Mesh not generated.")

            self.progress_updated.emit(0, "Spouštím výpočet...")

            # 4. Initialize Solver
            solver = Solver(model=self.model)

            # 5. Run Simulation
            tot_time = self.project.total_time_minutes * 60.0  # total simulation time in seconds
            dt = self.project.time_step  # time step in seconds

            # ---- Progress callback ----
            def progress_callback(percentage: int) -> None:
                percentage = min(percentage, 98) # Cap at 99% until done
                msg = f"Probíhá výpočet... {percentage}% dokončeno."
                self.progress_updated.emit(percentage, msg)

            # --- RUN SOLVER ---
            # Try passing the callback. If Solver doesn't accept it yet, fallback.
            try:
                result = solver.solve(
                    dt=dt,
                    total_time=tot_time,
                    callback=progress_callback  # <--- Injecting callback
                )
            except TypeError:
                logger.warning("Solver.solve() does not accept 'callback' argument. Running without live updates.")
                result = solver.solve(dt=dt, total_time=tot_time)

            self.progress_updated.emit(99, "Zpracovávám výsledky...")

            logger.info("Extracting results from the model...")
            self.project.results = result.temperatures
            self.project.time_steps = result.time_steps

            self.finished.emit()

        except Exception as e:
            logger.error(f"Error in SolverWorker: {e}")
            self.error_occurred.emit(str(e))

    def stop(self) -> None:
        self.is_running = False
