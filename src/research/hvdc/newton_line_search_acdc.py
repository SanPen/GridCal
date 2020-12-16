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
from GridCal.Engine import *
from matplotlib import pyplot as plt
import pandas as pd
import os
import time
import scipy
scipy.ALLOW_THREADS = True

np.set_printoptions(precision=4, linewidth=100000)


def determine_branch_indices(circuit: SnapshotData):
    """
    This function fills in the lists of indices to control different magnitudes

    :param circuit: Instance of AcDcSnapshotCircuit
    :returns idx_sh, idx_qz, idx_vf, idx_vt, idx_qt

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
    mismatch  →  |  ∆Pf	Qf	Q@f Q@t	∆Qt
    variable  →  |  Ɵsh	Beq	m	m	Beq
    Indices   →  |  Ish	Iqz	Ivf	Ivt	Iqt
    ------------------------------------
    VSC 1	     |  -	1	-	1	-   |   AC voltage control (voltage “to”)
    VSC 2	     |  1	1	-	-	1   |   Active and reactive power control
    VSC 3	     |  1	1	-	1	-   |   Active power and AC voltage control
    VSC 4	     |  -	-	1	-	1   |   Dc voltage and Reactive power flow control
    VSC 5	     |  -	-	-	1	1   |   Ac and Dc voltage control
    ------------------------------------
    Transformer 0|	-	-	-	-	-   |   Fixed transformer
    Transformer 1|	1	-	-	-	-   |   Phase shifter → controls power
    Transformer 2|	-	-	1	-	-   |   Control the voltage at the “from” side
    Transformer 3|	-	-	-	1	-   |   Control the voltage at the “to” side
    Transformer 4|	1	-	1	-	-   |   Control the power flow and the voltage at the “from” side
    Transformer 5|	1	-	-	1	-   |   Control the power flow and the voltage at the “to” side
    ------------------------------------

    """
        
    # indices in the global branch scheme
    iPfsh = list()  # indices of the branches controlling Pf flow
    iQfma = list()
    iBeqz = list()  # indices of the branches when forcing the Qf flow to zero (aka "the zero condition")
    iBeqv = list()  # indices of the branches when controlling Vf
    iVtma = list()  # indices of the branches when controlling Vt
    iQtma = list()  # indices of the branches controlling the Qt flow
    iPfdp = list()
    iVscL = list()  # indices of the converters

    for k, tpe in enumerate(circuit.branch_data.control_mode):

        if tpe == TransformerControlType.fixed:
            pass

        elif tpe == TransformerControlType.power:
            iPfsh.append(k)

        elif tpe == TransformerControlType.v_to:
            iVtma.append(k)

        elif tpe == TransformerControlType.power_v_to:
            iPfsh.append(k)
            iVtma.append(k)

        # VSC ----------------------------------------------------------------------------------------------------------
        elif tpe == ConverterControlType.type_1_free:  # 1a:Free
            iBeqz.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_1_pf:  # 1b:Pflow
            iPfsh.append(k)
            iBeqz.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_1_qf:  # 1c:Qflow
            iBeqz.append(k)
            iQtma.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_1_vac:  # 1d:Vac
            iBeqz.append(k)
            iVtma.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_2_vdc:  # 2a:Vdc
            iPfsh.append(k)
            iBeqv.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_2_vdc_pf:  # 2b:Vdc+Pflow
            iPfsh.append(k)
            iBeqv.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_3:  # 3a:Droop
            iPfsh.append(k)
            iBeqz.append(k)
            iPfdp.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_4:  # 4a:Droop-slack
            iPfdp.append(k)

            iVscL.append(k)

        elif tpe == 0:
            pass  # required for the no-control case

        else:
            raise Exception('Unknown control type:' + str(tpe))

    return iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, iVscL


def compile_y(circuit: SnapshotData, m, theta, Beq, If):
    """
    Compile the admittance matrices using the variable elements
    :param circuit: AcDcSnapshotCircuit instance
    :param m: array of tap modules (for all branches, regardless of their type)
    :param theta: array of tap angles (for all branches, regardless of their type)
    :param Beq: Array of equivalent susceptance
    :param If: Array of currents "from" in all the branches
    :return: Ybus, Yf, Yt
    """

    # form the connectivity matrices with the states applied -------------------------------------------------------
    br_states_diag = sp.diags(circuit.branch_data.branch_active)
    Cf = br_states_diag * circuit.branch_data.C_branch_bus_f
    Ct = br_states_diag * circuit.branch_data.C_branch_bus_t

    # compute G-switch
    Gsw = circuit.branch_data.G0 * np.power(If / circuit.branch_data.Inom, 2.0)

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = circuit.shunt_data.C_bus_shunt * (circuit.shunt_data.shunt_admittance * circuit.shunt_data.shunt_active / circuit.Sbase)
    yshunt_f = Cf * Yshunt_from_devices
    yshunt_t = Ct * Yshunt_from_devices

    # form the admittance matrices ---------------------------------------------------------------------------------

    ys = 1.0 / (circuit.branch_data.R + 1.0j * circuit.branch_data.X)  # series impedance
    bc2 = 1j * circuit.branch_data.B / 2  # shunt conductance
    # mp = circuit.k * m  # k is already filled with the appropriate value for each type of branch
    mp = m
    tap = mp * np.exp(1.0j * theta)

    # compose the primitives
    Yff = Gsw + (ys + bc2 + 1.0j * Beq + yshunt_f) / (mp * mp)
    Yft = -ys / np.conj(tap)
    Ytf = -ys / tap
    Ytt = ys + bc2 + yshunt_t

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt)

    return Ybus, Yf, Yt, tap


def split_x(x, pq, pvpq, idx_pf, idx_qz, idx_mvf, idx_mvt, idx_qt):
    """

    :param x:
    :param pq:
    :param pvpq:
    :param idx_pf:
    :param idx_qz:
    :param idx_mvf:
    :param idx_mvt:
    :param idx_qt:
    :return:
    """
    a = 0
    b = len(pvpq)
    va = x[a:b]

    a = b
    b += len(pq)
    vm = x[a:b]

    a = b
    b += len(idx_pf)
    theta1 = x[a:b]

    a = b
    b += len(idx_qz)
    Beq1 = x[a:b]  # Beq for Qflow = 0

    a = b
    b += len(idx_mvf)
    m1 = x[a:b]  # m controlling Vf

    a = b
    b += len(idx_mvt)
    m2 = x[a:b]  # m controlling Vt

    a = b
    b += len(idx_qt)
    Beq2 = x[a:b]  # Beq for Qflow = Qset

    return va, vm, theta1, Beq1, m1, m2, Beq2


