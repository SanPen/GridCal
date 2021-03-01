# PGD code, generic
import time
import pandas as pd
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sp_linalg
import sys
import numba as nb
from math import ceil, floor


pd.options.display.precision = 2
pd.set_option('display.precision', 2)


def progress_bar(i, n, size):
    percent = float(i) / float(n)
    sys.stdout.write("\r"
                     + str(int(i)).rjust(3, '0')
                     + "/"
                     + str(int(n)).rjust(3, '0')
                     + ' ['
                     + '='*ceil(percent*size)
                     + ' '*floor((1-percent)*size)
                     + ']')


def read_grid_data(fname):
    """
    Read the grid data
    :param fname: name of the excel file
    :return: n_buses, Qmax, Qmin, Y, Yinv, V_mod, P_pq, Q_pq, P_pv, I0_pq, n_pv, n_pq
    """
    df_b = pd.read_excel(fname, sheet_name="buses")
    df_l = pd.read_excel(fname, sheet_name="lines")

    # BEGIN INITIALIZATION OF DATA
    n_b = 0
    n_pq = 0
    n_pv = 0
    pq = []
    pv = []
    pq0 = []  # store pq buses indices relative to its own
    pv0 = []  # store pv buses indices relative to its own
    d_pq = {}  # dict of pq
    d_pv = {}  # dict of pv
    for i in range(len(df_b)):
        if df_b.iloc[i, 4] == "slack":  # index 0 is reserved for the slack bus
            pass

        elif df_b.iloc[i, 4] == "PQ":
            pq0.append(n_pq)
            d_pq[df_b.iloc[i, 0]] = n_pq
            n_b += 1
            n_pq += 1
            pq.append(df_b.iloc[i, 0] - 1)

        elif df_b.iloc[i, 4] == "PV":
            pv0.append(n_pv)
            d_pv[df_b.iloc[i, 0]] = n_pv
            n_b += 1
            n_pv += 1
            pv.append(df_b.iloc[i, 0] - 1)

    n_l = len(df_l)  # number of lines

    V0 = df_b.iloc[0, 3]  # the slack is always positioned in the first row
    I0_pq = np.zeros(n_pq, dtype=complex)
    I0_pv = np.zeros(n_pv, dtype=complex)
    Y = np.zeros((n_b, n_b), dtype=complex)  # I will build it with block matrices
    Y11 = np.zeros((n_pq, n_pq), dtype=complex)  # pq pq
    Y12 = np.zeros((n_pq, n_pv), dtype=complex)  # pq pv
    Y21 = np.zeros((n_pv, n_pq), dtype=complex)  # pv pq
    Y22 = np.zeros((n_pv, n_pv), dtype=complex)  # pv pv

    for i in range(n_l):
        Ys = 1 / (df_l.iloc[i, 2] + 1j * df_l.iloc[i, 3])  # series element
        Ysh = df_l.iloc[i, 4] + 1j * df_l.iloc[i, 5]  # shunt element
        t = df_l.iloc[i, 6] * np.cos(df_l.iloc[i, 7]) + 1j * df_l.iloc[i, 6] * np.sin(df_l.iloc[i, 7])  # tap as a complex number

        a = df_l.iloc[i, 0]
        b = df_l.iloc[i, 1]

        if a == 0:
            if b - 1 in pq:
                I0_pq[d_pq[b]] += V0 * Ys / t
                Y11[d_pq[b], d_pq[b]] += Ys + Ysh
            if b - 1 in pv:
                I0_pv[d_pv[b]] += V0 * Ys / t
                Y22[d_pv[b], d_pv[b]] += Ys + Ysh

        elif b == 0:
            if a - 1 in pq:
                I0_pq[d_pq[a]] += V0 * Ys / np.conj(t)
                Y11[d_pq[a], d_pq[a]] += (Ys + Ysh) / (t * np.conj(t))
            if a - 1 in pv:
                I0_pv[d_pv[a]] += V0 * Ys / np.conj(t)
                Y22[d_pv[a], d_pv[a]] += (Ys + Ysh) / (t * np.conj(t))

        else:
            if a - 1 in pq and b - 1 in pq:
                Y11[d_pq[a], d_pq[a]] += (Ys + Ysh) / (t * np.conj(t))
                Y11[d_pq[b], d_pq[b]] += Ys + Ysh
                Y11[d_pq[a], d_pq[b]] += - Ys / np.conj(t)
                Y11[d_pq[b], d_pq[a]] += - Ys / t

            if a - 1 in pq and b - 1 in pv:
                Y11[d_pq[a], d_pq[a]] += (Ys + Ysh) / (t * np.conj(t))
                Y22[d_pv[b], d_pv[b]] += Ys + Ysh
                Y12[d_pq[a], d_pv[b]] += - Ys / np.conj(t)
                Y21[d_pv[b], d_pq[a]] += - Ys / t

            if a - 1 in pv and b - 1 in pq:
                Y22[d_pv[a], d_pv[a]] += (Ys + Ysh) / (t * np.conj(t))
                Y11[d_pq[b], d_pq[b]] += Ys + Ysh
                Y21[d_pv[a], d_pq[b]] += - Ys / np.conj(t)
                Y12[d_pq[b], d_pv[a]] += - Ys / t

            if a - 1 in pv and b - 1 in pv:
                Y22[d_pv[a], d_pv[a]] += (Ys + Ysh) / (t * np.conj(t))
                Y22[d_pv[b], d_pv[b]] += Ys + Ysh
                Y22[d_pv[a], d_pv[b]] += - Ys / np.conj(t)
                Y22[d_pv[b], d_pv[a]] += - Ys / t

    # add shunts connected directly to the bus
    for i in range(len(df_b)):
        a = df_b.iloc[i, 0]
        if a - 1 in pq:
            Y11[d_pq[a], d_pq[a]] += df_b.iloc[i, 5] + 1j * df_b.iloc[i, 6]

        elif a - 1 in pv:
            Y22[d_pv[a], d_pv[a]] += df_b.iloc[i, 5] + 1j * df_b.iloc[i, 6]

    Y = np.block([[Y11, Y12], [Y21, Y22]])
    Yinv = np.linalg.inv(Y)

    V_mod = np.zeros(n_pv, dtype=float)
    P_pq = np.zeros(n_pq, dtype=float)
    P_pv = np.zeros(n_pv, dtype=float)
    Q_pq = np.zeros(n_pq, dtype=float)
    for i in range(len(df_b)):
        if df_b.iloc[i, 4] == "PV":
            V_mod[d_pv[df_b.iloc[i, 0]]] = df_b.iloc[i, 3]
            P_pv[d_pv[df_b.iloc[i, 0]]] = df_b.iloc[i, 1]
        elif df_b.iloc[i, 4] == "PQ":
            Q_pq[d_pq[df_b.iloc[i, 0]]] = df_b.iloc[i, 2]
            P_pq[d_pq[df_b.iloc[i, 0]]] = df_b.iloc[i, 1]

    n_buses = np.shape(Y)[0]  # number of buses

    Qmax = 1.00  # maximum reactive power of the capacitor
    Qmin = 0  # minimum reactive power of the capacitor
    # END INITIALIZATION OF DATA

    return n_buses, Qmax, Qmin, sp.csc_matrix(Y), V_mod, P_pq, Q_pq, P_pv, I0_pq, n_pv, n_pq


