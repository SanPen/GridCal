# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE_MATPOWER file.

# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Copyright (c) 2016-2017 by University of Kassel and Fraunhofer Institute for Wind Energy and
# Energy System Technology (IWES), Kassel. All rights reserved. Use of this source code is governed
# by a BSD-style license that can be found in the LICENSE file.

# The file has been modified from Pypower.
# The function mu() has been added to the solver in order to provide an optimal iteration control
#
# Copyright (c) 2018 Santiago Peñate Vera
#
# This file retains the BSD-Style license


from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray, zeros_like, zeros, complex128, \
empty, float64, int32, arange
from scipy.sparse import csr_matrix as sparse, hstack, vstack
from scipy.sparse.linalg import spsolve, splu
import numpy as np
import numdifftools as nd
import pandas as pd
import numba as nb
import time
from warnings import warn
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve
from matplotlib import pyplot as plt
import scipy
scipy.ALLOW_THREADS = True

np.set_printoptions(precision=8, suppress=True, linewidth=320)


def determine_branch_indices(circuit):
    """
    VSC Control modes:

    in the paper's scheme:
    from -> DC
    to   -> AC

    |   Mode    |   const.1 |   const.2 |   type    |
    -------------------------------------------------
    |   1       |   theta   |   Vac     |   I       |
    |   2       |   Pf      |   Qac     |   I       |
    |   3       |   Pf      |   Vac     |   I       |
    -------------------------------------------------
    |   4       |   Vdc     |   Qac     |   II      |
    |   5       |   Vdc     |   Vac     |   II      |
    -------------------------------------------------
    |   6       | Vdc droop |   Qac     |   III     |
    |   7       | Vdc droop |   Vac     |   III     |
    -------------------------------------------------

    Indices where each control goes:

     Device      |  Ish	Iqz	Ivf	Ivt	Iqt
    ------------------------------------
    VSC 1	     |  0	1	0	1	0   |   AC voltage control (voltage “to”)
    VSC 2	     |  1	1	0	0	1   |   Active and reactive power control
    VSC 3	     |  1	1	0	1	0   |   Active power and AC voltage control
    VSC 4	     |  0	0	1	0	1   |   Dc voltage and Reactive power flow control
    VSC 5	     |  0	0	1	1	0   |   Ac and Dc voltage control
    ------------------------------------
    Transformer 0|	0	0	0	0	0   |   Fixed transformer
    Transformer 1|	1	0	0	0	0   |   Phase shifter → controls power
    Transformer 2|	0	0	1	0	0   |   Control the voltage at the “from” side
    Transformer 3|	0	0	0	1	0   |   Control the voltage at the “to” side
    Transformer 4|	1	0	1	0	0   |   Control the power flow and the voltage at the “from” side
    Transformer 5|	1	0	0	1	0   |   Control the power flow and the voltage at the “to” side
    ------------------------------------


    """

    # indices in the global branch scheme
    idx_sh = list()
    idx_qz = list()
    idx_vf = list()
    idx_vt = list()
    idx_qt = list()

    # indices in the local vsc scheme
    idx_vsc_qt0 = list()
    idx_vsc_sh0 = list()

    i_offset = circuit.nline  # offset to the first vsc device in the branches list
    for i, tpe in enumerate(circuit.tr_control_mode):

        k = i + i_offset  # real index
        f = circuit.F[k]
        t = circuit.T[k]

        if tpe == 1:
            idx_sh.append(k)

        elif tpe == 2:
            idx_vf.append(f)

        elif tpe == 3:
            idx_vt.append(t)

        elif tpe == 4:
            idx_sh.append(k)
            idx_vf.append(f)

        elif tpe == 5:
            idx_sh.append(k)
            idx_vt.append(t)

    i_offset = circuit.nline + circuit.ntr  # offset to the first vsc device in the branches list
    for i, tpe in enumerate(circuit.vsc_control_mode):

        k = i + i_offset
        f = circuit.F[k]
        t = circuit.T[k]

        if tpe == 1:
            idx_qz.append(k)
            idx_vt.append(t)

        elif tpe == 2:
            idx_qz.append(k)
            idx_sh.append(k)
            idx_qt.append(k)
            idx_vsc_qt0.append(i)
            idx_vsc_sh0.append(i)

        elif tpe == 3:
            idx_qz.append(k)
            idx_sh.append(k)
            idx_vt.append(t)
            idx_vsc_sh0.append(i)

        elif tpe == 4:
            idx_vf.append(f)
            idx_qt.append(k)
            idx_vsc_qt0.append(i)

        elif tpe == 5:
            idx_vf.append(f)
            idx_vt.append(t)

        else:
            raise Exception('Unknown VSC type')

    return idx_sh, idx_qz, idx_vf, idx_vt, idx_qt, idx_vsc_qt0, idx_vsc_sh0


