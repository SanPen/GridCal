import os
from GridCalEngine.api import *


def test_non_linear_factors():
    # Prepare simulation
    # get the directory of this file
    current_path = os.path.dirname(__file__)

    # navigate to the grids folder
    grids_path = os.path.join(current_path, 'data', 'grids')
    fname = os.path.join(grids_path, 'RAW', 'IEEE 30 bus.raw')
    main_circuit = FileOpen(fname).open()

    # run a HELM power flow --------------------------------------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Run the nonlinear factors calculation ----------------------------------------------------------------------------
    nl_options = ContingencyAnalysisOptions(distributed_slack=False,
                                            correct_values=True,
                                            pf_options=pf.options)
    lmc = LinearMultiContingencies(grid=main_circuit)
    nl_simulation = ContingencyAnalysisDriver(grid=main_circuit, options=nl_options, linear_multiple_contingencies=lmc)
    nl_simulation.run()

    # Check results, run pf with line out
    line_idx_test = 10

    main_circuit.lines[line_idx_test].active = False

    # re-run the power flow after disconnecting a line -----------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Print results ----------------------------------------------------------------------------------------------------
    Vcont = abs(nl_simulation.results.voltage)
    Vexact = abs(pf.results.voltage)

    print('V when disconnecting first branch: ')
    print(Vcont[:, line_idx_test])

    print('V with full precision: ')
    print(Vexact)

    print('Absolute error: ')
    err = Vexact - Vcont[:, line_idx_test]
    print(err)

    print('Max error: ')
    print(max(err))

    return True


if __name__ == '__main__':
    test_non_linear_factors()
