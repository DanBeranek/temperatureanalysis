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

import gmsh
import os
from typing import Dict, Tuple, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

from temperatureanalysis.model.profiles import (
    ALL_PROFILES, TunnelProfile, TunnelOutline
)
from temperatureanalysis.model.geometry_primitives import Point, Line, Arc, BoundaryLoop

if TYPE_CHECKING:
    from temperatureanalysis.model.state import ProjectState


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
        # Using 6 decimals allows for sub-millimeter precision which is fine for tunnels
        key = (round(pt.x, 6), round(pt.y, 6))

        if key in self.cache:
            return self.cache[key]

        # Create new point in Gmsh
        # tag = gmsh.model.geo.addPoint(x, y, z, mesh_size)
        tag = gmsh.model.geo.addPoint(pt.x, pt.y, 0.0, mesh_size)
        self.cache[key] = tag
        return tag


class GmshMesher:
    def __init__(self):
        self._initialized = False

    def _ensure_init(self):
        if not self._initialized:
            gmsh.initialize()
            self._initialized = True

    def generate_mesh(self, project: ProjectState, mesh_size: float = 0.5) -> MeshStats:
        """
        Generates a 2D mesh from the project geometry.
        Returns the path to the generated .msh file.
        """
        self._ensure_init()
        gmsh.model.add("Tunel")

        # 1. Clear previous geometry
        gmsh.clear()

        # 2. Get the geometry loop
        loop = self._get_boundary_loop(project)

        if not loop or not loop.entities:
            raise ValueError("No valid geometry found to mesh.")

        # 3. Translate to GMSH
        point_cache = PointCache()
        curve_tags: list[int] = []

        # Categories for Physical Groups
        tags_inner = []
        tags_outer = []

        try:
            for entity in loop.entities:
                p1_tag = point_cache.get_or_create(entity.start, mesh_size)
                p2_tag = point_cache.get_or_create(entity.end, mesh_size)
                c_tag = -1

                if isinstance(entity, Line):
                    c_tag = gmsh.model.geo.add_line(p1_tag, p2_tag)
                if isinstance(entity, Arc):
                    pc_tag = point_cache.get_or_create(entity.center, mesh_size)
                    c_tag = gmsh.model.geo.add_circle_arc(p1_tag, pc_tag, p2_tag)

                if c_tag != -1:
                    curve_tags.append(c_tag)
                    # Sort by label
                    match entity.label:
                        case "inner":
                            tags_inner.append(c_tag)
                        case "outer":
                            tags_outer.append(c_tag)

            if not curve_tags:
                raise ValueError("Failed to create any curves.")

            # 4. Create Surface
            loop_tag = gmsh.model.geo.add_curve_loop(curve_tags)
            surface_tag = gmsh.model.geo.add_plane_surface([loop_tag])

            # PHYSICAL GROUPS
            # A. Domain (Surface)
            # The name "Beton" matches the material mapping.
            gmsh.model.add_physical_group(2, [surface_tag], name="Beton")

            # B. Boundaries
            if tags_inner:
                gmsh.model.add_physical_group(1, tags_inner, name="FIRE EXPOSED SIDE")

            # 5. Synchronization & Meshing
            gmsh.model.geo.synchronize()
            gmsh.option.set_number("Mesh.CharacteristicLengthMin", mesh_size * 0.9)
            gmsh.option.set_number("Mesh.CharacteristicLengthMax", mesh_size * 1.1)
            gmsh.model.mesh.generate(2)

            # 6. Extract statistics
            node_tags, _, _ = gmsh.model.mesh.get_nodes()
            num_nodes = len(node_tags)

            _, elem_tags, _ = gmsh.model.mesh.get_elements(dim=2)
            num_elements = len(elem_tags[0])

            # 7. Export
            if project.filepath:
                # If project is "C:/Data/Tunnel.h5", output becomes "C:/Data/Tunnel-mesh.msh"
                base_name = os.path.splitext(os.path.basename(project.filepath))[0]
                output_filename = f"{base_name}-mesh.msh"
            else:
                # Fallback for unsaved project
                output_filename = "tunel-mesh.msh"

            gmsh.write(output_filename)

            # gmsh.fltk.run()

            return MeshStats(
                filepath=output_filename,
                num_nodes=num_nodes,
                num_elements=num_elements,
            )

        except Exception as e:
            print(f"Gmsh Error: {e}")
            raise e

        finally:
            # Cleanup: Release memory and reset state
            gmsh.finalize()
            self._initialized = False

    @staticmethod
    def _get_boundary_loop(project: ProjectState) -> Optional[BoundaryLoop]:
        """
        Returns the boundary loop from the project geometry state.
        """
        geo = project.geometry

        # 1. Get the profile
        profile = geo.get_resolved_profile()
        if not profile:
            return None

        # Apply thickness
        thickness = getattr(geo.parameters, "thickness", 20)

        return profile.get_combined_loop(user_thickness=thickness)