def gx_function(x, args):
    """

    :param x:
    :param args:
    :return:
    """

    '''
    args=(nc, pq, pvpq, idx_pf, idx_qz, idx_mvf, idx_mvt, idx_vf, idx_vt, idx_qt,
          Yf, Yt, S0, Pset, Qset, If,
          va, vm, m, theta, Beq),
    '''

    nc, pq, pvpq, idx_pf, idx_qz, idx_vf, idx_vt, idx_qt, Yf, Yt, S0, Pset, Qset, If, va_, vm_, m_, theta_, Beq_ = args

    va = va_.copy()
    vm = vm_.copy()
    m = m_.copy()
    theta = theta_.copy()
    Beq = Beq_.copy()

    # update the variables:                        x, pq, pvpq, idx_pf, idx_qz, idx_mvf, idx_mvt, idx_qt
    va1, vm1, theta1, Beq1, m1, m2, Beq2 = split_x(x, pq, pvpq, idx_pf, idx_qz, idx_vf, idx_vt, idx_qt)
    va[pvpq] = va1
    vm[pq] = vm1
    theta[idx_pf] = theta1
    Beq[idx_qz] = Beq1
    m[idx_vf] = m1
    m[idx_vt] = m2
    Beq[idx_qt] = Beq2

    # compose the voltage
    V = vm * np.exp(1.0j * va)

    # compute branch flows
    If = Yf * V
    It = Yt * V
    Vf = nc.C_branch_bus_f * V
    Vt = nc.C_branch_bus_t * V
    Sf = Vf * np.conj(If)  # eq. (8)
    St = Vt * np.conj(It)  # eq. (9)
    gf = Sf - S0[nc.F]  # power increment at the "from" sides
    gt = St - S0[nc.T]  # power increment at the "to" sides

    # compute admittances as a function of the branch variables
    Ybus, Yf, Yt = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=If)

    # compute the new mismatch (g)
    S_calc = V * np.conj(Ybus * V)  # compute Bus power injections
    gs = S_calc - S0  # equation (6)
    gp = gs.real[pvpq]  # eq. (12)
    gq = gs.imag[pq]  # eq. (13)
    gsh = Sf.real[idx_pf] - Pset[idx_pf]  # eq. (14) controls that the specified power flow is met
    gqz = Sf.imag[idx_qz]  # eq. (15) controls that 'Beq' absorbs the reactive power.
    gvf = gf.imag[idx_vf]  # eq. (16) Controls that 'ma' modulates to control the "voltage from" module.
    gvt = gt.imag[idx_vt]  # eq. (17) Controls that 'ma' modulates to control the "voltage to" module.
    gqt = St.imag[idx_qt] - Qset[idx_qt]  # eq. (18) controls that the specified reactive power flow is met

    g = np.r_[gp, gq, gsh, gqz, gvf, gvt, gqt]  # complete mismatch function

    return g


def numerical_jacobian(f, x, args, dx=1e-8):
    """
    Compute the numerical Jacobian of a function
    :param f: function to evaluate
    :param x: "point" at which to evaluate the jacobian
    :param args: Extra arguments to pass to the function
    :param dx: tolerance
    :return: Jacobian matrix
    """
    n = len(x)
    f0 = f(x, args)
    jac = np.zeros((n, n))
    for j in range(n):  # through columns to allow for vector addition
        Dxj = (np.abs(x[j]) * dx if x[j] != 0 else dx)
        x_plus = np.array([(xi if k != j else xi + Dxj) for k, xi in enumerate(x)])
        f1 = f(x_plus, args)
        col = (f1 - f0) / Dxj
        jac[:, j] = col
    return jac


