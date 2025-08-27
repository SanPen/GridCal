# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
from VeraGridEngine.api import *


def test_opf():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    print('Running OPF...', '')
    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF)
    opf = OptimalPowerFlowDriver(grid=main_circuit, options=opf_options)
    opf.run()


def test_opf_ts():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    print('Running OPF-TS...', '')

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          time_grouping=TimeGrouping.Daily,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # run the opf time series
    opf_ts = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                              options=opf_options,
                                              time_indices=main_circuit.get_all_time_indices())
    opf_ts.run()

    # check that no error or warning is generated
    assert opf_ts.logger.error_count() == 0
    assert opf_ts.logger.warning_count() == 0


def test_opf_ts_batt_concatenation():
    """

    :return:
    """
    fname = os.path.join('data', 'grids', 'IEEE39_1W_batt.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    print('Running OPF-TS...', '')

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          time_grouping=TimeGrouping.Daily,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # run the opf time series
    opf_ts = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                              options=opf_options,
                                              time_indices=main_circuit.get_all_time_indices())
    opf_ts.run()

    p_rise_lim = main_circuit.batteries[0].Pmax
    p_redu_lim = main_circuit.batteries[0].Pmin

    batt_energy = opf_ts.results.battery_energy[:, 0]

    tol = power_flow_options.tolerance
    # no dt calculated as it is always 1.0 hours
    for i in range(1, len(batt_energy)):
        assert batt_energy[i - 1] + p_rise_lim + tol >= batt_energy[i] >= batt_energy[i - 1] + p_redu_lim - tol


def test_opf_ts_hydro_concatenation():
    """

    :return:
    """
    fname = os.path.join('data', 'grids', 'IEEE39_1W_hydro.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    print('Running OPF-TS...', '')

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          time_grouping=TimeGrouping.Daily,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # run the opf time series
    opf_ts = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                              options=opf_options,
                                              time_indices=main_circuit.get_all_time_indices())
    opf_ts.run()

    p_path0_max = main_circuit.fluid_paths[0].max_flow
    p_path0_min = main_circuit.fluid_paths[0].min_flow

    l_node0 = opf_ts.results.fluid_node_current_level[:, 0]

    tol = power_flow_options.tolerance
    # no dt calculated as it is always 1.0 hours
    for i in range(1, len(l_node0)):
        assert l_node0[i - 1] - p_path0_max * 3600 + tol <= l_node0[i] <= l_node0[i - 1] + p_path0_min * 3600 - tol


def test_opf_hvdc():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # HVDC dispatch on
    main_circuit.hvdc_lines[0].dispatchable = True

    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()

    pf_on = opf.results.hvdc_Pf[0]

    # HVDC dispatch off
    main_circuit.hvdc_lines[0].dispatchable = False

    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()

    pf_off = opf.results.hvdc_Pf[0]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf_on != pf_off
    assert np.isclose(pf_off, 0.0, atol=1e-5)


def test_opf_gen():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # Gen dispatch on
    main_circuit.generators[0].enabled_dispatch = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pgen_on = opf.results.generator_power[0]

    # Gen dispatch off
    main_circuit.generators[0].enabled_dispatch = False
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pgen_off = opf.results.generator_power[0]

    # Gen dispatch back on
    main_circuit.generators[0].enabled_dispatch = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pgen_on2 = opf.results.generator_power[0]

    assert opf.logger.error_count() == 0
    assert pgen_on != pgen_off
    assert np.isclose(pgen_on, pgen_on2, atol=1e-10)


def test_opf_line_monitoring():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # branch 2 monitoring on
    br_idx = 2
    main_circuit.lines[br_idx].monitor_loading = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_on = opf.results.Sf[br_idx]

    # HVDC dispatch off
    main_circuit.lines[br_idx].monitor_loading = False
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_off = opf.results.Sf[br_idx]

    # HVDC dispatch back on
    main_circuit.lines[br_idx].monitor_loading = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_on2 = opf.results.Sf[br_idx]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf_on != pf_off
    assert np.isclose(pf_on, pf_on2, atol=1e-10)


