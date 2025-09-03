from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numba as nb

from temperatureanalysis.fea.analysis.finite_elements.finite_element import FiniteElement
import temperatureanalysis.fea.analysis.gauss as gauss

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.fea.analysis.node import Node
    from temperatureanalysis.fea.pre.material import Material


# B_N = [
#   [dN1(r,s)/dr, dN2(r,s)/dr, dN3(r,s)/dr],
#   [dN1(r,s)/ds, dN2(r,s)/ds, dN3(r,s)/ds]
# ]
B_N = np.array([
    [-1.0, 1.0, 0.0],
    [-1.0, 0.0, 1.0],
])


@nb.jit(cache=True, fastmath=True)
def _inv2(
    a11: float,
    a12: float,
    a21: float,
    a22: float
) -> tuple[tuple[float, float, float, float], float]:
    """
    Compute the inverse and determinant of a 2×2 matrix [[a11, a12], [a21, a22]].

    Args:
        a11, a12, a21, a22: Elements of the 2x2 matrix.

    Returns:
        A tuple containing the elements of the inverse matrix and the determinant.
    """
    det = a11 * a22 - a12 * a21
    inv = (a22 / det, -a12 / det, -a21 / det, a11 / det)
    return inv, det

@nb.jit(cache=True, fastmath=True)
def _tri3_B_and_detJ(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], float]:
    """
    Build the constant B matrix and |det(J)| for a Tri3 element.

    Args:
        x: (3, ) array of x-coordinates of the element's nodes.
        y: (3, ) array of y-coordinates of the element's nodes.

    Returns:
        B: (2, 3) array representing the B matrix.
        detJ_abs: Absolute value of the Jacobian determinant.
    """
    # J = B_N @ [[x], [y]].T
    J00 = B_N[0, 0] * x[0] + B_N[0, 1] * x[1] + B_N[0, 2] * x[2]
    J01 = B_N[0, 0] * y[0] + B_N[0, 1] * y[1] + B_N[0, 2] * y[2]
    J10 = B_N[1, 0] * x[0] + B_N[1, 1] * x[1] + B_N[1, 2] * x[2]
    J11 = B_N[1, 0] * y[0] + B_N[1, 1] * y[1] + B_N[1, 2] * y[2]

    (i00, i01, i10, i11), detJ = _inv2(J00, J01, J10, J11)

    # B = inv(J) @ B_N
    B = np.empty((2, 3), dtype=np.float64)
    for j in range(3):
        b0, b1 = B_N[0, j], B_N[1, j]
        B[0, j] = i00 * b0 + i01 * b1
        B[1, j] = i10 * b0 + i11 * b1

    return B, abs(detJ)

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

        self._B, self._detJ = _tri3_B_and_detJ(self.x, self.y)
        self._gp, self._w = gauss.gauss_points_weights_triangle(self.n_integration_points)


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

    @property
    def jacobian_determinant(self) -> float:
        """
        Absolute Jacobian determinant (constant for Tri3).

        Returns:
            |det(J)|
        """
        return self._detJ

    def get_integration_scheme(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Return cached Gauss points and weights for 3-point triangle rule.

        Returns:
            Tuple of Gauss points and weights for numerical integration.
        """
        return self._gp, self._w

    def get_conductivity_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate element conductivity matrix [K] = ∑ (Bᵀ B * k(T_gp) * |detJ| * w).

        Uses:
            - Cached B matrix (constant for Tri3)
            - Material thermal conductivity at integration points
            - Jacobian determinant (constant for Tri3)
            - Integration weights

        Returns:
            (3, 3) conductivity matrix for Tri3.
        """
        B = self._B
        detJ = self._detJ
        Tn = self.temperature_at_nodes

        # Temperatures at gauss points
        Tgp = np.empty(3, dtype=np.float64)
        for i, (gp_i, _) in enumerate(zip(self._gp, self._w)):
            N = self.shape_functions(gp_i)  # (1, 3)
            Tgp[i] = float(N @ Tn)  # (1, 3) @ (3,) -> (1,)

        # thermal conductivity at the integration points
        if hasattr(self.material, "props_batch"):
            k_gp, _ = self.material.props_batch(Tgp)
        else:
            k_gp = np.array([self.material.thermal_conductivity(t) for t in Tgp], dtype=np.float64)

        # Accumulate scalar factor ∑ k_i * w_i
        k_weight_sum = float(np.dot(k_gp, self._w))

        BtB = B.T @ B
        return BtB * (detJ * k_weight_sum)

    def get_capacity_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate element capacity matrix [C] = ∑ (Nᵀ N * c(T_gp) * ρ(T_gp) * |detJ| * w).

        Uses:
            - Material specific heat capacity and density at integration points
            - Jacobian determinant (constant for Tri3)
            - Integration weights

        Returns:
            (3, 3) capacity matrix for Tri3.
        """
        detJ = self._detJ
        Tn = self.temperature_at_nodes

        # Temperatures at gauss points and keep N at each point
        Tgp = np.empty(3, dtype=np.float64)
        N_store: list[npt.NDArray[np.float64]] = []
        for i, (gp_i, _) in enumerate(zip(self._gp, self._w)):
            N = self.shape_functions(gp_i)  # (1, 3)
            N_store.append(N)
            Tgp[i] = float(N @ Tn)  # (1, 3) @ (3,) -> (1,)

        if hasattr(self.material, "props_batch"):
            _, rho_c_gp = self.material.props_batch(Tgp)
        else:
            rho_c_gp = np.array(
                [self.material.density(t) * self.material.specific_heat_capacity(t) for t in Tgp],
                dtype=np.float64
            )

        C = np.zeros((3, 3), dtype=np.float64)
        for i, (_, w_i) in enumerate(zip(self._gp, self._w)):
            N = N_store[i]
            C += (N.T @ N) * (rho_c_gp[i] * detJ * w_i)

        return C



if __name__ == "__main__":
    # Example usage
    from temperatureanalysis.fea.analysis.node import Node
    from temperatureanalysis.fea.pre.material import Concrete

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




