"""
3D Visualization Widget (PyVista Wrapper) - Unified Rendering
"""

from __future__ import annotations

import traceback
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import os

import logging
import numpy as np
import numpy.typing as npt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QStyle
)
from PySide6.QtCore import QTimer, QSize
from PySide6.QtGui import QCloseEvent, QResizeEvent

from pyvistaqt import QtInteractor
import pyvista as pv

from temperatureanalysis.model.state import GeometryData, ProjectState
# Note: No longer need manual profile factories here, state.py handles it
from temperatureanalysis.view.widgets.grid_manager import GridManager
from temperatureanalysis.view.widgets.vtk_utils import VtkUtils

logger = logging.getLogger(__name__)

# --- DATA CLASSES FOR VISUALIZATION ---

@dataclass
class PreviewDomain:
    """A domain consisting of a single filled region (No holes)."""
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

        # --- Managers ---
        self._grid_manager = GridManager(self.plotter)
        self._vtk_utils = VtkUtils()

        # --- Actors state ---
        self._geo_actors: list[pv.Actor] = []
        self._mesh_wireframe_actor: Optional[pv.Actor] = None

        # Result Cache (To prevent flickering)
        self._result_heatmap_actor: Optional[pv.Actor] = None
        self._result_iso_actor: Optional[pv.Actor] = None

        # --- Data cache ---
        # Geometry cache
        self._cached_geo_signature: Optional[str] = None
        # Hold the mesh object in memory to avoid
        # reloading from disk during animation
        self._cached_mesh: Optional[pv.DataSet] = None
        self._cached_mesh_path: Optional[str] = None

        # --- Visibility state ---
        self._visible_geometry: bool = True
        self._visible_mesh: bool = True
        self._visible_results: bool = True

        # --- Regrid logic ---
        self._last_camera_signature: Optional[Tuple[float, float, float, int, int]] = None
        self._attach_observers()
        self._setup_overlay_controls()

        # Debounce timer for grid updates
        self._regrid_timer = QTimer(self)
        self._regrid_timer.setSingleShot(True)
        self._regrid_timer.setInterval(100)
        self._regrid_timer.timeout.connect(self._regrid_if_changed)

    # ------------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------------

    def update_scene(
        self,
        project_state: ProjectState,
        scalars: Optional[np.ndarray] = None,
        reset_camera: bool = True,
        draw_isotherm: bool = True,
        v_min: Optional[float] = None,
        v_max: Optional[float] = None,
        levels: Optional[List[float]] = None
    ) -> None:
        """
        Refreshes all layers in the 3D preview:
        1. Geometry (cached)
        2. Results (if scalars are provided)
        3. Mesh (If mesh path is valid)
        """
        logger.info("Updating 3D preview scene.")
        # --- 1. LAYER: GEOMETRY ---
        self._update_geometry_layer(project_state.geometry)

        # --- 2. LAYER: RESULTS ---
        # Load or retrieve cached mesh object (needed for results & wireframe mesh)
        mesh_data = self._get_or_load_mesh(project_state.mesh_path)

        if scalars is not None and mesh_data is not None:
            # Create/Update Heatmaps and Isolines
            self._update_results_layer(
                mesh_data,
                scalars,
                draw_isotherm,
                v_min,
                v_max,
                levels
            )
            # Auto-enable results visibility if new results are provided
            if not self.btn_vis_res.isChecked():
                self.btn_vis_res.setChecked(True)
        else:
            # Clear previous results
            self._clear_results_layer()

        # --- 3. LAYER: MESH ---
        if mesh_data is not None:
            self._update_mesh_layer(mesh_data)
        else:
            self._clear_mesh_layer()

        # --- 4. APPLY VISIBILITY ---
        self._apply_visibility()

        # --- 5. RESET CAMERA ---
        if reset_camera:
            self.plotter.reset_camera()
            self._grid_manager.update_grid_from_camera()

        self.plotter.render()

    def set_geometry_visible(self, visible: bool, render: bool = True) -> None:
        """
        Public slot to toggle geometry visibility.
        Args:
            visible: True to show, False to hide.
            render: If True, triggers a re-render immediately. Set False for batch updates.
        """
        self._visible_geometry = visible
        # Sync UI button without triggering signal loop
        if self.btn_vis_geo.isChecked() != visible:
            self.btn_vis_geo.blockSignals(True)
            self.btn_vis_geo.setChecked(visible)
            self.btn_vis_geo.blockSignals(False)

        self._apply_visibility()
        if render:
            self.plotter.render()

    def set_mesh_visible(self, visible: bool, render: bool = True) -> None:
        """
        Public slot to toggle mesh visibility.
        Args:
            visible: True to show, False to hide.
            render: If True, triggers a re-render immediately. Set False for batch updates.
        """
        self._visible_mesh = visible
        if self.btn_vis_mesh.isChecked() != visible:
            self.btn_vis_mesh.blockSignals(True)
            self.btn_vis_mesh.setChecked(visible)
            self.btn_vis_mesh.blockSignals(False)

        self._apply_visibility()
        if render:
            self.plotter.render()

    def set_results_visible(self, visible: bool, render: bool = True) -> None:
        """
        Public slot to toggle results visibility.
        Args:
            visible: True to show, False to hide.
            render: If True, triggers a re-render immediately. Set False for batch updates.
        """
        self._visible_results = visible
        if self.btn_vis_res.isChecked() != visible:
            self.btn_vis_res.blockSignals(True)
            self.btn_vis_res.setChecked(visible)
            self.btn_vis_res.blockSignals(False)

        self._apply_visibility()
        if render:
            self.plotter.render()

    # ------------------------------------------------------------------------------
    # Internal: Layer Management
    # ------------------------------------------------------------------------------

    def _get_or_load_mesh(self, path: Optional[str]) -> Optional[pv.DataSet]:
        """Loads mesh from disk only if path changed."""
        if path is None or not os.path.exists(path):
            self._cached_mesh = None
            self._cached_mesh_path = None
            return None

        if self._cached_mesh_path == path and self._cached_mesh is not None:
            return self._cached_mesh

        try:
            # clear previous mesh from the plot
            self._clear_mesh_layer()
            mesh = pv.read(path)
            self._cached_mesh = mesh
            self._cached_mesh_path = path
            return mesh
        except Exception as e:
            logger.error(f"Failed to load mesh from {path}: {e}")
            return None

    def _update_geometry_layer(self, geometry_data: GeometryData) -> None:
        """Rebuild geometry actors only if parameters changed."""
        # Create a simple signature based on string representation of the dataclass
        # This works because GeometryData is a dataclass and str() dumps all fields
        current_signature = str(geometry_data)

        # Check cache
        if self._cached_geo_signature == current_signature:
            return  # No change, skip update

        # --- Rebuild logic ---
        # 1. Clear old actors
        for actor in self._geo_actors:
            self.plotter.remove_actor(actor)
        self._geo_actors.clear()

        # 2. Update cache
        self._cached_geo_signature = current_signature

        profile = geometry_data.get_resolved_profile()
        if not profile:
            return

        thickness = getattr(geometry_data.parameters, "thickness", 0.5)
        loop = profile.get_combined_loop(user_thickness=thickness, assume_symmetric=False)

        if not loop.entities:
            return

        # 3. Discretize loop to points
        points_2d = self._vtk_utils.discretize_loop_to_array(loop)

        # 4. Create a Domain for the Concrete Lining
        domain = PreviewDomain(
            name="tunnel_lining",
            outer=points_2d,
            # fill_color="lightgrey",
            edge_color="black",
            edge_width=3.0,
            opacity=0.5
        )

        # 5. Render
        self._draw_domains([domain])

    def _draw_domains(self, domains: List[PreviewDomain]) -> None:
        """
        Draws domains. Does NOT clear the plotter.
        """
        for domain in domains:
            poly_pts = self._vtk_utils.as_closed_xy(domain.outer)

            # Triangulate and add Fill actor
            tri_pd = self._vtk_utils.triangulate_loops_xy([poly_pts])
            if tri_pd.n_cells > 0:
                act_fill = self.plotter.add_mesh(
                    tri_pd,
                    color=domain.fill_color,
                    opacity=domain.opacity,
                    pickable=False,
                    show_scalar_bar=False,
                    label="Geometry"
                )
                act_fill.position = (0, 0, -0.001)  # Slight offset to prevent z-fighting
                self._geo_actors.append(act_fill)

            # Add Edge actor
            edge_pd = self._vtk_utils.polyline_to_polydata(poly_pts)
            edge_pd.verts = np.empty(0, dtype=int)  # Fix for markers

            act_edge = self.plotter.add_mesh(
                edge_pd,
                color=domain.edge_color,
                line_width=domain.edge_width,
                pickable=False,
                render_lines_as_tubes=False,
                show_scalar_bar=False,
            )
            act_edge.position = (0, 0, -0.001)  # Slight offset to prevent z-fighting
            self._geo_actors.append(act_edge)

    def _update_mesh_layer(self, mesh: pv.DataSet) -> None:
        """Ensures mesh actor exists."""
        if self._mesh_wireframe_actor:
            return  # Already exists

        # create
        self._mesh_wireframe_actor = self.plotter.add_mesh(
            mesh,
            style='wireframe',
            color='black',
            line_width=1,
            opacity=0.2,
            label='Mesh'
        )
        self._mesh_wireframe_actor.position = (0, 0, 0.001)

    def _update_results_layer(
        self,
        mesh: pv.DataSet,
        scalars: npt.NDArray[np.float64],
        draw_isotherm: bool = True,
        v_min: Optional[float] = None,
        v_max: Optional[float] = None,
        levels: Optional[List[float]] = None
    ) -> None:
        """Updates or creates the results heatmap and isolines."""
        celsius_data = scalars - 273.15  # Convert from Kelvin to Celsius
        mesh.point_data["temperature"] = celsius_data

        # Determine plot limits if not provided
        if v_min is None:
            v_min = np.nanmin(celsius_data)
        if v_max is None:
            v_max = np.nanmax(celsius_data)

        self._update_heatmap(mesh, v_min, v_max)
        self._update_isolines(mesh, v_min, v_max, draw_isotherm, levels)

    def _update_heatmap(
        self,
        mesh: pv.DataSet,
        v_min: float,
        v_max: float
    ) -> None:
        """
        Creates or updates the heatmap actor.
        """
        if self._result_heatmap_actor is None:
            # Create new actor
            self._result_heatmap_actor = self.plotter.add_mesh(
                mesh,
                scalars="temperature",
                # cmap="jet",
                cmap="fire",
                lighting=False,
                clim=[v_min, v_max],
                scalar_bar_args={
                    "title": "Teplota (°C)",
                    "vertical": True,
                    "fmt": "%.0f",
                    "position_x": 0.85,
                    "position_y": 0.5,
                },
                show_edges=False,
                interpolate_before_map=True,
            )
        else:
            # Update existing actor
            self._result_heatmap_actor.mapper.scalar_range = (v_min, v_max)
            self._result_heatmap_actor.mapper.scalar_visibility = True
            # Visibility handled in _apply_visibility()

    def _update_isolines(
        self,
        mesh: pv.DataSet,
        v_min: float,
        v_max: float,
        draw_isotherm: bool,
        levels: Optional[List[float]] = None
    ) -> None:
        """Updates or recreates isoline actors."""
        valid_levels = [l for l in levels if v_min <= l <= v_max]

        if not draw_isotherm or not levels or not valid_levels:
            if self._result_iso_actor:
                self.plotter.remove_actor(self._result_iso_actor)
                self._result_iso_actor = None
            return

        # Generate contour lines
        try:
            contours = mesh.contour(isosurfaces=valid_levels, scalars="temperature")
            # Fix for "dots" appearing at vertices by removing vertex cells
            contours.verts = np.empty(0, dtype=int)

            # Update Actor (caching logic)
            if self._result_iso_actor is None:
                self._result_iso_actor = self.plotter.add_mesh(
                    contours,
                    color="black",
                    line_width=1.5,
                    show_scalar_bar=False,
                    render_lines_as_tubes=True,  # nicer visibility
                )
            else:
                # CRITICAL: Update existing data in-place to prevent blinking
                # copy_from() updates points and cells of the existing actor's mapper dataset
                self._result_iso_actor.mapper.dataset.copy_from(contours)

            # Note: Visibility will be enforced by _apply_visibility() later

        except Exception as e:
            # Fallback if contour generation fails
            if self._result_iso_actor:
                self.plotter.remove_actor(self._result_iso_actor)
                self._result_iso_actor = None
            logger.exception(f"Failed to generate isolines: {e}")

    def _clear_mesh_layer(self):
        """Removes the mesh wireframe actor."""
        if self._mesh_wireframe_actor:
            self.plotter.remove_actor(self._mesh_wireframe_actor)
            self._mesh_wireframe_actor = None

    def _clear_results_layer(self):
        """Removes results actors."""
        try:
            self.plotter.remove_scalar_bar("Teplota (°C)", False)
        except Exception as e:
            pass
        if self._result_heatmap_actor:
            self.plotter.remove_actor(self._result_heatmap_actor)
            self._result_heatmap_actor = None
        if self._result_iso_actor:
            self.plotter.remove_actor(self._result_iso_actor)
            self._result_iso_actor = None

    def _apply_visibility(self):
        """Applies visibility states to all layers."""
        # Geometry
        for a in self._geo_actors:
            if a: a.SetVisibility(self._visible_geometry)

        # Mesh
        if self._mesh_wireframe_actor:
            self._mesh_wireframe_actor.SetVisibility(self._visible_mesh)

        # Results
        if self._result_heatmap_actor:
            self._result_heatmap_actor.SetVisibility(self._visible_results)

        if self._result_iso_actor:
            # Only show isolines if results are visible AND we actually computed them
            # We assume if the actor is visible from _update_isolines, it should stay visible
            # But the master switch is _visible_results
            if not self._visible_results:
                self._result_iso_actor.SetVisibility(False)
            else:
                # If master switch is ON, we respect the state left by _update_isolines
                # (which might have hidden it if no levels were valid)
                # However, usually we just want to force it ON if valid levels existed.
                # Since _update_isolines runs before this, let's just leave it unless master is OFF.
                pass

    # ------------------------------------------------------------------------------
    # Internal: Setup & Observers
    # ------------------------------------------------------------------------------

    def _init_plotter(self) -> None:
        self.plotter.set_background("white")
        self.plotter.enable_parallel_projection()
        self.plotter.view_xy()
        self.plotter.enable_image_style()

    def _attach_observers(self) -> None:
        iren = self.plotter.iren
        # Debounce grid updates on interaction
        iren.add_observer("EndInteractionEvent", lambda *_: self._schedule_regrid())
        iren.add_observer("MouseWheelForwardEvent", lambda *_: self._schedule_regrid())
        iren.add_observer("MouseWheelBackwardEvent", lambda *_: self._schedule_regrid())
        iren.add_observer("ConfigureEvent", lambda *_: self._schedule_regrid())

    def _schedule_regrid(self) -> None:
        self._regrid_timer.start()

    def _regrid_if_changed(self) -> None:
        cam = self.plotter.camera
        sig = (cam.focal_point[0], cam.focal_point[1], cam.parallel_scale)
        if sig != self._last_camera_signature:
            self._last_camera_signature = sig
            self._grid_manager.update_grid_from_camera()

    def _setup_overlay_controls(self) -> None:
        """Floating toggle buttons."""
        self.overlay_widget = QFrame(self)
        self.overlay_widget.setStyleSheet("""
            QFrame { background-color: rgba(255, 255, 255, 200); border-radius: 6px; border: 1px solid #ccc; }
            QPushButton { background-color: transparent; border: none; padding: 4px; }
            QPushButton:checked { background-color: rgba(0, 120, 215, 50); border: 1px solid #0078D7; border-radius: 3px; }
            QPushButton:hover { background-color: rgba(0, 0, 0, 10); }
        """)

        layout = QHBoxLayout(self.overlay_widget)
        layout.setContentsMargins(4, 4, 4, 4)

        def make_btn(icon, slot, tooltip, default_state=True):
            btn = QPushButton()
            btn.setIcon(self.style().standardIcon(icon))
            btn.setCheckable(True)
            btn.setChecked(default_state)
            btn.setToolTip(tooltip)
            btn.toggled.connect(slot)
            layout.addWidget(btn)
            return btn

        # Define buttons and link to toggle slots
        self.btn_vis_geo = make_btn(QStyle.SP_FileIcon, self.on_toggle_geometry, "Zobrazit Geometrii")
        self.btn_vis_mesh = make_btn(QStyle.SP_FileDialogListView, self.on_toggle_mesh, "Zobrazit Síť")
        self.btn_vis_res = make_btn(QStyle.SP_DialogApplyButton, self.on_toggle_results, "Zobrazit Výsledky",
                                    default_state=False)

        # Sync internal state
        self._visible_geometry = self.btn_vis_geo.isChecked()
        self._visible_mesh = self.btn_vis_mesh.isChecked()
        self._visible_results = self.btn_vis_res.isChecked()

        self.overlay_widget.adjustSize()

    # --- Toggle Slots ---
    def on_toggle_geometry(self, checked: bool):
        self._visible_geometry = checked
        self._apply_visibility()
        self.plotter.render()

    def on_toggle_mesh(self, checked: bool):
        self._visible_mesh = checked
        self._apply_visibility()
        self.plotter.render()

    def on_toggle_results(self, checked: bool):
        self._visible_results = checked
        self._apply_visibility()
        self.plotter.render()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.plotter.close()
        event.accept()

    # def show_results(
    #     self,
    #     mesh_path: str,
    #     scalars: np.ndarray,
    #     draw_isotherm: bool = True,
    #     draw_temperature: bool = True,
    #     v_min: Optional[float] = None,
    #     v_max: Optional[float] = None,
    #     regrid: bool = True,
    # ) -> None:
    #     """
    #     Displays a scalar field on the mesh.
    #     Optimized to avoid flickering by reusing the mesh actor.
    #
    #     Args:
    #         mesh_path: Path to the .vtu/.msh file.
    #         scalars: Numpy array of temperature values (assumed Kelvin).
    #         draw_isotherm: Whether to draw contour lines.
    #         draw_temperature: Whether to show the colored heat map.
    #         v_min: Minimum value for the scalar bar (color map).
    #         v_max: Maximum value for the scalar bar (color map).
    #         regrid: Whether to recompute the grid after rendering.
    #     """
    #     # --- CLEANUP PREVIOUS MODES ---
    #     # Ensure Geometry (Blue/Grey fill) is gone
    #     self._clear_preview()
    #     # Ensure Static Mesh (Wireframe overlay) is gone
    #     self._clear_mesh()
    #
    #     try:
    #         celsius_data = scalars - 273.15  # Convert from Kelvin to Celsius
    #
    #         # Determine plot limits if not provided
    #         if v_min is None:
    #             v_min = np.nanmin(celsius_data)
    #         if v_max is None:
    #             v_max = np.nanmax(celsius_data)
    #
    #         # 2. Check if we need a full reload or just an update
    #         # We reload if the file path changed or if we don't have a cache
    #         is_new_mesh = (mesh_path != self._cached_mesh_path) or (self._cached_mesh is None)
    #
    #         if is_new_mesh:
    #             # -- FULL RELOAD --
    #             self._clear_results()  # Clear all previous result actors
    #
    #             # Load new mesh
    #             self._cached_mesh = pv.read(mesh_path)
    #             self._cached_mesh_path = mesh_path
    #             self._cached_mesh_actor = None  # Will be created below
    #
    #             # Validate size
    #             if len(scalars) != self._cached_mesh.n_points:
    #                 print(f"Error: Result size {len(scalars)} != Mesh points {self._cached_mesh.n_points}")
    #                 return
    #
    #         else:
    #             # -- UPDATE EXISTING --
    #             # Remove "decorations" (Isolines, Labels) but KEEP the main mesh actor
    #             # We iterate backwards to safely remove items from the list
    #             for actor in list(self._result_actors):
    #                 if actor == self._cached_mesh_actor:
    #                     continue  # Keep the main heatmap
    #                 self.plotter.remove_actor(actor)
    #                 self._result_actors.remove(actor)
    #
    #         # 3. Update Scalar Data on the Mesh Object
    #         # This updates the data in memory without destroying the object
    #         self._cached_mesh.point_data["temperature"] = celsius_data
    #
    #         if draw_temperature:
    #             scalars = "temperature"
    #         else:
    #             scalars = None
    #
    #         # 4. Create or Update Main Actor
    #         if self._cached_mesh_actor is None:
    #             # Create the actor for the first time
    #             self._cached_mesh_actor = self.plotter.add_mesh(
    #                 self._cached_mesh,
    #                 scalars=scalars,
    #                 cmap="jet",
    #                 clim=[v_min, v_max],
    #                 # show_edges=draw_mesh,
    #                 line_width=0.01,
    #                 edge_color='grey',
    #                 scalar_bar_args={
    #                     "title": "Teplota (°C)",
    #                     "vertical": True,
    #                     "fmt": "%.0f",
    #                     "position_x": 0.85,
    #                     "position_y": 0.5,
    #                 },
    #                 interpolate_before_map=True,
    #             )
    #             self._result_actors.append(self._cached_mesh_actor)
    #
    #         else:
    #             # Update existing actor
    #             # If we toggled visibility of scalars
    #             if draw_temperature:
    #                 self._cached_mesh_actor.mapper.scalar_range = (v_min, v_max)
    #                 self._cached_mesh_actor.mapper.scalar_visibility = True
    #             else:
    #                 self._cached_mesh_actor.mapper.scalar_visibility = False
    #
    #         if draw_isotherm and draw_temperature:
    #             # Generate contour lines at default levels
    #             celsius_min = np.nanmin(celsius_data)
    #             celsius_max = np.nanmax(celsius_data)
    #             levels = [500]
    #             valid_levels = [l for l in levels if celsius_min <= l <= celsius_max]
    #
    #             if valid_levels:
    #                 isolines = self._cached_mesh.contour(isosurfaces=levels, scalars="temperature")
    #
    #                 # Add them as black isolines
    #                 isolines_actor = self.plotter.add_mesh(
    #                     isolines,
    #                     color="black",
    #                     line_width=1.5,
    #                     show_scalar_bar=False,
    #                     render_lines_as_tubes=True  # nicer visibility
    #                 )
    #
    #                 self._result_actors.append(isolines_actor)
    #
    #                 # Add labels manually
    #                 for value in levels:
    #                     # Extract only the polyline(s) for this isovalue
    #                     iso = self._cached_mesh.contour(isosurfaces=[value], scalars="temperature")
    #
    #                     # --- FIX FOR STUCK POINTS ---
    #                     # Explicitly remove vertex cells (dots) from the contour polydata
    #                     iso.verts = np.empty(0, dtype=int)
    #
    #                     # Take the first point of the isoline
    #                     if iso.n_points > 0:
    #                         idx = iso.n_points // 2
    #                         point = iso.points[idx]
    #
    #                         lbl_actor = self.plotter.add_point_labels(
    #                             point,
    #                             [f"{value}°C"],
    #                             font_size=12,
    #                             text_color="black",
    #                             fill_shape=True,
    #                             always_visible=True,
    #                             show_points=False,
    #                         )
    #                         self._result_actors.append(lbl_actor)
    #                         # self._result_actors.append(point)
    #
    #         # # Force redraw
    #         self.plotter.render()
    #
    #         # Re-add grid
    #         if regrid:
    #             if self._grid_minor_actor: self.plotter.remove_actor(self._grid_minor_actor)
    #             if self._grid_major_actor: self.plotter.remove_actor(self._grid_major_actor)
    #             for a in self._ruler_actors:
    #                 self.plotter.renderer.RemoveActor2D(a)
    #             self.plotter.reset_camera()
    #             self._update_grid_from_camera()
    #
    #     except Exception as e:
    #         print(f"Failed to render results: {e}")
    #
    # def _setup_overlay_controls(self) -> None:
    #     """Creates the floating buttons in the top-right corner."""
    #     # Container Frame
    #     self.overlay_widget = QFrame(self)
    #     # Semi-transparent background + rounded corners
    #     self.overlay_widget.setStyleSheet("""
    #         QFrame {
    #             background-color: rgba(255, 255, 255, 200);
    #             border: 1px solid #bbbbbb;
    #             border-radius: 6px;
    #         }
    #         QPushButton {
    #             background-color: transparent;
    #             border: none;
    #             border-radius: 4px;
    #             padding: 4px;
    #         }
    #         QPushButton:hover {
    #             background-color: rgba(0, 0, 0, 20);
    #         }
    #         QPushButton:checked {
    #             background-color: rgba(0, 120, 215, 50);
    #             border: 1px solid rgba(0, 120, 215, 150);
    #         }
    #     """)
    #
    #     layout = QHBoxLayout(self.overlay_widget)
    #     layout.setContentsMargins(4, 4, 4, 4)
    #     layout.setSpacing(4)
    #
    #     # Helper to create buttons
    #     def create_btn(icon_type, tooltip: str, callback: Callable[[bool], None], checked: bool):
    #         btn = QPushButton()
    #         btn.setIcon(self.style().standardIcon(icon_type))
    #         btn.setIconSize(QSize(20, 20))
    #         btn.setCheckable(True)
    #         btn.setChecked(checked)
    #         btn.setToolTip(tooltip)
    #         btn.toggled.connect(callback)
    #         layout.addWidget(btn)
    #         return btn
    #
    #     # 1. Geometry Toggle
    #     self.btn_vis_geo = create_btn(
    #         QStyle.SP_FileIcon,
    #         "Zobrazit Geometrii",
    #         self.set_geometry_visible,
    #         self._visible_geometry
    #     )
    #
    #     # 2. Mesh Toggle
    #     self.btn_vis_mesh = create_btn(
    #         QStyle.SP_FileDialogListView,
    #         "Zobrazit Síť",
    #         self.set_mesh_visible,
    #         self._visible_mesh
    #     )
    #
    #     # 3. Results Toggle
    #     self.btn_vis_res = create_btn(
    #         QStyle.SP_DialogApplyButton,
    #         "Zobrazit Výsledky",
    #         self.set_results_visible,
    #         self._visible_results
    #     )
    #
    #     self.overlay_widget.adjustSize()
    #
    # def set_geometry_visible(self, visible: bool) -> None:
    #     self._visible_geometry = visible
    #     # Update button state if called programmatically
    #     if self.btn_vis_geo.isChecked() != visible:
    #         self.btn_vis_geo.blockSignals(True)
    #         self.btn_vis_geo.setChecked(visible)
    #         self.btn_vis_geo.blockSignals(False)
    #
    #     for actor in self._preview_domain_actors.values():
    #         actor.SetVisibility(visible)
    #     for actor in self._preview_edge_actors.values():
    #         actor.SetVisibility(visible)
    #     self.plotter.render()
    #
    # def set_mesh_visible(self, visible: bool) -> None:
    #     self._visible_mesh = visible
    #     if self.btn_vis_mesh.isChecked() != visible:
    #         self.btn_vis_mesh.blockSignals(True)
    #         self.btn_vis_mesh.setChecked(visible)
    #         self.btn_vis_mesh.blockSignals(False)
    #
    #     for actor in self._preview_mesh_actors.values():
    #         actor.SetVisibility(visible)
    #     self.plotter.render()
    #
    # def set_results_visible(self, visible: bool) -> None:
    #     self._visible_results = visible
    #     if self.btn_vis_res.isChecked() != visible:
    #         self.btn_vis_res.blockSignals(True)
    #         self.btn_vis_res.setChecked(visible)
    #         self.btn_vis_res.blockSignals(False)
    #
    #     for actor in self._result_actors:
    #         actor.SetVisibility(visible)
    #     self.plotter.render()
    #
    # def _clear_results(self) -> None:
    #     """Remove only results-related actors."""
    #     for actor in self._result_actors:
    #         self.plotter.remove_actor(actor)
    #     self._result_actors.clear()
    #
    # def _clear_mesh(self) -> None:
    #     """Remove the wireframe mesh overlay used in Geometry preview."""
    #     for actor in self._preview_mesh_actors:
    #         self.plotter.remove_actor(actor)
    #     self._preview_mesh_actors.clear()
    #
    # # def _render_geometry_layer(self, geometry_data: GeometryData) -> None:
    # #     """
    # #     Main entry point triggered by Architecture (Signals).
    # #     Converts ProjectState geometry -> Visualization Domains -> Renders.
    # #     """
    # #     # 1. Generate the BoundaryLoop from Model
    # #     logger.info("Rendering geometry layer.")
    # #     profile = geometry_data.get_resolved_profile()
    # #     if not profile:
    # #         self._clear_preview()
    # #         return
    # #
    # #     # Fix: Use object attribute access instead of dictionary .get()
    # #     # Fallback to 0.5 if attribute is missing (safety)
    # #     thickness = getattr(geometry_data.parameters, "thickness", 0.5)
    # #
    # #     loop = profile.get_combined_loop(user_thickness=thickness)
    # #
    # #     if not loop.entities:
    # #         self._clear_preview()
    # #         return
    # #
    # #     # 2. Convert BoundaryLoop (Arcs/Lines) to Dense Points (N, 2)
    # #     points_2d = self._discretize_loop_to_array(loop)
    # #
    # #     # 3. Create a Domain for the Concrete Lining
    # #     domain = PreviewDomain(
    # #         name="tunnel_lining",
    # #         outer=points_2d,
    # #         # fill_color="lightgrey",
    # #         edge_color="black",
    # #         edge_width=3.0,
    # #         opacity=0.5
    # #     )
    # #
    # #     # 4. Render
    # #     self._draw_domains([domain])
    #
    # def _render_mesh_layer(self, filepath: str) -> None:
    #     """Loads .vtu/.msh and adds it to the existing scene."""
    #     logger.info(f"Loading mesh for preview: {filepath}")
    #     try:
    #         mesh = pv.read(filepath)
    #
    #         # Wireframe (Black edges)
    #         act = self.plotter.add_mesh(
    #             mesh,
    #             style='wireframe',
    #             color='black',
    #             line_width=1,
    #             label='Mesh Edges'
    #         )
    #
    #         self._preview_mesh_actors["mesh"] = act
    #
    #     except Exception as e:
    #         print(f"Failed to load mesh preview: {e}")
    #
    #
    #
    # def load_mesh_file(self, filepath: str) -> None:
    #     """
    #     Loads and displays a VTK/Gmsh mesh file (.vtu, .msh).
    #     """
    #     # self.plotter.clear()
    #
    #     try:
    #         # Read the mesh
    #         mesh = pv.read(filepath)
    #
    #         # Plot edges (Wireframe)
    #         self.plotter.add_mesh(
    #             mesh,
    #             style='wireframe',
    #             color='black',
    #             line_width=1,
    #             label='Mesh Edges'
    #         )
    #
    #         self.plotter.reset_camera()
    #
    #     except Exception as e:
    #         print(f"Failed to load mesh preview: {e}")
    #
    # # ------------------------------------------------------------------------------
    # # Data Conversion Helpers
    # # ------------------------------------------------------------------------------
    #
    #
    #
    # # ------------------------------------------------------------------------------
    # # Internal: Plotter & Grid Logic
    # # ------------------------------------------------------------------------------
    #
    # def _init_plotter(self) -> None:
    #     """Initialization of the plotter."""
    #     self.plotter.set_background("white")
    #     self.plotter.enable_parallel_projection()
    #     self.plotter.render_lines_as_tubes = True
    #
    # def _configure_2d_mode(self) -> None:
    #     """Lock to 2D XY with orthographic camera and pan/zoom only."""
    #     self.plotter.enable_parallel_projection()
    #     self.plotter.view_xy()
    #     self.plotter.enable_image_style()
    #
    # def _attach_observers(self) -> None:
    #     """Recompute grid/labels after interaction or resize."""
    #     iren = self.plotter.iren
    #     iren.add_observer("EndInteractionEvent", lambda *_: self._schedule_regrid())
    #     iren.add_observer("MouseWheelForwardEvent", lambda *_: self._schedule_regrid())
    #     iren.add_observer("MouseWheelBackwardEvent", lambda *_: self._schedule_regrid())
    #     iren.add_observer("ConfigureEvent", lambda *_: self._schedule_regrid())
    #
    # def _schedule_regrid(self) -> None:
    #     self._regrid_timer.start()
    #
    # def _camera_signature(self) -> tuple[float, float, float, int, int]:
    #     """A simple signature of the current camera view to detect changes."""
    #     cam = self.plotter.camera
    #     w = int(self.plotter.interactor.width())
    #     h = int(self.plotter.interactor.height())
    #     return (
    #         round(cam.focal_point[0], 9),
    #         round(cam.focal_point[1], 9),
    #         round(cam.parallel_scale, 9),
    #         w, h
    #     )
    #
    # def _is_view_ready(self) -> bool:
    #     """Check if the camera and viewport are properly initialized."""
    #     if self.plotter is None or self.plotter.renderer is None:
    #         return False
    #     w = int(self.plotter.interactor.width())
    #     h = int(self.plotter.interactor.height())
    #     return w > 1 and h > 1
    #
    # def _regrid_if_changed(self) -> None:
    #     """Recompute the grid and labels if the camera view has changed."""
    #     if not self._is_view_ready():
    #         return
    #     new_sig = self._camera_signature()
    #     if new_sig == self._last_camera_signature:
    #         return
    #     self._last_camera_signature = new_sig
    #     self._update_grid_from_camera()
    #     self.plotter.render()
    #
    #
    #
    #
    #
    #
    #
    #
    #
    # def _fit_camera_to_points(self, pts2d: npt.NDArray[np.float64]) -> None:
    #     x_min, y_min = pts2d.min(axis=0)
    #     x_max, y_max = pts2d.max(axis=0)
    #     cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
    #     dx, dy = max(1e-6, x_max - x_min), max(1e-6, y_max - y_min)
    #
    #     cam = self.plotter.camera
    #     cam.position = (cx, cy, 1.0)
    #     cam.focal_point = (cx, cy, 0.0)
    #     cam.parallel_scale = 0.5 * 1.2 * max(dx, dy)
    #
    # def _clear_preview(self) -> None:
    #     for d in self._preview_domain_actors.values(): self.plotter.remove_actor(d)
    #     for d in self._preview_edge_actors.values(): self.plotter.remove_actor(d)
    #     self._preview_domain_actors.clear()
    #     self._preview_edge_actors.clear()
    #
    # def closeEvent(self, event: QCloseEvent) -> None:
    #     self.plotter.close()
    #     event.accept()
