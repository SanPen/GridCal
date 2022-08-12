# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os

import numpy as np

from GridCal.Engine import *


def test_unbalanced_short_circuit():
    # example 10.6b from Hadi Saadat - Power System Analysis

    fname = os.path.join('data', 'grids', '5bus_Saadat')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                            verbose=False,  # Verbose option where available
                            tolerance=1e-6,  # power error in p.u.
                            max_iter=25,  # maximum iteration number
                            )
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
    # print(power_flow.results.get_report_dataframe())
    ####################################################################################################################
    # Short circuit
    ####################################################################################################################
    print('\n\n')
    print('Short Circuit')
    sc_options = ShortCircuitOptions(bus_index=[2], fault_type=FaultType.LG)
    sc = ShortCircuitDriver(main_circuit, options=sc_options, pf_options=pf_options, pf_results=power_flow.results)
    sc.run()
    print('\n\n', main_circuit.name)
    print('\t|V0|:', abs(sc.results.voltage0))
    print('\t|V1|:', abs(sc.results.voltage1))
    print('\t|V2|:', abs(sc.results.voltage2))

    V0_book = [0.12844037, 0.05963303, 0.32110092, 0.09633028, 0.0]
    V1_book = [0.88073394, 0.88990826, 0.79816514, 0.92844037, 0.93394495]
    V2_book = [0.11926606, 0.11009174, 0.20183486, 0.07155963, 0.06605505]

    v0_ok = np.allclose(sc.results.voltage0, V0_book, atol=1e-3)
    v1_ok = np.allclose(sc.results.voltage1, V1_book, atol=1e-3)
    v2_ok = np.allclose(sc.results.voltage2, V2_book, atol=1e-3)

    assert v0_ok
    assert v1_ok
    assert v2_ok


if __name__ == '__main__':
    test_unbalanced_short_circuit()