def compile_y(circuit, tr_tap_mod, tr_tap_ang, vsc_m, vsc_theta, vsc_Beq, vsc_If):
    """
    nbr = nline + ntr + nvsc + ndcline
    :param circuit:
    :param tr_tap_mod:
    :param tr_tap_ang:
    :param vsc_m:
    :param vsc_theta:
    :param vsc_G0:
    :param vsc_Beq:
    :return:
    """

    # form the connectivity matrices with the states applied -------------------------------------------------------
    br_states_diag = sp.diags(circuit.branch_active)
    Cf = br_states_diag * circuit.C_branch_bus_f
    Ct = br_states_diag * circuit.C_branch_bus_t

    # Declare the empty primitives ---------------------------------------------------------------------------------

    # The composition order is and will be: Pi model, HVDC, VSC
    Ytt = np.empty(circuit.nbr, dtype=complex)
    Yff = np.empty(circuit.nbr, dtype=complex)
    Yft = np.empty(circuit.nbr, dtype=complex)
    Ytf = np.empty(circuit.nbr, dtype=complex)

    # line ---------------------------------------------------------------------------------------------------------
    a = 0
    b = circuit.nline

    # use the specified of the temperature-corrected resistance
    Ys_line = 1.0 / (circuit.line_R + 1.0j * circuit.line_X)
    Ysh_line = 1.0j * circuit.line_B
    Ys_line2 = Ys_line + Ysh_line / 2.0

    # branch primitives in vector form for Ybus
    Ytt[a:b] = Ys_line2
    Yff[a:b] = Ys_line2
    Yft[a:b] = - Ys_line
    Ytf[a:b] = - Ys_line

    # transformer models -------------------------------------------------------------------------------------------
    a = circuit.nline
    b = a + circuit.ntr

    Ys_tr = 1.0 / (circuit.tr_R + 1.0j * circuit.tr_X)
    Ysh_tr = 1.0j * circuit.tr_B
    Ys_tr2 = Ys_tr + Ysh_tr / 2.0
    tap = tr_tap_mod * np.exp(1.0j * tr_tap_ang)

    # branch primitives in vector form for Ybus
    Ytt[a:b] = Ys_tr2 / (circuit.tr_tap_t * circuit.tr_tap_t)
    Yff[a:b] = Ys_tr2 / (circuit.tr_tap_f * circuit.tr_tap_f * tap * np.conj(tap))
    Yft[a:b] = - Ys_tr / (circuit.tr_tap_f * circuit.tr_tap_t * np.conj(tap))
    Ytf[a:b] = - Ys_tr / (circuit.tr_tap_t * circuit.tr_tap_f * tap)

    # VSC MODEL ----------------------------------------------------------------------------------------------------
    # in GridCal the VSC model is "wired" from AC to DC always
    a = circuit.nline + circuit.ntr
    b = a + circuit.nvsc

    Y_vsc = 1.0 / (circuit.vsc_R1 + 1.0j * circuit.vsc_X1)  # Y1
    vsc_Gsw = circuit.vsc_G0 * np.power(vsc_If / circuit.vsc_Inom, 2.0)
    vsc_m2 = 0.8660254037844386 * vsc_m  # sqrt(3)/2 * m

    Yff[a:b] = Y_vsc
    Yft[a:b] = -Y_vsc / (vsc_m2 * np.exp(1.0j * vsc_theta))
    Ytf[a:b] = -Y_vsc / (vsc_m2 * np.exp(-1.0j * vsc_theta))
    Ytt[a:b] = vsc_Gsw + (Y_vsc + 1.0j * vsc_Beq) / (vsc_m2 * vsc_m2)

    # dc-line ------------------------------------------------------------------------------------------------------
    a = circuit.nline + circuit.ntr + circuit.nvsc
    b = a + circuit.ndcline

    # use the specified of the temperature-corrected resistance
    Ys_dc_line = 1.0 / circuit.dc_line_R

    # branch primitives in vector form for Ybus
    Yff[a:b] = Ys_dc_line
    Yft[a:b] = - Ys_dc_line
    Ytf[a:b] = - Ys_dc_line
    Ytt[a:b] = Ys_dc_line

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = circuit.C_bus_shunt * (circuit.shunt_admittance * circuit.shunt_active / circuit.Sbase)

    # form the admittance matrices ---------------------------------------------------------------------------------

    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt) + sp.diags(Yshunt_from_devices)

    return Ybus, Yf, Yt



