
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
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Sf[k] = V[f] * np.conj(Yf[k, f] * V[f] + Yf[k, t] * V[t])

    return Sf

def getPowerElementT(F, T, V, Yt):

    Sf = np.zeros(len(F), dtype=complex)
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Sf[k] = V[t] * np.conj(Yt[k, f] * V[f] + Yt[k, t] * V[t])

    return Sf


def getPowerElement2F(F, T, V, Yf):
    Vm = np.abs(V)
    Va = np.angle(V)
    Gf = Yf.real
    Bf = Yf.imag
    Sf = np.zeros(len(F), dtype=complex)
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Sf[k] = Vm[f] * (cos(Va[f]) + 1j * sin(Va[f])) * (
                + Gf[k, f] * Vm[f] * cos(Va[f])
                - 1j * Gf[k, f] * Vm[f] * sin(Va[f])
                - 1j * Bf[k, f] * Vm[f] * cos(Va[f])
                - 1j * Bf[k, f] * Vm[f] * sin(Va[f])
                + Gf[k, t] * Vm[t] * cos(Va[t])
                - 1j * Gf[k, t] * Vm[t] * sin(Va[t])
                - 1j * Bf[k, t] * Vm[t] * cos(Va[t])
                - 1j * Bf[k, t] * Vm[t] * sin(Va[t])
                )

    return Sf


def getPowerElement2T(F, T, V, Yt):
    Vm = np.abs(V)
    Va = np.angle(V)
    Gt = Yt.real
    Bt = Yt.imag
    Sf = np.zeros(len(F), dtype=complex)
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Sf[k] = Vm[t] * (cos(Va[t]) + 1j * sin(Va[t])) * (
                + Gt[k, f] * Vm[f] * cos(Va[f])
                - 1j * Gt[k, f] * Vm[f] * sin(Va[f])
                - 1j * Bt[k, f] * Vm[f] * cos(Va[f])
                - 1j * Bt[k, f] * Vm[f] * sin(Va[f])
                + Gt[k, t] * Vm[t] * cos(Va[t])
                - 1j * Gt[k, t] * Vm[t] * sin(Va[t])
                - 1j * Bt[k, t] * Vm[t] * cos(Va[t])
                - 1j * Bt[k, t] * Vm[t] * sin(Va[t])
                )

    return Sf


def getPowerElement3F(F, T, V, Yf):
    Vm = np.abs(V)
    Va = np.angle(V)
    Gf = Yf.real
    Bf = Yf.imag
    Pf = np.zeros(len(F))
    Qf = np.zeros(len(F))
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Pf[k] = + Gf[k, f] * Vm[f]**2 * cos(Va[f])**2 \
                + Bf[k, f] * Vm[f]**2 * sin(Va[f])**2 \
                + Gf[k, f] * Vm[f]**2 * sin(Va[f])**2 \
                + Bf[k, f] * Vm[f]**2 * cos(Va[f]) * sin(Va[f]) \
                + Gf[k, t] * Vm[f] * Vm[t] * cos(Va[f]) * cos(Va[t])  \
                + Bf[k, t] * Vm[f] * Vm[t] * cos(Va[t]) * sin(Va[f]) \
                + Bf[k, t] * Vm[f] * Vm[t] * sin(Va[f]) * sin(Va[t]) \
                + Gf[k, t] * Vm[f] * Vm[t] * sin(Va[f]) * sin(Va[t])

        Qf[k] = - Bf[k, f] * Vm[f]**2 * cos(Va[f])**2 \
                - Bf[k, f] * Vm[f]**2 * cos(Va[f]) * sin(Va[f]) \
                - Bf[k, t] * Vm[f] * Vm[t] * cos(Va[f]) * cos(Va[t]) \
                - Bf[k, t] * Vm[f] * Vm[t] * cos(Va[f]) * sin(Va[t]) \
                - Gf[k, t] * Vm[f] * Vm[t] * cos(Va[f]) * sin(Va[t]) \
                + Gf[k, t] * Vm[f] * Vm[t] * cos(Va[t]) * sin(Va[f])

    return Pf + 1j * Qf


