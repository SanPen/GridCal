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

    # Check results, run pf with line out
    line_idx_test = 10

    # generate the contingency
    con_group = ContingencyGroup()
    con = Contingency(idtag='',
                      device_idtag=main_circuit.lines[line_idx_test].idtag,
                      group=con_group)
    main_circuit.add_contingency_group(con_group)
    main_circuit.add_contingency(con)

    # ------------------------------------------------------------------------------------------------------------------
    # run a HELM power flow
    # ------------------------------------------------------------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # ------------------------------------------------------------------------------------------------------------------
    # run a "full" contingency analysis with the same power flow options
    # ------------------------------------------------------------------------------------------------------------------
    nl_options = ContingencyAnalysisOptions(distributed_slack=False,
                                            pf_options=pf_options,
                                            engine=ContingencyEngine.PowerFlow)

    # lmc = LinearMultiContingencies(grid=main_circuit)
    nl_simulation = ContingencyAnalysisDriver(grid=main_circuit,
                                              options=nl_options,
                                              linear_multiple_contingencies=None)
    nl_simulation.run()

    main_circuit.lines[line_idx_test].active = False

    # re-run the power flow after disconnecting a line -----------------------------------------------------------------
    pf_options = PowerFlowOptions(SolverType.HELM,
                                  verbose=False,
                                  retry_with_other_methods=True)
    pf = PowerFlowDriver(main_circuit, pf_options)
    pf.run()

    # Print results ----------------------------------------------------------------------------------------------------

    # check that the power flow effectivelly failed the indicated line
    assert pf.results.Sf[line_idx_test] == 0

    # check that the contingency analisys effectivelly failed the indicated line
    assert nl_simulation.results.Sf[0, line_idx_test] == 0

    # check that the contingency and the "manual contingency" voltage are the same
    Vcont = abs(nl_simulation.results.voltage)
    Vexact = abs(pf.results.voltage)
    assert np.allclose(Vexact, Vcont[0, :], atol=1e-3)

    return True


if __name__ == '__main__':
    test_non_linear_factors()
