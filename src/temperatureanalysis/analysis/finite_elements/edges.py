from __future__ import annotations

from abc import ABC, abstractmethod

from typing import TYPE_CHECKING

import numpy as np

from temperatureanalysis.analysis.gauss import gauss_points_weights_edge
from temperatureanalysis.analysis.node import Node
import temperatureanalysis.analysis.gauss as gauss

if TYPE_CHECKING:
    import numpy.typing as npt

# TODO: Move these constants to a more appropriate location, such as a configuration file or a constants module.
CONVECTIVE_COEFFICIENT = 9.0 # W m^(-2) K^(-1) Convective heat transfer coefficient
STEFAN_BOLTZMANN = 5.67e-8  # W m^(-2) K^(-4) Stefan-Boltzmann constant, used for radiation heat transfer


class LineElement(ABC):
    """Abstract base class for edge elements in finite element analysis."""

    def __init__(
        self,
        index: int,
        tag: int,
        nodes: list[Node],
        number_of_integration_points: int,
    ) -> None:
        """
        Initialize the line element with an index, tag, and nodes.

        Args:
            index: Element index.
            tag: Element tag.
            nodes: List of nodes that form the element.
            number_of_integration_points: Number of integration points for numerical integration.
        """
        self.id = index
        self.tag = tag
        self.nodes = nodes
        self.number_of_integration_points = number_of_integration_points
        self.global_dofs: npt.NDArray[np.int64] = np.array([node.id for node in nodes], dtype=np.int64)

    def __repr__(self) -> str:
        """String representation of the line element."""
        return f"{self.__class__.__name__}(id={self.id}, tag={self.tag}, nodes={self.nodes})"

    @property
    def number_of_nodes(self) -> int:
        """Return the number of nodes in the edge element."""
        return len(self.nodes)

    @property
    def x(self) -> npt.NDArray[np.float64]:
        """Return the x-coordinates of the nodes in the edge element."""
        return np.array([node.x for node in self.nodes], dtype=np.float64)

    @property
    def y(self) -> npt.NDArray[np.float64]:
        """Return the y-coordinates of the nodes in the edge element."""
        return np.array([node.y for node in self.nodes], dtype=np.float64)

    @property
    def jacobian_determinant(self) -> npt.NDArray[np.float64]:
        """
        Calculate the Jacobian determinant of the edge element.

        Returns:
            The Jacobian determinant value.
        """
        return np.sqrt(np.sum(self.jacobian_matrix ** 2))

    @property
    def temperature_at_nodes(self) -> npt.NDArray[np.float64]:
        """
        Get the current temperature at each node of the edge element.

        Returns:
            Array of temperatures at the nodes.
        """
        return np.array([node.current_temperature for node in self.nodes], dtype=np.float64)

    @abstractmethod
    def shape_functions(self, iso_coord: float) -> npt.NDArray[np.float64]:
        """
        Calculate the shape functions for the line element at a given local coordinate.

        Args:
            iso_coord: Local coordinate in the range [-1, 1].

        Returns:
            Shape function values at the local coordinate.
        """
        pass

    @property
    @abstractmethod
    def jacobian_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the Jacobian of the line element at a given local coordinate.

        Returns:
            The Jacobian value at the local coordinate.
        """
        pass

    def get_integration_scheme(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Get the integration scheme for the line element.

        Returns:
            A tuple containing the integration points and weights.
        """
        return gauss.gauss_points_weights_edge(n_points=self.number_of_integration_points)

    def get_load_vector(self, temperature: float) -> npt.NDArray[np.float64]:
        """
        Calculate the load vector for the line element based on a given temperature.

        Args:
            temperature: Temperature value to be applied to the load vector.

        Returns:
            Load vector for the element.
        """
        alpha = CONVECTIVE_COEFFICIENT  # Convective heat transfer coefficient
        sigma = STEFAN_BOLTZMANN  # Stefan-Boltzmann constant

        f_e = np.zeros(self.number_of_nodes, dtype=np.float64)

        gauss_points, weights = self.get_integration_scheme()

        det_j = self.jacobian_determinant

        t_f = temperature # fire temperature

        for gp_i, w_i in zip(gauss_points, weights):
            # Calculate the shape functions at the integration point
            n_ei = self.shape_functions(iso_coord=gp_i)

            # Calculate the temperature at the integration point
            # t_i = np.sum(n_ei * temperature_at_nodes)
            t_i = n_ei @ self.temperature_at_nodes

            # Calculate the contribution to the load vector
            f_e += n_ei.T * (alpha * (t_i - t_f) + sigma * (t_i ** 4 - t_f ** 4)) * w_i * det_j

        return f_e

    def get_load_vector_tangent(self) -> npt.NDArray[np.float64]:
        """
        Compute the tangent matrix (df/dT) of this element’s nonlinear
        boundary load, for use in a Newton–Raphson method.

        Returns:
            Tangent load vector for the element.
        """
        alpha = CONVECTIVE_COEFFICIENT  # Convective heat transfer coefficient
        sigma = STEFAN_BOLTZMANN  # Stefan-Boltzmann constant

        df_dx_e = np.zeros((self.number_of_nodes, self.number_of_nodes), dtype=np.float64)

        gauss_points, weights = self.get_integration_scheme()

        det_j = self.jacobian_determinant

        for gp_i, w_i in zip(gauss_points, weights):
            # Calculate the shape functions at the integration point
            n_ei = self.shape_functions(iso_coord=gp_i)

            # Calculate the temperature at the integration point
            t_i = n_ei @ self.temperature_at_nodes

            outer_nn = np.outer(n_ei, n_ei)

            mat_factor = alpha + 4 * sigma * t_i ** 3

            # Calculate the contribution to the load vector
            df_dx_e += outer_nn * mat_factor * w_i * det_j

        return df_dx_e


class Line2(LineElement):
    """Linear line element with two nodes."""

    def __init__(self, index: int, tag: int, nodes: list[Node]) -> None:
        """
        Initialize the linear line element.

        Args:
            index: Element index.
            tag: Element tag.
            nodes: List of nodes that form the element.
        """
        super().__init__(index=index, tag=tag, nodes=nodes, number_of_integration_points=3)

    def shape_functions(self, iso_coord: float) -> npt.NDArray[np.float64]:
        """Shape functions for a linear line element."""
        return np.array([(1 - iso_coord) / 2, (1 + iso_coord) / 2], dtype=np.float64)

    @property
    def jacobian_matrix(self) -> npt.NDArray[np.float64]:
        """Jacobian for a linear line element."""
        b = np.array([-1/2, 1/2], dtype=np.float64)  # Derivative of shape functions w.r.t. local coordinate
        return b @ np.array([self.x, self.y]).T  # TODO: Check if this is correct for edges, as it might differ from area elements


if __name__ == "__main__":
    # Example usage of a Line2 element
    node1 = Node(index=1, coords=[0.0, 0.0])
    node2 = Node(index=2, coords=[0.1, 0.0])

    line_element = Line2(index=1, tag=101, nodes=[node1, node2])

    T = 50 + 273.15  # Example temperature in Kelvin

    print(line_element)
    print("Shape functions at iso_coord=0:", line_element.shape_functions(iso_coord=0))
    print("Shape functions at iso_coord=-1:", line_element.shape_functions(iso_coord=-1))
    print("Shape functions at iso_coord=1:", line_element.shape_functions(iso_coord=1))
    print("Jacobian matrix:", line_element.jacobian_matrix)
    print(f"Load vector for temperature {T}K:", line_element.get_load_vector(temperature=T))
    print(f"Load vector tangent for temperature {T}K:", line_element.get_load_vector_tangent())





