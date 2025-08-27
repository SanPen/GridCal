# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


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
from VeraGridEngine.Utils.NumericalMethods.sparse_solve import SparseSolver, get_sparse_type, get_linear_solver
import VeraGridEngine.api as gce


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
