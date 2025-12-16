"""
Mesh Generation Logic (Gmsh Adapter)
====================================
This module translates the ProjectState geometry into a Finite Element Mesh.

Why is this file needed?
------------------------
1. Translation: It converts our abstract 'GeometryData' (e.g., box width=10)
   into specific Gmsh API commands.
2. Export: It handles the generation of the physical .msh or .vtu files required
   by the solver.
"""
from __future__ import annotations

import tempfile
import uuid

import gmsh
import os
import logging
from typing import Dict, Tuple, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

from temperatureanalysis.model.profiles import (
    ALL_PROFILES, TunnelProfile, TunnelOutline
)
from temperatureanalysis.model.geometry_primitives import Point, Line, Arc, BoundaryLoop

if TYPE_CHECKING:
    from temperatureanalysis.model.state import ProjectState

# Get logger
logger = logging.getLogger(__name__)

@dataclass
class MeshStats:
    """Return object containing mesh metadata."""
    filepath: str
    num_nodes: int
    num_elements: int

class PointCache:
    """
    Helper to prevent duplicate points in Gmsh.
    Maps (x, y) coordinates to Gmsh Node Tags.
    """
    def __init__(self, tolerance: float = 1e-6):
        self.cache: Dict[Tuple[float, float], int] = {}
        self.tolerance = tolerance

    def get_or_create(self, pt: Point, mesh_size: float) -> int:
        # Round keys to avoid floating point mismatch issues
        # Using 6 decimals allows for sub-millimeter precision which is fine
        key = (round(float(pt.x), 6), round(float(pt.y), 6))

        if key in self.cache:
            return self.cache[key]

        # Create new point in Gmsh
        # tag = gmsh.model.geo.addPoint(x, y, z, mesh_size)
        tag = gmsh.model.geo.addPoint(pt.x, pt.y, 0.0, mesh_size)
        self.cache[key] = tag
        return tag

    def get(self, pt: Point) -> int:
        key = (round(float(pt.x), 6), round(float(pt.y), 6))
        if key in self.cache:
            return self.cache[key]
        else:
            raise ValueError("Point not in cache!")


