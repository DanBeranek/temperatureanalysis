from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from temperatureanalysis.pre.mesh import Mesh

if TYPE_CHECKING:
    import numpy.typing as npt


class Model:
    """
    Class represent the entire heat transfer model.

    This class encapsulates the nodes, elements, and materials used in the heat transfer analysis.
    """
    def __init__(self):
        """Initialize the Model object."""
        self.mesh: Mesh | None = None

        self.n_dof_per_node: int = 1  # Number of degrees of freedom per node (default is 1 for temperature)

        self.k_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)
        self.c_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        self.dof_connectivity_matrix: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)

    @property
    def number_of_nodes(self) -> int:
        """Return the number of nodes in the model."""
        return len(self.mesh.nodes)

    @property
    def number_of_elements(self) -> int:
        """Return the number of elements in the model."""
        return len(self.mesh.elements)

    @property
    def number_of_equations(self) -> int:
        """Return the total number of equations in the model."""
        return self.number_of_nodes * self.n_dof_per_node





