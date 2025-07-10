import gmsh

X = 0.2
Y = 0.3

N_X = 3
N_Y = 4

for coefficient, name in zip([1], ["rectangle-coarse-elements"]):

    gmsh.initialize()

    gmsh.model.add(f"{name}")

    lc = 0.1

    gmsh.model.geo.add_point(0, 0, 0, lc, 1)
    gmsh.model.geo.add_point(X, 0, 0, lc, 2)
    gmsh.model.geo.add_point(X, Y, 0, lc, 3)
    gmsh.model.geo.add_point(0, Y, 0, lc, 4)

    line1 = gmsh.model.geo.add_line(1, 2, 1)
    line2 = gmsh.model.geo.add_line(2, 3, 2)
    line3 = gmsh.model.geo.add_line(3, 4, 3)
    line4 = gmsh.model.geo.add_line(4, 1, 4)

    gmsh.model.geo.mesh.set_transfinite_curve(line1, N_X * coefficient)
    gmsh.model.geo.mesh.set_transfinite_curve(line2, N_Y * coefficient)
    gmsh.model.geo.mesh.set_transfinite_curve(line3, N_X * coefficient)
    gmsh.model.geo.mesh.set_transfinite_curve(line4, N_Y * coefficient)

    gmsh.model.geo.add_curve_loop([1, 2, 3, 4], 1)
    gmsh.model.geo.add_plane_surface([1], 1)

    gmsh.model.add_physical_group(1, [1], name="Bottom")
    gmsh.model.add_physical_group(1, [2], name="Right")
    gmsh.model.add_physical_group(1, [3], name="Top")
    gmsh.model.add_physical_group(1, [4], name="Left")

    gmsh.model.add_physical_group(2, [1], name="Domain")

    gmsh.model.geo.mesh.set_transfinite_surface(1, "Left", [1, 2, 3, 4])

    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(2)

    old_tags, new_tags = gmsh.model.mesh.computeRenumbering(method="RCMK", elementTags=[])
    print("old_tags:", old_tags[:10])
    print("new_tags:", new_tags[:10])

    gmsh.model.mesh.renumberNodes(oldTags=old_tags, newTags=new_tags)

    gmsh.option.setNumber("Mesh.PreserveNumberingMsh2", 0)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(f"{name}.msh")
    # gmsh.fltk.run()

    gmsh.finalize()