class GmshMesher:
    def __init__(self):
        self._initialized = False

    def _ensure_init(self):
        """Initialize Gmsh if not already initialized."""
        if not self._initialized:
            gmsh.initialize()
            self._initialized = True
        # Double-check gmsh state in case it was finalized externally
        elif not gmsh.is_initialized():
            logger.warning("Gmsh was finalized externally, reinitializing")
            gmsh.initialize()
            self._initialized = True

    def generate_mesh(
        self,
        project: ProjectState,
        lc_min: float = 0.1,
        lc_max: float = 0.3,
        use_gradient: bool = False,
        ) -> MeshStats:
        """
        Generates a 2D mesh from the project geometry.
        Returns the path to the generated .msh file.
        If use_gradient is True, creates finer mesh near 'inner' boundary.
        """
        self._ensure_init()
        gmsh.model.add("Tunel")

        try:
            # 1. Clear previous geometry
            gmsh.clear()
            logger.info(f"Generating mesh.")

            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)

            # 2. Get the geometry loop
            loop = self._get_boundary_loop(
                project=project,
                assume_symmetric=True,
                max_distance_between_points=project.thermocouple_distance
            )

            if not loop or not loop.entities:
                raise ValueError("No valid geometry found to mesh.")

            # Base mesh size for points (used as fallback or max)
            base_lc = lc_min if not use_gradient else lc_max

            # 3. Translate to GMSH
            point_cache = PointCache()
            curve_tags: list[int] = []

            # Categories for Physical Groups
            tags_inner = []
            tags_outer = []

            tags_inner_points = []
            tags_rebar_points = []

            for entity in loop.entities:
                p1_tag = point_cache.get_or_create(entity.start, base_lc)
                p2_tag = point_cache.get_or_create(entity.end, base_lc)
                c_tag = -1

                if isinstance(entity, Line):
                    c_tag = gmsh.model.geo.add_line(p1_tag, p2_tag)
                if isinstance(entity, Arc):
                    pc_tag = point_cache.get_or_create(entity.center, base_lc)
                    c_tag = gmsh.model.geo.add_circle_arc(p1_tag, pc_tag, p2_tag)

                if c_tag != -1:
                    curve_tags.append(c_tag)
                    # Sort by label
                    match entity.label:
                        case "inner":
                            tags_inner.append(c_tag)
                            # Register points if they lay at the inner boundary and are not in the list already
                            if p1_tag not in tags_inner_points: tags_inner_points.append(p1_tag)
                            if p2_tag not in tags_inner_points: tags_inner_points.append(p2_tag)
                        case "outer":
                            tags_outer.append(c_tag)

            if not curve_tags:
                raise ValueError("Failed to create any curves.")

            # 4. Create Surface
            loop_tag = gmsh.model.geo.add_curve_loop(curve_tags)
            surface_tag = gmsh.model.geo.add_plane_surface([loop_tag])

            # Generate points for rebar thermocouples
            rebar_pts = self._get_rebar_points(
                project=project,
                assume_symmetric=True,
                max_distance_between_points=project.thermocouple_distance
            )
            for pt in rebar_pts[1:-1]:  # Skip first and last (on boundary)
                pt_tag = point_cache.get_or_create(pt, base_lc)
                tags_rebar_points.append(pt_tag)

            # 5. Synchronization & Meshing
            gmsh.model.geo.synchronize()

            gmsh.model.mesh.embed(0, tags_rebar_points, 2, surface_tag)

            # PHYSICAL GROUPS
            # A. Domain (Surface)
            # The name "Beton" matches the material mapping.
            gmsh.model.add_physical_group(2, [surface_tag], name="Beton")

            # B. Boundaries
            if tags_inner:
                gmsh.model.add_physical_group(1, tags_inner, name="FIRE EXPOSED SIDE")

            # C. Thermocouple Points
            # C.1 Inner Boundary Points
            for i, pt_tag in enumerate(tags_inner_points):
                gmsh.model.add_physical_group(0, [pt_tag], name=f"THERMOCOUPLE - O{i+1}")

            tags_rebar_points.insert(0, point_cache.get(rebar_pts[0]))
            tags_rebar_points.append(point_cache.get(rebar_pts[-1]))
            for i, pt_tag in enumerate(tags_rebar_points):
                gmsh.model.add_physical_group(0, [pt_tag], name=f"THERMOCOUPLE - V{i+1}")

            # rebar_depth = getattr(project.geometry.parameters, "rebar_depth", 0.05)
            # thermocouple_tags = self._generate_thermocouple_points(loop, rebar_depth, point_cache, base_lc)
            # if thermocouple_tags:
            #     gmsh.model.add_physical_group(0, thermocouple_tags, name="THERMOCOUPLE")
            #     logger.info(f"Generated {len(thermocouple_tags)} thermocouple points at rebar depth {rebar_depth:.3f}m")


            if use_gradient and tags_inner:
                # Get thickness to scale the gradient field if needed
                geo = project.geometry
                thickness = getattr(geo.parameters, "thickness", 0.5)
                field_limit = max([thickness / 3, 0.3])  # Avoid too small values
                # 1. Distance field: Calc distance from inner boundary
                f_dist = gmsh.model.mesh.field.add("Distance")
                gmsh.model.mesh.field.set_numbers(f_dist, "CurvesList", tags_inner)
                # Sampling points for accuracy
                gmsh.model.mesh.field.set_number(f_dist, "Sampling", 100)

                # 2. Threshold field: Map distance to mesh size
                f_thresh = gmsh.model.mesh.field.add("Threshold")
                gmsh.model.mesh.field.set_number(f_thresh, "InField", f_dist)

                # Size constraints
                gmsh.model.mesh.field.set_number(f_thresh, "SizeMin", lc_min)
                gmsh.model.mesh.field.set_number(f_thresh, "SizeMax", lc_max)

                # Distance constraints
                # Within 0.0m to 0.15m from inner boundary -> SizeMin
                # From 0.15m to `field_lim` m -> Interpolate to SizeMax
                # Beyond `field_lim` m -> SizeMax
                gmsh.model.mesh.field.set_number(f_thresh, "DistMin", 0.15)
                gmsh.model.mesh.field.set_number(f_thresh, "DistMax", field_limit)

                # Apply as background field
                gmsh.model.mesh.field.set_as_background_mesh(f_thresh)

                # Disable general characteristic lengths options to let Field control sizing
                gmsh.option.setNumber("Mesh.CharacteristicLengthExtendFromBoundary", 0)
                gmsh.option.setNumber("Mesh.CharacteristicLengthFromPoints", 0)
                gmsh.option.setNumber("Mesh.CharacteristicLengthFromCurvature", 0)

                logger.info(f"Using mesh size gradient from {lc_min:.3f} (0.000 - 0.100) to {lc_max:.3f} (0.100 - {field_limit:.3f}).")
            else:
                # Standard uniform mesh size
                gmsh.option.set_number("Mesh.CharacteristicLengthMin", lc_min * 0.9)
                gmsh.option.set_number("Mesh.CharacteristicLengthMax", lc_min * 1.1)

            gmsh.model.mesh.generate(2)

            # 6. Extract statistics
            node_tags, _, _ = gmsh.model.mesh.get_nodes()
            num_nodes = len(node_tags)

            _, elem_tags, _ = gmsh.model.mesh.get_elements(dim=2)
            num_elements = len(elem_tags[0])

            # --- 7. Export to TEMP File (Hidden) ---
            temp_dir = tempfile.gettempdir()
            unique_name = f"mesh_{uuid.uuid4().hex}.msh"
            output_filename = os.path.join(temp_dir, unique_name)

            gmsh.write(output_filename)
            logger.info(f"Mesh generated at temp location: {output_filename}")

            # Register for cleanup (Delayed import to avoid circular dependency at module level)
            from temperatureanalysis.model.io import IOManager
            IOManager._TEMP_FILES.append(output_filename)

            logger.info(f"Mesh generated: {num_nodes} nodes, {num_elements} elements.")

            # gmsh.fltk.run()

            return MeshStats(
                filepath=output_filename,
                num_nodes=num_nodes,
                num_elements=num_elements,
            )

        except Exception as e:
            logger.exception("Gmsh generation failed")
            raise e

        finally:
            # Cleanup: Release memory and reset state
            if self._initialized:
                try:
                    gmsh.finalize()
                except Exception as finalize_error:
                    logger.warning(f"Failed to finalize Gmsh: {finalize_error}")
                finally:
                    self._initialized = False

    @staticmethod
    def _get_boundary_loop(
        project: ProjectState,
        assume_symmetric: bool = True,
        max_distance_between_points: Optional[float] = None,
    ) -> Optional[BoundaryLoop]:
        """
        Returns the boundary loop from the project geometry state.
        """
        geo = project.geometry

        # 1. Get the profile
        profile = geo.get_resolved_profile()
        if not profile:
            return None

        # Apply thickness
        thickness = getattr(geo.parameters, "thickness", 0.5)

        # Add rebar depth if available
        rebar_depth = getattr(geo.parameters, "rebar_depth", 0.1)

        return profile.get_combined_loop(
            user_thickness=thickness,
            rebar_depth=rebar_depth,
            assume_symmetric=assume_symmetric,
            max_distance_between_points=max_distance_between_points
        )

    @staticmethod
    def _get_rebar_points(
        project: ProjectState,
        assume_symmetric: bool = True,
        max_distance_between_points: Optional[float] = None,
    ) -> list[Point]:
        """
        Returns the points from the project geometry state.
        """
        geo = project.geometry

        # 1. Get the profile
        profile = geo.get_resolved_profile()
        if not profile:
            return []

        # Add rebar depth if available
        rebar_depth = getattr(geo.parameters, "rebar_depth", 0.1)

        return profile.get_rebar_points(
            rebar_depth=rebar_depth,
            assume_symmetric=assume_symmetric,
            max_length=max_distance_between_points
        )

