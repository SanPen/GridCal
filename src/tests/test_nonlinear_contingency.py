# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from VeraGridEngine.api import *


def test_non_linear_factors() -> None:
    """

    :return:
    """
    # navigate to the grids folder
    fname = os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw')
    main_circuit = FileOpen(fname).open()

    # Check results, run pf with line out
    line_idx_test = 10

    # generate the contingency
    con_group = ContingencyGroup()
    con = Contingency(idtag='',
                      device=main_circuit.lines[line_idx_test],
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
    nl_options = ContingencyAnalysisOptions(pf_options=pf_options,
                                            contingency_method=ContingencyMethod.PowerFlow)

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

    # Check results ----------------------------------------------------------------------------------------------------

    # check that the power flow effectivelly failed the indicated line
    assert pf.results.Sf[line_idx_test] == 0

    # check that the contingency analisys effectivelly failed the indicated line
    assert nl_simulation.results.Sf[0, line_idx_test] == 0

    # check that the contingency and the "manual contingency" voltage are the same
    Vcont = abs(nl_simulation.results.voltage)
    Vexact = abs(pf.results.voltage)
    assert np.allclose(Vexact, Vcont[0, :], atol=1e-3)


if __name__ == '__main__':
    test_non_linear_factors()
