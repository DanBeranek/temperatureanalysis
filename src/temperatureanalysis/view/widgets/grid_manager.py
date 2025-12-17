"""
Grid Manager
Handles the dynamic 2D background grid and rulers.
"""
from typing import Callable, List, Optional
import numpy as np
import pyvista as pv
from vtkmodules.vtkRenderingCore import vtkTextActor


class GridManager:
    def __init__(self, plotter: pv.Plotter) -> None:
        self.plotter = plotter
        self.major_spacing: float = 0.5
        self.minor_spacing: float = 0.1
        self.label_formatter: Callable[[float], str] = lambda v: f"{v:g}"

        self._grid_major_actor: Optional[pv.Actor] = None
        self._grid_minor_actor: Optional[pv.Actor] = None
        self._ruler_actors: List[vtkTextActor] = []

    def update_grid_from_camera(self) -> None:
        """Re-calculates grid lines based on current zoom/pan."""
        if self.plotter is None: return

        bounds = self._grid_extend_from_camera(margin=0.25)

        grid_minor = self._build_xy_grid_polydata(bounds, spacing=self.minor_spacing)
        grid_major = self._build_xy_grid_polydata(bounds, spacing=self.major_spacing)

        if self._grid_minor_actor: self.plotter.remove_actor(self._grid_minor_actor)
        if self._grid_major_actor: self.plotter.remove_actor(self._grid_major_actor)

        self._grid_minor_actor = self.plotter.add_mesh(
            grid_minor, color="#E0E0E0", line_width=1, opacity=0.5, pickable=False
        )
        self._grid_major_actor = self.plotter.add_mesh(
            grid_major, color="#B0B0B0", line_width=1, opacity=0.8, pickable=False
        )

        self._axis_labels_edge(bounds, self.major_spacing)

    def _grid_extend_from_camera(self, margin: float = 0.25) -> tuple[float, float, float, float]:
        cam = self.plotter.camera
        cx, cy, _ = cam.focal_point
        half_h = float(cam.parallel_scale)

        w_px = int(self.plotter.interactor.width())
        h_px = int(self.plotter.interactor.height())
        aspect = w_px / h_px if h_px > 0 else 1.0
        half_w = half_h * aspect

        x0, x1 = cx - half_w, cx + half_w
        y0, y1 = cy - half_h, cy + half_h
        dx, dy = x1 - x0, y1 - y0
        return x0 - margin * dx, x1 + margin * dx, y0 - margin * dy, y1 + margin * dy

    @staticmethod
    def _build_xy_grid_polydata(bounds, spacing) -> pv.PolyData:
        """
        Create a grid in the XY plane with the given bounds and spacing.

        Args:
            bounds: (x_min, x_max, y_min, y_max)
            spacing: Grid spacing in both directions.

        Returns:
            A PyVista PolyData grid object.
        """
        x_min, x_max, y_min, y_max = bounds
        xs = np.arange(np.floor(x_min / spacing) * spacing, np.ceil(x_max / spacing) * spacing + spacing, spacing)
        ys = np.arange(np.floor(y_min / spacing) * spacing, np.ceil(y_max / spacing) * spacing + spacing, spacing)

        n_lines = len(xs) + len(ys)
        if n_lines == 0: return pv.PolyData()

        points = np.empty((n_lines * 2, 3), dtype=float)
        cells = np.empty(n_lines * 3, dtype=int)

        pid, cid = 0, 0
        for x in xs:
            points[pid] = (x, y_min, -0.1)
            points[pid + 1] = (x, y_max, -0.1)
            cells[cid:cid + 3] = (2, pid, pid + 1)
            pid += 2
            cid += 3
        for y in ys:
            points[pid] = (x_min, y, -0.1)
            points[pid + 1] = (x_max, y, -0.1)
            cells[cid:cid + 3] = (2, pid, pid + 1)
            pid += 2
            cid += 3

        return pv.PolyData(points, lines=cells)

    def _axis_labels_edge(self, bounds, spacing) -> None:
        """Return label positions and strings along X and Y axes (where they cross the other axis)."""
        for a in self._ruler_actors:
            self.plotter.renderer.RemoveActor2D(a)
        self._ruler_actors.clear()

        x_min, x_max, y_min, y_max = bounds
        xs = np.arange(np.floor(x_min / spacing) * spacing, np.ceil(x_max / spacing) * spacing + spacing, spacing)
        ys = np.arange(np.floor(y_min / spacing) * spacing, np.ceil(y_max / spacing) * spacing + spacing, spacing)

        pad = 6
        ren = self.plotter.renderer

        for x in xs:
            ren.SetWorldPoint(x, y_min, 0.0, 1.0)
            ren.WorldToDisplay()
            dx, dy, _ = ren.GetDisplayPoint()

            t = vtkTextActor()
            t.SetInput(self.label_formatter(x))
            t.GetTextProperty().SetColor(0, 0, 0)
            t.GetTextProperty().SetFontSize(12)
            t.SetDisplayPosition(int(dx), int(pad))
            ren.AddActor2D(t)
            self._ruler_actors.append(t)

        for y in ys:
            ren.SetWorldPoint(x_min, y, 0.0, 1.0)
            ren.WorldToDisplay()
            dx, dy, _ = ren.GetDisplayPoint()

            t = vtkTextActor()
            t.SetInput(self.label_formatter(y))
            t.GetTextProperty().SetColor(0, 0, 0)
            t.GetTextProperty().SetFontSize(12)
            t.SetDisplayPosition(int(pad), int(dy))
            ren.AddActor2D(t)
            self._ruler_actors.append(t)

    def clear_actors(self) -> None:
        """Clears all grid and ruler actors from the plotter."""
        if self._grid_minor_actor: self.plotter.remove_actor(self._grid_minor_actor)
        if self._grid_major_actor: self.plotter.remove_actor(self._grid_major_actor)
        for a in self._ruler_actors: self.plotter.renderer.RemoveActor2D(a)
        self._grid_minor_actor = None
        self._grid_major_actor = None
        self._ruler_actors.clear()
