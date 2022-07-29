
import numpy as np
from math import sin, cos
from scipy.sparse import csc_matrix, diags
import GridCal.Engine as gc
np.set_printoptions(linewidth=1000000)


def data_1_4(Cf_data, Cf_indptr, Cf_indices, Ifc, V, E, n_cols):
    """
    Performs the operations:
        op1 = [diagIfc * Cf * diagV]
        op4 = [diagIfc * Cf * diagE]
    :param Cf_data:
    :param Cf_indptr:
    :param Cf_indices:
    :param Ifc:
    :param V:
    :param E:
    :param n_cols:
    :return:
    """
    data1 = np.empty(len(Cf_data), dtype=complex)
    data4 = np.empty(len(Cf_data), dtype=complex)
    for j in range(n_cols):  # column j ...
        for k in range(Cf_indptr[j], Cf_indptr[j + 1]):  # for each column entry k ...
            i = Cf_indices[k]  # row i
            data1[k] = Cf_data[k] * Ifc[i] * V[j]
            data4[k] = Cf_data[k] * Ifc[i] * E[j]

    return data1, data4


def data_2_3(Yf_data, Yf_indptr, Yf_indices, V, F, Vc, E, n_cols):
    """
    Performs the operations:
        op2 = [diagVf * Yfc * diagVc]
        op3 = [diagVf * np.conj(Yf * diagE)]
    :param Yf_data:
    :param Yf_indptr:
    :param Yf_indices:
    :param V:
    :param F:
    :param Vc:
    :param E:
    :param n_cols:
    :return:
    """
    data2 = np.empty(len(Yf_data), dtype=complex)
    data3 = np.empty(len(Yf_data), dtype=complex)
    for j in range(n_cols):  # column j ...
        for k in range(Yf_indptr[j], Yf_indptr[j + 1]):  # for each column entry k ...
            i = Yf_indices[k]  # row i
            data2[k] = np.conj(Yf_data[k]) * V[F[i]] * Vc[j]
            data3[k] = V[F[i]] * np.conj(Yf_data[k] * E[j])
    return data2, data3


def dSf_dV_fast(Yf, V, Vc, E, F, Cf):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    Works for dSf with Yf, F, Cf and for dSt with Yt, T, Ct
    :param Yf: Admittance matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param Vc: Array of voltages conjugates
    :param E: Array of voltages unitary vectors
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :return: dSf_dVa, dSf_dVm
    """

    Ifc = np.conj(Yf) * Vc  # conjugate  of "from"  current

    # Perform the following operations
    # op1 = [diagIfc * Cf * diagV]
    # op4 = [diagIfc * Cf * diagE]
    data1, data4 = data_1_4(Cf.data, Cf.indptr, Cf.indices, Ifc, V, E, Cf.shape[1])
    op1 = csc_matrix((data1, Cf.indices, Cf.indptr), shape=Cf.shape)
    op4 = csc_matrix((data4, Cf.indices, Cf.indptr), shape=Cf.shape)

    # Perform the following operations
    # op2 = [diagVf * Yfc * diagVc]
    # op3 = [diagVf * np.conj(Yf * diagE)]
    data2, data3 = data_2_3(Yf.data, Yf.indptr, Yf.indices, V, F, Vc, E, Yf.shape[1])
    op2 = csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)
    op3 = csc_matrix((data3, Yf.indices, Yf.indptr), shape=Yf.shape)

    dSf_dVa = 1j * (op1 - op2)
    dSf_dVm = op3 + op4

    return dSf_dVa, dSf_dVm

# ----------------------------------------------------------------------------------------------------------------------


def dSf_dV(Yf, V, F, Cf, Vc, E):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Vc: array of conjugate voltages
    :param E: array of unit voltage vectors
    :return: dSf_dVa, dSf_dVm
    """
    diagVc = diags(Vc)
    diagE = diags(E)
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

# ----------------------------------------------------------------------------------------------------------------------