def test_opf_hvdc_controls():
    """
    Checks that an HVDC line in Pset mode is dispatched exactly
    Checks the free mode is different from the dispatch mode
    Checks that the Pset mod in dispatchable is lower than the rate
    :return:
    """
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True,
                                          # export_model_fname="test_opf_hvdc_controls.lp"
                                          )

    # HVDC free mode
    main_circuit.hvdc_lines[0].control_mode = HvdcControlType.type_0_free
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_free = opf.results.hvdc_Pf[0]

    # HVDC Pset mode
    main_circuit.hvdc_lines[0].control_mode = HvdcControlType.type_1_Pset
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_pset = opf.results.hvdc_Pf[0]

    assert abs(pf_pset) <= main_circuit.hvdc_lines[0].rate

    # HVDC Pset mode non dispatchable
    main_circuit.hvdc_lines[0].dispatchable = False
    main_circuit.hvdc_lines[0].control_mode = HvdcControlType.type_1_Pset
    main_circuit.hvdc_lines[0].Pset = 50  # MW
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_pset2 = opf.results.hvdc_Pf[0]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf_free != pf_pset
    assert np.isclose(pf_pset2, 50, atol=1e-5)


def test_opf_trafo_controls():
    fname = os.path.join('data', 'grids', 'IEEE39_trafo.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=0,
                                          control_q=False,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.HIGHS,
                                          generate_report=True)

    # trafo fixed
    main_circuit.transformers2w[0].tap_phase_control_mode = TapPhaseControl.fixed
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf1 = opf.results.Sf[48]

    # trafo controlling
    main_circuit.transformers2w[0].tap_phase_control_mode = TapPhaseControl.Pf
    main_circuit.transformers2w[0].tap_phase_control_mode = TapPhaseControl.Pf
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf2 = opf.results.Sf[48]

    # trafo back to fixed
    main_circuit.transformers2w[0].tap_phase_control_mode = TapPhaseControl.fixed
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf3 = opf.results.Sf[48]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf1 != pf2
    assert np.isclose(pf1, pf3, atol=1e-3)


def test_opf_generation_shedding():
    """
    This test, checks that a fixed generator is shed appropriately
    to match the load in the grid and copper plate modes
    """
    grid = MultiCircuit()
    grid.create_profiles(steps=10, step_length=1, step_unit="h")

    bus1 = grid.add_bus(Bus(name="bus1", Vnom=10))
    load1 = grid.add_load(bus=bus1, api_obj=Load(name="load1", Cost=10000.0))

    load1.P_prof = np.array([10, 12, 10, 12, 10, 12, 10, 12, 10, 12])

    gen1 = grid.add_generator(bus=bus1, api_obj=Generator(name="gen1", enabled_dispatch=False, Cost=15.0))

    gen1.P_prof = np.array([12, 12, 12, 12, 12, 12, 12, 12, 12, 12])

    # GRID MODE
    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF)
    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    expected_shedding = gen1.P_prof.toarray() - load1.P_prof.toarray()

    assert np.allclose(driver.results.generator_shedding[:, 0], expected_shedding)

    # COPPER PLATE MODE
    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          zonal_grouping=ZonalGrouping.All,
                                          export_model_fname=None  # "test_opf_gen_shedding_copper_plate.lp"
                                          )

    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    expected_shedding = gen1.P_prof.toarray() - load1.P_prof.toarray()

    assert np.allclose(driver.results.generator_shedding[:, 0], expected_shedding)


def test_opf_battery_shedding():
    """
    This test, checks that a fixed battery is shed appropriately
    to match the load in the grid and copper plate modes
    """
    grid = MultiCircuit()
    grid.create_profiles(steps=10, step_length=1, step_unit="h")

    bus1 = grid.add_bus(Bus(name="bus1", Vnom=10))
    load1 = grid.add_load(bus=bus1, api_obj=Load(name="load1", Cost=10000.0))

    load1.P_prof = np.array([10, 12, 10, 12, 10, 12, 10, 12, 10, 12])

    gen1 = grid.add_battery(bus=bus1, api_obj=Battery(name="gen1", enabled_dispatch=False, Cost=15.0))

    gen1.P_prof = np.array([12, 12, 12, 12, 12, 12, 12, 12, 12, 12])

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          zonal_grouping=ZonalGrouping.NoGrouping, )

    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    # since we do not store the battery shedding, we check that the battery is exactly what we need
    assert np.allclose(driver.results.battery_power[:, 0], load1.P_prof.toarray())

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          zonal_grouping=ZonalGrouping.All, )

    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    assert np.allclose(driver.results.battery_power[:, 0], load1.P_prof.toarray())