def getPowerElement3T(F, T, V, Yt):
    Vm = np.abs(V)
    Va = np.angle(V)
    Gt = Yt.real
    Bt = Yt.imag
    Pf = np.zeros(len(F))
    Qf = np.zeros(len(F))
    for k in range(len(F)):
        f = F[k]
        t = T[k]
        Pf[k] = + Gt[k, t] * Vm[t]**2 * cos(Va[t])**2 \
                + Bt[k, t] * Vm[t]**2 * sin(Va[t])**2 \
                + Gt[k, t] * Vm[t]**2 * sin(Va[t])**2 \
                + Bt[k, t] * Vm[t]**2 * cos(Va[t]) * sin(Va[t]) \
                + Gt[k, f] * Vm[f] * Vm[t] * cos(Va[f]) * cos(Va[t]) \
                + Bt[k, f] * Vm[f] * Vm[t] * cos(Va[f]) * sin(Va[t]) \
                + Bt[k, f] * Vm[f] * Vm[t] * sin(Va[f]) * sin(Va[t]) \
                + Gt[k, f] * Vm[f] * Vm[t] * sin(Va[f]) * sin(Va[t])

        Qf[k] = - Bt[k, t] * Vm[t]**2 * cos(Va[t])**2 \
                - Bt[k, t] * Vm[t]**2 * cos(Va[t]) * sin(Va[t]) \
                - Bt[k, f] * Vm[f] * Vm[t] * cos(Va[f]) * cos(Va[t]) \
                - Bt[k, f] * Vm[f] * Vm[t] * cos(Va[t]) * sin(Va[f]) \
                + Gt[k, f] * Vm[f] * Vm[t] * cos(Va[f]) * sin(Va[t]) \
                - Gt[k, f] * Vm[f] * Vm[t] * cos(Va[t]) * sin(Va[f])

    return Pf + 1j * Qf
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

def dPf_dVa(Cf, Yf, V, F, T):
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

    mat = np.zeros((m, n))

    for k in range(m):
        f = F[k]
        t = T[k]
        Gf_kf = Yf[k, f].real
        Bf_kf = Yf[k, f].imag
        Gf_kt = Yf[k, t].real
        Bf_kt = Yf[k, t].imag
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        Va_f = np.angle(V[f])
        Va_t = np.angle(V[t])
        
        # dPf_dVaf
        mat[k, f] = + Bf_kf * Vm_f**2 * cos(Va_f)**2 \
                    - Bf_kf * Vm_f**2 * sin(Va_f)**2 \
                    + 2 * Bf_kf * Vm_f**2 * cos(Va_f) * sin(Va_f) \
                    + Bf_kt * Vm_f * Vm_t * cos(Va_f) * cos(Va_t) \
                    + Bf_kt * Vm_f * Vm_t * cos(Va_f) * sin(Va_t) \
                    + Gf_kt * Vm_f * Vm_t * cos(Va_f) * sin(Va_t) \
                    - Gf_kt * Vm_f * Vm_t * cos(Va_t) * sin(Va_f)
        
        # dPf_dVat
        mat[k, t] = + Bf_kt * Vm_f * Vm_t * cos(Va_t) * sin(Va_f)  \
                    - Gf_kt * Vm_f * Vm_t * cos(Va_f) * sin(Va_t)  \
                    + Gf_kt * Vm_f * Vm_t * cos(Va_t) * sin(Va_f)  \
                    - Bf_kt * Vm_f * Vm_t * sin(Va_f) * sin(Va_t) 

    return mat


