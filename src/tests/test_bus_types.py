import os

import numpy as np

import GridCal.Engine as gce


def test_1():
    fname = os.path.join('data', 'grids', 'IEEE14_types_test.gridcal')
    circuit = gce.FileOpen(fname).open()
    sn_nc = gce.compile_snapshot_circuit(circuit)
    ts_nc = gce.compile_time_circuit(circuit)

    # snapshot types
    sn_types = sn_nc.bus_types

    # the first time step does not change the generator status, hence it should be equal to the snapshot
    ts_types = ts_nc.bus_data.bus_types_prof[:, 0]
    expected = [3, 2, 2, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, ts_types))

    # the second time step deactivates generator 3_1
    ts_types = ts_nc.bus_data.bus_types_prof[:, 1]
    expected = [3, 2, 1, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, ts_types))

    # the third time step deactivates generator 3_1 and 1_1 (the generator of the slack bus,
    # but because the bus is marked as slack it remains the slack)
    ts_types = ts_nc.bus_data.bus_types_prof[:, 2]
    expected = [3, 2, 1, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, ts_types))

    # the third time step deactivates generator 3_1, 1_1 and 6_1
    ts_types = ts_nc.bus_data.bus_types_prof[:, 3]
    expected = [3, 2, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, ts_types))

    # deactivated bus 2 (index 1)
    ts_types = ts_nc.bus_data.bus_types_prof[:, 4]
    expected = [3, 1, 2, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, ts_types))

    print()