def test_opf_load_shedding():
    """
    This test, checks that a load is shed appropriately because of a generator constraint
    """
    grid = MultiCircuit()
    grid.create_profiles(steps=10, step_length=1, step_unit="h")

    bus1 = grid.add_bus(Bus(name="bus1", Vnom=10))
    load1 = grid.add_load(bus=bus1, api_obj=Load(name="load1", Cost=10000.0))

    load1.P_prof = np.array([10, 12, 10, 12, 10, 12, 10, 12, 10, 12])

    gen1 = grid.add_generator(bus=bus1, api_obj=Generator(name="gen1", enabled_dispatch=True, Cost=15.0, Pmax=10))

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          zonal_grouping=ZonalGrouping.NoGrouping,
                                          # export_model_fname="test_opf_load_shedding.lp"
                                          )

    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    expected_load = np.array([10, 10, 10, 10, 10, 10, 10, 10, 10, 10])
    expected_shedding = np.array([0, 2, 0, 2, 0, 2, 0, 2, 0, 2])

    # since we do not store the battery shedding, we check that the battery is exactly what we need
    assert np.allclose(driver.results.load_shedding[:, 0], expected_shedding)
    assert np.allclose(driver.results.load_power[:, 0], expected_load)


def test_opf_load_shedding_because_of_line():
    """
    This test, checks that a load is shed appropriately because of the line rate constraint and higher cost
    """
    grid = MultiCircuit()
    grid.create_profiles(steps=10, step_length=1, step_unit="h")

    bus1 = grid.add_bus(Bus(name="bus1", Vnom=10))
    bus2 = grid.add_bus(Bus(name="bus1", Vnom=10))

    grid.add_line(obj=Line(bus_from=bus1, bus_to=bus2, name="L12", rate=10, cost=20000.0))

    gen1 = grid.add_generator(bus=bus1, api_obj=Generator(name="gen1", enabled_dispatch=True, Cost=15.0, Pmax=15))

    load1 = grid.add_load(bus=bus2, api_obj=Load(name="load1", Cost=10000.0))
    load1.P_prof = np.array([10, 12, 10, 12, 10, 12, 10, 12, 10, 12])

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          zonal_grouping=ZonalGrouping.NoGrouping,
                                          # export_model_fname="test_opf_load_shedding.lp"
                                          )

    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    expected_load = np.array([10, 10, 10, 10, 10, 10, 10, 10, 10, 10])
    expected_shedding = np.array([0, 2, 0, 2, 0, 2, 0, 2, 0, 2])

    # since we do not store the battery shedding, we check that the battery is exactly what we need
    assert np.allclose(driver.results.load_shedding[:, 0], expected_shedding)
    assert np.allclose(driver.results.load_power[:, 0], expected_load)


def test_opf_load_not_shedding_because_of_line():
    """
    This test, checks that a load does not shed, and the line overloads,
    because the line overload cost is lower than the load shed cost
    """
    grid = MultiCircuit()
    grid.create_profiles(steps=10, step_length=1, step_unit="h")

    bus1 = grid.add_bus(Bus(name="bus1", Vnom=10))
    bus2 = grid.add_bus(Bus(name="bus1", Vnom=10))

    grid.add_line(obj=Line(bus_from=bus1, bus_to=bus2, name="L12", rate=10, cost=2000.0))

    gen1 = grid.add_generator(bus=bus1, api_obj=Generator(name="gen1", enabled_dispatch=True, Cost=15.0, Pmax=15))

    load1 = grid.add_load(bus=bus2, api_obj=Load(name="load1", Cost=10000.0))
    load1.P_prof = np.array([10, 12, 10, 12, 10, 12, 10, 12, 10, 12])

    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF,
                                          zonal_grouping=ZonalGrouping.NoGrouping,
                                          # export_model_fname="test_opf_load_shedding.lp"
                                          )

    driver = OptimalPowerFlowTimeSeriesDriver(grid=grid, options=opf_options)
    driver.run()

    expected_overload = np.array([0, 2, 0, 2, 0, 2, 0, 2, 0, 2])
    expected_shedding = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    # since we do not store the battery shedding, we check that the battery is exactly what we need
    assert np.allclose(driver.results.load_shedding[:, 0], expected_shedding)
    assert np.allclose(driver.results.load_power[:, 0], load1.P_prof.toarray())
    assert np.allclose(driver.results.overloads[:, 0], -expected_overload)


if __name__ == '__main__':
    # test_opf()
    test_opf_generation_shedding()
    test_opf_battery_shedding()
