from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import numpy as np
import scipy as sp

from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement

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

    def _assemble_global_matrix(
        self,
        get_local_matrix: Callable[[FiniteElement], npt.NDArray[np.float64]]
    ) -> sp.sparse.coo_matrix[np.float64]:
        """
        Assemble a global matrix in COO form for the model using a provided function to get the element matrix.

        Args:
            get_local_matrix:

        Returns:

        """
        row: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        col: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        data: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        for elements in self.model.mesh.elements.values():
            for element in elements:
                dofs = element.globals_dofs
                n_dofs = len(dofs)

                m_el = get_local_matrix(element)

                r = np.repeat(dofs, n_dofs)
                c = np.tile(dofs, n_dofs)

                row = np.hstack((row, r))
                col = np.hstack((col, c))
                data = np.hstack((data, m_el.flatten()))

        return sp.sparse.coo_matrix(
            (data, (row, col)),
            shape=(self.model.number_of_equations, self.model.number_of_equations)
        )


    def assemble_global_conductivity_matrix(self) -> None:
        """
        Assemble the global conductivity matrix [K] for the model.
        """
        self.model.k_global = self._assemble_global_matrix(
            get_local_matrix=lambda element: element.get_conductivity_matrix()
        )


    def assemble_global_capacity_matrix(self) -> None:
        """
        Assemble the global capacity matrix [C] for the model.
        """
        self.model.c_global = self._assemble_global_matrix(
            get_local_matrix=lambda element: element.get_capacity_matrix()
        )


