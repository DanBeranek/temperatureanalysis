import gmsh

import itertools as it

import numpy as np
import numpy.typing as npt

def get_coordinates_on_circle(center: tuple[float, float], radius: float, num_points: int) -> npt.NDArray[np.float64]:
    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    x = center[0] + radius * np.cos(angles)
    y = center[1] + radius * np.sin(angles)
    z = np.zeros(num_points)

    return np.vstack((x, y, z)).T

def add_circle(center: tuple[float, float], radius: float, num_points: int) -> tuple[int, list[int]]:
    points = get_coordinates_on_circle(center, radius, num_points)
    center_point_tag = gmsh.model.geo.add_point(center[0], center[1], 0.0)
    point_tags = []
    for x, y, z in points:
        tag = gmsh.model.geo.add_point(x, y, z)
        point_tags.append(tag)

    circle_arc_tags = []
    for start_tag, end_tag in zip(point_tags, point_tags[1:] + [point_tags[0]]):
        arc_tag = gmsh.model.geo.add_circle_arc(start_tag, center_point_tag, end_tag)
        circle_arc_tags.append(arc_tag)

    curve_loop_tag = gmsh.model.geo.add_curve_loop(circle_arc_tags)

    return curve_loop_tag, circle_arc_tags

LC = 0.2

gmsh.initialize()
gmsh.model.add("Masarykovo nádraží")

# define points
pt1 = gmsh.model.geo.add_point(0.01, 0.9, 0.0)
pt2 = gmsh.model.geo.add_point(0.00, 0.89, 0.0)
pt3 = gmsh.model.geo.add_point(0.00, 0.71, 0.0)
pt4 = gmsh.model.geo.add_point(0.10, 0.64, 0.0)
pt5 = gmsh.model.geo.add_point(0.10, 0.01, 0.0)
pt6 = gmsh.model.geo.add_point(0.11, 0.0, 0.0)
pt7 = gmsh.model.geo.add_point(0.83, 0.0, 0.0)
pt8 = gmsh.model.geo.add_point(0.84, 0.01, 0.0)
pt9 = gmsh.model.geo.add_point(0.84, 0.64, 0.0)
pt10 = gmsh.model.geo.add_point(0.94, 0.71, 0.0)
pt11 = gmsh.model.geo.add_point(0.94, 0.89, 0.0)
pt12 = gmsh.model.geo.add_point(0.93, 0.90, 0.0)
pt13 = gmsh.model.geo.add_point(0.73, 0.90, 0.0)
pt14 = gmsh.model.geo.add_point(0.72, 0.89, 0.0)
pt15 = gmsh.model.geo.add_point(0.72, 0.14, 0.0)
pt16 = gmsh.model.geo.add_point(0.70, 0.12, 0.0)
pt17 = gmsh.model.geo.add_point(0.24, 0.12, 0.0)
pt18 = gmsh.model.geo.add_point(0.22, 0.14, 0.0)
pt19 = gmsh.model.geo.add_point(0.22, 0.89, 0.0)
pt20 = gmsh.model.geo.add_point(0.21, 0.9, 0.0)

line1 = gmsh.model.geo.add_line(pt1, pt2)
line2 = gmsh.model.geo.add_line(pt2, pt3)
line3 = gmsh.model.geo.add_line(pt3, pt4)
line4 = gmsh.model.geo.add_line(pt4, pt5)
line5 = gmsh.model.geo.add_line(pt5, pt6)
line6 = gmsh.model.geo.add_line(pt6, pt7)
line7 = gmsh.model.geo.add_line(pt7, pt8)
line8 = gmsh.model.geo.add_line(pt8, pt9)
line9 = gmsh.model.geo.add_line(pt9, pt10)
line10 = gmsh.model.geo.add_line(pt10, pt11)
line11 = gmsh.model.geo.add_line(pt11, pt12)
line12 = gmsh.model.geo.add_line(pt12, pt13)
line13 = gmsh.model.geo.add_line(pt13, pt14)
line14 = gmsh.model.geo.add_line(pt14, pt15)
line15 = gmsh.model.geo.add_line(pt15, pt16)
line16 = gmsh.model.geo.add_line(pt16, pt17)
line17 = gmsh.model.geo.add_line(pt17, pt18)
line18 = gmsh.model.geo.add_line(pt18, pt19)
line19 = gmsh.model.geo.add_line(pt19, pt20)
line20 = gmsh.model.geo.add_line(pt20, pt1)
line21 = gmsh.model.geo.add_line(pt13, pt20)

