import os

import VeraGridEngine.api as gce


def test_copy():
    list_grids = ['IEEE14_types_test.gridcal',
                  'IEEE30-27_29_1.gridcal',
                  'IEEE39_trafo.gridcal',
                  'IEEE118-1_3_1-3_5_1.gridcal']
    for lg in list_grids:

        fname = os.path.join('data', 'grids', lg)

        original_circuit = gce.FileOpen(fname).open()
        copy_of_circuit = original_circuit.copy()

        original_circuit.set_snapshot_time_unix(0)
        copy_of_circuit.set_snapshot_time_unix(0)

        for o1, o2 in zip(original_circuit.items(), copy_of_circuit.items()):
            assert id(o1) != id(o2)

        ok, logger = original_circuit.compare_circuits(copy_of_circuit, skip_internals=True)
        assert ok