"""
This is the linear ac power flow from the article:

Linearized AC Load Flow Applied to Analysis in Electric Power Systems
by: P. Rossoni, W. M da Rosa and E. A. Belati

Implementation by Santiago Peñate Vera 2018
"""

import time
import numpy as np
np.set_printoptions(linewidth=320)
from numpy import zeros, ones, mod, conj, array, r_, linalg, Inf, complex128, c_, r_, angle
from itertools import product
from numpy.linalg import solve
from scipy.sparse.linalg import spsolve
from scipy.sparse import issparse, csc_matrix as sparse
from scipy.sparse import hstack as hstack_s, vstack as vstack_s
import pandas as pd


def LACPF(Y, Ys, S, Vset, pq, pv):
    """
    Linearized AC Load Flow
    Args:
        Y: Admittance matrix
        Ys: Admittance matrix of the series elements
        S: Power injections vector of all the nodes
        Vset: Set voltages of all the nodes (used for the slack and PV nodes)
        pq: list of indices of the pq nodes
        pv: list of indices of the pv nodes

    Returns: Voltage vector and error
    """

    pvpq = r_[pv, pq]
    npq = len(pq)
    npv = len(pv)

    # compose the system matrix
    G = Y.real
    B = Y.imag
    Gp = Ys.real
    Bp = Ys.imag

    A11 = -Bp[np.ix_(pvpq, pvpq)]
    A12 = G[np.ix_(pvpq, pq)]
    A21 = -Gp[np.ix_(pq, pvpq)]
    A22 = -B[np.ix_(pq, pq)]

    Asys = vstack_s([hstack_s([A11, A12]),
                     hstack_s([A21, A22])], format="csc")

    # compose the right hand side (power vectors)
    rhs = r_[S.real[pvpq], S.imag[pq]]

    # solve the linear system
    x = spsolve(Asys, rhs)

    # compose the results vector
    voltages_vector = Vset.copy()

    #  set the pv voltages
    va_pv = x[0:npv]
    vm_pv = np.abs(Vset[pv])
    voltages_vector[pv] = vm_pv * np.exp(1.0j * va_pv)

    # set the PQ voltages
    va_pq = x[npv:npv+npq]
    vm_pq = np.ones(npq) - x[npv+npq::]
    voltages_vector[pq] = vm_pq * np.exp(1.0j * va_pq)

    # Calculate the error and check the convergence
    Scalc = voltages_vector * conj(Y * voltages_vector)

    # complex power mismatch
    power_mismatch = Scalc - S

    # concatenate error by type
    mismatch = r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

    # check for convergence
    normF = linalg.norm(mismatch, Inf)

    return voltages_vector, normF


