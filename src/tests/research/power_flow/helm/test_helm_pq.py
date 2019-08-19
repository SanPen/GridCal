from numpy.ma.core import angle

from research.power_flow.helm.helm_pq import helm_pq
from tests.research.power_flow.helm.get_grid_lynn_5_bus_wiki import \
    get_grid_lynn_5_bus_wiki


def test_helm_pq():
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
    v, err = helm_pq(Vbus=circuit.power_flow_input.Vbus,
                     Sbus=circuit.power_flow_input.Sbus,
                     Ibus=circuit.power_flow_input.Ibus,
                     Ybus=circuit.power_flow_input.Ybus,
                     Yserie=circuit.power_flow_input.Yseries,
                     Ysh=circuit.power_flow_input.Yshunt,
                     pq=circuit.power_flow_input.pq,
                     pv=circuit.power_flow_input.pv,
                     ref=circuit.power_flow_input.ref,
                     pqpv=circuit.power_flow_input.pqpv)
    print('helm')
    print('V module:\t', abs(v))
    print('V angle: \t', angle(v))
    print('error: \t', err)
    # check the HELM solution: v against the NR power flow
    # print('\nNR')
    # options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
    # power_flow = PowerFlow(grid, options)
    # power_flow.run()
    # vnr = circuit.power_flow_results.voltage
    #
    # print('V module:\t', abs(vnr))
    # print('V angle: \t', angle(vnr))
    # print('error: \t', circuit.power_flow_results.error)
    #
    # # check
    # print('\ndiff:\t', v - vnr)
