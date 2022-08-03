
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


def dSf_dV_matpower(Yf, V, F, Cf, Vc, E):
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
    m, n = Cf.shape

    mat = np.zeros((m, n), dtype=complex)

    for k in range(m):
        f = F[k]
        t = T[k]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        
        # dSf_dVmf
        mat[k, f] = 2 * Vm_f * np.conj(Yf[k, f]) + Vm_t * np.conj(Yf[k, t]) * np.exp(th_f * 1j) * np.exp(-th_t * 1j)
        
        # dSf_dVmt
        mat[k, t] = Vm_f * np.conj(Yf[k, t]) * np.exp(th_f * 1j) * np.exp(-th_t * 1j)

    return mat


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
    m, n = Cf.shape

    mat = np.zeros((m, n), dtype=complex)

    for k in range(m):
        f = F[k]
        t = T[k]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])

        # dSf_dVaf
        mat[k, f] = Vm_f * Vm_t * np.conj(Yf[k, t]) * np.exp(th_f * 1j) * np.exp(-th_t * 1j) * 1j

        # dSf_dVat
        mat[k, t] = -Vm_f * Vm_t * np.conj(Yf[k, t]) * np.exp(th_f * 1j) * np.exp(-th_t * 1j) * 1j

    return mat


def matpower_to_spv_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # dSf_dVa, dSf_dVm = dSf_dV_fast(Yf, V, Vc, E, F, Cf)
    dSf_dVa_mat, dSf_dVm_mat = dSf_dV_matpower(Yf=nc.Yf, V=nc.Vbus, F=nc.branch_data.F, Cf=nc.Cf, Vc=np.conj(nc.Vbus), E=np.abs(nc.Vbus))

    # SPV derivatives
    dSf_dVa_spv = dSf_dVa(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus, F=F, T=T)
    dSf_dVm_spv = dSf_dVm(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus, F=F, T=T)

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
    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 bus.raw'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 bus.raw'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus v2.raw'

    #
    compare_power(fname)
    matpower_to_spv_comparison(fname)

