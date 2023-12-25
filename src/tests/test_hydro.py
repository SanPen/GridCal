import os
from GridCalEngine.api import *

np.set_printoptions(linewidth=10000)


def test_hydro_opf():

    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'hydro_grid1.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    results = np.array([[8.0, 3.0],
                        [8.0, 3.0],
                        [8.0, 3.0],
                        [8.0, 3.0],
                        [8.0, 3.0]])

    assert np.allclose(opf_driv.results.generator_power, results)


if __name__ == '__main__':
    test_hydro_opf()
