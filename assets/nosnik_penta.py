import gmsh

LC = 0.2

gmsh.initialize()
gmsh.model.add("PENTA")

# define points
pt1 = gmsh.model.geo.add_point(0.01, 0.9, 0.0, LC)
pt2 = gmsh.model.geo.add_point(0.0, 0.89, 0.0, LC)
pt3 = gmsh.model.geo.add_point(0.0, 0.71, 0.0, LC)
pt4 = gmsh.model.geo.add_point(0.1, 0.64, 0.0, LC)
pt5 = gmsh.model.geo.add_point(0.1, 0.01, 0.0, LC)
pt6 = gmsh.model.geo.add_point(0.11, 0.0, 0.0, LC)
pt7 = gmsh.model.geo.add_point(0.83, 0.0, 0.0, LC)
pt8 = gmsh.model.geo.add_point(0.84, 0.01, 0.0, LC)
pt9 = gmsh.model.geo.add_point(0.84, 0.64, 0.0, LC)
pt10 = gmsh.model.geo.add_point(0.94, 0.71, 0.0, LC)
pt11 = gmsh.model.geo.add_point(0.94, 0.89, 0.0, LC)
pt12 = gmsh.model.geo.add_point(0.93, 0.9, 0.0, LC)

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
line12 = gmsh.model.geo.add_line(pt12, pt1)

curve_loop = gmsh.model.geo.add_curve_loop(
    [line1, line2, line3, line4, line5, line6, line7, line8, line9, line10, line11, line12])

surface = gmsh.model.geo.add_plane_surface([curve_loop])

gmsh.model.geo.synchronize()

gmsh.model.add_physical_group(
    dim=1,
    tags=[line1, line2, line3, line4, line5, line6, line7, line8, line9, line10, line11],
    name="Fire side"
)

gmsh.model.add_physical_group(
    dim=2,
    tags=[surface],
    name="Domain"
)
gmsh.model.mesh.generate(2)

old_tags, new_tags = gmsh.model.mesh.computeRenumbering(method="RCMK", elementTags=[])
print("old_tags:", old_tags[:10])
print("new_tags:", new_tags[:10])

gmsh.model.mesh.renumberNodes(oldTags=old_tags, newTags=new_tags)

gmsh.write("PENTA.msh")

gmsh.fltk.run()
gmsh.finalize()
