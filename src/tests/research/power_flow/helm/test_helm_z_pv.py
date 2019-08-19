import time

import numpy as np

from research.power_flow.helm.helm_z_pv import helmz
from matplotlib import pyplot as plt
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_runnable \
    import PowerFlow
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options \
    import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType
from tests.research.power_flow.helm.get_grid_lynn_5_bus_wiki import \
    get_grid_lynn_5_bus_wiki


def test_helm_z_pv():
    grid = get_grid_lynn_5_bus_wiki()

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

    print('HELM-Z')
    start_time = time.time()
    cmax = 25
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helmz(admittances=circuit.power_flow_input.Ybus,
                              slackIndices=circuit.power_flow_input.ref,
                              maxcoefficientCount=cmax,
                              powerInjections=circuit.power_flow_input.Sbus,
                              voltageSetPoints=circuit.power_flow_input.Vbus,
                              types=circuit.power_flow_input.types,
                              eps=1e-9,
                              usePade=True,
                              inherited_pv=None)
    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)
    print('V module:\t', abs(V1))
    print('V angle: \t', np.angle(V1))
    print('error: \t', best_err)
    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False,
                               tolerance=1e-9)
    power_flow = PowerFlow(grid, options)
    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage
    print('V module:\t', abs(vnr))
    print('V angle: \t', np.angle(vnr))
    print('error: \t', circuit.power_flow_results.error)
    # check
    print('\ndiff:\t', V1 - vnr)
    plt.show()
