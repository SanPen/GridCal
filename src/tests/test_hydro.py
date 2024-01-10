import os
from GridCalEngine.api import *

np.set_printoptions(linewidth=10000)


def test_hydro_opf1():

    fname = os.path.join('data', 'grids', 'hydro_grid1.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    results = np.array([[1.0, 10.0],
                        [1.0, 10.0],
                        [1.0, 10.0],
                        [1.0, 10.0],
                        [1.0, 10.0]])

    assert np.allclose(opf_driv.results.generator_power, results)


def test_hydro_opf2():

    fname = os.path.join('data', 'grids', 'hydro_grid2.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    p_results = np.array([[11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [15.993758, -4.993758, 4.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0],
                          [11.248439, -1.248439, 1.0]])

    l_results = np.array([[0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.224742, 0.224742, 0.224742],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185],
                          [0.056185, 0.056185, 0.056185]])

    assert np.allclose(opf_driv.results.generator_power, p_results)
    assert np.allclose(opf_driv.results.fluid_path_flow, l_results)


def test_hydro_opf3():

    fname = os.path.join('data', 'grids', 'hydro_grid3.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    p_results = np.array([[11.11111111, -1.11111111, 1.0],
                          [13.33333333, -3.33333333, 3.0],
                          [11.11111111, -1.11111111, 1.0],
                          [11.11111111, -1.11111111, 1.0],
                          [11.11111111, -1.11111111, 1.0]])

    l_results = np.array([[1., -0.05, 0.05555556],
                          [1., -0.15, 0.16666667],
                          [1., -0.05, 0.05555556],
                          [1., -0.05, 0.05555556],
                          [1., -0.05, 0.05555556]])

    assert np.allclose(opf_driv.results.generator_power, p_results)
    assert np.allclose(opf_driv.results.loading, l_results)


def test_hydro_opf4():

    fname = os.path.join('data', 'grids', 'hydro_grid4.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()


if __name__ == '__main__':
    test_hydro_opf1()
    test_hydro_opf2()
    test_hydro_opf3()
    test_hydro_opf4()
