import numpy as np
np.set_printoptions(linewidth=320)
from numpy import zeros, ones, mod, conj, array, c_, r_, linalg, Inf, complex128
from itertools import product
from numpy.linalg import solve, inv
from scipy.sparse.linalg import factorized
from scipy.sparse import issparse, csc_matrix as sparse

np.set_printoptions(linewidth=1000000, )

# Set the complex precision to use
complex_type = complex128


def zpf(Vbus, Sbus, Ibus, Ybus, pq, pv, ref, pqpv, tol=1e-9, max_ter=100):
    """

    Args:
        Vbus:
        Sbus:
        Ibus:
        Ybus:
        pq:
        pv:
        ref:
        pqpv:
        tol:

    Returns:

    """

    # reduced impedance matrix
    Zred = factorized(Ybus[pqpv, :][:, pqpv])

    # slack currents
    Ivd = Ybus[pqpv, :][:, ref].dot(Vbus[ref])
    print('Ivd', np.vstack(Ivd))

    # slack voltages influence
    Ck = Zred(Ivd)
    print('Ck', np.vstack(Ck))
    # make a copy of the voltage for convergence control
    Vprev = Vbus[pqpv].copy()

    # Voltage module in the pv nodes
    Vpv = abs(Vbus[pv])

    # admittance matrix to compute the reactive power
    Ybus_pv = Ybus[pv, :][:, pv]

    # approximate the currents with the current voltage solution
    Ik = conj(Sbus[pqpv] / Vprev) + Ibus[pqpv]
    print('Sred', np.vstack(Sbus[pqpv]))
    print('Ik', np.vstack(Ik))

    # compute the new voltage solution
    Vk = Zred(Ik) - Ck
    print('Vk', np.vstack(Vk))

    # compute the voltage solution maximum difference
    diff = max(abs(Vprev - Vk))

    iter = 1
    while diff > tol and iter < max_ter:

        # make a copy of the voltage for convergence control
        Vprev = Vk

        # approximate the currents with the current voltage solution
        Ik = conj(Sbus[pqpv] / Vprev) + Ibus[pqpv]

        # compute the new voltage solution
        Vk = Zred(Ik) - Ck
        print(iter, 'Vk', Vk)
        print()
        # tune PV nodes
        #  ****** USE A reduced pv, pv, pqpv mapping!
        # Vk[pv] *= Vpv / abs(Vk[pv])
        # Qpv = (Vk * conj(Ybus[pv, :][:, pv].dot(Vk) - Ibus))[pv].imag
        # Sbus[pv] = Sbus[pv].real + 1j * Qpv

        # compute the voltage solution maximum difference
        diff = max(abs(Vprev - Vk))

        # Assign the reduced voltage solution to the complete voltage solution
        # voltage = Vbus.copy()  # the slack voltages are kept
        # voltage[pqpv] = Vk
        # compute the power mismatch: this is the true equation solution check
        # Scalc = voltage * conj(Ybus * voltage - Ibus)
        # mis = Scalc - Sbus  # complex power mismatch
        # diff = linalg.norm(r_[mis[pv].real, mis[pq].real, mis[pq].imag], Inf)

        iter += 1

    # Assign the reduced voltage solution to the complete voltage solution
    voltage = Vbus.copy()  # the slack voltages are kept
    voltage[pqpv] = Vk

    print(iter, 'voltage:\n', np.vstack(voltage))
    print()

    # compute the power mismatch: this is the true equation solution check
    Scalc = voltage * conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    normF = linalg.norm(r_[mis[pv].real, mis[pq].real, mis[pq].imag], Inf)

    print('Iter: ', iter)

    return voltage, normF


if __name__ == '__main__':
    from GridCal.Engine.calculation_engine import *

    grid = MultiCircuit()
    grid.load_file('lynn5buspq.xlsx')
    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('C:\\Users\\spenate\Documents\\PROYECTOS\\Monash\\phase0\\Grid\\Monash University.xlsx')
    # grid.load_file('D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE_14.xlsx')
    grid.compile()

    circuit = grid.circuits[0]

    print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
    print('\nYseries:\n', circuit.power_flow_input.Yseries.todense())
    print('\nYshunt:\n', circuit.power_flow_input.Yshunt)
    print('\nSbus:\n', circuit.power_flow_input.Sbus)
    print('\nIbus:\n', circuit.power_flow_input.Ibus)
    print('\nVbus:\n', circuit.power_flow_input.Vbus)
    print('\ntypes:\n', circuit.power_flow_input.types)
    print('\npq:\n', circuit.power_flow_input.pq)
    print('\npv:\n', circuit.power_flow_input.pv)
    print('\nvd:\n', circuit.power_flow_input.ref)

    import time

    print('Z-Gaus-Seidel')
    start_time = time.time()

    v, err = zpf(Vbus=circuit.power_flow_input.Vbus,
                 Sbus=circuit.power_flow_input.Sbus,
                 Ibus=circuit.power_flow_input.Ibus,
                 Ybus=circuit.power_flow_input.Ybus,
                 pq=circuit.power_flow_input.pq,
                 pv=circuit.power_flow_input.pv,
                 ref=circuit.power_flow_input.ref,
                 pqpv=circuit.power_flow_input.pqpv)

    print("--- %s seconds ---" % (time.time() - start_time))

    print('V module:\t', np.abs(v))
    print('V angle: \t', np.angle(v))
    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('V module:\t', np.abs(vnr))
    print('V angle: \t', np.angle(vnr))
    print('error: \t', circuit.power_flow_results.error)

    # check
    print('\ndiff:\t', v - vnr)