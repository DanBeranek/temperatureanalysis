from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict, TYPE_CHECKING

import numpy as np
import pyvista as pv
from PySide6.QtCore import QTimer
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QWidget, QVBoxLayout
from vtkmodules.vtkFiltersGeneral import vtkContourTriangulator
from vtkmodules.vtkRenderingCore import vtkTextActor

if TYPE_CHECKING:
    import numpy.typing as npt

# -------------------------------------------------------------------------------
# Data model
# -------------------------------------------------------------------------------

@dataclass
class PreviewDomain:
    """
    A domain consisting of one filled regions (with holes).
    """
    name: str  # unique name
    label: str  # user-displayed label
    outer: npt.NDArray[np.float64]
    holes: list[npt.NDArray[np.float64]] = field(default_factory=list)

    fill_color: str | tuple[float, float, float] = "#A0C4FF"
    edge_color: str | tuple[float, float, float] = "black"
    edge_width: float = 1.0
    opacity: float = 1.0

# -------------------------------------------------------------------------------
# Preview widget
# -------------------------------------------------------------------------------

class Preview2D(QWidget):
    """
    PyVista/Qt preview for 2D geometry_editors with:
      - locked orthographic XY camera (pan/zoom only),
      - user-defined major/minor grid spacings,
      - edge (bottom/left) labels on major ticks,
      - multiple domains with (holes supported),
      - optional outlines per material,
      - small legend.
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.plotter: QtInteractor | None = None
        self._init_plotter()
        layout.addWidget(self.plotter.interactor)

        # grid config
        self._major_spacing: float = 1.0
        self._minor_spacing: float = 0.25
        self._label_formatter = lambda v: f"{v:g}"

        # actors state
        self._grid_major_actor: pv.Actor | None = None
        self._grid_minor_actor: pv.Actor | None = None
        self._ruler_actors: list[vtkTextActor] = []
        self._preview_domain_actors: dict[str, pv.Actor] = {}
        self._preview_edge_actors: dict[str, pv.Actor] = {}
        # self._legend_actors: list[vtkTextActor] = []


        # cache for regrid
        self._last_bounds: tuple[float, float, float, float] | None = None
        self._last_camera_signature: tuple[float, float, float, int, int] | None = None

        # lock interaction & regrid on interaction/resize
        self._configure_2d_mode()
        self._attach_observers()

        # init debounce timer
        self._regrid_timer = QTimer(self)
        self._regrid_timer.setSingleShot(True)
        self._regrid_timer.setInterval(100)
        self._regrid_timer.timeout.connect(self._regrid_if_changed)

    # ------------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------------

    def set_grid_spacing(self, major: float, minor: float) -> None:
        """Set the major and minor grid spacing in world units."""
        self._major_spacing = major
        self._minor_spacing = minor
        self._update_grid_from_camera()
        self.plotter.render()

    def set_label_formatter(self, fmt: callable[[float], str]) -> None:
        """
        Set a callable number->string to format tick labels.

        Examples:
            - preview.set_label_formatter(lambda v: f"{v:g}")
            - preview.set_label_formatter(lambda v: f"{v:.2f} m")
            - preview.set_label_formatter(lambda v: f"{v*1000:.0f} mm")
        """
        self._label_formatter = fmt
        self._update_grid_from_camera()
        self.plotter.render()

    def set_preview(self, domains: list[PreviewDomain]) -> None:
        """
        Render the given material domains with filled regions.
        """
        self._clear_preview()

        allpts: list[npt.NDArray[np.float64]] = []

        for domain in domains:
            # Filled domain via triangulation
            loops = [self._as_closed_xy(domain.outer)] + [self._as_closed_xy(hole) for hole in domain.holes]
            tri_pd = self._triangulate_loops_xy(loops)
            if tri_pd.n_cells > 0:
                act_fill = self.plotter.add_mesh(
                    tri_pd,
                    color=domain.fill_color,
                    opacity=domain.opacity,
                    pickable=True,
                    show_scalar_bar=False
                )
                self._preview_domain_actors[domain.name] = act_fill
                allpts.append(tri_pd.points[:, :2])

            # optional crisp edges around the region (outer + holes)
            for i, ring in enumerate(loops):
                edge_pd = self._polyline_to_polydata(ring)

                # remove vertex cells, so they don't show up as dots
                edge_pd.verts = np.empty(0, np.int32)

                act_edge = self.plotter.add_mesh(
                    edge_pd,
                    color=domain.edge_color,
                    line_width=domain.edge_width,
                    pickable=False,
                    show_scalar_bar=False,
                )
                self._preview_edge_actors[f"{domain.name}-edge-{i}"] = act_edge
                allpts.append(ring)

        if allpts:
            self._fit_camera_to_points(np.vstack(allpts))

        self._update_grid_from_camera()
        # self._draw_legend(domains)
        self.plotter.render()

    # ------------------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------------------

    # ---- plotter / interaction ----

    def _init_plotter(self) -> None:
        """Lazy initialization of the plotter."""
        if self.plotter is not None:
            return
        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")
        self.plotter.render_lines_as_tubes = True

    def _configure_2d_mode(self) -> None:
        """Lock to 2D XY with orthographic camera and pan/zoom only."""
        self.plotter.enable_parallel_projection()
        self.plotter.view_xy()
        self.plotter.enable_image_style()

    def _attach_observers(self) -> None:
        """Recompute grid/labels after interaction or resize."""
        iren = self.plotter.iren
        iren.add_observer("EndInteractionEvent", lambda *_: self._schedule_regrid())
        iren.add_observer("MouseWheelForwardEvent", lambda *_: self._schedule_regrid())
        iren.add_observer("MouseWheelBackwardEvent", lambda *_: self._schedule_regrid())
        iren.add_observer("ConfigureEvent", lambda *_: self._schedule_regrid())

    def _schedule_regrid(self) -> None:
        self._regrid_timer.start()

    def _camera_signature(self) -> tuple[float, float, float, int, int]:
        """A simple signature of the current camera view to detect changes."""
        cam = self.plotter.camera
        w = int(self.plotter.interactor.width())
        h = int(self.plotter.interactor.height())
        return (
            round(cam.focal_point[0], 9),
            round(cam.focal_point[1], 9),
            round(cam.parallel_scale, 9),
            w,
            h
        )

    def _is_view_ready(self) -> bool:
        """Check if the camera and viewport are properly initialized."""
        if self.plotter is None or self.plotter.renderer is None:
            return False
        w = int(self.plotter.interactor.width())
        h = int(self.plotter.interactor.height())
        return w > 1 and h > 1

    def _regrid_if_changed(self) -> None:
        """Recompute the grid and labels if the camera view has changed."""
        if not self._is_view_ready():
            return
        new_sig = self._camera_signature()
        if new_sig == self._last_camera_signature:
            return
        self._last_camera_signature = new_sig
        self._update_grid_from_camera()
        self.plotter.render()

    # ---- math helpers ----

    @staticmethod
    def _as_closed_xy(a: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
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
    def _polyline_to_polydata(ring: npt.NDArray[np.float64]) -> pv.PolyData:
        """Convert a (N, 2) array of points"""
        ring = np.asarray(ring, dtype=np.float64).reshape(-1, 2)
        n = ring.shape[0]
        pts3 = np.c_[ring, np.zeros((n, 1), dtype=np.float64)]  # (N, 3)
        pd = pv.PolyData(pts3)
        pd.lines = np.hstack([[n], np.arange(n, dtype=np.int_)])
        return pd

    def _viewport_size_px(self) -> tuple[int, int]:
        w = int(self.plotter.interactor.width())
        h = int(self.plotter.interactor.height())
        return max(1, w), max(1, h)

    def _visible_world_bounds(self) -> tuple[float, float, float, float]:
        """
        Compute visible XY bounds using orthographic camera parameters.

        parallel_scale is half the vertical size of the viewport in world units.
        """
        camera = self.plotter.camera
        cx, cy, _ = camera.focal_point
        half_h = float(camera.parallel_scale)
        w_px, h_px = self._viewport_size_px()
        aspect = w_px / h_px if h_px else 1.0
        half_w = half_h * aspect
        return cx - half_w, cx + half_w, cy - half_h, cy + half_h

    def _fit_camera_to_points(self, pts2d: npt.NDArray[np.float64], margin: float = 0.25) -> None:
        x_min, y_min = pts2d.min(axis=0)
        x_max, y_max = pts2d.max(axis=0)
        cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
        dx, dy = max(1e-6, x_max - x_min), max(1e-6, y_max - y_min)
        self.plotter.view_xy()
        cam = self.plotter.camera
        cam.position = (cx, cy, 1.0)
        cam.focal_point = (cx, cy, 0.0)
        cam.up = (0.0, 1.0, 0.0)
        cam.parallel_scale = 0.5 * (1.0 + margin) * max(dx, dy)
        self.plotter.reset_camera_clipping_range()

    def _grid_extend_from_camera(self, margin: float = 0.25) -> tuple[float, float, float, float]:
        x0, x1, y0, y1 = self._visible_world_bounds()
        dx, dy = x1 - x0, y1 - y0
        return x0 - margin * dx, x1 + margin * dx, y0 - margin * dy, y1 + margin * dy

    # ---- grid and labels ----

    @staticmethod
    def _build_xy_grid_polydata(
        bounds: tuple[float, float, float, float],
        spacing: float = 1.0
    ) -> pv.PolyData:
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

        # Preallocate points and line cells: each line has 2 points and a [2, i, j] cell
        n_lines = len(xs) + len(ys)
        points = np.empty((n_lines * 2, 3), dtype=float)
        cells = np.empty(n_lines * 3, dtype=int)  # [2, id0, id1] repeated

        pid = 0
        cid = 0
        # verticals
        for x in xs:
            points[pid] = (x, y_min, -0.1)
            points[pid + 1] = (x, y_max, -0.1)
            cells[cid:cid + 3] = (2, pid, pid + 1)
            pid += 2
            cid += 3
        # horizontals
        for y in ys:
            points[pid] = (x_min, y, -0.1)
            points[pid + 1] = (x_max, y, -0.1)
            cells[cid:cid + 3] = (2, pid, pid + 1)
            pid += 2
            cid += 3

        return pv.PolyData(points, lines=cells)

    def _clear_ruler_labels(self) -> None:
        for actor in self._ruler_actors:
            try:
                self.plotter.renderer.RemoveActor2D(actor)
            except Exception:
                pass
        self._ruler_actors.clear()

    def _world_to_display(self, x: float, y: float) -> tuple[float, float]:
        ren = self.plotter.renderer
        ren.SetWorldPoint(x, y, 0.0, 1.0)
        ren.WorldToDisplay()
        dx, dy, _ = ren.GetDisplayPoint()
        return float(dx), float(dy)

    def _axis_labels_edge(self, bounds: tuple[float, float, float, float], spacing: float = 1.0) -> None:
        """Return label positions and strings along X and Y axes (where they cross the other axis)."""
        self._clear_ruler_labels()

        if spacing < 0:
            return

        x_min, x_max, y_min, y_max = bounds
        xs = np.arange(np.floor(x_min / spacing) * spacing, np.ceil(x_max / spacing) * spacing + spacing, spacing)
        ys = np.arange(np.floor(y_min / spacing) * spacing, np.ceil(y_max / spacing) * spacing + spacing, spacing)
        pad = 6  # px inset

        # Bottom edge (X labels at y = y_min)
        for x in xs:
            dx, _ = self._world_to_display(x, y_min)
            t = vtkTextActor()
            t.SetInput(self._label_formatter(x))
            tp = t.GetTextProperty()
            tp.SetFontSize(12)
            tp.SetColor(0, 0, 0)
            tp.SetBackgroundColor(1.0, 1.0, 1.0)
            tp.SetBackgroundOpacity(0.7)
            tp.BoldOff()
            tp.ShadowOff()
            t.SetDisplayPosition(int(dx - 10), int(pad))
            self.plotter.renderer.AddActor2D(t)
            self._ruler_actors.append(t)

        # Left edge (Y labels at x = x_min)
        for y in ys:
            _, dy = self._world_to_display(x_min, y)
            t = vtkTextActor()
            t.SetInput(self._label_formatter(y))
            tp = t.GetTextProperty()
            tp.SetFontSize(12)
            tp.SetColor(0, 0, 0)
            tp.SetBackgroundColor(1.0, 1.0, 1.0)
            tp.SetBackgroundOpacity(0.7)
            tp.BoldOff()
            tp.ShadowOff()
            t.SetDisplayPosition(int(pad), int(dy - 6))
            self.plotter.renderer.AddActor2D(t)
            self._ruler_actors.append(t)

    def _update_grid_from_camera(self) -> None:
        if self.plotter is None:
            return

        bounds = self._grid_extend_from_camera(margin=0.25)
        self._last_bounds = bounds

        # rebuild minor/major grid
        grid_minor = self._build_xy_grid_polydata(bounds, spacing=self._minor_spacing)
        grid_major = self._build_xy_grid_polydata(bounds, spacing=self._major_spacing)

        # replace grid actors
        if self._grid_minor_actor is not None:
            try: self.plotter.remove_actor(self._grid_minor_actor)
            except Exception: pass
        if self._grid_major_actor is not None:
            try: self.plotter.remove_actor(self._grid_major_actor)
            except Exception: pass

        self._grid_minor_actor = self.plotter.add_mesh(
            grid_minor, color="#C8C8C8", line_width=1, opacity=0.6, pickable=False
        )
        self._grid_major_actor = self.plotter.add_mesh(
            grid_major, color="#808080", line_width=2, opacity=0.9, pickable=False
        )

        self._axis_labels_edge(bounds, self._major_spacing)

    # ---- legend ----

    # def _clear_legend(self) -> None:
    #     for actor in self._legend_actors:
    #         try:
    #             self.plotter.renderer.RemoveActor2D(actor)
    #         except Exception:
    #             pass
    #     self._legend_actors.clear()
    #
    # def _draw_legend(self, domains: list[PreviewDomain]) -> None:
    #     """Tiny text legend in the top-left corner."""
    #     self._clear_legend()
    #     if not domains:
    #         return
    #     x0, y0 = 10, self.plotter.interactor.height() - 20
    #     dy = 14
    #
    #     for i, domain in enumerate(domains):
    #         t = vtkTextActor()
    #         t.SetInput(f"{domain.name}")
    #         tp = t.GetTextProperty()
    #         tp.SetFontSize(10); tp.SetColor(0, 0, 0); tp.BoldOff(); tp.ShadowOff()
    #         t.SetDisplayPosition(x0, y0 - i * dy)
    #         self.plotter.renderer.AddActor2D(t)
    #         self._legend_actors.append(t)

    # ---- view-change recompute ----

    def _on_view_changed(self) -> None:
        self._update_grid_from_camera()
        self.plotter.render()

    def _clear_preview(self) -> None:
        """Remove all preview actors."""
        actors = [
            self._preview_domain_actors,
            self._preview_edge_actors,
        ]

        for actor_dict in actors:
            for act in actor_dict.values():
                try:
                    self.plotter.remove_actor(act)
                except Exception:
                    pass
            actor_dict.clear()
        # self._clear_legend()

    # ---- triangulation ----

    @staticmethod
    def _triangulate_loops_xy(loops: list[npt.NDArray[np.float64]]) -> pv.PolyData:
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
            ring = np.asarray(ring, dtype=np.float64).reshape(-1, 2)
            if ring.size == 0:
                continue

            # ensure closed
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

        tri = vtkContourTriangulator()
        tri.SetInputData(pd)
        tri.Update()

        return pv.wrap(tri.GetOutput())
