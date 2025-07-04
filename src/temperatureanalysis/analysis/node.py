from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


class Node:
    """
    Represents a node in a temperature analysis simulation.
    """
    def __init__(
        self,
        index: int,
        coords: list[float] | npt.NDArray[np.float64],
    ) -> None:
        """
        Initialize the node with coordinates.

        Args:
            coords: Coordinates of the node in the global system [X, Y].
        """
        self.coords = np.array(coords, dtype=np.float64)
        self.id = index
        self.global_dofs: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        self.initial_temperature: float | None = 273.15 + 20.0 # TODO: Should the temperature be an argument?
        self.current_temperature: float | None = 273.15 + 20.0

    @property
    def x(self) -> float:
        """X-coordinate of the node."""
        return self.coords[0]

    @property
    def y(self) -> float:
        """Y-coordinate of the node."""
        return self.coords[1]
