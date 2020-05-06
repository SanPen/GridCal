# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import os
import numpy as np

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.ContinuationPowerFlow.voltage_collapse_driver import \
    VoltageCollapseOptions, VoltageCollapseInput, VoltageCollapse
from tests.conftest import ROOT_PATH


def test_voltage_collapse(root_path=ROOT_PATH):
    """

    :param root_path:
    :return:
    """
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'grid_2_islands.xlsx')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    vc_options = VoltageCollapseOptions()
    # just for this test
    numeric_circuit = main_circuit.compile_snapshot()
    numeric_inputs = numeric_circuit.compute()
    Sbase = np.zeros(len(main_circuit.buses), dtype=complex)
    Vbase = np.zeros(len(main_circuit.buses), dtype=complex)
    for c in numeric_inputs:
        Sbase[c.original_bus_idx] = c.Sbus
        Vbase[c.original_bus_idx] = c.Vbus
    unitary_vector = -1 + 2 * np.random.random(len(main_circuit.buses))
    # unitary_vector = random.random(len(grid.buses))
    vc_inputs = VoltageCollapseInput(Sbase=Sbase,
                                     Vbase=Vbase,
                                     Starget=Sbase * (1 + unitary_vector))
    vc = VoltageCollapse(circuit=main_circuit, options=vc_options,
                         inputs=vc_inputs)
    vc.run()
    # vc.results.plot()

    fname = root_path / 'data' / 'output' / 'test_demo_5_node.png'
    print(fname)
    # plt.savefig(fname=fname)


if __name__ == '__main__':
    test_voltage_collapse(root_path=ROOT_PATH)
