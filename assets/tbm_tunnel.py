from __future__ import annotations

from typing import TYPE_CHECKING

import gmsh
import itertools as it

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


def get_coordinates_on_circle(radius: float, num_points: int) -> npt.NDArray[np.float64]:
    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    x = radius * np.cos(angles)
    y = radius * np.sin(angles)
    z = np.zeros(num_points)

    return np.vstack((x, y, z)).T

def add_circle(radius: float, num_points: int, lc: float) -> tuple[int, list[int]]:
    points = get_coordinates_on_circle(radius, num_points)
    center_point_tag = gmsh.model.geo.add_point(0.0, 0.0, 0.0, lc)
    point_tags = []
    for x, y, z in points:
        tag = gmsh.model.geo.add_point(x, y, z, lc)
        point_tags.append(tag)

    circle_arc_tags = []
    for start_tag, end_tag in zip(point_tags, point_tags[1:] + [point_tags[0]]):
        arc_tag = gmsh.model.geo.add_circle_arc(start_tag, center_point_tag, end_tag)
        circle_arc_tags.append(arc_tag)

    curve_loop_tag = gmsh.model.geo.add_curve_loop(circle_arc_tags)

    return curve_loop_tag, circle_arc_tags

gmsh.initialize()
gmsh.model.add("TBM Tunnel")

LC = .5

# define center of the circle
center = gmsh.model.geo.add_point(0, 0, 0, LC)

# define inner and outer circle
inner_tag, inner_arc_tags = add_circle(4.8, 2, LC)
outer_tag, outer_arc_tags = add_circle(5.6, 2, LC)

# define tunnel wall
tunnel_wall_tag = gmsh.model.geo.add_plane_surface([outer_tag, inner_tag])

gmsh.model.geo.synchronize()
gmsh.model.mesh.generate(2)

gmsh.model.add_physical_group(1, inner_arc_tags, name="Inner Circle")
# gmsh.model.add_physical_group(1, outer_arc_tags, name="Outer Circle")
gmsh.model.add_physical_group(2, [tunnel_wall_tag], name="Domain")

types1, tags1, _ = gmsh.model.mesh.getElements(1)   # curves (1D)
types2, tags2, _ = gmsh.model.mesh.getElements(2)   # surface (2D)

element_tags = list(it.chain.from_iterable(tags1 + tags2))

old_tags, new_tags = gmsh.model.mesh.computeRenumbering(method="RCMK", elementTags=element_tags)
gmsh.model.mesh.renumberNodes(oldTags=old_tags, newTags=new_tags)

gmsh.write("TBM_tunnel.msh")

gmsh.fltk.run()
gmsh.finalize()