def nr_acdc_old(nc: SnapshotData, tolerance=1e-6, max_iter=4):
    """

    :param nc:
    :param tolerance:
    :param max_iter:
    :return:
    """
    # compute the indices of the converter/transformer variables from their control strategies
    iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, iVscL = determine_branch_indices(circuit=nc)

    VfBeqbus = nc.F[iBeqv]
    Vtmabus = nc.T[iVtma]

    # initialize the variables
    V = nc.Vbus
    S0 = nc.Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmset = Vm.copy()
    m = nc.branch_data.m.copy()
    theta = nc.branch_data.theta.copy() * 0
    Beq = nc.branch_data.Beq.copy() * 0
    Pset = nc.branch_data.Pset / nc.Sbase
    Qset = nc.branch_data.Qset / nc.Sbase
    Kdp = nc.branch_data.Kdp
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[VfBeqbus, Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    nPfsh = len(iPfsh)  # FUBM- number of Pf controlled elements by theta_shift
    nQfma = len(iQfma)  # FUBM- number of Qf controlled elements by ma
    nQtma = len(iQtma)  # FUBM- number of Qt controlled elements by ma
    nVtma = len(iVtma)  # FUBM- number of Vt controlled elements by ma
    nBeqz = len(iBeqz)  # FUBM- number of Qf controlled elements by Beq
    nBeqv = len(iBeqv)  # FUBM- number of Vf controlled elements by Beq
    nVscL = len(iVscL)  # FUBM- Number of VSC with active PWM Losses Calculation
    nPfdp = len(iPfdp)  # FUBM- Number of VSC with Voltage Droop Control by theta_shift
    nVfBeqbus = len(VfBeqbus)  # FUBM- number of buses for Vf controlled by Beq
    nVtmabus = len(Vtmabus)  # FUBM- number of buses for Vt controlled by ma
    # --------------------------------------------------------------------------

    # variables dimensions in Jacobian
    # FUBM----------------------------------------------------------------------
    j1 = 1
    j2 = npv  # j1 :j2  - V angle of pv buses (bus)
    j3 = j2 + 1
    j4 = j2 + npq  # j3 :j4  - V angle of pq buses (bus)
    j5 = j4 + 1
    j6 = j4 + npq  # j5 :j6  - V mag   of pq buses (bus)
    j7 = j6 + 1
    j8 = j6 + nPfsh  # j7 :j8  - ShiftAngle of VSC and PST (branch)
    j9 = j8 + 1
    j10 = j8 + nQfma  # j9 :j10 - ma of Qf Controlled Transformers (branch)
    jA1 = j10 + 1
    jA2 = j10 + nBeqz  # j11:j12 - Beq of VSC for Zero Constraint (branch)
    jA3 = jA2 + 1
    jA4 = jA2 + nVfBeqbus  # j13:j14 - Beq of VSC for Vdc  Constraint (bus)
    jA5 = jA4 + 1
    jA6 = jA4 + nVtmabus  # j15:j16 - ma of VSC and Transformers for Vt Control (bus)
    jA7 = jA6 + 1
    jA8 = jA6 + nQtma  # j17:j18 - ma of VSC and Transformers for Qt Control (branch)
    jA9 = jA8 + 1
    jB0 = jA8 + nPfdp  # j19:j20 - ShiftAngle of VSC for Qt Control (branch)
    # -------------------------------------------------------------------------

    # compute initial admittances
    Ybus, Yf, Yt = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=nc.branch_data.Inom)

    # compute branch flows
    If = Yf * V
    It = Yt * V
    Vf = nc.branch_data.C_branch_bus_f * V
    Vt = nc.branch_data.C_branch_bus_t * V
    Sf = Vf * np.conj(If)  # eq. (8)
    St = Vt * np.conj(It)  # eq. (9)
    gf = Sf - S0[nc.F]
    gt = St - S0[nc.T]

    # compute admittances as a function of the branch variables
    Ybus, Yf, Yt = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=If)

    # compute the mismatch (g)
    S_calc = V * np.conj(Ybus * V)  # compute Bus power injections
    mis = S_calc - S0
    misPbus = mis.real[pvpq]
    misQbus = mis.imag[pq]
    misPfsh = Sf.real[iPfsh] - Pset[iPfsh]
    misQfma = Sf.imag[iQfma] - Qset[iQfma]
    misBeqz = Sf.imag[iBeqz]
    misBeqv = mis.imag[VfBeqbus]
    misVtma = mis.imag[Vtmabus]
    misQtma = St.imag[iQtma] - Qset[iQtma]
    misPfdp = -Sf.real[iPfdp] + Pset[iPfdp] + Kdp[iPfdp] * (Vm[nc.F[iPfdp]] - Vmset[nc.F[iPfdp]])

    g = np.r_[misPbus,  # FUBM- F1(x0) Power balance mismatch - Va
              misQbus,  # FUBM- F2(x0) Power balance mismatch - Vm
              misPfsh,  # FUBM- F3(x0) Pf control    mismatch - Theta_shift
              misQfma,  # FUBM- F4(x0) Qf control    mismatch - ma
              misBeqz,  # FUBM- F5(x0) Qf control    mismatch - Beq
              misBeqv,  # FUBM- F6(x0) Vf control    mismatch - Beq
              misVtma,  # FUBM- F7(x0) Vt control    mismatch - ma
              misQtma,  # FUBM- F8(x0) Qt control    mismatch - ma
              misPfdp]  # return the complete mismatch function

    # compose the initial x value
    x = np.r_[Va[pvpq], Vm[pq], theta[iPfsh], Beq[iQfma], m[idx_vf], m[idx_vt], Beq[idx_qt]]

    # compute the error
    ff = np.r_[mis[pvpq_orig].real, mis[pq].imag]  # concatenate to form the mismatch function
    norm_f = 0.5 * ff.dot(ff)
    iterations = 0

    # compose equation names
    eq_names = ['gp' + str(k) for k in pvpq] \
               + ['gq' + str(k) for k in pq] \
               + ['gsh' + str(k) for k in idx_pf] \
               + ['gqz' + str(k) for k in idx_qz] \
               + ['gvf' + str(k) for k in idx_vf] \
               + ['gvt' + str(k) for k in idx_vt] \
               + ['gqf' + str(k) for k in idx_qt]

    var_names = ['va' + str(k) for k in pvpq] \
                + ['vm' + str(k) for k in pq] \
                + ['Ɵsh' + str(k) for k in idx_pf] \
                + ['Beq' + str(k) for k in idx_qz] \
                + ['m' + str(k) for k in idx_vf] \
                + ['m' + str(k) for k in idx_vt] \
                + ['Beq' + str(k) for k in idx_qt]

    type_names = [None] * len(V)
    for i in pq:
        type_names[i] = 'PQ'
    for i in pv:
        type_names[i] = 'PV'
    for i in nc.vd:
        type_names[i] = 'VD'

    print(['Ish' + str(k) for k in idx_pf])
    print(['IQz' + str(k) for k in idx_qz])
    print(['Ivf' + str(k) for k in idx_vf])
    print(['Ivt' + str(k) for k in idx_vt])
    print(['IQt' + str(k) for k in idx_qt])

    while norm_f > tolerance and iterations < max_iter:
        print('-' * 200)

        # compute the numerical Jacobian
        J = numerical_jacobian(gx_function,
                               x,
                               args=(nc, pq, pvpq, idx_pf, idx_qz, idx_vf, idx_vt, idx_qt,
                                     Yf, Yt, S0, Pset, Qset, If,
                                     Va, Vm, m, theta, Beq),
                               dx=tolerance)

        print('J:')
        print(pd.DataFrame(data=J, columns=var_names, index=eq_names))
        print('x:')
        print(pd.DataFrame(data=x, index=var_names, columns=['']).transpose())

        print('g:')
        print(pd.DataFrame(data=g, index=var_names, columns=['']).transpose())

        # solve the increments
        dx = np.linalg.solve(J, g)

        print('dx:')
        print(pd.DataFrame(data=dx, index=var_names, columns=['']).transpose())

        # update the point
        x -= dx

        # update the variables
        va1, vm1, theta1, Beq1, m1, m2, Beq2 = split_x(x, pq, pvpq, idx_pf, idx_qz, idx_vf, idx_vt, idx_qt)
        Va[pvpq] = va1
        Vm[pq] = vm1
        theta[idx_pf] = theta1
        Beq[idx_qz] = Beq1
        m[idx_vf] = m1
        m[idx_vt] = m2
        Beq[idx_qt] = Beq2

        # compose the voltage
        V = Vm * np.exp(1.0j * Va)

        # compute branch flows
        If = Yf * V
        It = Yt * V
        Vf = nc.branch_data.C_branch_bus_f * V
        Vt = nc.branch_data.C_branch_bus_t * V
        Sf = Vf * np.conj(If)  # eq. (8)
        St = Vt * np.conj(It)  # eq. (9)
        gf = Sf - S0[nc.F]
        gt = St - S0[nc.T]

        # compute admittances as a function of the branch variables
        Ybus, Yf, Yt = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=If)

        # compute the new mismatch (g)
        S_calc = V * np.conj(Ybus * V)  # compute Bus power injections
        mis = S_calc - S0  # equation (6)
        misPbus = mis.real[pvpq]  # eq. (12)
        misQbus = mis.imag[pq]  # eq. (13)
        misPfsh = Sf.real[idx_pf] - Pset[idx_pf]  # eq. (14) controls that the specified power flow is met
        gqz = Sf.imag[idx_qz]  # eq. (15) controls that 'Beq' absorbs the reactive power.
        gvf = gf.imag[idx_vf]  # eq. (16) Controls that 'ma' modulates to control the "voltage from" module.
        gvt = gt.imag[idx_vt]  # eq. (17) Controls that 'ma' modulates to control the "voltage to" module.
        gqt = St.imag[idx_qt] - Qset[idx_qt]  # eq. (18) controls that the specified reactive power flow is met
        g = np.r_[misPbus, misQbus, misPfsh, gqz, gvf, gvt, gqt]  # complete mismatch function

        # compute the error
        ff = np.r_[mis[pvpq_orig].real, mis[pq].imag]  # concatenate to form the mismatch function
        norm_f = 0.5 * ff.dot(ff)
        print('error:\n', norm_f)

        iterations += 1

    print('END', '-' * 200)
    print('Bus values')
    print(pd.DataFrame(data=np.c_[type_names, S_calc.real, S_calc.imag, mis.real, mis.imag, vm, va],
                       columns=['Type', 'P', 'Q', '∆P', '∆Q', 'Vm', 'Va'],
                       index=nc.bus_names))
    print('\nBranch values')
    print(pd.DataFrame(data=np.c_[nc.F, nc.T, nc.branch_data.control_mode, nc.branch_data.Pset, nc.branch_data.Qset,
                                  nc.branch_data.vf_set, nc.branch_data.vt_set,
                                  vm[nc.F] - vm[nc.T], va[nc.F] - va[nc.T],
                                  Sf.real, Sf.imag, Sf.real, Sf.imag, m, theta, Beq],
                       columns=['from', 'to', 'Ctrl mode', 'Pset', 'Qset', 'Vfset', 'Vtset',
                                '∆Vm', '∆Va', 'Pf', 'Qf', 'Pt', 'Qt', 'm', 'Ɵ', 'Beq'],
                       index=nc.branch_names))
    print('\nerror:', norm_f)

    return norm_f, V, m, theta, Beq


def dSbus_dV(Ybus, V):

    n = len(V)
    Ibus = Ybus * V

    diagV = sp.diags(V)
    diagIbus = sp.diags(Ibus)
    diagVnorm = sp.diags(V / np.abs(V))

    dSbus_dV1 = 1j * diagV * conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dV2 = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm  # dSbus / dVm

    return dSbus_dV1, dSbus_dV2


