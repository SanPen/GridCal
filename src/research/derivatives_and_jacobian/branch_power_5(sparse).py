
import numpy as np
from math import sin, cos
from scipy.sparse import csc_matrix, diags
import GridCal.Engine as gc
np.set_printoptions(linewidth=1000000)

# ----------------------------------------------------------------------------------------------------------------------


def getPowerVectorial(F, V, Yf):
    return V[F] * np.conj(Yf * V)


def getPowerElementF(F, T, V, Yf):

    Sf = np.zeros(len(F), dtype=complex)
    Vm = np.abs(V)
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Sf[k] = Vm[f] * Vm[f] * np.conj(Yf[k, f]) + V[f] * np.conj(V[t] * Yf[k, t])
        # Sf[k] = V[f] * np.conj(Yf[k, f] * V[f] + Yf[k, t] * V[t])

    return Sf


def getPowerElementT(F, T, V, Yt):

    Sf = np.zeros(len(F), dtype=complex)
    Vm = np.abs(V)
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Sf[k] = Vm[t] * Vm[t] * np.conj(Yt[k, t]) + V[t] * np.conj(V[f] * Yt[k, f])
        # Sf[k] = V[t] * np.conj(Yt[k, f] * V[f] + Yt[k, t] * V[t])

    return Sf

# ----------------------------------------------------------------------------------------------------------------------


def dSf_dV_matpower(Yf, V, F, Cf):
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

    Yfc = np.conj(Yf)
    Vc = np.conj(V)
    Ifc = Yfc * Vc

    Vnorm = V / np.abs(V)
    diagV = diags(V)
    diagVc = diags(Vc)
    diagVnorm = diags(Vnorm)
    diagVf = diags(V[F])
    diagIfc = diags(Ifc)

    CVf = Cf * diagV
    CVnf = Cf * diagVnorm

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc) #  dSf_dVa
    dSf_dVm = diagVf * np.conj(Yf * diagVnorm) + diagIfc * CVnf #  dSf_dVm

    # dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc) #  dSt_dVa
    # dSt_dVm = diagVt * conj(Yt * diagVnorm) + diagItc * CVnt #  dSt_dVm

    return dSf_dVa.tocsc(), dSf_dVm.tocsc()

# ----------------------------------------------------------------------------------------------------------------------


