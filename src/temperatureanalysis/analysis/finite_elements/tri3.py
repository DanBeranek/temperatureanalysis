from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement
import temperatureanalysis.analysis.gauss as gauss

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.analysis.node import Node
    from temperatureanalysis.pre.material import Material


TRI_ARRAY = np.array([
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
])

B_ISO = np.array([
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
])


class Tri3(FiniteElement):
    """
    Represents a three-node linear triangular finite element (Tri3).
    """
    def __init__(
        self,
        index: int,
        tag: str,
        nodes: list[Node],
        material: Material
    ) -> None:
        """
        Initialize the Tri3 element.

        Args:
            index: Element index.
            tag: Element tag.
            nodes: List of nodes that form the element.
            material: The material associated with the element.
        """
        super().__init__(
            index=index,
            tag=tag,
            nodes=nodes,
            material=material,
            n_integration_points=3
        )

    @staticmethod
    def shape_functions(iso_coords: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Calculate the shape functions for the Tri3 element.

        Args:
            iso_coords: Isoparametric coordinates [r, s, t] in the range [0, 1].

        Returns:
            Shape function values at the given coordinates [N1, N2, N3].
        """
        # For Tri3, the shape functions are the isoparametric coordinates
        return np.array([iso_coords])

    @property
    def area(self) -> float:
        """
        Calculate the area of the Tri3 element.

        Returns:
            Area of the triangular element.
        """
        x1, y1 = self.nodes[0].coords
        x2, y2 = self.nodes[1].coords
        x3, y3 = self.nodes[2].coords

        return 0.5 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    def b_matrix_jacobian(self) -> tuple[npt.NDArray[np.float64], float]:
        """
        Calculate the B matrix and its Jacobian for the Tri3 element.

        Returns:
            Tuple containing the B matrix and the Jacobian.
        """
        x1, y1 = self.nodes[0].coords
        x2, y2 = self.nodes[1].coords
        x3, y3 = self.nodes[2].coords

        # Calculate the area of the triangle
        A_e = self.area

        # Calculate the B matrix
        b1 = y2 - y3
        b2 = y3 - y1
        b3 = y1 - y2
        c1 = x3 - x2
        c2 = x1 - x3
        c3 = x2 - x1

        B_e = (1 / (2 * A_e)) * np.array([[b1, b2, b3], [c1, c2, c3]])

        return B_e, A_e

    def get_conductivity_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the conductivity matrix [K] for the Tri3 element.

        Returns:
            Conductivity matrix for the element.
        """
        K_e = np.zeros((3, 3), dtype=np.float64)

        gauss_points, weights = gauss.gauss_points_weights_triangle(self.n_integration_points)

        T_at_nodes = np.array([node.current_temperature for node in self.nodes])

        B_e, J = self.b_matrix_jacobian()

        for gp_i, w_i in zip(gauss_points, weights):
            # Calculate the shape functions at the integration point
            N_ei = self.shape_functions(iso_coords=gp_i)

            # Calculate the temperature at the integration point
            T_i = np.sum(N_ei * T_at_nodes)

            # Calculate the thermal conductivity at the integration point
            lambda_ci = self.material.thermal_conductivity(temperature_K=T_i)

            K_e += B_e.T @ B_e * J * lambda_ci * w_i

        return K_e


    def get_capacity_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the capacity matrix [C] for the Tri3 element.

        Returns:
            Capacity matrix for the element.
        """
        C_e = np.zeros((3, 3), dtype=np.float64)

        gauss_points, weights = gauss.gauss_points_weights_triangle(self.n_integration_points)

        A_e = self.area

        T_at_nodes = np.array([node.current_temperature for node in self.nodes])

        for gp_i, w_i in zip(gauss_points, weights):
            # Calculate the shape functions at the integration point
            N_ei = self.shape_functions(iso_coords=gp_i)

            # Calculate the temperature at the integration point
            T_i = np.sum(N_ei * T_at_nodes)

            # Calculate the density and specific heat capacity at the integration point
            rho_ci = self.material.density(temperature_K=T_i)
            c_pi = self.material.specific_heat_capacity(temperature_K=T_i)

            # Calculate the contribution to the capacity matrix
            C_e += A_e * N_ei.T @ N_ei * rho_ci * c_pi * w_i

        return C_e


if __name__ == "__main__":
    # Example usage
    from temperatureanalysis.analysis.node import Node
    from temperatureanalysis.pre.material import Concrete

    # Create nodes
    node1 = Node(index=0, coords=[0.0, 0.0])
    node2 = Node(index=1, coords=[1.0, 0.0])
    node3 = Node(index=2, coords=[0.0, 1.0])

    # Create material
    material = Concrete()

    # Create Tri3 element
    tri3_element = Tri3(index=1, tag="Tri3Element", nodes=[node1, node2, node3], material=material)

    print(tri3_element)
    print("Area:", tri3_element.area)
    print("Capacity Matrix:\n", tri3_element.get_capacity_matrix())
    print("Capacity Matrix:\n", tri3_element.get_conductivity_matrix())