def dP_dVa_simp(Cf, Yf, V, tap_mod, R, X, F, T):
    """
    According to Salvador Acha-Daza's book
    :param Cf:
    :param Yf:
    :param V:
    :param tap_mod:
    :param R:
    :param X:
    :param F:
    :param T:
    :return:
    """
    m, n = Cf.shape
    Vf = Cf * V
    If = Yf * V
    Sf = Vf * np.conj(If)
    Ys = 1 / (R + 1j * X)
    b = Ys.imag
    t2 = np.power(tap_mod, 2)
    vm2 = np.power(np.abs(V), 2)

    Qbr = Sf.imag

    mat = np.zeros((m, n))

    for i in range(m):
        k = F[i]
        m = T[i]
        mat[i, k] = -vm2[k] * t2[k] * b[i] - Qbr[i]
        mat[i, m] = vm2[k] * t2[k] * b[i] + Qbr[i]

    return mat


def dP_dVm_simp(Cf, Yf, V, tap_mod, R, X, F, T):
    """
    According to Salvador Acha-Daza's book
    :param Cf:
    :param Yf:
    :param V:
    :param tap_mod:
    :param R:
    :param X:
    :param F:
    :param T:
    :return:
    """
    m, n = Cf.shape
    Vf = Cf * V
    If = Yf * V
    Sf = Vf * np.conj(If)
    Ys = 1 / (R + 1j * X)
    g = Ys.real
    t2 = np.power(tap_mod, 2)
    vm = np.abs(V)
    vm2 = np.power(vm, 2)

    Pbr = Sf.real

    mat = np.zeros((m, n))

    for i in range(m):
        k = F[i]
        m = T[i]
        mat[i, k] = vm2[k] * tap_mod[k] * g[i] + Pbr[i]
        mat[i, m] = - vm2[k] / vm[m] * tap_mod[k] * g[i] + Pbr[i]

    return mat

# ----------------------------------------------------------------------------------------------------------------------


def dPf_dVm_monticelli(m, n, V, F, T, ys, bsh, tap_mod, tap_angle):
    """
    According to monticelli's book (page 269)
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    vm = np.abs(V)
    va = np.angle(V)
    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        Vk = vm[i]
        Vm = vm[j]
        Ɵkm = va[i] - va[j]
        akm = tap_mod[k]
        amk = 1.0
        φkm = tap_angle[k]
        φmk = 0.0
        gkm = ys[k].real
        bkm = ys[k].imag

        # 2 * akm * Vk * gkm - akm * amk * Vm * gkm * cos(Ɵkm + φkm - φmk) - akm * amk * Vm * bkm * sin(Ɵkm + φkm - φmk)
        mat[k, i] = 2 * akm * Vk * gkm - akm * amk * Vm * gkm * cos(Ɵkm + φkm - φmk) - akm * amk * Vm * bkm * sin(Ɵkm + φkm - φmk)

        # -akm * amk * Vk * gkm * cos(Ɵkm + φkm - φmk) + akm * amk * Vk * bkm * sin(Ɵkm + φkm - φmk)
        mat[k, j] = - akm * amk * Vk * gkm * cos(Ɵkm + φkm - φmk) + akm * amk * Vk * bkm * sin(Ɵkm + φkm - φmk)

    return mat


def dQf_dVm_monticelli(m, n, V, F, T, ys, bsh, tap_mod, tap_angle):
    """
    According to monticelli's book (page 269)
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    vm = np.abs(V)
    va = np.angle(V)
    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        Vk = vm[i]
        Vm = vm[j]
        Ɵkm = va[i] - va[j]
        akm = tap_mod[k]
        amk = 1.0
        φkm = tap_angle[k]
        φmk = 0.0
        gkm = ys[k].real
        bkm = ys[k].imag
        bshkm = bsh[k]

        # -2 * akm * Vk * (bkm + bshkm) + akm * amk * Vm * bkm * cos(Ɵkm + φkm - φmk) - akm * amk * Vm * gkm * sin(Ɵkm + φkm - φmk)
        mat[k, i] = -2 * akm * Vk * (bkm + bshkm) + akm * amk * Vm * bkm * cos(Ɵkm + φkm - φmk) - akm * amk * Vm * gkm * sin(Ɵkm + φkm - φmk)

        # akm * amk * Vk * bkm * cos(Ɵkm + φkm - φmk) - akm * amk * Vk * gkm * sin(Ɵkm + φkm - φmk)
        mat[k, j] = akm * amk * Vk * bkm * cos(Ɵkm + φkm - φmk) - akm * amk * Vk * gkm * sin(Ɵkm + φkm - φmk)

    return mat