def compile_y2(circuit, m, theta, Beq, vsc_If):
    """
    nbr = nline + ntr + nvsc + ndcline
    :param circuit:
    :param tr_tap_mod:
    :param tr_tap_ang:
    :param vsc_m:
    :param vsc_theta:
    :param vsc_G0:
    :param vsc_Beq:
    :return:
    """

    # form the connectivity matrices with the states applied -------------------------------------------------------
    br_states_diag = sp.diags(circuit.branch_active)
    Cf = br_states_diag * circuit.C_branch_bus_f
    Ct = br_states_diag * circuit.C_branch_bus_t

    # Declare the empty primitives ---------------------------------------------------------------------------------
    # The composition order is and will be: Pi model, HVDC, VSC
    R = np.empty(circuit.nbr)
    X = np.empty(circuit.nbr)
    G = np.empty(circuit.nbr)
    B = np.empty(circuit.nbr)
    Gsw = np.empty(circuit.nbr)

    # line ---------------------------------------------------------------------------------------------------------
    a = 0
    b = circuit.nline

    R[a:b] = circuit.line_R
    X[a:b] = circuit.line_X
    B[a:b] = circuit.line_B

    # transformer models -------------------------------------------------------------------------------------------
    a = circuit.nline
    b = a + circuit.ntr

    R[a:b] = circuit.tr_R
    X[a:b] = circuit.tr_X
    G[a:b] = circuit.tr_G
    B[a:b] = circuit.tr_B

    # VSC MODEL ----------------------------------------------------------------------------------------------------
    # in GridCal the VSC model is "wired" from AC to DC always
    a = circuit.nline + circuit.ntr
    b = a + circuit.nvsc

    R[a:b] = circuit.vsc_R1
    X[a:b] = circuit.vsc_X1
    Gsw[a:b] = circuit.vsc_G0 * np.power(vsc_If / circuit.vsc_Inom, 2.0)

    # dc-line ------------------------------------------------------------------------------------------------------
    a = circuit.nline + circuit.ntr + circuit.nvsc
    b = a + circuit.ndcline

    R[a:b] = circuit.dc_line_R

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = circuit.C_bus_shunt * (circuit.shunt_admittance * circuit.shunt_active / circuit.Sbase)

    # form the admittance matrices ---------------------------------------------------------------------------------

    ys = 1.0 / (R + 1.0j * X)  # Y1
    # vsc_m2 = 0.8660254037844386 * vsc_m  # sqrt(3)/2 * m

    # compose the primitives
    Yff = ys
    Yft = -ys / (m * np.exp(1.0j * theta))
    Ytf = -ys / (m * np.exp(-1.0j * theta))
    Ytt = Gsw + (ys + 1.0j * Beq) / (m * m)

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt) + sp.diags(Yshunt_from_devices)

    return Ybus, Yf, Yt


