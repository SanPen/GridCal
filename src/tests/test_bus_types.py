import os

import numpy as np

import GridCal.Engine as gce


def test_1():
    fname = os.path.join('data', 'grids', 'IEEE14_types_test.gridcal')
    circuit = gce.FileOpen(fname).open()
    sn_nc = gce.compile_numerical_circuit_at(circuit)

    # snapshot types
    sn_types = sn_nc.bus_types

    # the first time step does not change the generator status, hence it should be equal to the snapshot
    expected = [3, 2, 2, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, sn_types))