def init_apparent_powers_decomposition(n_buses, n_scale, P_pq, Q_pq, Qmin, Qmax):
    """

    :param n_buses:
    :param n_scale:
    :param P_pq:
    :param Q_pq:
    :param Qmin:
    :param Qmax:
    :return:
    """
    # DECOMPOSITION OF APPARENT POWERS
    SSk = np.empty((2, n_buses), dtype=complex)
    SSp = np.empty((2, n_buses), dtype=complex)
    SSq = np.empty((2, n_scale), dtype=complex)

    SKk0 = P_pq + Q_pq * 1j  # original load
    SPp0 = np.ones(n_buses)  # positions of standard the loads
    SQq0 = np.ones(n_scale)  # always multiply by a factor of 1, the original loads do not change

    SSk[0, :] = np.conj(SKk0)
    SSp[0, :] = np.conj(SPp0)
    SSq[0, :] = np.conj(SQq0)

    # go over all positions where we could have a capacitor (from bus 2 to 102)
    """
    for ii in range(2, n_buses):
        SKk1 = np.zeros(n_buses, dtype=complex)  # power amplitude, in this case, it will be reactive
        SKk1[ii] = Qmax * 1j  # put a 1 because only one capacitor at a time. This is the maximum capacitor power
        SPp1 = np.zeros(n_buses)  # possible positions of the capacitor
        SPp1[ii] = 1
        SQq1 = np.arange(Qmin, Qmax, Qmax / n_scale)  # scale the powers in a discrete form
        SSk.append(np.conj(SKk1))
        SSp.append(np.conj(SPp1))
        SSq.append(np.conj(SQq1))
    """
    # keep it simple, consider by now less cases
    # ----------
    # SKk1 = np.zeros(n_buses, dtype=complex)
    # SKk1[0] = Qmax * 1j
    SKk1 = 1 * np.random.rand(n_buses)  # generator of random active power
    SPp1 = np.zeros(n_buses)

    # for ii in range(2, n_buses):
    for ii in range(n_buses):  # only a few buses
        SPp1[ii] = ii / n_buses  # for instance
    SQq1 = np.arange(Qmin, Qmax, Qmax / n_scale)

    SSk[1, :] = np.conj(SKk1)
    SSp[1, :] = np.conj(SPp1)
    SSq[1, :] = np.conj(SQq1)

    return SSk, SSp, SSq


