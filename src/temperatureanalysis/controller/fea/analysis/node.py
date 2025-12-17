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
        self.uid = index
        self.global_dofs: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        self.current_temperature: float | None = 273.15 + 20.0
        self.temperature_history: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

    def __repr__(self) -> str:
        """String representation of the node."""
        return f"{self.__class__.__name__}(id={self.uid}, coords={self.coords})"

    @property
    def x(self) -> float:
        """X-coordinate of the node."""
        return self.coords[0]

    @property
    def y(self) -> float:
        """Y-coordinate of the node."""
        return self.coords[1]

    def plot_temperature_history(self, dt:float, name: str = "") -> None:
        """Plot the temperature history of the node."""
        import matplotlib.pyplot as plt

        if self.temperature_history.size == 0:
            print("No temperature history available to plot.")
            return

        plt.figure(figsize=(10, 5))
        time_steps = np.arange(len(self.temperature_history)) * dt / 60 # Convert to minutes
        plt.plot(time_steps, self.temperature_history - 273.15, marker='o')
        plt.title(f'Temperature History of Node {self.uid} ({name})')
        plt.xlabel('Time (minutes)')
        plt.ylabel('Temperature (°C)')
        plt.grid(True)
        plt.show()
