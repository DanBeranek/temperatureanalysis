from __future__ import annotations

from typing import TYPE_CHECKING
import meshio
import os
import pyvista as pv
import numpy as np
import scipy as sp

from temperatureanalysis.controller.fea.pre.mesh import Mesh

if TYPE_CHECKING:
    import numpy.typing as npt


class Model:
    """
    Class represent the entire heat transfer model.

    This class encapsulates the nodes, elements, and materials used in the heat transfer analysis.
    """
    def __init__(
        self,
        mesh: Mesh,
    ) -> None:
        """Initialize the Model object."""
        self.mesh = mesh

        self.n_dof_per_node: int = 1  # Number of degrees of freedom per node (default is 1 for temperature)

        self.k_global: sp.sparse.coo_matrix[np.float64] = sp.sparse.coo_matrix(
            ([], ([], [])),
            shape=(0, 0),
            dtype=np.float64
        )
        self.c_global: sp.sparse.coo_matrix[np.float64] = sp.sparse.coo_matrix(
            ([], ([], [])),
            shape=(0, 0),
            dtype=np.float64
        )

        self.q_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)
        self.dqdT_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)
        self.t_global: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)  # Global temperature vector

        self.dof_connectivity_matrix: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)

        self.neq_free: int = 0  # Number of free equations (degrees of freedom)
        self.neq_fixed: int = 0  # Number of fixed equations (degrees of freedom)

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

    def assemble_global_dofs(self) -> None:
        """
        Assemble the global degrees of freedom (DOFs) connectivity matrix.

        This method creates a connectivity matrix that maps the local DOFs of each element to the global DOFs.
        """
        self.dof_connectivity_matrix = np.full(
            (self.number_of_elements, self.n_dof_per_node * self.mesh.max_nodes_per_element),
            np.nan,
            dtype=np.int64
        )

        # 1) Setup the global DoF mapping
        for elements in self.mesh.elements.values():
            for i, element in elements:
                for j, node in enumerate(element.nodes):
                    node.global_dofs = np.zeros((node.n_dof_per_node,), dtype=int)

    # def plot_temperature_distribution(self, time: float) -> None:
    #     plt.rcParams["figure.constrained_layout.use"] = True
    #     fig = plt.figure()
    #
    #     plt.axis('equal')
    #
    #     for elements in self.mesh.elements.values():
    #         for element in elements:
    #             # Plot the polygon formed by the nodes of the element
    #             coords = np.array([node.coords for node in element.nodes])
    #             coords = np.vstack((coords, coords[0]))  # Close the polygon
    #             plt.plot(coords[:, 0], coords[:, 1], color='gray', lw=0.5)
    #
    #     X = []
    #     Y = []
    #     for node in self.mesh.nodes:
    #         X.append(node.x)
    #         Y.append(node.y)
    #
    #     Z = self.t_global
    #
    #     # polygon boundary
    #     polygon_x = np.array([0.0, 0.2, 0.2, 0.0, 0.0])
    #     polygon_y = np.array([0.0, 0.0, 0.3, 0.3, 0.0])
    #     domain = Path(np.column_stack((polygon_x, polygon_y)))
    #
    #     # rectangular grid
    #     xi = np.arange(polygon_x.min(), polygon_x.max()+0.005, 0.005)
    #     yi = np.arange(polygon_y.min(), polygon_y.max()+0.005, 0.005)
    #     XI, YI = np.meshgrid(xi, yi)
    #
    #     # interpolate onto the grid
    #     ZI = griddata((X, Y), Z, (XI, YI), method='cubic', fill_value=np.nan) - 273.15  # Convert from Kelvin to Celsius
    #
    #     pts = np.column_stack((XI.flatten(), YI.flatten()))
    #     # mask = domain.contains_points(pts).reshape(XI.shape)
    #     # ZI[~mask] = np.nan
    #
    #
    #     levels = np.arange(0, self.fire_curve.get_temperature(180 * 60) - 273.15, 20)
    #     cf = plt.contourf(XI, YI, ZI, levels=levels, cmap="jet", extend='neither')
    #     # cf = plt.contourf(XI, YI, ZI, cmap="jet", extend='neither')
    #     cbar = plt.colorbar(cf)
    #     plt.title(f"Temperature distribution at time {time:.0f} s")
    #     plt.xlabel("X Coordinate")
    #     plt.ylabel("Y Coordinate")
    #     plt.show()

    def plot_temperature_distribution(self, time: float) -> None:
        filename = self.mesh.filename

        # get the directory of the file
        dir_path = os.path.dirname(os.path.realpath(filename))

        out_filename = f"{dir_path}/temperature_{int(time)}s.vtu"

        # reag gmsh .msh file
        mesh = meshio.read(filename)

        i_array = np.array([m[0] for m in self.mesh.gmsh_nodes_mapping])
        zero_based_index_array = np.array([m[1] for m in self.mesh.gmsh_nodes_mapping])

        temperature_in_gmsh_order = np.empty_like(self.t_global)
        temperature_in_gmsh_order[i_array] = self.t_global[zero_based_index_array]

        mesh.point_data["temperature"] = temperature_in_gmsh_order - 273.15

        mesh.cell_sets = {}
        meshio.write(out_filename, mesh)

        grid = pv.read(out_filename)
        grid.plot(
            scalars="temperature",
            cmap="jet",
            show_edges=True,
            scalar_bar_args={"title": "Temperature (°C)"},
        )




