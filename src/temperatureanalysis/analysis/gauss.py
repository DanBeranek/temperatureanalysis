from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


def gauss_points_weights_edge(n_points: int) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Generate Gauss points and weights for a 1D Gaussian integration.

    Args:
        n_points: Number of integration points.

    Raises:
        ValueError: If `n_points` is not 1, 2, or 3.

    Returns:
        A tuple containing the Gauss points and weights.
    """
    if n_points == 1:
        return np.array([0.0]), np.array([2.0])
    elif n_points == 2:
        return np.array([-1/np.sqrt(3), 1/np.sqrt(3)]), np.array([1.0, 1.0])
    elif n_points == 3:
        return np.array([-np.sqrt(3/5), 0.0, np.sqrt(3/5)]), np.array([5/9, 8/9, 5/9])
    else:
        raise ValueError(f"Unsupported number of Gauss points: {n_points}. "
                         f"'n_points' must be 1, 2, or 3.")


def gauss_points_weights_triangle(n_points: int) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Generate Gauss points and weights for a triangular Gaussian integration.

    Args:
        n_points: Number of integration points.

    Raises:
        ValueError: If `n_points` is not 1 or 3.

    Returns:
        A tuple containing the Gauss points and weights.
    """
    if n_points == 1:
        return np.array([[1.0/3.0, 1.0/3.0, 1.0/3.0]]), np.array([1.0])
    elif n_points == 3:
        return np.array([
            [2.0/3.0, 1.0/6.0, 1.0/6.0],
            [1.0/6.0, 2.0/3.0, 1.0/6.0],
            [1.0/6.0, 1.0/6.0, 2.0/3.0]]
        ), np.array([1.0/3.0, 1.0/3.0, 1.0/3.0])
    else:
        raise ValueError(f"Unsupported number of Gauss points: {n_points}. "
                         f"'n_points' must be 1 or 3.")