def init_voltages_decomposition(n_mm, n_buses, n_scale):
    """

    :param n_buses:
    :param n_scale:
    :return:
    """
    # DECOMPOSITION OF VOLTAGES
    VVk = np.zeros((n_mm + 1, n_buses), dtype=complex)
    VVp = np.zeros((n_mm + 1, n_buses), dtype=complex)
    VVq = np.zeros((n_mm + 1, n_scale), dtype=complex)

    Kkv = np.ones(n_buses, dtype=complex)  # amplitude vector
    Ppv = np.ones(n_buses)  # position vector
    Qqv = np.ones(n_scale)  # scaling vector

    VVk[0, :] = np.conj(Kkv)
    VVp[0, :] = np.conj(Ppv)
    VVq[0, :] = np.conj(Qqv)

    return VVk, VVp, VVq


def init_currents_decomposition(n_gg, n_mm, nbus, n_scale):
    """

    :return:
    """
    # DECOMPOSITION OF CURRENTS
    IIk = np.zeros((n_gg * n_mm, nbus), dtype=complex)
    IIp = np.zeros((n_gg * n_mm, nbus), dtype=complex)
    IIq = np.zeros((n_gg * n_mm, n_scale), dtype=complex)
    return IIk, IIp, IIq


@nb.njit()
def fun_C(SSk, SSp, SSq, VVk, VVp, VVq, IIk, IIp, IIq, n_i_coeff, n_v_coeff, n_bus, n_scale):
    """
    # CREATION OF C (auxiliary variables).
    # THIS FUNCTION HAS TO BE CALLED EVERY TIME WE COMPUTE A NEW RESIDUE OF I, AND ALWAYS FOLLOWS THIS
    :param SSk:
    :param SSp:
    :param SSq:
    :param VVk:
    :param VVp:
    :param VVq:
    :param IIk:
    :param IIp:
    :param IIq:
    :param n: number of coefficients fo far
    :return:
    """
    Ns = SSk.shape[0]
    Nc = Ns + n_v_coeff * n_i_coeff

    CCk = np.empty((Nc, n_bus), dtype=np.complex128)
    CCp = np.empty((Nc, n_bus), dtype=np.complex128)
    CCq = np.empty((Nc, n_scale), dtype=np.complex128)

    # initialize with the S* decomposed variables
    CCk[:2, :] = SSk
    CCp[:2, :] = SSp
    CCq[:2, :] = SSq
    for ii in range(n_v_coeff):
        for jj in range(n_i_coeff):
            idx = ii * n_i_coeff + jj + 2  # this is the "count-like" index (+2 is the offset)
            CCk[idx, :] = - VVk[ii, :] * IIk[jj, :]
            CCp[idx, :] = - VVp[ii, :] * IIp[jj, :]
            CCq[idx, :] = - VVq[ii, :] * IIq[jj, :]

    return CCk, CCp, CCq, Nc, n_v_coeff, n_i_coeff


