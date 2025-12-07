"""
VTK and Geometry Utilities
Helper functions for polygon triangulation and data conversion.
"""
import numpy as np
import numpy.typing as npt
import pyvista as pv
from vtkmodules.vtkFiltersGeneral import vtkContourTriangulator

import logging

from temperatureanalysis.model.geometry_primitives import BoundaryLoop

logger = logging.getLogger(__name__)

class VtkUtils:
    @staticmethod
    def discretize_loop_to_array(loop: BoundaryLoop) -> npt.NDArray[np.float64]:
        """
        Converts the Geometric Primitives (Lines/Arcs) into a dense (N, 2) XY array.
        """
        points_list = []
        for entity in loop.entities:
            # entity.discretize() returns [Start, ..., End]
            pts = entity.discretize()

            # Skip the last point to avoid duplicates with the next segment's start point
            for p in pts[:-1]:
                points_list.append([p[0], p[1]])

        # Add the final closing point of the loop
        if loop.entities:
            last_p = loop.entities[-1].discretize()[-1]
            points_list.append([last_p[0], last_p[1]])

        return np.array(points_list, dtype=np.float64)

    @staticmethod
    def as_closed_xy(a: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Ensure the polyline is closed by repeating the first point at the end if necessary.

        Args:
            a: List of (x, y) tuples or (N, 2) array of points.

        Returns:
            (N, 2) array of points with the first point repeated at the end if needed.

        Raises:
            ValueError: If the input is not of shape (N, 2).
        """
        arr = np.asarray(a, dtype=np.float64).reshape(-1, 2)

        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError(f"Expected shape (N, 2), got {arr.shape}.")

        if not np.allclose(arr[0], arr[-1]):
            arr = np.vstack([arr, arr[0]])

        return arr

    @staticmethod
    def clean_duplicate_points(points: npt.NDArray[np.float64], tol: float = 1e-5) -> npt.NDArray[np.float64]:
        """
        Removes consecutive points that are too close to each other.
        This is crucial for vtkContourTriangulator stability.
        """
        if len(points) < 3:
            return points

        # Calculate Euclidean distance between consecutive points
        diff = points[1:] - points[:-1]
        dist = np.linalg.norm(diff, axis=1)

        # Keep the first point, and any point that is far enough from the previous one
        mask = np.concatenate(([True], dist > tol))

        cleaned = points[mask]

        # Check closure: Ensure last point is not duplicate of first
        if len(cleaned) > 2:
            if np.linalg.norm(cleaned[-1] - cleaned[0]) < tol:
                cleaned = cleaned[:-1]

        return cleaned

    @staticmethod
    def polyline_to_polydata(ring: npt.NDArray[np.float64]) -> pv.PolyData:
        """Convert a (N, 2) array of points to a PolyData line."""
        ring = np.asarray(ring, dtype=np.float64).reshape(-1, 2)
        n = ring.shape[0]
        pts3 = np.c_[ring, np.zeros((n, 1), dtype=np.float64)]
        pd = pv.PolyData(pts3)
        pd.lines = np.hstack([[n], np.arange(n, dtype=np.int_)])
        return pd

    def triangulate_loops_xy(self, loops: list[npt.NDArray[np.float64]]) -> pv.PolyData:
        """
        Triangulate multiple closed loops (first = outer, rest = holes) on Z=0.

        Args:
            loops: List of (N, 2) arrays of (x, y) points. Each loop should be closed.
                   Assuming loops are clear and non-self-intersecting.

        Returns:
            PolyData: Triangulated loops.
        """
        if not loops:
            return pv.PolyData()

        pts3_list: list[npt.NDArray[np.float64]] = []
        cells_list: list[npt.NDArray[np.int_]] = []
        offset = 0

        for ring in loops:
            # 1. Ensure format
            ring = np.asarray(ring, dtype=np.float64).reshape(-1, 2)
            if ring.size == 0:
                continue

            # 2. Clean Data (Remove microscopic segments)
            ring = self.clean_duplicate_points(ring)
            if len(ring) < 3:
                return pv.PolyData()

            # 3. Ensure closed for PolyData creation
            if not np.allclose(ring[0], ring[-1]):
                ring = np.vstack([ring, ring[0]])

            n = ring.shape[0]
            pts3 = np.c_[ring, np.zeros((n, 1), dtype=np.float64)]  # (N, 3)
            pts3_list.append(pts3)

            # polyline cell: [n, id0, id1, ..., id(n-1)]
            cells = np.hstack([[n], np.arange(offset, offset + n, dtype=np.int_)])
            cells_list.append(cells)

            offset += n

        if not pts3_list:
            return pv.PolyData()

        points = np.vstack(pts3_list)
        lines = np.concatenate(cells_list).astype(np.int_)

        pd = pv.PolyData(points)
        pd.lines = lines

        try:
            tri = vtkContourTriangulator()
            tri.SetInputData(pd)
            tri.Update()
            return pv.wrap(tri.GetOutput())
        except Exception as e:
            logger.error(f"Triangulation failed: {e}")
            return pv.PolyData()
