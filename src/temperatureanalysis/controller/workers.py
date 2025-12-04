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
    MesherWorker: Runs the Gmsh generation process.
"""
from PySide6.QtCore import QThread, Signal


class SolverWorker(QThread):
    # Signals to update the UI from the background
    progress_updated = Signal(int, str)  # e.g., (10, "Solving step 5/50...")
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, solver_instance, project_data):
        super().__init__()
        self.solver = solver_instance
        self.data = project_data

    def run(self):
        try:
            # Run the heavy loop
            # The solver should ideally yield progress
            for progress in self.solver.run_analysis(self.data):
                self.progress_updated.emit(progress, "Running...")

            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))
