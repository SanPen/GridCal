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

    p_total = 1910.0

    assert np.allclose(np.sum(opf_driv.results.generator_power), p_total)


def test_hydro_opf_ieee39():

    fname = os.path.join('data', 'grids', 'hydro_grid_IEEE39.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    l_results = np.array([[49.855986, 0, 50.144014, 50.0, 0, 0, 50.0],
                          [49.711971, 0, 50.288029, 50.0, 0, 0, 50.0],
                          [49.567957, 0, 50.432043, 50.0, 0, 0, 50.0],
                          [49.423942, 0, 50.576058, 50.0, 0, 0, 50.0],
                          [49.279928, 0, 50.720072, 50.0, 0, 0, 50.0],
                          [49.135914, 0, 50.864086, 50.0, 0, 0, 50.0],
                          [48.991899, 0, 51.008101, 50.0, 0, 0, 50.0],
                          [48.847885, 0, 51.152115, 50.0, 0, 0, 50.0],
                          [48.703870, 0, 51.296130, 50.0, 0, 0, 50.0],
                          [48.559856, 0, 51.440144, 50.0, 0, 0, 50.0]])

    assert np.allclose(opf_driv.results.fluid_node_current_level / 1e6, l_results)


def test_hydro_opf_simple1():
    fname = os.path.join('data', 'grids', 'hydro_simple1.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    l_results = np.array([[99999820, 180.018],
                          [99999640, 360.036],
                          [99999460, 540.05401],
                          [99999280, 720.07201],
                          [99999100, 900.09001],
                          [99998920, 1080.108],
                          [99998740, 1260.126],
                          [99998560, 1440.144],
                          [99998380, 1620.162],
                          [99998200, 1800.18]])

    p_results = np.array([[10.0],
                          [10.0],
                          [10.0],
                          [10.0],
                          [10.0],
                          [10.0],
                          [10.0],
                          [10.0],
                          [10.0],
                          [10.0]])

    assert np.allclose(opf_driv.results.fluid_node_current_level, l_results)
    assert np.allclose(opf_driv.results.generator_power, p_results)


def test_hydro_opf_simple2():
    fname = os.path.join('data', 'grids', 'hydro_simple2.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    p_results = np.array([[19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098],
                          [19.756098, -9.756098]])

    assert np.allclose(opf_driv.results.generator_power, p_results)


def test_hydro_opf_simple3():
    fname = os.path.join('data', 'grids', 'hydro_simple3.gridcal')
    main_circuit = FileOpen(fname).open()
    opf_driv = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

    opf_driv.run()

    p_results = np.array([[11.0, 0.0],
                          [11.0, 0.0],
                          [11.0, 0.0],
                          [11.0, 0.0],
                          [14.0, 0.0],
                          [11.0, 0.0],
                          [11.0, 0.0],
                          [11.0, 0.0],
                          [11.0, 0.0],
                          [11.0, 0.0]])

    l_results = np.array([[49.999868, 50.000132],
                          [49.999736, 50.000264],
                          [49.999604, 50.000396],
                          [49.999472, 50.000528],
                          [49.999304, 50.000696],
                          [49.999172, 50.000828],
                          [49.999040, 50.000960],
                          [49.998908, 50.001092],
                          [49.998776, 50.001224],
                          [49.998644, 50.001356]])

    assert np.allclose(opf_driv.results.generator_power, p_results)


if __name__ == '__main__':
    test_hydro_opf1()
    test_hydro_opf2()
    test_hydro_opf3()
    test_hydro_opf4()
    test_hydro_opf_ieee39()
    test_hydro_opf_simple1()
    test_hydro_opf_simple2()
    test_hydro_opf_simple3()
