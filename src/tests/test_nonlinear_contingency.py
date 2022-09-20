from GridCal.Engine import *


def test_ptdf():

    # Prepare simulation
    # get the directory of this file
    current_path = os.path.dirname(__file__)

    # navigate to the grids folder
    grids_path = os.path.join(current_path, 'data', 'grids')
    fname = os.path.join(grids_path, 'IEEE 30 bus.raw')
    main_circuit = FileOpen(fname).open()

    # run a HELM power flow --------------------------------------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # -----------------------------------------------------------------------------------------------------------------

    # CASE A) Run the nonlinear factors calculation for a set of branches
    discon_branches_idx = [[11, 14], [12, 17]]  # combinations of lines we decide
    nl_options = NonLinearAnalysisOptions(distribute_slack=False,
                                          correct_values=True,
                                          pf_results=pf.results,
                                          branches_sets=discon_branches_idx)
    nl_simulation = NonLinearAnalysisDriver(grid=main_circuit, options=nl_options)
    nl_simulation.run()

    # Check results, run pf with set of lines out
    set_selected = 0  # for instance
    for branch_idx in discon_branches_idx[set_selected]:  # disconnect the involved lines
        main_circuit.lines[branch_idx].active = False

    # re-run the power flow after disconnecting a line -----------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Print results ----------------------------------------------------------------------------------------------------
    Vcont = abs(nl_simulation.results.V_cont)
    Vexact = abs(pf.results.voltage)

    print('V when disconnecting a set of lines: ')
    print(Vcont[:, set_selected])

    print('V with full precision: ')
    print(Vexact)

    print('Absolute error: ')
    err = Vexact - Vcont[:, set_selected]
    print(err)

    print('Max error: ')
    print(max(err))

    # -----------------------------------------------------------------------------------------------------------------

    # CASE B) Run the nonlinear factors calculation for one line at a time -> branches_sets = None
    nl_options = NonLinearAnalysisOptions(distribute_slack=False,
                                          correct_values=True,
                                          pf_results=pf.results,
                                          branches_sets=None)
    nl_simulation = NonLinearAnalysisDriver(grid=main_circuit, options=nl_options)
    nl_simulation.run()

    # Check results, run pf with set of lines out
    line_selected = 12  # for instance
    main_circuit.lines[line_selected].active = False

    # re-run the power flow after disconnecting a line -----------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Print results ----------------------------------------------------------------------------------------------------
    Vcont = abs(nl_simulation.results.V_cont)
    Vexact = abs(pf.results.voltage)

    print('V when disconnecting a given line: ')
    print(Vcont[:, line_selected])

    print('V with full precision: ')
    print(Vexact)

    print('Absolute error: ')
    err = Vexact - Vcont[:, line_selected]
    print(err)

    print('Max error: ')
    print(max(err))

    return True


if __name__ == '__main__':
    test_ptdf()

