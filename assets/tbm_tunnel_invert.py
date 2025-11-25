from __future__ import annotations

from typing import TYPE_CHECKING

import gmsh
import itertools as it

import numpy as np

from temperatureanalysis.app.ui.panels.geometry_editors.math_utils import line_circle_intersection

if TYPE_CHECKING:
    import numpy.typing as npt


def get_coordinates_on_circle(center: tuple[float, float], radius: float, num_points: int) -> npt.NDArray[np.float64]:
    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    x = center[0] + radius * np.cos(angles)
    y = center[1] + radius * np.sin(angles)
    z = np.zeros(num_points)

    return np.vstack((x, y, z)).T

def add_circle(center: tuple[float, float], radius: float, num_points: int, lc: float) -> tuple[int, list[int]]:
    points = get_coordinates_on_circle(center, radius, num_points)
    center_point_tag = gmsh.model.geo.add_point(center[0], center[1], 0.0, lc)
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
gmsh.model.add("TBM Tunnel with invert")

LC = .4

d = 8.0
t = 0.6
cx = 0.5
cy = 2.6
tw = 3.0
tb = -0.4
lh = 0.15
rh = -0.14
ls = 3.0 / 100.0
rs = 3.0 / 100.0

r_inner = d / 2
r_outer = r_inner + t

p2 = (-tw / 2, lh)
p3 = (-tw / 2, tb)
p4 = (+tw / 2, tb)
p5 = (+tw / 2, rh)

p_left = (-tw / 2 - 2 * r_inner, lh + 2 * ls * r_inner)
p_right = (+tw / 2 + 2 * r_inner, rh + 2 * rs * r_inner)

p1 = line_circle_intersection(p2, (p_left[0] - p2[0], p_left[1] - p2[1]), (cx, cy), r_inner, as_segment=True)[0]
p6 = line_circle_intersection(p5, (p_right[0] - p5[0], p_right[1] - p5[1]), (cx, cy), r_inner, as_segment=True)[0]

# define center of the circle
center = gmsh.model.geo.add_point(cx, cy, 0, LC)
p1 = gmsh.model.geo.add_point(p1[0], p1[1], 0, LC)
p2 = gmsh.model.geo.add_point(p2[0], p2[1], 0, LC)
p3 = gmsh.model.geo.add_point(p3[0], p3[1], 0, LC)
p4 = gmsh.model.geo.add_point(p4[0], p4[1], 0, LC)
p5 = gmsh.model.geo.add_point(p5[0], p5[1], 0, LC)
p6 = gmsh.model.geo.add_point(p6[0], p6[1], 0, LC)

l1 = gmsh.model.geo.add_line(p2, p1)
l2 = gmsh.model.geo.add_line(p3, p2)
l3 = gmsh.model.geo.add_line(p4, p3)
l4 = gmsh.model.geo.add_line(p5, p4)
l5 = gmsh.model.geo.add_line(p6, p5)

# point on inner arc
p7 = gmsh.model.geo.add_point(cx + r_inner, cy, 0, LC)
p8 = gmsh.model.geo.add_point(cx, cy + r_inner, 0, LC)
p9 = gmsh.model.geo.add_point(cx - r_inner, cy, 0, LC)
p10 = gmsh.model.geo.add_point(cx, cy - r_inner, 0, 10*LC)

# add inner arcs
a1 = gmsh.model.geo.add_circle_arc(p7, center, p8)
a2 = gmsh.model.geo.add_circle_arc(p8, center, p9)
a3 = gmsh.model.geo.add_circle_arc(p9, center, p1)
a4 = gmsh.model.geo.add_circle_arc(p1, center, p10)
a5 = gmsh.model.geo.add_circle_arc(p10, center, p6)
a6 = gmsh.model.geo.add_circle_arc(p6, center, p7)

# define inner and outer circle
# inner_tag, inner_arc_tags = add_circle(4.8, 2, LC)
inner_circle_tags = [a1, a2, a3, a4, a5, a6]
inner_circle_loop_tag = gmsh.model.geo.add_curve_loop(inner_circle_tags)

invert_tags = [a4, a5, l5, l4, l3, l2, l1]
invert_circle_loop_tag = gmsh.model.geo.add_curve_loop(invert_tags)

outer_tag, outer_arc_tags = add_circle((cx, cy), r_outer, 2, 10*LC)
#
# # define tunnel wall
tunnel_wall_tag = gmsh.model.geo.add_plane_surface([outer_tag, inner_circle_loop_tag])
invert_tag = gmsh.model.geo.add_plane_surface([invert_circle_loop_tag])
#
gmsh.model.geo.synchronize()
gmsh.model.mesh.generate(2)
#
gmsh.model.add_physical_group(1, [
    a1, a2, a3, a6, l1, l2, l3, l4, l5
], name="Inner Circle")
# # gmsh.model.add_physical_group(1, outer_arc_tags, name="Outer Circle")
gmsh.model.add_physical_group(2, [tunnel_wall_tag, invert_tag], name="Domain")
#
types1, tags1, _ = gmsh.model.mesh.getElements(1)   # curves (1D)
types2, tags2, _ = gmsh.model.mesh.getElements(2)   # surface (2D)

element_tags = list(it.chain.from_iterable(tags1 + tags2))

old_tags, new_tags = gmsh.model.mesh.computeRenumbering(method="RCMK", elementTags=element_tags)
gmsh.model.mesh.renumberNodes(oldTags=old_tags, newTags=new_tags)

gmsh.write("TBM_tunnel_invert.msh")

gmsh.fltk.run()
gmsh.finalize()



