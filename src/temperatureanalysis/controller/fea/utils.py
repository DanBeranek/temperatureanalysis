from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


ABSOLUTE_ZERO_CELSIUS = -273.15

def celsius_to_kelvin(celsius: float) -> float:
    """Convert Celsius to Kelvin."""
    return celsius - ABSOLUTE_ZERO_CELSIUS

def kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to Celsius."""
    return kelvin + ABSOLUTE_ZERO_CELSIUS

def assemble_subarray_at_indices(
    array: npt.NDArray[np.float64],
    subarray: npt.NDArray[np.float64],
    indices: list[int],
) -> None:
    """
    Insert a subarray into a specified position within a larger array, identified by indices.

    This method modifies the larger array in-place, adding the values from the subarray to the
    elements of the array at the specified indices.

    :var array: The larger array to which the subarray will be added. This array is modified in-place.
    :var subarray: A smaller (n x n) array whose values are to be inserted into the larger array.
    :var indices: A list of integer indices specifying the rows and columns in the larger array
                  where the subarray's values should be added. The indices correspond to the positions
                  in the larger array.

    :return: None. The operation modifies the 'array' argument in-place.

    **Example**:

        large_array = np.zeros((4, 4))
        small_array = np.array([[1, 2], [3, 4]])
        indices = [1, 2]
        assemble_subarray_at_indices(large_array, small_array, indices)
        print(large_array)
        # Output:
        # [[0. 0. 0. 0.]
        # [0. 1. 2. 0.]
        # [0. 3. 4. 0.]
        # [0. 0. 0. 0.]]
    """
    # Split the indices into row and column lists
    rows, cols = zip(*[(i, j) for i in indices for j in indices])
    # Assemble values using indexing
    array[rows, cols] += subarray.flatten()

def flatten_groups_in_order(groups: dict[str, list]) -> list:
    """Deterministic flatten of dict-of-lists (sorted by key)."""
    out: list = []
    for k in sorted(groups.keys()):
        out.extend(groups[k])
    return out
