import gmsh
from math import sin, cos, radians

gmsh.initialize()
LC = 0.1

arc_segments = [
    # radius, angle in degrees
    [3.750, 70.05],
    [8.000, 41.613],
    [1.530, 52.6],
    [9.650, 180-70.05-41.613-52.6]
]

# Calculate start, end and center points of each arc segment
arc_points = []
current_angle = 90.0  # Starting from the top (90 degrees)

tag = 0

prev_end_x = 0
prev_end_y = 0

for radius, angle in arc_segments:
    start_angle = current_angle
    end_angle = current_angle + angle

    center_x = prev_end_x - radius * cos(radians(start_angle))
    center_y = prev_end_y - radius * sin(radians(start_angle))
    center_point = gmsh.model.geo.add_point(center_x, center_y, 0, LC, tag)
    tag += 1

    start_x = center_x + radius * cos(radians(start_angle))
    start_y = center_y + radius * sin(radians(start_angle))
    start_point = gmsh.model.geo.add_point(start_x, start_y, 0, LC, tag)
    tag += 1

    end_x = center_x + radius * cos(radians(end_angle))
    end_y = center_y + radius * sin(radians(end_angle))
    prev_end_x = end_x
    prev_end_y = end_y
    end_point = gmsh.model.geo.add_point(end_x, end_y, 0, LC, tag)
    tag += 1

    gmsh.model.geo.add_circle_arc(tag-2, tag-3, tag-1)

    current_angle = end_angle

    center_point = gmsh.model.geo.add_point(-center_x, center_y, 0, LC, tag)
    tag += 1

    start_point = gmsh.model.geo.add_point(-start_x, start_y, 0, LC, tag)
    tag += 1

    end_point = gmsh.model.geo.add_point(-end_x, end_y, 0, LC, tag)
    tag += 1
    gmsh.model.geo.add_circle_arc(tag - 2, tag - 3, tag - 1)


gmsh.model.geo.synchronize()
gmsh.fltk.run()
gmsh.finalize()
