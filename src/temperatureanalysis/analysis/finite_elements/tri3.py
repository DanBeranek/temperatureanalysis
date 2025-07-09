from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement
import temperatureanalysis.analysis.gauss as gauss

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.analysis.node import Node
    from temperatureanalysis.pre.material import Material


# B_N = [
#   [dN1(r,s)/dr, dN2(r,s)/dr, dN3(r,s)/dr],
#   [dN1(r,s)/ds, dN2(r,s)/ds, dN3(r,s)/ds]
# ]
B_N = np.array([
    [-1.0, 1.0, 0.0],
    [-1.0, 0.0, 1.0],
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
            iso_coords: Isoparametric coordinates [1 - r - s, r, s] in the range [0, 1].

        Returns:
            Shape function values at the given coordinates ``[N1, N2, N3]``.
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

    @property
    def jacobian_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the Jacobian matrix for the Tri3 element.

        Returns:
            Jacobian matrix of the element.
        """
        return B_N @ np.array([self.x, self.y]).T

    @property
    def b_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the [B] matrix for the Tri3 element.

        [B] = ∇[N] = [J]⁻¹ [B_N]

        Returns:
            B matrix of the element.
        """
        return np.linalg.inv(self.jacobian_matrix) @ B_N

    def get_integration_scheme(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Get the integration scheme for the Tri3 element.

        Returns:
            Tuple of Gauss points and weights for numerical integration.
        """
        return gauss.gauss_points_weights_triangle(self.n_integration_points)

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

    print(f"{tri3_element.jacobian_matrix=}\n")
    print(f"{np.linalg.inv(tri3_element.jacobian_matrix)=}\n")
    print(f"{tri3_element.jacobian_determinant=}\n")
    # print(f"{tri3_element.B=}\n")
    # print(f"{tri3_element.b_matrix_jacobian()=}")


    # print(tri3_element)
    # print("Area:", tri3_element.area)
    print("Capacity Matrix:\n", tri3_element.get_capacity_matrix())
    print("Capacity Matrix:\n", tri3_element.get_conductivity_matrix())




