from __future__ import annotations

from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import gmsh

from temperatureanalysis.pre.material import Concrete
from temperatureanalysis.analysis.node import Node
from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement
from temperatureanalysis.analysis.finite_elements.tri3 import Tri3
from temperatureanalysis.analysis.finite_elements.tri6 import Tri6
from temperatureanalysis.analysis.finite_elements.quad4 import Quad4
from temperatureanalysis.analysis.finite_elements.quad8 import Quad8

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import numpy.typing as npt


DUMMY_CONCRETE = Concrete()

class Mesh:
    def __init__(
        self,
        nodes: list[Node],
        elements: list[FiniteElement],
        boundary_elements: list[FiniteElement] | None = None,
    ) -> None:
        """
        Initialize the Mesh class.
        """
        self.nodes = nodes
        self.elements = elements
        self.boundary_elements = boundary_elements

    @classmethod
    def from_file(cls, filename: str) -> Mesh:
        """Load mesh data from a file."""
        gmsh.initialize()
        gmsh.open(filename)

        # 1) Load nodes
        node_tags, flat_coords, _ = gmsh.model.mesh.get_nodes()
        coords = flat_coords.reshape(-1, 3)  # Reshape to (num_nodes, 3)
        nodes = []
        node_tag_to_object = {}
        for i, (tag, xy) in enumerate(zip(node_tags, coords[:, :2])):  # Use only x and y coordinates
            node = Node(index=tag, coords=xy)
            nodes.append(node)
            node_tag_to_object[tag] = node

        # 2) Load elements
        # gmsh element type code to (FiniteElement class, number of nodes per element)
        element_type_map = {
            2: (Tri3, 3),
            9: (Tri6, 6),
            3: (Quad4, 4),
            10: (Quad8, 8),
        }

        element_types, element_tags, element_node_tags = gmsh.model.mesh.get_elements()
        elements = []
        for etype, tags, flat_node_tags in zip(element_types, element_tags, element_node_tags):
            if etype not in element_type_map:
                # skip unsupported element types
                continue

            ElementClass, nodes_per_element = element_type_map[etype]
            node_connectivity_matrix = flat_node_tags.reshape(-1, nodes_per_element)

            # Instantiate elements
            for node_tags, element_tag in zip(node_connectivity_matrix, tags):
                # Get the nodes for this element
                element_nodes = [node_tag_to_object[tag] for tag in node_tags]
                element = ElementClass(index=element_tag, tag="", nodes=element_nodes, material=DUMMY_CONCRETE)  # TODO: Replace DUMMY_CONCRETE with actual material
                elements.append(element)

        gmsh.finalize()
        return cls(nodes=nodes, elements=elements)

    def add_node(self, node: Node) -> None:
        """Add a node to the mesh."""
        self.nodes.append(node)

    def add_element(self, element: FiniteElement) -> None:
        """Add an element to the mesh."""
        self.elements.append(element)

    def plot(self) -> None:
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
    # Example usage of the Mesh class
    test = Mesh.from_file("../../../assets/rectangle-coarse-elements.msh")
    test.plot()

    # concrete = Concrete()

    # mesh = Mesh()

    # nodes = [
    #     Node(0, [0.0, 0.0]),
    #     Node(1, [0.1, 0.0]),
    #     Node(2, [0.2, 0.0]),
    #     Node(3, [0.0, 0.1]),
    #     Node(4, [0.1, 0.1]),
    #     Node(5, [0.2, 0.1]),
    #     Node(6, [0.0, 0.2]),
    #     Node(7, [0.1, 0.2]),
    #     Node(8, [0.2, 0.2]),
    #     Node(9, [0.0, 0.3]),
    #     Node(10, [0.1, 0.3]),
    #     Node(11, [0.2, 0.3]),
    # ]
    #
    # elements = [
    #     Tri3(0, "", [nodes[0], nodes[1], nodes[3]], concrete),
    #     Tri3(1, "", [nodes[1], nodes[4], nodes[3]], concrete),
    #     Tri3(2, "", [nodes[1], nodes[2], nodes[4]], concrete),
    #     Tri3(3, "", [nodes[2], nodes[5], nodes[4]], concrete),
    #     Tri3(4, "", [nodes[3], nodes[4], nodes[6]], concrete),
    #     Tri3(5, "", [nodes[4], nodes[7], nodes[6]], concrete),
    #     Tri3(6, "", [nodes[4], nodes[5], nodes[7]], concrete),
    #     Tri3(7, "", [nodes[5], nodes[8], nodes[7]], concrete),
    #     Tri3(8, "", [nodes[6], nodes[7], nodes[9]], concrete),
    #     Tri3(9, "", [nodes[7], nodes[10], nodes[9]], concrete),
    #     Tri3(10, "", [nodes[7], nodes[8], nodes[10]], concrete),
    #     Tri3(11, "", [nodes[8], nodes[11], nodes[10]], concrete),
    # ]
    #
    # for n in nodes:
    #     mesh.add_node(n)
    #
    # for e in elements:
    #     mesh.add_element(e)
    #
    # mesh.plot()