def dPf_dVa_monticelli(m, n, V, F, T, ys, bsh, tap_mod, tap_angle):
    """
    According to monticelli's book (page 269)
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    vm = np.abs(V)
    va = np.angle(V)
    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        Vk = vm[i]
        Vm = vm[j]
        Ɵkm = va[i] - va[j]
        akm = tap_mod[k]
        amk = 1.0
        φkm = tap_angle[k]
        φmk = 0.0
        gkm = ys[k].real
        bkm = ys[k].imag
        bshkm = bsh[k]

        #  akm * Vk * amk * Vm * gkm * sin(Ɵkm + φkm - φmk) - akm * Vk * amk * Vm * bkm * cos(Ɵkm + φkm - φmk)
        mat[k, i] = akm * Vk * amk * Vm * gkm * sin(Ɵkm + φkm - φmk) - akm * Vk * amk * Vm * bkm * cos(Ɵkm + φkm - φmk)

        # -akm * Vk * amk * Vm * gkm * sin(Ɵkm + φkm - φmk) + akm * Vk * amk * Vm * bkm * cos(Ɵkm + φkm - φmk)
        mat[k, j] = -akm * Vk * amk * Vm * gkm * sin(Ɵkm + φkm - φmk) + akm * Vk * amk * Vm * bkm * cos(Ɵkm + φkm - φmk)

    return mat


def dQf_dVa_monticelli(m, n, V, F, T, ys, bsh, tap_mod, tap_angle):
    """
    According to monticelli's book (page 269)
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    vm = np.abs(V)
    va = np.angle(V)
    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        Vk = vm[i]
        Vm = vm[j]
        Ɵkm = va[i] - va[j]
        akm = tap_mod[k]
        amk = 1.0
        φkm = tap_angle[k]
        φmk = 0.0
        gkm = ys[k].real
        bkm = ys[k].imag
        bshkm = bsh[k]

        # - akm * Vk * amk * Vm * bkm * sin(Ɵkm + φkm - φmk) - akm * Vk * amk * Vm * gkm * cos(Ɵkm + φkm - φmk)
        mat[k, i] = - akm * Vk * amk * Vm * bkm * sin(Ɵkm + φkm - φmk) - akm * Vk * amk * Vm * gkm * cos(Ɵkm + φkm - φmk)

        #   akm * Vk * amk * Vm * bkm * sin(Ɵkm + φkm - φmk) + akm * Vk * amk * Vm * gkm * cos(Ɵkm + φkm - φmk)
        mat[k, j] = akm * Vk * amk * Vm * bkm * sin(Ɵkm + φkm - φmk) + akm * Vk * amk * Vm * gkm * cos(Ɵkm + φkm - φmk)

    return mat

# ----------------------------------------------------------------------------------------------------------------------


