from __future__ import annotations

from abc import ABC, abstractmethod

from typing import TYPE_CHECKING

import numpy as np

from temperatureanalysis.analysis.node import Node

if TYPE_CHECKING:
    import numpy.typing as npt


class EdgeElement(ABC):
    """Abstract base class for line elements in finite element analysis."""

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

    @abstractmethod
    def shape_functions(self, iso_coord: float) -> npt.NDArray[np.float64]:
        """
        Calculate the shape functions for the line element at a given local coordinate.

        Args:
            iso_coord: Local coordinate in the range [0, 1].

        Returns:
            Shape function values at the local coordinate.
        """
        pass

    @abstractmethod
    def jacobian(self, iso_coord: float) -> float:
        """
        Calculate the Jacobian of the line element at a given local coordinate.

        Args:
            iso_coord: Local coordinate in the range [0, 1].

        Returns:
            The Jacobian value at the local coordinate.
        """
        pass

    def get_load_vector(self, temperature: float) -> npt.NDArray[np.float64]:
        pass



