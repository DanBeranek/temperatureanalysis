"""Command-line interface."""
from temperatureanalysis.dev import timer
from temperatureanalysis.fea.pre import Mesh
from temperatureanalysis.fea.pre import ISO834FireCurve
from temperatureanalysis.fea.analysis import Model
from temperatureanalysis.fea.solvers import Solver

import cProfile


@timer
def main() -> None:
    mesh = Mesh.from_file("../../assets/TBM_tunnel.msh")
    # mesh = Mesh.from_file("../../assets/rectangle-fine-elements.msh")
    # mesh.plot()

    fire_curve = ISO834FireCurve()

    model = Model(mesh=mesh, fire_curve=fire_curve)

    solver = Solver(model)

    solver.solve(dt=30.0, total_time=30.0*180)
    # solver.solve(dt=30.0, total_time=30.0*6)

if __name__ == "__main__":
    # main()
    cProfile.run("main()", filename="profile.prof")
    # #
    # Load and inspect the stats
    # stats = pstats.Stats("profile.prof")
    # # stats.strip_dirs()  # remove extraneous path info
    # stats.sort_stats("tottime")  # sort by total time spent in function
    # stats.print_stats(50)  # show top 50 slowest functions

    import pyvista as pv

    # Load mesh
    grid = pv.read("../../assets/temperature_10800s.vtu")

    # Create a plotter
    plotter = pv.Plotter()

    # Add mesh with edges and temperature colormap
    plotter.add_mesh(
        grid,
        scalars="temperature",
        cmap="jet",
        show_edges=False,
        line_width=0.01,
        scalar_bar_args={
            "title": "Temperature (°C)",
            "vertical": True,
            "fmt": "%.0f",
            "position_x": 0.85,
            "position_y": 0.5,
        },
        interpolate_before_map=True,
    )

    plotter.show()


