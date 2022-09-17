from GridCal.Engine import *


def test_ptdf():
    fname = os.path.join('src', 'tests', 'data', 'grids', 'IEEE 30 bus.raw')
    main_circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(SolverType.HELM,
                                   verbose=False,
                                   retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    nl_options = NonLinearAnalysisOptions(distribute_slack=False, correct_values=False, pf_results=pf.results)
    nl_simulation = NonLinearAnalysisDriver(grid=main_circuit, options=nl_options)
    nl_simulation.run()

    print('Finished!')

    # lodf: open a line and save the pu variation of P in the lines
    # ptdf: open a line and save the pu variation of P in the buses

    # 1: solve power flow with all lines OK
    # 2: compute the new voltages with HELM
    # 3: post-process to get the powers: V(YV)* for ptdf, Vf(Yf V)* for lodf (check power_flow_post_process)
    # 4: also store the voltages
    # 5: get Sbus, Sf, and voltages, and from here, ptdf and lodf


    return True


if __name__ == '__main__':
    test_ptdf()

