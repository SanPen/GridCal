#!/usr/bin/env python
# coding: utf-8


import numpy as np
import scipy.sparse.linalg as la
import scipy.sparse as sp
import time

from bbd_matrix import *


def schur_lu(A_bbd, dense_corner=False):
    """

    :param A_bbd:
    :param dense_corner:
    :return:
    """
    L = bbd_matrix(A_bbd.block_dim)
    U = bbd_matrix(A_bbd.block_dim)

    for idx in A_bbd.diag_blocks.keys():
        Aii = A_bbd.diag_blocks[idx]
        Ain = A_bbd.right_blocks[idx]
        Ani = A_bbd.lower_blocks[idx]

        N = Aii.shape[0]

        lu = la.splu(Aii.tocsc(), permc_spec="NATURAL")
        L.diag_blocks[idx] = lu.L[lu.perm_r, :]
        U.diag_blocks[idx] = lu.U

        L.lower_blocks[idx] = la.spsolve(lu.U.transpose().tocsc(), Ani.transpose().tocsc()).transpose()
        U.right_blocks[idx] = la.spsolve(L.diag_blocks[idx], Ain.tocsc())

    N = A_bbd.corner.shape[0]
    B = sp.csc_matrix((N, N))
    for idx in A_bbd.diag_blocks.keys():
        B += L.lower_blocks[idx] @ U.right_blocks[idx]

    lu = la.splu(A_bbd.corner.tocsc() - B)
    L.corner = lu.L[lu.perm_r, :]
    U.corner = lu.U[:, lu.perm_c]

    if dense_corner:
        L.corner = L.corner.todense()
        U.corner = U.corner.todense()

    L.complete = True
    U.complete = True

    return L, U


class schur_bbd_lu:
    """
    schur_bbd_lu
    """
    def __init__(self, A_bbd, dense_corner=False):

        (self.L, self.U) = schur_lu(A_bbd, dense_corner=dense_corner)

        self.block_sizes = A_bbd.block_sizes

        self.dense_corner = dense_corner

        self.t_formbv = 0.0
        self.t_forward = 0.0
        self.t_backward = 0.0

        self.tf_yloop = 0.0
        self.tf_csolve = 0.0

        self.tb_csolve = 0.0
        self.tb_loop = 0.0

        self.solves = 0

        return

    def _schur_forward(self, b_bv):

        t0 = time.time()

        L = self.L

        y = {}
        c = np.zeros(L.corner.shape[0])
        for idx in L.diag_blocks.keys():
            y[idx] = la.spsolve(L.diag_blocks[idx], b_bv[idx])
            c += L.lower_blocks[idx] @ y[idx]

        t1 = time.time()

        if self.dense_corner:
            yn = dla.solve(L.corner, b_bv[L.block_dim - 1] - c)
        else:
            yn = la.spsolve(L.corner, b_bv[L.block_dim - 1] - c)

        t2 = time.time()

        self.tf_yloop += t1 - t0
        self.tf_csolve += t2 - t1

        return (y, yn)

    def _schur_backward(self, y, yn, block_sizes):

        t0 = time.time()

        U = self.U

        if self.dense_corner:
            xn = dla.solve(U.corner, yn)
        else:
            xn = la.spsolve(U.corner, yn)

        t1 = time.time()

        x_bv = block_vector(block_sizes)
        for idx in U.diag_blocks.keys():
            rhs_i = y[idx] - U.right_blocks[idx] @ xn
            x_bv[idx] = la.spsolve(U.diag_blocks[idx], rhs_i, permc_spec="NATURAL")
        x_bv[U.block_dim - 1] = xn

        t2 = time.time()

        self.tb_csolve += t1 - t0
        self.tb_loop += t2 - t1

        return x_bv.to_dense()

    def schur_solve(self, b_dense):

        t0 = time.time()

        b_bv = block_vector(self.block_sizes, x_dense=b_dense)

        t1 = time.time()

        (y, yn) = self._schur_forward(b_bv)

        t2 = time.time()

        x_bv = self._schur_backward(y, yn, b_bv.sizes)

        t3 = time.time()

        self.t_formbv += t1 - t0
        self.t_forward += t2 - t1
        self.t_backward += t3 - t2
        self.solves += 1

        return x_bv

    def print_timing(self):

        total = self.t_forward + self.t_backward
        time_str = """
        Calls:      {:d}
        BlkVectr:   {:10.2e} {:8.2%} {:8.2e}
        Forward:    {:10.2e} {:8.2%} {:8.2e}
          FLoop:    {:10.2e} {:8.2%} {:8.2e}
          FCSolve:  {:10.2e} {:8.2%} {:8.2e}
        Backward:   {:10.2e} {:8.2%} {:8.2e}
          BCSolve:  {:10.2e} {:8.2%} {:8.2e}
          BLoop:    {:10.2e} {:8.2%} {:8.2e}
        SchurSolve: {:10.2e}
        """.format(
            self.solves,
            self.t_formbv, self.t_formbv / total, self.t_formbv / self.solves,
            self.t_forward, self.t_forward / total, self.t_forward / self.solves,
            self.tf_yloop, self.tf_yloop / total, self.tf_yloop / self.solves,
            self.tf_csolve, self.tf_csolve / total, self.tf_csolve / self.solves,
            self.t_backward, self.t_backward / total, self.t_backward / self.solves,
            self.tb_csolve, self.tb_csolve / total, self.tb_csolve / self.solves,
            self.tb_loop, self.tb_loop / total, self.tb_loop / self.solves,
            total,
        )

        print(time_str)

        return

    def print_summary(self):

        lsum = self.L.summarize()
        usum = self.U.summarize()

        bbd_str = """
        **** {0} Summary ****
        {0} Total NNZ:      {1:7d}
        {0} Min Block Size: {2:7d}
        {0} Min Block NNZ:  {3:7d}
        {0} Max Block Size: {4:7d}
        {0} Max Block NNZ:  {5:7d}
        {0} Corner Size:    {6:7d}
        {0} Corner NNZ:     {7:7d}
        """

        print(bbd_str.format(
            'L',
            lsum[0],
            lsum[1],
            lsum[2],
            lsum[3],
            lsum[4],
            lsum[5],
            lsum[6],
        ))

        print(bbd_str.format(
            'U',
            usum[0],
            usum[1],
            usum[2],
            usum[3],
            usum[4],
            usum[5],
            usum[6],
        ))

        return
