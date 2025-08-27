# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import numpy as np

from VeraGridEngine.api import *


def test_short_circuit():

    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(solver_type=SolverType.NR, verbose=0, control_q=False)
    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()
    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sf|:', abs(power_flow.results.Sf))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())
    ####################################################################################################################
    # Short circuit
    ####################################################################################################################
    print('\n\n')
    print('Short Circuit')
    sc_options = ShortCircuitOptions(bus_index=16)
    # grid, options, pf_options:, pf_results:
    sc = ShortCircuitDriver(grid=main_circuit, options=sc_options, pf_options=pf_options, pf_results=power_flow.results)
    sc.run()
    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(sc.results.voltage1))
    print('\t|Sf|:', abs(sc.results.Sf1))
    print('\t|loading|:', abs(sc.results.loading1) * 100)


if __name__ == '__main__':
    test_short_circuit()
