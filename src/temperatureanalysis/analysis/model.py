from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
import matplotlib.pyplot as plt

from temperatureanalysis.pre.material import Material

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.analysis.node import Node
    from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement


class Model:
    """
    Class represent the entire heat transfer model.

    This class encapsulates the nodes, elements, and materials used in the heat transfer analysis.
    """
    def __init__(self):
        """Initialize the Model object."""
        self.nodes: set[Node] = set()
        self.elements: set[FiniteElement] = set()
        self.materials: set[Material] = set()

        self.n_dof_per_node: int = 1  # Number of degrees of freedom per node (default is 1 for temperature)

        self.k_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)
        self.c_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        self.dof_connectivity_matrix: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)

    @property
    def number_of_nodes(self) -> int:
        """Return the number of nodes in the model."""
        return len(self.nodes)

    @property
    def number_of_elements(self) -> int:
        """Return the number of elements in the model."""
        return len(self.elements)

    @property
    def number_of_equations(self) -> int:
        """Return the total number of equations in the model."""
        return self.number_of_nodes * self.n_dof_per_node

    def add_node(self, node: Node) -> None:
        """Add a node to the model."""
        self.nodes.add(node)

    def add_element(self, element: FiniteElement) -> None:
        """Add an element to the model."""
        self.elements.add(element)

    def plot_mesh(self) -> None:
        """Plot the mesh of the model."""
        plt.rcParams["figure.constrained_layout.use"] = True
        fig = plt.figure()

        plt.axis('equal')

        for element in self.elements:
            # Plot the polygon formed by the nodes of the element
            coords = np.array([node.coords for node in element.nodes])
            coords = np.vstack((coords, coords[0]))  # Close the polygon
            plt.plot(coords[:, 0], coords[:, 1], color='black', lw=1)

            # Plot the index of the element at its centroid
            centroid = np.mean(coords[:-1], axis=0)
            plt.text(centroid[0], centroid[1], str(element.id), fontsize=12, color='blue', ha='center', va='center')

        for node in self.nodes:
            # Plot the nodes
            plt.plot(node.x, node.y, 'ro')
            plt.text(node.x, node.y, str(node.id), fontsize=12, color='red', ha='left', va='bottom')

        plt.grid(visible=True, which='major', axis='both', linestyle='-', color='gray', lw=0.5)
        plt.minorticks_on()
        plt.grid(visible=True, which='minor', axis='both', linestyle=':', color='gray', lw=0.5)

        plt.title(f"Mesh plotted at {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        plt.xlabel("X Coordinate")
        plt.ylabel("Y Coordinate")
        plt.show()


if __name__ == "__main__":
    from temperatureanalysis.analysis.finite_elements.tri3 import Tri3
    from temperatureanalysis.analysis.node import Node
    from temperatureanalysis.pre.material import Concrete

    concrete = Concrete()

    model = Model()

    nodes = [
        Node(0, [0.0, 0.0]),
        Node(1, [0.1, 0.0]),
        Node(2, [0.2, 0.0]),
        Node(3, [0.0, 0.1]),
        Node(4, [0.1, 0.1]),
        Node(5, [0.2, 0.1]),
        Node(6, [0.0, 0.2]),
        Node(7, [0.1, 0.2]),
        Node(8, [0.2, 0.2]),
        Node(9, [0.0, 0.3]),
        Node(10, [0.1, 0.3]),
        Node(11, [0.2, 0.3]),
    ]

    elements = [
        Tri3(0, "", [nodes[0], nodes[1], nodes[3]], concrete),
        Tri3(1, "", [nodes[1], nodes[4], nodes[3]], concrete),
        Tri3(2, "", [nodes[1], nodes[2], nodes[4]], concrete),
        Tri3(3, "", [nodes[2], nodes[5], nodes[4]], concrete),
        Tri3(4, "", [nodes[3], nodes[4], nodes[6]], concrete),
        Tri3(5, "", [nodes[4], nodes[7], nodes[6]], concrete),
        Tri3(6, "", [nodes[4], nodes[5], nodes[7]], concrete),
        Tri3(7, "", [nodes[5], nodes[8], nodes[7]], concrete),
        Tri3(8, "", [nodes[6], nodes[7], nodes[9]], concrete),
        Tri3(9, "", [nodes[7], nodes[10], nodes[9]], concrete),
        Tri3(10, "", [nodes[7], nodes[8], nodes[10]], concrete),
        Tri3(11, "", [nodes[8], nodes[11], nodes[10]], concrete),
    ]

    for n in nodes:
        model.add_node(n)

    for e in elements:
        model.add_element(e)

    model.plot_mesh()