def dPf_dVm(Cf, Yf, V, F, T):
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

    mat = np.zeros((m, n))

    for k in range(m):
        f = F[k]
        t = T[k]
        Gf_kf = Yf[k, f].real
        Bf_kf = Yf[k, f].imag
        Gf_kt = Yf[k, t].real
        Bf_kt = Yf[k, t].imag
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        Va_f = np.angle(V[f])
        Va_t = np.angle(V[t])
        
        mat[k, f] = + 2 * Gf_kf * Vm_f * cos(Va_f)**2 \
                    + 2 * Bf_kf * Vm_f * sin(Va_f)**2 \
                    + 2 * Gf_kf * Vm_f * sin(Va_f)**2 \
                    + Gf_kt * Vm_t * cos(Va_f) * cos(Va_t) \
                    + 2 * Bf_kf * Vm_f * cos(Va_f) * sin(Va_f) \
                    + Bf_kt * Vm_t * cos(Va_t) * sin(Va_f) \
                    + Bf_kt * Vm_t * sin(Va_f) * sin(Va_t) \
                    + Gf_kt * Vm_t * sin(Va_f) * sin(Va_t)

        mat[k, t] = + Gf_kt * Vm_f * cos(Va_f) * cos(Va_t) \
                    + Bf_kt * Vm_f * cos(Va_t) * sin(Va_f) \
                    + Bf_kt * Vm_f * sin(Va_f) * sin(Va_t) \
                    + Gf_kt * Vm_f * sin(Va_f) * sin(Va_t)

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


def dQf_dVm(Cf, Y, V, F, T, bs, bsh):
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


def matpower_to_gomez_comparison(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)
    ys = 1. / (nc.branch_data.R + 1j * nc.branch_data.X)
    ysh = nc.branch_data.G + 1j * nc.branch_data.B
    F = nc.branch_data.F
    T = nc.branch_data.T
    tap_mod = nc.branch_data.m[:, 0]
    tap_angle = nc.branch_data.theta[:, 0]

    # dSf_dVa, dSf_dVm = dSf_dV_fast(Yf, V, Vc, E, F, Cf)
    dSf_dVa, dSf_dVm = dSf_dV_matpower(Yf=nc.Yf, V=nc.Vbus, F=nc.branch_data.F, Cf=nc.Cf)

    # Gomez exposito derivatives
    dPf_dVa_exp = dPf_dVa(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus, F=F, T=T)
    dPf_dVm_exp = dPf_dVm(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus, F=F, T=T)
    # dQf_dVa_exp = dQf_dVa(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus, F=F, T=T)
    # dQf_dVm_exp = dQf_dVm(Cf=nc.Cf, Yf=nc.Yf, V=nc.Vbus, F=F, T=T)

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

    # print('dQf/dVa matpower\n', dSf_dVa.imag.toarray())
    # print('dQf/dVa\n', dQf_dVa_exp)
    # print('err\n', np.max(np.abs(dSf_dVa.imag.toarray() - dQf_dVa_exp)))
    # print('_' * 100)
    #
    # print('dQf/dVm matpower\n', dSf_dVm.imag.toarray())
    # print('dQf/dVm\n', dQf_dVm_exp)  # not the same
    # print('err\n', np.max(np.abs(dSf_dVm.imag.toarray() - dQf_dVm_exp)))


def compare_power(fname):
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)

    Sf_matpower = getPowerVectorial(F=nc.branch_data.F, V=nc.Vbus, Yf=nc.Yf)
    Sf_element = getPowerElement3F(F=nc.branch_data.F, T=nc.branch_data.T, V=nc.Vbus, Yf=nc.Yf)

    diffP = Sf_matpower.real - Sf_element.real
    diffQ = Sf_matpower.imag - Sf_element.imag

    print(diffP)
    print(diffQ)
    print(np.max(np.abs(diffP)))
    print(np.max(np.abs(diffQ)))

    St_matpower = getPowerVectorial(F=nc.branch_data.T, V=nc.Vbus, Yf=nc.Yt)
    St_element = getPowerElement3T(F=nc.branch_data.F, T=nc.branch_data.T, V=nc.Vbus, Yt=nc.Yt)

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
    # matpower_to_gomez_comparison(fname)

