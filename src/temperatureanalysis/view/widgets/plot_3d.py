from __future__ import annotations

import logging
import os
from typing import Optional, List, Dict, Callable, Tuple, Union
from dataclasses import dataclass
import numpy as np
import numpy.typing as npt

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent

from pyvistaqt import QtInteractor
import pyvista as pv

# VTK Imports for advanced actors and triangulation
from vtkmodules.vtkRenderingCore import vtkTextActor
from vtkmodules.vtkFiltersGeneral import vtkContourTriangulator

from temperatureanalysis.model.state import GeometryData, ProjectState
from temperatureanalysis.model.profiles import (
    ALL_PROFILES, TunnelProfile, TunnelOutline, OutlineShape, TunnelCategory, ProfileGroupKey, CustomTunnelShape
)
from temperatureanalysis.model.geometry_primitives import Point, Line, Arc, BoundaryLoop

logger = logging.getLogger(__name__)

# --- DATA CLASSES FOR VISUALIZATION ---

@dataclass
class PreviewDomain:
    """
    A domain consisting of a single filled region (No holes).
    """
    name: str
    outer: npt.NDArray[np.float64]  # (N, 2) array

    fill_color: str | Tuple[float, float, float] = "#A0C4FF"
    edge_color: str | Tuple[float, float, float] = "black"
    edge_width: float = 2.0
    opacity: float = 0.5


# --- WIDGET CLASS ---

class PyVistaWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.layout_box: QVBoxLayout = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)

        self.plotter: QtInteractor = QtInteractor(self)
        self.layout_box.addWidget(self.plotter)

        self._init_plotter()

        # Grid config
        self._major_spacing: float = 1.0
        self._minor_spacing: float = 0.5
        self._label_formatter: Callable[[float], str] = lambda v: f"{v:g}"

        # Actors state
        self._grid_major_actor: Optional[pv.Actor] = None
        self._grid_minor_actor: Optional[pv.Actor] = None
        self._ruler_actors: List[vtkTextActor] = []
        self._preview_domain_actors: Dict[str, pv.Actor] = {}
        self._preview_edge_actors: Dict[str, pv.Actor] = {}

        # Cache for regrid
        self._last_camera_signature: Optional[Tuple[float, float, float, int, int]] = None

        # Init View
        self._configure_2d_mode()
        self._attach_observers()

        # Debounce timer for grid updates
        self._regrid_timer = QTimer(self)
        self._regrid_timer.setSingleShot(True)
        self._regrid_timer.setInterval(100)
        self._regrid_timer.timeout.connect(self._regrid_if_changed)

    # ------------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------------

    def update_scene(self, project_state: ProjectState, reset_camera: bool = True) -> None:
        """
        Main entry point. Clears scene and renders layers in order.
        1. Geometry (Base)
        2. Mesh (Overlay)
        """
        logger.info("Updating 3D preview scene.")
        # 1. Clear everything
        self.plotter.clear()
        self._preview_domain_actors.clear()
        self._preview_edge_actors.clear()
        self._ruler_actors.clear()  # Cleared via _update_grid, but good to be safe

        # 2. Render Geometry Layer
        self._render_geometry_layer(project_state.geometry)

        # 3. Render Mesh Layer (Overlay)
        logger.debug(f"Trying to load mesh layer from: {project_state.mesh_path}")
        if project_state.mesh_path and os.path.exists(project_state.mesh_path):
            self._render_mesh_layer(project_state.mesh_path)

        # 4. Finalize
        # self.plotter.add_legend()
        if reset_camera:
            self.plotter.reset_camera()

        self._update_grid_from_camera()

        # Update grid based on the final camera position

    def show_results(
        self,
        mesh_path: str,
        scalars: np.ndarray,
        draw_isotherm: bool = True,
        draw_temperature: bool = True,
        v_min: Optional[float] = None,
        v_max: Optional[float] = None,
    ) -> None:
        """
        Displays a scalar field on the mesh.

        Args:
            mesh_path: Path to the .vtu/.msh file.
            scalars: Numpy array of temperature values (assumed Kelvin).
            draw_isotherm: Whether to draw contour lines.
            draw_temperature: Whether to show the colored heat map.
            v_min: Minimum value for the scalar bar (color map).
            v_max: Maximum value for the scalar bar (color map).
        """
        # Don't clear everything, just update the mesh layer
        # But for safety in this version, let's clear actors.
        self.plotter.clear()

        try:
            mesh = pv.read(mesh_path)

            # Ensure scalars match node count
            if len(scalars) != mesh.n_points:
                print(f"Error: Result size {len(scalars)} != Mesh points {mesh.n_points}")
                return

            # Assign scalars
            celsius_data = scalars - 273.15  # Convert from Kelvin to Celsius
            mesh.point_data["temperature"] = celsius_data  # Convert from Kelvin to Celsius

            # Determine plot limits if not provided
            if v_min is None:
                v_min = np.nanmin(celsius_data)
            if v_max is None:
                v_max = np.nanmax(celsius_data)

            if draw_temperature:
                scalars = "temperature"
            else:
                scalars = None

            self.plotter.add_mesh(
                mesh,
                scalars=scalars,
                cmap="jet",
                clim=[v_min, v_max],
                # show_edges=draw_mesh,
                line_width=0.01,
                edge_color='grey',
                scalar_bar_args={
                    "title": "Teplota (°C)",
                    "vertical": True,
                    "fmt": "%.0f",
                    "position_x": 0.85,
                    "position_y": 0.5,
                },
                interpolate_before_map=True,
            )

            if draw_isotherm and draw_temperature:
                # Generate contour lines at default levels
                levels = [500]
                isolines = mesh.contour(isosurfaces=levels, scalars="temperature")

                # Add them as black isolines
                self.plotter.add_mesh(
                    isolines,
                    color="black",
                    line_width=1.5,
                    show_scalar_bar=False,
                    render_lines_as_tubes=True  # nicer visibility
                )

                # Add labels manually
                for value in levels:
                    # Extract only the polyline(s) for this isovalue
                    iso = mesh.contour(isosurfaces=[value], scalars="temperature")

                    # Take the first point of the isoline
                    if iso.n_points > 0:
                        idx = iso.n_points // 2
                        point = iso.points[idx]

                        self.plotter.add_point_labels(
                            point,
                            [f"{value}°C"],
                            font_size=12,
                            text_color="black",
                            fill_shape=True,
                            always_visible=True,
                        )

            # Re-add grid
            self._update_grid_from_camera()
            # self.plotter.reset_camera() # Optional: Don't reset if animating

        except Exception as e:
            print(f"Failed to render results: {e}")

    def _render_geometry_layer(self, geometry_data: GeometryData) -> None:
        """
        Main entry point triggered by Architecture (Signals).
        Converts ProjectState geometry -> Visualization Domains -> Renders.
        """
        # 1. Generate the BoundaryLoop from Model
        logger.info("Rendering geometry layer.")
        profile = geometry_data.get_resolved_profile()
        if not profile:
            self._clear_preview()
            return

        # Fix: Use object attribute access instead of dictionary .get()
        # Fallback to 0.5 if attribute is missing (safety)
        thickness = getattr(geometry_data.parameters, "thickness", 0.5)

        loop = profile.get_combined_loop(user_thickness=thickness)

        if not loop.entities:
            self._clear_preview()
            return

        # 2. Convert BoundaryLoop (Arcs/Lines) to Dense Points (N, 2)
        points_2d = self._discretize_loop_to_array(loop)

        # 3. Create a Domain for the Concrete Lining
        domain = PreviewDomain(
            name="tunnel_lining",
            outer=points_2d,
            # fill_color="lightgrey",
            edge_color="black",
            edge_width=3.0,
            opacity=0.5
        )

        # 4. Render
        self._draw_domains([domain])

    def _render_mesh_layer(self, filepath: str) -> None:
        """Loads .vtu/.msh and adds it to the existing scene."""
        logger.info(f"Loading mesh for preview: {filepath}")
        try:
            mesh = pv.read(filepath)

            # Wireframe (Black edges)
            self.plotter.add_mesh(
                mesh,
                style='wireframe',
                color='black',
                line_width=1,
                label='Mesh Edges'
            )

        except Exception as e:
            print(f"Failed to load mesh preview: {e}")

    def _draw_domains(self, domains: List[PreviewDomain]) -> None:
        """
        Draws domains. Does NOT clear the plotter.
        """
        allpts: List[npt.NDArray[np.float64]] = []

        for domain in domains:
            poly_pts = self._as_closed_xy(domain.outer)

            # Fill
            tri_pd = self._triangulate_loops_xy([poly_pts])
            if tri_pd.n_cells > 0:
                act_fill = self.plotter.add_mesh(
                    tri_pd,
                    color=domain.fill_color,
                    opacity=domain.opacity,
                    pickable=True,
                    show_scalar_bar=False,
                    label="Geometry"
                )
                self._preview_domain_actors[domain.name] = act_fill
                allpts.append(tri_pd.points[:, :2])

            # Edge
            edge_pd = self._polyline_to_polydata(poly_pts)
            edge_pd.verts = np.empty(0, dtype=int)  # Fix for markers

            act_edge = self.plotter.add_mesh(
                edge_pd,
                color=domain.edge_color,
                line_width=domain.edge_width,
                pickable=False,
                render_lines_as_tubes=False,
                show_scalar_bar=False,
            )
            self._preview_edge_actors[f"{domain.name}-edge"] = act_edge
            allpts.append(poly_pts)

    def load_mesh_file(self, filepath: str) -> None:
        """
        Loads and displays a VTK/Gmsh mesh file (.vtu, .msh).
        """
        # self.plotter.clear()

        try:
            # Read the mesh
            mesh = pv.read(filepath)

            # Plot edges (Wireframe)
            self.plotter.add_mesh(
                mesh,
                style='wireframe',
                color='black',
                line_width=1,
                label='Mesh Edges'
            )

            self.plotter.reset_camera()

        except Exception as e:
            print(f"Failed to load mesh preview: {e}")

    # ------------------------------------------------------------------------------
    # Data Conversion Helpers
    # ------------------------------------------------------------------------------

    def _discretize_loop_to_array(self, loop: BoundaryLoop) -> npt.NDArray[np.float64]:
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

    # ------------------------------------------------------------------------------
    # Internal: Plotter & Grid Logic
    # ------------------------------------------------------------------------------

    def _init_plotter(self) -> None:
        """Initialization of the plotter."""
        self.plotter.set_background("white")
        self.plotter.enable_parallel_projection()
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
            w, h
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
        """Convert a (N, 2) array of points to a PolyData line."""
        ring = np.asarray(ring, dtype=np.float64).reshape(-1, 2)
        n = ring.shape[0]
        pts3 = np.c_[ring, np.zeros((n, 1), dtype=np.float64)]
        pd = pv.PolyData(pts3)
        pd.lines = np.hstack([[n], np.arange(n, dtype=np.int_)])
        return pd

    @staticmethod
    def _clean_duplicate_points(points: npt.NDArray[np.float64], tol: float = 1e-5) -> npt.NDArray[np.float64]:
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

    def _triangulate_loops_xy(self, loops: list[npt.NDArray[np.float64]]) -> pv.PolyData:
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
            ring = self._clean_duplicate_points(ring)
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
            output = tri.GetOutput()

            if output.GetNumberOfCells() == 0:
                # Fallback: Sometimes winding order affects it
                # Reverse points and try again?
                pass
            return pv.wrap(output)
        except Exception as e:
            print(f"Triangulation failed: {e}")
            return pv.PolyData()

    # ---- Grid & Labels ----

    def _update_grid_from_camera(self) -> None:
        if self.plotter is None: return

        bounds = self._grid_extend_from_camera(margin=0.25)

        grid_minor = self._build_xy_grid_polydata(bounds, spacing=self._minor_spacing)
        grid_major = self._build_xy_grid_polydata(bounds, spacing=self._major_spacing)

        if self._grid_minor_actor: self.plotter.remove_actor(self._grid_minor_actor)
        if self._grid_major_actor: self.plotter.remove_actor(self._grid_major_actor)

        self._grid_minor_actor = self.plotter.add_mesh(
            grid_minor, color="#E0E0E0", line_width=1, opacity=0.5, pickable=False
        )
        self._grid_major_actor = self.plotter.add_mesh(
            grid_major, color="#B0B0B0", line_width=1, opacity=0.8, pickable=False
        )

        self._axis_labels_edge(bounds, self._major_spacing)

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
            t.SetInput(self._label_formatter(x))
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
            t.SetInput(self._label_formatter(y))
            t.GetTextProperty().SetColor(0, 0, 0)
            t.GetTextProperty().SetFontSize(12)
            t.SetDisplayPosition(int(pad), int(dy))
            ren.AddActor2D(t)
            self._ruler_actors.append(t)

    def _fit_camera_to_points(self, pts2d: npt.NDArray[np.float64]) -> None:
        x_min, y_min = pts2d.min(axis=0)
        x_max, y_max = pts2d.max(axis=0)
        cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
        dx, dy = max(1e-6, x_max - x_min), max(1e-6, y_max - y_min)

        cam = self.plotter.camera
        cam.position = (cx, cy, 1.0)
        cam.focal_point = (cx, cy, 0.0)
        cam.parallel_scale = 0.5 * 1.2 * max(dx, dy)

    def _clear_preview(self) -> None:
        for d in self._preview_domain_actors.values(): self.plotter.remove_actor(d)
        for d in self._preview_edge_actors.values(): self.plotter.remove_actor(d)
        self._preview_domain_actors.clear()
        self._preview_edge_actors.clear()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.plotter.close()
        event.accept()
