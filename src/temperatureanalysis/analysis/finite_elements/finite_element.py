from __future__ import annotations

from abc import ABC, abstractmethod, abstractproperty

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.pre.material import Material
    from temperatureanalysis.analysis.node import Node


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
        self.globals_dofs: npt.NDArray[np.int64] = np.array([node.id for node in nodes], dtype=np.int64)

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

    @abstractmethod
    def b_matrix_jacobian(self) -> tuple[npt.NDArray[np.float64], float]:
        """Calculate the B matrix and its Jacobian for the finite element."""
        pass

    @abstractmethod
    def get_conductivity_matrix(self) -> npt.NDArray[np.float64]:
        """Calculate the conductivity matrix [K] for the finite element."""
        pass

    @abstractmethod
    def get_capacity_matrix(self) -> npt.NDArray[np.float64]:
        """Calculate the capacity matrix [C] for the finite element."""
        pass


    # @abstractmethod
    # def jacobian(self, xi: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    #     """Calculate the Jacobian matrix at given local coordinates."""
    #     pass
