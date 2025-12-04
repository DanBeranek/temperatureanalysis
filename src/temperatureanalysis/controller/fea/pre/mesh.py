from __future__ import annotations

from datetime import datetime

from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import gmsh

from temperatureanalysis.controller.fea.pre.fire_curves import FireCurve
from temperatureanalysis.controller.fea.pre.material import Material
from temperatureanalysis.controller.fea.analysis.node import Node
from temperatureanalysis.controller.fea.analysis.finite_elements.finite_element import FiniteElement
from temperatureanalysis.controller.fea.analysis.finite_elements.tri3 import Tri3
from temperatureanalysis.controller.fea.analysis.finite_elements.tri6 import Tri6
from temperatureanalysis.controller.fea.analysis.finite_elements.quad4 import Quad4
from temperatureanalysis.controller.fea.analysis.finite_elements.quad8 import Quad8
from temperatureanalysis.controller.fea.analysis.finite_elements.edges import LineElement, Line2, Line3

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    pass

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

THERMOCOUPLE_PREFIX = "THERMOCOUPLE"

class Mesh:
    def __init__(
        self,
        nodes: list[Node],
        elements: dict[str, list[FiniteElement]],
        boundary_elements: dict[str, list[LineElement]],
        filename: str | None = None,
        gmsh_nodes_mapping: list[tuple[int, int]] | None = None,
        thermocouples: dict[str, Node] | None = None,
    ) -> None:
        """
        Initialize the Mesh class.
        """
        nodes.sort(key=lambda node: node.uid)
        self.nodes = nodes
        self.elements = elements
        self.boundary_elements = boundary_elements
        self.thermocouples = thermocouples or {}
        self.filename = filename
        self.gmsh_nodes_mapping = gmsh_nodes_mapping  # (gmsh position, zero-based index)

    @classmethod
    def from_file(
        cls,
        filename: str,
        physical_surface_to_material_mapping: dict[str, Material],
        physical_line_to_fire_curve_mapping: dict[str, FireCurve],
    ) -> Mesh:
        """
        Strict, string-only parsing with three kinds of entities:
            - Points: physical name must start with 'THERMOCOUPLE';
                      must map to exactly one unique Node.
            - Lines: require fire-curve mapping by physical *name*.
            - Surfaces: require material mapping by physical *name*.

        Also enforces 1:1 correspondence:
            - set(surface_to_material_mapping.keys()) == set(surface names in mesh)
            - set(boundary_to_fire_curve_mapping.keys()) == set(line names in mesh)

        """
        gmsh.initialize()
        gmsh.open(filename)

        # 1) Read all nodes once
        node_tags, flat_coords, _ = gmsh.model.mesh.get_nodes()
        coords = flat_coords.reshape(-1, 3)  # Reshape to (num_nodes, 3)
        nodes: list[Node] = []
        nodes_lookup: dict[int, Node] = {}
        nodes_mapping: list[tuple[int, int]] = []  # stores the mapping from GMSH file node position to zero-based index

        for i, (tag, xy) in enumerate(zip(node_tags, coords[:, :2])):  # Use only x and y coordinates
            zero_based_index = tag - 1  # GMSH uses 1-based indexing, convert to 0-based
            node = Node(index=zero_based_index, coords=xy)
            nodes.append(node)
            nodes_lookup[zero_based_index] = node
            nodes_mapping.append((i, zero_based_index))

        # 2) Prepare containers for elements by physical-group names
        surface_elements: dict[str, list[FiniteElement]] = defaultdict(list)
        boundary_elements: dict[str, list[LineElement]] = defaultdict(list)

        # Track used physical tags for the 1:1 mapping check later
        used_surface_physical_tags: set[str] = set()
        used_line_physical_tags: set[str] = set()

        # temporary storage for points -> set of zero-based node indices (validate to exactly one later)
        thermocouples_temporary: dict[str, set[int]] = defaultdict(set)

        def get_single_named_physical(dim: int, entity_tag: int) -> str:
            """
            Strict resolver, requires exactly one non-empty physical name.
            """
            phys_tags = gmsh.model.get_physical_groups_for_entity(dim, entity_tag)
            if not phys_tags:
                raise ValueError(
                    f"Entity (dim={dim}, tag={entity_tag}) has no associated physical group. "
                    "Every entity with elements must belong to exactly one physical group."
                )

            names = []
            for pt in phys_tags:
                name = gmsh.model.get_physical_name(dim, pt)
                if name is None or name.strip() == "":
                    raise ValueError(
                        f"Physical group (dim={dim}, tag={pt}) has empty/undefined name. "
                        "Only non-empty physical group names are supported."
                    )
                names.append(name)

            # Must be exactly one name to avoid ambiguity
            if len(names) != 1:
                raise ValueError(
                    f"Entity (dim={dim}, tag={entity_tag}) belongs to multiple physical groups: {names}. "
                    "Each entity must belong to exactly one named physical group."
                )

            return names[0]

        # 3) Loop all gmsh entities to pick up physical-group names and entities' elements
        for dim, entity_tag in gmsh.model.get_entities():
            # Get the element types and tags and node connectivity for this entity
            element_types, element_tags_list, node_tags = gmsh.model.mesh.get_elements(dim, entity_tag)
            if element_types.size == 0:
                continue  # No elements for this entity, skip

            blocks = [
                (t, etags, ntags)
                for t, etags, ntags in zip(element_types, element_tags_list, node_tags)
                if t in ELEMENT_TYPE_MAP or t == 15  # 15 is for point elements (thermocouples)
            ]

            if not blocks:
                continue

            # Determine the strict domain name; this also validates the name exists in mapping
            domain_name = get_single_named_physical(dim, entity_tag)

            # Points (thermocouples)
            point_blocks = [(t, etags, ntags) for t, etags, ntags in blocks if t == 15]
            if point_blocks:
                if not domain_name.startswith(THERMOCOUPLE_PREFIX):
                    raise ValueError(
                        f"Point entity (dim=0, tag={entity_tag}) has physical name '{domain_name}' "
                        f"but point physical names must start with '{THERMOCOUPLE_PREFIX}'."
                    )
                for _, _, flat_node_tags in point_blocks:
                    node_ids0 = (flat_node_tags - 1).tolist()  # Convert to 0-based index
                    for nid in node_ids0:
                        thermocouples_temporary[domain_name].add(nid)

            # Non-point blocks
            non_point_blocks = [(t, etags, ntags) for t, etags, ntags in blocks if t != 15]
            if not non_point_blocks:
                continue  # No non-point elements, skip

            has_surface = any(t in SURFACE_ELEMENT_TYPE_MAP for t, _, _ in non_point_blocks)
            has_line = any(t in LINE_ELEMENT_TYPE_MAP for t, _, _ in non_point_blocks)

            # Resolve mapping and track usage
            material = None
            if has_surface:
                if domain_name not in physical_surface_to_material_mapping:
                    raise ValueError(
                        f"Surface entity (dim={dim}, tag={entity_tag}) has physical name '{domain_name}' "
                        "which is not present in the provided `physical_surface_to_material_mapping`."
                    )
                material = physical_surface_to_material_mapping[domain_name]
                used_surface_physical_tags.add(domain_name)

            fire_curve = None
            if has_line:
                if domain_name not in physical_line_to_fire_curve_mapping:
                    raise ValueError(
                        f"Line entity (dim={dim}, tag={entity_tag}) has physical name '{domain_name}' "
                        "which is not present in the provided `physical_line_to_fire_curve_mapping`."
                    )
                fire_curve = physical_line_to_fire_curve_mapping[domain_name]
                used_line_physical_tags.add(domain_name)

            # Build elements

            # Loop through each element type
            for element_type, element_tags, flat_node_tags in zip(element_types, element_tags_list, node_tags):
                if element_type not in ELEMENT_TYPE_MAP:
                    # Skip unsupported element types
                    continue

                # Get the correct element class and number of nodes per element
                element_class, nodes_per_element = ELEMENT_TYPE_MAP[element_type]
                node_connectivity_matrix = flat_node_tags.reshape(-1, nodes_per_element) - 1 # Convert to 0-based index

                is_line = element_type in LINE_ELEMENT_TYPE_MAP
                is_surface = element_type in SURFACE_ELEMENT_TYPE_MAP

                # Instantiate elements
                for node_tags_for_element, element_tag in zip(node_connectivity_matrix, element_tags):
                    # Get the nodes for this element
                    element_nodes = [nodes_lookup[tag] for tag in node_tags_for_element]

                    # Convert the element tag to zero-based index
                    element_tag = element_tag - 1  # GMSH uses 1-based indexing, convert to 0-based

                    # Create the element instance
                    if is_line:
                        element = element_class(index=element_tag, tag="", nodes=element_nodes, fire_curve=fire_curve)
                        boundary_elements[domain_name].append(element)

                    elif is_surface:
                        # For surface elements, we need to specify the material
                        element = element_class(index=element_tag, tag="", nodes=element_nodes, material=material)
                        surface_elements[domain_name].append(element)

        # 4) Validate thermocouples
        thermocouples: dict[str, Node] = {}
        for name, ids_set in thermocouples_temporary.items():
            if len(ids_set) != 1:
                raise ValueError(
                    f"Physical group '{name}' has {len(ids_set)} associated nodes, but exactly one is required."
                )
            idx0 = next(iter(ids_set))
            thermocouples[name] = nodes_lookup[idx0]

        # 5) 1:1 correspondence checks
        mesh_surface_names = used_surface_physical_tags
        mesh_line_names = used_line_physical_tags
        map_surface_names = set(physical_surface_to_material_mapping.keys())
        map_line_names = set(physical_line_to_fire_curve_mapping.keys())

        extra_surfaces = sorted(map_surface_names - mesh_surface_names)
        missing_surfaces = sorted(map_surface_names - map_surface_names)

        extra_lines = sorted(map_line_names - mesh_line_names)
        missing_lines = sorted(map_line_names - map_line_names)

        msgs = []
        if missing_surfaces or extra_surfaces:
            part = []
            if missing_surfaces: part.append(f"surface missing in mapping: {missing_surfaces}")
            if extra_surfaces: part.append(f"surface unused in mesh: {extra_surfaces}")
            msgs.append("; ".join(part))
        if missing_lines or extra_lines:
            part = []
            if missing_lines: part.append(f"boundary missing in mapping: {missing_lines}")
            if extra_lines:   part.append(f"boundary unused in mesh: {extra_lines}")
            msgs.append("; ".join(part))

        if msgs:
            raise ValueError("Physical names do not correspond to the dictionaries (" + " | ".join(msgs) + ").")


        gmsh.finalize()
        return cls(
            nodes=nodes,
            elements=surface_elements,
            boundary_elements=boundary_elements,
            filename=filename,
            gmsh_nodes_mapping=nodes_mapping,
            thermocouples=thermocouples
        )

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
    test = Mesh.from_file("../../../../../assets/rectangle-middle-elements.msh")
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