@nb.njit()
def build_map(MMk, MMp, MMq):
    """
    Build 3-D mapping from decomposed variables bu adding the individual 3D decomposed tensors
    :param MMk: 2D array
    :param MMp: 2D array
    :param MMq: 2D array
    :return: 3D array
    """
    # the tri-dimensional representation I am looking for
    n = MMk.shape[0]
    nnk = MMk.shape[1]
    nnp = MMp.shape[1]
    nnq = MMq.shape[1]
    MM_map = np.zeros((nnk, nnp, nnq), dtype=np.complex128)
    for d in range(n):
        for k in range(nnk):
            for p in range(nnp):
                val = MMk[d, k] * MMp[d, p]  # if I do this here, I do less operations
                for q in range(nnq):
                    # MMk[d, k] * MMp[d, p] * MMq[d, q]
                    MM_map[k, p, q] += val * MMq[d, q]

        # progress_bar(d + 1, n, 50)

    return MM_map


def save_map(MM_map, fname):
    """

    :param MM_map: 3D tensor
    :param fname:
    :return:
    """
    writer = pd.ExcelWriter(fname)
    for i in range(n_buses):
        V_map_df = pd.DataFrame(MM_map[:][i][:])
        V_map_df.to_excel(writer, sheet_name=str(i))
    writer.save()