def compute_g(V, S0, m, theta, Beq, vsc_Inom,
              pqpv, pq, idx_sh, idx_sh0, idx_qz, idx_vf, idx_vt, idx_qt, idx_qt0):
    """

    :param V:
    :param S0:
    :param tr_tap_mod:
    :param tr_tap_ang:
    :param vsc_m:
    :param vsc_theta:
    :param vsc_Beq:
    :param vsc_Inom:
    :param pqpv:
    :param pq:
    :param idx_sh:
    :param idx_sh0:
    :param idx_qz:
    :param idx_vf:
    :param idx_vt:
    :param idx_qt:
    :param idx_qt0:
    :return:
    """

    Ybus, Yf, Yt = compile_y2(circuit=nc,
                              m=m,
                              theta=theta,
                              Beq=Beq,
                              vsc_If=vsc_Inom)

    print(Ybus.toarray())

    S_calc = V * np.conj(Ybus * V)

    # equation (6)
    gs = S_calc - S0

    If = Yf * V
    It = Yt * V
    Vf = nc.C_branch_bus_f * V
    Vt = nc.C_branch_bus_t * V
    Sf = Vf * np.conj(If)  # eq. (8)
    St = Vt * np.conj(It)  # eq. (9)

    gp = gs.real[pqpv]  # eq. (12)
    gq = gs.imag[pq]  # eq. (13)

    # controls that the specified power flow is met
    # Applicable to:
    # - VSC devices where the power flow is set, this is types 2 and 3
    # - Transformer devices where the power flow is set (is it?, apparently it only depends on the value of theta)
    gsh = Sf.real[idx_sh] - nc.vsc_Pset[idx_sh0]  # eq. (14)

    # controls that 'Beq' absorbs the reactive power.
    # Applicable to:
    # - All the VSC converters (is it?)
    gqz = Sf.imag[idx_qz]  # eq. (15)

    # Controls that 'ma' modulates to control the "voltage from" module.
    # Applicable to:
    # - Transformers that control the "from" voltage side
    # - VSC that control the "from" voltage side, this is types 4 and 5
    gvf = gs.imag[idx_vf]  # eq. (16)

    # Controls that 'ma' modulates to control the "voltage to" module.
    # Applicable to:
    # - Transformers that control the "to" voltage side
    # - VSC that control the "from" voltage side, this is types 1, 3, 5 and 7
    gvt = gs.imag[idx_vt]  # eq. (17)

    # controls that the specified reactive power flow is met, this is Qf=0
    # Applicable to:
    # - All VSC converters (is it?)  this is types 2, 4, 6
    gqt = St.imag[idx_qt] - nc.vsc_Qset[idx_qt0]  # eq. (18)

    # return the complete mismatch function
    return np.r_[gp, gq, gsh, gqz, gvf, gvt, gqt]


def dSbus_dV(Ybus, V, I):
    """
    Computes partial derivatives of power injection w.r.t. voltage.
    :param Ybus: Admittance matrix
    :param V: Bus voltages array
    :param I: Bus current injections array
    :return:
    """
    '''
    Computes partial derivatives of power injection w.r.t. voltage.

    Returns two matrices containing partial derivatives of the complex bus
    power injections w.r.t voltage magnitude and voltage angle respectively
    (for all buses). If C{Ybus} is a sparse matrix, the return values will be
    also. The following explains the expressions used to form the matrices::

        Ibus = Ybus * V - I

        S = diag(V) * conj(Ibus) = diag(conj(Ibus)) * V

    Partials of V & Ibus w.r.t. voltage magnitudes::
        dV/dVm = diag(V / abs(V))
        dI/dVm = Ybus * dV/dVm = Ybus * diag(V / abs(V))

    Partials of V & Ibus w.r.t. voltage angles::
        dV/dVa = j * diag(V)
        dI/dVa = Ybus * dV/dVa = Ybus * j * diag(V)

    Partials of S w.r.t. voltage magnitudes::
        dS/dVm = diag(V) * conj(dI/dVm) + diag(conj(Ibus)) * dV/dVm
               = diag(V) * conj(Ybus * diag(V / abs(V)))
                                        + conj(diag(Ibus)) * diag(V / abs(V))

    Partials of S w.r.t. voltage angles::
        dS/dVa = diag(V) * conj(dI/dVa) + diag(conj(Ibus)) * dV/dVa
               = diag(V) * conj(Ybus * j * diag(V))
                                        + conj(diag(Ibus)) * j * diag(V)
               = -j * diag(V) * conj(Ybus * diag(V))
                                        + conj(diag(Ibus)) * j * diag(V)
               = j * diag(V) * conj(diag(Ibus) - Ybus * diag(V))

    For more details on the derivations behind the derivative code used
    in PYPOWER information, see:

    [TN2]  R. D. Zimmerman, "AC Power Flows, Generalized OPF Costs and
    their Derivatives using Complex Matrix Notation", MATPOWER
    Technical Note 2, February 2010.
    U{http://www.pserc.cornell.edu/matpower/TN2-OPF-Derivatives.pdf}

    @author: Ray Zimmerman (PSERC Cornell)
    '''

    ib = range(len(V))

    Ibus = Ybus * V - I

    diagV = sparse((V, (ib, ib)))
    diagIbus = sparse((Ibus, (ib, ib)))
    diagVnorm = sparse((V / np.abs(V), (ib, ib)))

    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1.0j * diagV * conj(diagIbus - Ybus * diagV)

    return dS_dVm, dS_dVa


