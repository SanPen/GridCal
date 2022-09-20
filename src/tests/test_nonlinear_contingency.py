from GridCal.Engine import *


def test_ptdf():

    # Prepare simulation
    fname = os.path.join('src', 'tests', 'data', 'grids', 'IEEE 30 bus.raw')
    main_circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(SolverType.HELM,
                                   verbose=False,
                                   retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Run with nonlinear factors
    nl_options = NonLinearAnalysisOptions(distribute_slack=False, correct_values=True, pf_results=pf.results)
    nl_simulation = NonLinearAnalysisDriver(grid=main_circuit, options=nl_options)
    nl_simulation.run()

    # Check results, run pf with line out
    line_idx_test = 13

    main_circuit.lines[line_idx_test].active = False

    pf_options = PowerFlowOptions(SolverType.HELM,
                                   verbose=False,
                                   retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Print results
    Vcont = abs(nl_simulation.results.V_cont)
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
    test_ptdf()