def dS_dVm_num(Cf, Yf, V, dx=1e-8):
    """
    Numerical derivative of the branch power w.r.t the voltage module
    :param Cf:
    :param Yf:
    :param V:
    :return:
    """
    m, n = Cf.shape
    Vm = np.abs(V)
    Va = np.angle(V)
    Vf = Cf * V
    Sf = Vf * np.conj(Yf * V)
    Pf = Sf.real
    Qf = Sf.imag

    mat_P = np.zeros((m, n))
    mat_Q = np.zeros((m, n))

    for i in range(n):
        V2 = V.copy()
        V2[i] = (Vm[i] + dx) * np.exp(1j * Va[i])
        Vf2 = Cf * V2
        Sf2 = Vf2 * np.conj(Yf * V2)
        mat_P[:, i] = (Sf2.real - Pf) / dx
        mat_Q[:, i] = (Sf2.imag - Qf) / dx

    return mat_P, mat_Q


def dS_dVa_num(Cf, Yf, V, dx=1e-8):
    """
    Numerical derivative of the branch power w.r.t the voltage module
    :param Cf:
    :param Yf:
    :param V:
    :return:
    """
    m, n = Cf.shape
    Vm = np.abs(V)
    Va = np.angle(V)
    Vf = Cf * V
    Sf = Vf * np.conj(Yf * V)
    Pf = Sf.real
    Qf = Sf.imag

    mat_P = np.zeros((m, n))
    mat_Q = np.zeros((m, n))

    for i in range(n):
        V2 = V.copy()
        V2[i] = Vm[i] * np.exp(1j * (Va[i] + dx))
        Vf2 = Cf * V2
        Sf2 = Vf2 * np.conj(Yf * V2)
        mat_P[:, i] = (Sf2.real - Pf) / dx
        mat_Q[:, i] = (Sf2.imag - Qf) / dx

    return mat_P, mat_Q

# ----------------------------------------------------------------------------------------------------------------------


def dPf_dVa_exposito(Cf, Y, V, F, T):
    """
    According to antonio exposito's book
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    m, n = Cf.shape
    G = Y.real
    B = Y.imag
    vm = np.abs(V)
    va = np.angle(V)

    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        va_ij = va[i] - va[j]
        mat[k, i] = vm[i] * vm[j] * (-G[i, j] * sin(va_ij) + B[i, j] * cos(va_ij))
        mat[k, j] = vm[i] * vm[j] * (G[i, j] * sin(va_ij) - B[i, j] * cos(va_ij))

    return mat


def dPf_dVm_exposito(Cf, Y, V, F, T):
    """
    Acording to antonio exposito's book
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    m, n = Cf.shape
    G = Y.real
    B = Y.imag
    vm = np.abs(V)
    va = np.angle(V)

    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        va_ij = va[i] - va[j]
        mat[k, i] = vm[j] * (G[i, j] * cos(va_ij) + B[i, j] * sin(va_ij)) - 2 * G[i, j] * vm[i]
        mat[k, j] = vm[i] * (G[i, j] * cos(va_ij) + B[i, j] * sin(va_ij))

    return mat


def dQf_dVa_exposito(Cf, Y, V, F, T):
    """
    Acording to antonio exposito's book
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    m, n = Cf.shape
    G = Y.real
    B = Y.imag
    vm = np.abs(V)
    va = np.angle(V)

    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        va_ij = va[i] - va[j]
        mat[k, i] = vm[i] * vm[j] * (G[i, j] * cos(va_ij) + B[i, j] * sin(va_ij))
        mat[k, j] = - vm[i] * vm[j] * (G[i, j] * cos(va_ij) + B[i, j] * sin(va_ij))

    return mat


def dQf_dVm_exposito(Cf, Y, V, F, T, bsh):
    """
    Acording to antonio exposito's book
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    m, n = Cf.shape
    G = Y.real
    B = Y.imag
    vm = np.abs(V)
    va = np.angle(V)

    mat = np.zeros((m, n))

    for k in range(m):
        i = F[k]
        j = T[k]
        va_ij = va[i] - va[j]
        mat[k, i] = vm[j] * (G[i, j] * sin(va_ij) - B[i, j] * cos(va_ij)) + 2 * vm[i] * (B[i, j] - bsh[k])
        mat[k, j] = vm[i] * (G[i, j] * sin(va_ij) - B[i, j] * cos(va_ij))

    return mat


