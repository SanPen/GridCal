# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from scipy.sparse.linalg import spsolve
import numpy as np
import numba as nb
import os
import time
from scipy.sparse import lil_matrix, diags
import scipy.sparse as sp


def dSf_dV(Yf, V, F, Cf):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :return: dSf_dVa, dSf_dVm
    """

    Vc = np.conj(V)
    diagVc = diags(Vc)
    diagE = diags(V / np.abs(V))
    diagV = diags(V)

    Yfc = np.conj(Yf)
    Ifc = Yfc * Vc  # conjugate  of "from"  current

    diagIfc = diags(Ifc)
    Vf = V[F]
    diagVf = diags(Vf)

    CVf = Cf * diagV
    CVnf = Cf * diagE

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagE) + diagIfc * CVnf

    return dSf_dVa.tocsc(), dSf_dVm.tocsc()


def dSt_dV(Yt, V, T, Ct):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param T: Array of branch "to" bus indices
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """

    Vc = np.conj(V)
    diagVc = diags(Vc)
    diagE = diags(V / np.abs(V))
    diagV = diags(V)

    Ytc = np.conj(Yt)
    Itc = Ytc * Vc  # conjugate of "to" current

    diagItc = diags(Itc)
    Vt = V[T]
    diagVt = diags(Vt)

    CVt = Ct * diagV
    CVnt = Ct * diagE

    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagE) + diagItc * CVnt

    return dSt_dVa.tocsc(), dSt_dVm.tocsc()


def dSf_dV_fast_v1(Yf, V, F, Cf):

    Vc = np.conj(V)
    diagVc = diags(Vc)
    E = V / np.abs(V)
    diagE = diags(E)
    diagV = diags(V)

    Yfc = np.conj(Yf).tocsc()
    Ifc = Yfc * Vc  # conjugate  of "from"  current

    diagIfc = diags(Ifc)
    Vf = V[F]
    diagVf = diags(Vf)

    CVf = Cf * diagV
    CVnf = Cf * diagE

    op1 = diagIfc * CVf  # diagIfc * Cf * diagV
    op2 = diagVf * Yfc * diagVc
    op3 = diagVf * np.conj(Yf * diagE)
    op4 = diagIfc * CVnf

    # realizamos la operación [diagIfc * Cf * diagV] y [diagIfc * Cf * diagE]
    data1 = np.empty(len(Cf.data), dtype=complex)
    data4 = np.empty(len(Cf.data), dtype=complex)
    for j in range(Cf.shape[1]):  # para cada columna j ...
        for k in range(Cf.indptr[j], Cf.indptr[j + 1]):  # para cada entrada de la columna ....
            i = Cf.indices[k]  # obtener el índice de la fila
            data1[k] = Cf.data[k] * Ifc[i] * V[j]
            data4[k] = Cf.data[k] * Ifc[i] * E[j]
    op1_b = sp.csc_matrix((data1, Cf.indices, Cf.indptr), shape=Cf.shape)
    op4_b = sp.csc_matrix((data4, Cf.indices, Cf.indptr), shape=Cf.shape)

    # realizamos la operación [diagVf * Yfc * diagVc] y [diagVf * np.conj(Yf * diagE)]
    data2 = np.empty(len(Yf.data), dtype=complex)
    data3 = np.empty(len(Yf.data), dtype=complex)
    for j in range(Yf.shape[1]):  # para cada columna j ...
        for k in range(Yf.indptr[j], Yf.indptr[j + 1]):  # para cada entrada de la columna ....
            i = Yf.indices[k]  # obtener el índice de la fila
            data2[k] = np.conj(Yf.data[k]) * Vf[i] * Vc[j]
            data3[k] = Vf[i] * np.conj(Yf.data[k] * E[j])

    op2_b = sp.csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)
    op3_b = sp.csc_matrix((data3, Yf.indices, Yf.indptr), shape=Yf.shape)

    c1 = op1 - op1_b
    c2 = op2 - op2_b
    c3 = op3 - op3_b
    c4 = op4 - op4_b

    dSf_dVa = 1j * (op1 - op2)
    dSf_dVm = op3 + op4

    return dSf_dVa, dSf_dVm


