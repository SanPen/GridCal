"""
Method implemented from the article:
Online voltage stability assessment for load areas based on the holomorphic embedding method
by Chengxi Liu, Bin Wang, Fengkai Hu, Kai Sun and Claus Leth Bak

Implemented by Santiago Peñate Vera 2018
This implementation computes W[n] for all the buses outside the system matrix leading to better results
"""
import time

import numpy as np
from numpy import complex128

from GridCal.Engine.IO import FileOpen
from GridCal.Engine.Simulations.PowerFlow.helm_power_flow import res_2_df, \
    helm_vanilla
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options import \
    PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType
from research.three_phase.Engine import PowerFlow

np.set_printoptions(linewidth=32000, suppress=False)

# Set the complex precision to use
complex_type = complex128


if __name__ == '__main__':
    file_name = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'

    grid = FileOpen(file_name).open()

    grid.compile()

    circuit = grid.circuits[0]

    print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
    print('\nSbus:\n', circuit.power_flow_input.Sbus)
    print('\nIbus:\n', circuit.power_flow_input.Ibus)
    print('\nVbus:\n', circuit.power_flow_input.Vbus)
    print('\ntypes:\n', circuit.power_flow_input.types)
    print('\npq:\n', circuit.power_flow_input.pq)
    print('\npv:\n', circuit.power_flow_input.pv)
    print('\nvd:\n', circuit.power_flow_input.ref)

    start_time = time.time()

    v, err = helm_vanilla(Vbus=circuit.power_flow_input.Vbus,
                          Sbus=circuit.power_flow_input.Sbus,
                          # Ibus=circuit.power_flow_input.Ibus,
                          Ybus=circuit.power_flow_input.Ybus,
                          pq=circuit.power_flow_input.pq,
                          pv=circuit.power_flow_input.pv,
                          ref=circuit.power_flow_input.ref,
                          pqpv=circuit.power_flow_input.pqpv)

    print('HEM:')
    print("--- %s seconds ---" % (time.time() - start_time))
    print('Results:\n', res_2_df(v, circuit.power_flow_input.Sbus, circuit.power_flow_input.types))
    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, tolerance=1e-9, control_q=False)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('Results:\n', res_2_df(vnr, circuit.power_flow_input.Sbus, circuit.power_flow_input.types))
    print('error: \t', circuit.power_flow_results.error)

    # check
    print('\ndiff:\t', v - vnr)
