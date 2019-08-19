import time

from matplotlib import pyplot as plt

from GridCal.Engine.Core import MultiCircuit, NumericalCircuit
from research.power_flow.helm.helm_chengxi_2 import helm_, res_2_df
from tests.research.power_flow.helm.get_grid_lynn_5_bus_wiki import \
    get_grid_lynn_5_bus_wiki
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_runnable import \
    PowerFlow
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options import \
    PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType


def test_chengxi_2():
    grid: MultiCircuit = get_grid_lynn_5_bus_wiki()
    numerical_circuit: NumericalCircuit = grid.numerical_circuit

    print('\nYbus:\n', numerical_circuit.Ybus.todense())
    print('\nSbus:\n', grid.Sbus)
    print('\nIbus:\n', grid.Ibus)
    print('\nVbus:\n', grid.Vbus)
    print('\ntypes:\n', grid.types)
    print('\npq:\n', grid.pq)
    print('\npv:\n', grid.pv)
    print('\nvd:\n', grid.ref)
    start_time = time.time()
    v, err = helm_(
        Vbus=grid.Vbus,
        Sbus=grid.Sbus,
        Ibus=grid.Ibus,
        Ybus=grid.Ybus,
        pq=grid.pq,
        pv=grid.pv,
        ref=grid.ref,
        pqpv=grid.pqpv
    )
    print('HELM Chengxi:')
    print("--- %s seconds ---" % (time.time() - start_time))
    print('Results:\n', res_2_df(v, grid.Sbus,
                                 grid.types))
    print('error: \t', err)
    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False,
                               tolerance=1e-9, control_q=False)
    power_flow = PowerFlow(grid, options)
    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = grid.voltage
    print('Results:\n', res_2_df(vnr, grid.Sbus,
                                 grid.types))
    print('error: \t', grid.power_flow_results.error)

    # check
    print('\ndiff:\t', v - vnr)
    plt.show()