def matpower_to_gomez_exposito_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # dSf_dVa, dSf_dVm = dSf_dV_fast(Yf, V, Vc, E, F, Cf)
    dSf_dVa, dSf_dVm = dSf_dV(Yf=nc.Yf, V=nc.Vbus, F=nc.branch_data.F, Cf=nc.Cf, Vc=np.conj(nc.Vbus), E=np.abs(nc.Vbus))

    # Gomez exposito derivatives
    dPf_dVa_exp = dPf_dVa_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T)
    dPf_dVm_exp = dPf_dVm_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T)
    dQf_dVa_exp = dQf_dVa_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T)
    dQf_dVm_exp = dQf_dVm_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T, bsh=nc.branch_data.B / 2)

    print('dPf/dVa matpower\n', dSf_dVa.real.toarray())
    print('dPf/dVa\n', dPf_dVa_exp)
    print('diff\n', dSf_dVa.real.toarray() - dPf_dVa_exp)
    print('err\n', np.max(np.abs(dSf_dVa.real.toarray() - dPf_dVa_exp)))
    print('_' * 100)

    print('dPf/dVm matpower\n', dSf_dVm.real.toarray())
    print('dPf/dVm\n', dPf_dVm_exp)  # not the same
    print('diff\n', dSf_dVm.real.toarray() - dPf_dVm_exp)
    print('err\n', np.max(np.abs(dSf_dVm.real.toarray() - dPf_dVm_exp)))
    print('_' * 100)

    print('dQf/dVa matpower\n', dSf_dVa.imag.toarray())
    print('dQf/dVa\n', dQf_dVa_exp)
    print('err\n', np.max(np.abs(dSf_dVa.imag.toarray() - dQf_dVa_exp)))
    print('_' * 100)

    print('dQf/dVm matpower\n', dSf_dVm.imag.toarray())
    print('dQf/dVm\n', dQf_dVm_exp)  # not the same
    print('err\n', np.max(np.abs(dSf_dVm.imag.toarray() - dQf_dVm_exp)))


def numerical_to_gomez_exposito_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # Numerical derivatives
    dPf_dVm_, dQf_dVm_ = dS_dVm_num(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus)
    dPf_dVa_, dQf_dVa_ = dS_dVa_num(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus)

    # Gomez exposito derivatives
    dPf_dVa_2 = dPf_dVa_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T)
    dPf_dVm_2 = dPf_dVm_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T)
    dQf_dVa_2 = dQf_dVa_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T)
    dQf_dVm_2 = dQf_dVm_exposito(Cf=nc.Cf, Y=nc.Ybus, V=nc.Vbus, F=F, T=T, bsh=nc.branch_data.B / 2)

    # print('dPf/dVa exposito\n', dPf_dVa_2)
    # print('dPf/dVa\n', dPf_dVa_)
    print('diff\n', dPf_dVa_2 - dPf_dVa_)
    print('err\n', np.max(np.abs(dPf_dVa_2 - dPf_dVa_)))
    print('_' * 100)

    # print('dPf/dVm exposito\n', dPf_dVm_2)
    # print('dPf/dVm\n', dPf_dVm_)
    print('diff\n', dPf_dVm_2 - dPf_dVm_)
    print('err\n', np.max(np.abs(dPf_dVm_2 - dPf_dVm_)))
    print('_' * 100)

    # print('dQf/dVa exposito\n', dQf_dVa_2)
    # print('dQf/dVa\n', dQf_dVa_)
    print('diff\n', dQf_dVa_2 - dQf_dVa_)
    print('err\n', np.max(np.abs(dQf_dVa_2 - dQf_dVa_)))
    print('_' * 100)

    print('dQf/dVm exposito\n', dQf_dVm_2)
    print('dQf/dVm numeric\n', dQf_dVm_)
    print('diff\n', dQf_dVm_2 - dQf_dVm_)
    print('err\n', np.max(np.abs(dQf_dVm_2 - dQf_dVm_)))


