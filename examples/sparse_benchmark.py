# -*- coding: utf-8 -*-
# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# import time
# import numpy as np
# import scipy.sparse as sp
# import pypardiso as pp
#
# np.random.seed(0)
# n = 4000
# repetitions = 50
#
# start = time.time()
# for r in range(repetitions):
#     A = sp.csr_matrix(sp.rand(n, n, 0.01)) + sp.diags(np.random.rand(n) * 10.0, shape=(n, n))
#     b = np.random.rand(n)
#     print(r)
#     x = pp.spsolve(A, b)
# end = time.time()
# dt = end - start
#
# print('pardiso', '  total', dt, 's, average:', dt / repetitions, 's')


import os
import time
import numpy as np
import pandas as pd
import scipy.sparse as sp
from GridCalEngine.Utils.NumericalMethods.sparse_solve import SparseSolver, get_sparse_type, get_linear_solver
import GridCalEngine.api as gce


#  list of solvers to try
solver_types = [SparseSolver.UMFPACK,
                # SparseSolver.KLU,
                SparseSolver.SuperLU,
                SparseSolver.Pardiso,
                SparseSolver.ILU,
                # SparseSolver.GMRES
                ]


def generic_benchmark(n=4000, repetitions=50):
    """
    Run a generic benchmark
    :param n: size of the A matrix
    :param repetitions: number of times a random system is solved per solver
    """
    data = list()
    for solver_type_ in solver_types:
        start = time.time()

        np.random.seed(0)

        sparse = get_sparse_type(solver_type_)
        solver = get_linear_solver(solver_type_)

        for r in range(repetitions):
            A = sparse(sp.rand(n, n, 0.01)) + sp.diags(np.random.rand(n) * 10.0, shape=(n, n))
            b = np.random.rand(n)
            x = solver(A, b)

        end = time.time()
        dt = end - start
        print(solver_type_, '  total', dt, 's, average:', dt / repetitions, 's')
        data.append([solver_type_, dt,  dt / repetitions])

    df = pd.DataFrame(data=data, columns=['Solver', 'Total (s)', 'Average (s)'])
    print("Generic benchmark:\n", df)
    df.to_csv('generic_sparse_benchmark.csv')


def grid_solve_benchmark(repetitions=50):
    """
    Grid Benchmark where a DC linear system is solved
    :param repetitions: number of times the DC system is solved
    """
    folder = os.path.join('..', 'Grids_and_profiles', 'grids')
    fname = os.path.join(folder, '2869 Pegase.gridcal')
    main_circuit = gce.FileOpen(fname).open()
    numeric_circuit = gce.compile_numerical_circuit_at(main_circuit, t_idx=None)

    B = numeric_circuit.Bpqpv
    P = numeric_circuit.Pbus[numeric_circuit.pqpv]

    data = list()
    for solver_type_ in solver_types:
        start = time.time()

        solver = get_linear_solver(solver_type_)

        for r in range(repetitions):
            x = solver(B, P)

        end = time.time()
        dt = end - start
        # print(solver_type_, '  total', dt, 's, average:', dt / repetitions, 's')
        data.append([solver_type_, dt, dt / repetitions])

    df = pd.DataFrame(data=data, columns=['Solver', 'Total (s)', 'Average (s)'])
    print("Grid benchmark:\n", df)
    df.to_csv('{}_benchmark.csv'.format(main_circuit))


grid_solve_benchmark()

generic_benchmark(repetitions=20)
