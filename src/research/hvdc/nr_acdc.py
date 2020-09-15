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


def determine_branch_indices(circuit: AcDcSnapshotCircuit):
    """
    This function fills in the lists of indices to control different magnitudes

    :param circuit: Instance of AcDcSnapshotCircuit
    :returns idx_sh, idx_qz, idx_vf, idx_vt, idx_qt

    VSC Control modes:

    in the paper's scheme:
    from -> DC
    to   -> AC

                                                       | Incompatible with iQtma | incompatible with iVtma |
    |---------------|----------|-------|-------|-------|-------------------------|-------------------------|-------|
    |               | iPfsh    | iQfma | iBeqz | iBeqv | iVtma                   | iQtma                   | iPfdp |
    |---------------|----------|-------|-------|-------|-------------------------|-------------------------|-------|
    | VSC – 1       | Optional |       | x     |       | Optional                | Optional                |       |
    | VSC – 2       | x        |       |       | x     | Optional                | Optional                |       |
    | VSC – 3       | x        |       | x     |       | Optional                | Optional                | x     |
    | VSC – 4       | Optional |       |       |       | Optional                | Optional                | x     |
    | Transformer   |          |       |       |       |                         |                         |       |
    | Tap changer   |          |       |       |       | x                       |                         |       |
    | Phase shifter | x        |       |       |       |                         |                         |       |

    x: the variable is required
    """

    # indices in the global branch scheme (Vf=Vdc, Vt=Vac)
    iPfsh = list()  # All branches controlling Pf with theta_sh
    iQfma = list()  # Transformers controlling Qt with m
    iBeqz = list()  # all converters type I
    iBeqv = list()  # Converters controlling Vf with Beq
    iVtma = list()  # Branches controlling Vt with ma
    iQtma = list()  # Branches controlling Qt con m
    iPfdp = list()  # VSC type III

    for k, tpe in enumerate(circuit.control_mode):

        # Transformers -------------------------------------------------------------------------------------------------
        if tpe == TransformerControlType.fixed:
            pass

        elif tpe == TransformerControlType.power:
            iPfsh.append(k)

        # elif tpe == TransformerControlType.v_from:

        elif tpe == TransformerControlType.v_to:
            iVtma.append(k)

        # elif tpe == TransformerControlType.power_v_from:
        #     iPfsh.append(k)

        elif tpe == TransformerControlType.power_v_to:
            iPfsh.append(k)
            iVtma.append(k)

        # VSC ----------------------------------------------------------------------------------------------------------
        elif tpe == ConverterControlType.theta_vac:  # type 1 (I)
            iBeqz.append(k)
            iVtma.append(k)

        elif tpe == ConverterControlType.pf_qac:  # type 2  (I)
            iBeqz.append(k)
            iPfsh.append(k)

        elif tpe == ConverterControlType.pf_vac:  # type 3  (I)
            iBeqz.append(k)
            iPfsh.append(k)

        elif tpe == ConverterControlType.vdc_qac:  # type 4 (II)
            iBeqv.append(k)

        elif tpe == ConverterControlType.vdc_vac:  # type 5 (II)
            iBeqv.append(k)

        elif tpe == ConverterControlType.vdc_droop_qac:  # type 6 (III)
            iPfdp.append(k)

        elif tpe == ConverterControlType.vdc_droop_vac:  # type 7 (III)
            iPfdp.append(k)
            iVtma.append(k)

        elif tpe == 0:
            pass

        else:
            raise Exception('Unknown control type:' + str(tpe))

    vtBeqBus = circuit.F[iBeqv]
    vtmaBus = circuit.T[iVtma]

    return iBeqz, iPfsh, iQfma, iQtma, iPfdp, iBeqv, iVtma, vtBeqBus, vtmaBus


def compile_y(circuit: AcDcSnapshotCircuit, m, theta, Beq, If):
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
    br_states_diag = sp.diags(circuit.branch_active)
    Cf = br_states_diag * circuit.C_branch_bus_f
    Ct = br_states_diag * circuit.C_branch_bus_t

    # compute G-switch
    Gsw = circuit.G0 * np.power(If / circuit.Inom, 2.0)

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = circuit.C_bus_shunt * (circuit.shunt_admittance * circuit.shunt_active / circuit.Sbase)
    yshunt_f = Cf * Yshunt_from_devices
    yshunt_t = Ct * Yshunt_from_devices

    # form the admittance matrices ---------------------------------------------------------------------------------

    ys = 1.0 / (circuit.R + 1.0j * circuit.X)  # series impedance
    bc2 = 1j * circuit.B / 2  # shunt conductance
    # mp = circuit.k * m  # k is already filled with the appropriate value for each type of branch
    mp = m

    # compose the primitives
    Yff = Gsw + (ys + bc2 + 1.0j * Beq + yshunt_f) / (mp * mp)
    Yft = -ys / (mp * np.exp(-1.0j * theta))
    Ytf = -ys / (mp * np.exp(1.0j * theta))
    Ytt = ys + bc2 + yshunt_t

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt)

    return Ybus, Yf, Yt


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


