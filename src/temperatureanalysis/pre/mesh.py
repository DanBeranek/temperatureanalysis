from __future__ import annotations

from datetime import datetime

from collections import defaultdict

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
from temperatureanalysis.analysis.finite_elements.edges import LineElement, Line2, Line3

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import numpy.typing as npt

LINE_ELEMENT_TYPE_MAP = {
    1: (Line2, 2),  # 2-node line
    8: (Line3, 3),  # 3-node second order line (2 nodes associated with the vertices and 1 with the edge).
}

SURFACE_ELEMENT_TYPE_MAP = {
    2: (Tri3, 3),  # 3-node triangle
    3: (Quad4, 4),  # 4-node quadrangle
    9: (Tri6, 6),  # 6-node second order triangle (3 nodes associated with the vertices and 3 with the edges).
    16: (Quad8, 8),  # 8-node second order quadrangle (4 nodes associated with the vertices and 4 with the edges).
}

ELEMENT_TYPE_MAP = {
    **LINE_ELEMENT_TYPE_MAP,
    **SURFACE_ELEMENT_TYPE_MAP,
}

DUMMY_CONCRETE = Concrete()

class Mesh:
    def __init__(
        self,
        nodes: list[Node],
        elements: dict[str, list[FiniteElement]],
        boundary_elements: dict[str, list[LineElement]],
    ) -> None:
        """
        Initialize the Mesh class.
        """
        nodes.sort(key=lambda node: node.uid)
        self.nodes = nodes
        self.elements = elements
        self.boundary_elements = boundary_elements

    @classmethod
    def from_file(cls, filename: str) -> Mesh:
        """Load mesh data from a file."""
        gmsh.initialize()
        gmsh.open(filename)

        # 1) Read all nodes once
        node_tags, flat_coords, _ = gmsh.model.mesh.get_nodes()
        coords = flat_coords.reshape(-1, 3)  # Reshape to (num_nodes, 3)
        nodes = []
        nodes_lookup = {}
        for i, (tag, xy) in enumerate(zip(node_tags, coords[:, :2])):  # Use only x and y coordinates
            zero_based_index = tag - 1  # GMSH uses 1-based indexing, convert to 0-based
            node = Node(index=zero_based_index, coords=xy)
            nodes.append(node)
            nodes_lookup[zero_based_index] = node

        # 2) Prepare containers for elements by physical-group names
        surface_elements: dict[str, list[FiniteElement]] = defaultdict(list)
        boundary_elements: dict[str, list[LineElement]] = defaultdict(list)

        # 3) Loop all gmsh entities to pick up physical-group names and entities' elements
        for dim, entity_tag in gmsh.model.get_entities():
            # Get the names of the physical groups for this entity
            physical_tags = gmsh.model.get_physical_groups_for_entity(dim, entity_tag)
            physical_names = [
                gmsh.model.get_physical_name(dim, physical_tag)
                for physical_tag in physical_tags
            ]

            # Get the element types and tags and node connectivity for this entity
            element_types, element_tags_list, node_tags = gmsh.model.mesh.get_elements(dim, entity_tag)

            # Loop through each element type
            for element_type, element_tags, flat_node_tags in zip(element_types, element_tags_list, node_tags):
                if element_type not in ELEMENT_TYPE_MAP:
                    # Skip unsupported element types
                    continue

                # Get the correct element class and number of nodes per element
                element_class, nodes_per_element = ELEMENT_TYPE_MAP[element_type]
                node_connectivity_matrix = flat_node_tags.reshape(-1, nodes_per_element) - 1 # Convert to 0-based index

                # Instantiate elements
                for node_tags_for_element, element_tag in zip(node_connectivity_matrix, element_tags):
                    # Get the nodes for this element
                    element_nodes = [nodes_lookup[tag] for tag in node_tags_for_element]

                    # Convert the element tag to zero-based index
                    element_tag = element_tag - 1  # GMSH uses 1-based indexing, convert to 0-based

                    # Create the element instance
                    if element_type in LINE_ELEMENT_TYPE_MAP:
                        element = element_class(index=element_tag, tag="", nodes=element_nodes)
                        boundary_elements[physical_names[0]].append(element)

                    elif element_type in SURFACE_ELEMENT_TYPE_MAP:
                        # For surface elements, we need to specify the material
                        element = element_class(index=element_tag, tag="", nodes=element_nodes, material=DUMMY_CONCRETE)
                        surface_elements[physical_names[0]].append(element)

        gmsh.finalize()
        return cls(nodes=nodes, elements=surface_elements, boundary_elements=boundary_elements)

    @property
    def max_nodes_per_element(self) -> int:
        """Return the maximum number of nodes per element in the mesh."""
        if not self.elements:
            return 0
        return max(len(element.nodes) for elements in self.elements.values() for element in elements)

    def add_node(self, node: Node) -> None:
        """Add a node to the mesh."""
        self.nodes.append(node)

    def add_element(self, element: FiniteElement, domain: str) -> None:
        """Add an element to the mesh."""
        self.elements[domain].append(element)

    def add_boundary_element(self, element: LineElement, domain: str) -> None:
        """Add a surface element to the mesh."""
        self.boundary_elements[domain].append(element)

    def plot(self) -> None:
        """Plot the mesh of the model."""
        plt.rcParams["figure.constrained_layout.use"] = True
        fig = plt.figure()

        plt.axis('equal')

        all_tags = list(self.elements.keys()) + list(self.boundary_elements.keys())
        unique_tags = []
        for tag in all_tags:
            if tag not in unique_tags:
                unique_tags.append(tag)

        cmap = plt.get_cmap("gist_rainbow", len(unique_tags))
        tag_to_color = {
            tag: cmap(i % cmap.N) for i, tag in enumerate(unique_tags)
        }
        # keep track of which tags have been seen to avoid duplicate labels
        seen_tags = set()

        for element_tag, elements in self.elements.items():
            color = tag_to_color[element_tag]
            for element in elements:
                # Plot the polygon formed by the nodes of the element
                coords = np.array([node.coords for node in element.nodes])
                coords = np.vstack((coords, coords[0]))  # Close the polygon

                label = element_tag if element_tag not in seen_tags else "_nolegend_"
                seen_tags.add(element_tag)

                plt.fill(coords[:, 0], coords[:, 1], color=color, lw=1, label=label, alpha=0.1)
                plt.plot(coords[:, 0], coords[:, 1], color='black', lw=1)


                # Plot the index of the element at its centroid
                centroid = np.mean(coords[:-1], axis=0)
                plt.text(centroid[0], centroid[1], str(element.id), fontsize=12, color=color, ha='center', va='center')

        for element_tag, elements in self.boundary_elements.items():
            color = tag_to_color[element_tag]
            for element in elements:
                coords = np.array([node.coords for node in element.nodes])

                label = element_tag if element_tag not in seen_tags else "_nolegend_"
                seen_tags.add(element_tag)

                plt.plot(coords[:, 0], coords[:, 1], color=color, lw=2, label=label)
                centroid = np.mean(coords, axis=0)
                plt.text(centroid[0], centroid[1], str(element.id), fontsize=12, color=color, ha='center', va='center',
                         bbox={'boxstyle': 'circle', 'facecolor': 'white', 'edgecolor': color})

        for node in self.nodes:
            # Plot the nodes
            plt.plot(node.x, node.y, 'ko')
            plt.text(node.x, node.y, str(node.uid), fontsize=12, color='k', ha='left', va='bottom')

        plt.grid(visible=True, which='major', axis='both', linestyle='-', color='gray', lw=0.5)
        plt.minorticks_on()
        plt.grid(visible=True, which='minor', axis='both', linestyle=':', color='gray', lw=0.5)

        plt.title(f"Mesh plotted at {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        plt.xlabel("X Coordinate")
        plt.ylabel("Y Coordinate")
        plt.legend(loc='best')
        plt.show()


if __name__ == "__main__":
    # Example usage of the Mesh class
    test = Mesh.from_file("../../../assets/rectangle-middle-elements.msh")
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