def numerical_to_monticelli_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # Numerical derivatives
    dPf_dVm_num, dQf_dVm_num = dS_dVm_num(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus)
    dPf_dVa_num, dQf_dVa_num = dS_dVa_num(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus)

    # Monticelli derivatives
    dPf_dVm_2 = dPf_dVm_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, ysh=ysh, tap_mod=tap_mod, tap_angle=tap_angle)
    dQf_dVm_2 = dQf_dVm_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, ysh=ysh, tap_mod=tap_mod, tap_angle=tap_angle)
    dPf_dVa_2 = dPf_dVa_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, ysh=ysh, tap_mod=tap_mod, tap_angle=tap_angle)
    dQf_dVa_2 = dQf_dVa_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, ysh=ysh, tap_mod=tap_mod, tap_angle=tap_angle)

    # print('dPf/dVa exposito\n', dPf_dVa_2)
    # print('dPf/dVa\n', dPf_dVa_)
    # print('diff dPf_dVa\n', dPf_dVa_2 - dPf_dVa_)
    # print('err dPf_dVa\n', np.max(np.abs(dPf_dVa_2 - dPf_dVa_)))
    # print('_' * 100)

    print('dPf/dVm monticelli\n', dPf_dVm_2)
    print('dPf/dVm numerical\n', dPf_dVm_num)
    print('diff dPf_dVm\n', dPf_dVm_2 - dPf_dVm_num)
    print('err dPf_dVm\n', np.max(np.abs(dPf_dVm_2 - dPf_dVm_num)))
    print('_' * 100)

    # print('dQf/dVa exposito\n', dQf_dVa_2)
    # print('dQf/dVa\n', dQf_dVa_)
    # print('diff dQf_dVa\n', dQf_dVa_2 - dQf_dVa_)
    # print('err dQf_dVa\n', np.max(np.abs(dQf_dVa_2 - dQf_dVa_)))
    # print('_' * 100)

    # print('dQf/dVm exposito\n', dQf_dVm_2)
    # print('dQf/dVm numeric\n', dQf_dVm_)
    # print('diff dQf_dVm\n', dQf_dVm_2 - dQf_dVm_)
    # print('err dQf_dVm\n', np.max(np.abs(dQf_dVm_2 - dQf_dVm_)))


def matpower_to_monticelli_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # Matpower derivatives
    dSf_dVa, dSf_dVm = dSf_dV(Yf=nc.Yf, V=nc.Vbus, F=nc.branch_data.F, Cf=nc.Cf, Vc=np.conj(nc.Vbus), E=np.abs(nc.Vbus))
    dPf_dVm_mat, dQf_dVm_mat = dSf_dVm.real.toarray(), dSf_dVm.imag.toarray()
    dPf_dVa_mat, dQf_dVa_mat = dSf_dVa.real.toarray(), dSf_dVa.imag.toarray()

    # Monticelli derivatives
    dPf_dVm_2 = dPf_dVm_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, bsh=nc.branch_data.B / 2, tap_mod=tap_mod, tap_angle=tap_angle)
    dQf_dVm_2 = dQf_dVm_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, bsh=nc.branch_data.B / 2, tap_mod=tap_mod, tap_angle=tap_angle)
    dPf_dVa_2 = dPf_dVa_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, bsh=nc.branch_data.B / 2, tap_mod=tap_mod, tap_angle=tap_angle)
    dQf_dVa_2 = dQf_dVa_monticelli(m=nc.nbr, n=nc.nbus, V=nc.Vbus, F=F, T=T, ys=ys, bsh=nc.branch_data.B / 2, tap_mod=tap_mod, tap_angle=tap_angle)

    print('dPf/dVa monticelli\n', dPf_dVa_2)
    print('dPf/dVa matpower\n', dPf_dVa_mat)
    print('diff dPf_dVa\n', dPf_dVa_2 - dPf_dVa_mat)
    print('err dPf_dVa\n', np.max(np.abs(dPf_dVa_2 - dPf_dVa_mat)))
    print('_' * 100)

    print('dPf/dVm monticelli\n', dPf_dVm_2)
    print('dPf/dVm matpower\n', dPf_dVm_mat)
    print('diff dPf_dVm\n', dPf_dVm_2 - dPf_dVm_mat)
    print('err dPf_dVm\n', np.max(np.abs(dPf_dVm_2 - dPf_dVm_mat)))
    print('_' * 100)

    print('dQf/dVa monticelli\n', dQf_dVa_2)
    print('dQf/dVa matpower\n', dQf_dVa_mat)
    print('diff dQf_dVa\n', dQf_dVa_2 - dQf_dVa_mat)
    print('err dQf_dVa\n', np.max(np.abs(dQf_dVa_2 - dQf_dVa_mat)))
    print('_' * 100)

    print('dQf/dVm monticelli\n', dQf_dVm_2)
    print('dQf/dVm matpower\n', dQf_dVm_mat)
    print('diff dQf_dVm\n', dQf_dVm_2 - dQf_dVm_mat)
    print('err dQf_dVm\n', np.max(np.abs(dQf_dVm_2 - dQf_dVm_mat)))