def dSbus_dsh(nbranch, V, iPxsh, Cf, Ct, k2, tap, Ys):
    """
    The following explains the expressions used to form the matrices:

    S = diag(V) * conj(Ibus) = diag(conj(Ibus)) * V
    S = diag(V) * conj(Ybus * V)
    where:
        Ybus = Cf' * Yf + Ct' * Yt + diag(Ysh)

        Yf = Yff * Cf + Yft * Ct
        Yt = Ytf * Cf + Ytt * Ct

        Ytt = Ys + 1j*Bc/2
        Yff = Gsw+( (Ytt+1j*Beq) ./ ((k2.^2).*tap .* conj(tap))  )
        Yft = - Ys ./ conj(tap)
        Ytf = - Ys ./ tap

    Polar coordinates:
      Partials of Ytt, Yff, Yft and Ytf w.r.t. Theta_shift
        dYtt/dsh = zeros(nl,1)
        dYff/dsh = zeros(nl,1)
        dYft/dsh = -Ys./(-1j*k2.*conj(tap))
        dYtf/dsh = -Ys./( 1j*k2.*tap      )

      Partials of Yf, Yt, Ybus w.r.t. Theta_shift
        dYf/dsh = dYff/dsh * Cf + dYft/dsh * Ct
        dYt/dsh = dYtf/dsh * Cf + dYtt/dsh * Ct

        dYbus/dsh = Cf' * dYf/dsh + Ct' * dYt/dsh

      Partials of Sbus w.r.t. shift angle
        dSbus/dsh = diag(V) * conj(dYbus/dsh * V)

    :param branch:
    :param V:
    :param iPfsh:
    :param Cf: Cf connectivity "from" matrix
    :param Ct: Ct connectivity "to" matrix
    :param k2: 'k2' parameter for the branches
    :param tap: tap vector for the branches
    :param Ys: Yseries vector for the branches
    :return:
    """
    # Location of the branch elements with Pf control by theta_shift to
    # meet the setting.
    # (Converters and Phase Shifter Transformers, but no VSCIII)
    nl = nbranch
    nb = len(V)
    nPxsh = len(iPxsh)

    # # Selector of active Theta shifters
    # # shAux = zeros(nl)  # AAB- Vector of zeros for the selector
    # # shAux[iPxsh] = 1  # AAB- Fill the selector with "1" where Theta_shift is active
    # # AAB- Theta_shift selector multiplied by the series admittance Ys, size [nl,nl]
    # diagYssh = sp.diags(Ys[iPxsh]).tocsc()
    #
    diagV = sp.diags(V).tocsc()
    #
    # # Allocate for computational speed
    # dYtt_dsh = sp.lil_matrix((nl, nPxsh))
    # dYff_dsh = sp.lil_matrix((nl, nPxsh))
    # dYft_dsh = sp.lil_matrix((nl, nPxsh))
    # dYtf_dsh = sp.lil_matrix((nl, nPxsh))
    # dSbus_dPxsh = sp.lil_matrix((nb, nPxsh))
    #
    # for k, i in enumerate(iPxsh):
    #     # AAB- Selects the column of diagYssh representing only the active shift angles
    #     Yssh = diagYssh[:, k].toarray()[:, 0]
    #
    #     # Partials of Ytt, Yff, Yft and Ytf w.r.t. Theta shift
    #     dYtt_dsh[:, k] = sp.lil_matrix((nl))
    #     dYff_dsh[:, k] = sp.lil_matrix((nl))
    #     dYft_dsh[:, k] = -Yssh / (-1j * k2 * conj(tap))  # AAB- It also could be: sparse( ( -1j .* Yssh ) ./ ( k2 .* conj(tap) ) )
    #     dYtf_dsh[:, k] = -Yssh / (1j * k2 * tap)  # AAB- It also could be: sparse( (  1j .* Yssh ) ./ ( k2 .*      tap  ) )
    #
    #     # Partials of Yf, Yt, Ybus w.r.t. Theta shift
    #     dYf_dsh = dYff_dsh[:, k] * Cf + dYft_dsh[:, k] * Ct  # AAB- size [nl,nb] per active Theta shift
    #     dYt_dsh = dYtf_dsh[:, k] * Cf + dYtt_dsh[:, k] * Ct  # AAB- size [nl,nb] per active Theta shift
    #
    #     dYbus_dsh = Cf.t * dYf_dsh + Ct.t * dYt_dsh  # AAB- size [nb,nb] per active Theta shift
    #
    #     # Partials of S w.r.t. Theta shift
    #     dSbus_dPxsh[:, k] = diagV * conj(dYbus_dsh * V)  # AAB- Final dSbus_dsh has a size of [nb, nPxsh]
    mask = np.zeros(len(Ys))
    mask[iPxsh] = 1
    Ys2 = Ys * mask
    dYft_dsh = sp.diags(-Ys2 / (-1j * k2 * conj(tap)))
    dYtf_dsh = sp.diags(-Ys2 / (1j * k2 * tap))

    # Cf2 = Cf[iPxsh, :]
    # Ct2 = Ct[iPxsh, :]

    dYbus_dsh = Cf.T * (dYft_dsh * Cf) + Ct.T * (dYtf_dsh * Ct)

    dSbus_dPxsh = diagV * (dYbus_dsh * diagV).conjugate()

    return dSbus_dPxsh


def dSbus_dma(iXxma, nbranch, V, Ys, Bc, Beq, k2, tap, Cf, Ct):

    nb = len(V)
    nl = nbranch
    nXxma = len(iXxma)
    diagV = sp.diags(V).tocsc()

    YttB = Ys + 1j * Bc / 2 + 1j * Beq  # Ytt + 1j * Beq

    # Selector of active ma for the specified control
    maAux = zeros(nl)  # AAB- Vector of zeros for the seclector
    maAux[iXxma] = 1  # AAB- Fill the selector with "1" where ma is active
    diagYsma = sparse(diag(maAux * Ys))  # AAB- ma selector multilied by the series addmitance Ys,  size [nl,nl]
    diagYttBma = sparse(diag(maAux * YttB))  # AAB- ma selector multilied by the series addmitance Ytt, size [nl,nl]

    # Dimensionalize (Allocate for computational speed)
    dYtt_dma = sp.lil_matrix((nl, nXxma))
    dYff_dma = sp.lil_matrix((nl, nXxma))
    dYft_dma = sp.lil_matrix((nl, nXxma))
    dYtf_dma = sp.lil_matrix((nl, nXxma))
    dSbus_dmax = sp.lil_matrix((nb, nXxma))

    for k, i in enumerate(iXxma):
        Ysma = diagYsma[:, i]  # AAB- Selects the column of diagYsma representing only the active ma for the specified control multiplied by Ys
        YttBma = diagYttBma[:, i]  # AAB- Selects the column of diagmaAux representing only the active ma for the specified control

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. ma
        dYff_dma[:, k] = sparse(-2 * YttBma / ((k2**2) * ((abs(tap))**3)))
        dYft_dma[:, k] = sparse(Ysma / (k2 * (abs(tap) * conj(tap))))
        dYtf_dma[:, k] = sparse(Ysma / (k2 * (abs(tap) * tap)))
        dYtt_dma[:, k] = sp.lil_matrix((nl))

        # Partials of Yf, Yt, Ybus w.r.t. ma
        dYf_dma = dYff_dma[:, k] * Cf + dYft_dma[:, k] * Ct  # AAB- size [nl,nb] per active ma
        dYt_dma = dYtf_dma[:, k] * Cf + dYtt_dma[:, k] * Ct  # AAB- size [nl,nb] per active ma

        dYbus_dma = Cf.t * dYf_dma + Ct.t * dYt_dma  # AAB- size [nb,nb] per active ma

        # Partials of Sbus w.r.t. ma
        dSbus_dmax[:, k] = diagV * conj(dYbus_dma * V)  # AAB- Final dSbus_dma has a size of [nb, nXxma]

    return dSbus_dmax