def nr_acdc(nc: AcDcSnapshotCircuit, tolerance=1e-6, max_iter=4):
    """

    :param nc:
    :param tolerance:
    :param max_iter:
    :return:
    """
    # compute the indices of the converter/transformer variables from their control strategies
    idx_pf, idx_qz, idx_vf, idx_vt, idx_qt = determine_branch_indices(circuit=nc)

    # initialize the variables
    V = nc.Vbus
    S0 = nc.Sbus
    va = np.angle(V)
    vm = np.abs(V)
    m = nc.m.copy()
    theta = nc.theta.copy() * 0
    Beq = nc.Beq.copy() * 0
    Pset = nc.Pset / nc.Sbase
    Qset = nc.Qset / nc.Sbase
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[idx_vf, idx_vt])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    pvpq.sort()

    # compute initial admittances
    Ybus, Yf, Yt = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=nc.Inom)

    # compute branch flows
    If = Yf * V
    It = Yt * V
    Vf = nc.C_branch_bus_f * V
    Vt = nc.C_branch_bus_t * V
    Sf = Vf * np.conj(If)  # eq. (8)
    St = Vt * np.conj(It)  # eq. (9)
    gf = Sf - S0[nc.F]
    gt = St - S0[nc.T]

    # compute admittances as a function of the branch variables
    Ybus, Yf, Yt = compile_y(circuit=nc, m=m, theta=theta, Beq=Beq, If=If)

    # compute the mismatch (g)
    S_calc = V * np.conj(Ybus * V)  # compute Bus power injections
    gs = S_calc - S0  # equation (6)
    gp = gs.real[pvpq]  # eq. (12)
    gq = gs.imag[pq]  # eq. (13)
    gsh = Sf.real[idx_pf] - Pset[idx_pf]  # eq. (14) controls that the specified power flow is met
    gqz = Sf.imag[idx_qz]  # eq. (15) controls that 'Beq' absorbs the reactive power.
    gvf = gf.imag[idx_vf]  # eq. (16) Controls that 'ma' modulates to control the "voltage from" module.
    gvt = gt.imag[idx_vt]  # eq. (17) Controls that 'ma' modulates to control the "voltage to" module.
    gqt = St.imag[idx_qt] - Qset[idx_qt]  # eq. (18)  controls that the specified reactive power flow is met
    g = np.r_[gp, gq, gsh, gqz, gvf, gvt, gqt]  # return the complete mismatch function

    # compose the initial x value
    x = np.r_[va[pvpq], vm[pq], theta[idx_pf], Beq[idx_qz], m[idx_vf], m[idx_vt], Beq[idx_qt]]

    # compute the error
    ff = np.r_[gs[pvpq_orig].real, gs[pq].imag]  # concatenate to form the mismatch function
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
                                     va, vm, m, theta, Beq),
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
        gf = Sf - S0[nc.F]
        gt = St - S0[nc.T]

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

        # compute the error
        ff = np.r_[gs[pvpq_orig].real, gs[pq].imag]  # concatenate to form the mismatch function
        norm_f = 0.5 * ff.dot(ff)
        print('error:\n', norm_f)

        iterations += 1

    print('END', '-' * 200)
    print('Bus values')
    print(pd.DataFrame(data=np.c_[type_names, S_calc.real, S_calc.imag, gs.real, gs.imag, vm, va],
                       columns=['Type', 'P', 'Q', '∆P', '∆Q', 'Vm', 'Va'],
                       index=nc.bus_names))
    print('\nBranch values')
    print(pd.DataFrame(data=np.c_[nc.F, nc.T, nc.control_mode, nc.Pset, nc.Qset, nc.vf_set, nc.vt_set,
                                  vm[nc.F] - vm[nc.T], va[nc.F] - va[nc.T],
                                  Sf.real, Sf.imag, Sf.real, Sf.imag, m, theta, Beq],
                       columns=['from', 'to', 'Ctrl mode', 'Pset', 'Qset', 'Vfset', 'Vtset',
                                '∆Vm', '∆Va', 'Pf', 'Qf', 'Pt', 'Qt', 'm', 'Ɵ', 'Beq'],
                       index=nc.branch_names))
    print('\nerror:', norm_f)

    return norm_f, V, m, theta, Beq


if __name__ == "__main__":
    np.set_printoptions(linewidth=10000)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/LineHVDCGrid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE57+IEEE14 DC grid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/ACDC_example_grid.gridcal'
    grid = FileOpen(fname).open()

    ####################################################################################################################
    # Compile
    ####################################################################################################################
    nc_ = compile_acdc_snapshot_circuit(grid)

    res = nr_acdc(nc=nc_, tolerance=1e-4, max_iter=2)

