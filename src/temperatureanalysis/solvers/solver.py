from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import scipy as sp

if TYPE_CHECKING:
    import numpy.typing as npt

    from temperatureanalysis.analysis.model import Model


class Solver:
    """
    Class for a FEM solver.
    """

    def __init__(
        self,
        model: Model,
        time_step: float = 1.0,
        initial_time: float = 0.0
    ) -> None:
        """
        Initialize the solver with a model.

        Args:
            model: The model to be solved.
            time_step: The time step in seconds (default is 1.0).
            initial_time: The initial time in seconds (default is 0.0).
        """
        self.model = model
        self.temperature_vector: npt.NDArray[npt.NDArray[float]] = None
        self.time_step = time_step
        self.current_time: initial_time

    def assemble_global_conductivity_matrix(self) -> None:
        """
        Assemble the global conductivity matrix [K] for the model.
        """
        row: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        col: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        data: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        for element in self.model.elements:
            dofs = element.globals_dofs
            n_dofs = len(dofs)

            k_el = element.get_conductivity_matrix()

            r = np.repeat(dofs, n_dofs)
            c = np.tile(dofs, n_dofs)

            k = k_el.flatten()

            row = np.hstack((row, r))
            col = np.hstack((col, c))
            data = np.hstack((data, k))

        self.model.k_global = sp.sparse.coo_matrix(
            (data, (row, col)),
            shape=(self.model.number_of_equations, self.model.number_of_equations)
        )


    def assemble_global_capacity_matrix(self) -> None:
        """
        Assemble the global capacity matrix [C] for the model.
        """
        row: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        col: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        data: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        for element in self.model.elements:
            dofs = element.globals_dofs
            n_dofs = len(dofs)

            c_el = element.get_capacity_matrix()

            r = np.repeat(dofs, n_dofs)
            c = np.tile(dofs, n_dofs)

            row = np.hstack((row, r))
            col = np.hstack((col, c))
            data = np.hstack((data, c_el.flatten()))

        self.model.c_global = sp.sparse.coo_matrix(
            (data, (row, col)),
            shape=(self.model.number_of_equations, self.model.number_of_equations)
        )


