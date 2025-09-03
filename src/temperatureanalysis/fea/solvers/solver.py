from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import numpy as np
import scipy as sp

from temperatureanalysis.fea.analysis import FiniteElement

from temperatureanalysis.fea.utils import flatten_groups_in_order

if TYPE_CHECKING:
    import numpy.typing as npt

    from temperatureanalysis.fea.analysis import Model

try:
    import pypardiso
    spsolve = pypardiso.spsolve
    print("Using pypardiso as sparse linear solver.")
except ImportError:
    spsolve = sp.sparse.linalg.spsolve
    print("Using scipy.sparse.linalg.spsolve as sparse linear solver.")

# spsolve = sp.sparse.linalg.spsolve

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

        self._surface_elements = flatten_groups_in_order(self.model.mesh.elements)
        self._boundary_elements = flatten_groups_in_order(self.model.mesh.boundary_elements)

        self.neq = self.model.number_of_equations

        # Precompute sparsity pattern and scatter vectors for surface elements (used in K and C)
        self._A_struct, self._A_scatter = self._precompute_pattern_and_scatter(elements=self._surface_elements)

        # Keep persistent copy of the structure for reuse
        self._K = self._A_struct.copy()
        self._C = self._A_struct.copy()

        #Precompute sparsity pattern and scatter vectors for boundary elements (used in dqdT)
        self._D_struct, self._D_scatter = self._precompute_pattern_and_scatter(elements=self._boundary_elements)
        self._dqdT = self._D_struct.copy()

    def _precompute_pattern_and_scatter(self, elements: list) -> tuple[sp.sparse.csr_matrix, list[npt.NDArray[np.int64]]]:
        """
        Precompute the sparsity pattern of the global matrices and the scatter vectors for each element.

        Returns:
            A_template: csr_matrix with correct indptr/indices (float64 data, zeros).
            scatter_list: list of 1D arrays; for element e, scatter_list[e] gives
                          data indices in A_template.data where Ke.ravel(order="C") adds.
                          Length of each entry is (n_dofs, n_dofs) for element with n_dofs.
        """
        # 1) Build the sparsity pattern via COO triplets
        row_parts: list[npt.NDArray[np.int64]] = []
        col_parts: list[npt.NDArray[np.int64]] = []

        element_dofs: list[npt.NDArray[np.int64]] = []
        for element in elements:
            dofs = element.global_dofs
            element_dofs.append(dofs)
            n_dofs = dofs.size

            row_parts.append(np.repeat(dofs, n_dofs))
            col_parts.append(np.tile(dofs, n_dofs))

        if not element_dofs:
            raise ValueError("No elements found in the model mesh.")

        rows = np.concatenate(row_parts)
        cols = np.concatenate(col_parts)

        # Use ones for a boolean-like pattern
        neq = self.model.number_of_equations
        pattern = sp.sparse.coo_matrix(
            (
                np.ones_like(rows, dtype=np.int8),
                (rows, cols),
            ),
            shape=(neq, neq)
        ).tocsr()

        # Cast to float64 data with zeros, keep structure
        A_template = pattern.astype(np.float64, copy=True)
        A_template.data[:] = 0.0

        # 2) For each element, find where each (row, col) lives in A_template.data
        indptr, indices = A_template.indptr, A_template.indices
        scatter_list: list[npt.NDArray[np.int64]] = []

        for dofs in element_dofs:
            n_dofs = dofs.size
            scatter_e = np.empty(n_dofs * n_dofs, dtype=np.int64)

            # For each row r in this element, search columns in that CSR row
            pos = 0
            for ii, r in enumerate(dofs):
                a, b = indptr[r], indptr[r + 1]  # indices[a:b] sorted
                # positions of all dofs within this row:
                # searchsorted gives offsets inside indices[a:b]
                offs = np.searchsorted(indices[a:b], dofs)
                scatter_e[pos:pos + n_dofs] = a + offs
                pos += n_dofs
            scatter_list.append(scatter_e)

        return A_template, scatter_list

    def _assemble_global_matrix_fast(
        self,
        A: sp.sparse.csr_matrix[np.float64],
        elements: list[FiniteElement],
        scatter_list: list[npt.NDArray[np.int64]],
        get_local_matrix: Callable[[FiniteElement], npt.NDArray[np.float64]]
    ) -> sp.sparse.csr_matrix[np.float64]:
        """
        Assemble a global matrix in CSR form for the model using a provided function to get the element matrix.

        Args:
            A: The global matrix to assemble (in CSR format).
            elements: List of finite elements to assemble from.
            scatter_list: Precomputed scatter list for the elements.
            get_local_matrix: Function to get the local element matrix.

        Returns:
            The assembled global matrix in CSR format.
        """
        A.data[:] = 0.0
        for i, element in enumerate(elements):
            Ke = np.asarray(get_local_matrix(element), dtype=np.float64)
            A.data[scatter_list[i]] += Ke.ravel(order="C")
        return A

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
                dofs = element.global_dofs
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
        # self.model.k_global = self._assemble_global_matrix(
        #     get_local_matrix=lambda element: element.get_conductivity_matrix()
        # )
        self.model.k_global = self._assemble_global_matrix_fast(
            A=self._K,
            elements=self._surface_elements,
            scatter_list=self._A_scatter,
            get_local_matrix=lambda element: element.get_conductivity_matrix()
        )


    def assemble_global_capacity_matrix(self) -> None:
        """
        Assemble the global capacity matrix [C] for the model.
        """
        # self.model.c_global = self._assemble_global_matrix(
        #     get_local_matrix=lambda element: element.get_capacity_matrix()
        # )
        self.model.c_global = self._assemble_global_matrix_fast(
            A=self._C,
            elements=self._surface_elements,
            scatter_list=self._A_scatter,
            get_local_matrix=lambda element: element.get_capacity_matrix()
        )

    def assemble_load_vector(self, time: float) -> None:
        # # q_global can be dense, because it's just length of number_of_equations
        # self.model.q_global = np.zeros((self.model.number_of_equations,), dtype=np.float64)
        #
        # # dqdT_global have to be sparse, because it's number_of_equations x number_of_equations
        # row: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        # col: npt.NDArray[np.int64] = np.empty(0, dtype=np.int64)
        # data: npt.NDArray[np.float64] = np.empty(0, dtype=np.float64)
        #
        # # self.model.dqdT_global = np.zeros((self.model.number_of_equations, self.model.number_of_equations), dtype=np.float64)
        # temperature = self.model.fire_curve.get_temperature(time=time)
        # for elements in self.model.mesh.boundary_elements.values():
        #     for element in elements:
        #         dofs = element.global_dofs
        #         n_dofs = len(dofs)
        #
        #         self.model.q_global[dofs] += element.get_load_vector(temperature=temperature)
        #
        #         # accumulate dqdT_el into global sparse triplets
        #         # (COO tolerates duplicates; .tocsr() will sum them)
        #         r = np.repeat(dofs, n_dofs)
        #         c = np.tile(dofs, n_dofs)
        #
        #         row = np.hstack((row, r))
        #         col = np.hstack((col, c))
        #         data = np.hstack((data, element.get_load_vector_tangent().flatten()))
        #
        #         # assemble_subarray_at_indices(
        #         #     array=self.model.dqdT_global,
        #         #     subarray=element.get_load_vector_tangent(),
        #         #     indices=dofs
        #         # )
        #
        # # finalize dqdT_global as sparse matrix
        # self.model.dqdT_global = sp.sparse.coo_matrix(
        #     (data, (row, col)),
        #     shape=(self.model.number_of_equations, self.model.number_of_equations),
        #     dtype=np.float64
        # ).tocsr()
        F = np.zeros((self.neq,), dtype=np.float64)
        T = self._dqdT
        T.data[:] = 0.0

        temperature = self.model.fire_curve.get_temperature(time=time)
        for i, element in enumerate(self._boundary_elements):
            dofs = element.global_dofs

            F[dofs] += element.get_load_vector(temperature=temperature)

            dqdT_el = np.asarray(element.get_load_vector_tangent(), dtype=np.float64)
            T.data[self._D_scatter[i]] += dqdT_el.ravel(order="C")

        self.model.q_global = F
        self.model.dqdT_global = T

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