def LACPF_2(Y, Ys, S, Vset, pq, pv):
    """
    Linearized AC Load Flow
    Args:
        Y: Admittance matrix
        Ys: Admittance matrix of the series elements
        S: Power injections vector of all the nodes
        Vset: Set voltages of all the nodes (used for the slack and PV nodes)
        pq: list of indices of the pq nodes
        pv: list of indices of the pv nodes

    Returns: Voltage vector and error
    """

    pvpq = r_[pv, pq]
    npq = len(pq)
    npv = len(pv)

    # compose the system matrix
    G = Y.real
    B = Y.imag
    Gp = Ys.real
    Bp = Ys.imag

    A11 = -Bp[np.ix_(pvpq, pvpq)]
    A12 = G[np.ix_(pvpq, pq)]
    A21 = -Gp[np.ix_(pq, pvpq)]
    A22 = -B[np.ix_(pq, pq)]

    Asys = vstack_s([hstack_s([A11, A12]),
                     hstack_s([A21, A22])], format="csc")

    # compose the right hand side (power vectors)
    rhs = r_[S.real[pvpq], S.imag[pq]]

    # solve the linear system
    x = spsolve(Asys, rhs)

    # compose the results vector
    voltages_vector = Vset.copy()

    #  set the pv voltages
    va_pv = x[0:npv]
    vm_pv = np.abs(Vset[pv])
    voltages_vector[pv] = vm_pv * np.exp(1.0j * va_pv)

    # set the PQ voltages
    va_pq = x[npv:npv + npq]
    vm_pq = np.ones(npq) - x[npv + npq::]
    voltages_vector[pq] = vm_pq * np.exp(1.0j * va_pq)

    # Calculate the error and check the convergence
    Scalc = voltages_vector * conj(Y * voltages_vector)

    # complex power mismatch
    power_mismatch = Scalc - S

    # ------------------------------------------------------------------------------------------------------------------
    drhs = r_[power_mismatch.real[pvpq], power_mismatch.imag[pq]]
    dx = spsolve(Asys, drhs)

    #  set the pv voltages
    va_pv = x[0:npv] + dx[0:npv]
    vm_pv = np.abs(Vset[pv])
    voltages_vector[pv] = vm_pv * np.exp(1.0j * va_pv)

    # set the PQ voltages
    va_pq = x[npv:npv + npq] + dx[npv:npv + npq]
    vm_pq = np.ones(npq) - x[npv + npq::] - dx[npv + npq::]
    voltages_vector[pq] = vm_pq * np.exp(1.0j * va_pq)

    # ------------------------------------------------------------------------------------------------------------------

    # concatenate error by type
    mismatch = r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

    # check for convergence
    normF = linalg.norm(mismatch, Inf)

    return voltages_vector, normF


def res_2_df(V, Sbus, tpe):
    """
    Create dataframe to display the results nicely
    :param V: Voltage complex vector
    :param Sbus: Power complex vector
    :param tpe: Types
    :return: Pandas DataFrame
    """
    vm = abs(V)
    va = np.angle(V)

    d = {1: 'PQ', 2: 'PV', 3: 'VD'}

    tpe_str = array([d[i] for i in tpe], dtype=object)
    data = c_[tpe_str, Sbus.real, Sbus.imag, vm, va]
    cols = ['Type', 'P', 'Q', '|V|', 'angle']
    df = pd.DataFrame(data=data, columns=cols)

    return df


if __name__ == '__main__':
    from GridCal.Engine import FileOpen, PowerFlowOptions, PowerFlowDriver, SolverType
    from matplotlib import pyplot as plt


    # grid.load_file('lynn5buspq.xlsx')
    # grid.load_file('lynn5buspv.xlsx')
    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx')

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'


    grid = FileOpen(fname).open()

    numerical_circuit = grid.compile_snapshot()

    circuits = numerical_circuit.compute()

    circuit = circuits[0]

    print('\nYbus:\n', circuit.Ybus.todense())
    print('\nSbus:\n', circuit.Sbus)
    print('\nIbus:\n', circuit.Ibus)
    print('\nVbus:\n', circuit.Vbus)
    print('\ntypes:\n', circuit.types)
    print('\npq:\n', circuit.pq)
    print('\npv:\n', circuit.pv)
    print('\nvd:\n', circuit.ref)

    start_time = time.time()

    # Y, Ys, Ysh, max_coefficient_count, S, voltage_set_points, pq, pv, vd
    v, err = LACPF_2(Y=circuit.Ybus,
                     Ys=circuit.Yseries,
                     S=circuit.Sbus,
                     Vset=circuit.Vbus,
                     pq=circuit.pq,
                     pv=circuit.pv)

    print('Linear AC:')
    print("--- %s seconds ---" % (time.time() - start_time))
    print('Results:\n', res_2_df(v, circuit.Sbus, circuit.types))
    print('error: \t', err)

    # check the method solution: v against the Newton-Raphson power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, tolerance=1e-9, control_q=False)
    power_flow = PowerFlowDriver(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = power_flow.results.voltage

    print('Results:\n', res_2_df(vnr, circuit.Sbus, circuit.types))
    print('error: \t', power_flow.results.error)

    # check
    dif = v - vnr
    print('\ndiff:\t', dif)
    print('\nmax diff:\t', max(abs(dif)))

    plt.show()
