import os
from GridCalEngine.api import *

np.set_printoptions(linewidth=10000)


def test_hydro_opf1():

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


def test_hydro_opf2():

    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'hydro_grid2.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    p_results = np.array([[10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.55561729, 5.55561729],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346],
                          [10., -0.11112346, 1.11112346]])

    l_results = np.array([[1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.03704115, -0.37037449],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749],
                          [1., 0.00740823, -0.0740749]])

    assert np.allclose(opf_driv.results.generator_power, p_results)
    assert np.allclose(opf_driv.results.loading, l_results)


if __name__ == '__main__':
    test_hydro_opf1()
    test_hydro_opf2()
