"""
Application Initialization
==========================
This module constructs the MVC (Model-View-Controller) architecture and starts
the Qt Event Loop.

Why is this file needed?
------------------------
It acts as the "Dependency Injection" root. It:
1. Instantiates the Global Data Model (ProjectState).
2. Instantiates the Main Window (View).
3. Passes the Model into the View so they can communicate.
4. Prevents circular import errors by being the orchestrator.
"""
import logging
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLibraryInfo

from temperatureanalysis.logging_config import setup_logging
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.view.main_window import MainWindow


def main() -> None:
    # 1. Setup Logging (Console + Optional File)
    # Use logging.DEBUG to see everything during development
    # setup_logging(level=logging.DEBUG, log_file="app_debug.log")

    # 2. Create the Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("Tunel: Požár")

    # 3. Install Czech translations for Qt standard widgets (OK, Cancel, etc.)
    translator = QTranslator()
    translations_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if translator.load("qtbase_cs", translations_path):
        app.installTranslator(translator)
    else:
        # Fallback: try loading from Qt6 directory
        if translator.load("qtbase_cs", translations_path + "/Qt6"):
            app.installTranslator(translator)

    # 4. Initialize the Data Model
    project = ProjectState()

    # 5. Initialize the Main Window, passing the model
    window = MainWindow(project)
    window.show()

    # 6. Start Event Loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# from temperatureanalysis.dev import timer
# from temperatureanalysis.controller.fea.pre.material import Concrete, Steel, ThermalConductivityBoundary
# from temperatureanalysis.controller.fea.pre.mesh import Mesh
# from temperatureanalysis.controller.fea.pre.fire_curves import ISO834FireCurve
# from temperatureanalysis.controller.fea.analysis import Model
# from temperatureanalysis.controller.fea.solvers.solver import Solver
#
#
# @timer
# def main() -> None:
#
#     fire_curve = ISO834FireCurve()
#
#     # mesh = Mesh.from_file("../../assets/TBM_tunnel.msh")
#     # mesh = Mesh.from_file("../../assets/TBM_tunnel_invert.msh")
#     # mesh = Mesh.from_file("../../assets/PENTA.msh")
#     # mesh = Mesh.from_file("../../assets/rectangle-fine-elements.msh")
#     uhpc = Concrete(
#         initial_density=2450.0,
#         boundary=ThermalConductivityBoundary.UPPER,
#     )
#
#     concrete = Concrete(
#         initial_density=2300.0,
#         boundary=ThermalConductivityBoundary.UPPER,
#     )
#
#     steel = Steel()
#
#     mesh = Mesh.from_file(
#         filename="../../assets/masaryk_with_slab.msh",
#         physical_surface_to_material_mapping={
#             "UHPC": uhpc,
#             "CONCRETE": concrete,
#             "TENDONS": steel,  # Assuming tendons have the same properties as concrete for this example
#         },
#         physical_line_to_fire_curve_mapping={'FIRE EXPOSED SIDE': fire_curve}
#     )
#     # mesh.plot()
#
#
#
#     model = Model(mesh=mesh)
#
#     solver = Solver(model)
#
#     tot_time = 60.0 * 180  # total simulation time in seconds
#
#     solver.solve(dt=30.0, total_time=tot_time)
#     # solver.solve(dt=30.0, total_time=30.0*6)
#
#     model.plot_temperature_distribution(time=tot_time)
#
#     for thermocouple_name, node in mesh.thermocouples.items():
#         node.plot_temperature_history(30, thermocouple_name)
#
# if __name__ == "__main__":
#     # main()
#     # cProfile.run("main()", filename="profile.prof")
#     # #
#     # Load and inspect the stats
#     # stats = pstats.Stats("profile.prof")
#     # # stats.strip_dirs()  # remove extraneous path info
#     # stats.sort_stats("tottime")  # sort by total time spent in function
#     # stats.print_stats(50)  # show top 50 slowest functions
#
#     import pyvista as pv
#
#     draw_isotherm = True
#     draw_mesh = True
#     draw_temperature = True
#
#     # Load mesh
#     grid = pv.read("../../assets/temperature_10800s.vtu")
#     # grid = pv.read("../../assets/temperature_30s.vtu")
#
#     # Create a plotter
#     plotter = pv.Plotter()
#
#     # Add mesh with edges and temperature colormap
#     if draw_temperature:
#         scalars = "temperature"
#     else:
#         scalars = None
#     plotter.add_mesh(
#         grid,
#         scalars=scalars,
#         cmap="jet",
#         show_edges=draw_mesh,
#         line_width=0.01,
#         edge_color='grey',
#         scalar_bar_args={
#             "title": "Temperature (°C)",
#             "vertical": True,
#             "fmt": "%.0f",
#             "position_x": 0.85,
#             "position_y": 0.5,
#         },
#         interpolate_before_map=True,
#     )
#
#     if draw_isotherm and draw_temperature:
#         # Generate contour lines at default levels
#         levels = [350, 500]
#         isolines = grid.contour(isosurfaces=levels, scalars="temperature")
#
#         # Add them as black isolines
#         plotter.add_mesh(
#             isolines,
#             color="black",
#             line_width=1.5,
#             show_scalar_bar=False,
#             render_lines_as_tubes=True  # nicer visibility
#         )
#
#         # Add labels manually
#         for value in levels:
#             # Extract only the polyline(s) for this isovalue
#             iso = grid.contour(isosurfaces=[value], scalars="temperature")
#
#             # Take the first point of the isoline
#             if iso.n_points > 0:
#                 idx = iso.n_points // 2
#                 point = iso.points[idx]
#
#                 plotter.add_point_labels(
#                     point,
#                     [f"{value}°C"],
#                     font_size=12,
#                     text_color="black",
#                     fill_shape=True,
#                     always_visible=True,
#                 )
#
#     plotter.enable_parallel_projection()
#     plotter.view_xy()
#     plotter.enable_image_style()
#     plotter.show()