def dSf_dVm(Cf, Yf, V, F, T):
    """
    derived by SPV
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    # m, n = Cf.shape
    #
    # mat = np.zeros((m, n), dtype=complex)
    #
    # for k in range(m):
    #     f = F[k]
    #     t = T[k]
    #     Vm_f = np.abs(V[f])
    #     Vm_t = np.abs(V[t])
    #     th_f = np.angle(V[f])
    #     th_t = np.angle(V[t])
    #
    #     # dSf_dVmf
    #     mat[k, f] = 2 * Vm_f * np.conj(Yf[k, f]) + Vm_t * np.conj(Yf[k, t]) * np.exp((th_f - th_t) * 1j)
    #
    #     # dSf_dVmt
    #     mat[k, t] = Vm_f * np.conj(Yf[k, t]) * np.exp((th_f - th_t) * 1j)

    """
        CSC format
         0  1  2
        _________
    0  | 4       |
    1  | 3  9    |
    2  |    7  8 |
    3  | 3     8 |
    4  |    8  9 |
    5  |    4    |
        ---------
        columnas = 3
        filas = 6
    
     índices -> 0  1  2  3  4  5  6  7  8  9   
     data    = [4, 3, 3, 9, 7, 8, 4, 8, 8, 9]
     indices = [0, 1, 3, 1, 2, 4, 5, 2, 3, 4]  (row indices)
     indptr  = [0, 3, 7, 10]
    
    """
    # map the i, j coordinates
    idx_f = np.zeros(Yf.shape[0], dtype=int)
    idx_t = np.zeros(Yf.shape[0], dtype=int)
    for j in range(Yf.shape[1]):  # para cada columna j ...
        for k in range(Yf.indptr[j], Yf.indptr[j + 1]):  # para cada entrada de la columna ....
            i = Yf.indices[k]  # obtener el índice de la fila

            if j == F[i]:
                idx_f[i] = k
            elif j == T[i]:
                idx_t[i] = k

    # traverse the rows
    data2 = np.zeros(Yf.nnz, dtype=complex)
    for k in range(Yf.shape[0]):  # number of branches
        f = F[k]
        t = T[k]
        kf = idx_f[k]
        kt = idx_t[k]

        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])

        data2[kf] = 2 * Vm_f * np.conj(Yf.data[kf]) + Vm_t * np.conj(Yf.data[kt]) * np.exp((th_f - th_t) * 1j)
        data2[kt] = Vm_f * np.conj(Yf.data[kt]) * np.exp((th_f - th_t) * 1j)

    return csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)


def dSf_dVa(Cf, Yf, V, F, T):
    """
    derived by SPV
    :param Cf:
    :param Y:
    :param V:
    :param F:
    :param T:
    :return:
    """
    # m, n = Cf.shape
    #
    # mat = np.zeros((m, n), dtype=complex)
    #
    # for k in range(m):
    #     f = F[k]
    #     t = T[k]
    #     Vm_f = np.abs(V[f])
    #     Vm_t = np.abs(V[t])
    #     th_f = np.angle(V[f])
    #     th_t = np.angle(V[t])
    #
    #     # dSf_dVaf
    #     mat[k, f] = Vm_f * Vm_t * np.conj(Yf[k, t]) * np.exp((th_f - th_t) * 1j) * 1j
    #
    #     # dSf_dVat
    #     mat[k, t] = -Vm_f * Vm_t * np.conj(Yf[k, t]) * np.exp((th_f - th_t) * 1j) * 1j

    # map the i, j coordinates
    idx_f = np.zeros(Yf.shape[0], dtype=int)
    idx_t = np.zeros(Yf.shape[0], dtype=int)
    for j in range(Yf.shape[1]):  # para cada columna j ...
        for k in range(Yf.indptr[j], Yf.indptr[j + 1]):  # para cada entrada de la columna ....
            i = Yf.indices[k]  # obtener el índice de la fila

            if j == F[i]:
                idx_f[i] = k
            elif j == T[i]:
                idx_t[i] = k

    # traverse the rows
    data2 = np.zeros(Yf.nnz, dtype=complex)
    for k in range(Yf.shape[0]):  # number of branches
        f = F[k]
        t = T[k]
        kf = idx_f[k]
        kt = idx_t[k]

        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])

        data2[kf] = Vm_f * Vm_t * np.conj(Yf.data[kt]) * np.exp((th_f - th_t) * 1j) * 1j
        data2[kt] = -Vm_f * Vm_t * np.conj(Yf.data[kt]) * np.exp((th_f - th_t) * 1j) * 1j

    return csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)


def matpower_to_spv_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    F = nc.branch_data.F
    T = nc.branch_data.T

    print('V0r:', nc.Vbus.real)
    print('V0i:', nc.Vbus.imag)

    # dSf_dVa, dSf_dVm = dSf_dV_fast(Yf, V, Vc, E, F, Cf)
    dSf_dVa_mat, dSf_dVm_mat = dSf_dV_matpower(Yf=nc.Yf, V=nc.Vbus, F=nc.branch_data.F, Cf=nc.Cf)

    # SPV derivatives
    dSf_dVa_spv = dSf_dVa(Cf=nc.Cf, Yf=nc.Yf.tocsc(), V=nc.Vbus, F=F, T=T).toarray()
    dSf_dVm_spv = dSf_dVm(Cf=nc.Cf, Yf=nc.Yf.tocsc(), V=nc.Vbus, F=F, T=T).toarray()

    dPf_dVa_spv, dQf_dVa_spv = dSf_dVa_spv.real, dSf_dVa_spv.imag
    dPf_dVm_spv, dQf_dVm_spv = dSf_dVm_spv.real, dSf_dVm_spv.imag

    print('dPf/dVa matpower\n', dSf_dVa_mat.real.toarray())
    print('dPf/dVa SPV\n', dPf_dVa_spv)
    print('diff\n', dSf_dVa_mat.real.toarray() - dPf_dVa_spv)
    print('err\n', np.max(np.abs(dSf_dVa_mat.real.toarray() - dPf_dVa_spv)))
    print('_' * 100)

    print('dQf/dVa matpower\n', dSf_dVa_mat.imag.toarray())
    print('dQf/dVa SPV\n', dQf_dVa_spv)
    print('diff\n', dSf_dVa_mat.imag.toarray() - dQf_dVa_spv)
    print('err\n', np.max(np.abs(dSf_dVa_mat.imag.toarray() - dQf_dVa_spv)))
    print('_' * 100)

    print('dPf/dVm matpower\n', dSf_dVm_mat.real.toarray())
    print('dPf/dVm SPV\n', dPf_dVm_spv)  # not the same
    print('diff\n', dSf_dVm_mat.real.toarray() - dPf_dVm_spv)
    print('err\n', np.max(np.abs(dSf_dVm_mat.real.toarray() - dPf_dVm_spv)))
    print('_' * 100)

    print('dQf/dVm matpower\n', dSf_dVm_mat.imag.toarray())
    print('dQf/dVm SPV\n', dQf_dVm_spv)  # not the same
    print('diff\n', dSf_dVm_mat.imag.toarray() - dQf_dVm_spv)
    print('err\n', np.max(np.abs(dSf_dVm_mat.imag.toarray() - dQf_dVm_spv)))


def compare_power(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)

    Sf_matpower = getPowerVectorial(F=nc.branch_data.F, V=nc.Vbus, Yf=nc.Yf)
    Sf_element = getPowerElementF(F=nc.branch_data.F, T=nc.branch_data.T, V=nc.Vbus, Yf=nc.Yf)

    diffP = Sf_matpower.real - Sf_element.real
    diffQ = Sf_matpower.imag - Sf_element.imag

    print(diffP)
    print(diffQ)
    print(np.max(np.abs(diffP)))
    print(np.max(np.abs(diffQ)))

    St_matpower = getPowerVectorial(F=nc.branch_data.T, V=nc.Vbus, Yf=nc.Yt)
    St_element = getPowerElementT(F=nc.branch_data.F, T=nc.branch_data.T, V=nc.Vbus, Yt=nc.Yt)

    diffP = St_matpower.real - St_element.real
    diffQ = St_matpower.imag - St_element.imag

    print(diffP)
    print(diffQ)
    print(np.max(np.abs(diffP)))
    print(np.max(np.abs(diffQ)))

# ----------------------------------------------------------------------------------------------------------------------


if __name__ == '__main__':
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus (pq).gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 bus.raw'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 bus.raw'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus v2.raw'
    # fname = '/home/santi/matpower7.0/data/case14.m'
    #
    fname = r'C:\Git\Github\GridCal\Grids_and_profiles\grids\IEEE 14 bus.raw'
    compare_power(fname)
    matpower_to_spv_comparison(fname)