def dSbus_dBeq(iBeqx, nbranch, V, Cf, Ct, k2, tap):
    nb = len(V)
    nl = nbranch
    nBeqx = len(iBeqx)
    diagV = sp.diags(V).tocsc()

    # Selector of active Beq
    BeqAux = zeros(nl)  # AAB- Vector of zeros for the seclector
    BeqAux[iBeqx] = 1  # AAB- Fill the selector with 1 where Beq is active
    diagBeqsel = sparse(diag(BeqAux))  # AAB- Beq Selector [nl,nl]

    # Dimensionalize (Allocate for computational speed)
    dYtt_dBeq = sp.lil_matrix((nl, nBeqx))
    dYff_dBeq = sp.lil_matrix((nl, nBeqx))
    dYft_dBeq = sp.lil_matrix((nl, nBeqx))
    dYtf_dBeq = sp.lil_matrix((nl, nBeqx))
    dSbus_dBeqx = sp.lil_matrix((nb, nBeqx))

    for k, i in enumerate(iBeqx):
        Beqsel = diagBeqsel[:, i]  # AAB- Selects the column of diagBeqsel representing only the active Beq

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Beq
        dYtt_dBeq[:, k] = sp.lil_matrix((nl))
        dYff_dBeq[:, k] = sparse(((1j * Beqsel) / ((k2 * np.abs(tap))**2)))
        dYft_dBeq[:, k] = sp.lil_matrix((nl))
        dYtf_dBeq[:, k] = sp.lil_matrix((nl))

        # Partials of Yf, Yt, Ybus w.r.t. Beq
        dYf_dBeq = dYff_dBeq[:, k] * Cf + dYft_dBeq[:, k] * Ct  # AAB- size [nl,nb] per active Beq
        dYt_dBeq = dYtf_dBeq[:, k] * Cf + dYtt_dBeq[:, k] * Ct  # AAB- size [nl,nb] per active Beq

        dYbus_dBeq = Cf.t * dYf_dBeq + Ct.t * dYt_dBeq  # AAB- size [nb,nb] per active Beq

        # Partials of S w.r.t. Beq
        dSbus_dBeqx[:, k] = diagV * conj(dYbus_dBeq * V)  # AAB- Final dSbus_dBeq has a size of [nb, nBeqx]

    return dSbus_dBeqx


def dSbus_dx(Ybus, V, nbranch, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv,
             Cf, Ct, k2, tap, Ys, Bc, Beq):

    # Va, Vm Partials
    dSbus_dVa, dSbus_dVm = dSbus_dV(Ybus, V)

    # Shift Angle Partials
    dSbus_dPfsh = dSbus_dsh(nbranch, V, iPfsh, Cf, Ct, k2, tap, Ys)
    dSbus_dPfdp = dSbus_dsh(nbranch, V, iPfdp, Cf, Ct, k2, tap, Ys)

    # ma Partials
    dSbus_dQfma = dSbus_dma(iQfma, nbranch, V, Ys, Bc, Beq, k2, tap, Cf, Ct)
    dSbus_dQtma = dSbus_dma(iQtma, nbranch, V, Ys, Bc, Beq, k2, tap, Cf, Ct)
    dSbus_dVtma = dSbus_dma(iVtma, nbranch, V, Ys, Bc, Beq, k2, tap, Cf, Ct)

    # Beq Partials
    dSbus_dBeqz = dSbus_dBeq(iBeqz, nbranch, V, Cf, Ct, k2, tap)
    dSbus_dBeqv = dSbus_dBeq(iBeqv, nbranch, V, Cf, Ct, k2, tap)

    return dSbus_dVa, dSbus_dVm, dSbus_dPfsh, dSbus_dQfma, dSbus_dBeqz, dSbus_dBeqv, dSbus_dVtma, dSbus_dQtma, dSbus_dPfdp


def dSbr_dV(F, T, V, Cf, Ct, Yf, Yt):
    nl = len(F)
    nb = len(V)

    Yfc = conj(Yf)
    Ytc = conj(Yt)
    Vc = conj(V)
    Ifc = Yfc * Vc  # conjugate of "from" current
    Itc = Ytc * Vc  # conjugate of "to" current
    Vf = V[F]
    Vt = V[T]

    diagVf = sp.diags(Vf).tocsc()
    diagVt = sp.diags(Vt).tocsc()
    diagIfc = sp.diags(Ifc).tocsc()
    diagItc = sp.diags(Itc).tocsc()

    Vnorm = V / np.abs(V)
    diagVc = sp.diags(Vc).tocsc()
    diagVnorm = sp.diags(Vnorm).tocsc()
    CVf = Cf * Vf  # sparse(1:nl, f, V(f), nl, nb)
    CVnf = Cf * Vnorm[F]  # sparse(1:nl, f, Vnorm(f), nl, nb)
    CVt = Ct * Vt  # sparse(1:nl, t, V(t), nl, nb)
    CVnt = Ct * Vnorm[T]  # sparse(1:nl, t, Vnorm(t), nl, nb)

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)  # dSf_dVa
    dSf_dVm = diagVf * conj(Yf * diagVnorm) + diagIfc * CVnf  # dSf_dVm
    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)  # dSt_dVa
    dSt_dVm = diagVt * conj(Yt * diagVnorm) + diagItc * CVnt  # dSt_dVm

    # dSf_dV1, dSf_dV2, dSt_dV1, dSt_dV2
    return dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm


def dSbr_dsh(iPxsh, nl, V, Cf, Ct, k2, tap, Ys):

    nPxsh = len(iPxsh)

    # Selector of active Theta shifters
    shAux = zeros(nl)  # AAB- Vector of zeros for the seclector
    shAux[iPxsh] = 1  # AAB- Fill the selector with "1" where Theta_shift is active
    diagYssh = sp.diags(shAux * Ys).tocsc()  # AAB- Theta_shift selector multilied by the series addmitance Ys, size [nl,nl]

    # Dimensionalize (Allocate for computational speed)
    dYtt_dsh = sp.lil_matrix((nl, nPxsh))
    dYff_dsh = sp.lil_matrix((nl, nPxsh))
    dYft_dsh = sp.lil_matrix((nl, nPxsh))
    dYtf_dsh = sp.lil_matrix((nl, nPxsh))
    dSf_dshx = sp.lil_matrix((nl, nPxsh))
    dSt_dshx = sp.lil_matrix((nl, nPxsh))

    for k, i in enumerate(iPxsh):
        Yssh = diagYssh[:, i]  # AAB- Selects the column of diagYssh representing only the active shift angles

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Theta shift
        dYtt_dsh[:, k] = sp.lil_matrix((nl))
        dYff_dsh[:, k] = sp.lil_matrix((nl))
        dYft_dsh[:, k] = sparse(-Yssh / (-1j * k2 * conj(tap)))  # AAB- It also could be: sparse( ( -1j .* Yssh ) ./ ( k2 .* conj(tap) ) )
        dYtf_dsh[:, k] = sparse(-Yssh / (1j * k2 * tap))  # AAB- It also could be: sparse( (  1j .* Yssh ) ./ ( k2 .*      tap  ) )

        # Partials of Yf and Yt w.r.t. Theta shift
        dYf_dsh = dYff_dsh[:, k] * Cf + dYft_dsh[:, k] * Ct  # AAB- size [nl,nb] per active Theta shift
        dYt_dsh = dYtf_dsh[:, k] * Cf + dYtt_dsh[:, k] * Ct  # AAB- size [nl,nb] per active Theta shift

        # Partials of Sf and St w.r.t. Theta shift
        dSf_dshx[:, k] = diag(Cf * V) * conj(dYf_dsh * V)  # AAB- Final dSf_dsh has a size of [nl, nPxsh]
        dSt_dshx[:, k] = diag(Ct * V) * conj(dYt_dsh * V)  # AAB- Final dSt_dsh has a size of [nl, nPxsh]

    return dSf_dshx, dSt_dshx


