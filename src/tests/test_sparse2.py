# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from time import time
import numpy as np
import numba as nb
from scipy.sparse import csc_matrix, random, hstack, vstack
from GridCalEngine.Utils.Sparse.csc2 import sp_slice, sp_slice_rows, csc_stack_2d_ff, scipy_to_mat, mat_to_scipy


def test_sp_slice():

    m = 6
    n = 3
    data = np.array([4, 3, 3, 9, 7, 8, 4, 8, 8, 9]).astype(np.float64)
    indices = np.array([0, 1, 3, 1, 2, 4, 5, 2, 3, 4]).astype(np.int32)
    indptr = np.array([0, 3, 7, 10]).astype(np.int32)

    A = csc_matrix((data, indices, indptr), shape=(m, n))
    Acsc = scipy_to_mat(A)

    list_a = np.array([1, 2, 5])
    list_b = np.array([0, 2])

    A1 = A[np.ix_(list_a, list_b)]
    A2 = sp_slice(Acsc, list_a, list_b)

    ok = np.allclose(A1.toarray(), A2.toarray())

    assert ok

    A3 = A[list_a, :]
    A4 = sp_slice_rows(Acsc, list_a)

    ok2 = np.allclose(A3.toarray(), A4.toarray())

    assert ok2


def test_stack_4():
    """

    :return:
    """
    k = 1000
    l = 4 * k
    m = 6 * k

    A = csc_matrix(random(k, l, density=0.1))
    B = csc_matrix(random(k, k, density=0.1))
    C = csc_matrix(random(m, l, density=0.1))
    D = csc_matrix(random(m, k, density=0.1))
    t = time()
    E = hstack((vstack((A, C)), vstack((B, D))))
    # print('Scipy\t', time() - t)

    t = time()
    A1 = scipy_to_mat(A)
    B1 = scipy_to_mat(B)
    C1 = scipy_to_mat(C)
    D1 = scipy_to_mat(D)
    E1 = csc_stack_2d_ff(nb.typed.List([A1, B1, C1, D1]), 2, 2)
    # print('Csparse3\t', time() - t)
    # print(A1)
    # print(B1)
    # print(C1)
    # print(D1)
    # print(E1)

    stack_test = np.allclose(E.todense(), E1.todense())

    # print('Stacking pass:', stack_test)
    assert stack_test

    return True