def Jacobian(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the system Jacobian matrix
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix
    """
    dS_dVm, dS_dVa = dSbus_dV(Ybus, V, Ibus)  # compute the derivatives

    J11 = dS_dVa[array([pvpq]).T, pvpq].real
    J12 = dS_dVm[array([pvpq]).T, pq].real
    J21 = dS_dVa[array([pq]).T, pvpq].imag
    J22 = dS_dVm[array([pq]).T, pq].imag

    J = vstack([hstack([J11, J12]),
                hstack([J21, J22])], format="csr")

    return J


def NR_LSDC(Ybus, Sbus, V0, Ibus, pv, pq, dc_F, dc_T, tol, max_it=15, acceleration_parameter=0.05, error_registry=None):
    """
    Solves the power flow using a full Newton's method with backtrack correction.
    @Author: Santiago Peñate Vera
    :param Ybus: Admittance matrix
    :param Sbus: Array of nodal power injections
    :param V0: Array of nodal voltages (initial solution)
    :param Ibus: Array of nodal current injections
    :param pv: Array with the indices of the PV buses
    :param pq: Array with the indices of the PQ buses
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param acceleration_parameter: parameter used to correct the "bad" iterations, should be be between 1e-3 ~ 0.5
    :param error_registry: list to store the error for plotting
    :return: Voltage solution, converged?, error, calculated power injections
    """
    start = time.time()

    # initialize
    back_track_counter = 0
    back_track_iterations = 0
    converged = 0
    iter_ = 0
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

    # set up indexing for updating V
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)
    mcd = len(dc_F)
    dc = np.array(list(set(dc_F).union(set(dc_T))))
    dc.sort()

    # j1:j2 - V angle of pv and pq buses
    j1 = 0
    j2 = npv + npq
    # j2:j3 - V mag of pq buses
    j3 = j2 + npq

    if (npq + npv) > 0:

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
        pvpq_lookup[pvpq] = np.arange(len(pvpq))
        # createJ = get_fastest_jacobian_function(pvpq, pq)

        # evaluate F(x0)
        Scalc = V * np.conj(Ybus * V - Ibus)
        dS = Scalc - Sbus  # compute the mismatch
        f = np.r_[dS[pvpq].real, dS[pq].imag]

        # check tolerance
        norm_f = 0.5 * f.dot(f)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f < tol:
            converged = 1

        # to be able to compare
        Ybus.sort_indices()

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            J = Jacobian(Ybus, V, Ibus, pq, pvpq)
            # J = _create_J_with_numba(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)

            # compute update step
            dx = spsolve(J, f)

            # reassign the solution vector
            dVa[pvpq] = dx[j1:j2]
            dVm[pq] = dx[j2:j3]
            # dVa[dc] = 0.0

            # update voltage the Newton way (mu=1)
            mu_ = 1.0
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * np.exp(1.0j * Va)

            # compute the mismatch function f(x_new)
            Scalc = Vnew * np.conj(Ybus * Vnew - Ibus)
            dS = Scalc - Sbus  # complex power mismatch
            f_new = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function
            norm_f_new = 0.5 * f_new.dot(f_new)

            if error_registry is not None:
                error_registry.append(norm_f_new)

            cond = norm_f_new > norm_f  # condition to back track (no improvement at all)

            if not cond:
                back_track_counter += 1

            l_iter = 0
            while not cond and l_iter < 10 and mu_ > 0.01:
                # line search back
                # update voltage with a closer value to the last value in the Jacobian direction
                mu_ *= acceleration_parameter
                Vm -= mu_ * dVm
                Va -= mu_ * dVa
                Vnew = Vm * np.exp(1.0j * Va)

                # compute the mismatch function f(x_new)
                Scalc = Vnew * np.conj(Ybus * Vnew - Ibus)
                dS = Scalc - Sbus  # complex power mismatch
                f_new = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function

                norm_f_new = 0.5 * f_new.dot(f_new)

                cond = norm_f_new > norm_f

                if error_registry is not None:
                    error_registry.append(norm_f_new)

                l_iter += 1
                back_track_iterations += 1

            # update calculation variables
            V = Vnew
            f = f_new

            # check for convergence
            if l_iter == 0:
                # no correction loop executed, hence compute the error fresh
                norm_f = 0.5 * f_new.dot(f_new)
            else:
                # pick the latest computer error in the correction loop
                norm_f = norm_f_new

            if error_registry is not None:
                error_registry.append(norm_f)

            if norm_f < tol:
                converged = 1

    else:
        norm_f = 0
        converged = True
        Scalc = Sbus

    end = time.time()
    elapsed = end - start

    return V, converged, norm_f, Scalc, iter_, elapsed


########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine import *
    from matplotlib import pyplot as plt
    import pandas as pd
    import os
    import time
    np.set_printoptions(linewidth=10000)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    grid = FileOpen('').open()

    ####################################################################################################################
    # Compile
    ####################################################################################################################
    nc = compile_snapshot_circuit(grid)

    # compute the indices of the converter/transformer variables from their control strategies
    idx_sh, idx_qz, idx_vf, idx_vt, idx_qt, idx_qt0, idx_sh0 = determine_branch_indices(circuit=nc)

    # initialize the variables
    V = nc.Vbus
    S0 = nc.Sbus
    tr_tap_mod = nc.tr_tap_mod
    tr_tap_ang = nc.tr_tap_ang
    vsc_m = nc.vsc_m
    vsc_theta = nc.vsc_theta
    vsc_Beq = nc.vsc_Beq
    vsc_Inom = nc.vsc_Inom
    pqpv = nc.pqpv
    pq = nc.pq
    pv = nc.pv
    npq = len(pq)
    npv = len(pv)
    npqpv = npq + npv

    # compute the mismatch function
    m = np.ones(nc.nbr)
    theta = np.zeros(nc.nbr)
    Beq = np.zeros(nc.nbr)

    # Transformer
    a = nc.nline
    b = a + nc.ntr
    m[a:b] = nc.tr_tap_mod
    theta[a:b] = nc.tr_tap_ang

    # VSC
    a = nc.nline + nc.ntr
    b = a + nc.nvsc
    m[a:b] = nc.vsc_m
    theta[a:b] = nc.vsc_theta
    Beq[a:b] = nc.vsc_Beq

    va = np.angle(V)
    vm = np.abs(V)
    x0 = np.r_[va[pqpv], vm[pq], theta[idx_sh], Beq[idx_qz], m[idx_vf], m[idx_vt], Beq[idx_qt]]

    g = compute_g(V=V,
                  S0=S0,
                  m=m,
                  theta=theta,
                  Beq=Beq,
                  vsc_Inom=vsc_Inom,
                  pqpv=pqpv,
                  pq=pq,
                  idx_sh=idx_sh,
                  idx_sh0=idx_sh0,
                  idx_qz=idx_qz,
                  idx_vf=idx_vf,
                  idx_vt=idx_vt,
                  idx_qt=idx_qt,
                  idx_qt0=idx_qt0)


    def fun(x):

        va = np.angle(V)
        vm = np.abs(V)
        m = np.ones(nc.nbr)
        theta = np.zeros(nc.nbr)
        Beq = np.zeros(nc.nbr)

        a = 0
        b = npqpv
        va[pqpv] = x[a:b]

        a = b
        b += npq
        vm[pq] = x[a:b]

        a = b
        b += len(idx_sh)
        theta[idx_sh] = x[a:b]

        a = b
        b += len(idx_qz)
        Beq[idx_qz] = x[a:b]  # Beq for Qflow = 0

        a = b
        b += len(idx_vf)
        m[idx_vf] = x[a:b]  # m controlling Vf

        a = b
        b += len(idx_vt)
        m[idx_vt] = x[a:b]  # m controlling Vt

        a = b
        b += len(idx_qt)
        Beq[idx_qt] = x[a:b]  # Beq for Qflow = Qset

        return compute_g(V=vm * np.exp(1.0j * va),
                         S0=S0,
                         m=m,
                         theta=theta,
                         Beq=Beq,
                         vsc_Inom=vsc_Inom,
                         pqpv=pqpv,
                         pq=pq,
                         idx_sh=idx_sh,
                         idx_sh0=idx_sh0,
                         idx_qz=idx_qz,
                         idx_vf=idx_vf,
                         idx_vt=idx_vt,
                         idx_qt=idx_qt,
                         idx_qt0=idx_qt0)


    def Jacobian(f, x, dx=1e-8):
        n = len(x)
        func = f(x)
        jac = np.zeros((n, n))
        for j in range(n):  # through columns to allow for vector addition
            Dxj = (abs(x[j]) * dx if x[j] != 0 else dx)
            x_plus = [(xi if k != j else xi + Dxj) for k, xi in enumerate(x)]
            jac[:, j] = (f(x_plus) - func) / Dxj
        return jac


    J = Jacobian(fun, x0)  # see: https://pypi.org/project/numdifftools/

    print(J)

    dx = np.linalg.solve(J, g)