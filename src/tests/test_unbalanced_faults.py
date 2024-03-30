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

from GridCalEngine.api import *
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.enumerations import FaultType


def test_unbalanced_short_circuit():
    """
    Example 10.6b from Hadi Saadat - Power System Analysis (pag 498)
    Single line-to-ground fault at bus 3 through a fault impedance Zj = jO.1
    """

    fname = os.path.join('data', 'grids', '5bus_Saadat.xlsx')
    grid = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                                  verbose=False,  # Verbose option where available
                                  tolerance=1e-6,  # power error in p.u.
                                  max_iter=25,  # maximum iteration number
                                  )
    pf = PowerFlowDriver(grid, pf_options)
    pf.run()

    sc_options = ShortCircuitOptions(bus_index=2,
                                     fault_type=FaultType.LG)

    sc = ShortCircuitDriver(grid,
                            options=sc_options,
                            pf_options=pf_options,
                            pf_results=pf.results)
    sc.run()

    print('\t|V0|:', np.abs(sc.results.voltage0))
    print('\t|V1|:', np.abs(sc.results.voltage1))
    print('\t|V2|:', np.abs(sc.results.voltage2))

    vm0 = np.abs(sc.results.voltage0)
    vm1 = np.abs(sc.results.voltage1)
    vm2 = np.abs(sc.results.voltage2)

    vm0_book = [0.12844037, 0.05963303, 0.32110092, 0.09633028, 0.0]
    vm1_book = [0.88073394, 0.88990826, 0.79816514, 0.92844037, 0.93394495]
    vm2_book = [0.11926606, 0.11009174, 0.20183486, 0.07155963, 0.06605505]

    v0_ok = np.allclose(vm0, vm0_book, atol=1e-2)
    v1_ok = np.allclose(vm1, vm1_book, atol=1e-2)
    v2_ok = np.allclose(vm2, vm2_book, atol=1e-2)

    assert v0_ok
    assert v1_ok
    assert v2_ok


if __name__ == '__main__':
    test_unbalanced_short_circuit()

