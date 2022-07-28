
import numpy as np
from math import sin, cos
from scipy.sparse import csc_matrix, diags
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
    :param diagVc: diagonal matrix of conjugate voltages
    :param diagE: diagonal matrix of normalized voltages
    :param diagV: diagonal matrix of voltages
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
        mat[i, k] = vm2[k] * t2[k] * g[i] + Pbr[i]
        mat[i, m] = - vm2[k] / vm[m] * t2[k] * g[i] + Pbr[i]

    return mat


def dPf_dVa(Cf, Y, V, F, T):
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
        mat[k, i] = vm[i] * vm[j] * (-G[i, j] * sin(va_ij) + B[i, j] * cos(va_ij))
        mat[k, j] = vm[i] * vm[j] * (G[i, j] * sin(va_ij) - B[i, j] * cos(va_ij))

    return mat


def dPf_dVm(Cf, Y, V, F, T):
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


def dQf_dVa(Cf, Y, V, F, T):
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


def dQf_dVm(Cf, Y, V, F, T, b):
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
        mat[k, i] = vm[j] * (G[i, j] * sin(va_ij) - B[i, j] * cos(va_ij)) + 2 * vm[i] * (B[i, j] - b[k])
        mat[k, j] = vm[i] * (G[i, j] * sin(va_ij) - B[i, j] * cos(va_ij))

    return mat


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':

    Y = np.array([[10.958904-25.997397j, -3.424658+7.534247j, -3.424658+7.534247j, 0.000000+0.000000j, -4.109589+10.958904j],
                  [-3.424658+7.534247j, 11.672080-26.060948j, -4.123711+9.278351j, 0.000000+0.000000j, -4.123711+9.278351j],
                  [-3.424658+7.534247j, -4.123711+9.278351j, 10.475198-23.119061j, -2.926829+6.341463j, 0.000000+0.000000j],
                  [0.000000+0.000000j, 0.000000+0.000000j, -2.926829+6.341463j, 7.050541-15.594814j, -4.123711+9.278351j],
                  [-4.109589+10.958904j, -4.123711+9.278351j, 0.000000+0.000000j, -4.123711+9.278351j, 12.357012-29.485605j]])
    Y = csc_matrix(Y)

    Yf = np.array([[-3.424658+7.534247j, 0.000000+0.000000j, 3.424658-7.524247j, 0.000000+0.000000j, 0.000000+0.000000j],
                   [0.000000+0.000000j, 0.000000+0.000000j, -2.926829+6.341463j, 2.926829-6.326463j, 0.000000+0.000000j],
                   [0.000000+0.000000j, 0.000000+0.000000j, 0.000000+0.000000j, -4.123711+9.278351j, 4.123711-9.268351j],
                   [0.000000+0.000000j, -4.123711+9.278351j, 0.000000+0.000000j, 0.000000+0.000000j, 4.123711-9.268351j],
                   [-4.109589+10.958904j, 0.000000+0.000000j, 0.000000+0.000000j, 0.000000+0.000000j, 4.109589-10.948904j],
                   [-3.424658+7.534247j, 3.424658-7.524247j, 0.000000+0.000000j, 0.000000+0.000000j, 0.000000+0.000000j],
                   [0.000000+0.000000j, 4.123711-9.268351j, -4.123711+9.278351j, 0.000000+0.000000j, 0.000000+0.000000j]])
    Yf = csc_matrix(Yf)

    Cf = np.array([[0.000000, 0.000000, 1.000000, 0.000000, 0.000000],
                   [0.000000, 0.000000, 0.000000, 1.000000, 0.000000],
                   [0.000000, 0.000000, 0.000000, 0.000000, 1.000000],
                   [0.000000, 0.000000, 0.000000, 0.000000, 1.000000],
                   [0.000000, 0.000000, 0.000000, 0.000000, 1.000000],
                   [0.000000, 1.000000, 0.000000, 0.000000, 0.000000],
                   [0.000000, 1.000000, 0.000000, 0.000000, 0.000000]])
    Cf = csc_matrix(Cf)

    V = np.array([1. + 0.j, 0.95446473-0.04008461j, 0.9540054 -0.03938094j, 0.93144092-0.0594139j, 0.95234448-0.0447275j])
    Vc = np.conj(V)
    E = V / np.abs(V)

    F = np.array([2, 3, 4, 4, 4, 1, 1])
    T = np.array([0, 2, 3, 1, 0, 0, 2])

    R = np.array([0.05, 0.06, 0.04, 0.04, 0.03, 0.05, 0.04])
    X = np.array([0.11, 0.13, 0.09, 0.09, 0.08, 0.11, 0.09])
    bsh = np.array([0.02, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02])
    tap_mod = np.array([1., 1., 1., 1., 1., 1., 1.])

    # dSf_dVa, dSf_dVm = dSf_dV_fast(Yf, V, Vc, E, F, Cf)
    dSf_dVa, dSf_dVm = dSf_dV(Yf, V, F, Cf, Vc, E)
    dPf_dVa_ = dPf_dVa(Cf, Y, V, F, T)
    dPf_dVm_ = dPf_dVm(Cf, Y, V, F, T)
    dQf_dVa_ = dQf_dVa(Cf, Y, V, F, T)
    dQf_dVm_ = dQf_dVm(Cf, Y, V, F, T, bsh/2)

    print('dP/dVa matpower\n', dSf_dVa.real.toarray())
    print('dP/dVa\n', dPf_dVa_)
    print('err\n', np.max(np.abs(dSf_dVa.real.toarray() - dPf_dVa_)))
    print('_' * 100)

    print('dP/dVm matpower\n', dSf_dVm.real.toarray())
    print('dP/dVm\n', dPf_dVm_)
    print('err\n', np.max(np.abs(dSf_dVm.real.toarray() - dPf_dVm_)))
    print('_' * 100)

    print('dQ/dVa matpower\n', dSf_dVa.imag.toarray())
    print('dQ/dVa\n', dQf_dVa_)
    print('err\n', np.max(np.abs(dSf_dVa.imag.toarray() - dQf_dVa_)))
    print('_' * 100)

    print('dQ/dVm matpower\n', dSf_dVm.imag.toarray())
    print('dQ/dVm\n', dQf_dVm_)
    print('err\n', np.max(np.abs(dSf_dVm.imag.toarray() - dQf_dVm_)))