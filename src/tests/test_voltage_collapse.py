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