def dSbr_dma(iXxma, nl, V, Cf, Ct, k2, tap, Ys, Bc, Beq):

    nXxma = len(iXxma)

    YttBeq = Ys + 1j * Bc / 2 + 1j * Beq  # Ytt + jBeq

    # Selector of active ma for the specified control
    maAux = zeros(nl)  # AAB- Vector of zeros for the seclector
    maAux[iXxma] = 1  # AAB- Fill the selector with "1" where ma is active
    diagYsma = sp.diags(maAux * Ys).tocsc()  # AAB- ma selector multilied by the series addmitance Ys,  size [nl,nl]
    diagYttBeqma = sp.diags(maAux * YttBeq).tocsc()  # AAB- ma selector multilied by the series addmitance Ytt, size [nl,nl]

    # Dimensionalize (Allocate for computational speed)
    dYtt_dma = sp.lil_matrix((nl, nXxma))
    dYff_dma = sp.lil_matrix((nl, nXxma))
    dYft_dma = sp.lil_matrix((nl, nXxma))
    dYtf_dma = sp.lil_matrix((nl, nXxma))
    dSf_dmax = sp.lil_matrix((nl, nXxma))
    dSt_dmax = sp.lil_matrix((nl, nXxma))

    for k, i in enumerate(iXxma):

        Ysma = diagYsma[:, i]  # AAB- Selects the column of diagYsma representing only the active ma for the specified control multiplied by Ys
        YttBeqma = diagYttBeqma[:, i]  # AAB- Selects the column of diagmaAux representing only the active ma for the specified control

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. ma
        dYtt_dma[:, k] = sp.lil_matrix((nl))
        dYff_dma[:, k] = sparse(-2 * YttBeqma / ((k2**2) * (np.abs(tap)**3)))
        dYft_dma[:, k] = sparse(Ysma / (k2 * (np.abs(tap) * conj(tap))))
        dYtf_dma[:, k] = sparse(Ysma / (k2 * (np.abs(tap) * tap)))

        # Partials of Yf and Yt w.r.t. ma
        dYf_dma = dYff_dma[:, k] * Cf + dYft_dma[:, k] * Ct  # AAB- size [nl,nb] per active ma
        dYt_dma = dYtf_dma[:, k] * Cf + dYtt_dma[:, k] * Ct  # AAB- size [nl,nb] per active ma

        # Partials of Sf and St w.r.t. ma
        dSf_dmax[:, k] = diag(Cf * V) * conj(dYf_dma * V)  # AAB- Final dSf_dma has a size of [nl, nXxma]
        dSt_dmax[:, k] = diag(Ct * V) * conj(dYt_dma * V)  # AAB- Final dSf_dma has a size of [nl, nXxma]

    return dSf_dmax, dSt_dmax


def dSbr_dBeq(iBeqx, nl, V, Cf, Ct, k2, tap):

    nBeqx = len(iBeqx)

    # Selector of active Beq
    BeqAux = zeros(nl)  # AAB- Vector of zeros for the seclector
    BeqAux[iBeqx] = 1  # AAB- Fill the selector with 1 where Beq is active
    diagBeqsel = sparse(diag(BeqAux))  # AAB- Beq Selector [nl,nl]

    # Dimensionalize (Allocate for computational speed)
    dYtt_dBeq = sp.lil_matrix((nl, nBeqx))
    dYff_dBeq = sp.lil_matrix((nl, nBeqx))
    dYft_dBeq = sp.lil_matrix((nl, nBeqx))
    dYtf_dBeq = sp.lil_matrix((nl, nBeqx))
    dSf_dBeqx = sp.lil_matrix((nl, nBeqx))
    dSt_dBeqx = sp.lil_matrix((nl, nBeqx))

    for k, i in enumerate(iBeqx):
        Beqsel = diagBeqsel[:, i]  # AAB- Selects the column of diagBeqsel representing only the active Beq

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Beq
        dYtt_dBeq[:, k] = sp.lil_matrix((nl))
        dYff_dBeq[:, k] = sparse(((1j * Beqsel) / ((k2 * np.abs(tap))**2)))
        dYft_dBeq[:, k] = sp.lil_matrix((nl))
        dYtf_dBeq[:, k] = sp.lil_matrix((nl))

        # Partials of Yf, Yt, Ybus w.r.t. Beq
        dYf_dBeq = dYff_dBeq[:, k] * Cf + dYft_dBeq[:, k] * Ct  # AAB- size [nl,nb] per active Beq
        dYt_dBeq = dYtf_dBeq[:, k] * Cf + dYtt_dBeq[:, k] * Ct  # AAB- size [nl,nb] per active Beq

        # Partials of Sf and St w.r.t. Beq
        dSf_dBeqx[:, k] = diag(Cf * V) * conj(dYf_dBeq * V)  # AAB- Final dSf_dBeq has a size of [nl, nBeqx]
        dSt_dBeqx[:, k] = diag(Ct * V) * conj(dYt_dBeq * V)  # AAB- Final dSt_dBeq has a size of [nl, nBeqx]

    return dSf_dBeqx, dSt_dBeqx


