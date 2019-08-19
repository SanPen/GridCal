from research.power_flow.helm.helm_vect_asu import helm, res_2_df
import time
from matplotlib import pyplot as plt
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_runnable \
    import PowerFlow
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options \
    import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType
from tests.research.power_flow.helm.get_grid_lynn_5_bus_wiki import \
    get_grid_lynn_5_bus_wiki


def test_helm_vect_asu():
    grid = get_grid_lynn_5_bus_wiki()

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
    # Y, Ys, Ysh, max_coefficient_count, S, voltage_set_points, pq, pv, vd
    v, err = helm(Y=circuit.power_flow_input.Ybus,
                  Ys=circuit.power_flow_input.Yseries,
                  Ysh=circuit.power_flow_input.Yshunt,
                  max_coefficient_count=30,
                  S=circuit.power_flow_input.Sbus,
                  voltage_set_points=circuit.power_flow_input.Vbus,
                  pq=circuit.power_flow_input.pq,
                  pv=circuit.power_flow_input.pv,
                  vd=circuit.power_flow_input.ref,
                  eps=1e-15)
    print('HEM:')
    print("--- %s seconds ---" % (time.time() - start_time))
    print('Results:\n', res_2_df(v, circuit.power_flow_input.Sbus,
                                 circuit.power_flow_input.types))
    print('error: \t', err)
    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False,
                               tolerance=1e-9, control_q=False)
    power_flow = PowerFlow(grid, options)
    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage
    print('Results:\n', res_2_df(vnr, circuit.power_flow_input.Sbus,
                                 circuit.power_flow_input.types))
    print('error: \t', circuit.power_flow_results.error)
    # check
    print('\ndiff:\t', v - vnr)
    plt.show()
