from __future__ import annotations

from abc import ABC, abstractmethod

from typing import TYPE_CHECKING

import numpy as np

import temperatureanalysis.fea.analysis.gauss as gauss

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.fea.pre.material import Material
    from temperatureanalysis.fea.analysis.node import Node


class FiniteElement(ABC):
    """
    Abstract base class for finite elements in temperature analysis.
    """

    def __init__(
        self,
        index: int,
        tag: str,
        nodes: list[Node],
        material: Material,
        n_integration_points: int
    ) -> None:
        """
        Initialize the finite element with an index and a tag.

        Args:
            index: Element index.
            tag: Element tag.
            nodes: List of nodes.
            material: The material associated with the element.
            n_integration_points: Number of integration points for numerical integration.
        """
        self.id = index
        self.tag = tag
        self.material = material
        self.nodes = nodes
        self.n_integration_points = n_integration_points
        self.global_dofs: npt.NDArray[np.int64] = np.array([node.uid for node in nodes], dtype=np.int64)

        self.x = np.array([node.coords[0] for node in nodes], dtype=np.float64)
        self.y = np.array([node.coords[1] for node in nodes], dtype=np.float64)

    def __repr__(self) -> str:
        """String representation of the finite element."""
        return f"{self.__class__.__name__}(id={self.id}, tag='{self.tag}', material={self.material.name})"

    @property
    def number_of_nodes(self) -> int:
        """Number of nodes in the finite element."""
        return len(self.nodes)

    @staticmethod
    @abstractmethod
    def shape_functions(iso_coords: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Calculate the shape function at given local coordinates."""
        pass

    @abstractmethod
    def area(self) -> float:
        """Calculate the area of the finite element."""
        pass

    @property
    def jacobian_determinant(self) -> float:
        """
        Calculate the determinant of the Jacobian matrix for the element.

        Returns:
            Determinant of the Jacobian matrix.
        """
        return np.linalg.det(self.jacobian_matrix)

    @property
    def temperature_at_nodes(self) -> npt.NDArray[np.float64]:
        """
        Get the current temperature at each node of the edge element.

        Returns:
            Array of temperatures at the nodes.
        """
        return np.array([node.current_temperature for node in self.nodes], dtype=np.float64)

    @abstractmethod
    def get_integration_scheme(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Get the integration scheme for the finite element.

        Returns:
            Tuple of Gauss points and weights for numerical integration.
        """
        pass

    @abstractmethod
    def jacobian_matrix(self) -> npt.NDArray[np.float64]:
        """Calculate the Jacobian matrix for the element.

        Returns:
            Jacobian matrix of the element.
        """
        pass

    @abstractmethod
    def b_matrix(self) -> npt.NDArray[np.float64]:
        """Calculate the [B] matrix for the finite element."""
        pass

    def get_conductivity_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the conductivity matrix [K] for the finite element.

        Returns:
            Conductivity matrix for the element.
        """
        k_e = np.zeros((self.number_of_nodes, self.number_of_nodes), dtype=np.float64)

        gauss_points, weights = self.get_integration_scheme()

        b_e = self.b_matrix
        det_j = self.jacobian_determinant

        for gp_i, w_i in zip(gauss_points, weights):
            # Calculate the shape functions at the integration point
            n_ei = self.shape_functions(iso_coords=gp_i)

            # Calculate the temperature at the integration point
            t_i = n_ei @ self.temperature_at_nodes
            # t_i = np.sum(n_ei * temperature_at_nodes)

            # Calculate the thermal conductivity at the integration point
            lambda_ci = self.material.thermal_conductivity(temperature_K=t_i)

            k_e += b_e.T @ b_e * det_j * lambda_ci * w_i

        return k_e

    def get_capacity_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the capacity matrix [C] of the finite element.

        Returns:
            Capacity matrix of the element.
        """
        c_e = np.zeros((self.number_of_nodes, self.number_of_nodes), dtype=np.float64)

        gauss_points, weights = gauss.gauss_points_weights_triangle(self.n_integration_points)

        det_j = self.jacobian_determinant

        for gp_i, w_i in zip(gauss_points, weights):
            # Calculate the shape functions at the integration point
            n_ei = self.shape_functions(iso_coords=gp_i)

            # Calculate the temperature at the integration point
            # t_i = np.sum(n_ei * t_at_nodes)
            t_i = n_ei @ self.temperature_at_nodes

            # Calculate the density and specific heat capacity at the integration point
            rho_ci = self.material.density(temperature_K=t_i)
            c_pi = self.material.specific_heat_capacity(temperature_K=t_i)

            # Calculate the contribution to the capacity matrix
            c_e += det_j * n_ei.T @ n_ei * rho_ci * c_pi * w_i

        return c_e

