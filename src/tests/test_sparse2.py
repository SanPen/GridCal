# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from time import time
import numpy as np
import numba as nb
from scipy.sparse import csc_matrix, random, hstack, vstack
from scipy.sparse import rand
from scipy.sparse.linalg import spsolve as spsolve_scipy
from VeraGridEngine.Utils.Sparse.csc2 import (sp_slice, sp_slice_rows, csc_stack_2d_ff, scipy_to_mat, spsolve_csc,
                                              extend, CSC, csc_multiply_ff, csc_add_ff)


def get_scipy_random_matrix(m: int | None = None, n: int | None = None) -> csc_matrix:
    """

    :param m: number or rows (if None, random)
    :param n: number or cols (if None, random)
    :return:
    """
    if m is None:
        m = np.random.randint(1, 1000)

    if n is None:
        n = np.random.randint(1, 1000)

    return rand(m, n, density=0.25, format="csc", random_state=42)


def get_csc_random_matrix(m: int | None = None, n: int | None = None) -> CSC:
    """

    :param m: number or rows (if None, random)
    :param n: number or cols (if None, random)
    :return:
    """
    return scipy_to_mat(get_scipy_random_matrix(m, n))


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


def test_spsolve() -> None:
    """
    Test the CSC oriented spsolve_csc function
    """
    for i in range(100):
        m = np.random.randint(1, 1000)
        matrix = rand(m, m, density=0.25, format="csc", random_state=42)
        rhs = np.random.rand(m)

        try:
            a = spsolve_scipy(matrix, rhs)
            ok_a = not np.isnan(a).any()

            try:
                b, ok_b = spsolve_csc(scipy_to_mat(matrix), rhs)

                assert ok_a == ok_b
                if ok_a and ok_b:
                    assert np.allclose(a, b)

            except RuntimeError:
                ok_b = False

        except RuntimeError:
            ok_a = False


def test_extend():
    """
    Test the extend function
    """
    for i in range(100):
        m = np.random.randint(1, 1000)
        n = np.random.randint(1, 1000)
        matrix = rand(m, n, density=0.25, format="csc", random_state=42)
        last_col = np.random.rand(m)
        last_row = np.random.rand(n)
        val = 1.0

        last_row2 = np.r_[last_row, np.full(1, val)]
        A = vstack([hstack([matrix, last_col.reshape(m, 1)]), last_row2.reshape(1, n + 1)], format="csc")

        B = extend(scipy_to_mat(matrix), last_col, last_row, val)

        assert np.allclose(A.todense(), B.todense())


# def test_mat_mat_mult():
#     for i in range(10):
#         m = np.random.randint(1, 1000)
#         n = np.random.randint(1, 1000)
#         o = np.random.randint(1, 1000)
#
#         A1 = get_scipy_random_matrix(m, n)
#         B1 = get_scipy_random_matrix(n, o)
#         C1 = A1 @ B1
#
#         A2 = get_csc_random_matrix(m, n)
#         B2 = get_csc_random_matrix(n, o)
#         C2 = A2.mul(B2)
#
#         assert np.allclose(C1.toarray(), C2.toarray())


# def test_sum():
#
#     for i in range(10):
#         m = np.random.randint(1, 1000)
#         n = np.random.randint(1, 1000)
#
#         A1 = get_scipy_random_matrix(m, n)
#         B1 = get_scipy_random_matrix(m, n)
#         C1 = A1 + B1
#
#         A2 = scipy_to_mat(A1)
#         B2 = scipy_to_mat(B1)
#         C2 = A2.sum(B2)
#         # C2 = csc_add_ff(A2, B2, 1.0, 1.0)
#         assert np.allclose(C1.toarray(), C2.toarray())