def pgd(fname, n_gg=20, n_mm=20, n_kk=20, n_scale=1001):
    """

    :param fname: data file name
    :param n_gg: outer iterations
    :param n_mm: intermediate iterations
    :param n_kk: inner iterations
    :param n_scale: number of discretized points, arbitrary
    :return:
    """

    n_buses, Qmax, Qmin, Y, V_mod, P_pq, Q_pq, P_pv, I0_pq, n_pv, n_pq = read_grid_data(fname)

    SSk, SSp, SSq = init_apparent_powers_decomposition(n_buses, n_scale, P_pq, Q_pq, Qmin, Qmax)
    VVk, VVp, VVq = init_voltages_decomposition(n_mm, n_buses, n_scale)
    IIk, IIp, IIq = init_currents_decomposition(n_gg, n_mm, n_buses, n_scale)

    n_max = n_gg * n_mm * n_kk
    iter_count = 1
    idx_i = 0
    idx_v = 1
    for gg in range(n_gg):  # outer loop: iterate on γ to solve the power flow as such

        for mm in range(n_mm):  # intermediate loop: iterate on i to find the superposition of terms of the I tensor.
            # define the new C
            CCk, CCp, CCq, Nc, Nv, n = fun_C(SSk, SSp, SSq,
                                             VVk, VVp, VVq,
                                             IIk, IIp, IIq,
                                             idx_i, idx_v,
                                             n_buses, n_scale)

            # initialize the residues we have to find
            IIk1 = (np.random.rand(n_buses) - np.random.rand(n_buses)) * 1  # could also try to set IIk1 = VVk1
            IIp1 = (np.random.rand(n_buses) - np.random.rand(n_buses)) * 1
            IIq1 = (np.random.rand(n_scale) - np.random.rand(n_scale)) * 1

            for kk in range(n_kk):  # inner loop: iterate on Γ to find the residues.

                # compute IIk1 (residues on Ik)
                RHSk = np.zeros(n_buses, dtype=complex)
                for ii in range(Nc):
                    prodRK = np.dot(IIp1, CCp[ii]) * np.dot(IIq1, CCq[ii])
                    RHSk += prodRK * CCk[ii]

                LHSk = np.zeros(n_buses, dtype=complex)
                for ii in range(Nv):
                    prodLK = np.dot(IIp1, VVp[ii] * IIp1) * np.dot(IIq1, VVq[ii] * IIq1)
                    LHSk += prodLK * VVk[ii]

                IIk1 = RHSk / LHSk

                # compute IIp1 (residues on Ip)
                RHSp = np.zeros(n_buses, dtype=complex)
                for ii in range(Nc):
                    prodRP = np.dot(IIk1, CCk[ii]) * np.dot(IIq1, CCq[ii])
                    RHSp += prodRP * CCp[ii]

                LHSp = np.zeros(n_buses, dtype=complex)
                for ii in range(Nv):
                    prodLP = np.dot(IIk1, VVk[ii] * IIk1) * np.dot(IIq1, VVq[ii] * IIq1)
                    LHSp += prodLP * VVp[ii]

                IIp1 = RHSp / LHSp

                # compute IIq1 (residues on Iq)
                RHSq = np.zeros(n_scale, dtype=complex)
                for ii in range(Nc):
                    prodRQ = np.dot(IIk1, CCk[ii]) * np.dot(IIp1, CCp[ii])
                    RHSq += prodRQ * CCq[ii]

                LHSq = np.zeros(n_scale, dtype=complex)
                for ii in range(Nv):
                    prodLQ = np.dot(IIk1, VVk[ii] * IIk1) * np.dot(IIp1, VVp[ii] * IIp1)
                    LHSq += prodLQ * VVq[ii]

                IIq1 = RHSq / LHSq

                progress_bar(iter_count, n_max, 50)  # display the inner operations
                iter_count += 1

            IIk[idx_i, :] = IIk1
            IIp[idx_i, :] = IIp1
            IIq[idx_i, :] = IIq1
            idx_i += 1

        for ii in range(n_mm):
            VVk[ii, :] = np.conj(sp_linalg.spsolve(Y, IIk[ii]))
            VVp[ii, :] = IIp[ii]
            VVq[ii, :] = IIq[ii]

        # try to add I0 this way:
        VVk[n_mm, :] = np.conj(sp_linalg.spsolve(Y, I0_pq))
        VVp[n_mm, :] = np.ones(n_buses)
        VVq[n_mm, :] = np.ones(n_scale)
        idx_v = n_mm + 1

    # VVk: size (n_mm + 1, nbus)
    # VVp: size (n_mm + 1, nbus)
    # VVq: size (n_mm + 1, n_scale)
    v_map = build_map(VVk, VVp, VVq)

    # SSk: size (2, nbus)
    # SSp: size (2, nbus)
    # SSq: size (2, n_scale)
    s_map = build_map(SSk, SSp, SSq)

    # IIk: size (n_gg * n_mm, nbus)
    # IIp: size (n_gg * n_mm, nbus)
    # IIq: size (n_gg * n_mm, n_scale)
    i_map = build_map(IIk, IIp, IIq)

    # the size of the maps is nbus, nbus, n_scale
    return v_map, s_map, i_map


if __name__ == '__main__':
    np.random.seed(42)
    # v_map_, s_map_, i_map_ = pgd('data_10PQ.xlsx', n_gg=5, n_mm=8, n_kk=10, n_scale=100)
    v_map_, s_map_, i_map_ = pgd('data_10PQ.xlsx', n_gg=20, n_mm=20, n_kk=20, n_scale=1001)
