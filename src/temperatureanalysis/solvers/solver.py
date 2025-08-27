from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import numpy as np
import scipy as sp

from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement
from temperatureanalysis.utils import assemble_subarray_at_indices

if TYPE_CHECKING:
    import numpy.typing as npt

    from temperatureanalysis.analysis.model import Model

# try:
#     import pypardiso
#     spsolve = pypardiso.spsolve
#     print("Using pypardiso as sparse linear solver.")
# except ImportError:
#     spsolve = sp.sparse.linalg.spsolve
#     print("Using scipy.sparse.linalg.spsolve as sparse linear solver.")

spsolve = sp.sparse.linalg.spsolve

class Solver:
    """
    Class for a FEM solver.
    """

    def __init__(
        self,
        model: Model,
    ) -> None:
        """
        Initialize the solver with a model.

        Args:
            model: The model to be solved.
        """
        self.model = model

    def _assemble_global_matrix(
        self,
        get_local_matrix: Callable[[FiniteElement], npt.NDArray[np.float64]]
    ) -> sp.sparse.coo_matrix[np.float64]:
        """
        Assemble a global matrix in CSR form for the model using a provided function to get the element matrix.

        Args:
            get_local_matrix:

        Returns:

        """
        row: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        col: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        data: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        for elements in self.model.mesh.elements.values():
            for element in elements:
                dofs = element.globals_dofs
                n_dofs = len(dofs)

                m_el = get_local_matrix(element)

                r = np.repeat(dofs, n_dofs)
                c = np.tile(dofs, n_dofs)

                row = np.hstack((row, r))
                col = np.hstack((col, c))
                data = np.hstack((data, m_el.flatten()))

        return sp.sparse.coo_matrix(
            (data, (row, col)),
            shape=(self.model.number_of_equations, self.model.number_of_equations)
        ).tocsr()


    def assemble_global_conductivity_matrix(self) -> None:
        """
        Assemble the global conductivity matrix [K] for the model.
        """
        self.model.k_global = self._assemble_global_matrix(
            get_local_matrix=lambda element: element.get_conductivity_matrix()
        )


    def assemble_global_capacity_matrix(self) -> None:
        """
        Assemble the global capacity matrix [C] for the model.
        """
        self.model.c_global = self._assemble_global_matrix(
            get_local_matrix=lambda element: element.get_capacity_matrix()
        )

    def assemble_load_vector(self, time: float) -> None:
        # q_global can be dense, because it's just length of number_of_equations
        self.model.q_global = np.zeros((self.model.number_of_equations,), dtype=np.float64)

        # dqdT_global have to be sparse, because it's number_of_equations x number_of_equations
        row: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        col: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        data: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)

        # self.model.dqdT_global = np.zeros((self.model.number_of_equations, self.model.number_of_equations), dtype=np.float64)
        temperature = self.model.fire_curve.get_temperature(time=time)
        for elements in self.model.mesh.boundary_elements.values():
            for element in elements:
                dofs = element.global_dofs
                n_dofs = len(dofs)

                self.model.q_global[dofs] += element.get_load_vector(temperature=temperature)

                # accumulate dqdT_el into global sparse triplets
                # (COO tolerates duplicates; .tocsr() will sum them)
                r = np.repeat(dofs, n_dofs)
                c = np.tile(dofs, n_dofs)

                row = np.hstack((row, r))
                col = np.hstack((col, c))
                data = np.hstack((data, element.get_load_vector_tangent().flatten()))

                # assemble_subarray_at_indices(
                #     array=self.model.dqdT_global,
                #     subarray=element.get_load_vector_tangent(),
                #     indices=dofs
                # )

        # finalize dqdT_global as sparse matrix
        self.model.dqdT_global = sp.sparse.coo_matrix(
            (data, (row, col)),
            shape=(self.model.number_of_equations, self.model.number_of_equations),
            dtype=np.float64
        ).tocsr()

    def solve(
        self,
        dt: float,
        total_time: float,
        initial_temperature: float = 20 + 273.15,
        tolerance: float = 1e-2,
        verbose: bool = False
    ) -> None:
        # Time step parameters
        current_time = 0.0
        step = 0
        inv_dt = 1.0 / dt

        # number of equations
        neq = self.model.number_of_equations

        # Initialize the global temperature vector with the initial temperature
        temp_old = np.full(
            (neq,),
            initial_temperature,
            dtype=np.float64
        )

        self.model.t_global = temp_old.copy()

        results = [temp_old.copy()]

        # Main time loop
        while current_time < total_time:
            current_time += dt
            step += 1

            temp_new = temp_old.copy()  # Initialize the next temperature vector

            # Assemble global matrices for this iteration
            self.assemble_global_conductivity_matrix()
            self.assemble_global_capacity_matrix()
            self.assemble_load_vector(time=current_time)

            K = self.model.k_global
            C = self.model.c_global
            F = self.model.q_global
            dFdT = self.model.dqdT_global

            dRdT = C * inv_dt + K + dFdT  # Residual derivative w.r.t. temperature

            # Reuse C.dot(temp_old)/dt inside Newton (It does not change during NR iterations)
            C_temp_old_over_dt = C.dot(temp_old) * inv_dt

            # R = (C.dot((temp_new - temp_old) / dt) + K.dot(temp_new) + F)
            R = C.dot(temp_new) * inv_dt
            R -= C_temp_old_over_dt
            R += K.dot(temp_new)
            R += F

            r_norm = np.linalg.norm(R, ord=np.inf)

            # Newton-Raphson iteration
            iteration = 0
            while r_norm > tolerance and iteration < 100:
                # solve dRdT * delta = -R
                delta = spsolve(dRdT, -R)
                temp_new += delta

                # Update nonlinear terms
                self.assemble_load_vector(time=current_time)

                F = self.model.q_global
                dFdT = self.model.dqdT_global

                # Update residual and its derivative
                dRdT = C * inv_dt + K + dFdT  # Residual derivative w.r.t. temperature

                R = C.dot(temp_new) * inv_dt
                R -= C_temp_old_over_dt
                R += K.dot(temp_new)
                R += F

                r_norm = np.linalg.norm(R, ord=np.inf)
                iteration += 1

                if iteration == 100:
                    raise RuntimeError(f"Newton-Raphson did not converge after {iteration} iterations at time {current_time:.2f} s.")

            # Save converged temperature
            results.append(temp_new.copy())
            temp_old = temp_new

            self.model.t_global = temp_new.copy()

            # assemble temperature to nodes
            for i, node in enumerate(self.model.mesh.nodes):
                node.current_temperature = temp_new[i]

            progress = int((current_time / total_time) * 100)
            print(f"Progress: {progress} % - Time: {current_time:.2f} s - Step: {step} - Residual Norm: {r_norm:.6f} - Iterations: {iteration}")
            # print(f"Step: {step} | Finished {progress} %")
            # vector = ' '.join(f"{x:.3f}" for x in F)
            # print(f"F: [{vector}]")
            # vector = ' '.join(f"{x:.3f}" for x in temp_new)
            # print(f"T: [{vector}]")
            # self.model.plot_temperature_distribution(time=current_time)
        # self.model.plot_temperature_distribution(time=current_time)






