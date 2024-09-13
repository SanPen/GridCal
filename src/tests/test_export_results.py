import os
import GridCalEngine.api as gce


def test_export_results():
    """
    Test that the results export works
    :return:
    """
    fname = os.path.join("data", "grids", "IEEE39_1W.gridcal")

    grid = gce.open_file(fname)

    # create the driver
    pf_driver = gce.PowerFlowTimeSeriesDriver(grid=grid,
                                              options=gce.PowerFlowOptions(),
                                              time_indices=grid.get_all_time_indices())
    # run
    pf_driver.run()

    power_flow_options = gce.PowerFlowOptions(gce.SolverType.NR,
                                              verbose=0,
                                              control_q=False,
                                              retry_with_other_methods=False)

    opf_options = gce.OptimalPowerFlowOptions(verbose=0,
                                              solver=gce.SolverType.LINEAR_OPF,
                                              power_flow_options=power_flow_options,
                                              time_grouping=gce.TimeGrouping.Daily,
                                              mip_solver=gce.MIPSolvers.CBC,
                                              generate_report=True)

    # run the opf time series
    opf_ts_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=grid,
                                                         options=opf_options,
                                                         time_indices=grid.get_all_time_indices())
    opf_ts_driver.run()

    gce.export_drivers(drivers_list=[pf_driver, opf_ts_driver],
                       file_name="IEEE39_1W_results.zip")