def matpower_to_numerical_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # Matpower derivatives
    dSf_dVa, dSf_dVm = dSf_dV(Yf=nc.Yf, V=nc.Vbus, F=nc.branch_data.F, Cf=nc.Cf, Vc=np.conj(nc.Vbus), E=np.abs(nc.Vbus))
    dPf_dVm_mat, dQf_dVm_mat = dSf_dVm.real.toarray(), dSf_dVm.imag.toarray()
    dPf_dVa_mat, dQf_dVa_mat = dSf_dVa.real.toarray(), dSf_dVa.imag.toarray()

    # Numerical derivatives
    dPf_dVm_num, dQf_dVm_num = dS_dVm_num(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus)
    dPf_dVa_num, dQf_dVa_num = dS_dVa_num(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus)

    print('dPf/dVa numerical\n', dPf_dVa_num)
    print('dPf/dVa matpower\n', dPf_dVa_mat)
    print('diff dPf_dVa\n', dPf_dVa_num - dPf_dVa_mat)
    print('err dPf_dVa\n', np.max(np.abs(dPf_dVa_num - dPf_dVa_mat)))
    print('_' * 100)

    print('dPf/dVm numerical\n', dPf_dVm_num)
    print('dPf/dVm matpower\n', dPf_dVm_mat)
    print('diff dPf_dVm\n', dPf_dVm_num - dPf_dVm_mat)
    print('err dPf_dVm\n', np.max(np.abs(dPf_dVm_num - dPf_dVm_mat)))
    print('_' * 100)

    print('dQf/dVa numerical\n', dQf_dVa_num)
    print('dQf/dVa matpower\n', dQf_dVa_mat)
    print('diff dQf_dVa\n', dQf_dVa_num - dQf_dVa_mat)
    print('err dQf_dVa\n', np.max(np.abs(dQf_dVa_num - dQf_dVa_mat)))
    print('_' * 100)

    print('dQf/dVm numerical\n', dQf_dVm_num)
    print('dQf/dVm matpower\n', dQf_dVm_mat)
    print('diff dQf_dVm\n', dQf_dVm_num - dQf_dVm_mat)
    print('err dQf_dVm\n', np.max(np.abs(dQf_dVm_num - dQf_dVm_mat)))

# ----------------------------------------------------------------------------------------------------------------------


if __name__ == '__main__':
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus (pq).gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 bus.raw'

    # matpower_to_gomez_exposito_comparison(fname)
    # numerical_to_gomez_exposito_comparison(fname)
    # numerical_to_monticelli_comparison(fname)
    # matpower_to_monticelli_comparison(fname)
    matpower_to_numerical_comparison(fname)