def dSf_dV_fast_v2(Yf, V, F, Cf):
    """

    :param Yf:
    :param V:
    :param F:
    :param Cf:
    :return:
    """
    Vc = np.conj(V)
    E = V / np.abs(V)
    Ifc = np.conj(Yf) * Vc  # conjugate  of "from"  current

    # Perform the following operations
    # op1 = [diagIfc * Cf * diagV]
    # op4 = [diagIfc * Cf * diagE]
    data1 = np.empty(len(Cf.data), dtype=complex)
    data4 = np.empty(len(Cf.data), dtype=complex)
    for j in range(Cf.shape[1]):  # column j ...
        for k in range(Cf.indptr[j], Cf.indptr[j + 1]):  # for each column entry k ...
            i = Cf.indices[k]  # row i
            data1[k] = Cf.data[k] * Ifc[i] * V[j]
            data4[k] = Cf.data[k] * Ifc[i] * E[j]
    op1 = sp.csc_matrix((data1, Cf.indices, Cf.indptr), shape=Cf.shape)
    op4 = sp.csc_matrix((data4, Cf.indices, Cf.indptr), shape=Cf.shape)

    # Perform the following operations
    # op2 = [diagVf * Yfc * diagVc]
    # op3 = [diagVf * np.conj(Yf * diagE)]
    data2 = np.empty(len(Yf.data), dtype=complex)
    data3 = np.empty(len(Yf.data), dtype=complex)
    for j in range(Yf.shape[1]):  # column j ...
        for k in range(Yf.indptr[j], Yf.indptr[j + 1]):  # for each column entry k ...
            i = Yf.indices[k]  # row i
            data2[k] = np.conj(Yf.data[k]) * V[F[i]] * Vc[j]
            data3[k] = V[F[i]] * np.conj(Yf.data[k] * E[j])
    op2 = sp.csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)
    op3 = sp.csc_matrix((data3, Yf.indices, Yf.indptr), shape=Yf.shape)

    dSf_dVa = 1j * (op1 - op2)
    dSf_dVm = op3 + op4

    return dSf_dVa, dSf_dVm


@nb.njit()
def data_1_4(Cf_data, Cf_indptr, Cf_indices, Ifc, V, E, n_cols):
    data1 = np.empty(len(Cf_data), dtype=nb.complex128)
    data4 = np.empty(len(Cf_data), dtype=nb.complex128)
    for j in range(n_cols):  # column j ...
        for k in range(Cf_indptr[j], Cf_indptr[j + 1]):  # for each column entry k ...
            i = Cf_indices[k]  # row i
            data1[k] = Cf_data[k] * Ifc[i] * V[j]
            data4[k] = Cf_data[k] * Ifc[i] * E[j]

    return data1, data4


@nb.njit()
def data_2_3(Yf_data, Yf_indptr, Yf_indices, V, F, Vc, E, n_cols):
    data2 = np.empty(len(Yf_data), dtype=nb.complex128)
    data3 = np.empty(len(Yf_data), dtype=nb.complex128)
    for j in range(n_cols):  # column j ...
        for k in range(Yf_indptr[j], Yf_indptr[j + 1]):  # for each column entry k ...
            i = Yf_indices[k]  # row i
            data2[k] = np.conj(Yf_data[k]) * V[F[i]] * Vc[j]
            data3[k] = V[F[i]] * np.conj(Yf_data[k] * E[j])
    return data2, data3


def dSf_dV_fast(Yf, V, F, Cf):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    Works for dSf with Yf, F, Cf and for dSt with Yt, T, Ct
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :return: dSf_dVa, dSf_dVm
    """
    Vc = np.conj(V)
    E = V / np.abs(V)
    Ifc = np.conj(Yf) * Vc  # conjugate  of "from"  current

    # Perform the following operations
    # op1 = [diagIfc * Cf * diagV]
    # op4 = [diagIfc * Cf * diagE]
    data1, data4 = data_1_4(Cf.data, Cf.indptr, Cf.indices, Ifc, V, E, Cf.shape[1])
    op1 = sp.csc_matrix((data1, Cf.indices, Cf.indptr), shape=Cf.shape)
    op4 = sp.csc_matrix((data4, Cf.indices, Cf.indptr), shape=Cf.shape)

    # Perform the following operations
    # op2 = [diagVf * Yfc * diagVc]
    # op3 = [diagVf * np.conj(Yf * diagE)]
    data2, data3 = data_2_3(Yf.data, Yf.indptr, Yf.indices, V, F, Vc, E, Yf.shape[1])
    op2 = sp.csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)
    op3 = sp.csc_matrix((data3, Yf.indices, Yf.indptr), shape=Yf.shape)

    dSf_dVa = 1j * (op1 - op2)
    dSf_dVm = op3 + op4

    return dSf_dVa, dSf_dVm


if __name__ == '__main__':

    from GridCal.Engine import FileOpen, compile_snapshot_circuit

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    main_circuit = FileOpen(fname).open()

    nc = compile_snapshot_circuit(main_circuit)

    V = nc.Vbus + np.array([0.01, -0.05, 0.002, -0.007, 0.006])  # to not to be perfectly 1

    dSf_dVa_1, dSf_dVm_1 = dSf_dV(Yf=nc.Yf, V=V, F=nc.F, Cf=nc.Cf)
    dSf_dVa_2, dSf_dVm_2 = dSf_dV_fast(Yf=nc.Yf.tocsc(), V=V, F=nc.F, Cf=nc.Cf.tocsc())
    da = dSf_dVa_1 - dSf_dVa_2
    dm = dSf_dVm_1 - dSf_dVm_2
    assert len(da.data) == 0
    assert len(dm.data) == 0

    dSt_dVa_1, dSt_dVm_1 = dSt_dV(Yt=nc.Yt, V=V, T=nc.T, Ct=nc.Ct)
    dSt_dVa_2, dSt_dVm_2 = dSf_dV_fast(Yf=nc.Yt.tocsc(), V=V, F=nc.T, Cf=nc.Ct.tocsc())
    da = dSt_dVa_1 - dSt_dVa_2
    dm = dSt_dVm_1 - dSt_dVm_2
    assert len(da.data) == 0
    assert len(dm.data) == 0

    print()