def calc_J(F, T, Cf, Ct, Ybus, Yf, Yt, Ys, V, k2, tap, Bc, Beq, Kdp, pvpq, pq,
           iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, VfBeqbus, Vtmabus):

    nl, nb = Cf.shape

    # -------------------------------------------
    # Sbus derivatives: F1(x), F2(x), F6(x) and F7(x) Partial derivatives Power Balance w.r.t. x

    # Va, Vm Partials
    dSbus_dVa, dSbus_dVm = dSbus_dV(Ybus, V)

    # Shift Angle Partials
    dSbus_dPfsh = dSbus_dsh(nl, V, iPfsh, Cf, Ct, k2, tap, Ys)
    dSbus_dPfdp = dSbus_dsh(nl, V, iPfdp, Cf, Ct, k2, tap, Ys)

    # ma Partials
    dSbus_dQfma = dSbus_dma(iQfma, nl, V, Ys, Bc, Beq, k2, tap, Cf, Ct)
    dSbus_dQtma = dSbus_dma(iQtma, nl, V, Ys, Bc, Beq, k2, tap, Cf, Ct)
    dSbus_dVtma = dSbus_dma(iVtma, nl, V, Ys, Bc, Beq, k2, tap, Cf, Ct)

    # Beq Partials
    dSbus_dBeqz = dSbus_dBeq(iBeqz, nl, V, Cf, Ct, k2, tap)
    dSbus_dBeqv = dSbus_dBeq(iBeqv, nl, V, Cf, Ct, k2, tap)

    # ---------------------------------------------
    # Sbr derivatives: F3(x), F4(x), F5(x) and F8(x) Partial derivatives Sf and St w.r.t. x

    # Va, Vm Partials
    dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm = dSbr_dV(F, T, V, Cf, Ct, Yf, Yt)

    # Shift Angle Partials
    dSf_dPfsh, dSt_dPfsh = dSbr_dsh(iPfsh, nl, V, Cf, Ct, k2, tap, Ys)
    # Shift Angle Partials for Voltage Droop Control
    dSf_dPfdp, dSt_dPfdp = dSbr_dsh(iPfdp, nl, V, Cf, Ct, k2, tap, Ys)

    # ma Partials
    dSf_dQfma, dSt_dQfma = dSbr_dma(iQfma, nl, V, Cf, Ct, k2, tap, Ys, Bc, Beq)
    dSf_dQtma, dSt_dQtma = dSbr_dma(iQtma, nl, V, Cf, Ct, k2, tap, Ys, Bc, Beq)
    dSf_dVtma, dSt_dVtma = dSbr_dma(iVtma, nl, V, Cf, Ct, k2, tap, Ys, Bc, Beq)

    dSf_dBeqz, dSt_dBeqz = dSbr_dBeq(iBeqz, nl, V, Cf, Ct, k2, tap)
    dSf_dBeqv, dSt_dBeqv = dSbr_dBeq(iBeqv, nl, V, Cf, Ct, k2, tap)

    # ---------------------------------------------
    # Droop: F9(x) Partial derivatives Droop Control w.r.t. x
    # Partials of Pfdp w.r.t. Va
    dPfdp_dVa = -dSf_dVa.real

    # Partials of Pfdp w.r.t. Vm

    dVmf_dVm = sp.lil_matrix((nl, nb))  # Initialize for speed [nl,nb]
    fdp = F[iPfdp]  # List of "from" buses with Voltage Droop Control [nPfdp, 1]
    nPfdp = len(iPfdp)
    Cfdp = Cf * sp.diags(ones(nPfdp)).tocsc()  # connection matrix for line & from buses with Voltage Droop Control [nPfdp, nb]
    dVmf_dVm[iPfdp, :] = Cfdp  # Fill derivatives [nl, nb]
    dPfdp_dVm = -dSf_dVm.real + Kdp * dVmf_dVm

    # Partials of Pfdp w.r.t. ThetaSh for PST, VSCI and VSCII
    dPfdp_dPfsh = -dSf_dPfsh.real

    # Partials of Pfdp w.r.t. ma
    dPfdp_dQfma = -dSf_dQfma.real
    dPfdp_dQtma = -dSf_dQtma.real
    dPfdp_dVtma = -dSf_dVtma.real

    # Partials of Pfdp w.r.t. Beq
    dPfdp_dBeqz = -dSf_dBeqz.real
    dPfdp_dBeqv = -dSf_dBeqv.real

    # Partials of Pfdp w.r.t. ThetaSh for VSCIII
    dPfdp_dPfdp = -dSf_dPfdp.real

    j11 = dSbus_dVa[pvpq, pvpq].real  # avoid Slack
    j12 = dSbus_dVm[pvpq, pq].real  # avoid Slack
    j13 = dSbus_dPfsh[pvpq, :].real  # avoid Slack
    j14 = dSbus_dQfma[pvpq, :].real  # avoid Slack
    j15 = dSbus_dBeqz[pvpq, :].real  # avoid Slack
    j16 = dSbus_dBeqv[pvpq, :].real  # avoid Slack
    j17 = dSbus_dVtma[pvpq, :].real  # avoid Slack
    j18 = dSbus_dQtma[pvpq, :].real  # avoid Slack
    j19 = dSbus_dPfdp[pvpq, :].real  # avoid Slack

    j21 = dSbus_dVa[pq, pvpq].imag  # avoid Slack and pv
    j22 = dSbus_dVm[pq, pq].imag  # avoid Slack and pv
    j23 = dSbus_dPfsh[pq, :].imag  # avoid Slack and pv
    j24 = dSbus_dQfma[pq, :].imag  # avoid Slack and pv
    j25 = dSbus_dBeqz[pq, :].imag  # avoid Slack and pv
    j26 = dSbus_dBeqv[pq, :].imag  # avoid Slack and pv
    j27 = dSbus_dVtma[pq, :].imag  # avoid Slack and pv
    j28 = dSbus_dQtma[pq, :].imag  # avoid Slack and pv
    j29 = dSbus_dPfdp[pq, :].imag  # avoid Slack and pv

    j31 = dSf_dVa[iPfsh, pvpq].real  # Only Pf control elements iPfsh
    j32 = dSf_dVm[iPfsh, pq].real  # Only Pf control elements iPfsh
    j33 = dSf_dPfsh[iPfsh, :].real  # Only Pf control elements iPfsh
    j34 = dSf_dQfma[iPfsh, :].real  # Only Pf control elements iPfsh
    j35 = dSf_dBeqz[iPfsh, :].real  # Only Pf control elements iPfsh
    j36 = dSf_dBeqv[iPfsh, :].real  # Only Pf control elements iPfsh
    j37 = dSf_dVtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j38 = dSf_dQtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j39 = dSf_dPfdp[iPfsh, :].real  # Only Pf control elements iPfsh

    j41 = dSf_dVa[iQfma, pvpq].imag  # Only Qf control elements iQfma
    j42 = dSf_dVm[iQfma, pq].imag  # Only Qf control elements iQfma
    j43 = dSf_dPfsh[iQfma, :].imag  # Only Qf control elements iQfma
    j44 = dSf_dQfma[iQfma, :].imag  # Only Qf control elements iQfma
    j45 = dSf_dBeqz[iQfma, :].imag  # Only Qf control elements iQfma
    j46 = dSf_dBeqv[iQfma, :].imag  # Only Qf control elements iQfma
    j47 = dSf_dVtma[iQfma, :].imag  # Only Qf control elements iQfma
    j48 = dSf_dQtma[iQfma, :].imag  # Only Qf control elements iQfma
    j49 = dSf_dPfdp[iQfma, :].imag  # Only Qf control elements iQfma

    j51 = dSf_dVa[iBeqz, pvpq].imag  # Only Qf control elements iQfbeq
    j52 = dSf_dVm[iBeqz, pq].imag  # Only Qf control elements iQfbeq
    j53 = dSf_dPfsh[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j54 = dSf_dQfma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j55 = dSf_dBeqz[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j56 = dSf_dBeqv[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j57 = dSf_dVtma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j58 = dSf_dQtma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j59 = dSf_dPfdp[iBeqz, :].imag  # Only Qf control elements iQfbeq

    j61 = dSbus_dVa[VfBeqbus, pvpq].imag  # Only Vf control elements iVfbeq
    j62 = dSbus_dVm[VfBeqbus, pq].imag  # Only Vf control elements iVfbeq
    j63 = dSbus_dPfsh[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j64 = dSbus_dQfma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j65 = dSbus_dBeqz[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j66 = dSbus_dBeqv[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j67 = dSbus_dVtma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j68 = dSbus_dQtma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j69 = dSbus_dPfdp[VfBeqbus, :].imag  # Only Vf control elements iVfbeq

    j71 = dSbus_dVa[Vtmabus, pvpq].imag  # Only Vt control elements iVtma
    j72 = dSbus_dVm[Vtmabus, pq].imag  # Only Vt control elements iVtma
    j73 = dSbus_dPfsh[Vtmabus, :].imag  # Only Vt control elements iVtma
    j74 = dSbus_dQfma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j75 = dSbus_dBeqz[Vtmabus, :].imag  # Only Vt control elements iVtma
    j76 = dSbus_dBeqv[Vtmabus, :].imag  # Only Vt control elements iVtma
    j77 = dSbus_dVtma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j78 = dSbus_dQtma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j79 = dSbus_dPfdp[Vtmabus, :].imag  # Only Vt control elements iVtma

    j81 = dSt_dVa[iQtma, pvpq].imag  # Only Qt control elements iQtma
    j82 = dSt_dVm[iQtma, pq].imag  # Only Qt control elements iQtma
    j83 = dSt_dPfsh[iQtma, :].imag  # Only Qt control elements iQtma
    j84 = dSt_dQfma[iQtma, :].imag  # Only Qt control elements iQtma
    j85 = dSt_dBeqz[iQtma, :].imag  # Only Qt control elements iQtma
    j86 = dSt_dBeqv[iQtma, :].imag  # Only Qt control elements iQtma
    j87 = dSt_dVtma[iQtma, :].imag  # Only Qt control elements iQtma
    j88 = dSt_dQtma[iQtma, :].imag  # Only Qt control elements iQtma
    j89 = dSt_dPfdp[iQtma, :].imag  # Only Qt control elements iQtma

    j91 = dPfdp_dVa[iPfdp, pvpq]  # Only Droop control elements iPfdp
    j92 = dPfdp_dVm[iPfdp, pq]  # Only Droop control elements iPfdp
    j93 = dPfdp_dPfsh[iPfdp, :]  # Only Droop control elements iPfdp
    j94 = dPfdp_dQfma[iPfdp, :]  # Only Droop control elements iPfdp
    j95 = dPfdp_dBeqz[iPfdp, :]  # Only Droop control elements iPfdp
    j96 = dPfdp_dBeqv[iPfdp, :]  # Only Droop control elements iPfdp
    j97 = dPfdp_dVtma[iPfdp, :]  # Only Droop control elements iPfdp
    j98 = dPfdp_dQtma[iPfdp, :]  # Only Droop control elements iPfdp
    j99 = dPfdp_dPfdp[iPfdp, :]  # Only Droop control elements iPfdp

    # Jacobian
    J = sp.vstack((
        sp.hstack((j11, j12, j13, j14, j15, j16, j17, j18, j19)),
        sp.hstack((j21, j22, j23, j24, j25, j26, j27, j28, j29)),
        sp.hstack((j31, j32, j33, j34, j35, j36, j37, j38, j39)),
        sp.hstack((j41, j42, j43, j44, j45, j46, j47, j48, j49)),
        sp.hstack((j51, j52, j53, j54, j55, j56, j57, j58, j59)),
        sp.hstack((j61, j62, j63, j64, j65, j66, j67, j68, j69)),
        sp.hstack((j71, j72, j73, j74, j75, j76, j77, j78, j79)),
        sp.hstack((j81, j82, j83, j84, j85, j86, j87, j88, j89)),
        sp.hstack((j91, j92, j93, j94, j95, j96, j97, j98, j99))
    ))  # FUBM-Jacobian Matrix
    return J


def calc_g(Ybus, Yf, Yt, Cf, Ct, F, V, S0, Kdp, Pset, Qset, Vmset, pvpq, pq,
           iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, VfBeqbus, Vtmabus):

    If = Yf * V
    It = Yt * V
    Vf = Cf * V
    Vt = Ct * V
    Sf = Vf * np.conj(If)  # eq. (8)
    St = Vt * np.conj(It)  # eq. (9)
    Vm = np.abs(V)

    # compute the mismatch (g)
    S_calc = V * np.conj(Ybus * V)  # compute Bus power injections
    mis = S_calc - S0
    misPbus = mis.real[pvpq]
    misQbus = mis.imag[pq]
    misPfsh = Sf.real[iPfsh] - Pset[iPfsh]
    misQfma = Sf.imag[iQfma] - Qset[iQfma]
    misBeqz = Sf.imag[iBeqz]
    misBeqv = mis.imag[VfBeqbus]
    misVtma = mis.imag[Vtmabus]
    misQtma = St.imag[iQtma] - Qset[iQtma]
    misPfdp = -Sf.real[iPfdp] + Pset[iPfdp] + Kdp[iPfdp] * (Vm[F[iPfdp]] - Vmset[F[iPfdp]])

    g = np.r_[misPbus,  # FUBM- F1(x0) Power balance mismatch - Va
              misQbus,  # FUBM- F2(x0) Power balance mismatch - Vm
              misPfsh,  # FUBM- F3(x0) Pf control    mismatch - Theta_shift
              misQfma,  # FUBM- F4(x0) Qf control    mismatch - ma
              misBeqz,  # FUBM- F5(x0) Qf control    mismatch - Beq
              misBeqv,  # FUBM- F6(x0) Vf control    mismatch - Beq
              misVtma,  # FUBM- F7(x0) Vt control    mismatch - ma
              misQtma,  # FUBM- F8(x0) Qt control    mismatch - ma
              misPfdp]  # return the complete mismatch function
    return g


def nr_acdc(nc: SnapshotData, tolerance=1e-6, max_iter=4):
    """

    :param nc:
    :param tolerance:
    :param max_iter:
    :return:
    """
    # compute the indices of the converter/transformer variables from their control strategies
    iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, iVscL = determine_branch_indices(circuit=nc)

    VfBeqbus = nc.F[iBeqv]
    Vtmabus = nc.T[iVtma]

    # initialize the variables
    V = nc.Vbus
    S0 = nc.Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmset = Vm.copy()
    m = nc.m.copy()
    theta = nc.theta.copy() * 0
    Beq = nc.Beq.copy() * 0
    Pset = nc.Pset / nc.Sbase
    Qset = nc.Qset / nc.Sbase
    Kdp = nc.Kdp
    k2 = nc.k
    Cf = nc.C_branch_bus_f
    Ct = nc.C_branch_bus_t
    F = nc.F
    T = nc.T
    Ys = 1.0 / (nc.R + 1j * nc.X)
    Bc = nc.B
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[VfBeqbus, Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    nPfsh = len(iPfsh)  # FUBM- number of Pf controlled elements by theta_shift
    nQfma = len(iQfma)  # FUBM- number of Qf controlled elements by ma
    nQtma = len(iQtma)  # FUBM- number of Qt controlled elements by ma
    nVtma = len(iVtma)  # FUBM- number of Vt controlled elements by ma
    nBeqz = len(iBeqz)  # FUBM- number of Qf controlled elements by Beq
    nBeqv = len(iBeqv)  # FUBM- number of Vf controlled elements by Beq
    nVscL = len(iVscL)  # FUBM- Number of VSC with active PWM Losses Calculation
    nPfdp = len(iPfdp)  # FUBM- Number of VSC with Voltage Droop Control by theta_shift
    nVfBeqbus = len(VfBeqbus)  # FUBM- number of buses for Vf controlled by Beq
    nVtmabus = len(Vtmabus)  # FUBM- number of buses for Vt controlled by ma
    # --------------------------------------------------------------------------

    # variables dimensions in Jacobian
    # FUBM----------------------------------------------------------------------
    j1 = 1
    j2 = npv  # j1 :j2  - V angle of pv buses (bus)
    j3 = j2 + 1
    j4 = j2 + npq  # j3 :j4  - V angle of pq buses (bus)
    j5 = j4 + 1
    j6 = j4 + npq  # j5 :j6  - V mag   of pq buses (bus)
    j7 = j6 + 1
    j8 = j6 + nPfsh  # j7 :j8  - ShiftAngle of VSC and PST (branch)
    j9 = j8 + 1
    j10 = j8 + nQfma  # j9 :j10 - ma of Qf Controlled Transformers (branch)
    jA1 = j10 + 1
    jA2 = j10 + nBeqz  # j11:j12 - Beq of VSC for Zero Constraint (branch)
    jA3 = jA2 + 1
    jA4 = jA2 + nVfBeqbus  # j13:j14 - Beq of VSC for Vdc  Constraint (bus)
    jA5 = jA4 + 1
    jA6 = jA4 + nVtmabus  # j15:j16 - ma of VSC and Transformers for Vt Control (bus)
    jA7 = jA6 + 1
    jA8 = jA6 + nQtma  # j17:j18 - ma of VSC and Transformers for Qt Control (branch)
    jA9 = jA8 + 1
    jB0 = jA8 + nPfdp  # j19:j20 - ShiftAngle of VSC for Qt Control (branch)
    # -------------------------------------------------------------------------

    # compute initial admittances
    Ybus, Yf, Yt, tap = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=nc.Inom)

    g = calc_g(Ybus, Yf, Yt, Cf, Ct, F, V, S0, Kdp, Pset, Qset, Vmset, pvpq, pq,
               iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, VfBeqbus, Vtmabus)


    norm_f = np.max(np.abs(g))

    J = calc_J(F, T, Cf, Ct, Ybus, Yf, Yt, Ys, V, k2, tap, Bc, Beq, Kdp, pvpq, pq,
               iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, VfBeqbus, Vtmabus)

    return norm_f, V, m, theta, Beq


if __name__ == "__main__":

    np.set_printoptions(linewidth=10000)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/LineHVDCGrid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE57+IEEE14 DC grid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/ACDC_example_grid.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
    grid = FileOpen(fname).open()

    ####################################################################################################################
    # Compile
    ####################################################################################################################
    nc_ = compile_snapshot_circuit(grid)

    res = nr_acdc(nc=nc_, tolerance=1e-4, max_iter=2)