uhpc_curve_loop = gmsh.model.geo.add_curve_loop(
    [
        line1, line2, line3, line4, line5, line6, line7, line8, line9, line10, line11, line12,
        line13, line14, line15, line16, line17, line18, line19, line20
    ])

concrete_curve_loop = gmsh.model.geo.add_curve_loop(
    [
        line13, line14, line15, line16, line17, line18, line19, -line21
    ]
)

# uhpc_center_left = gmsh.model.geo.add_point(0.11, 0.8, 0.0)
# uhpc_center_right = gmsh.model.geo.add_point(0.83, 0.8, 0.0)
# concrete_center_left = gmsh.model.geo.add_point(0.27, 0.371, 0.0)
# concrete_center_middle = gmsh.model.geo.add_point(0.47, 0.371, 0.0)
# concrete_center_right = gmsh.model.geo.add_point(0.67, 0.371, 0.0)

uhpc_center_left_tag, uhpc_center_left_arc_tags = add_circle((0.11, 0.8), 0.05, 2)
uhpc_center_right_tag, uhpc_center_right_arc_tags = add_circle((0.83, 0.8), 0.05, 2)

uhpc_surface = gmsh.model.geo.add_plane_surface([uhpc_curve_loop, uhpc_center_left_tag, uhpc_center_right_tag])


concrete_center_left_tag, concrete_center_left_arc_tags = add_circle((0.271, 0.371), 0.05, 2)
concrete_center_middle_tag, concrete_center_middle_arc_tags = add_circle((0.470, 0.371), 0.05, 2)
concrete_center_right_tag, concrete_center_right_arc_tags = add_circle((0.669, 0.371), 0.05, 2)

cast_in_surface = gmsh.model.geo.add_plane_surface([
    concrete_curve_loop,
    concrete_center_left_tag,
    concrete_center_middle_tag,
    concrete_center_right_tag
])

uhpc_left_tendons = gmsh.model.geo.add_plane_surface([uhpc_center_left_tag])
uhpc_right_tendons = gmsh.model.geo.add_plane_surface([uhpc_center_right_tag])
concrete_left_tendons = gmsh.model.geo.add_plane_surface([concrete_center_left_tag])
concrete_middle_tendons = gmsh.model.geo.add_plane_surface([concrete_center_middle_tag])
concrete_right_tendons = gmsh.model.geo.add_plane_surface([concrete_center_right_tag])

point_A = gmsh.model.geo.add_point(0.11, 0.8, 0.0)
point_B = gmsh.model.geo.add_point(0.27, 0.371, 0.0)

gmsh.model.geo.synchronize()
#
gmsh.model.mesh.embed(0, [point_A], 2, uhpc_left_tendons)
gmsh.model.mesh.embed(0, [point_B], 2, concrete_left_tendons)

gmsh.model.add_physical_group(
    dim=0,
    tags=[point_A],
    name="THERMOCOUPLE - UHPC"
)

gmsh.model.add_physical_group(
    dim=0,
    tags=[point_B],
    name="THERMOCOUPLE - CONCRETE"
)

gmsh.model.add_physical_group(
    dim=1,
    tags=[line1, line2, line3, line4, line5, line6, line7, line8, line9, line10, line11],
    name="FIRE EXPOSED SIDE"
)

gmsh.model.add_physical_group(
    dim=2,
    tags=[uhpc_surface],
    name="UHPC"
)

gmsh.model.add_physical_group(
    dim=2,
    tags=[cast_in_surface],
    name="CONCRETE"
)

gmsh.model.add_physical_group(
    dim=2,
    tags=[uhpc_left_tendons, uhpc_right_tendons, concrete_left_tendons, concrete_middle_tendons, concrete_right_tendons],
    name="TENDONS"
)

gmsh.option.set_number("Mesh.CharacteristicLengthMin", LC)
gmsh.option.set_number("Mesh.CharacteristicLengthMax", LC)

gmsh.model.mesh.generate(2)

types1, tags1, _ = gmsh.model.mesh.getElements(1)   # curves (1D)
types2, tags2, _ = gmsh.model.mesh.getElements(2)   # surface (2D)

element_tags = list(it.chain.from_iterable(tags1 + tags2))

old_tags, new_tags = gmsh.model.mesh.computeRenumbering(method="RCMK", elementTags=element_tags)
print("old_tags:", old_tags[:10])
print("new_tags:", new_tags[:10])

gmsh.model.mesh.renumberNodes(oldTags=old_tags, newTags=new_tags)

gmsh.write("masaryk.msh")

gmsh.fltk.run()
gmsh.finalize()
